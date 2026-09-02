#!/usr/bin/env python3
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration

from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from mavros_msgs.msg import State as MavState
from mavros_msgs.srv import CommandBool, SetMode
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from tf2_ros import Buffer, TransformListener


SENSOR_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE
)

def quat_to_rotmat(qx, qy, qz, qw):
    """
    Convert quaternion (x,y,z,w) -> 3x3 rotation matrix.
    Assumes quaternion is normalized (ROS tf usually is).
    """
    xx = qx * qx
    yy = qy * qy
    zz = qz * qz
    xy = qx * qy
    xz = qx * qz
    yz = qy * qz
    wx = qw * qx
    wy = qw * qy
    wz = qw * qz

    return np.array([
        [1.0 - 2.0*(yy + zz),     2.0*(xy - wz),         2.0*(xz + wy)],
        [    2.0*(xy + wz),   1.0 - 2.0*(xx + zz),       2.0*(yz - wx)],
        [    2.0*(xz - wy),       2.0*(yz + wx),     1.0 - 2.0*(xx + yy)]
    ], dtype=float)

def tf_to_mat(t):
    """
    geometry_msgs/Transform -> 4x4 homogeneous matrix, pure numpy
    """
    T = np.eye(4, dtype=float)
    R = quat_to_rotmat(
        t.rotation.x,
        t.rotation.y,
        t.rotation.z,
        t.rotation.w
    )
    T[:3, :3] = R
    T[0, 3] = t.translation.x
    T[1, 3] = t.translation.y
    T[2, 3] = t.translation.z
    return T


