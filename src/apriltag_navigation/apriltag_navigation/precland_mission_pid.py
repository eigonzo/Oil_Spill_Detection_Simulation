# #!/usr/bin/env python3
# import rclpy
# from rclpy.node import Node
# import numpy as np
# from geometry_msgs.msg import Point, PoseStamped, Twist
# from apriltag_msgs.msg import AprilTagDetectionArray
# from nav_msgs.msg import Odometry
# from mavros_msgs.msg import State as MavState
# from mavros_msgs.srv import CommandBool, SetMode
# from tf2_ros import TransformException
# from tf2_ros.buffer import Buffer
# from tf2_ros.transform_listener import TransformListener
# import math

# # Define proper QoS profiles
# SENSOR_QOS = rclpy.qos.QoSProfile(
#     depth=10,
#     reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT,
#     durability=rclpy.qos.DurabilityPolicy.VOLATILE,
# )

# CONTROL_QOS = rclpy.qos.QoSProfile(
#     depth=10,
#     reliability=rclpy.qos.ReliabilityPolicy.RELIABLE,
#     durability=rclpy.qos.DurabilityPolicy.VOLATILE,
# )

# class SimpleAprilTagLanding(Node):
#     def __init__(self):
#         super().__init__('simple_apriltag_landing')
        
#         # --- Parameters ---
#         self.declare_parameter('takeoff_alt', 2.0)
#         self.declare_parameter('kp_xy', 0.3)
#         self.declare_parameter('kp_z', 0.2)
#         self.declare_parameter('max_xy_vel', 0.5)
#         self.declare_parameter('max_z_vel', 0.3)
#         self.declare_parameter('desired_alt_above_tag', 1.0)
#         self.declare_parameter('xy_tolerance', 0.1)
#         self.declare_parameter('z_tolerance', 0.1)
#         self.declare_parameter('tag_id', 0)
#         self.declare_parameter('debug', True)
        
#         # Get parameters
#         self.takeoff_alt = float(self.get_parameter('takeoff_alt').value)
#         self.kp_xy = float(self.get_parameter('kp_xy').value)
#         self.kp_z = float(self.get_parameter('kp_z').value)
#         self.max_xy_vel = float(self.get_parameter('max_xy_vel').value)
#         self.max_z_vel = float(self.get_parameter('max_z_vel').value)
#         self.desired_alt_above_tag = float(self.get_parameter('desired_alt_above_tag').value)
#         self.xy_tolerance = float(self.get_parameter('xy_tolerance').value)
#         self.z_tolerance = float(self.get_parameter('z_tolerance').value)
#         self.tag_id_ = self.get_parameter('tag_id').value
#         self.debug_ = self.get_parameter('debug').value
        
#         # TF listener
#         self.tf_buffer = Buffer()
#         self.tf_listener = TransformListener(self.tf_buffer, self)
        
#         # Drone state
#         self.mav_state = MavState()
#         self.have_odom = False
#         self.altitude = 0.0
#         self.position = [0.0, 0.0, 0.0]
        
#         # Tag tracking
#         self.tag_detected = False
#         self.tag_position = [0.0, 0.0, 0.0]  # In camera frame
#         self.last_tag_time = self.get_clock().now()
        
#         # Control state machine
#         self.IDLE, self.TAKEOFF, self.SEARCH, self.TRACK, self.LAND, self.FINISHED = range(6)
#         self.state = self.IDLE
        
#         # State management variables
#         self.consecutive_detections = 0
#         self.consecutive_timeouts = 0
#         self.alignment_counter = 0
        
#         # Last commands
#         self.last_cmd = Twist()
        
#         # --- Publishers ---
#         self.cmd_vel_pub = self.create_publisher(
#             Twist, 
#             "/mavros/setpoint_velocity/cmd_vel_unstamped", 
#             CONTROL_QOS
#         )
        
#         # --- Subscribers ---
#         self.tags_sub_ = self.create_subscription(
#             AprilTagDetectionArray,
#             '/detections',
#             self.tags_callback,
#             10
#         )
#         self.state_sub = self.create_subscription(
#             MavState, 
#             "/mavros/state", 
#             self._state_cb, 
#             10
#         )
#         self.odom_sub = self.create_subscription(
#             Odometry,
#             "/mavros/local_position/odom",
#             self._odom_cb,
#             SENSOR_QOS
#         )
        
#         # --- Services ---
#         self.arm_cli = self.create_client(CommandBool, "/mavros/cmd/arming")
#         self.mode_cli = self.create_client(SetMode, "/mavros/set_mode")
        
#         # --- Timers ---
#         self.control_timer = self.create_timer(0.1, self._control_loop)
        
#         self.get_logger().info(f"🚀 Simple AprilTag Landing - Tracking tag ID: {self.tag_id_}")
#         self.get_logger().info(f"📊 Parameters: kp_xy={self.kp_xy}, kp_z={self.kp_z}, max_xy_vel={self.max_xy_vel}")

