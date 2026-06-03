import base64
import json
import os
import re
import requests


def _auth_headers(base_url: str) -> dict:
    """Return Authorization header dict from credentials embedded in TEST_BASE_URL."""
    raw = os.environ.get("TEST_BASE_URL", base_url)
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return {}


def create_test_job(
    base_url: str,
    api_key: str,
    stage: int,
    tutor_id: str,
    client_email: str = "",
) -> dict:
    """
    Call the owl_create_test_job monitoring endpoint to create a ready-to-use
    test job at Stage 3 or Stage 4 on the dev site.

    The job is flagged with _ot_test_post=1 so the existing cleanup endpoint
    deletes it at the end of the test run.

    Returns the parsed JSON response dict, e.g.:
        {"success": true, "job_id": "12345", "job_url": "/jobs/12345/", ...}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":       "owl_create_test_job",
            "api_key":      api_key,
            "stage":        stage,
            "tutor_id":     tutor_id,
            "client_email": client_email,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(
            f"owl_create_test_job failed (stage={stage}): "
            f"{data.get('error', 'unknown error')}\n"
            f"Full response: {data}"
        )
    return data
