# 03 · Export pipeline (Onshape → URDF)

## One command per step

```bash
make check      # 1. .env keys + document access
make inspect    # 2. assembly structure: links, mates, joint verdict
make urdf       # 3. export URDF + STL meshes      (scripts/run_export.py)
make urdf-env   # 3b. export the environment       (Whole setup tab)
make sync       # 4. copy into the ROS 2 package   (scripts/sync_to_ros.py)
```

`make urdf` runs a **pre-flight** first: if no `dof_*` mate exists it aborts
with the exact renames instead of silently producing a rigid robot.

## What `make urdf` produces

```
export/
├── ur10.urdf           # the robot description
├── meshes/*.stl        # one mesh per link (visual = collision here)
└── inspect/*.json      # raw API dumps used by the inspector
```

Notes:

* Mesh references in the URDF are written as
  `package://ur10_robot_description/meshes/<part>.stl` because
  `package_name` is set in `export/config.json`.
* Masses/inertias come from the Onshape mass properties (real CAD data).
* Colors come from the part appearances in Onshape (the visible robot
  palette is applied later by `make sync` — see docs/06).
* Limits: Onshape mate limits if enabled, otherwise ±π with
  effort/velocity from `joint_properties` (`default`, `Revolute_base`, …).

## What `make urdf-env` produces (the cell around the robot)

The **table, stand, tube extender and glory machines** live in the Onshape
**"Whole setup"** tab (all mates FASTENED → one rigid link). This step is a
second, independent export that excludes the robot:

```bash
make urdf-env   # = scripts/dump_whole_setup.py + onshape-to-robot export_env/
```

```
export_env/
├── config.json           # points at the "Whole setup" tab; ignore = 36 UR10 parts
├── environment.urdf      # ONE link, 54 visuals, 54 colors
├── meshes/*.stl          # 22 meshes (table, stand parts, tubes, glory)
└── export.log
export/inspect/whole_setup.json   # read-only dump — source of the mount pose
```

Details (mount transform math, Cyrillic names, colors) are in
`docs/06_environment_and_colors.md`.

## What `make sync` changes

1. **Name sanitising** — spaces in joint/link names become `_`
   (TF frame ids cannot contain spaces).
2. **Mesh path rewriting** to `package://ur10_robot_description/meshes/…`
   and copies the STLs into the package (renaming files if needed).
   Non-ASCII (Cyrillic) mesh names are repaired (mojibake) and
   transliterated to ASCII.
3. **Environment merge** — if `export_env/environment.urdf` exists, it is
   appended as one fixed link `environment` with a `environment_mount`
   fixed joint on the root link; the mount origin is computed from the
   **root-link part occurrence** of the robot inside
   `export/inspect/whole_setup.json`
   (`T_mount = inv(T_part @ inv(T_R_part))` — never hard-coded; the
   sub-assembly origin is *not* used, see `docs/06`).
   The articulable-joint gate counts only non-fixed joints, so a rigid
   0-DOF export can never sneak past it via this fixed mount.
4. **Robot color palette** — the Onshape robot appearances are almost all
   grey, so sync recolors the robot parts with the classic white/blue UR
   look (`ROBOT_PALETTE`); the environment keeps its vivid CAD colors.
   Use `--cad-colors` to keep the raw Onshape appearances.
5. **Root link detection** → patches `rviz/ur10.rviz`
   `Global Options → Fixed Frame` automatically.
6. Prints the full kinematic chain (joint, type, parent → child, limits).

Outputs go to:

```
ros2_ws/src/ur10_robot_description/
├── urdf/ur10.urdf        # 8 links: 7 robot + environment
└── meshes/*.stl          # 50 files: 28 robot + 22 environment
```

## Configuration reference (`export/config.json`)

| Key | Value used here | Meaning |
|---|---|---|
| `url` | UR10 tab URL | which assembly to export |
| `output_format` | `urdf` | target format |
| `output_filename` | `ur10` | output file name |
| `assets_directory` | `meshes` | folder for STL files |
| `package_name` | `ur10_robot_description` | `package://` prefix for meshes |
| `ignore` | `table*`, `*machine*`, `*glory*` | drop non-robot geometry |
| `joint_properties` | `default` + per-joint | effort/velocity in `<limit>` |
| `round_decimals` | `6` | number formatting |

Full reference: <https://onshape-to-robot.readthedocs.io/en/latest/config.html>

The environment export (`export_env/config.json`) uses the same schema with
only `url` (Whole-setup tab), `output_filename` (`environment`) and an
`ignore` block listing the 36 UR10 part names so the robot geometry is not
duplicated.

## Speed tips

* **Response cache**: Onshape replies are cached in `~/.cache/onshape-to-robot`.
  Clear with `onshape-to-robot-clear-cache` if things look stale.
* **Split retrieve/convert** (fast iteration *after* the first export):

  ```bash
  onshape-to-robot export --save-pickle   # network (slow)
  onshape-to-robot export --convert       # local only (fast)
  ```

  Useful when tweaking `joint_properties`/`ignore` without re-downloading.
* STL generation is server-side — the first export spends most of its time
  downloading meshes (watch `export/export.log`).