#     def tags_callback(self, msg):
#         """Process AprilTag detections"""
#         if not msg.detections:
#             self.tag_detected = False
#             return
            
#         for tag in msg.detections:
#             if tag.id == self.tag_id_:
#                 try:
#                     transform = self.tf_buffer.lookup_transform(
#                         'camera_link',  # Source frame
#                         f'tag36h11:{self.tag_id_}',  # Target frame
#                         rclpy.time.Time()
#                     )
                    
#                     # Get position from transform
#                     self.tag_position[0] = transform.transform.translation.x
#                     self.tag_position[1] = transform.transform.translation.y
#                     self.tag_position[2] = transform.transform.translation.z
                    
#                     self.tag_detected = True
#                     self.last_tag_time = self.get_clock().now()
                    
#                     if self.debug_ and self.get_clock().now().nanoseconds % 2e9 < 1e8:
#                         self.get_logger().info(
#                             f"📏 Tag {self.tag_id_}: x={self.tag_position[0]:.3f}, "
#                             f"y={self.tag_position[1]:.3f}, z={self.tag_position[2]:.3f}"
#                         )
                    
#                     break
                    
#                 except TransformException as e:
#                     if self.debug_:
#                         self.get_logger().warn(f"TF lookup failed: {e}")
#                     self.tag_detected = False

#     def _state_cb(self, msg: MavState):
#         self.mav_state = msg

#     def _odom_cb(self, msg: Odometry):
#         self.have_odom = True
#         self.altitude = float(msg.pose.pose.position.z)
#         self.position[0] = msg.pose.pose.position.x
#         self.position[1] = msg.pose.pose.position.y
#         self.position[2] = msg.pose.pose.position.z

#     def _maybe_arm(self, arm: bool):
#         if not self.arm_cli.service_is_ready():
#             return
#         if (arm and not self.mav_state.armed) or ((not arm) and self.mav_state.armed):
#             req = CommandBool.Request()
#             req.value = arm
#             self.arm_cli.call_async(req)

#     def _maybe_set_mode(self, mode_str: str):
#         if not self.mode_cli.service_is_ready():
#             return
#         if self.mav_state.mode != mode_str:
#             req = SetMode.Request()
#             req.custom_mode = mode_str
#             self.mode_cli.call_async(req)

#     def _check_tag_timeout(self):
#         """Check if we've lost tag detection for too long"""
#         current_time = self.get_clock().now()
#         time_since_tag = (current_time - self.last_tag_time).nanoseconds / 1e9
#         return time_since_tag > 5.0

#     def _compute_control_command(self):
#         """Simple P-control based on tag position"""
#         cmd = Twist()
        
#         if self.state == self.IDLE:
#             self._maybe_set_mode('OFFBOARD')
#             self._maybe_arm(True)
            
#             if self.mav_state.armed and self.mav_state.mode == 'OFFBOARD':
#                 self.state = self.TAKEOFF
#                 self.get_logger().info("✅ ARMED and OFFBOARD → TAKEOFF")
                
#         elif self.state == self.TAKEOFF:
#             if self.altitude < (self.takeoff_alt - 0.1):
#                 cmd.linear.z = 0.8
#                 if self.debug_ and self.get_clock().now().nanoseconds % 2e9 < 1e8:
#                     self.get_logger().info(f"🛫 TAKEOFF: {self.altitude:.2f}m / {self.takeoff_alt:.2f}m")
#             else:
#                 cmd.linear.z = 0.0
#                 self.state = self.SEARCH
#                 self.get_logger().info("🔍 SEARCH: Reached altitude, searching for tag...")
                
#         elif self.state == self.SEARCH:
#             # Small slow search pattern to help find the tag
#             current_time = self.get_clock().now()
#             search_time = (current_time.nanoseconds / 1e9) % 12.0  # 12-second cycle
            
#             if search_time < 3.0:
#                 cmd.linear.x = 0.1
#             elif search_time < 6.0:
#                 cmd.linear.x = -0.1
#             elif search_time < 9.0:
#                 cmd.linear.y = 0.1
#             else:
#                 cmd.linear.y = -0.1
                
#             cmd.linear.z = 0.0
            
#             # Require multiple consecutive detections to switch to TRACK
#             if self.tag_detected:
#                 self.consecutive_detections += 1
                
#                 if self.consecutive_detections >= 3:  # Require 3 consecutive detections
#                     self.state = self.TRACK
#                     self.consecutive_detections = 0
#                     self.consecutive_timeouts = 0
#                     self.get_logger().info("🎯 TRACK: Tag detected consistently, starting precision approach")
#             else:
#                 self.consecutive_detections = 0
                
#             if self.debug_ and self.get_clock().now().nanoseconds % 3e9 < 1e8:
#                 self.get_logger().info("🔍 Still searching for tag...")
                
