#!/usr/bin/env python3
"""
env_check.py — verify the whole chain before exporting:

  [1/3] .env file .......... keys present (not placeholders)?
  [2/3] API authentication .. signed request accepted by Onshape?
  [3/3] Document access ..... can these keys read the UR10 assembly?

Run:  python scripts/env_check.py     (or: make check)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from onshape_common import (  # noqa: E402
    describe_http_error,
    get_assembly_ids,
    get_credentials,
    make_client,
    signed_get,
    wmv_selector,
)


def ok(label: str, detail: str = "") -> None:
    print(f"  [OK]   {label:<22} {detail}")


def fail(label: str, detail: str) -> None:
    print(f"  [FAIL] {label:<22} {detail}")


def warn(label: str, detail: str) -> None:
    print(f"  [WARN] {label:<22} {detail}")


def main() -> int:
    print("Onshape API pre-flight check")
    print("=" * 64)

    # ---- [1/3] credentials from .env -------------------------------------
    try:
        api, _access, _secret = get_credentials()
    except SystemExit as exc:
        fail(".env file", str(exc))
        return 1
    ok(".env file", f"keys loaded ({api})")

    # ---- [2/3] authentication + [3/3] document access --------------------
    ids = get_assembly_ids()
    ok("assembly URL", f"document {ids['document_id']}")

    client = make_client()

    resp = signed_get(client, f"/api/documents/{ids['document_id']}")
    if resp.status_code != 200:
        fail("API authentication", describe_http_error(resp.status_code, api))
        return 2
    try:
        doc = resp.json()
    except ValueError:
        doc = {}
    ok("API authentication", "signed request accepted")

    doc_name = doc.get("name", "(unnamed)")
    ok("document access", f'"{doc_name}"')

    # ---- bonus: workspace / element sanity --------------------------------
    wmv, wmvid = wmv_selector(ids)
    resp = signed_get(
        client,
        f"/api/assemblies/d/{ids['document_id']}/{wmv}/{wmvid}/e/{ids['element_id']}",
        query={"includeMateFeatures": "true", "includeMateConnectors": "true"},
    )
    if resp.status_code == 200:
        ok("assembly element", "assembly reachable")
        print("=" * 64)
        print("All good. Next step:")
        print("    python scripts/inspect_assembly.py")
        return 0

    if resp.status_code in (400, 404):
        fail("assembly element", describe_http_error(resp.status_code, api))
        print("       Hint: the URL element id must be the ASSEMBLY tab.")
        return 2

    warn("assembly element", f"HTTP {resp.status_code} (will retry during export)")
    print("=" * 64)
    print("Credentials work. Next step:")
    print("    python scripts/inspect_assembly.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
