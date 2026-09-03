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


def create_test_duplicate_jobs(base_url: str, api_key: str, client_email: str) -> dict:
    """
    Call owl_create_test_duplicate_jobs to create two Stage-1 jobs for the
    same client with an overlapping subject (matching
    ot_system_check_for_duplicate_jobs()'s own logic), with
    mgmt_job_auto_lost and mgmt_chase_client set on the higher-ID
    ("duplicate") job — ready to fire ot_jobs_schedule_stage_1_duplicate_jobs
    against duplicate_job_id via trigger_scheduled_event().

    client_email must belong to an existing test user (_ot_test_user=1).

    Returns: {"success": True, "original_job_id": "...", "duplicate_job_id": "..."}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":       "owl_create_test_duplicate_jobs",
            "api_key":      api_key,
            "client_email": client_email,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_create_test_duplicate_jobs failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data