#         elif self.state == self.TRACK:
#             if self.tag_detected:
#                 # Reset timeout counter when we see the tag
#                 self.consecutive_timeouts = 0
                
#                 # Conservative control with deadzones
#                 tag_x = self.tag_position[0]
#                 tag_y = self.tag_position[1]
#                 tag_z = self.tag_position[2]
                
#                 # Deadzone for small errors to prevent jitter
#                 xy_deadzone = 0.05
#                 if abs(tag_x) > xy_deadzone:
#                     cmd.linear.x = self.kp_xy * tag_x
#                 else:
#                     cmd.linear.x = 0.0
                    
#                 if abs(tag_y) > xy_deadzone:
#                     cmd.linear.y = self.kp_xy * tag_y
#                 else:
#                     cmd.linear.y = 0.0
                
#                 # FIXED: Proper altitude control - if tag_z is larger, we need to descend (negative velocity)
#                 # tag_z = current distance to tag
#                 # desired_alt_above_tag = desired distance to tag
#                 altitude_error = tag_z - self.desired_alt_above_tag
                
#                 # Deadzone for altitude control
#                 if abs(altitude_error) > 0.1:  # 10cm deadzone
#                     # FIXED: Use NEGATIVE gain since we need to descend when tag is far
#                     cmd.linear.z = -self.kp_z * altitude_error
#                 else:
#                     cmd.linear.z = 0.0
                
#                 # Velocity limits
#                 cmd.linear.x = max(min(cmd.linear.x, self.max_xy_vel), -self.max_xy_vel)
#                 cmd.linear.y = max(min(cmd.linear.y, self.max_xy_vel), -self.max_xy_vel)
#                 cmd.linear.z = max(min(cmd.linear.z, self.max_z_vel), -self.max_z_vel)
                
#                 # Check alignment
#                 xy_error = math.sqrt(tag_x**2 + tag_y**2)
#                 z_error = abs(tag_z - self.desired_alt_above_tag)
                
#                 if self.debug_ and self.get_clock().now().nanoseconds % 1e9 < 1e8:
#                     self.get_logger().info(
#                         f"🎯 Tracking: xy_err={xy_error:.2f}m, z_err={z_error:.2f}m, "
#                         f"tag_dist={tag_z:.2f}m, cmd_z={cmd.linear.z:.2f}m/s"
#                     )
                
#                 # Start landing when aligned (require sustained alignment)
#                 if xy_error < self.xy_tolerance and z_error < self.z_tolerance:
#                     self.alignment_counter += 1
                    
#                     if self.alignment_counter >= 10:  # 1 second of good alignment
#                         self.state = self.LAND
#                         self.alignment_counter = 0
#                         self.get_logger().info("🛬 LAND: Starting final descent - aligned with tag!")
#                 else:
#                     self.alignment_counter = 0
                    
#             else:
#                 # Only switch back to SEARCH after multiple timeouts
#                 if self._check_tag_timeout():
#                     self.consecutive_timeouts += 1
                    
#                     if self.consecutive_timeouts >= 3:  # Require 3 timeouts
#                         self.state = self.SEARCH
#                         self.consecutive_timeouts = 0
#                         self.consecutive_detections = 0
#                         self.get_logger().warn("🔍 SEARCH: Lost tag detection consistently")
#                     elif self.debug_:
#                         self.get_logger().warn(f"⚠️  TRACK: Lost tag ({self.consecutive_timeouts}/3 timeouts)")
                
#         elif self.state == self.LAND:
#             if self.tag_detected:
#                 tag_x = self.tag_position[0]
#                 tag_y = self.tag_position[1]
#                 tag_z = self.tag_position[2]
                
#                 # Maintain XY position while descending
#                 cmd.linear.x = self.kp_xy * tag_x
#                 cmd.linear.y = self.kp_xy * tag_y
                
#                 # Slow descent with altitude safety check
#                 if tag_z > 0.5:  # If still reasonably high, descend slowly
#                     cmd.linear.z = -0.2
#                 else:  # When very close to tag, descend very slowly
#                     cmd.linear.z = -0.1
                
#                 # Velocity limits
#                 cmd.linear.x = max(min(cmd.linear.x, self.max_xy_vel), -self.max_xy_vel)
#                 cmd.linear.y = max(min(cmd.linear.y, self.max_xy_vel), -self.max_xy_vel)
                
#                 if self.debug_ and self.get_clock().now().nanoseconds % 2e9 < 1e8:
#                     self.get_logger().info(f"🛬 LANDING: alt={self.altitude:.2f}m, tag_dist={tag_z:.2f}m")
                
#                 # Check if landed
#                 if self.altitude < 0.1:
#                     cmd.linear.z = 0.0
#                     self.state = self.FINISHED
#                     self._maybe_arm(False)  # Disarm after landing
#                     self.get_logger().info("✅ FINISHED: Landed successfully!")
                    
