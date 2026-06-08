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

    with open("results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(results)} results to results.json")


if __name__ == "__main__":
    write_results(sys.argv[1])
