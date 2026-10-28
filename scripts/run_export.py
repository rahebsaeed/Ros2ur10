#!/usr/bin/env python3
"""
run_export.py — run the Onshape -> URDF export.

  1. validates the .env keys
  2. pre-flight: aborts if the assembly has NO `dof_*` mates (would produce
     a rigid robot) and prints the exact renames to fix it
  3. executes `onshape-to-robot export/` (streams its output)
  4. reports what was produced + the next step

Run:   python scripts/run_export.py          (or: make urdf)
       python scripts/run_export.py --force  (skip the DOF pre-flight)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    EXPORT_DIR,
    PROJECT_ROOT,
    get_assembly_ids,
    load_export_config,
    make_client,
    wmv_selector,
)


def find_cli() -> str:
    """Path of the onshape-to-robot executable (same venv as this script)."""
    candidate = Path(sys.executable).with_name("onshape-to-robot")
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("onshape-to-robot")
    if found:
        return found
    sys.exit("[FAIL] onshape-to-robot not found. Run: pip install onshape-to-robot")


def preflight(client) -> int:
    """Count movable mates and dof_ mates; return exit code if we should abort."""
    ids = get_assembly_ids()
    config = load_export_config()
    wmv, wmvid = wmv_selector(ids)
    configuration = config.get("configuration", "default")
    if isinstance(configuration, dict):
        configuration = ";".join(f"{k}={v}" for k, v in configuration.items())

    print("[1/2] Pre-flight: checking that the assembly has DOF mates ...")
    asm = client.get_assembly(
        ids["document_id"], wmvid, ids["element_id"],
        wmv=wmv, configuration=configuration,
    )
    features = asm.get("rootAssembly", {}).get("features", [])
    mates = [f for f in features if f.get("featureType") == "mate" and not f.get("suppressed")]
    dofs = [f for f in mates if f.get("featureData", {}).get("name", "").startswith("dof_")]
    movable = [
        f for f in mates
        if f.get("featureData", {}).get("mateType") in ("REVOLUTE", "CYLINDRICAL", "SLIDER")
        and not f.get("featureData", {}).get("name", "").startswith("dof_")
    ]

    print(f"       dof_* joints : {len(dofs)}")
    print(f"       total mates  : {len(mates)}")
    if dofs == 0:
        print("\n       [FAIL] No mate named 'dof_*' -> the export would be RIGID.")
        print("       Rename your 6 revolute mates in the Onshape assembly, e.g.:")
        print("           'Revolute base' -> 'dof_Revolute_base'")
        print("           'shoulder'      -> 'dof_shoulder'")
        print("           'elbow'         -> 'dof_elbow'")
        print("           'Revolute 2'    -> 'dof_Revolute_2'")
        print("           'Revolute 3'    -> 'dof_Revolute_3'")
        print("           'Revolute 4'    -> 'dof_Revolute_4'")
        print("       Full guide: docs/02_onshape_assembly_setup.md")
        return 2
    if movable:
        print(f"\n       [WARN] {len(movable)} movable mate(s) missing the dof_ prefix "
              "(they will be IGNORED):")
        for f in movable:
            name = f["featureData"].get("name", "(unnamed)")
            print(f"           '{name}'  ->  'dof_{name.replace(' ', '_')}'")
    return 0


def main() -> int:
    force = "--force" in sys.argv
    print("Onshape -> URDF export (onshape-to-robot)")
    print("=" * 64)

    client = make_client()  # validates .env keys, exits with help if unset

    if not force:
        code = preflight(client)
        if code != 0:
            return code

    cli = find_cli()
    print("\n[2/2] Running:", cli, str(EXPORT_DIR.relative_to(PROJECT_ROOT)))
    print("-" * 64)
    proc = subprocess.run([cli, str(EXPORT_DIR)], cwd=str(PROJECT_ROOT))
    print("-" * 64)
    if proc.returncode != 0:
        print("[FAIL] Export failed — see messages above "
              "(credentials? assembly structure? docs/05_troubleshooting.md)")
        return proc.returncode

    config = load_export_config()
    out_name = config.get("output_filename", "robot")
    urdf = EXPORT_DIR / f"{out_name}.urdf"
    assets = EXPORT_DIR / config.get("assets_directory", "assets")
    stls = list(assets.glob("*.stl")) if assets.is_dir() else []

    if not urdf.is_file():
        print(f"[FAIL] Expected output missing: {urdf}")
        return 1

    print(f"[OK] URDF  : {urdf}")
    print(f"[OK] Meshes: {len(stls)} STL files in {assets}")
    print("\nNext step:  python scripts/sync_to_ros.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
