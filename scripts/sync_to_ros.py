#!/usr/bin/env python3
"""
sync_to_ros.py — copy the export into the ROS 2 package and make it launchable.

What it does:
  * reads export/<name>.urdf (the articulated UR10)
  * reads export_env/environment.urdf (table/stand/tube/glory, optional)
      - merges it into the robot URDF as ONE fixed link "environment"
      - mounts it with the transform of the robot ROOT-LINK PART inside
        "Whole setup" (export/inspect/whole_setup.json), which is the pose
        the mates actually constrain — NOT the sub-assembly origin
  * sanitises joint/link names (spaces -> '_', TF cannot use spaces)
  * transliterates non-ASCII (Cyrillic) mesh file names to ASCII
  * rewrites mesh references to package://ur10_robot_description/meshes/...
  * copies the STL meshes (robot + environment) into the ROS package
  * applies the visible color palette to the ROBOT parts
      (Onshape robot appearances are almost all grey -> the palette gives
       the classic white-body/blue-joints UR look; the environment keeps
       its own vivid Onshape colors). Use --cad-colors to keep the raw
       Onshape appearances instead.
  * detects the ROOT link and patches the RViz fixed frame accordingly
  * writes urdf/ur10.urdf + a report of the kinematic chain

Run:  python scripts/sync_to_ros.py                (or: make sync)
      python scripts/sync_to_ros.py --cad-colors   # keep Onshape colors
"""

from __future__ import annotations

import math
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    EXPORT_DIR,
    PACKAGE_NAME,
    PROJECT_ROOT,
    ROS_PACKAGE,
    load_export_config,
)

# Output names follow export/config.json ("output_filename") so the repo
# works for any robot project without code edits (ur10 -> ur10.urdf, ...).
_OUT_NAME = load_export_config().get("output_filename", "robot")
URDF_DEST = ROS_PACKAGE / "urdf" / f"{_OUT_NAME}.urdf"
MESH_DEST = ROS_PACKAGE / "meshes"
RVIZ_CONFIG = ROS_PACKAGE / "rviz" / f"{_OUT_NAME}.rviz"

ENV_EXPORT_DIR = PROJECT_ROOT / "export_env"
ENV_URDF = ENV_EXPORT_DIR / "environment.urdf"
WHOLE_SETUP_DUMP = EXPORT_DIR / "inspect" / "whole_setup.json"

# --------------------------------------------------------------------------
# Visible color palette for the ROBOT parts.
# fnmatch wildcards, case-insensitive, FIRST match wins, matched against the
# part name (material name minus the "_material" suffix).
# The Onshape appearances of the UR10 parts are almost all grey/white, so
# RViz faithfully renders a "white" robot; this palette restores the classic
# Universal Robots look (white body + blue joint caps + dark hardware) so
# every element is clearly distinguishable. Environment parts are NOT in the
# palette - they keep their vivid Onshape colors.
# --------------------------------------------------------------------------
ROBOT_PALETTE: list[tuple[str, str]] = [
    ("31602*",              "0.18 0.18 0.20 1"),   # bearings / hardware
    ("size_3_joint_lid*",   "0.00 0.55 0.85 1"),   # wrist lid - UR blue accent
    ("size_4_joint*",       "0.00 0.42 0.68 1"),   # shoulder housing - UR blue
    ("size_3_joint*",       "0.28 0.33 0.40 1"),   # elbow housing - blue grey
    ("size_3_elbow*",       "0.28 0.33 0.40 1"),   # elbow housing - blue grey
    ("size_2_joint*",       "0.24 0.24 0.27 1"),   # wrist joints - dark grey
    ("base*",               "0.80 0.82 0.85 1"),   # base - light grey
    ("lower_arm",           "0.93 0.93 0.95 1"),   # body tube - white
    ("upper_arm",           "0.93 0.93 0.95 1"),   # body tube - white
    ("tool_flange",         "0.35 0.35 0.38 1"),   # tool flange - dark grey
]

