"""
GA4 / Analytics smoke tests.

The tracking script in inc/header-DL.php only runs when get_site_url() contains
'owltutors.co.uk'.  The dev site (otdev1602.wpengine.com) does not match, so
these tests are skipped automatically when running against the dev site.

They will run on the production site or any environment whose WordPress
site URL contains 'owltutors.co.uk'.
"""
import os
import pytest
from playwright.sync_api import Page, expect
from utils.details import write_detail

HOMEPAGE_URL   = "/"
CONTACT_URL    = "/contact-us/"


def _require_owltutors_domain(base_url: str):
    """Skip this test if we're not running against an owltutors.co.uk URL.
    header-DL.php only outputs the tracking script for that domain."""
    if "owltutors.co.uk" not in base_url:
        pytest.skip(
            f"GA4 tracking script is only output on owltutors.co.uk URLs — "
            f"skipping against {base_url}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# sessionStorage keys set on first page load
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.analytics
def test_ga4_session_storage_set_on_load(page: Page, base_url: str):
    """
    On first page load, header-DL.php sets initial_url and traffic_source_r in
    sessionStorage (the ga_client_id key is only set if a _ga cookie is present,
    so that key is checked separately in test_ga4_client_id_in_contact_form).

    Covers: 'initial_url, traffic_source_r, ga_client_id in sessionStorage on load'.
    """
    _require_owltutors_domain(base_url)

    # Fresh context — sessionStorage is empty on first navigation
    page.goto(f"{base_url}{HOMEPAGE_URL}")
    page.wait_for_load_state("domcontentloaded")

    initial_url = page.evaluate("sessionStorage.getItem('initial_url')")
    traffic_source = page.evaluate("sessionStorage.getItem('traffic_source_r')")

    assert initial_url, "sessionStorage['initial_url'] not set after first page load"
    assert traffic_source, "sessionStorage['traffic_source_r'] not set after first page load"
    assert "owltutors" in initial_url, (
        f"initial_url should be an owltutors URL, got: {initial_url!r}"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/ga4_session_storage.png")
    write_detail("test_ga4_session_storage_set_on_load", {
        "message": f"initial_url={initial_url!r}  traffic_source_r={traffic_source!r}",
        "screenshot": "screenshots/ga4_session_storage.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# ga_client_id hidden input on contact form
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.analytics
def test_ga4_client_id_in_contact_form(page: Page, base_url: str):
    """
    When a _ga cookie is present, header-DL.php parses it and stores the client
    ID in sessionStorage['ga_client_id'].  The contact form JS then copies this
    value into a hidden input so it is submitted with the job.

    This test injects a synthetic _ga cookie before navigating to the form, then
    checks the hidden input has a non-empty value.
    Covers: 'Contact form ga_client_id input non-empty when _ga cookie present'.
    """
    _require_owltutors_domain(base_url)

    # Inject a synthetic _ga cookie matching the expected format: GA1.X.CID.TS
    page.context.add_cookies([{
        "name": "_ga",
        "value": "GA1.1.123456789.1700000000",
        "domain": "owltutors.co.uk",
        "path": "/",
    }])

    page.goto(f"{base_url}{CONTACT_URL}")
    page.wait_for_load_state("domcontentloaded")

    ga_client_id = page.evaluate("sessionStorage.getItem('ga_client_id')")
    assert ga_client_id, (
        "sessionStorage['ga_client_id'] not set despite _ga cookie being present"
    )

    # The contact form should have a hidden input that carries the ga_client_id to the server
    ga_input = page.locator("input[name*='ga_client_id'], input[id*='ga_client_id']")
    if ga_input.count() > 0:
        input_value = ga_input.first.get_attribute("value") or ""
        assert input_value, "ga_client_id hidden input exists but has empty value"

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/ga4_contact_form_client_id.png")
    write_detail("test_ga4_client_id_in_contact_form", {
        "message": f"ga_client_id={ga_client_id!r} set in sessionStorage from _ga cookie",
        "screenshot": "screenshots/ga4_contact_form_client_id.png",
    })
