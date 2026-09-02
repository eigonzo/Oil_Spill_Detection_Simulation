#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from apriltag_msgs.msg import AprilTagDetectionArray
from cv_bridge import CvBridge
import cv2
import numpy as np

class TagVisualizer(Node):
    def __init__(self):
        super().__init__('tag_visualizer')

        # subs
        self.img_sub = self.create_subscription(
            Image,
            '/camera/image_raw',      # your camera topic
            self.image_cb,
            10
        )
        self.det_sub = self.create_subscription(
            AprilTagDetectionArray,
            '/detections',            # apriltag_ros detections
            self.detect_cb,
            10
        )

        # pub
        self.vis_pub = self.create_publisher(
            Image,
            '/tag_visualization',     # debug image out
            10
        )

        self.bridge = CvBridge()
        self.latest_detection = None  # we'll store most recent detection msg

    def detect_cb(self, msg: AprilTagDetectionArray):
        # just cache latest detections so image_cb can draw them
        if len(msg.detections) > 0:
            self.latest_detection = msg.detections[0]  # take first tag for now
        else:
            self.latest_detection = None

    def image_cb(self, img_msg: Image):
        # convert ROS -> OpenCV
        frame = self.bridge.imgmsg_to_cv2(img_msg, desired_encoding='bgr8')

        det = self.latest_detection
        if det is not None:
            # draw polygon around the tag corners
            corners_px = [(int(c.x), int(c.y)) for c in det.corners]
            if len(corners_px) == 4:
                cv2.polylines(
                    frame,
                    [np.array(corners_px, dtype=np.int32)],
                    isClosed=True,
                    color=(0, 255, 0),
                    thickness=2
                )

            # draw center dot
            cx = int(det.centre.x)
            cy = int(det.centre.y)
            cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)

            # label: Tag ID
            # NOTE: in apriltag_msgs/AprilTagDetection, `id` is an int32
            tag_id_text = f"ID {det.id}"
            cv2.putText(
                frame,
                tag_id_text,
                (cx, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
                lineType=cv2.LINE_AA
            )

        # convert back OpenCV -> ROS Image
        out_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        out_msg.header.stamp = self.get_clock().now().to_msg()
        out_msg.header.frame_id = "camera_link"
        self.vis_pub.publish(out_msg)

def main(args=None):
    rclpy.init(args=args)
    node = TagVisualizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()