#             else:
#                 # Lost tag during landing - very slow descent or hover
#                 cmd.linear.z = -0.05
#                 if self.debug_ and self.get_clock().now().nanoseconds % 2e9 < 1e8:
#                     self.get_logger().warn("⚠️  LANDING: Lost tag but continuing slow descent")
                
#         elif self.state == self.FINISHED:
#             cmd.linear.x = 0.0
#             cmd.linear.y = 0.0
#             cmd.linear.z = 0.0
            
#         return cmd

#     def _control_loop(self):
#         """Main control loop"""
#         if not self.have_odom:
#             self.get_logger().warn("⏳ Waiting for odometry...")
#             return

#         cmd = self._compute_control_command()
#         self.cmd_vel_pub.publish(cmd)
#         self.last_cmd = cmd

# def main():
#     rclpy.init()
#     node = SimpleAprilTagLanding()
#     try:
#         rclpy.spin(node)
#     except KeyboardInterrupt:
#         node.get_logger().info("🛑 Shutting down...")
#     finally:
#         node.destroy_node()
#         rclpy.shutdown()

# if __name__ == '__main__':
#     main()

#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from mavros_msgs.msg import State as MavState
from mavros_msgs.srv import CommandBool, SetMode

from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from tf2_ros import Buffer, TransformListener


# QoS for MAVROS topics / odom
SENSOR_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def quat_to_yaw(qx, qy, qz, qw):
    s_yaw = 2.0 * (qw * qz + qx * qy)
    c_yaw = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(s_yaw, c_yaw)

def ang_norm(a):
    while a > math.pi:  a -= 2*math.pi
    while a < -math.pi: a += 2*math.pi
    return a


