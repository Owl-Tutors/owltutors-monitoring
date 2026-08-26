import os
import re
import pytest
from playwright.sync_api import Page, expect

from utils.cleanup import delete_test_posts
from utils.details import write_detail
from utils.get_test_job_fields import get_test_job_fields

CONTACT_URL = "/contact-us/"

FIRST_NAME = "Owl"
LAST_NAME  = "TestBot"
EMAIL      = "testbot@owltutors.co.uk"
PHONE      = "07700900000"


@pytest.fixture(autouse=False)
def cleanup_after(base_url):
    """Delete any test-flagged job posts after each test in this module."""
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


@pytest.mark.jobs
@pytest.mark.critical
def test_contact_form_callback_submission(page: Page, base_url: str, api_key: str, cleanup_after):
    """
    Submit the contact form as 'Book a callback with an agent'.
    Verifies the form is accepted and the browser is redirected to the new job URL.

    DB assertion (docs/TESTING_REBUILD_SPEC.md Days 2-3): job_create_type must
    actually be 'Regular' with no requested_job_members — this is the field
    that shipped blank on every job of every type for a month while redirect
    behaviour looked fine.
    """
    page.goto(f"{base_url}{CONTACT_URL}")
    expect(page.locator("#tutor_request_form")).to_be_visible()

    # Select form type
    page.locator("select[name='acf[field_64997c72bef9f]']").select_option(
        label="Book a callback with an agent"
    )

    # Client details
    page.locator("input[name='acf[field_5edf8887fb5e7]']").fill(FIRST_NAME)
    page.locator("input[name='acf[field_5edf8899fb5e8]']").fill(LAST_NAME)
    page.locator("input[name='acf[field_5edf889ffb5e9]']").fill(EMAIL)
    page.locator("input[name='acf[field_5a573454bb670]']").fill(PHONE)

    # Flag as test post before submitting
    _flag_test_post(page)

    # Ensure all JS (reCAPTCHA widget, submit handler) is fully initialised
    page.wait_for_load_state("networkidle")

    # Submit — PHP echoes a JS redirect so use wait_for_url rather than expect_navigation
    page.locator("#contact_form_submit").click()
    page.wait_for_url(re.compile(r".*/jobs/"), timeout=90000)

    job_id = re.search(r"/jobs/(\d+)/", page.url).group(1)
    print(f"\n[result] job_id={job_id}")

    fields = get_test_job_fields(base_url, api_key, job_id)
    print(f"\n[db-assert] job {job_id} fields: {fields}")
    assert fields["job_create_type"] == "Regular", (
        f"job {job_id}: job_create_type={fields['job_create_type']!r}, expected 'Regular'"
    )
    assert fields["requested_job_members"] == [], (
        f"job {job_id}: requested_job_members={fields['requested_job_members']!r}, expected empty"
    )

    write_detail("test_contact_form_callback_submission", {
        "message": f"Callback enquiry submitted and redirected to job {job_id}; job_create_type verified against DB",
        "job_id": job_id,
        "job_create_type": fields["job_create_type"],
    })