# Cyrillic -> Latin transliteration for mesh file names (RViz/resource_retriever
# is happiest with pure-ASCII package:// URIs). Multi-character mappings are
# applied first, then the single-character remainder.
_CYR_MULTI = [
    ("Ж", "Zh"), ("ж", "zh"), ("Х", "Kh"), ("х", "kh"), ("Ц", "Ts"), ("ц", "ts"),
    ("Ч", "Ch"), ("ч", "ch"), ("Ш", "Sh"), ("ш", "sh"), ("Щ", "Sch"), ("щ", "sch"),
    ("Ё", "Yo"), ("ё", "yo"), ("Ю", "Yu"), ("ю", "yu"), ("Я", "Ya"), ("я", "ya"),
    ("Ы", "Yi"), ("ы", "yi"),
]
_CYR_SINGLE = str.maketrans(
    "АБВГДЕЗИЙКЛМНОПРСТУФЪЬ" "абвгдезийклмнопрстуфъь",
    "ABVGDEZIYKLMNOPRSTUF__" "abvgdeziyklmnoprstuf__",
)


def translit(text: str) -> str:
    for src, dst in _CYR_MULTI:
        text = text.replace(src, dst)
    return text.translate(_CYR_SINGLE)


def sanitize(name: str) -> str:
    """TF/URDF-safe name: no spaces, collapse whitespace."""
    return re.sub(r"\s+", "_", name.strip())


def _fix_mojibake(text: str) -> str:
    """Repair Cyrillic names mangled into the Latin-1 range.

    onshape-to-robot emits non-ASCII (Cyrillic) part names as Latin-1
    characters whose codepoints are exactly 0x350 BELOW the real Cyrillic
    letters (e.g. 'â' U+00E2 -> 'в' U+0432, 'ä' U+00E4 -> 'д' U+0434).
    Verified against the 'Whole setup' part names (втулка_резьбовая,
    диск_верхний, ...). Shift such characters back; ASCII is untouched."""
    return "".join(
        chr(ord(c) + 0x350) if 0x00C0 <= ord(c) <= 0x00FF else c
        for c in text
    )


def safe_mesh_name(filename: str) -> str:
    """ASCII-only, filesystem/URI-safe mesh file name (keeps the extension)."""
    stem, ext = os.path.splitext(filename)
    stem = translit(_fix_mojibake(stem))
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    stem = re.sub(r"_{2,}", "_", stem).strip("_")
    return f"{stem}{ext.lower()}"


# --------------------------------------------------------------------------
# environment helpers
# --------------------------------------------------------------------------
def _urn_name(name: str) -> str:
    """'Base <3>' -> 'base' (strip the occurrence suffix, case/space-insensitive)."""
    name = re.sub(r"\s*<\d+>\s*$", "", str(name))
    return re.sub(r"[\s_-]+", "", name).lower()


