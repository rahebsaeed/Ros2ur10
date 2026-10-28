# 08 · Adding a new robot assembly (or switching to another robot)

This is the hands-on guide for two situations:

* **A. Add a new robot assembly to this project** — you built a new robot
  (or a new version) in Onshape and want the same pipeline to export *it*.
* **B. Modify the project for another robot** — replace the UR10 with a
  different arm/cell entirely.

Config-level checklist: `docs/07_reuse_new_project.md`.
Mate naming rules (reference): `docs/02_onshape_assembly_setup.md`.

---

## 0. What the pipeline reads (so you know what to touch)

```
Onshape tab (assembly)  --url-->  export/config.json  --make urdf-->  export/*.urdf
                                                                          |
                                             make sync  (names, meshes, mount, palette)
                                                                          v
                                   ros2_ws/src/<package>/  --make build--> RViz2
```

Only **two configs** (`export/config.json`, `export_env/config.json`), the
**`.env` keys** and the **Onshape assembly** are inputs — the scripts stay
untouched.

---

## A. Add a new robot assembly in this project

### Step 1 — Create the robot tab in Onshape

1. Open the project document → **+ Tab** → *Create assembly* → name it
   (e.g. `MyRobot`). Keep the existing `UR10` tab — nothing breaks.
2. Insert/assemble the robot parts in that tab.
3. Order matters: the **first instance in the assembly tree becomes the
   `base` link** (root link, RViz Fixed Frame). Put the fixed base first.
4. Mates must be **top-level mates of the tab** whose instances are the
   robot links — joints inside a sub-assembly are NOT exported
   (`make inspect` prints `0 joints` in that case).

### Step 2 — Add the articulations (mates → joints)

Create one mate per joint in the UI, then rename it with the `dof_` prefix:

| Mate type in Onshape | `dof_` name example | URDF joint |
|---|---|---|
| Revolute / Cylindrical | `dof_shoulder` | `revolute` (rotary) |
| Slider | `dof_lift` | `prismatic` (linear) |
| Fastened (with `dof_`) | `dof_gripper` | `fixed` (no DOF) |
| any mate **without** `dof_` | `pin_join` | ignored (bodies stay separate) |

Naming rules (full table in `docs/02`):

* prefix **`dof_`**, no spaces (use `_`), exported joint = name minus `dof_`.
* suffix `_inv` → invert the rotation direction (`dof_elbow_inv`).
* `fix_<name>` → merge two bodies into one link.
* `frame_<name>` → extra TF frame (e.g. tool tip), `link_<name>` → rename link.
* joint axis = the mate's **Z axis**; enable the mate's **limits** checkbox to
  export real `<limit>` bounds (otherwise `joint_properties` / ±π are used).

> ⚠️ **Never create/rename mates through the API** — it breaks the mate's
> connectors and the export sees 0 joints (`docs/05`). UI only.

**The number of `dof_*` mates = the number of joints in the URDF.**

### Step 3 — Wire the configs

`export/config.json`:

| Key | Change to |
|---|---|
| `url` | the **new robot tab** assembly URL (`.../e/<element id>`) |
| `output_filename` | new output name → `export/<name>.urdf`, `<name>.rviz` |
| `robot_name` | robot name inside the URDF |
| `robot_instance` | only if the robot also sits in the cell tab (`MyRobot <1>` → `MyRobot`) |
| `ignore` | exclude non-robot parts in that tab (`make inspect` lists real names) |
| `joint_properties` | keys = exported joint names (without `dof_`), effort/velocity |
| `package_name` | keep `ur10_robot_description`, or rename — see §B step 3 |

`export_env/config.json` — **only if** you also want the cell/scene:

| Key | Change to |
|---|---|
| `url` | the cell tab (e.g. `Whole setup`) where robot + environment coexist |
| `ignore` | every robot part (the robot comes from its own export) |

`.env` — only if the assembly lives in a **new document/account**: new
`ONSHAPE_ACCESS_KEY` / `ONSHAPE_SECRET_KEY` (`docs/01`).

### Step 4 — Export, sync, verify

```bash
make check      # keys + document reachable
make inspect    # MUST list your dof_* joints (see expected output below)
make urdf       # export the new robot
make urdf-env   # only if you have a cell tab
make sync       # into the ROS 2 package (+ mount, palette, RViz frame)
make build
make rviz
```

Expected `make inspect` tail:

```
 Joints that WILL be exported : 6
   - Revolute_base
   - shoulder
   ...
[OK] All expected DOFs present — ready for export.
```

In RViz: the **slider count = exported joint count**, `Randomize` moves every
joint, the cell (if any) stays fixed.

> `make sync` refuses to run with **0 non-fixed joints** — a static model can
> never pass for a robot.

---

## B. Modify the project for another robot (replace the UR10)

1. **Onshape** — in the robot tab, replace the parts/mates with the new
   robot's (or point at a completely different document tab).
2. **`export/config.json`** — `url`, `output_filename`, `robot_name`,
   `ignore`, `joint_properties` (see table above).
3. **Package name (optional)** — outputs follow `output_filename`
   automatically (`urdf/<name>.urdf`, `rviz/<name>.rviz`, launch globs them).
   Renaming the *package folder* itself needs 2 extra edits:
   * `scripts/onshape_common.py` → `ROS_PACKAGE`, `PACKAGE_NAME`
   * `Makefile` → `PKG`
4. **`export_env/config.json`** — `url` + `ignore` (robot parts) if you have
   a cell; refresh the dump so the mount is recomputed (`make urdf-env`).
5. **Palette (optional)** — `ROBOT_PALETTE` in `scripts/sync_to_ros.py`
   colors the robot by part-name wildcards; `python scripts/sync_to_ros.py
   --cad-colors` keeps raw CAD colors instead.
6. Run §A Step 4 (export → sync → build → rviz).

Nothing else changes: root link is auto-detected, output file names follow
`output_filename`, the launch file discovers any `urdf/*.urdf` +
`rviz/*.rviz`, and the environment mount is computed from the dump.

---

## C. Adding / removing / renaming articulations later

| Change in Onshape (UI) | Then run | Also update |
|---|---|---|
| **Add** a joint → create mate, rename `dof_*` | `make urdf sync build` | `joint_properties` (optional — `default` applies) |
| **Remove** a joint → delete mate or drop the `dof_` prefix | `make urdf sync build` | remove its `joint_properties` entry |
| **Rename** a joint → rename the mate | `make urdf sync build` | `joint_properties` key (matches the new name) |
| **Invert** axis → rename `..._inv` | `make urdf sync build` | — |
| **Limits** → enable on the mate | `make urdf sync build` | or set `joint_properties` |
| **New cell parts** → add to cell tab | `make urdf-env sync build` | cell `ignore` if they are robot parts |

Always finish with `make inspect` (count/names) + RViz `Randomize` (motion).

---

## D. Quick checklist (copy/paste)

```text
[ ] Onshape: new/updated tab, base first, top-level mates
[ ] Mates renamed dof_* (no spaces), limits set
[ ] export/config.json  : url, output_filename, ignore, joint_properties
[ ] export_env/config.json : url, ignore (cell only)
[ ] .env : keys for the document (docs/01)
[ ] make check inspect urdf [urdf-env] sync build rviz
[ ] RViz : slider count = joint count, Randomize OK, cell fixed
```

Troubleshooting: `docs/05_troubleshooting.md`.
Reuse checklist for a brand-new project: `docs/07_reuse_new_project.md`.
