"""
CI-only script: run after the suite finishes with --video=on (every test's
video is recorded to test-results/<slug>/*.webm by pytest-playwright itself).
Deletes videos for tests that don't earn a place per
docs/TESTING_REBUILD_SPEC.md Day 8 — "Business-critical tests always (pass or
fail), plus every failure at any level. Non-critical passes keep nothing."

Using pytest-playwright's own --video=on (rather than the built-in
retain-on-failure) and pruning afterwards, instead of trying to vary the
--video option per test, avoids re-implementing its ArtifactsRecorder
save/delete logic per marker — recording is comparatively cheap; encoding a
video that then gets deleted here costs about what retain-on-failure already
costs per test today.

Usage: python utils/prune_videos.py <pytest-report.json> [output_dir]
"""
import json
import os
import sys

from slugify import slugify

DEFAULT_OUTPUT_DIR = "test-results"


def _truncate_file_name(name: str) -> str:
    """Mirror pytest_playwright.truncate_file_name() exactly, so the slug this
    script computes matches the directory pytest-playwright actually wrote to."""
    if len(name) < 256:
        return name
    import hashlib
    return f"{name[:100]}-{hashlib.sha256(name.encode()).hexdigest()[:7]}-{name[-100:]}"


def prune_videos(report_path: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> tuple:
    with open(report_path) as f:
        report = json.load(f)

    kept = pruned = 0
    for test in report.get("tests", []):
        nodeid = test["nodeid"]
        keywords = test.get("keywords", [])
        outcome = test.get("outcome")

        is_critical = "critical" in keywords
        failed = outcome not in ("passed", "skipped")
        keep = is_critical or failed

        test_dir = os.path.join(output_dir, _truncate_file_name(slugify(nodeid)))
        if not os.path.isdir(test_dir):
            continue

        for fname in os.listdir(test_dir):
            if not fname.endswith(".webm"):
                continue
            video_path = os.path.join(test_dir, fname)
            if keep:
                kept += 1
            else:
                os.remove(video_path)
                pruned += 1

        try:
            if not os.listdir(test_dir):
                os.rmdir(test_dir)
        except OSError:
            pass

    return kept, pruned


if __name__ == "__main__":
    report_path = sys.argv[1] if len(sys.argv) > 1 else "pytest-report.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR

    kept, pruned = prune_videos(report_path, output_dir)
    print(f"[prune_videos] kept {kept} video(s), pruned {pruned} video(s)")
