import base64
import json
import os
import re
import requests


def _auth_headers(base_url: str) -> dict:
    # Prefer explicit TEST_HTTP_USER/TEST_HTTP_PASS secrets — avoids regex
    # breakage when the password contains special characters such as '@'.
    user = os.environ.get("TEST_HTTP_USER", "")
    pw   = os.environ.get("TEST_HTTP_PASS", "")
    _UA = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}
    if user and pw:
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    # Fallback: parse credentials embedded in TEST_BASE_URL
    raw = os.environ.get("TEST_BASE_URL", base_url)
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return {"Authorization": f"Basic {token}", **_UA}
    return _UA


def advance_test_job(
    base_url: str,
    api_key: str,
    job_id: str,
    tutor_id: str,
) -> dict:
    """
    Call owl_advance_test_job to mark the tutor as forwarded to client and
    advance the job to 'Stage 3 - Tutors to review'.

    The job must have _ot_test_post=1 and the tutor must have already applied
    via the front-end form before this is called.

    Returns the parsed JSON response.
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":   "owl_advance_test_job",
            "api_key":  api_key,
            "job_id":   job_id,
            "tutor_id": tutor_id,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(
            f"owl_advance_test_job failed: {data.get('error', 'unknown')}\n"
            f"Full response: {data}"
        )
    return data
