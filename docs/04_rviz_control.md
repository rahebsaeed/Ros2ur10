# 04 · RViz visualisation & joint control

## Build the package

```bash
make build          # = colcon build --packages-select ur10_robot_description
```

## Launch

```bash
make rviz
# equivalent:
#   source /opt/ros/jazzy/setup.bash
#   source ros2_ws/install/setup.bash
#   ros2 launch ur10_robot_description display.launch.py
```

What starts:

| Node | Role |
|---|---|
| `robot_state_publisher` | publishes the URDF (`/robot_description`) + TF for every link |
| `joint_state_publisher_gui` | **the slider window** — moves the joints, publishes `/joint_states` |
| `rviz2` | 3D view: Grid + RobotModel + TF axes, fixed frame = the URDF root link |

Launch arguments:

```bash
ros2 launch ur10_robot_description display.launch.py use_gui:=false  # no sliders
ros2 launch ur10_robot_description display.launch.py rviz:=false      # headless test
```

## Controlling the articulations

The GUI window shows one slider per URDF joint:

| Slider | Joint | Expected motion |
|---|---|---|
| `Revolute_base` | joint 1 | whole arm rotates about the base Z axis |
| `shoulder` | joint 2 | lower arm swings |
| `elbow` | joint 3 | upper arm swings |
| `Revolute_2` | joint 4 | wrist 1 pitch |
| `Revolute_3` | joint 5 | wrist 2 pitch |
| `Revolute_4` | joint 6 | tool flange rotates |

* Sliders respect the limits from the URDF (`±π` when Onshape has no limits,
  effort/velocity from `export/config.json → joint_properties`).
* **Randomize** jumps all 6 joints to random valid poses (verified live in
  docs/06 — the environment link stays fixed while the arm moves),
  **Center** returns everything to 0.
* Use **File → Save Config** in RViz to persist a nice camera angle for the demo.
* The TF display shows the frame chain moving live — great for the presentation.

## Useful checks during the demo

```bash
ros2 topic echo /joint_states          # see the slider values streaming
ros2 run tf2_tools view_frames         # generate the TF graph PDF
ros2 param get /robot_state_publisher robot_description | head   # URDF is loaded
```

## How the pieces fit together

```
joint_state_publisher_gui  --/joint_states-->  robot_state_publisher
                                                     │  /robot_description (latched)
                                                     ▼
                                                RViz RobotModel
                                                     + TF tree
```

No controllers, no simulation needed — this is the standard ROS 2
"description + manual joint control" stack.
