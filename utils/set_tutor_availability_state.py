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


def set_tutor_availability_state(
    base_url: str,
    api_key: str,
    tutor_id: str,
    dow: int = None,
    slot_index: int = None,
    slots: list = None,
    capacity: int = None,
    availability_updated_unix: int = None,
    date_free: str = None,
) -> dict:
    """
    Call owl_set_tutor_availability_state to deterministically control a real
    tutor's day/time-search-relevant state: which single (dow, slot_index) slot
    they have saved (or restore a full slot list via `slots`), their capacity,
    their availability-confirmation timestamp, and their date_free.

    Only pass dow+slot_index (a single slot) OR slots (a full [dow, slot_index]
    list, e.g. to restore an original set) — not both.

    Returns {"success": True, "tutor_id": ..., "previous": {...}} — "previous"
    contains capacity, availability_updated_unix, date_free, and slots (the
    tutor's full original [dow, slot_index] list), so a caller can restore
    everything exactly afterward:

        result = set_tutor_availability_state(base_url, api_key, tutor_id,
                                               dow=0, slot_index=10, capacity=5,
                                               availability_updated_unix=int(time.time()))
        ...
        set_tutor_availability_state(base_url, api_key, tutor_id,
                                      slots=result["previous"]["slots"],
                                      capacity=result["previous"]["capacity"],
                                      availability_updated_unix=result["previous"]["availability_updated_unix"],
                                      date_free=result["previous"]["date_free"])
    """
    data = {
        "action":   "owl_set_tutor_availability_state",
        "api_key":  api_key,
        "tutor_id": tutor_id,
    }
    if dow is not None and slot_index is not None:
        data["dow"] = dow
        data["slot_index"] = slot_index
    elif slots is not None:
        data["slots_json"] = json.dumps(slots)

    if capacity is not None:
        data["capacity"] = capacity
    if availability_updated_unix is not None:
        data["availability_updated_unix"] = availability_updated_unix
    if date_free is not None:
        data["date_free"] = date_free

    resp = requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data=data,
        headers=_auth_headers(base_url),
        timeout=15,
    )
    resp.raise_for_status()
    result = json.loads(resp.content.decode("utf-8-sig"))
    if not result.get("success"):
        raise RuntimeError(f"owl_set_tutor_availability_state failed: {result.get('error', 'unknown')}")
    return result
