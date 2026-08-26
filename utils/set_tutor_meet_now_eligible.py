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


def set_tutor_meet_now_eligible(
    base_url: str,
    api_key: str,
    tutor_id: str,
    include_tutor_in_auto_swap: int = 1,
    auto_swap_active: int = 1,
    availability_updated_unix: int = None,
) -> dict:
    """
    Call owl_set_tutor_meet_now_eligible to set include_tutor_in_auto_swap,
    auto_swap_active, and the availability-last-updated timestamp on the
    given tutor (default: force both flags true and the timestamp to now).

    The timestamp matters because ot_tutor_availability_info_handler() only
    ever computes availability_outcome == '1b' (required for the meet-now
    button) when it's within the last 30 days — dev/staging tutor fixtures
    drift past that within weeks of nobody touching them.

    Returns {"success": True, "tutor_id": ..., "previous": {...}} — the
    previous values, so a caller that forced a real (non-fixture) tutor
    eligible can restore them afterward:

        result = set_tutor_meet_now_eligible(base_url, api_key, tutor_id)
        ...
        set_tutor_meet_now_eligible(base_url, api_key, tutor_id, **result["previous"])
    """
    data = {
        "action":                     "owl_set_tutor_meet_now_eligible",
        "api_key":                    api_key,
        "tutor_id":                   tutor_id,
        "include_tutor_in_auto_swap": include_tutor_in_auto_swap,
        "auto_swap_active":           auto_swap_active,
    }
    if availability_updated_unix is not None:
        data["availability_updated_unix"] = availability_updated_unix

    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data=data,
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_set_tutor_meet_now_eligible failed: {data.get('error', 'unknown')}")
    return data
