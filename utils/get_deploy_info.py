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


def get_deploy_info(base_url: str, api_key: str) -> dict:
    """
    Call owl_get_deploy_info to read the plugin/theme version and (best-effort)
    git commit SHA of the site currently under test, so a run's results can be
    stamped with "which deploy caused this" (docs/TESTING_REBUILD_SPEC.md
    Days 4-6).

    Returns the parsed JSON response:
        {"success": True, "plugin_version": "10.2.26", "theme_version": "10.2.26",
         "commit_sha": "abc123def456" | None}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={"action": "owl_get_deploy_info", "api_key": api_key},
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_get_deploy_info failed: {data.get('error', 'unknown')}")
    return data
