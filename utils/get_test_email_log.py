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


def get_test_email_log(base_url: str, api_key: str, post_id: str) -> list:
    """
    Call owl_get_test_email_log to read back the ot_test_email_log post meta
    written by ot_sg_mail()'s test-mode branch (services/sendgrid/system.php)
    — confirms an email was (or wasn't) attempted, and lets tests inspect its
    subject/custom_args, without ever sending a real email.

    Only works on posts flagged _ot_test_post=1. Returns a list of log entry
    dicts (empty list if no email has been logged against this post yet):
        [{"timestamp": ..., "to": ..., "subject": ..., "options": {...}}, ...]
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":  "owl_get_test_email_log",
            "api_key": api_key,
            "post_id": post_id,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_get_test_email_log failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data["log"]
