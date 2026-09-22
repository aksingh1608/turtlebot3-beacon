"""The three Beacon nodes only, for a Gazebo that is already running."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_beacon = get_package_share_directory('beacon')
    use_sim_time = LaunchConfiguration('use_sim_time')
    params_file = LaunchConfiguration('params_file')
    image_topic = LaunchConfiguration('image_topic')
    trials_dir = LaunchConfiguration('trials_dir')
    common = {'use_sim_time': use_sim_time, 'trials_dir': trials_dir}

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('image_topic', default_value='/camera/image_raw'),
        DeclareLaunchArgument('trials_dir', default_value=''),
        DeclareLaunchArgument('params_file',
                              default_value=os.path.join(pkg_beacon, 'config', 'params.yaml')),
        Node(package='beacon', executable='detector_node', name='detector_node', output='screen',
             parameters=[params_file, dict(common, image_topic=image_topic)]),
        Node(package='beacon', executable='controller_node', name='controller_node',
             output='screen', parameters=[params_file, common]),
        Node(package='beacon', executable='trial_logger_node', name='trial_logger_node',
             output='screen', parameters=[params_file, common]),
    ])
