#!/usr/bin/env python3
"""
display.launch.py — show the Onshape-exported robot in RViz2 and let the user
articulate its revolute joints (whatever "dof_" mates were renamed in the
Onshape assembly) with the joint_state_publisher_gui sliders.

Usage:
    ros2 launch ur10_robot_description display.launch.py
    ros2 launch ur10_robot_description display.launch.py use_gui:=false   # no sliders
    ros2 launch ur10_robot_description display.launch.py rviz:=false      # headless
"""

import glob
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("ur10_robot_description")

    # Generic: pick up whatever sync_to_ros.py wrote (names come from
    # "output_filename" in export/config.json — e.g. ur10.urdf, mybot.urdf)
    urdfs = sorted(glob.glob(os.path.join(pkg_share, "urdf", "*.urdf")))
    if not urdfs:
        raise FileNotFoundError(
            f"no *.urdf in {os.path.join(pkg_share, 'urdf')} — run: make sync && make build"
        )
    urdf_path = urdfs[0]
    rviz_configs = sorted(glob.glob(os.path.join(pkg_share, "rviz", "*.rviz")))
    rviz_config = rviz_configs[0] if rviz_configs else None

    # Plain URDF straight from the Onshape export (no xacro processing needed)
    with open(urdf_path, "r", encoding="utf-8") as f:
        robot_description = f.read()

    use_gui = LaunchConfiguration("use_gui")
    use_rviz = LaunchConfiguration("rviz")

    return LaunchDescription([
        DeclareLaunchArgument(
            "use_gui", default_value="true",
            description="Start joint_state_publisher_gui (sliders to move the joints)",
        ),
        DeclareLaunchArgument(
            "rviz", default_value="true",
            description="Start RViz2 with the pre-configured view",
        ),

        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{"robot_description": robot_description}],
        ),

        # GUI sliders -> /joint_states (this is how you articulate the robot)
        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            name="joint_state_publisher_gui",
            output="screen",
            condition=IfCondition(use_gui),
        ),

        # Headless fallback (reads /source list from parameters or defaults)
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            name="joint_state_publisher",
            output="screen",
            condition=UnlessCondition(use_gui),
        ),

        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            output="screen",
            arguments=(["-d", rviz_config] if rviz_config else []),
            condition=IfCondition(use_rviz),
        ),
    ])
