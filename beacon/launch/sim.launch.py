"""Full Beacon simulation: Gazebo, TurtleBot3 Waffle Pi, the three nodes,
optional RViz and an optional first trial.

Modelled on turtlebot3_gazebo/launch/turtlebot3_world.launch.py (Humble).
Jazzy uses ros_gz instead of gazebo_ros; this file targets Gazebo Classic.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription,
                            OpaqueFunction, TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def setup(context, *args, **kwargs):
    pkg_beacon = get_package_share_directory('beacon')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_tb3 = get_package_share_directory('turtlebot3_gazebo')

    # The turtlebot3_gazebo launch files read this at import time.
    os.environ['TURTLEBOT3_MODEL'] = 'waffle_pi'

    world_name = LaunchConfiguration('world').perform(context)
    if world_name == 'turtlebot3_world':
        world = os.path.join(pkg_tb3, 'worlds', 'turtlebot3_world.world')
    else:
        world = os.path.join(pkg_beacon, 'worlds', 'beacon_room.world')

    use_sim_time = LaunchConfiguration('use_sim_time')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    params_file = LaunchConfiguration('params_file')
    image_topic = LaunchConfiguration('image_topic')
    trials_dir = LaunchConfiguration('trials_dir')
    trial = LaunchConfiguration('trial')
    spawn_delay = float(LaunchConfiguration('spawn_delay').perform(context))

    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')),
        # init and factory load libgazebo_ros_init.so and libgazebo_ros_factory.so,
        # which provide /reset_world and /spawn_entity. CONFIRM IN SIM.
        launch_arguments={'world': world, 'init': 'true', 'factory': 'true'}.items())

    gzclient = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')))

    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_tb3, 'launch', 'robot_state_publisher.launch.py')),
        launch_arguments={'use_sim_time': use_sim_time}.items())

    spawn_turtlebot3 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_tb3, 'launch', 'spawn_turtlebot3.launch.py')),
        launch_arguments={'x_pose': x_pose, 'y_pose': y_pose}.items())

    common = {'use_sim_time': use_sim_time, 'trials_dir': trials_dir}
    detector = Node(package='beacon', executable='detector_node', name='detector_node',
                    output='screen',
                    parameters=[params_file, dict(common, image_topic=image_topic)])
    controller = Node(package='beacon', executable='controller_node', name='controller_node',
                      output='screen', parameters=[params_file, common])
    logger = Node(package='beacon', executable='trial_logger_node', name='trial_logger_node',
                  output='screen', parameters=[params_file, common])

    rviz = Node(package='rviz2', executable='rviz2', name='rviz2', output='screen',
                arguments=['-d', os.path.join(pkg_beacon, 'config', 'beacon.rviz')],
                parameters=[{'use_sim_time': use_sim_time}],
                condition=IfCondition(LaunchConfiguration('rviz')))

    spawn_marker = TimerAction(
        period=spawn_delay,
        actions=[ExecuteProcess(
            cmd=['ros2', 'run', 'beacon', 'spawn_marker', '--trial', trial,
                 '--trials-dir', trials_dir],
            output='screen',
            condition=IfCondition(PythonExpression(["'", trial, "' != 'none'"])))])

    return [gzserver, gzclient, robot_state_publisher, spawn_turtlebot3,
            detector, controller, logger, rviz, spawn_marker]


def generate_launch_description():
    pkg_beacon = get_package_share_directory('beacon')
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='beacon_room',
                              description='beacon_room or turtlebot3_world'),
        DeclareLaunchArgument('x_pose', default_value='0.0'),
        DeclareLaunchArgument('y_pose', default_value='0.0'),
        DeclareLaunchArgument('rviz', default_value='false'),
        DeclareLaunchArgument('trial', default_value='none',
                              description='row of positions.csv to spawn after launch'),
        DeclareLaunchArgument('spawn_delay', default_value='10.0',
                              description='seconds to wait for Gazebo before spawning the marker'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('image_topic', default_value='/camera/image_raw'),
        DeclareLaunchArgument('trials_dir', default_value='',
                              description='empty means the source tree trials folder'),
        DeclareLaunchArgument('params_file',
                              default_value=os.path.join(pkg_beacon, 'config', 'params.yaml')),
        OpaqueFunction(function=setup),
    ])