class ForwardReturnPrecland(Node):
    def __init__(self):
        super().__init__('forward_return_precland')

        # ---------- Params ----------
        self.declare_parameter('takeoff_alt', 2.5)
        self.declare_parameter('forward_distance', 2.0)
        self.declare_parameter('forward_vx', 1.0)
        self.declare_parameter('return_xy_kp', 0.6)
        self.declare_parameter('return_vmax', 0.6)
        self.declare_parameter('alt_kp', 0.8)
        self.declare_parameter('alt_vz_max', 0.7)
        self.declare_parameter('tag_stable_frames', 4)
        self.declare_parameter('precland_timeout_s', 30.0)
        self.declare_parameter('camera_frame', 'camera_link')
        self.declare_parameter('base_link', 'base_link')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('tag_frame', 'tag36h11:0')
        self.declare_parameter('use_tf_extrinsic', True)
        self.declare_parameter('external_camera', False)
        self.declare_parameter('debug', True)

        # precision landing tuning
        self.declare_parameter('xy_kp', 0.5)
        self.declare_parameter('xy_vmax', 0.5)
        self.declare_parameter('xy_tol', 0.05)
        self.declare_parameter('descent_vz', -0.3)     # negative = go down if z is up
        self.declare_parameter('land_alt_threshold', 0.15)

        # pull params
        self.takeoff_alt         = float(self.get_parameter('takeoff_alt').value)
        self.forward_distance    = float(self.get_parameter('forward_distance').value)
        self.forward_vx          = float(self.get_parameter('forward_vx').value)
        self.return_xy_kp        = float(self.get_parameter('return_xy_kp').value)
        self.return_vmax         = float(self.get_parameter('return_vmax').value)
        self.alt_kp              = float(self.get_parameter('alt_kp').value)
        self.alt_vz_max          = float(self.get_parameter('alt_vz_max').value)
        self.tag_stable_frames   = int(self.get_parameter('tag_stable_frames').value)
        self.precland_timeout_s  = float(self.get_parameter('precland_timeout_s').value)
        self.camera_frame        = str(self.get_parameter('camera_frame').value)
        self.base_link           = str(self.get_parameter('base_link').value)
        self.map_frame           = str(self.get_parameter('map_frame').value)
        self.tag_frame           = str(self.get_parameter('tag_frame').value)
        self.use_tf_extrinsic    = bool(self.get_parameter('use_tf_extrinsic').value)
        self.external_camera     = bool(self.get_parameter('external_camera').value)
        self.debug               = bool(self.get_parameter('debug').value)

        self.xy_kp               = float(self.get_parameter('xy_kp').value)
        self.xy_vmax             = float(self.get_parameter('xy_vmax').value)
        self.xy_tol              = float(self.get_parameter('xy_tol').value)
        self.descent_vz          = float(self.get_parameter('descent_vz').value)
        self.land_alt_threshold  = float(self.get_parameter('land_alt_threshold').value)

        # ---------- States ----------
        # IDLE -> TAKEOFF -> FORWARD -> RETURN_HOME -> LOCK_TAG -> PRECISION_LAND -> DONE
        self.IDLE, self.TAKEOFF, self.FORWARD, self.RETURN_HOME, self.LOCK_TAG, self.PRECISION_LAND, self.DONE = range(7)
        self.state = self.IDLE

        # ---------- MAVROS ----------
        self.mav_state = MavState()
        self.have_local_pose = False
        self.current_pose_enu = None
        self.home_pose_enu = None
        self.forward_start_pose_enu = None

        self.state_sub = self.create_subscription(MavState, '/mavros/state', self._state_cb, 10)
        self.odom_sub  = self.create_subscription(Odometry, '/mavros/local_position/odom', self._odom_cb, qos_profile=SENSOR_QOS)
        self.pose_sub  = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self._pose_cb, qos_profile=SENSOR_QOS)

        self.cmd_vel_pub = self.create_publisher(Twist, '/mavros/setpoint_velocity/cmd_vel_unstamped', 10)

        self.arm_cli  = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.mode_cli = self.create_client(SetMode, '/mavros/set_mode')

        # ---------- TF listener ----------
        self.tf_buf = Buffer()
        self.tf_listener = TransformListener(self.tf_buf, self)

        # tag tracking
        self.tag_visible_frames = 0
        self._last_body_vec = None  # tag pos in base_link: [x_fwd, y_left, z_up]

        # command streaming
        self.last_cmd = Twist()
        self.keepalive_timer = self.create_timer(0.05, self._keepalive_tick)  # 20 Hz
        self.logic_timer     = self.create_timer(0.05, self._logic_tick)      # 20 Hz

        self.landing_deadline = None

        self.get_logger().info("forward_return_precland node ready.")

    # ---------- Callbacks ----------
    def _state_cb(self, msg: MavState):
        self.mav_state = msg

    def _odom_cb(self, msg: Odometry):
        self.have_local_pose = True
        self.current_pose_enu = msg.pose.pose  # geometry_msgs/Pose

    def _pose_cb(self, msg: PoseStamped):
        self.have_local_pose = True
        self.current_pose_enu = msg.pose       # geometry_msgs/Pose

    # ---------- Timers ----------
    def _keepalive_tick(self):
        self.cmd_vel_pub.publish(self.last_cmd)

    def _logic_tick(self):
        # update tag info every tick
        if self._update_tag_vector():
            self.tag_visible_frames = min(self.tag_visible_frames + 1, 1000)
        else:
            self.tag_visible_frames = max(0, self.tag_visible_frames - 1)

        if not self.have_local_pose:
            return

        current_alt = float(self.current_pose_enu.position.z)

        # ---- STATE MACHINE ----
        if self.state == self.IDLE:
            # arm + set OFFBOARD, record home
            self.last_cmd = Twist()
            self._maybe_set_mode('OFFBOARD')
            self._maybe_arm(True)

            if self.mav_state.armed and self.mav_state.mode == 'OFFBOARD':
                self.home_pose_enu = self._copy_pose(self.current_pose_enu)
                self.state = self.TAKEOFF
                self.get_logger().info("→ TAKEOFF")

        elif self.state == self.TAKEOFF:
            # climb to takeoff_alt
            vz = 0.8 if current_alt < self.takeoff_alt - 0.1 else 0.0
            cmd = Twist()
            cmd.linear.z = vz
            self.last_cmd = cmd

            if current_alt >= self.takeoff_alt - 0.05:
                self.forward_start_pose_enu = self._copy_pose(self.current_pose_enu)
                self.last_cmd = Twist()
                self.state = self.FORWARD
                self.get_logger().info("Reached takeoff altitude. → FORWARD")

        elif self.state == self.FORWARD:
            # move in +x until forward_distance reached
            cmd = Twist()
            cmd.linear.x = float(self.forward_vx)

            # hold altitude while moving forward
            alt_err = self.takeoff_alt - current_alt
            vz_cmd = self.alt_kp * alt_err
            vz_cmd = max(-self.alt_vz_max, min(self.alt_vz_max, vz_cmd))
            cmd.linear.z = float(vz_cmd)

            dx = self.current_pose_enu.position.x - self.forward_start_pose_enu.position.x
            dy = self.current_pose_enu.position.y - self.forward_start_pose_enu.position.y
            dist_xy = math.hypot(dx, dy)

            if dist_xy >= self.forward_distance:
                cmd.linear.x = 0.0
                self.state = self.RETURN_HOME
                self.get_logger().info(f"Forward distance ~{dist_xy:.2f} m reached. → RETURN_HOME")

            self.last_cmd = cmd

        elif self.state == self.RETURN_HOME:
            # drive back to home XY, hold altitude
            cmd = Twist()

            ex = self.home_pose_enu.position.x - self.current_pose_enu.position.x
            ey = self.home_pose_enu.position.y - self.current_pose_enu.position.y

            vx_cmd = self.return_xy_kp * ex
            vy_cmd = self.return_xy_kp * ey

            # clamp
            vx_cmd = max(-self.return_vmax, min(self.return_vmax, vx_cmd))
            vy_cmd = max(-self.return_vmax, min(self.return_vmax, vy_cmd))

            cmd.linear.x = float(vx_cmd)
            cmd.linear.y = float(vy_cmd)

            # altitude hold
            alt_err = self.takeoff_alt - current_alt
            vz_cmd = self.alt_kp * alt_err
            vz_cmd = max(-self.alt_vz_max, min(self.alt_vz_max, vz_cmd))
            cmd.linear.z = float(vz_cmd)

            self.last_cmd = cmd

            dist_home_xy = math.hypot(ex, ey)
            if dist_home_xy < 0.05:
                # we're basically at home spot, now lock tag
                self.state = self.LOCK_TAG
                self.get_logger().info("Back at home XY. → LOCK_TAG")

        elif self.state == self.LOCK_TAG:
            # hover, wait for stable tag before landing
            cmd = Twist()

            # altitude hold
            alt_err = self.takeoff_alt - current_alt
            vz_cmd = self.alt_kp * alt_err
            vz_cmd = max(-self.alt_vz_max, min(self.alt_vz_max, vz_cmd))
            cmd.linear.z = float(vz_cmd)

            cmd.linear.x = 0.0
            cmd.linear.y = 0.0

            self.last_cmd = cmd

            if self.tag_visible_frames >= self.tag_stable_frames and self._last_body_vec is not None:
                self.landing_deadline = self.get_clock().now() + Duration(seconds=self.precland_timeout_s)
                self.state = self.PRECISION_LAND
                self.get_logger().info("Tag locked. → PRECISION_LAND")

        elif self.state == self.PRECISION_LAND:
            # precision landing phase using tag vector in base_link

            if self.landing_deadline is not None and self.get_clock().now() > self.landing_deadline:
                self.get_logger().warn("Landing timeout. Disarming.")
                self.last_cmd = Twist()
                self._maybe_arm(False)
                self.state = self.DONE
                return

            cmd = Twist()

            if self._last_body_vec is None:
                # lost tag -> hold position, don't descend
                self.get_logger().warn("Lost tag during PRECISION_LAND, holding.")
                self.last_cmd = Twist()
                return

            # tag position in base_link (x fwd, y left, z up)
            ex = float(self._last_body_vec[0])  # forward/back error
            ey = float(self._last_body_vec[1])  # left/right error

            # horizontal centering toward tag
            vx_cmd = self.xy_kp * ex      # drive forward/back to kill ex
            vy_cmd = self.xy_kp * ey      # drive left/right to kill ey
            vx_cmd = max(-self.xy_vmax, min(self.xy_vmax, vx_cmd))
            vy_cmd = max(-self.xy_vmax, min(self.xy_vmax, vy_cmd))
            cmd.linear.x = float(vx_cmd)
            cmd.linear.y = float(vy_cmd)

            # only descend if mostly centered
            lateral_err = math.hypot(ex, ey)
            if lateral_err < self.xy_tol:
                cmd.linear.z = float(self.descent_vz)   # descend (negative if z up)
            else:
                cmd.linear.z = 0.0

            self.last_cmd = cmd

            # touchdown check
            if current_alt <= self.land_alt_threshold:
                self.get_logger().info("Touchdown. Disarming.")
                self.last_cmd = Twist()
                self._maybe_arm(False)
                self.state = self.DONE

        elif self.state == self.DONE:
            self.last_cmd = Twist()
            # stay here

    # ---------- tag TF math ----------
    def _update_tag_vector(self):
        """
        Update self._last_body_vec with tag position (in meters)
        expressed in the drone's base_link frame.
        Return True if successful this cycle.
        """

        # camera -> tag from apriltag
        try:
            t_cam_tag = self.tf_buf.lookup_transform(
                self.camera_frame,
                self.tag_frame,
                rclpy.time.Time()
            )
        except Exception:
            return False

        T_cam_tag = tf_to_mat(t_cam_tag.transform)

        if self.external_camera:
            # case: camera not on drone, need map->camera and map->base_link
            try:
                t_map_cam = self.tf_buf.lookup_transform(self.map_frame, self.camera_frame, rclpy.time.Time())
                T_map_cam = tf_to_mat(t_map_cam.transform)

                t_map_bl = self.tf_buf.lookup_transform(self.map_frame, self.base_link, rclpy.time.Time())
                T_map_bl = tf_to_mat(t_map_bl.transform)
            except Exception:
                return False

            # base_link -> tag = inv(map->base_link) * (map->camera * camera->tag)
            T_bl_tag = np.linalg.inv(T_map_bl) @ (T_map_cam @ T_cam_tag)
            p_bl = T_bl_tag[:3, 3]
        else:
            # case: camera mounted on drone
            p_cam = T_cam_tag[:3, 3]

            if self.use_tf_extrinsic:
                try:
                    t_bl_cam = self.tf_buf.lookup_transform(self.base_link, self.camera_frame, rclpy.time.Time())
                    T_bl_cam = tf_to_mat(t_bl_cam.transform)
                    p_bl_h = T_bl_cam @ np.array([p_cam[0], p_cam[1], p_cam[2], 1.0])
                    p_bl = p_bl_h[:3]
                except Exception:
                    # fallback assume camera ~= base_link
                    p_bl = p_cam
            else:
                p_bl = p_cam

        self._last_body_vec = p_bl.astype(float)
        return True

    # ---------- helpers for PX4/MAVROS ----------
    def _maybe_arm(self, arm: bool):
        if not self.arm_cli.service_is_ready():
            self.arm_cli.wait_for_service(timeout_sec=0.0)
        if (arm and not self.mav_state.armed) or ((not arm) and self.mav_state.armed):
            req = CommandBool.Request()
            req.value = arm
            self.arm_cli.call_async(req)

    def _maybe_set_mode(self, mode_str: str):
        if not self.mode_cli.service_is_ready():
            self.mode_cli.wait_for_service(timeout_sec=0.0)
        if self.mav_state.mode != mode_str:
            req = SetMode.Request()
            req.custom_mode = mode_str
            self.mode_cli.call_async(req)

    @staticmethod
    def _copy_pose(p):
        from geometry_msgs.msg import Pose
        q = Pose()
        q.position.x = p.position.x
        q.position.y = p.position.y
        q.position.z = p.position.z
        q.orientation = p.orientation
        return q


def main():
    rclpy.init()
    node = ForwardReturnPrecland()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
