"""
Small, self-contained tests for utilities that don't fit any specific user
journey — phone number validation (services/libphonenumber/system.php,
docs/libphonenumber.md; and the contact form's own field validator,
owl_system/includes/job-mgmt.php, docs/job-creation.md) and the GPA
calculator tool (pages/frontend-shortcodes.php,
docs/frontend-shortcodes-index.md §11).
"""
from playwright.sync_api import Page, expect
from utils.validate_phone_number import validate_phone_number, validate_job_phone_number
from utils.details import write_detail
import pytest

# The GPA calculator's own JS (ot_gpa_calculator2) is only enqueued on this
# specific post per owltheme/docs/asset-management.md — navigating by ID
# (?p=175250) avoids needing to know/maintain the real slug.
GPA_CALCULATOR_POST_ID = 175250


@pytest.mark.misc
def test_validate_number_classifies_uk_mobile_landline_and_invalid(base_url: str, api_key: str):
    """
    ot_libphonenumber_validate_number() (services/libphonenumber/system.php)
    correctly classifies a UK mobile as a bare digit string, a UK landline
    as the literal string 'Landline', and an unparseable input as null.

    Pure-logic test — no job/client/tutor fixture needed, just the new
    owl_validate_phone_number monitoring endpoint wrapping the function
    directly.

    Uses 07911 123456 rather than the more obvious-looking 07700 900xxx —
    the latter is Ofcom's officially reserved "drama"/fictional range (used
    in TV and film so no real subscriber is ever affected), which
    libphonenumber correctly treats as *not* a valid allocated number,
    returning null. Discovered on the first real run of this test: the
    function was working correctly, the chosen test number wasn't a real
    one.
    """
    mobile_result = validate_phone_number(base_url, api_key, "07911123456", "GB")
    assert mobile_result == "447911123456", (
        f"Expected a valid UK mobile to normalise to '447911123456', got: {mobile_result!r}"
    )

    landline_result = validate_phone_number(base_url, api_key, "02079460000", "GB")
    assert landline_result == "Landline", (
        f"Expected a valid UK landline to classify as 'Landline', got: {landline_result!r}"
    )

    invalid_result = validate_phone_number(base_url, api_key, "not a phone number", "GB")
    assert invalid_result is None, (
        f"Expected an unparseable input to return null, got: {invalid_result!r}"
    )

    write_detail("test_validate_number_classifies_uk_mobile_landline_and_invalid", {
        "message": (
            f"Mobile -> {mobile_result!r}, Landline -> {landline_result!r}, "
            f"Invalid -> {invalid_result!r}"
        ),
    })


@pytest.mark.misc
@pytest.mark.critical
def test_job_phone_validation_tolerates_invisible_unicode_chars(base_url: str, api_key: str):
    """
    Regression test for the v10.2.31 fix (docs/job-creation.md Known Issues):
    ot_jobs_validate_phone_number() — the contact form's telephone field
    validator — must accept a visibly-valid number even when it carries
    invisible Unicode formatting characters (category Cf), and must still
    reject a genuinely malformed number.

    U+202A (LEFT-TO-RIGHT EMBEDDING) / U+202C (POP DIRECTIONAL FORMATTING)
    are the exact characters found in real failed submissions — WhatsApp Web
    (and similar apps: iOS Contacts, Telegram) wrap copied phone numbers in
    these marks so they display correctly regardless of surrounding text
    direction. They render as nothing, so a number carrying them looks
    identical to a clean one in every UI, but previously failed validation
    outright.

    Marked critical: this sits directly in the job-creation contact form
    funnel — a false rejection here silently blocks a real client enquiry.
    """
    contaminated_number = "‪07771 660542‬"
    valid, message = validate_job_phone_number(base_url, api_key, contaminated_number)
    assert valid, (
        f"Expected a visibly-valid number with invisible Unicode formatting "
        f"characters to pass validation, but it was rejected: {message!r}"
    )

    invalid_valid, invalid_message = validate_job_phone_number(base_url, api_key, "not a phone number")
    assert not invalid_valid, "Expected a genuinely malformed number to still be rejected"
    assert invalid_message, "Expected a rejection message for a genuinely malformed number"

    write_detail("test_job_phone_validation_tolerates_invisible_unicode_chars", {
        "message": (
            f"Contaminated number valid -> {valid!r}, "
            f"malformed number rejected with message -> {invalid_message!r}"
        ),
    })


