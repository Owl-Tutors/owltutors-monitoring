import os
import re
from playwright.sync_api import Page, expect

from utils.details import write_detail

TUTORS_URL  = "/tutors/"
CONTACT_URL = "/contact-us/"


def _add_tutors(page: Page, count: int) -> list:
    """Click `count` Add-to-Request buttons and return the sessionStorage ID list."""
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".add-to-cart", timeout=15000)
    for _ in range(count):
        page.locator(".add-to-cart").first.click()
    page.wait_for_load_state("networkidle")
    return page.evaluate(
        "JSON.parse(sessionStorage.getItem('ot_requested_tutor_ids') || '[]')"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Add to cart — basic mechanism
# ─────────────────────────────────────────────────────────────────────────────

def test_add_to_cart_updates_session_storage(page: Page, base_url: str):
    """
    Clicking a single Add-to-Request button on the tutor listings page writes
    the tutor's ID to sessionStorage['ot_requested_tutor_ids'] and shows the
    shortlist panel (#requested_tutor_output).
    Covers: '.add-to-cart updates sessionStorage and renders #requested_tutor_output'.
    """
    page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
    ids = _add_tutors(page, count=1)

    expect(page.locator("#requested_tutor_output")).to_be_visible()
    assert len(ids) == 1, f"Expected 1 ID in sessionStorage, got: {ids}"

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/rb_add_to_cart.png")
    write_detail("test_add_to_cart_updates_session_storage", {
        "message": f"Add-to-cart wrote tutor ID {ids[0]} to sessionStorage and showed shortlist panel",
        "tutor_ids": ids,
        "screenshot": "screenshots/rb_add_to_cart.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Badge increment
# ─────────────────────────────────────────────────────────────────────────────

def test_request_count_badge_increments(page: Page, base_url: str):
    """
    The shortlist count badge (#rb-count) increments correctly from 1 to 3 as
    tutors are added one by one via .add-to-cart.
    Covers: '#request_count_badge increments correctly as tutors are added'.
    """
    page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".add-to-cart", timeout=15000)

    for expected_count in range(1, 4):
        page.locator(".add-to-cart").first.click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("#rb-count")).to_have_text(str(expected_count), timeout=5000)

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/rb_badge_increment.png")
    write_detail("test_request_count_badge_increments", {
        "message": "Request count badge incremented correctly from 1 to 3",
        "screenshot": "screenshots/rb_badge_increment.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Remove tutor — URL updates
# ─────────────────────────────────────────────────────────────────────────────

def test_remove_tutor_updates_url(page: Page, base_url: str):
    """
    On the contact form, removing a tutor from the shortlist widget reloads the
    page with the remaining tutor ID only in the URL. Removing the last tutor
    reloads to plain /contact-us/.

    Flow:
      1. Add 2 tutors from /tutors/
      2. Navigate to contact form via the shortlist submit link
      3. Verify both IDs are in the URL
      4. Remove one tutor — page reloads with 1 ID in URL
      5. Remove the last tutor — page reloads to /contact-us/ (no params)

    Covers: 'Removing a tutor reloads with updated URL and remaining IDs only'.
    """
    page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
    ids = _add_tutors(page, count=2)
    assert len(ids) == 2, f"Expected 2 IDs in sessionStorage, got: {ids}"

    # Navigate to contact form via the submit link
    page.wait_for_function(
        "document.getElementById('selected_tutors_link').href.includes('requested_tutors')",
        timeout=10000,
    )
    page.locator("#selected_tutors_link").click()
    page.wait_for_load_state("domcontentloaded")

    # Both tutor IDs should appear in the URL
    assert "requested_tutors" in page.url, f"Expected requested_tutors in URL, got: {page.url}"
    assert "tutor_ids=" in page.url, f"Expected tutor_ids= in URL, got: {page.url}"

    # Remove first tutor from the shortlist widget
    page.locator("#requested_tutor_output .remove_tutor").first.click()
    # JS triggers window.location.href — wait for navigation
    page.wait_for_load_state("domcontentloaded", timeout=15000)

    # Only one ID should remain in the URL
    url_after_first_remove = page.url
    assert "requested_tutors" in url_after_first_remove, (
        f"Expected requested_tutors in URL after first remove, got: {url_after_first_remove}"
    )
    remaining_ids_in_url = re.search(r"tutor_ids=([^&]+)", url_after_first_remove)
    assert remaining_ids_in_url, f"No tutor_ids param after first remove: {url_after_first_remove}"
    # Should be a single ID, no pipe separator
    assert "|" not in remaining_ids_in_url.group(1), (
        f"Expected single ID in tutor_ids, got pipe-separated: {remaining_ids_in_url.group(1)}"
    )

    # Remove the last tutor — should reload to plain /contact-us/
    page.locator("#requested_tutor_output .remove_tutor").first.click()
    page.wait_for_load_state("domcontentloaded", timeout=15000)

    assert page.url.rstrip("/").endswith("/contact-us"), (
        f"Expected plain /contact-us/ after removing all tutors, got: {page.url}"
    )
    assert "requested_tutors" not in page.url, (
        f"requested_tutors still in URL after removing all: {page.url}"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/rb_remove_tutor.png")
    write_detail("test_remove_tutor_updates_url", {
        "message": "Remove tutor updated URL correctly; removing last tutor returned to plain /contact-us/",
        "screenshot": "screenshots/rb_remove_tutor.png",
    })
