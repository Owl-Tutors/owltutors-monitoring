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


def validate_phone_number(base_url: str, api_key: str, phone_number: str, country_code: str = "GB"):
    """
    Call owl_validate_phone_number to run a number through
    ot_libphonenumber_validate_number() (services/libphonenumber/system.php)
    without needing any job/client/tutor fixture — pure-logic assertion.

    Returns the classification: a bare digit string (valid mobile, or a valid
    landline in a different region than country_code), the literal string
    'Landline' (same-region landline), or None (unparseable).
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":       "owl_validate_phone_number",
            "api_key":      api_key,
            "phone_number": phone_number,
            "country_code": country_code,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_validate_phone_number failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data["result"]


def validate_job_phone_number(base_url: str, api_key: str, phone_number: str):
    """
    Call owl_validate_job_phone_number to run a number through
    ot_jobs_validate_phone_number() (owl_system/includes/job-mgmt.php) —
    the contact form's own telephone field validator — without needing any
    job/client/tutor fixture.

    Distinct from validate_phone_number() above, which exercises
    ot_libphonenumber_validate_number() (a different function, used for
    WATI/Twilio contact creation).

    Returns (is_valid, message): message is empty when is_valid is True,
    otherwise the rejection string shown to the user on the contact form.
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":       "owl_validate_job_phone_number",
            "api_key":      api_key,
            "phone_number": phone_number,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_validate_job_phone_number failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data["valid"], data["message"]
