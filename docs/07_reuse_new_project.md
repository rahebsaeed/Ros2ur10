# 07 · Reuse: point the pipeline at a new Onshape project

Everything downstream of the export is **generic**: change the two configs and
the Onshape assembly, not the code. This is the checklist for running the same
CAD → URDF → ROS 2 → RViz2 process on your own robot/cell.

Hands-on assembly guide (create the tab, add articulations, switch robot):
`docs/08_add_new_robot_assembly.md`.

---

## 1. What is already generic (no code changes needed)

| Piece | Driven by |
|---|---|
| Output names `urdf/*.urdf`, `rviz/*.rviz` | `output_filename` in `export/config.json` |
| Launch file discovery of URDF + RViz config | glob `urdf/*.urdf` + `rviz/*.rviz` (any name works) |
| Root link (RViz `Fixed Frame`) | auto-detected from the URDF tree |
| Environment mount pose | computed from the Whole-setup dump + `robot_instance` |
| Robot look | `ROBOT_PALETTE` wildcards in `scripts/sync_to_ros.py` (`--cad-colors` to keep CAD look) |
| Package / mesh URIs | `package_name` in the configs |

---

## 2. Checklist — new project

### Step 1 — CAD (Onshape or any CAD that can export an assembly)

* Two assembly tabs (elements) in one document:
  * **Robot tab** — the robot alone, its joints as mates renamed with the
    `dof_` prefix (`dof_shoulder`, …) → one URDF `revolute` joint each
    (see `docs/02`).
  * **Cell tab** — robot + table/tube/machines, cell mates `FASTENED`
    (0 DOF), the cell fixed to the robot's base.
* Never rename/create mates through the API — only in the UI
  (API writes broke mates, see `docs/05`).

### Step 2 — API keys

* Put the new document's keys in `.env`: `ONSHAPE_ACCESS_KEY` +
  `ONSHAPE_SECRET_KEY` (see `docs/01`). Never commit them.

### Step 3 — `export/config.json` (robot export)

Change at least:

* `url` → the **robot** assembly tab of the new document.
* `robot_instance` → the robot's instance name in the cell tab
  (e.g. `UR10 <1>` → `UR10`); used to find the root-link part for the mount.
* `output_filename` → your robot name (drives all output file names).
* `package_name` → your ROS 2 package name.
* `ignore` → exclude anything in the robot tab that is not the robot
  (`make inspect` lists the real part names).
* `joint_properties` → effort/velocity per joint name.

### Step 4 — `export_env/config.json` (cell export)

* `url` → the **cell** assembly tab.
* `ignore` → every robot part (the robot comes from the robot export;
  `make inspect` gives the exact names).
* `output_filename`, `package_name` → same package as Step 3.

### Step 5 — Export and verify

```bash
make check      # .env keys + document access
make inspect    # real instance/mate/part names (for ignore, robot_instance)
make urdf       # robot  -> export/<name>.urdf + meshes
make urdf-env   # cell   -> export_env/ (only if you have a cell tab)
```

Gate: the export must contain **≥ 1 non-fixed joint**, otherwise `make sync`
stops — a 0-DOF cell can never pass for a robot.

### Step 6 — ROS 2 + RViz2

```bash
make sync       # into the package: names, meshes, mount, palette, RViz frame
make build      # colcon build
make rviz       # RViz2 + joint sliders
```

### Step 7 — Verify (see `docs/04`)

* Sliders + **Randomize**: every joint moves, the cell stays fixed.
* `ros2 run tf2_ros tf2_echo base tool_flange` — numbers change with the pose.
* `base → environment` never changes → the mount is correct.

---

## 3. Changing the articulations (number / names)

1. Rename the mates in the **Onshape UI** with the `dof_` prefix — the
   number of `dof_*` revolute mates *is* the number of joints in the URDF.
2. Update `joint_properties` in `export/config.json` — the keys match the
   exported joint names (the `dof_` prefix is stripped by the exporter).
3. Re-run Steps 5–6; `make inspect` shows the mate names before you export.
4. If a joint is missing in RViz, its mate lost the `dof_` prefix or was
   suppressed — fix in the UI and re-export (never via the API).

---

## 4. If something breaks

* Mount/robot detached from the cell → `robot_instance` or the root-link
  part name no longer matches the dump (`make urdf-env` refreshes it).
* Stale model after editing Onshape → `make urdf urdf-env sync build`.
* Everything else: `docs/05_troubleshooting.md`.
