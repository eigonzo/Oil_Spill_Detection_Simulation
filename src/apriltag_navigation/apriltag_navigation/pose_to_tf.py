#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, TransformStamped
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from tf2_ros import TransformBroadcaster

POSE_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,   # <-- matches MAVROS publisher
    durability=DurabilityPolicy.VOLATILE
)

class PoseToTF(Node):
    def __init__(self):
        super().__init__('pose_to_tf')
        self.declare_parameter('pose_topic', '/mavros/local_position/pose')
        self.declare_parameter('map_frame', 'map')     # set to header.frame_id you saw above
        self.declare_parameter('base_link', 'base_link')

        self.pose_topic = self.get_parameter('pose_topic').value
        self.map_frame  = self.get_parameter('map_frame').value
        self.base_link  = self.get_parameter('base_link').value

        self.br = TransformBroadcaster(self)
        self.create_subscription(PoseStamped, self.pose_topic, self._pose_cb, qos_profile=POSE_QOS)
        self.get_logger().info(f"Publishing TF {self.map_frame} -> {self.base_link} from {self.pose_topic}")

    def _pose_cb(self, msg: PoseStamped):
        tf = TransformStamped()
        tf.header = msg.header
        tf.header.frame_id = self.map_frame
        tf.child_frame_id  = self.base_link
        tf.transform.translation.x = msg.pose.position.x
        tf.transform.translation.y = msg.pose.position.y
        tf.transform.translation.z = msg.pose.position.z
        tf.transform.rotation = msg.pose.orientation
        self.br.sendTransform(tf)

def main():
    rclpy.init(); node = PoseToTF()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
