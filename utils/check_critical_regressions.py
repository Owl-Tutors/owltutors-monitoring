"""
CI-only script (docs/TESTING_REBUILD_SPEC.md, Day 8 alerting): compares this
run's results.json against the previous run's (read from the `results`
branch before it's overwritten) and emails an alert for any business-critical
test that transitioned from not-failing to failing.

State-change only, by design: a critical test failing today that also failed
yesterday does NOT re-fire — "you get told" once, not every day for a known
issue. Non-critical tests never alert regardless of outcome.

Usage:
    python utils/check_critical_regressions.py <previous_results.json> <results.json> <pytest-report.json>

Reads TEST_BASE_URL, OWL_TEST_API_KEY, and (optionally) TEST_HTTP_USER/
TEST_HTTP_PASS from the environment — same credentials the rest of the suite
uses to reach the WP Engine-gated dev site. RUN_URL (optional) is included in
the alert email as a link to this Actions run's logs and video artifact.
"""
import base64
import json
import os
import re
import sys

import requests

_UA = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}


def _clean_url_and_auth_headers(raw_url: str) -> tuple:
    """Strip embedded user:pass@ from the URL (matches conftest.py's base_url
    fixture) and build the Basic Auth header needed for WP Engine's
    platform-level auth wall."""
    user = os.environ.get("TEST_HTTP_USER", "")
    pw = os.environ.get("TEST_HTTP_PASS", "")
    clean_url = re.sub(r"(https?://)[^:@]+:[^@]+@", r"\1", raw_url)

    if user and pw:
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return clean_url, {"Authorization": f"Basic {token}", **_UA}

    match = re.match(r"https?://([^:@]+):([^@]+)@", raw_url)
    if match:
        token = base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
        return clean_url, {"Authorization": f"Basic {token}", **_UA}

    return clean_url, dict(_UA)


def _load_results(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("results", {})


def _critical_test_names(report_path: str) -> set:
    with open(report_path) as f:
        report = json.load(f)
    names = set()
    for test in report.get("tests", []):
        if "critical" in test.get("keywords", []):
            names.add(test["nodeid"].split("::")[-1].split("[")[0])
    return names


def find_new_critical_failures(previous_path: str, current_path: str, report_path: str) -> list:
    previous = _load_results(previous_path)
    current = _load_results(current_path)
    critical = _critical_test_names(report_path)

    newly_failing = []
    for name in sorted(critical):
        curr_status = current.get(name, {}).get("status")
        prev_status = previous.get(name, {}).get("status")
        if curr_status == "fail" and prev_status != "fail":
            newly_failing.append(name)
    return newly_failing


def send_alert(base_url: str, api_key: str, failing_tests: list, run_url: str) -> dict:
    clean_url, headers = _clean_url_and_auth_headers(base_url)
    resp = requests.post(
        f"{clean_url}/wp-admin/admin-ajax.php",
        data={
            "action": "owl_send_test_alert",
            "api_key": api_key,
            "failing_tests": ",".join(failing_tests),
            "run_url": run_url,
        },
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8-sig"))
    if not data.get("success"):
        raise RuntimeError(f"owl_send_test_alert failed: {data.get('error', 'unknown')}")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python utils/check_critical_regressions.py <previous_results.json> <results.json> <pytest-report.json>")
        sys.exit(1)

    previous_path, current_path, report_path = sys.argv[1], sys.argv[2], sys.argv[3]
    base_url = os.environ["TEST_BASE_URL"]
    api_key = os.environ["OWL_TEST_API_KEY"]
    run_url = os.environ.get("RUN_URL", "")

    newly_failing = find_new_critical_failures(previous_path, current_path, report_path)
    if not newly_failing:
        print("[check_critical_regressions] no newly-failing critical tests")
        sys.exit(0)

    print(f"[check_critical_regressions] newly-failing critical tests: {newly_failing}")
    result = send_alert(base_url, api_key, newly_failing, run_url)
    print(f"[check_critical_regressions] alert sent: {result}")
