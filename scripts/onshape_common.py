"""
onshape_common.py — shared helpers for the Onshape -> URDF -> ROS 2 pipeline.

Responsibilities:
  * locate the project root and load the .env API keys
  * parse the Onshape assembly URL from export/config.json
  * build an Onshape API client that authenticates EXACTLY like the
    onshape-to-robot exporter does (HMAC-signed requests, not plain Basic auth)

All pipeline scripts import from this module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Project layout
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = PROJECT_ROOT / "export"
CONFIG_FILE = EXPORT_DIR / "config.json"
ROS_PACKAGE = PROJECT_ROOT / "ros2_ws" / "src" / "ur10_robot_description"
PACKAGE_NAME = "ur10_robot_description"

# Values that mean "the user did not fill in the key yet"
_PLACEHOLDER_KEYS = {
    "",
    "PASTE_YOUR_ACCESS_KEY_HERE",
    "PASTE_YOUR_SECRET_KEY_HERE",
    "your_access_key",
    "your_secret_key",
}


# --------------------------------------------------------------------------
# .env / credentials
# --------------------------------------------------------------------------
def load_env() -> None:
    """Load the project .env without overriding variables already in the shell."""
    load_dotenv(PROJECT_ROOT / ".env")


def get_credentials() -> tuple[str, str, str]:
    """Return (api_url, access_key, secret_key); exit with help if unset."""
    load_env()
    api = os.getenv("ONSHAPE_API", "https://cad.onshape.com").rstrip("/")
    access = (os.getenv("ONSHAPE_ACCESS_KEY") or "").strip()
    secret = (os.getenv("ONSHAPE_SECRET_KEY") or "").strip()
    if access in _PLACEHOLDER_KEYS or secret in _PLACEHOLDER_KEYS:
        sys.exit(
            "[FAIL] Onshape API keys are not set yet.\n"
            "       1. Create keys : https://dev-portal.onshape.com/keys\n"
            f"       2. Fill them in: {PROJECT_ROOT / '.env'}\n"
            "       3. Re-run this command.\n"
            "       (see docs/01_onshape_api_keys.md)"
        )
    return api, access, secret


# --------------------------------------------------------------------------
# export/config.json
# --------------------------------------------------------------------------
def load_export_config() -> dict:
    """Parse export/config.json (JSON allowing // comments)."""
    if not CONFIG_FILE.is_file():
        sys.exit(f"[FAIL] Missing export config: {CONFIG_FILE}")
    import commentjson  # ships with onshape-to-robot

    return commentjson.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def get_assembly_ids() -> dict:
    """Extract document/workspace/version/element ids from the config URL."""
    url = str(load_export_config().get("url", ""))
    parts = [p for p in url.split("/") if p]
    ids = {"document_id": None, "workspace_id": None, "version_id": None, "element_id": None}
    try:
        i = parts.index("documents")
        ids["document_id"] = parts[i + 1]
        if parts[i + 2] in ("w", "v"):
            ids[{"w": "workspace_id", "v": "version_id"}[parts[i + 2]]] = parts[i + 3]
        ids["element_id"] = parts[parts.index("e") + 1]
    except (ValueError, IndexError):
        sys.exit(f"[FAIL] Cannot parse the Onshape URL in export/config.json:\n       {url}")
    if not ids["document_id"] or not ids["element_id"]:
        sys.exit(f"[FAIL] Onshape URL lacks a document or element id:\n       {url}")
    return ids


def wmv_selector(ids: dict) -> tuple[str, str]:
    """Return (wmv, wmv_id): ('w', workspace) or ('v', version)."""
    if ids.get("version_id"):
        return "v", ids["version_id"]
    return "w", ids["workspace_id"]


# --------------------------------------------------------------------------
# Onshape client (same signing mechanism as onshape-to-robot)
# --------------------------------------------------------------------------
def make_client():
    """Authenticated Onshape client reused from onshape-to-robot."""
    get_credentials()  # validates keys and loads .env first
    from onshape_to_robot.onshape_api.client import Client

    return Client(logging=False, creds=str(CONFIG_FILE))


def signed_get(client, path: str, query: dict | None = None) -> requests.Response:
    """Signed GET returning the raw Response (so callers can read status codes)."""
    try:
        return client._api.request("get", path, query=query or {})
    except requests.HTTPError as exc:  # in case the client raises on 4xx/5xx
        if exc.response is not None:
            return exc.response
        raise


def describe_http_error(status: int, api: str) -> str:
    """Human-readable explanation for common Onshape HTTP errors."""
    if status == 401:
        return "Authentication failed (401) — access/secret key pair is wrong."
    if status == 403:
        return (
            "No permission (403) — keys are valid but cannot reach this document.\n"
            "       Check that the keys belong to an account that has access to the\n"
            "       document (same account, or the document is shared/public)."
        )
    if status == 404:
        return "Not found (404) — the document/workspace/element id in the URL is wrong."
    return f"Unexpected HTTP status {status}."
