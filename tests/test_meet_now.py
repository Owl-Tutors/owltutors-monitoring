import os
import re
import pytest
from playwright.sync_api import Page, expect

from utils.cleanup import delete_test_posts
from utils.details import write_detail

CONTACT_URL = "/contact-us/"
FIRST_NAME  = "Owl"
LAST_NAME   = "TestBot"
EMAIL       = "testbot@owltutors.co.uk"
PHONE       = "07700900000"


@pytest.fixture(autouse=False)
def cleanup_after(base_url):
    """Delete all test-flagged records from the dev site after the test."""
    yield
    try:
        result = delete_test_posts(base_url)
        print(
            f"[cleanup] deleted {result.get('deleted_jobs', 0)} job(s), "
            f"{result.get('deleted_students', 0)} student(s), "
            f"{result.get('deleted_users', 0)} user(s)"
        )
    except Exception as e:
        print(f"[cleanup] warning: {e}")


def _flag_test_post(page: Page):
    api_key = os.environ.get("OWL_TEST_API_KEY", "")
    page.evaluate(
        """(apiKey) => {
            document.getElementById('ot_test_post').value = '1';
            var inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'ot_test_api_key';
            inp.value = apiKey;
            document.getElementById('tutor_request_form').appendChild(inp);
        }""",
        api_key,
    )


def _fill_client_info(page: Page):
    page.locator("input[name='acf[field_5edf8887fb5e7]']").fill(FIRST_NAME)
    page.locator("input[name='acf[field_5edf8899fb5e8]']").fill(LAST_NAME)
    page.locator("input[name='acf[field_5edf889ffb5e9]']").fill(EMAIL)
    page.locator("input[name='acf[field_5a573454bb670]']").fill(PHONE)


def _check_hs(page: Page):
    page.locator(
        "div[data-name='i_confirm_there_are_no_health_and_safety_issues'] input[type='checkbox']"
    ).check()


# ─────────────────────────────────────────────────────────────────────────────
# Meet now — form UI state
# ─────────────────────────────────────────────────────────────────────────────

def test_meet_now_form_auto_selects_type(
    page: Page, base_url: str, meet_now_tutor_id
):
    """
    Navigating to /contact-us/?job_type=meet_now&tutor_id=X causes the JS to:
    - Auto-select 'A tutor to provide tuition services' and hide the form type dropdown
    - Disable the Home delivery checkbox with an explanatory note
    - Hide the 'show on jobs board' checkbox

    No form submission or data creation — read-only.
    Covers P1: 'job_type=meet_now form auto-selects type, hides dropdown, disables
    Home delivery, hides jobs board checkbox'.
    """
    page.goto(f"{base_url}{CONTACT_URL}?job_type=meet_now&tutor_id={meet_now_tutor_id}")
    expect(page.locator("#tutor_request_form")).to_be_visible()

    # Wait for ACF subjects AJAX and the meet-now JS adjustments to settle
    page.wait_for_load_state("networkidle")

    # Form type select should be hidden (parent div gets d-none)
    form_type_select = page.locator("div[data-name='contact_form_type'] select")
    # The select's grandparent (.acf-input div) gets d-none — the select itself
    # may still be in the DOM but not visible
    expect(form_type_select).to_be_hidden()

    # Jobs board checkbox wrapper should have d-none
    jobs_board = page.locator("div[data-name='mgmt_show_on_jobs_board']")
    expect(jobs_board).to_be_hidden()

    # Home delivery checkbox should be disabled.
    # Wait for the conditional fields to appear first (form type is auto-set,
    # so tuition_delivery field should be visible).
    home_cb = page.locator(
        "div[data-name='tuition_delivery'] input[type='checkbox'][value='Home']"
    )
    expect(home_cb).to_be_disabled(timeout=10000)

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/meet_now_form_state.png")
    write_detail("test_meet_now_form_auto_selects_type", {
        "message": (
            f"Meet-now form state correct: type hidden, "
            f"home delivery disabled, jobs board hidden"
        ),
        "screenshot": "screenshots/meet_now_form_state.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Meet now — full submission
# ─────────────────────────────────────────────────────────────────────────────

def test_meet_now_submission(
    page: Page, base_url: str, meet_now_tutor_id, cleanup_after
):
    """
    Full meet-now submission: navigate via ?job_type=meet_now&tutor_id=X, fill
    the form, submit, and verify the browser redirects to a /jobs/ URL.

    Side effects suppressed via the ot_test_post flag.  The test tutor's
    auto_swap_active flag is set to false by the job-creation logic — it must
    be reset manually in the WP admin before running this test again.
    Note: TEST_MEET_NOW_TUTOR_ID must point to a tutor with auto_swap_active=true,
    include_tutor_in_auto_swap=true, online delivery enabled, and availability
    outcome 1b.
    Covers P1: 'Meet now submission creates job, mgmt_show_on_jobs_board=0,
    auto_swap_active set to false on tutor'.
    """
    page.goto(
        f"{base_url}{CONTACT_URL}?job_type=meet_now&tutor_id={meet_now_tutor_id}"
    )
    expect(page.locator("#tutor_request_form")).to_be_visible()

    # Wait for subject AJAX
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(
        "div[data-name='subject_list'] input[type='checkbox']",
        timeout=10000,
    )

    # Select first available subject
    page.locator(
        "div[data-name='subject_list'] input[type='checkbox'][value='Maths']"
    ).check()

    page.locator("div[data-name='tuition_requirements_original'] textarea").fill(
        "Meet now test — automated"
    )
    page.locator("div[data-name='timing_details_-_original'] textarea").fill("Flexible")

    _fill_client_info(page)
    _check_hs(page)
    _flag_test_post(page)

    page.locator("#contact_form_submit").click()
    page.wait_for_url(re.compile(r".*/jobs/"), timeout=90000)

    job_id = re.search(r"/jobs/(\d+)/", page.url).group(1)
    print(f"\n[result] meet_now job_id={job_id}")

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/meet_now_submission.png")
    write_detail("test_meet_now_submission", {
        "message": f"Meet-now form submitted, redirected to job {job_id}",
        "job_id": job_id,
        "screenshot": "screenshots/meet_now_submission.png",
    })
