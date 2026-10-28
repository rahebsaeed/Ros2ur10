#!/usr/bin/env python3
"""
rename_mates.py — ⚠️  DEPRECATED / DANGEROUS — kept for reference only.

WHY IT IS GATED:
Updating a mate through the Onshape API (POST .../features/featureid/{fid})
makes the server REGENERATE the feature's nodeIds and its implicit mate
connector ids, while the mate's `mateConnectorsQuery` still references the
OLD connector ids. The mate then evaluates to ERROR, and the assembly API
returns `matedEntities: []` for it — onshape-to-robot sees "0 degrees of
freedom". Every subsequent API write regenerates the ids again (whack-a-mole),
so this CANNOT be repaired over the API.

THE SAFE WAY (do it in the Onshape UI — 15 seconds per mate):
  1. Double-click the mate in the UR10 assembly tree
  2. Edit the name field:  dof_Revolute_base, dof_shoulder, dof_elbow,
     dof_Revolute_2, dof_Revolute_3, dof_Revolute_4
  3. Click the green checkmark
UI renames only touch the name — nothing else changes.

If your mates are already broken by this script: use the Onshape
"Versions and history" panel, right-click the entry from before the API
writes and "Restore to…", then rename manually (docs/02, docs/05).

The old behavior is still reachable with:  --i-know-what-im-doing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    get_assembly_ids,
    load_export_config,
    make_client,
    wmv_selector,
)

V2_JSON = "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.2"
MOVABLE = ("REVOLUTE", "CYLINDRICAL", "SLIDER")

DANGER_OK = "--i-know-what-im-doing" in sys.argv


def mate_type(msg: dict) -> str | None:
    """Read the mate type from a GET /features message (enum parameter)."""
    if msg.get("featureType") != "mate":
        return None
    for p in msg.get("parameters", []):
        pm = p.get("message", {})
        if pm.get("parameterId") == "mateType":
            return pm.get("value")
    return None


def sanitize(name: str) -> str:
    return re.sub(r"\s+", "_", name.strip())


def post_update(client, ids, feature_id: str, feature: dict) -> tuple[int, str]:
    """POST an updated feature definition; returns (status, response text).

    The body MUST be the full read-envelope {type, typeName, message} inside
    `feature` (bare BTMFeature objects are rejected with 400).

    Reuses the bundled client's HMAC signing (`_make_headers`) but performs
    the HTTP call directly, so we get the status code instead of the
    client's built-in exit() on non-2xx responses.
    """
    import json as _json

    import requests

    path = (
        f"/api/assemblies/d/{ids['document_id']}/w/{ids['workspace_id']}"
        f"/e/{ids['element_id']}/features/featureid/{feature_id}"
    )
    api = client._api
    headers = api._make_headers("post", path, query={}, headers={"Content-Type": V2_JSON})
    url = api._url + path
    try:
        res = requests.request(
            "post", url, headers=headers,
            data=_json.dumps({"feature": feature}),
            allow_redirects=False, timeout=60,
        )
        return res.status_code, res.text[:400]
    except requests.RequestException as exc:
        return 0, str(exc)


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    if not DANGER_OK:
        print("=" * 70)
        print(" rename_mates.py is DISABLED — API mate renames BREAK the mates.")
        print("=" * 70)
        print(__doc__)
        if dry_run:
            print("(--dry-run was given: nothing would be written anyway.)")
        return 2

    print("[WARN] --i-know-what-im-doing given: proceeding despite the risk.")
    ids = get_assembly_ids()
    config = load_export_config()
    wmv, wmvid = wmv_selector(ids)
    if wmv != "w":
        sys.exit("[FAIL] Renaming requires a workspace URL (…/w/…), not a version.")
    configuration = config.get("configuration", "default")
    if isinstance(configuration, dict):
        configuration = ";".join(f"{k}={v}" for k, v in configuration.items())

    client = make_client()
    print(f"Assembly element: {ids['element_id']}")
    feats = client.get_features(
        ids["document_id"], ids["workspace_id"], ids["element_id"],
        wmv="w", configuration=configuration,
    )

    todo = []
    for f in feats.get("features", []):
        msg = f.get("message", {})
        name = msg.get("name", "")
        if mate_type(msg) not in MOVABLE:
            continue
        if name.startswith("dof_"):
            print(f"  [skip]   {name}  (already prefixed)")
            continue
        new_name = f"dof_{sanitize(name)}"
        envelope = {"type": f.get("type"), "typeName": f.get("typeName"), "message": msg}
        todo.append((msg.get("featureId"), name, new_name, msg, envelope))

    if not todo:
        print("[OK] Nothing to rename — all movable mates already have dof_.")
        return 0

    print(f"\n{'DRY-RUN: ' if dry_run else ''}Renaming {len(todo)} mate(s):")
    for fid, old, new, _msg, _env in todo:
        print(f"    {old!r}  ->  {new!r}   (featureId {fid})")

    if dry_run:
        print("\n(dry run — nothing was changed)")
        return 0

    failures = 0
    for fid, old, new, msg, envelope in todo:
        envelope["message"]["name"] = new
        status, text = post_update(client, ids, fid, envelope)
        if 200 <= status <= 206:
            print(f"  [OK]   {old} -> {new}")
        else:
            failures += 1
            print(f"  [FAIL] {old}: HTTP {status} {text}")
            envelope["message"]["name"] = old  # restore for consistency

    # ---- verify by re-reading ------------------------------------------
    print("\nVerifying ...")
    feats = client.get_features(
        ids["document_id"], ids["workspace_id"], ids["element_id"],
        wmv="w", configuration=configuration,
    )
    names = [
        f["message"].get("name", "")
        for f in feats.get("features", [])
        if f.get("message", {}).get("featureType") == "mate"
    ]
    renamed = [n for n in names if n.startswith("dof_")]
    for n in sorted(names):
        print(f"    - {n}")

    if len(renamed) >= 6 and failures == 0:
        print(f"\n[OK] {len(renamed)} dof_* mates ready. Next: python scripts/inspect_assembly.py")
        return 0
    if failures:
        print("\n[FAIL] Some updates were rejected (message above).")
        print("       Fallback: rename the mates manually in the Onshape tree")
        print("       (docs/02_onshape_assembly_setup.md).")
        return 2
    print(f"\n[WARN] Only {len(renamed)} dof_* mates found (expected 6).")
    return 3


if __name__ == "__main__":
    sys.exit(main())
