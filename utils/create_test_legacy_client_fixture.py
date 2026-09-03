import base64
import json
import os
import re
import requests


_UA = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}


def _auth_headers(base_url: str) -> dict:
    """Return Authorization header dict from credentials embedded in TEST_BASE_URL."""
    raw = os.environ.get("TEST_BASE_URL", base_url)
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    return dict(_UA)


def create_test_legacy_client_fixture(
    base_url: str,
    api_key: str,
    first_name: str = "",
    last_name: str = "",
) -> dict:
    """
    Call owl_create_test_legacy_client_fixture to build a disposable legacy
    `client` CPT post (owl_system docs/client-post-mgmt.md Part 1), plus a
    `students` post linked straight to it and a `jobs` post linking both --
    the shape docs/TESTING_SYSTEM.md's three legacy-CPT tests need.

    All three created posts are flagged _ot_test_post=1 for cleanup.

    Returns the parsed JSON response, e.g.:
        {"success": true, "client_id": "123", "student_id": "456",
         "job_id": "789", "first_name": "...", "last_name": "...",
         "client_email": "testbot.legacyclient.xxxx@owltutors.co.uk"}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":     "owl_create_test_legacy_client_fixture",
            "api_key":    api_key,
            "first_name": first_name,
            "last_name":  last_name,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig").lstrip('﻿'))
    if not data.get("success"):
        raise RuntimeError(
            f"owl_create_test_legacy_client_fixture failed: "
            f"{data.get('error', 'unknown error')}\nFull response: {data}"
        )
    return data
