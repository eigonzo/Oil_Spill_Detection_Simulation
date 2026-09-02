

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

   

    return LaunchDescription([
        
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
                ('image_rect', '/camera/camera/color/image_raw'),
                ('camera_info', '/camera/camera/color/camera_info'),
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
