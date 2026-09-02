# import os
# from launch import LaunchDescription
# from launch_ros.actions import Node
# from ament_index_python.packages import get_package_share_directory


# def generate_launch_description():
#     nav_share = get_package_share_directory('apriltag_navigation')

#     apriltag_param_file = os.path.join(
#         nav_share,
#         'config',
#         'apriltag_params.yaml'
#     )

#     # Gazebo topics (you already used this)
#     gz_cam_image_topic = (
#         '/world/aruco/model/x500_depth_0/link/camera_link/sensor/IMX214/image'
#     )
#     gz_cam_info_topic = (
#         '/world/aruco/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info'
#     )

#     return LaunchDescription([
#         # --- 0) Gazebo ↔ ROS camera bridge ---
#         Node(
#             package='ros_gz_bridge',
#             executable='parameter_bridge',
#             name='gz_camera_bridge',
#             output='screen',
#             parameters=[{'use_sim_time': True}],
#             arguments=[
#                 gz_cam_image_topic
#                 + '@sensor_msgs/msg/Image'
#                 + '@gz.msgs.Image',

#                 gz_cam_info_topic
#                 + '@sensor_msgs/msg/CameraInfo'
#                 + '@gz.msgs.CameraInfo',
#             ],
#             remappings=[
#                 (gz_cam_image_topic, '/camera/image_raw'),
#                 (gz_cam_info_topic,  '/camera/camera_info'),
#             ],
#         ),

#         # --- 1) Static TF: base_link -> camera_link ---
#         # Camera mounted at (0.12, 0.03, 0.242) and looking DOWN (pitch +90°)
#         Node(
#             package='tf2_ros',
#             executable='static_transform_publisher',
#             name='static_cam_tf',
#             output='screen',
#             parameters=[{'use_sim_time': True}],
#             arguments=[
#                 '0.12', '0.03', '0.242',   # x y z (m)
#                 '0', '1.5708', '0',        # roll pitch yaw (rad)
#                 'base_link', 'camera_link' # parent, child
#             ]
#         ),

#         # --- 2) AprilTag detector ---
#         Node(
#             package='apriltag_ros',
#             executable='apriltag_node',
#             name='apriltag_node',
#             output='screen',
#             parameters=[
#                 {'use_sim_time': True},
#                 apriltag_param_file,
#             ],
#             remappings=[
#                 ('image_rect', '/camera/image_raw'),
#                 ('camera_info', '/camera/camera_info'),
#             ],
#         ),

#         # --- 3) Precision landing / mission node (ROS2) ---
#         Node(
#             package='apriltag_navigation',
#             executable='precland_mission_pid',
#             name='precision_land_simple',
#             output='screen',
#         ),

#         # --- 4) Optional: tag visualizer (for debugging) ---
#         Node(
#             package='apriltag_navigation',
#             executable='tag_visualizer',
#             name='tag_visualizer',
#             output='screen',
#             parameters=[{'use_sim_time': True}],
#         ),
#     ])

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    nav_share = get_package_share_directory('apriltag_navigation')

    apriltag_param_file = os.path.join(
        nav_share,
        'config',
        'apriltag_params.yaml'
    )

    # Gazebo topics (adjust model name if sim renames it, e.g. x500_depth vs x500_depth_0)
    gz_cam_image_topic = (
        '/world/aruco/model/x500_depth_0/link/camera_link/sensor/IMX214/image'
    )
    gz_cam_info_topic = (
        '/world/aruco/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info'
    )

    return LaunchDescription([
        # --- 0. Bridge camera image + camera_info together (one process!)
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='gz_camera_bridge',
            output='screen',
            parameters=[{'use_sim_time': True}],
            arguments=[
                # format: <gz_topic>@<ros_msg>@<gz_msg>
                gz_cam_image_topic
                + '@sensor_msgs/msg/Image'
                + '@gz.msgs.Image',

                gz_cam_info_topic
                + '@sensor_msgs/msg/CameraInfo'
                + '@gz.msgs.CameraInfo',
            ],
            remappings=[
                (gz_cam_image_topic, '/camera/image_raw'),
                (gz_cam_info_topic,  '/camera/camera_info'),
            ],
        ),

        # --- 1. Static TF: base_link -> camera_link
        # This matches your SDF mount: translation (0.12,0.03,0.242), RPY (0, +1.5708, 0).
        # IMPORTANT: static_transform_publisher in ROS 2 wants:
        # x y z roll pitch yaw parent child
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='static_cam_tf',
            output='screen',
            parameters=[{'use_sim_time': True}],
            arguments=[
                '0.12', '0.03', '0.242',   # translation (m)
                '0', '0', '0',        # rotation RPY (rad)
                'base_link', 'camera_link' # parent child
            ]
        ),

        # --- 2. AprilTag detector
        Node(
            package='apriltag_ros',
            executable='apriltag_node',
            name='apriltag_node',
            output='screen',
            parameters=[
                {'use_sim_time': True},
                apriltag_param_file
            ],
            remappings=[
                ('image_rect', '/camera/image_raw'),
                ('camera_info', '/camera/camera_info'),
            ],
        ),

        # --- 3. Precision landing / hover control node
        Node(
            package='apriltag_navigation',
            executable='precland_mission_pid',  
            name='precision_land_simple',
            output='screen',
        ),

        #  visualization
        Node(
            package='apriltag_navigation',
            executable='tag_visualizer',
            name='tag_visualizer',
            output='screen',
            parameters=[{'use_sim_time': True}],
        ),
    ])