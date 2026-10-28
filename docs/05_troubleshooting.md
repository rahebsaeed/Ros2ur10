# 05 · Troubleshooting

## 🔴 The big one: mates broke over the API (0 joints exported)

**Symptom chain** (exactly what happened during this setup):

1. `onshape-to-robot` prints `* Found total 0 degrees of freedom`
2. The generated URDF has **1 link, 0 joints** (robot is rigid)
3. `scripts/inspect_assembly.py` shows mates with correct `dof_` names but
   **no `A <-> B` partners**
4. Onshape API: `GET /assemblies/.../features` returns
   `featureData.matedEntities: []` for the mates
5. Onshape API: `GET /features` → `featureStates` reports
   `"featureStatus": "ERROR"` for those mates

**Cause**: the mate was *updated through the API*
(`POST /assemblies/.../features/featureid/{fid}`). The server then regenerates
the feature's `nodeId`s and its **implicit mate connector ids**, while the
mate's `mateConnectorsQuery` still references the *old* connector ids →
dangling references → feature ERROR → no mated entities → no DOFs.
Every further API write regenerates the ids again, so **it cannot be repaired
over the API** (that is why `scripts/rename_mates.py` is disabled).

**Recovery (≈5 minutes, done in the Onshape UI):**

1. Open the document → **Versions and history** panel (clock icon).
2. Right-click the last entry from **before the API writes**
   (mates still named `Revolute base`, `shoulder`, `elbow`, `Revolute 2/3/4`
   — without `dof_`) → **Restore to…** → Main → confirm.
   *(Restore is non-destructive: later entries stay in history.)*
3. In the **UR10** tab, rename the 6 mates **manually**:
   double-click → name field → `dof_Revolute_base`, `dof_shoulder`,
   `dof_elbow`, `dof_Revolute_2`, `dof_Revolute_3`, `dof_Revolute_4` → ✓.
   UI renames never touch the connectors.
4. Verify, then continue:

   ```bash
   make inspect     # must print "Joints that WILL be exported : 6"
   make urdf && make sync && make build && make rviz
   ```

**Lesson (put this in the presentation 😉):** CAD-name conventions that drive
the export (`dof_` prefix) must be applied *inside CAD*, not through raw API
feature updates.

**What `make sync` does in this state (exit code 2):**

* ✅ all `export/meshes/*.stl` are copied into
  `ros2_ws/src/ur10_robot_description/meshes/` — geometry is independent of
  the joint state, so it always syncs (everything the URDF references *plus*
  every other exported STL, flattened to match the `package://` URIs).
* ❌ the package **URDF and RViz config are NOT written** — a rigid 1-link
  URDF must never overwrite a good one. The gate runs before any URDF write.

---

## `make check` fails

| Output | Meaning | Fix |
|---|---|---|
| "keys are not set yet" | `.env` still has placeholders | paste real keys (docs/01) |
| `401` | wrong key pair | re-copy both keys |
| `403` | keys valid, no document access | use keys of the account owning/sharing the doc |
| `404` | wrong id in the URL | re-copy the URL from the correct tab |

## `make inspect` says 0 joints / "no revolute mates at the ROOT"

* Mates missing the `dof_` prefix → rename in the UI (docs/02).
* Mates live *inside* a subassembly → joints must mate the top-level instances.
* Mates in ERROR state → see "The big one" above.

## URDF exports but RViz shows nothing / errors

* `Fixed Frame [x] does not exist` → re-run `make sync` (it patches the fixed
  frame from the URDF root link), rebuild, relaunch.
* Robot invisible → check `package://ur10_robot_description/meshes/...` files
  exist (`ls ros2_ws/src/ur10_robot_description/meshes/`), rebuild after `make sync`.
* `Failed to find root link` / multiple roots → the assembly produced several
  disconnected trees: fasten stray parts to the robot (or `fix_` mates), or
  exclude them via `ignore` in `export/config.json`.

## `make sync` → "No '<root link>' part occurrence under the robot instance"

Example (new robot exported, cell still from the old project):

```
[FAIL] No 'planetary_gearbox' part occurrence under the robot
       instance 'UR10' in the Whole setup dump.
       Robot parts found: ['Base <2>', 'Lower arm <1>', ...]
```

`sync` computes the environment mount from the **cell tab** declared in
`export_env/config.json` (via `export/inspect/whole_setup.json`). The failure
means the new robot's root link was not found inside that dump. Causes, in
order of likelihood:

1. **Stale dump** — the robot changed (new tab/document) since the last dump.
   Fix: `make urdf-env` (re-dumps the cell tab configured in
   `export_env/config.json`).
2. **Wrong `robot_instance`** — the instance of the robot inside the cell tab
   has another name. Fix: set `robot_instance` in `export/config.json`
   (prefix match: `"UR10"` matches `'UR10 <1>'`). The error prints the
   available top-level instances.
3. **The robot is not in that cell at all** (new robot, no cell yet) —
   there is nothing to mount. Fix: delete `export_env/environment.urdf`
   and re-run `make sync` — the environment merge is skipped automatically
   (robot-only URDF). See docs/08 → "Environment mount".

## RViz panels eat the whole window (3D view squeezed to a strip)

RViz2 **saves its layout back into the `.rviz` file on exit** (it writes to the
*installed* config under `ros2_ws/install/...`). A session that was closed in a
weird state (resized docks, maximized panels) can therefore come back with the
3D view squeezed to a sliver on the next launch.

* Fix: the serialized `QMainWindow State:` line was removed from
  `ros2_ws/src/ur10_robot_description/rviz/ur10.rviz`, so RViz always falls
  back to its default (sane) dock layout. If it ever breaks again, delete the
  `QMainWindow State:` line from the `.rviz` file and re-run `make build`.
* `make build` re-installs the pristine source config over whatever the last
  RViz session wrote into `install/` — so a rebuild also resets the layout.

## `ros2 launch` → package not found

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash     # every new terminal
ros2 pkg list | grep ur10             # must show ur10_robot_description
```

## `colcon build` → `ModuleNotFoundError: No module named 'catkin_pkg'`

CMake picked up a user-local Python (`~/.local/bin/python3.11`, uv-managed)
instead of the system interpreter ROS 2 Jazzy is built against. Fix:

```bash
rm -rf ros2_ws/build ros2_ws/install ros2_ws/log
bash -c "source /opt/ros/jazzy/setup.bash && cd ros2_ws && \
  colcon build --packages-select ur10_robot_description \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3"
```

The `Makefile` `build` target already passes this `-DPython3_EXECUTABLE`
flag, so a plain `make build` works. Clean `build/` if a cache with the
wrong interpreter already exists (stale `Python3_EXECUTABLE:INTERNAL=` in
`ros2_ws/build/*/CMakeCache.txt`).

## Export is slow / looks stale

* First export downloads every STL (server-side tessellation) — watch
  `export/export.log`.
* After config-only changes use the pickle:

  ```bash
  .venv/bin/onshape-to-robot export --save-pickle   # network (slow)
  .venv/bin/onshape-to-robot export --convert       # local (fast)
  ```

* Stale API cache: `onshape-to-robot-clear-cache` (cache lives in
  `~/.cache/onshape-to-robot`).

## "has no dynamics (maybe it is a surface)" warnings

Harmless for RViz: the part has no solid mass properties in CAD; inertia is
zeroed. Visualization, TF and joint control are unaffected.

## Joint moves the wrong direction

Add the `_inv` suffix in Onshape (`dof_Revolute_2_inv`), re-export — or just
note it during the demo.
