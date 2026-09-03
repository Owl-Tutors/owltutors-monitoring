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


def schedule_test_event(base_url: str, api_key: str, hook: str, post_id: str, seconds_ahead: int = 3600) -> dict:
    """
    Call owl_schedule_test_event to schedule (not fire) one of the
    event-mgmt.php handlers via wp_schedule_single_event(), so a test job has
    a real pending event for the 'Job scheduled events' admin metabox
    (job_scheduled_events_metabox_content(), docs/metaboxes.md) to display.

    Unlike trigger_scheduled_event(), this does not run the handler — it only
    queues it, matching what the real job-creation flow does.
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":        "owl_schedule_test_event",
            "api_key":       api_key,
            "hook":          hook,
            "post_id":       post_id,
            "seconds_ahead": seconds_ahead,
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_schedule_test_event failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data
