import json
import os
import sys
from datetime import datetime, timezone


def write_results(report_path: str):
    with open(report_path) as f:
        report = json.load(f)

    results = {}
    for test in report.get("tests", []):
        name = test["nodeid"].split("::")[-1].split("[")[0]
        outcome = test["outcome"]  # "passed", "failed", "error", "skipped"
        call  = test.get("call", {})
        setup = test.get("setup", {})

        if outcome == "passed":
            status  = "pass"
            message = "OK"
        elif outcome == "skipped":
            # Skip reason lives in setup.longrepr for fixture-skipped tests
            # (pytest.skip() in a fixture fires before the call phase exists).
            raw = setup.get("longrepr") or call.get("longrepr") or "Skipped"
            # longrepr is sometimes a 3-tuple (file, line, reason)
            if isinstance(raw, (list, tuple)) and len(raw) >= 3:
                raw = raw[2]
            status  = "skip"
            message = str(raw)[:300]
        else:
            status  = "fail"
            message = str(call.get("longrepr", ""))[:300]

        results[name] = {
            "status":      status,
            "message":     message,
            "duration_ms": int(call.get("duration", 0) * 1000),
        }

    output = {
        "last_run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results":  results,
    }

    # Stamp with the deployed version/commit SHA, if pytest_sessionstart managed
    # to fetch one (docs/TESTING_REBUILD_SPEC.md Days 4-6). reporter.py runs as a
    # separate process after the pytest session finishes, so this crosses that
    # boundary via a file rather than in-memory state.
    if os.path.exists("deploy_info.json"):
        try:
            with open("deploy_info.json") as f:
                deploy_info = json.load(f)
            output["plugin_version"] = deploy_info.get("plugin_version")
            output["theme_version"]  = deploy_info.get("theme_version")
            output["commit_sha"]     = deploy_info.get("commit_sha")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Could not read deploy_info.json: {e}")

    with open("results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(results)} results to results.json")


if __name__ == "__main__":
    write_results(sys.argv[1])
