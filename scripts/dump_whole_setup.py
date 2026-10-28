#!/usr/bin/env python3
"""
dump_whole_setup.py — fetch the "Whole setup" assembly (READ-ONLY) and save
export/inspect/whole_setup.json.

Why: sync_to_ros.py needs the Onshape transform of the "UR10 <1>" instance
inside "Whole setup" to mount the exported environment (table/stand/tube/glory)
at the correct pose relative to the robot base link.

The "Whole setup" element id is taken from export_env/config.json (the same
URL the environment export uses), so config and dump can never drift apart.

Run:  python scripts/dump_whole_setup.py        (or: make urdf-env)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    EXPORT_DIR,
    PROJECT_ROOT,
    make_client,
    signed_get,
    wmv_selector,
)

ENV_CONFIG = PROJECT_ROOT / "export_env" / "config.json"
OUT_FILE = EXPORT_DIR / "inspect" / "whole_setup.json"


def element_ids_from_env_config() -> dict:
    """Parse document/workspace ids + the Whole setup element id from the
    environment config URL."""
    import commentjson  # ships with onshape-to-robot

    if not ENV_CONFIG.is_file():
        sys.exit(f"[FAIL] Missing {ENV_CONFIG} — the environment export is not configured.")
    url = str(commentjson.loads(ENV_CONFIG.read_text(encoding="utf-8")).get("url", ""))
    parts = [p for p in url.split("/") if p]
    ids = {"document_id": None, "workspace_id": None, "version_id": None, "element_id": None}
    try:
        i = parts.index("documents")
        ids["document_id"] = parts[i + 1]
        if parts[i + 2] in ("w", "v"):
            ids[{"w": "workspace_id", "v": "version_id"}[parts[i + 2]]] = parts[i + 3]
        ids["element_id"] = parts[parts.index("e") + 1]
    except (ValueError, IndexError):
        sys.exit(f"[FAIL] Could not parse ids from the env config url: {url}")
    if not ids["document_id"] or not ids["element_id"]:
        sys.exit(f"[FAIL] Incomplete ids parsed from: {url}")
    return ids


def main() -> int:
    ids = element_ids_from_env_config()
    client = make_client()

    # Use the workspace when the URL points at one, else the version
    wmv, wmvid = ("w", ids["workspace_id"]) if ids["workspace_id"] else ("v", ids["version_id"])
    print(f"Fetching 'Whole setup' assembly ({wmv}/{wmvid}) ...")

    asm = signed_get(
        client,
        f"/api/assemblies/d/{ids['document_id']}/{wmv}/{wmvid}/e/{ids['element_id']}",
        {"configuration": "default"},
    ).json()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(asm, indent=2), encoding="utf-8")

    root = asm.get("rootAssembly", {})
    instances = root.get("instances", [])
    occurrences = root.get("occurrences", [])
    mates = [
        f for f in root.get("features", [])
        if f.get("featureType") == "mate" and not f.get("suppressed")
    ]
    print(f"  top-level instances : {len(instances)}")
    for i in instances:
        print(f"    - {i.get('name')}")
    print(f"  occurrences         : {len(occurrences)}")
    print(f"  root mates          : {len(mates)} "
          f"({sum(1 for m in mates if m.get('featureData', {}).get('mateType') == 'FASTENED')} FASTENED)")
    print(f"Saved -> {OUT_FILE.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
