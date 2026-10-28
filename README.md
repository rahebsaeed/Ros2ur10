# UR10 · Onshape → URDF → ROS 2 (RViz)

Pipeline that takes the **UR10 robot** designed in Onshape and turns it into a
ROS 2 package you can **visualise and articulate in RViz2** with joint sliders.

```
 Onshape document "Universal Robot UR10 - Raheb"
        │  (UR10 assembly tab — 6 revolute mates: dof_Revolute_base, dof_shoulder,
        │   dof_elbow, dof_Revolute_2, dof_Revolute_3, dof_Revolute_4)
        │  ("Whole setup" tab — table + stand + tube + glory machines, all FASTENED)
        │  API keys from .env  (HMAC-signed requests)
        │
        ├─ (one-time, in the Onshape UI) rename the 6 mates with a dof_ prefix:
        │     dof_Revolute_base, dof_shoulder, dof_elbow,
        │     dof_Revolute_2, dof_Revolute_3, dof_Revolute_4
        │
        ▼
 scripts/inspect_assembly.py ─ shows exactly what will be exported
 scripts/run_export.py      ── onshape-to-robot  →  export/ur10.urdf + meshes/*.stl
 scripts/dump_whole_setup.py ─ (read-only) Whole-setup dump for the mount pose
 scripts/sync_to_ros.py     ── copies into ros2_ws/src/ur10_robot_description/
        │                        + merges the environment as ONE fixed link
        │                        + applies the visible robot color palette
        ▼
 ros2 launch ur10_robot_description display.launch.py
        ▼
 RViz2: RobotModel + TF + sliders for all 6 articulations,
        with the colored table/stand/tube/glory cell around the robot
```

## Quick start

```bash
# 0. one-time python env (already done in this repo)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. put your Onshape API keys in .env   (https://dev-portal.onshape.com/keys)
# 2. check them
make check

# 3. verify the assembly structure (mates -> joints)
make inspect

# 4. export URDF + STL from Onshape
make urdf

# 5. export the environment (Whole setup tab: table/stand/tube/glory machines)
make urdf-env

# 6. copy into the ROS 2 package (fixes names + merges the environment
#    as a fixed link + applies the robot color palette + RViz fixed frame)
make sync

# 7. build + open RViz with joint sliders
make build
make rviz
```

## Repository layout

```
UR10/
├── .env                            # API keys (git-ignored) — YOU FILL THIS IN
├── .env.example                    # template
├── Makefile                        # make check | inspect | urdf | urdf-env | sync | build | rviz
├── requirements.txt                # python deps (installed into .venv)
├── export/
│   ├── config.json                 # onshape-to-robot config (URL, ignore, limits)
│   ├── ur10.urdf                   # generated URDF
│   ├── meshes/*.stl                # generated meshes
│   └── inspect/*.json              # raw API dumps (debugging / presentation)
├── export_env/
│   ├── config.json                 # environment export (Whole setup tab, robot ignored)
│   ├── environment.urdf            # generated rigid environment link
│   └── meshes/*.stl                # table / stand / tube / glory meshes
├── scripts/
│   ├── onshape_common.py           # shared .env / URL / API client helpers
│   ├── env_check.py                # [1] verify keys + document access
│   ├── inspect_assembly.py         # [2] what will be exported (links/joints)
│   ├── rename_mates.py             # one-time: dof_ prefix via Onshape API
│   ├── run_export.py               # [3] Onshape → URDF export
│   ├── dump_whole_setup.py         # [3b] read-only Whole-setup dump (mount pose)
│   ├── rename_mates.py             # ⚠️ disabled (API renames break mates — docs/05)
│   └── sync_to_ros.py              # [4] URDF → ROS 2 package + env merge + colors
├── ros2_ws/src/ur10_robot_description/
│   ├── package.xml / CMakeLists.txt
│   ├── urdf/ur10.urdf              # (filled by make sync)
│   ├── meshes/                     # (filled by make sync)
│   ├── launch/display.launch.py    # robot_state_publisher + sliders + RViz
│   └── rviz/ur10.rviz              # fixed frame auto-patched by make sync
└── docs/
    ├── 01_onshape_api_keys.md
    ├── 02_onshape_assembly_setup.md
    ├── 03_export_pipeline.md
    ├── 04_rviz_control.md
    ├── 05_troubleshooting.md
    ├── 06_environment_and_colors.md
    ├── 07_reuse_new_project.md
    ├── 08_add_new_robot_assembly.md
    └── presentation/du_cad_au_ros2.pptx   # course deck (python-pptx, git-ignored)
```

## The 6 articulations

| Onshape mate (UR10 tab)        | URDF joint      | Slider in RViz      |
|--------------------------------|-----------------|---------------------|
| `dof_Revolute_base`            | `Revolute_base` | base rotation       |
| `dof_shoulder`                 | `shoulder`      | shoulder            |
| `dof_elbow`                    | `elbow`         | elbow               |
| `dof_Revolute_2`               | `Revolute_2`    | wrist 1             |
| `dof_Revolute_3`               | `Revolute_3`    | wrist 2             |
| `dof_Revolute_4`               | `Revolute_4`    | wrist 3             |

The **table, stand, tube extender and glory machines** live in the "Whole setup"
Onshape tab. They are exported separately (`make urdf-env`, robot excluded via
`ignore` patterns) and merged into the URDF as ONE fixed link `environment`,
mounted at the Onshape pose of the robot's root-link **part** occurrence
(`UR10 <1>/Base <3>` — the pose the mate constrains, not the sub-assembly
origin) — so the robot keeps its 6 articulations while the cell stays static
around it. See
`docs/06_environment_and_colors.md` (including the color palette that makes the
robot show its classic white/blue UR look instead of the all-grey CAD
appearances).

## Course deck

`docs/presentation/du_cad_au_ros2.pptx` presents the whole process (French,
English keywords) — regenerate with `python scripts/make_pptx.py`
(the `.pptx` is git-ignored, it is a generated file).
To run the same pipeline on **your own Onshape project**, follow
`docs/07_reuse_new_project.md`; to add a new robot assembly or articulations
to this project, follow `docs/08_add_new_robot_assembly.md`.

## References

* onshape-to-robot docs: <https://onshape-to-robot.readthedocs.io/>
* Onshape API keys: <https://dev-portal.onshape.com/keys>
* ROS 2 Jazzy · robot_state_publisher · joint_state_publisher_gui · RViz2
