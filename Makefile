# =====================================================================
#  UR10 · Onshape -> URDF -> ROS 2 (RViz) pipeline
#
#  Typical flow:
#     make check      # 1. verify API keys in .env
#     make inspect    # 2. verify the assembly (mates -> joints)
#     make urdf       # 3. export URDF + meshes from Onshape
#     make urdf-env   # 3b. export the environment (table/stand/tube/glory)
#     make sync       # 4. copy into the ROS 2 package (+ merge environment)
#     make build      # 5. colcon build
#     make rviz       # 6. RViz2 + joint sliders
# =====================================================================

PYTHON  := .venv/bin/python
PKG     := ur10_robot_description

.PHONY: check inspect urdf urdf-env sync build rviz all clean

check:            ## verify .env keys + access to the document
	$(PYTHON) scripts/env_check.py

inspect:          ## list instances/mates of the assembly (what will be exported)
	$(PYTHON) scripts/inspect_assembly.py

urdf:             ## export URDF + STL meshes from Onshape
	$(PYTHON) scripts/run_export.py

urdf-env:         ## export the environment (Whole setup tab: table/stand/tube/glory)
	$(PYTHON) scripts/dump_whole_setup.py
	.venv/bin/onshape-to-robot export_env/

sync:             ## copy export into the ROS 2 package + merge env + patch RViz frame
	$(PYTHON) scripts/sync_to_ros.py

build:            ## colcon build the description package
	bash -c "source /opt/ros/jazzy/setup.bash && cd ros2_ws && colcon build --packages-select $(PKG) --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3"

rviz:             ## RViz2 with joint sliders (build first!)
	bash -c "source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash && ros2 launch $(PKG) display.launch.py"

all: urdf sync build

clean:
	rm -rf ros2_ws/build ros2_ws/install ros2_ws/log export/.cache