def load_mount_transform(
    robot_root: ET.Element, robot_root_link: str
) -> np.ndarray:
    """Return T (env -> robot root link) = inv(T_W_R).

    The exported environment link frame IS the Whole-setup origin (the
    exporter uses an identity world transform for root links), so mounting
    the env under the robot root link R needs the world pose of R.

    T_W_R is taken from the robot's ROOT-LINK PART occurrence inside
    "Whole setup" (e.g. 'UR10 <1>/Base <3>'), NOT from the sub-assembly
    occurrence 'UR10 <1>': occurrence transforms are CUMULATIVE in the
    assembly frame, and the mates place parts relative to the sub-assembly
    origin — so the sub-assembly origin is generally NOT the robot base
    pose (here they differ by 0.816 m: using 'UR10 <1>' detached the robot
    from the tube it is mated to).

        T_W_R = T_W_part @ inv(T_R_part)

    with
      * T_W_part = cumulative occurrence transform of the root-link part
        in export/inspect/whole_setup.json,
      * T_R_part = the root link's <visual> origin in the robot URDF
        (mesh frame = Onshape part frame; the URDF root-link frame is the
        robot tab's export origin).
    """
    if not WHOLE_SETUP_DUMP.is_file():
        sys.exit(
            f"[FAIL] {WHOLE_SETUP_DUMP} not found.\n"
            "       The environment export needs the 'Whole setup' dump to\n"
            "       compute the mount pose. Run:  make urdf-env"
        )
    import json

    data = json.loads(WHOLE_SETUP_DUMP.read_text(encoding="utf-8"))
    robot_instance = str(load_export_config().get("robot_instance", "")).strip()
    if not robot_instance:
        sys.exit(
            "[FAIL] 'robot_instance' missing in export/config.json.\n"
            "       Set it to the robot instance name in 'Whole setup'\n"
            "       (e.g. \"UR10\" for the instance 'UR10 <1>')."
        )

    # instance id -> name, at EVERY level (root assembly + sub-assemblies)
    names: dict[str, str] = {}

    def _collect(obj) -> None:
        if isinstance(obj, dict):
            for inst in obj.get("instances") or []:
                if inst.get("id"):
                    names[inst["id"]] = inst.get("name", "")
            for v in obj.values():
                _collect(v)
        elif isinstance(obj, list):
            for v in obj:
                _collect(v)

    _collect(data)
    root = data.get("rootAssembly", {})
    occurrences = root.get("occurrences", [])

    # 1) the robot's top-level instance in Whole setup
    robot_id = None
    for occ in occurrences:
        path = occ.get("path", [])
        if len(path) == 1 and str(names.get(path[0], "")).startswith(robot_instance):
            robot_id = path[0]
            break
    if robot_id is None:
        available = sorted(
            {str(names.get(o["path"][0], "")) for o in occurrences if len(o.get("path", [])) == 1}
        )
        sys.exit(
            f"[FAIL] No instance starting with {robot_instance!r} in the Whole\n"
            f"       setup dump. Top-level instances: {available}\n"
            "       Fix 'robot_instance' in export/config.json, then: make urdf-env"
        )

    # 2) the root-link part occurrence under it (e.g. 'UR10 <1>/Base <3>')
    want = _urn_name(robot_root_link)
    part_occ = None
    for occ in occurrences:
        path = occ.get("path", [])
        if len(path) == 2 and path[0] == robot_id and _urn_name(names.get(path[1], "")) == want:
            part_occ = occ
            break
    if part_occ is None:
        parts = sorted(
            names.get(o["path"][1], "") for o in occurrences
            if len(o.get("path", [])) == 2 and o["path"][0] == robot_id
        )
        sys.exit(
            f"[FAIL] No {robot_root_link!r} part occurrence under the robot\n"
            f"       instance {robot_instance!r} in the Whole setup dump.\n"
            f"       Robot parts found: {parts}\n"
            "       Check 'robot_instance' in export/config.json."
        )

    # 3) T_R_part: root link's <visual> origin in the robot URDF
    T_R_part = np.eye(4)
    link_el = next(
        (el for el in robot_root.iter("link") if el.get("name") == robot_root_link), None
    )
    origin = None
    if link_el is not None:
        vis = link_el.find("visual")
        if vis is not None:
            origin = vis.find("origin")
    if origin is not None:
        xyz = [float(v) for v in (origin.get("xyz") or "0 0 0").split()]
        rpy = [float(v) for v in (origin.get("rpy") or "0 0 0").split()]
        r, p, y = rpy
        cr, sr = math.cos(r), math.sin(r)
        cp, sp = math.cos(p), math.sin(p)
        cy, sy = math.cos(y), math.sin(y)
        T_R_part[:3, :3] = [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]
        T_R_part[:3, 3] = xyz

    # 4) world pose of the root-link frame -> mount
    T_W_part = np.array(part_occ["transform"], dtype=float).reshape(4, 4)
    T_W_R = T_W_part @ np.linalg.inv(T_R_part)
    print(
        f"  [mount] robot part {names.get(part_occ['path'][1])!r} in W: "
        f"xyz=({', '.join(f'{v:.6g}' for v in T_W_part[:3, 3])})"
    )
    return np.linalg.inv(T_W_R)


