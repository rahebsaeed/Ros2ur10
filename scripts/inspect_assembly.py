#!/usr/bin/env python3
"""
inspect_assembly.py — read the Onshape assembly and explain what the
onshape-to-robot exporter WILL do with it, before spending an export:

  * lists top-level instances   -> become URDF *links*
                                   (the FIRST one becomes the base link)
  * lists mates                 -> only mates named `dof_...` become *joints*
  * lists mate connectors       -> `link_...` renames links, `frame_...` adds frames
  * prints warnings + the exact renames needed for the UR10 DOFs

Raw JSON dumps are saved under export/inspect/ for reference.

Run:  python scripts/inspect_assembly.py     (or: make inspect)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    EXPORT_DIR,
    get_assembly_ids,
    load_export_config,
    make_client,
    wmv_selector,
)

INSPECT_DIR = EXPORT_DIR / "inspect"

# The 6 UR10 articulations the user wants to control (Onshape feature names)
UR10_EXPECTED = ["Revolute base", "shoulder", "elbow", "Revolute 2", "Revolute 3", "Revolute 4"]

MATE_MEANING = {
    "dof_": "JOINT (revolute/prismatic — this is a DOF)",
    "fix_": "MERGE (bodies fused into one link)",
    "frame_": "FRAME (dummy link / TF frame)",
    "closing_": "LOOP CLOSURE",
    "(none)": "IGNORED by the exporter",
}


def sanitize(name: str) -> str:
    """Onshape mate name -> recommended suffix after dof_ (no spaces)."""
    return re.sub(r"\s+", "_", name.strip())


def rule_for(name: str, mate_type: str) -> str:
    if name.startswith("dof_"):
        kind = "JOINT"
        if mate_type in ("FASTENED",):
            kind = "JOINT (type overridden to fixed by FASTENED)"
        return f"{kind}: {name[4:] or '(MISSING NAME)'}"
    if name.startswith("fix_"):
        return MATE_MEANING["fix_"]
    if name.startswith("frame_"):
        return MATE_MEANING["frame_"]
    if name.startswith("closing_"):
        return MATE_MEANING["closing_"]
    if mate_type == "FASTENED":
        return "MERGE (unnamed fastened mate -> bodies fused)"
    return MATE_MEANING["(none)"]


def main() -> int:
    ids = get_assembly_ids()
    config = load_export_config()
    wmv, wmvid = wmv_selector(ids)
    configuration = config.get("configuration", "default")
    if isinstance(configuration, dict):
        configuration = ";".join(f"{k}={v}" for k, v in configuration.items())

    client = make_client()
    print("Fetching assembly from Onshape ...")

    doc = client.get_document(ids["document_id"])
    asm = client.get_assembly(
        ids["document_id"], wmvid, ids["element_id"],
        wmv=wmv, configuration=configuration,
    )

    INSPECT_DIR.mkdir(parents=True, exist_ok=True)
    (INSPECT_DIR / "document.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    (INSPECT_DIR / "assembly.json").write_text(json.dumps(asm, indent=2), encoding="utf-8")

    root = asm.get("rootAssembly", {})
    instances = root.get("instances", [])
    features = root.get("features", [])

    # ------------------------------------------------------------------ header
    print()
    print("=" * 74)
    print(f' Document : {doc.get("name", "?")}')
    print(f' Assembly : {root.get("name", "(root)")}')
    print(f" URL      : {config.get('url')}")
    print("=" * 74)

    # ------------------------------------------------------------- subassemblies
    subassemblies = asm.get("subAssemblies", [])
    if subassemblies:
        print("\n SUB-ASSEMBLIES (exported as single rigid links):")
        for s in subassemblies:
            print(f"   - {s.get('name', '?')}")

    # ---------------------------------------------------------------- instances
    print(f"\n TOP-LEVEL INSTANCES -> URDF LINKS ({len(instances)}):")
    if instances:
        print("   (the FIRST instance becomes the BASE LINK of the robot)")
    for idx, inst in enumerate(instances):
        marker = "  <- BASE LINK" if idx == 0 else ""
        name = inst.get("name", inst.get("id", "?"))
        print(f"   [{idx:2d}] {name}{marker}")

    # ------------------------------------------------------------------- mates
    mates = [f for f in features if f.get("featureType") == "mate" and not f.get("suppressed")]
    connectors = [f for f in features if f.get("featureType") == "mateConnector" and not f.get("suppressed")]
    groups = [f for f in features if f.get("featureType") == "mateGroup" and not f.get("suppressed")]

    id2name = {i.get("id"): i.get("name", i.get("id", "?")) for i in instances}

    def occ_name(occurrence_path) -> str:
        if isinstance(occurrence_path, list) and occurrence_path:
            return id2name.get(occurrence_path[0], str(occurrence_path[0]))
        return str(occurrence_path)

    print(f"\n MATES -> only `dof_*` become joints ({len(mates)} mates, {len(groups)} mate groups):")
    dofs, non_dof_revolute, broken = [], [], []
    for f in mates:
        data = f.get("featureData", {})
        name = data.get("name", "")
        mtype = data.get("mateType", "?")
        ents = data.get("matedEntities", [])
        between = ""
        if len(ents) == 2:
            a = occ_name(ents[0].get("matedOccurrence", [None])[0] if ents[0].get("matedOccurrence") else None)
            b = occ_name(ents[1].get("matedOccurrence", [None])[0] if ents[1].get("matedOccurrence") else None)
            between = f" :  {a}  <->  {b}"
        print(f"   - {name or '(unnamed)'} [{mtype}]{between}")
        print(f"       -> {rule_for(name, mtype)}")
        if name.startswith("dof_"):
            if len(ents) == 2:
                dofs.append(name)
            else:
                broken.append(name)
                print("       [FAIL] NO mated entities — the mate is broken (ERROR state).")
                print("              Recovery: restore history + rename in the UI")
                print("              (docs/05_troubleshooting.md -> 'The big one')")
        elif mtype in ("REVOLUTE", "CYLINDRICAL", "SLIDER"):
            non_dof_revolute.append((name, mtype))

    if connectors:
        print(f"\n MATE CONNECTORS ({len(connectors)}):")
        for f in connectors:
            name = f.get("featureData", {}).get("name", "")
            note = ""
            if name.startswith("link_"):
                note = f"  -> renames link to '{name[5:]}'"
            elif name.startswith("frame_"):
                note = f"  -> creates TF frame '{name[6:]}'"
            elif name:
                note = "  (no prefix -> not used by the exporter)"
            print(f"   - {name}{note}")

    # ----------------------------------------------------------------- verdict
    print("\n" + "=" * 74)
    print(" VERDICT")
    print("=" * 74)
    print(f"   Joints that WILL be exported : {len(dofs)}")
    for d in dofs:
        print(f"       - {d[4:]}")

    exit_code = 0
    if broken:
        exit_code = 3
        print(f"\n   [FAIL] {len(broken)} dof_* mate(s) have NO entities (ERROR state):")
        for b in broken:
            print(f"       - {b}")
        print("   Recovery (Onshape UI, ~5 min):")
        print("     1. Versions and history panel -> right-click the entry from BEFORE")
        print("        the API writes -> 'Restore to...' -> Main")
        print("     2. Rename the 6 mates manually in the UR10 tab (docs/02)")
        print("     3. Re-run: make inspect")
    elif len(dofs) == 0:
        exit_code = 2
        print("\n   [FAIL] No joint will be exported! The robot would be RIGID in RViz.")
        if non_dof_revolute:
            print("\n   Required Onshape renames (rename the features in the assembly tree):")
            print("   (dof_ prefix = DOF, no spaces; the exported joint keeps the rest)")
            for name, mtype in non_dof_revolute:
                suggestion = f"dof_{sanitize(name) if name else 'JOINT_NAME'}"
                print(f"       '{name or '(unnamed)'}' [{mtype}]  ->  rename to  '{suggestion}'")
        else:
            print("\n   No revolute/slider mates found at the ROOT of the assembly.")
            print("   Make sure the joint mates live in this assembly (not inside a")
            print("   subassembly), and see docs/02_onshape_assembly_setup.md.")
    elif non_dof_revolute:
        print(f"\n   [WARN] {len(non_dof_revolute)} movable mate(s) will be IGNORED "
              "(missing dof_ prefix):")
        for name, mtype in non_dof_revolute:
            print(f"       '{name}' [{mtype}]  ->  rename to  'dof_{sanitize(name)}'")
    elif len(dofs) < 6:
        print(f"\n   [WARN] UR10 expects 6 DOFs, found {len(dofs)}.")
        print("   Check docs/02_onshape_assembly_setup.md if joints are missing.")
    else:
        print("\n   [OK] All expected DOFs present — ready for export.")
        print("        Next:  python scripts/run_export.py")

    # ------------------------------------------------------- ignore suggestions
    ignore_cfg = config.get("ignore", {})
    if ignore_cfg:
        print("\n   Parts excluded by export/config.json \"ignore\":")
        for pattern, what in ignore_cfg.items():
            print(f"       {pattern!r} -> {what}")
    print(f"\n   Raw dumps written to: {INSPECT_DIR}/")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