class PrecisionLandMerged(Node):
    def __init__(self):
        super().__init__('precland_merged')

        # ---------------- params ----------------
        # outbound / tag1 routine
        self.declare_parameter('takeoff_alt', 2.0)
        self.declare_parameter('forward_speed', 0.4)             # m/s forward during search
        self.declare_parameter('first_tag_frame', 'tag36h11:1')  # scan tag1 on outbound
        self.declare_parameter('post_detect_forward_time_s', 1.6)# coast forward after detecting tag1

        # vertical actions for tag1 routine
        self.declare_parameter('tag1_descend_m', 1.0)            # descend 1 m
        self.declare_parameter('tag1_descent_rate', 0.3)         # m/s down
        self.declare_parameter('tag1_ascent_rate', 0.4)          # m/s up
        self.declare_parameter('wait_after_sweep_s', 2.0)        # wait 2 s before ascending

        # yaw sweep after descend (tag1 phase)
        self.declare_parameter('sweep_angle_deg', 30.0)
        self.declare_parameter('yaw_kp', 1.2)                    # yaw rate = kp * error
        self.declare_parameter('yaw_rate_max', 0.7)              # rad/s
        self.declare_parameter('yaw_tol_deg', 2.0)

        # return / pass-through-home mission (tag0)
        self.declare_parameter('return_speed', 0.4)              # m/s when flying back toward home
        self.declare_parameter('scan_speed', 0.4)                # m/s after crossing home (continuing past)
        self.declare_parameter('home_radius', 0.15)              # "I crossed home" distance trigger

        # landing behavior over tag0
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('tag0_frame', 'tag36h11:0')
        self.declare_parameter('xy_tolerance', 0.30)
        self.declare_parameter('xy_reacquire', 0.60)
        self.declare_parameter('descent_rate', 0.08)             # m/s down (final landing)
        self.declare_parameter('land_height', 0.20)

        # PID gains for landing alignment (tag0)
        self.declare_parameter('KP', 0.008)
        self.declare_parameter('KD', 0.0004)
        self.declare_parameter('KI', 0.00005)
        self.declare_parameter('max_xy_speed', 0.4)

        # brake-on-see duration for tag0
        self.declare_parameter('brake_time_s', 0.6)

        # pull params
        self.takeoff_alt   = float(self.get_parameter('takeoff_alt').value)
        self.forward_speed = float(self.get_parameter('forward_speed').value)

        self.first_tag_frame = str(self.get_parameter('first_tag_frame').value)
        self.post_detect_forward_time_s = float(self.get_parameter('post_detect_forward_time_s').value)

        self.tag1_descend_m   = float(self.get_parameter('tag1_descend_m').value)
        self.tag1_descent_rate= float(self.get_parameter('tag1_descent_rate').value)
        self.tag1_ascent_rate = float(self.get_parameter('tag1_ascent_rate').value)
        self.wait_after_sweep_s = float(self.get_parameter('wait_after_sweep_s').value)

        self.sweep_angle_deg = float(self.get_parameter('sweep_angle_deg').value)
        self.yaw_kp          = float(self.get_parameter('yaw_kp').value)
        self.yaw_rate_max    = float(self.get_parameter('yaw_rate_max').value)
        self.yaw_tol_deg     = float(self.get_parameter('yaw_tol_deg').value)

        self.return_speed  = float(self.get_parameter('return_speed').value)
        self.scan_speed    = float(self.get_parameter('scan_speed').value)
        self.home_radius   = float(self.get_parameter('home_radius').value)

        self.base_frame    = str(self.get_parameter('base_frame').value)
        self.tag0_frame    = str(self.get_parameter('tag0_frame').value)

        self.xy_tolerance  = float(self.get_parameter('xy_tolerance').value)
        self.xy_reacquire  = float(self.get_parameter('xy_reacquire').value)
        self.descent_rate  = float(self.get_parameter('descent_rate').value)
        self.land_height   = float(self.get_parameter('land_height').value)

        self.KP            = float(self.get_parameter('KP').value)
        self.KD            = float(self.get_parameter('KD').value)
        self.KI            = float(self.get_parameter('KI').value)
        self.max_xy_speed  = float(self.get_parameter('max_xy_speed').value)

        self.brake_time_s  = float(self.get_parameter('brake_time_s').value)

        # ---------------- state machine ----------------
        (
            self.IDLE,
            self.TAKEOFF,
            self.FWD_TO_TAG1,      # fly forward, watch for tag1
            self.TAG1_COAST,       # keep going a bit after seeing tag1
            self.TAG1_DESCEND,     # descend 1 m
            self.TAG1_YAW_SWEEP,   # +30 -> back -> -30 -> back
            self.TAG1_WAIT,        # wait 2 s
            self.TAG1_ASCEND,      # ascend 1 m to detection altitude
            self.RETURN_THROUGH_HOME,
            self.PAST_HOME_SCAN,
            self.BRAKE_ON_SEE,     # short hard stop when tag0 first appears
            self.ALIGN_XY,
            self.DESCEND,
            self.REALIGN,
            self.TOUCHDOWN,
            self.DONE
        ) = range(16)
        self.state = self.IDLE

        # ---------------- mavros interfaces ----------------
        self.mav_state = MavState()
        self.state_sub = self.create_subscription(MavState, '/mavros/state', self._state_cb, 10)

        self.odom_sub  = self.create_subscription(
            Odometry, '/mavros/local_position/odom', self._odom_cb, qos_profile=SENSOR_QOS
        )

        self.cmd_vel_pub = self.create_publisher(
            Twist, '/mavros/setpoint_velocity/cmd_vel_unstamped', 10
        )

        self.arm_cli  = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.mode_cli = self.create_client(SetMode,    '/mavros/set_mode')

        self.tf_buf = Buffer()
        self.tf_listener = TransformListener(self.tf_buf, self)

        # odom state
        self.have_odom = False
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.altitude  = 0.0
        self.yaw_enu   = 0.0
        self.vel_z     = 0.0  # for touchdown logic

        # home info
        self.home_set = False
        self.home_x = 0.0
        self.home_y = 0.0
        self.home_yaw = 0.0  # heading we consider "forward line"

        # timers / counters
        self.last_cmd = Twist()
        self.dt_logic = 0.1    # 10 Hz logic loop
        self.keepalive_timer = self.create_timer(0.05, self._keepalive_tick)  # 20 Hz
        self.logic_timer     = self.create_timer(self.dt_logic, self._logic_tick)

        # tag1 routine bookkeeping
        self.coast_ticks_left = 0
        self.detect_alt = None
        self.detect_yaw = None
        self.target_alt_down = None
        self.target_alt_up   = None
        self.sweep_phase = 0
        self.yaw_target = None
        self.wait_ticks_left = 0

        # PID controller memory (for tag0)
        self.x_sum_error = 0.0
        self.y_sum_error = 0.0
        self.x_prev_error = 0.0
        self.y_prev_error = 0.0

        # landing tracking
        self.tag_lost_count = 0
        self.max_tag_lost_frames = 10
        self.realign_count = 0
        self.timeout = 30

        # touchdown/disarm helper
        self.landed_still_count = 0

        # brake-on-see
        self.brake_ticks_left = 0

        self.get_logger().info("Merged mission: tag1 routine → return past home → tag0 align & land ✅")

    # ---------------- callbacks ----------------
    def _state_cb(self, msg: MavState):
        self.mav_state = msg

    def _odom_cb(self, msg: Odometry):
        self.have_odom = True
        self.pos_x = float(msg.pose.pose.position.x)
        self.pos_y = float(msg.pose.pose.position.y)
        self.altitude = float(msg.pose.pose.position.z)

        q = msg.pose.pose.orientation
        self.yaw_enu = quat_to_yaw(q.x, q.y, q.z, q.w)

        self.vel_z = float(msg.twist.twist.linear.z)

    # ---------------- helpers ----------------
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

    def _get_tag_in_base_frame(self, frame: str):
        """
        TF lookup: base_link -> <frame>
        Returns ok flag and (tx, ty, tz, lateral_err).
        """
        try:
            t = self.tf_buf.lookup_transform(
                self.base_frame,
                frame,
                rclpy.time.Time()
            )
        except Exception:
            return False, 0.0, 0.0, 0.0, 999.0

        tx = t.transform.translation.x
        ty = t.transform.translation.y
        tz = t.transform.translation.z
        lateral_err = math.hypot(tx, ty)
        return True, tx, ty, tz, lateral_err

    def _get_tag0_in_base(self):
        return self._get_tag_in_base_frame(self.tag0_frame)

    def _tag_visible(self, frame: str) -> bool:
        ok, *_ = self._get_tag_in_base_frame(frame)
        return ok

    def _body_vel_to_enu(self, vx_body, vy_body, yaw):
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        vx_enu = cy * vx_body - sy * vy_body
        vy_enu = sy * vx_body + cy * vy_body
        return vx_enu, vy_enu

    def _compute_pid_vel(self, err_x, err_y):
        dx = err_x - self.x_prev_error
        dy = err_y - self.y_prev_error

        self.x_sum_error += err_x
        self.y_sum_error += err_y

        vx_body = (self.KP * err_x + self.KD * dx + self.KI * self.x_sum_error)
        vy_body = (self.KP * err_y + self.KD * dy + self.KI * self.y_sum_error)

        self.x_prev_error = err_x
        self.y_prev_error = err_y

        vx_body = clamp(vx_body, -self.max_xy_speed, self.max_xy_speed)
        vy_body = clamp(vy_body, -self.max_xy_speed, self.max_xy_speed)
        return vx_body, vy_body

    def _reset_pid_controller(self):
        self.x_sum_error = self.y_sum_error = 0.0
        self.x_prev_error = self.y_prev_error = 0.0
        self.timeout = 30

    def _dist_from_home(self):
        if not self.home_set:
            return 0.0
        dx = self.pos_x - self.home_x
        dy = self.pos_y - self.home_y
        return math.hypot(dx, dy)

    def _yaw_to_target(self):
        err = ang_norm(self.yaw_enu - self.yaw_target) * -1.0  # target - current
        if abs(err) < math.radians(self.yaw_tol_deg):
            return 0.0, True
        rate = self.yaw_kp * err
        rate = clamp(rate, -self.yaw_rate_max, self.yaw_rate_max)
        return rate, False

    # ---------------- timers ----------------
    def _keepalive_tick(self):
        self.cmd_vel_pub.publish(self.last_cmd)

    def _logic_tick(self):
        if not self.have_odom:
            return

        # === IDLE ===
        if self.state == self.IDLE:
            self._maybe_set_mode('OFFBOARD')
            self._maybe_arm(True)
            if self.mav_state.armed and self.mav_state.mode == 'OFFBOARD':
                self.state = self.TAKEOFF
                self.get_logger().info("→ TAKEOFF")

        # === TAKEOFF ===
        elif self.state == self.TAKEOFF:
            cmd = Twist()

            if self.altitude < (self.takeoff_alt - 0.1):
                cmd.linear.z = 0.8
            else:
                cmd.linear.z = 0.0

            self.last_cmd = cmd

            if self.altitude >= (self.takeoff_alt - 0.05):
                if not self.home_set:
                    self.home_x = self.pos_x
                    self.home_y = self.pos_y
                    self.home_yaw = self.yaw_enu
                    self.home_set = True
                    self.get_logger().info(
                        f"Home set @ ({self.home_x:.2f},{self.home_y:.2f}) yaw={self.home_yaw:.2f}rad"
                    )

                self.state = self.FWD_TO_TAG1
                self.get_logger().info("Reached takeoff alt. → FWD_TO_TAG1")

        # === FWD_TO_TAG1 (scan for tag1 while moving forward) ===
        elif self.state == self.FWD_TO_TAG1:
            cmd = Twist()

            # move body-forward along home_yaw
            vx_body = self.forward_speed
            vy_body = 0.0
            vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.home_yaw)

            cmd.linear.x = float(vx_enu)
            cmd.linear.y = float(vy_enu)
            cmd.linear.z = 0.0

            # check for tag1
            if self._tag_visible(self.first_tag_frame):
                self.coast_ticks_left = int(self.post_detect_forward_time_s / self.dt_logic)
                self.detect_alt = self.altitude
                self.detect_yaw = self.yaw_enu
                self.target_alt_down = max(0.1, self.detect_alt - self.tag1_descend_m)
                self.target_alt_up   = self.detect_alt
                self.state = self.TAG1_COAST
                self.get_logger().info(
                    f"✅ Tag1 detected — coasting {self.post_detect_forward_time_s:.1f}s, "
                    f"then descend to {self.target_alt_down:.2f} m"
                )

            self.last_cmd = cmd

        # === TAG1_COAST ===
        elif self.state == self.TAG1_COAST:
            cmd = Twist()
            vx_body = self.forward_speed
            vy_body = 0.0
            vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.home_yaw)
            cmd.linear.x = float(vx_enu)
            cmd.linear.y = float(vy_enu)
            cmd.linear.z = 0.0

            self.coast_ticks_left -= 1
            if self.coast_ticks_left <= 0:
                self.state = self.TAG1_DESCEND
                self.get_logger().info("⏹️ Coast complete — starting 1 m descent")

            self.last_cmd = cmd

        # === TAG1_DESCEND ===
        elif self.state == self.TAG1_DESCEND:
            cmd = Twist()
            if self.altitude > self.target_alt_down + 0.05:
                cmd.linear.z = -abs(self.tag1_descent_rate)
            else:
                cmd.linear.z = 0.0
                # start yaw sweep
                self.sweep_phase = 0
                self.yaw_target = ang_norm(self.detect_yaw + math.radians(self.sweep_angle_deg))
                self.state = self.TAG1_YAW_SWEEP
                self.get_logger().info(f"↺ Yaw +{self.sweep_angle_deg:.0f}°")
            self.last_cmd = cmd

        # === TAG1_YAW_SWEEP ===
        elif self.state == self.TAG1_YAW_SWEEP:
            cmd = Twist()
            yaw_rate, reached = self._yaw_to_target()
            cmd.angular.z = float(yaw_rate)
            if reached:
                if self.sweep_phase == 0:
                    self.sweep_phase = 1; self.yaw_target = self.detect_yaw
                    self.get_logger().info("↻ Return to heading")
                elif self.sweep_phase == 1:
                    self.sweep_phase = 2; self.yaw_target = ang_norm(self.detect_yaw - math.radians(self.sweep_angle_deg))
                    self.get_logger().info(f"↺ Yaw -{self.sweep_angle_deg:.0f}°")
                elif self.sweep_phase == 2:
                    self.sweep_phase = 3; self.yaw_target = self.detect_yaw
                    self.get_logger().info("↻ Return to heading")
                else:
                    self.wait_ticks_left = int(self.wait_after_sweep_s / self.dt_logic)
                    self.state = self.TAG1_WAIT
                    self.get_logger().info(f"⏳ Sweep done — waiting {self.wait_after_sweep_s:.1f}s")
            self.last_cmd = cmd

        # === TAG1_WAIT ===
        elif self.state == self.TAG1_WAIT:
            cmd = Twist()
            self.wait_ticks_left -= 1
            if self.wait_ticks_left <= 0:
                self.state = self.TAG1_ASCEND
                self.get_logger().info(f"⬆️ Ascend to {self.target_alt_up:.2f} m")
            self.last_cmd = cmd

        # === TAG1_ASCEND ===
        elif self.state == self.TAG1_ASCEND:
            cmd = Twist()
            if self.altitude < self.target_alt_up - 0.05:
                cmd.linear.z = abs(self.tag1_ascent_rate)
            else:
                cmd.linear.z = 0.0
                self.get_logger().info("✅ Tag1 routine done → RETURN_THROUGH_HOME")
                self.state = self.RETURN_THROUGH_HOME
            self.last_cmd = cmd

        # === RETURN_THROUGH_HOME ===
        elif self.state == self.RETURN_THROUGH_HOME:
            cmd = Twist()

            vx_body = -abs(self.return_speed)  # back toward home along home_yaw
            vy_body = 0.0
            vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.home_yaw)

            cmd.linear.x = float(vx_enu)
            cmd.linear.y = float(vy_enu)
            cmd.linear.z = 0.0  # hold altitude

            dist = self._dist_from_home()
            if dist <= self.home_radius:
                self.state = self.PAST_HOME_SCAN
                self.get_logger().info("Crossed home → PAST_HOME_SCAN (looking for tag0)")
            self.last_cmd = cmd

        # === PAST_HOME_SCAN ===
        elif self.state == self.PAST_HOME_SCAN:
            cmd = Twist()

            vx_body = -abs(self.scan_speed)  # continue same direction past home
            vy_body = 0.0
            vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.home_yaw)

            cmd.linear.x = float(vx_enu)
            cmd.linear.y = float(vy_enu)
            cmd.linear.z = 0.0  # stay at same altitude

            ok, tx, ty, tz, lateral = self._get_tag0_in_base()

            if ok:
                # NEW: hard brake before ALIGN_XY to prevent overshoot
                self.state = self.BRAKE_ON_SEE
                self.brake_ticks_left = max(1, int(self.brake_time_s / self.dt_logic))
                self._reset_pid_controller()
                self.get_logger().info(
                    f"[PAST_HOME_SCAN] tag0 seen → BRAKE_ON_SEE (lat={lateral:.3f} m, {self.brake_time_s:.1f}s)"
                )
                cmd = Twist()  # zero immediately
            self.last_cmd = cmd

        # === BRAKE_ON_SEE ===
        elif self.state == self.BRAKE_ON_SEE:
            cmd = Twist()
            cmd.linear.x = cmd.linear.y = cmd.linear.z = 0.0
            self.brake_ticks_left -= 1
            if self.brake_ticks_left <= 0:
                self.state = self.ALIGN_XY
                self.get_logger().info("Brake complete → ALIGN_XY")
            self.last_cmd = cmd

        # === ALIGN_XY (final, for tag0) ===
        elif self.state == self.ALIGN_XY:
            ok, tx, ty, tz, lateral = self._get_tag0_in_base()

            cmd = Twist()
            cmd.linear.z = 0.0  # hold height, slide over tag

            if ok:
                err_x = -tx  # body-forward error to center
                err_y = -ty  # body-left error to center

                vx_body, vy_body = self._compute_pid_vel(err_x, err_y)
                vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.yaw_enu)

                cmd.linear.x = float(vx_enu)
                cmd.linear.y = float(vy_enu)

                if lateral < self.xy_tolerance:
                    self.state = self.DESCEND
                    self.tag_lost_count = 0
                    self._reset_pid_controller()
                    self.get_logger().info("Centered → DESCEND")
            else:
                cmd.linear.x = cmd.linear.y = 0.0
            self.last_cmd = cmd

        # === DESCEND (final, for tag0) ===
        elif self.state == self.DESCEND:
            ok, tx, ty, tz, lateral = self._get_tag0_in_base()

            cmd = Twist()

            if ok:
                self.tag_lost_count = 0

                if lateral > self.xy_reacquire:
                    self.state = self.REALIGN
                    self.realign_count += 1
                    self._reset_pid_controller()
                    self.get_logger().warn(f"Lateral error {lateral:.3f}m → REALIGN")
                    self.last_cmd = Twist()
                    return

                err_x = -tx
                err_y = -ty

                vx_body, vy_body = self._compute_pid_vel(err_x, err_y)
                vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.yaw_enu)

                cmd.linear.x = float(vx_enu)
                cmd.linear.y = float(vy_enu)
            else:
                self.tag_lost_count += 1
                cmd.linear.x = cmd.linear.y = 0.0

                if self.tag_lost_count > self.max_tag_lost_frames:
                    self.get_logger().error("Tag lost too long → TOUCHDOWN")
                    self.state = self.TOUCHDOWN
                    self._reset_pid_controller()
                    self.last_cmd = Twist()
                    return

            cmd.linear.z = float(-abs(self.descent_rate))

            self.timeout -= 1
            if self.timeout == 0 and self.altitude > 0.7:
                self.get_logger().warn("Timeout - resetting PID during DESCEND")
                self._reset_pid_controller()

            if ok and tz <= self.land_height:
                self.state = self.TOUCHDOWN
                self._reset_pid_controller()
                self.get_logger().info("Close to ground → TOUCHDOWN")

            self.last_cmd = cmd

        # === REALIGN (final, for tag0) ===
        elif self.state == self.REALIGN:
            ok, tx, ty, tz, lateral = self._get_tag0_in_base()

            cmd = Twist()
            cmd.linear.z = 0.0  # hold altitude

            if ok:
                err_x = -tx
                err_y = -ty

                vx_body, vy_body = self._compute_pid_vel(err_x, err_y)
                vx_enu, vy_enu = self._body_vel_to_enu(vx_body, vy_body, self.yaw_enu)

                cmd.linear.x = float(vx_enu)
                cmd.linear.y = float(vy_enu)

                if lateral < (self.xy_tolerance + 0.05):
                    self.state = self.DESCEND
                    self._reset_pid_controller()
                    self.get_logger().info("Recentered → DESCEND")
            else:
                cmd.linear.x = cmd.linear.y = 0.0
            self.last_cmd = cmd

        # === TOUCHDOWN ===
        elif self.state == self.TOUCHDOWN:
            cmd = Twist()
            cmd.linear.x = cmd.linear.y = cmd.linear.z = 0.0
            self.last_cmd = cmd

            self._maybe_set_mode('AUTO.LAND')

            low_enough  = (self.altitude <= 0.25)
            slow_enough = (abs(self.vel_z) < 0.05)

            if low_enough and slow_enough:
                self.landed_still_count += 1
            else:
                self.landed_still_count = 0

            if self.landed_still_count >= 10 and self.mav_state.armed:
                self._maybe_arm(False)

            if not self.mav_state.armed:
                self.state = self.DONE
                self.get_logger().info(
                    f"Disarmed. → DONE (realigned {self.realign_count} times)"
                )

        # === DONE ===
        elif self.state == self.DONE:
            self.last_cmd = Twist()
            return


def main():
    rclpy.init()
    node = PrecisionLandMerged()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
