import os
from playwright.sync_api import Page, expect
from utils.details import write_detail

CONTACT_URL = "/contact-us/"
TUTORS_URL  = "/tutors/"


def test_contact_form_renders(page: Page, base_url: str):
    """Contact form page loads and the ACF form is visible."""
    page.goto(f"{base_url}{CONTACT_URL}")
    expect(page.locator("#tutor_request_form")).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/contact_form_renders.png")
    write_detail("test_contact_form_renders", {
        "message": "Contact form page loaded with ACF form visible",
        "screenshot": "screenshots/contact_form_renders.png",
    })


def test_contact_form_has_submit(page: Page, base_url: str):
    """Submit button is present and enabled."""
    page.goto(f"{base_url}{CONTACT_URL}")
    expect(page.locator("#contact_form_submit")).to_be_visible()
    expect(page.locator("#contact_form_submit")).to_be_enabled()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/contact_form_submit.png")
    write_detail("test_contact_form_has_submit", {
        "message": "Contact form submit button present and enabled",
        "screenshot": "screenshots/contact_form_submit.png",
    })


def test_contact_form_validation(page: Page, base_url: str):
    """
    Clicking submit without filling required fields shows ACF validation errors
    and does not navigate away from the contact form page.
    """
    page.goto(f"{base_url}{CONTACT_URL}")
    expect(page.locator("#tutor_request_form")).to_be_visible()

    # Select a form type so tuition fields become visible (and required)
    page.locator("select[name='acf[field_64997c72bef9f]']").select_option(
        label="A tutor to provide tuition services"
    )
    # Wait for subject checkboxes to load via AJAX
    page.wait_for_selector(
        "div[data-name='subject_list'] input[type='checkbox']",
        timeout=10000,
    )

    # Click submit without filling any required fields
    page.locator("#contact_form_submit").click()

    # ACF frontend validation should block submission and show error messages
    expect(page.locator(".acf-error-message").first).to_be_visible(timeout=10000)

    # Must still be on the contact form — no redirect to /jobs/
    assert "/contact-us/" in page.url
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/contact_form_validation.png")
    write_detail("test_contact_form_validation", {
        "message": "Contact form validation blocked empty submit and showed errors",
        "screenshot": "screenshots/contact_form_validation.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Jobs board checkbox visibility
# ─────────────────────────────────────────────────────────────────────────────

def test_jobs_board_checkbox_hidden_on_plain_form(page: Page, base_url: str):
    """
    On the plain contact form (/contact-us/ with no URL params), the jobs board
    checkbox wrapper (div#show_on_jobs_board) is hidden — it only appears for
    requested_tutors submissions or admin/owl users.
    Covers: 'Jobs board checkbox visibility logic (sessionStorage / admin)'.
    """
    page.goto(f"{base_url}{CONTACT_URL}", wait_until="domcontentloaded")
    page.wait_for_selector("#tutor_request_form", timeout=15000)

    jobs_board_div = page.locator("div#show_on_jobs_board")
    # The div must exist in the DOM but be hidden for a logged-out visitor on the plain form
    expect(jobs_board_div).to_be_hidden()

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/jobs_board_hidden.png")
    write_detail("test_jobs_board_checkbox_hidden_on_plain_form", {
        "message": "Jobs board checkbox hidden on plain /contact-us/ for logged-out visitor",
        "screenshot": "screenshots/jobs_board_hidden.png",
    })


def test_jobs_board_checkbox_visible_on_requested_tutors(page: Page, base_url: str):
    """
    When the contact form is loaded with job_type=requested_tutors in the URL,
    the jobs board checkbox wrapper (div#show_on_jobs_board) is visible —
    clients can choose whether their shortlisted-tutor job appears on the board.

    Uses a real tutor ID fetched dynamically from the listings page so no
    TEST_TUTOR_IDS env var is required.
    Covers: 'Jobs board checkbox visibility logic (sessionStorage / admin)'.
    """
    # Get at least one real tutor ID from the listings page
    page.goto(f"{base_url}{TUTORS_URL}")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".add-to-cart", timeout=15000)
    page.locator(".add-to-cart").first.click()
    page.wait_for_load_state("networkidle")
    ids = page.evaluate(
        "JSON.parse(sessionStorage.getItem('ot_requested_tutor_ids') || '[]')"
    )
    assert ids, "Could not get a tutor ID from the listings page"
    tutor_id = ids[0]

    page.goto(
        f"{base_url}{CONTACT_URL}?job_type=requested_tutors&tutor_ids={tutor_id}"
    )
    expect(page.locator("#tutor_request_form")).to_be_visible()
    page.wait_for_load_state("networkidle")

    jobs_board_div = page.locator("div#show_on_jobs_board")
    expect(jobs_board_div).to_be_visible()

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/jobs_board_visible.png")
    write_detail("test_jobs_board_checkbox_visible_on_requested_tutors", {
        "message": "Jobs board checkbox visible on requested_tutors contact form",
        "screenshot": "screenshots/jobs_board_visible.png",
    })
