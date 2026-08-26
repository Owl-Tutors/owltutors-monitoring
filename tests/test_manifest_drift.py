import ast
import os

from utils.get_test_manifest import get_test_manifest

TESTS_DIR = os.path.dirname(__file__)

# This test's own name, deliberately excluded from both sides of the
# comparison below -- it's a meta-check of the manifest, not itself a
# site-behaviour test, so it isn't (and shouldn't be) listed in
# ot_get_test_manifest() in owl_system/includes/dashboard/dashboard-main.php.
_SELF = "test_manifest_matches_pytest_functions"


def _all_test_function_names() -> set:
    """Every top-level test_* function across tests/test_*.py, found by
    parsing each file's AST rather than importing it -- avoids needing every
    fixture/env var satisfied just to enumerate what exists."""
    names = set()
    for fname in os.listdir(TESTS_DIR):
        if not (fname.startswith("test_") and fname.endswith(".py")):
            continue
        path = os.path.join(TESTS_DIR, fname)
        # utf-8-sig: at least one test file in this suite carries a UTF-8 BOM
        # (test_tutor_dashboard.py) -- plain utf-8 makes ast.parse choke on it.
        with open(path, encoding="utf-8-sig") as f:
            tree = ast.parse(f.read(), filename=fname)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                names.add(node.name)
    names.discard(_SELF)
    return names


def test_manifest_matches_pytest_functions(base_url: str, api_key: str):
    """Manifest drift check (docs/TESTING_REBUILD_SPEC.md, Days 11-12): every
    dashboard-widget manifest entry (ot_get_test_manifest() in
    owl_system/includes/dashboard/dashboard-main.php) must map to a real
    pytest function, and every pytest test function must appear in the
    manifest. Previously a silent failure -- a rename on either side just
    stopped that row matching in the widget; this turns it into a visible
    red row here instead.
    """
    manifest = get_test_manifest(base_url, api_key)
    manifest_keys = set(manifest["tests"].keys())
    actual_keys = _all_test_function_names()

    missing_from_manifest = sorted(actual_keys - manifest_keys)
    missing_from_suite = sorted(manifest_keys - actual_keys)

    assert not missing_from_manifest, (
        f"Test function(s) exist but aren't tracked in ot_get_test_manifest(): {missing_from_manifest}"
    )
    assert not missing_from_suite, (
        f"Manifest entries have no matching pytest function (renamed or deleted?): {missing_from_suite}"
    )
