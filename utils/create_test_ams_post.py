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


def create_test_ams_post(base_url: str, api_key: str, author_id: int = 0, deadline_offset: int = 2) -> dict:
    """
    Call owl_create_test_ams_post to create a disposable 'post' with
    ams_v2_status='Author writing' and ams_v2_deadline set deadline_offset
    days from today — the exact state ot_ams_scheduled_author_writing_remind_*
    handlers (includes/event-mgmt.php) check for. Flagged _ot_test_post=1 for
    cleanup.

    author_id: leave as 0 (default) to let the endpoint pick any real
    administrator automatically — safer than guessing a hardcoded WP user ID,
    which is not reliable on a database synced down from production.

    Returns the parsed JSON response: {"success": True, "post_id": "...", "author_id": ...}
    """
    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={
            "action":          "owl_create_test_ams_post",
            "api_key":         api_key,
            "author_id":       author_id,
            "deadline_offset": deadline_offset,
        },
        headers=_auth_headers(base_url),
        # get_users(['role' => 'administrator']) — used when author_id falls back to 0 —
        # runs an unindexed LIKE query against wp_usermeta.wp_capabilities, which measured
        # ~39s against this site's real (synced-from-production) user table. Not worth
        # optimising for a test-only endpoint; just give it room to finish.
        timeout=90,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_create_test_ams_post failed: {data.get('error', 'unknown')}\nFull response: {data}")
    return data
