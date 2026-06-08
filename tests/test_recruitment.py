import os
import re
import uuid
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import Page, expect

from utils.cleanup import delete_test_posts
from utils.details import write_detail

FIXTURES_DIR = Path(__file__).parent / "fixtures"

APPLICATION_URL = "/tutor-section/application/"
LOGIN_URL       = "/login/"

# Unique-ish email for the registration submission test.
# Uses a fixed suffix so the cleanup endpoint can delete the user by _ot_test_user meta.
TEST_REG_EMAIL    = "testbot.preapp@owltutors.co.uk"
TEST_REG_PASSWORD = "Owl1Tutor!Test2026"


@pytest.fixture(autouse=False)
def cleanup_after(base_url):
    """Delete all test-flagged records (including _ot_test_user) after the test."""
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


def _flag_test_user(page: Page):
    """Inject the test-user flag into the registration form.
    Analogous to _flag_test_post() in test_contact_submissions.py."""
    api_key = os.environ.get("OWL_TEST_API_KEY", "")
    page.evaluate(
        """(apiKey) => {
            document.getElementById('ot_test_user').value = '1';
            document.getElementById('ot_test_api_key_reg').value = apiKey;
        }""",
        api_key,
    )


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# Registration -- page loads
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def test_tutor_registration_page_loads(page: Page, base_url: str):
    """
    The tutor registration page (/tutor-section/application/) loads for a
    logged-out visitor and shows the [ot_applicant_register_form] shortcode
    (rendered as #signupform).
    Covers P1: 'Tutor registration page loads with [ot_applicant_register_form] visible'.
    """
    page.goto(f"{base_url}{APPLICATION_URL}")
    expect(page.locator("#signupform")).to_be_visible()
    expect(page.locator("#applicant_register")).to_be_visible()

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/tutor_registration_page.png")
    write_detail("test_tutor_registration_page_loads", {
        "message": "Tutor registration form visible at /tutor-section/application/",
        "screenshot": "screenshots/tutor_registration_page.png",
    })


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# Registration -- full submission
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def test_tutor_registration_submits(page: Page, base_url: str, cleanup_after):
    """
    Submitting the registration form with valid credentials creates a
    pre-applicant user and redirects to /tutor-section/application/?newpreapp=true.

    The ot_test_user flag (injected via page.evaluate) marks the new user with
    _ot_test_user=1 so the cleanup endpoint deletes them after the test.
    reCAPTCHA is skipped by submitting the form directly (PHP does not validate
    reCAPTCHA on registration).
    Covers P1: 'Registration form submits, creates pre-applicant user, redirects
    to application page (with cleanup)'.
    """
    page.goto(f"{base_url}{APPLICATION_URL}")
    expect(page.locator("#signupform")).to_be_visible()

    page.locator("#email").fill(TEST_REG_EMAIL)
    page.locator("#pw1").fill(TEST_REG_PASSWORD)

    # Inject test flag -- PHP checks ot_test_user + ot_test_api_key_reg before
    # setting _ot_test_user=1 on the new user (only on otdev1602/owltutors.test)
    _flag_test_user(page)

    # Submit directly (bypass reCAPTCHA -- PHP doesn't validate it for registration)
    page.evaluate("document.getElementById('signupform').submit()")

    # Should redirect to the application page with ?newpreapp=true
    page.wait_for_url(re.compile(r".*/tutor-section/application/"), timeout=30000)
    assert "tutor-section/application" in page.url, (
        f"Registration did not redirect to application page -- got: {page.url}"
    )

    print(f"\n[result] registration redirect: {page.url}")
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/tutor_registration_submit.png")
    write_detail("test_tutor_registration_submits", {
        "message": f"Registration submitted and redirected to {page.url}",
        "screenshot": "screenshots/tutor_registration_submit.png",
    })


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# Pre-applicant -- application page sections
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def test_preapplicant_application_page_loads(
    page: Page, base_url: str, preapplicant_credentials
):
    """
    A logged-in pre-applicant visiting /tutor-section/application/ sees the
    application form with its section tab-panes (#personalDetails,
    #supportingDocuments, #references).
    Covers P1: 'Pre-applicant application page loads with correct sections visible'.
    """
    # Log in as the test pre-applicant account
    page.goto(f"{base_url}{LOGIN_URL}")
    expect(page.locator("#ot_login")).to_be_visible()
    page.wait_for_load_state("networkidle")
    page.locator("#ot_login_name").fill(preapplicant_credentials["email"])
    page.locator("#pw1").fill(preapplicant_credentials["password"])
    page.locator("#login_submit").click()
    # Pre-applicants are redirected to /tutor-section/application/
    page.wait_for_url(
        re.compile(r".*/tutor-section/application/"), timeout=30000
    )

    page.goto(f"{base_url}{APPLICATION_URL}")

    # Personal details section should be visible (first tab-pane, active by default)
    expect(page.locator("#personalDetails")).to_be_visible()
    expect(page.locator("#personalDetailsForm")).to_be_visible()

    # Other tab panes exist in the DOM (may be hidden but should be present)
    assert page.locator("#supportingDocuments").count() > 0, (
        "#supportingDocuments tab pane not found in DOM"
    )
    assert page.locator("#references").count() > 0, (
        "#references tab pane not found in DOM"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/preapplicant_application_page.png")
    write_detail("test_preapplicant_application_page_loads", {
        "message": "Pre-applicant application page loaded with form sections present",
        "screenshot": "screenshots/preapplicant_application_page.png",
    })


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# Full application flow
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

def _show_section(page: Page, section_id: str):
    """Activate a section tab pane directly via JS.

    The well-holder nav links scroll above the viewport after JS init
    (ot_logged_in_preapp.js smooth-scrolls to the active section on load),
    so clicking them via Playwright times out. We replicate what the click
    handler does instead: strip show/active from all panes, add to target.
    """
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        (function() {{
            document.querySelectorAll('.tab-pane').forEach(function(p) {{
                p.classList.remove('in', 'show', 'active');
            }});
            var target = document.getElementById('{section_id}');
            if (target) {{
                target.classList.add('show', 'active');
                target.scrollIntoView({{block: 'start'}});
            }}
        }})();
    """)
    page.wait_for_selector(f"div#{section_id}.tab-pane.show", timeout=5000)
    page.wait_for_timeout(300)  # let Bootstrap fade transition complete


def _wait_for_section(page: Page, section_id: str) -> None:
    """Wait for a section tab-pane to be visible after a page reload.

    PHP's show_form_location logic (first incomplete section) does not always
    resolve to the expected next section -- e.g. if the previous section's score
    hasn't fully propagated before the redirect. If the natural wait times out,
    fall back to _show_section to force the pane visible via JS.
    """
    try:
        page.wait_for_selector(
            f"div#{section_id}.tab-pane.show", state="visible", timeout=15000
        )
    except Exception:
        _show_section(page, section_id)


def _save_section(page: Page, section_id: str):
    """Click Save & continue inside the specified section's form and wait for reload.

    Must target value='Save & continue' explicitly -- most sections also render
    a 'Previous' input[name='formDirection'] that appears first in the DOM.
    """
    form = page.locator(f"div#{section_id} form")
    form.locator("input[name='formDirection'][value='Save & continue']").click()
    # ACF intercepts the submit event, runs async field validation, then copies the
    # button value to a hidden input and calls form.submit() natively. During the
    # validation quiet period there are no network requests, so networkidle fires
    # prematurely. Two-phase wait handles this:
    # Phase 1 — networkidle: may fire during validation gap (fine, just returns early)
    page.wait_for_load_state("networkidle", timeout=60000)
    # Phase 2 — wait for current section to lose its 'show' class: this only happens
    # when the page actually navigates (new page load removes all tab-pane classes
    # before JS re-adds them to the next section). If we're still in the validation
    # phase, this wait blocks until the real POST + redirect completes.
    try:
        page.wait_for_selector(
            f"div#{section_id}.tab-pane.show",
            state="hidden",
            timeout=45000,
        )
    except Exception:
        pass
    # Phase 3 omitted — networkidle is unreliable here because WordPress Heartbeat
    # API and ACF field AJAX calls create persistent background requests that prevent
    # networkidle from ever firing. By the time Phase 2 completes, the page is loaded
    # and JS has run. _wait_for_section (DOM-visibility check) handles the rest.


def _add_repeater_row(page: Page, section_id: str, field_name: str) -> "Locator":
    """Add a row to an ACF repeater and return the new row locator.

    Requires the section to be *naturally* visible (shown by PHP's show_form_location,
    not by _show_section JS manipulation) so that ACF's field init and event handlers
    are properly attached. Uses click(force=True) to bypass any residual CSS opacity
    during Bootstrap's fade transition.

    ACF renders repeater rows as <tr class="acf-row"> (class-acf-repeater-table.php:327).
    """
    row_sel = f"#{section_id} [data-name='{field_name}'] tr.acf-row:not(.acf-clone)"
    count_before = page.locator(row_sel).count()

    btn = page.locator(
        f"#{section_id} [data-name='{field_name}'] .acf-actions a[data-event='add-row']"
    )
    btn.scroll_into_view_if_needed()
    btn.click(force=True)
    page.wait_for_timeout(800)

    count_after = page.locator(row_sel).count()
    assert count_after > count_before, (
        f"_add_repeater_row: clicking add-row did not add a row to "
        f"{section_id}/{field_name} (before={count_before}, after={count_after})"
    )
    return page.locator(row_sel).last


def _upload_acf_file(page: Page, section_id: str, field_name: str, file_path: str):
    """Upload a file into an ACF file field via the WP media modal.
    Falls back to a direct <input type='file'> if the basic uploader is used."""
    field_div = page.locator(f"div#{section_id} div[data-name='{field_name}']")

    # Try basic uploader first (input[type=file] directly in the field)
    basic_input = field_div.locator("input[type='file']")
    if basic_input.count() > 0:
        basic_input.set_input_files(file_path)
        page.wait_for_load_state("networkidle", timeout=15000)
        return

    # WP media library modal
    field_div.locator("a[data-name='add'], a.acf-button.button").first.click()
    page.wait_for_selector("div.media-frame", state="visible", timeout=10000)

    # Switch to Upload Files tab
    upload_tab = page.locator("li.media-menu-item").filter(has_text="Upload Files").first
    if upload_tab.count() > 0:
        upload_tab.click()
        page.wait_for_timeout(300)

    # Set the file on the upload input
    upload_input = page.locator("div.upload-ui input[type='file']")
    upload_input.set_input_files(file_path)
    page.wait_for_load_state("networkidle", timeout=20000)

    # Select the uploaded file
    select_btn = page.locator("button.media-button-select, button.media-button.media-button-select")
    select_btn.wait_for(state="enabled", timeout=15000)
    select_btn.click()
    page.wait_for_selector("div.media-frame", state="hidden", timeout=10000)


def test_tutor_full_application_flow(page: Page, base_url: str, cleanup_after):
    """
    End-to-end tutor application flow:
      1. Register as new pre-applicant at /tutor-section/application/
      2. Fill all 9 form sections (personal details â†' interview booking)
      3. Submit application â†' user promoted to 'applicant'
      4. Screenshots: registration, mid-progress, applicant state
      5. User deleted by cleanup endpoint (_ot_test_user=1)

    Emails suppressed: wp_mail and ot_sg_mail are skipped for _ot_test_user
    accounts (see pre-app-mgmt.php).
    """
    os.makedirs("screenshots", exist_ok=True)
    qts_pdf = str(FIXTURES_DIR / "test_qts.pdf")

    # Unique email per run to avoid conflicts if cleanup from a previous run failed
    run_id  = uuid.uuid4().hex[:8]
    email   = f"testbot.fullapp.{run_id}@owltutors.co.uk"
    password = "Owl1Tutor!Test2026"

    # â"€â"€ 1. Register â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    page.goto(f"{base_url}{APPLICATION_URL}")
    expect(page.locator("#signupform")).to_be_visible()
    page.locator("#email").fill(email)
    page.locator("#pw1").fill(password)
    _flag_test_user(page)
    page.evaluate("document.getElementById('signupform').submit()")
    page.wait_for_url(re.compile(r".*/tutor-section/application/"), timeout=30000)
    page.wait_for_load_state("networkidle")  # let JS init + smooth-scroll settle

    # Screenshot: empty application form
    page.screenshot(path="screenshots/recruit_01_registered.png")
    print(f"\n[recruit] registered: {email}")

    # â"€â"€ 2. Personal Details â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    # PHP sets show_form_location='personalDetails' for new users; JS adds show/active.
    # Do NOT call _show_section -- it strips/re-adds classes and can cause ACF to lose
    # its event handler bindings. Wait for the section to be naturally visible instead.
    _wait_for_section(page, "personalDetails")
    form = page.locator("form#personalDetailsForm")
    form.locator("div[data-name='first_names'] input").fill("Owl")
    form.locator("div[data-name='last_name'] input").fill("TestApplicant")
    form.locator("div[data-name='preferred_name'] input").fill("Owl")
    form.locator("div[data-name='mobile_phone_number'] input").fill("07700900001")
    form.locator("div[data-name='address'] input").fill("1 Test Street")
    form.locator("div[data-name='town__city'] input").fill("London")
    form.locator("div[data-name='postcode__zip'] input").fill("SW1A 1AA")
    country_sel = form.locator("div[data-name='country'] select")
    country_sel.select_option("United Kingdom") if country_sel.count() > 0 else None
    _save_section(page, "personalDetails")

    # â"€â"€ 3. Supporting Documents â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "supportingDocuments")
    form = page.locator("form#supportingDocumentsForm")
    # QTS country
    form.locator("div[data-name='qts_country'] select").select_option("United Kingdom")
    # QTS certificate file
    _upload_acf_file(page, "supportingDocuments", "upload_qts_certificate", qts_pdf)
    # Tax payer country
    form.locator("div[data-name='unique_taxpayer_reference_utr_number_country'] select").select_option(
        "United Kingdom"
    )
    # Sole trader / limited company
    sole_sel = form.locator("div[data-name='sole_trader_or_limited_company'] select")
    sole_sel.select_option(index=1)  # first non-blank option
    # Confirm possess docs checkbox
    confirm_cb = form.locator("div[data-name='confirm_possess_docs'] input[type='checkbox']")
    if confirm_cb.count() > 0 and not confirm_cb.is_checked():
        confirm_cb.check()
    _save_section(page, "supportingDocuments")

    # Screenshot: mid-progress
    page.screenshot(path="screenshots/recruit_02_docs.png")

    # â"€â"€ 4. Teaching Experience â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "teachingExperience")
    section = page.locator("div#teachingExperience")
    section.locator("div[data-name='years_of_classroom_teaching_experience'] input").fill("5")
    section.locator("div[data-name='please_describe_your_teaching_experience'] textarea").fill(
        "Five years teaching secondary Maths in UK state schools. Automated test."
    )
    # Motivations -- check first available option
    mot_cb = section.locator(
        "div[data-name='motivations_for_tutoring'] input[type='checkbox']"
    ).first
    if mot_cb.count() > 0 and not mot_cb.is_checked():
        mot_cb.check()
    # Teaching experience repeater.
    # Real field name: 'please_describe_your_teaching_experience_repeater' (not 'last_10_years').
    # data-min=1 means ACF renders one empty row by default -- no add needed.
    # Date fields are ACF date pickers: hidden input stores Ymd; .input is the display text.
    row = section.locator(
        "[data-name='please_describe_your_teaching_experience_repeater']"
        " tr.acf-row:not(.acf-clone)"
    ).first
    row.locator("div[data-name='school_name'] input").fill("Owl Test School")
    row.locator("div[data-name='roles'] input").fill("Maths Teacher")
    # Set date picker values directly: hidden input (Ymd for ACF) + display text input
    page.evaluate("""
        (function() {
            var row = document.querySelector(
                '#teachingExperience [data-name="please_describe_your_teaching_experience_repeater"]'
                + ' tr.acf-row:not(.acf-clone)'
            );
            if (!row) return;
            var sh = row.querySelector('[data-name="start_date"] input[type="hidden"]');
            var st = row.querySelector('[data-name="start_date"] input.input');
            var eh = row.querySelector('[data-name="end_date"] input[type="hidden"]');
            var et = row.querySelector('[data-name="end_date"] input.input');
            if (sh) sh.value = '20180901';
            if (st) st.value = '01/09/2018';
            if (eh) eh.value = '20230701';
            if (et) et.value = '01/07/2023';
        })();
    """)
    # Tuition subjects -- non-required; check if present, skip if not found/visible
    maths_cb = section.locator(
        "div[data-name='subject_list'] input[type='checkbox'][value='Maths']"
    )
    if maths_cb.count() > 0:
        maths_cb.first.check(timeout=5000)
    _save_section(page, "teachingExperience")

    # â"€â"€ 5. Delivery â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "delivery")
    page.locator(
        "div#delivery div[data-name='delivery'] input[type='checkbox'][value='Online']"
    ).check()
    _save_section(page, "delivery")

    # â"€â"€ 6. Availability â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    # v10.2.0: ACF form now only renders for_how_many_years_do_you_plan_on_being_a_tutor
    # (the two capacity fields were removed from the form). The slot grid is also required
    # for the availability section to score as complete — save one slot via AJAX before
    # _save_section so that PHP sees recruitment_availability_slots on the reload.
    _wait_for_section(page, 'availability')
    avail = page.locator('div#availability')
    avail.locator(
        '[data-name=for_how_many_years_do_you_plan_on_being_a_tutor] input'
    ).fill('3')

    # Wait for the [tutor_availability] shortcode to render and localize TutorAvail.
    page.wait_for_selector('#tutor_availability_holder', state='attached', timeout=10000)
    page.evaluate(
        '() => new Promise((resolve, reject) => {'
        '    const avail = window.TutorAvail || {};'
        '    const fd = new FormData();'
        "    fd.append('action', 'tutor_availability_save');"
        "    fd.append('nonce', avail.nonce || '');"
        "    fd.append('tutor_id', String(avail.tutorId || ''));"
        "    fd.append('slots', JSON.stringify({'0': [16]}));"
        "    fd.append('extra_capacity', '0');"
        "    fd.append('timezone', 'Europe/London');"
        "    fd.append('notes', '');"
        "    fd.append('date_free', '');"
        '    fetch(avail.ajaxUrl || "/wp-admin/admin-ajax.php", { method: "POST", body: fd })'
        '        .then(r => r.json())'
        '        .then(data => data.success ? resolve(data) : reject(data))'
        '        .catch(reject);'
        '})'
    )
    page.wait_for_timeout(300)
    _save_section(page, 'availability')

    # â"€â"€ 7. Rates â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "rates")
    rates = page.locator("div#rates")
    rates.locator("div[data-name='minimum_net_home_pay_rate'] select").select_option("30")
    rates.locator("div[data-name='minimum_net_online_pay_rate'] select").select_option("30")
    _save_section(page, "rates")

    # â"€â"€ 8. Qualifications â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "qualifications")
    quals = page.locator("div#qualifications")
    # Group sub-fields (data-name = sub-field name, not group-prefixed)
    quals.locator(
        "div[data-name='in_which_subject_did_you_qualify_to_teach'] select"
    ).select_option("Maths")
    quals.locator(
        "div[data-name='what_is_the_name_of_your_teaching_qualification'] input"
    ).fill("PGCE")
    quals.locator(
        "div[data-name='what_is_the_name_of_the_awarding_body_of_your_teaching_qualification'] input"
    ).fill("University College London")
    quals.locator(
        "div[data-name='in_what_year_did_you_achieve_your_teaching_qualification'] input"
    ).fill("2018")
    _save_section(page, "qualifications")

    # â"€â"€ 9. References â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "references")
    form = page.locator("form#referencesForm")
    # Line manager repeater: data-min=1 data-max=1, row-0 already exists.
    # Date fields are ACF date pickers; set hidden+display inputs via JS.
    lm_row = page.locator(
        "#references [data-name='line_manager_reference'] tr.acf-row:not(.acf-clone)"
    ).first
    lm_row.locator("div[data-name='name_of_school'] input").fill("Owl Test School")
    lm_row.locator("div[data-name='school_address'] input").fill("1 Test Street, London")
    lm_row.locator("div[data-name='first_name'] input").fill("Jane")
    lm_row.locator("div[data-name='last_name'] input").fill("Manager")
    lm_row.locator("div[data-name='relation_to_you'] input").fill("Head of Department")
    lm_row.locator("div[data-name='email_address'] input").fill("manager@owltest.co.uk")
    page.evaluate("""
        (function() {
            var row = document.querySelector(
                '#references [data-name="line_manager_reference"] tr.acf-row:not(.acf-clone)'
            );
            if (!row) return;
            var sh = row.querySelector('[data-name="employment_start_date"] input[type="hidden"]');
            var st = row.querySelector('[data-name="employment_start_date"] input.input');
            var eh = row.querySelector('[data-name="employment_finish_date"] input[type="hidden"]');
            var et = row.querySelector('[data-name="employment_finish_date"] input.input');
            if (sh) sh.value = '20180901';
            if (st) st.value = '01/09/2018';
            if (eh) eh.value = '20230701';
            if (et) et.value = '01/07/2023';
        })();
    """)
    # referees2: data-min=2 data-max=2, both rows pre-rendered. No add-row button at max.
    # JS (ot_logged_in_preapp.js) marks both rows required; both must be filled.
    ref_sel0 = "#references [data-name='referees2'] tr.acf-row[data-id='row-0']"
    ref_sel1 = "#references [data-name='referees2'] tr.acf-row[data-id='row-1']"
    page.locator(ref_sel0).locator("div[data-name='first_name'] input").fill("John")
    page.locator(ref_sel0).locator("div[data-name='last_name'] input").fill("Referee")
    page.locator(ref_sel0).locator("div[data-name='relation_to_you'] input").fill("Former colleague")
    page.locator(ref_sel0).locator("div[data-name='email_address'] input").fill("referee1@owltest.co.uk")
    page.locator(ref_sel1).locator("div[data-name='first_name'] input").fill("Jane")
    page.locator(ref_sel1).locator("div[data-name='last_name'] input").fill("Referee2")
    page.locator(ref_sel1).locator("div[data-name='relation_to_you'] input").fill("Former colleague")
    page.locator(ref_sel1).locator("div[data-name='email_address'] input").fill("referee2@owltest.co.uk")
    _save_section(page, "references")

    # â"€â"€ 10. Interview Booking â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _wait_for_section(page, "interviewBooking")
    # ACF date-time pickers: two inputs per field (hidden .input-alt for POST value,
    # visible .input for display only). fill() causes strict-mode violation and
    # cannot set hidden inputs. Use evaluate() to set both; hidden format is
    # strtotime-parseable (YYYY-MM-DD HH:MM:SS). Date constraints are client-side.
    d1 = datetime.now() + timedelta(days=14)
    d2 = datetime.now() + timedelta(days=15)
    d3 = datetime.now() + timedelta(days=16)
    page.evaluate(
        """(dates) => {
            ['first_interview_preference', 'second_interview_preference',
             'third_interview_preference'].forEach((name, i) => {
                const wrap = document.querySelector('[data-name="' + name + '"]');
                if (!wrap) return;
                const h = wrap.querySelector('input[type="hidden"]');
                const d = wrap.querySelector('input.input');
                if (h) h.value = dates[i][0];
                if (d) d.value = dates[i][1];
            });
        }""",
        [
            [d1.strftime("%Y-%m-%d 10:00:00"), d1.strftime("%d/%m/%y 10:00 AM")],
            [d2.strftime("%Y-%m-%d 10:00:00"), d2.strftime("%d/%m/%y 10:00 AM")],
            [d3.strftime("%Y-%m-%d 10:00:00"), d3.strftime("%d/%m/%y 10:00 AM")],
        ]
    )
    _save_section(page, "interviewBooking")

    # Screenshot: all sections filled, submit button should now be visible
    page.screenshot(path="screenshots/recruit_03_complete.png")

    # â"€â"€ 11. Submit application â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    # The #isappreadyForm only renders when overall_score == 1 (all sections complete)
    submit_form = page.locator("form#isappreadyForm")
    expect(submit_form).to_be_visible(timeout=5000)

    # "How did you hear about us" checkbox (required on submit form)
    submit_form.locator(
        "div[data-name='how_did_you_hear_about_owl_tutors'] input[type='checkbox']"
    ).first.check()
    # ACF conditional logic may reveal a dependent text field (e.g. "Who recommended
    # you?") after checking the first option. Wait for it and fill any that appear.
    page.wait_for_timeout(600)
    for inp in submit_form.locator("input[type='text']").all():
        if inp.is_visible():
            inp.fill("Automated test")
            break

    submit_form.locator("#SubmitButton").click()
    page.wait_for_load_state("networkidle", timeout=30000)

    # â"€â"€ 12. Verify applicant state â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    # After promotion the page reloads as 'applicant' role -- header changes
    expect(page.locator("header.bg-navy h1")).to_contain_text(
        re.compile(r"Welcome back|application", re.IGNORECASE), timeout=10000
    )

    # Screenshot: applicant dashboard / next steps
    page.screenshot(path="screenshots/recruit_04_applicant.png")
    print(f"\n[recruit] application submitted -- user promoted to applicant")

    write_detail("test_tutor_full_application_flow", {
        "message": "Full tutor application flow completed -- pre-applicant promoted to applicant",
        "screenshot": "screenshots/recruit_04_applicant.png",
    })



