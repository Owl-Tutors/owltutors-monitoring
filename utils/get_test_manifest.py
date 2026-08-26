import base64
import json
import os
import re

import requests


def _auth_headers(base_url: str) -> dict:
    user = os.environ.get("TEST_HTTP_USER", "")
    pw   = os.environ.get("TEST_HTTP_PASS", "")
    _UA = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}
    if user and pw:
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    raw = os.environ.get("TEST_BASE_URL", base_url)
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    return _UA


def get_test_manifest(base_url: str, api_key: str) -> dict:
    """
    Call owl_get_test_manifest to read the dashboard widget's test manifest
    (ot_get_test_manifest() in owl_system/includes/dashboard/dashboard-main.php),
    for the manifest-drift check (docs/TESTING_REBUILD_SPEC.md Days 11-12).

    Returns the parsed JSON response:
        {"success": True, "tests": {"<pytest function name>": {"area": ...,
         "label": ..., "critical": bool}, ...}}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={"action": "owl_get_test_manifest", "api_key": api_key},
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_get_test_manifest failed: {data.get('error', 'unknown')}")
    return data
