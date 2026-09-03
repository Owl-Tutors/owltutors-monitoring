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


def trigger_scheduled_event(
    base_url: str, api_key: str, hook: str, post_id: str, simulate_production: bool = False
) -> dict:
    """
    Call owl_trigger_scheduled_event to fire one of the wp_schedule_single_event()
    handlers in includes/event-mgmt.php immediately, instead of waiting for the
    real scheduled timestamp. Only works against posts flagged _ot_test_post=1,
    and only for hooks in the plugin-side allowlist (see rest-endpoint.php).

    simulate_production: every handler calls ot_jobs_dev_site_event_email_blocker()
    first, which returns true (block) unconditionally on this environment —
    checked *before* the post-status/stage logic a test usually cares about.
    Pass True to fake a production-looking get_site_url() for the duration of
    this one call, so the real business logic underneath the blocker is
    actually observable. Discovered necessary on the first real run of the
    Scheduled Events tests: without this, every one of them "passed" for the
    wrong reason (no email is ever possible on this environment regardless of
    post state), which would have masked a real regression just as easily as
    it hid a real bug.

    Returns the parsed JSON response: {"success": True, "hook": ..., "post_id": ...}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":              "owl_trigger_scheduled_event",
            "api_key":             api_key,
            "hook":                hook,
            "post_id":             post_id,
            "simulate_production": "1" if simulate_production else "",
        },
        headers=_auth_headers(base_url),
        timeout=30,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_trigger_scheduled_event failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data
