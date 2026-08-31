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


def create_test_job(
    base_url: str,
    api_key: str,
    stage: int,
    tutor_id: str,
    client_email: str = "",
    job_type: str = "",
    first_time_client: bool = False,
) -> dict:
    """
    Call the owl_create_test_job monitoring endpoint to create a ready-to-use
    test job at Stage 3, Stage 4, or Live (stage=5) on the dev site.

    The job is flagged with _ot_test_post=1 so the existing cleanup endpoint
    deletes it at the end of the test run.

    job_type: optional, 'EA job' or 'EB job' — sets mgmt_ea_or_eb_job, for
    timesheet-wizard tests that need to force the Stripe Connect check step
    ('EA job') vs. the default/EB path (leave blank).

    first_time_client: only meaningful when client_email is left blank (auto-
    create path). Sets using_default_pw=true and last_login=now() on the new
    client, matching a real client who was auto-logged-in once by the contact
    form but never set their own password — required so a later magic-link
    visit shows the 'Connect with tutor' button (and, when clicked while
    logged out, the Set PW modal) instead of silently auto-logging in for
    real (see single-jobs.php's magic-link handler / TESTING_CHANGELOG.md,
    28 Aug 2026).

    Returns the parsed JSON response dict, e.g.:
        {"success": true, "job_id": "12345", "job_url": "/jobs/12345/", ...}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":             "owl_create_test_job",
            "api_key":            api_key,
            "stage":              stage,
            "tutor_id":           tutor_id,
            "client_email":       client_email,
            "job_type":           job_type,
            "first_time_client":  "1" if first_time_client else "",
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig").lstrip('﻿'))
    if not data.get("success"):
        raise RuntimeError(
            f"owl_create_test_job failed (stage={stage}): "
            f"{data.get('error', 'unknown error')}\n"
            f"Full response: {data}"
        )
    return data