@pytest.mark.misc
def test_gpa_calculator_returns_result_for_valid_input(page: Page, base_url: str):
    """
    The GPA calculator (ot_gpa_calculator shortcode + ot_gpa_calculator_ajax_callback)
    returns a computed result for a known, valid grade conversion — US letter
    grade 'A' should convert to GPA 4, per the grades_to_gpa_table in
    ot_gpa_calculator_ajax_callback().

    Driven through the real UI (not a raw AJAX POST) because the endpoint is
    nonce-protected (check_ajax_referer('ot_gpa_calculator_action', ...)) —
    the nonce is only available embedded in a real page render.
    """
    page.goto(f"{base_url}/?p={GPA_CALCULATOR_POST_ID}", wait_until="domcontentloaded")
    expect(page.locator("#gpa_input")).to_be_visible(timeout=15000)

    page.locator("#gpa_input").select_option(value="us_letter_to_gpa")
    expect(page.locator("#us_letter_grade_select")).to_be_visible(timeout=10000)
    page.locator("#us_letter_grade_select").select_option(value="A")
    page.locator("#gpa_calculate").click()

    expect(page.locator("#gpa_result_value")).to_be_visible(timeout=10000)
    result_text = page.locator("#gpa_result_value").inner_text().strip()
    assert result_text, "Expected #gpa_result_value to contain a computed result, got empty text"
    assert "4" in result_text, (
        f"Expected the GPA for letter grade 'A' to include '4' (grades_to_gpa_table maps "
        f"'A' -> 4), got: {result_text!r}"
    )

    write_detail("test_gpa_calculator_returns_result_for_valid_input", {
        "message": f"GPA calculator returned {result_text!r} for US letter grade 'A'",
    })


# ot_school_fee_calculator_callback() renders its own real page at this slug —
# a plain full-page form POST (not AJAX), unlike the GPA calculator above.
SCHOOL_FEE_CALCULATOR_URL = "/private-school-fees/"


@pytest.mark.misc
def test_school_fee_calculator_returns_result_for_valid_input(page: Page, base_url: str):
    """
    The school fee calculator (ot_school_fee_calculator shortcode,
    pages/frontend-shortcodes.php) renders a fee projection for valid input.

    Plain full-page form POST protected by wp_verify_nonce() rather than an
    AJAX callback -- fill and submit the real #schoolFees form rather than
    posting directly, so the nonce is genuine. start_month only ever offers
    one option ('September') in the current implementation.
    """
    page.goto(f"{base_url}{SCHOOL_FEE_CALCULATOR_URL}", wait_until="domcontentloaded")
    expect(page.locator("#schoolFees")).to_be_visible(timeout=15000)

    page.locator("#current_fees").fill("18000")
    page.locator("#years_at_school").fill("5")
    page.locator("#start_year").select_option(label="2027")
    page.locator("#schoolFees button[type='submit'], #schoolFees input[type='submit']").click()

    page.wait_for_load_state("domcontentloaded")
    results_table = page.locator("#school_fee_calculator_results")
    expect(results_table).to_be_visible(timeout=15000)
    results_text = results_table.inner_text()
    assert "£" in results_text, (
        f"Expected the results table to contain a £-denominated fee figure, got: {results_text!r}"
    )

    write_detail("test_school_fee_calculator_returns_result_for_valid_input", {
        "message": "School fee calculator rendered a fee breakdown table for 5 years from 2027",
    })