def matrix_to_xyz_rpy(T: np.ndarray) -> tuple[str, str]:
    """4x4 transform -> URDF origin xyz / rpy strings (R = Rz*Ry*Rx)."""
    xyz = " ".join(f"{0.0 if abs(v) < 1e-9 else v:.6g}" for v in T[:3, 3])
    r00, r01, r02 = T[0, :3]
    r10, r11, r12 = T[1, :3]
    r20, r21, r22 = T[2, :3]
    pitch = math.asin(max(-1.0, min(1.0, -r20)))
    if abs(math.cos(pitch)) < 1e-9:          # gimbal lock
        roll, yaw = 0.0, math.atan2(-r01, r11)
    else:
        roll = math.atan2(r21, r22)
        yaw = math.atan2(r10, r00)
    clean = lambda v: 0.0 if abs(v) < 1e-9 else v  # noqa: E731
    rpy = f"{clean(roll):.6g} {clean(pitch):.6g} {clean(yaw):.6g}"
    return xyz, rpy


def merge_environment(
    robot_root: ET.Element, robot_root_link: str
) -> tuple[dict[str, Path], int]:
    """Merge export_env/environment.urdf into the robot URDF.

    Returns ({package-relative mesh path: source file}, number of links added).
    """
    if not ENV_URDF.is_file():
        print("  [INFO] no export_env/environment.urdf — skipping environment merge")
        return {}, 0

    env_root = ET.parse(
        ENV_URDF, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    ).getroot()
    T_mount = load_mount_transform(robot_root, robot_root_link)
    xyz, rpy = matrix_to_xyz_rpy(T_mount)
    print(f"  environment mount: xyz=({xyz})  rpy=({rpy})  [from Whole setup]")

    env_links = list(env_root.iter("link"))
    mesh_sources: dict[str, Path] = {}
    used_safe: dict[str, str] = {}   # safe name -> original file name

    def rewrite_mesh(mesh: ET.Element) -> None:
        fn = mesh.get("filename", "")
        original = fn.rsplit("/", 1)[-1]
        safe = safe_mesh_name(original)
        # keep names unique if two Cyrillic names transliterate alike
        if safe in used_safe and used_safe[safe] != original:
            stem, ext = os.path.splitext(safe)
            n = 2
            while f"{stem}_{n}{ext}" in used_safe:
                n += 1
            safe = f"{stem}_{n}{ext}"
        used_safe[safe] = original
        rel = f"meshes/{safe}"
        mesh_sources[rel] = ENV_EXPORT_DIR / "meshes" / original
        mesh.set("filename", f"package://{PACKAGE_NAME}/{rel}")

    added = 0
    for i, link in enumerate(env_links):
        name = "environment" if i == 0 else f"environment_{i + 1}"
        link.set("name", name)
        for mesh in link.iter("mesh"):
            rewrite_mesh(mesh)
        robot_root.append(link)

        joint = ET.Element(
            "joint",
            {"name": "environment_mount" if i == 0 else f"environment_mount_{i + 1}",
             "type": "fixed"},
        )
        ET.SubElement(joint, "parent", {"link": robot_root_link})
        ET.SubElement(joint, "child", {"link": name})
        ET.SubElement(joint, "origin", {"xyz": xyz, "rpy": rpy})
        robot_root.append(joint)
        added += 1

    print(f"  merged {added} environment link(s), "
          f"{sum(len(list(l.iter('visual'))) for l in env_links)} visuals")
    return mesh_sources, added


def apply_palette(root: ET.Element) -> int:
    """Recolor the ROBOT visuals per ROBOT_PALETTE (env parts keep CAD colors)."""
    import fnmatch

    colored = 0
    for visual in root.iter("visual"):
        material = visual.find("material")
        if material is None:
            continue
        mname = material.get("name", "")
        part = mname[: -len("_material")] if mname.endswith("_material") else mname
        rgba = None
        for pattern, color in ROBOT_PALETTE:
            if fnmatch.fnmatch(part.lower(), pattern.lower()):
                rgba = color
                break
        if rgba is None:
            continue                       # environment parts: keep Onshape color
        color_el = material.find("color")
        if color_el is None:
            color_el = ET.SubElement(material, "color")
        color_el.set("rgba", rgba)
        colored += 1
    return colored


