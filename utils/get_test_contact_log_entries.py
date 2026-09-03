import base64
import json
import os
import re
import requests


_UA = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}


def _auth_headers(base_url: str) -> dict:
    raw = os.environ.get("TEST_BASE_URL", base_url)
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    return dict(_UA)


def get_test_contact_log_entries(base_url: str, api_key: str, entity_type: str, user_id: str) -> dict:
    """
    Call owl_get_test_contact_log_entries to read a client's or tutor's
    Contact Logging repeater rows directly, so a test can confirm a native
    user-profile ACF form save actually persisted a new row rather than
    trusting the rendered admin table, which can't tell a real save apart
    from a stale page.

    entity_type: 'client' or 'tutor'.

    Returns the parsed JSON response:
        {"success": True, "entries": [{"date": "...", "method": "...",
         "notes": "...", "author": 123}], "count": 1}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":      "owl_get_test_contact_log_entries",
            "api_key":     api_key,
            "entity_type": entity_type,
            "user_id":     user_id,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig").lstrip('﻿'))
    if not data.get("success"):
        raise RuntimeError(
            f"owl_get_test_contact_log_entries failed: {data.get('error', 'unknown error')}\n"
            f"Full response: {data}"
        )
    return data
