from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'apriltag_navigation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # required so `ros2 pkg prefix apriltag_navigation` works
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        # package manifest
        ('share/' + package_name, ['package.xml']),

        # install launch files into share/apriltag_navigation/launch
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),

        # install config files into share/apriltag_navigation/config
        (os.path.join('share', package_name, 'config'), ['config/apriltag_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='imateyau',
    maintainer_email='imateyau@todo.todo',
    description='AprilTag-based precision landing and navigation for PX4 SITL',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'apriltag_navigation_node = apriltag_navigation.apriltag_navigation:main',
            'precland_mission_node = apriltag_navigation.precland_mission_pnp:main',
            'dynamic_tag_node = apriltag_navigation.dynamic_tag_tf:main',
            'pose_to_tf = apriltag_navigation.pose_to_tf:main',
            'tag_visualizer = apriltag_navigation.tag_visualizer:main',
             'precland_mission_pid = apriltag_navigation.precland_mission_pid:main'
        ],
    },
)