# --------------------------------------------------------------------------
def sync_urdf() -> int:
    config = load_export_config()
    out_name = config.get("output_filename", "robot")
    assets_dir = config.get("assets_directory", "assets")
    src_urdf = EXPORT_DIR / f"{out_name}.urdf"
    if not src_urdf.is_file():
        sys.exit(f"[FAIL] {src_urdf} not found — run: python scripts/run_export.py")

    # Parse while keeping <!-- comments --> (the exporter adds nice ones)
    tree = ET.parse(src_urdf, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    root = tree.getroot()

    # ---------------------------------------------------------- name sanitising
    renames: dict[str, str] = {}
    for tag in ("link", "joint", "transmission"):
        for el in root.iter(tag):
            old = el.get("name")
            if old:
                new = sanitize(old)
                if new != old:
                    renames[old] = new
                    el.set("name", new)

    def fix_ref(el: ET.Element, attr: str) -> None:
        val = el.get(attr)
        if val in renames:
            el.set(attr, renames[val])

    for el in root.iter():
        for attr in ("link", "joint", "reference"):
            fix_ref(el, attr)

    # ------------------------------------------------- articulable joint gate
    # Counted BEFORE the environment merge (which only adds fixed joints), so
    # a rigid 0-DOF export can never pass this gate.
    articulable = [j for j in root.iter("joint") if j.get("type") != "fixed"]

    # ------------------------------------------------------------- mesh rewrite
    ref_map: dict[str, str] = {}   # relative path in export -> relative path in package
    for mesh in root.iter("mesh"):
        fn = mesh.get("filename", "")
        if fn.startswith("package://"):
            rest = fn[len("package://"):]
            rel = rest.split("/", 1)[1] if "/" in rest else rest
        else:
            rel = fn[2:] if fn.startswith("./") else fn
        dirname, fname = os.path.split(rel)
        if not dirname:
            dirname = assets_dir
        new_fname = sanitize(fname)
        rel_new = f"{dirname}/{new_fname}"
        ref_map.setdefault(rel, rel_new)
        mesh.set("filename", f"package://{PACKAGE_NAME}/{rel_new}")

    # ------------------------------------------------------ environment merge
    # Runs AFTER the robot mesh rewrite: environment meshes are rewritten to
    # safe ASCII package:// names inside merge_environment() itself.
    children = {j.find("child").get("link") for j in root.iter("joint")
                if j.find("child") is not None}
    robot_root_link = next(
        (el.get("name") for el in root.iter("link") if el.get("name") not in children),
        "base",
    )
    env_mesh_sources, env_links_added = merge_environment(root, robot_root_link)

    # ------------------------------------------------------------- copy meshes
    # Geometry is independent of the joint state, so ALWAYS sync it — even a
    # failed (rigid) export leaves the meshes usable in the ROS package.
    # Destination must match the package:// URI exactly, i.e. be rooted at the
    # package dir (not MESH_DEST), otherwise "meshes/x.stl" refs end up nested
    # in meshes/meshes/.
    MESH_DEST.mkdir(parents=True, exist_ok=True)
    for old in MESH_DEST.glob("*"):
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
    copied = 0
    done_dst: set[str] = set()

    # 1) every STL the URDF actually references (path/sanitisation aware)
    for rel_src, rel_dst in ref_map.items():
        src = EXPORT_DIR / rel_src
        dst = ROS_PACKAGE / rel_dst
        if not src.is_file():
            # try sanitised source name as well
            d, f = os.path.split(rel_src)
            alt = EXPORT_DIR / d / sanitize(f) if d else EXPORT_DIR / sanitize(f)
            src = alt if alt.is_file() else src
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            done_dst.add(str(dst))
            copied += 1
        else:
            print(f"  [WARN] mesh not found in export: {rel_src}")

    # 2) environment meshes (already rewritten to safe ASCII names)
    for rel_dst, src in sorted(env_mesh_sources.items()):
        dst = ROS_PACKAGE / rel_dst
        if not src.is_file():
            print(f"  [WARN] environment mesh not found: {src}")
            continue
        if str(dst) in done_dst:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        done_dst.add(str(dst))
        copied += 1

    # 3) any other STL in export/meshes/ (a rigid/failed export only
    #    references the base links — the rest must come along anyway)
    for src in sorted((EXPORT_DIR / "meshes").rglob("*.stl")):
        rel = src.relative_to(EXPORT_DIR / "meshes")   # e.g. arm/elbow.stl
        dst = MESH_DEST / rel                          # -> .../meshes/arm/elbow.stl
        if str(dst) in done_dst:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    # 4) leftover environment STLs (not referenced by the URDF)
    for src in sorted((ENV_EXPORT_DIR / "meshes").glob("*.stl")):
        dst = MESH_DEST / safe_mesh_name(src.name)
        if str(dst) in done_dst:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    # ---------------------------------------------------------------- colors
    if "--cad-colors" in sys.argv:
        print("  colors: keeping raw Onshape appearances (--cad-colors)")
    else:
        n = apply_palette(root)
        print(f"  colors: robot palette applied to {n} visual(s) "
              f"(--cad-colors to keep Onshape appearances)")

    # ---------------------------------------------------------------- write URDF
    # Pre-flight gate: a rigid 0-joint URDF must never overwrite a good one
    # in ros2_ws/src (meshes are already synced above — harmless).
    if len(articulable) == 0:
        print("  [FAIL] 0 articulable joints in the exported URDF! "
              "The robot would be rigid.")
        print("         Your mates are missing the 'dof_' prefix (or are broken).")
        print("         Meshes were synced, but the package URDF was NOT touched.")
        print("         See docs/02_onshape_assembly_setup.md and run: make inspect")
        return 2

    URDF_DEST.parent.mkdir(parents=True, exist_ok=True)
    body = ET.tostring(root, encoding="unicode")
    URDF_DEST.write_text('<?xml version="1.0"?>\n' + body + "\n", encoding="utf-8")

    # ----------------------------------------------------------- chain analysis
    links = [el.get("name") for el in root.iter("link")]
    joints = list(root.iter("joint"))
    children = {j.find("child").get("link") for j in joints if j.find("child") is not None}
    roots = [l for l in links if l not in children]

    print("=" * 70)
    print(" KINEMATIC CHAIN")
    print("=" * 70)
    for j in joints:
        parent = j.find("parent")
        child = j.find("child")
        limit = j.find("limit")
        lim = ""
        if limit is not None:
            lim = (f"  limits[{limit.get('lower', '?')} .. {limit.get('upper', '?')}]"
                   f"  v<={limit.get('velocity', '?')}  effort<={limit.get('effort', '?')}")
        print(f"  {j.get('name')}  [{j.get('type')}]  "
              f"{parent.get('link') if parent is not None else '?'} -> "
              f"{child.get('link') if child is not None else '?'}{lim}")
    print("-" * 70)
    print(f"  links: {len(links)}   joints: {len(joints)}   meshes: {copied}")
    if env_links_added:
        print(f"  environment: {env_links_added} fixed link(s) merged "
              f"(table, stand, tube, glory machines)")
    if len(roots) != 1:
        print(f"  [WARN] expected exactly 1 root link, found {len(roots)}: {roots}")
        fixed_frame = roots[0] if roots else "base_link"
    else:
        fixed_frame = roots[0]
        print(f"  root link / RViz fixed frame: {fixed_frame}")

    # --------------------------------------------------------- patch RViz frame
    if RVIZ_CONFIG.is_file():
        text = RVIZ_CONFIG.read_text(encoding="utf-8")
        text, n = re.subn(r"(?m)^(\s*Fixed Frame:).*$", rf"\g<1> {fixed_frame}", text, count=1)
        if n:
            RVIZ_CONFIG.write_text(text, encoding="utf-8")
            print(f"  RViz fixed frame set to: {fixed_frame}")
    else:
        print(f"  [WARN] {RVIZ_CONFIG} missing — RViz will use its default frame")

    print("=" * 70)
    print("Synced into the ROS 2 package:")
    print(f"  {URDF_DEST.relative_to(ROS_PACKAGE.parents[2])}")
    print(f"  ros2_ws/src/{PACKAGE_NAME}/meshes/  ({copied} STL file(s))")
    print("\nNext steps:")
    print("  make build     # colcon build the description package")
    print("  make rviz      # RViz2 + joint sliders to control the UR10")
    return 0


if __name__ == "__main__":
    sys.exit(sync_urdf())
