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


def get_test_status_record(base_url: str, api_key: str, record_type: str, status: str) -> dict:
    """
    Call owl_get_test_status_record to find a real (non-fixture) testimonial or
    reference post with the given status, from the local pool of production-
    synced records (1,188+ Incomplete of each, as of 26/27 Aug 2026 — see
    docs/TESTING_SYSTEM.md). record_type is 'testimonials' or 'reference'.

    Returns {"success": True, "post_id": ..., "url": ...} for references, plus
    "job_id", "client_id", "j", "c" (pre-computed crc32 hashes matching
    single-testimonials.php's own ?j=&c= URL validation) for testimonials.
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action": "owl_get_test_status_record",
            "api_key": api_key,
            "type": record_type,
            "status": status,
        },
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    result = json.loads(resp.content.decode("utf-8-sig"))
    if not result.get("success"):
        raise RuntimeError(f"owl_get_test_status_record failed: {result.get('error', 'unknown')}")
    return result


def reset_status_field(base_url: str, api_key: str, post_id, field: str, value: str) -> dict:
    """
    Call owl_reset_status_field to set a testimonial/reference post's status
    field back to a known value — used to restore a real record consumed by a
    submission test (e.g. back to 'Incomplete') so the local pool doesn't get
    permanently depleted by repeated runs. field is 'testimonial_status' or
    'reference_status'.
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action": "owl_reset_status_field",
            "api_key": api_key,
            "post_id": post_id,
            "field": field,
            "value": value,
        },
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    result = json.loads(resp.content.decode("utf-8-sig"))
    if not result.get("success"):
        raise RuntimeError(f"owl_reset_status_field failed: {result.get('error', 'unknown')}")
    return result
