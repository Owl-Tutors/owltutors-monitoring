import json
import os
from playwright.sync_api import Page, expect
from utils.details import write_detail

SCHOOLS_URL = "/school-entrance-guide/"
SCHOOL_PROFILE_URL = "/schools/westminster/"


def _dismiss_cookies(page: Page):
    """Dismiss the cookie consent banner if it is present."""
    try:
        page.locator("#ot_local_storage_accept").click(timeout=3000)
    except Exception:
        pass


def test_school_listing_page_loads(page: Page, base_url: str):
    """School entrance guide listing page loads and the filter form is visible."""
    page.goto(f"{base_url}{SCHOOLS_URL}")
    expect(page.locator("#school_entry_points")).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_listing_page.png")
    write_detail("test_school_listing_page_loads", {
        "message": "School entrance guide listing page loaded with filter form visible",
        "screenshot": "screenshots/school_listing_page.png",
    })


def test_school_text_search_ajax(page: Page, base_url: str):
    """Inline AJAX text search returns matching schools in the dropdown."""
    page.goto(f"{base_url}{SCHOOLS_URL}")
    _dismiss_cookies(page)
    page.locator("#school-search-form input[name='school_name']").fill("Westminster")
    page.wait_for_selector("#school_search_results a.list-group-item", timeout=10000)
    expect(page.locator("#school_search_results a.list-group-item").first).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_text_search.png")
    write_detail("test_school_text_search_ajax", {
        "message": "School AJAX text search returned results for 'Westminster'",
        "screenshot": "screenshots/school_text_search.png",
    })


def test_school_filter_form_returns_results(page: Page, base_url: str):
    """Multi-select filter form returns matching school cards when submitted."""
    page.goto(f"{base_url}{SCHOOLS_URL}")
    _dismiss_cookies(page)
    page.select_option("#school_entry_points", label="11 Plus")
    page.locator("form[name='school_search_form'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("article.school_result_box", timeout=15000)
    expect(page.locator("article.school_result_box").first).to_be_visible()
    page.locator("article.school_result_box").first.scroll_into_view_if_needed()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_filter_results.png")
    write_detail("test_school_filter_form_returns_results", {
        "message": "School filter form returned results for 11 Plus entry point",
        "screenshot": "screenshots/school_filter_results.png",
    })


def test_school_profile_loads(page: Page, base_url: str):
    """Westminster school profile loads correctly via the AJAX text search."""
    page.goto(f"{base_url}{SCHOOLS_URL}")
    _dismiss_cookies(page)
    page.locator("#school-search-form input[name='school_name']").fill("Westminster")
    page.wait_for_selector("#school_search_results a.list-group-item", timeout=10000)
    page.locator("#school_search_results a.list-group-item").first.click()
    page.wait_for_load_state("networkidle", timeout=60000)
    expect(page.locator("section#overview")).to_be_visible(timeout=15000)
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_profile.png")
    write_detail("test_school_profile_loads", {
        "message": "Westminster school profile loaded with overview section visible",
        "screenshot": "screenshots/school_profile.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# School profile — JSON-LD
# ─────────────────────────────────────────────────────────────────────────────

def test_school_profile_json_ld_present(page: Page, base_url: str):
    """
    A school profile page renders at least one valid JSON-LD block with
    schema.org context.  Checks that content-schema.php is outputting
    structured data correctly for the 'schools' CPT.
    Covers P3: 'JSON-LD EducationalOccupationalProgram on profile'.
    Note: once EducationalOccupationalProgram is added to ot_build_school_schema_payload,
    update this test to assert that @type value specifically.
    """
    page.goto(f"{base_url}{SCHOOL_PROFILE_URL}")
    page.wait_for_load_state("domcontentloaded")

    ld_json_blocks = page.locator("script[type='application/ld+json']")
    assert ld_json_blocks.count() > 0, "No JSON-LD script tags found on school profile page"

    # Parse each block and find at least one with schema.org @context
    found_schema = False
    errors = []
    for i in range(ld_json_blocks.count()):
        raw = ld_json_blocks.nth(i).inner_html()
        try:
            data = json.loads(raw)
            ctx = data.get("@context", "")
            if "schema.org" in ctx:
                found_schema = True
                break
        except json.JSONDecodeError as e:
            errors.append(f"Block {i}: {e}")

    assert found_schema, (
        f"No JSON-LD block with schema.org @context found on {SCHOOL_PROFILE_URL}. "
        f"Parse errors: {errors}"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_json_ld.png")
    write_detail("test_school_profile_json_ld_present", {
        "message": "School profile has valid JSON-LD with schema.org context",
        "screenshot": "screenshots/school_json_ld.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# School profile — linked papers
# ─────────────────────────────────────────────────────────────────────────────

def test_school_profile_linked_papers(page: Page, base_url: str):
    """
    Westminster school profile renders an exam papers section (the
    #entrance_papers_for_westminster section) containing at least one paper
    card.  single-schools.php outputs this section when ot_get_school_papers()
    returns results for the school.
    Covers P3: 'School-linked papers rendered on profile page'.
    """
    page.goto(f"{base_url}{SCHOOL_PROFILE_URL}")
    page.wait_for_load_state("networkidle", timeout=60000)

    # The section ID is built from the school slug: entrance_papers_for_{slug}
    papers_section = page.locator("section[id^='entrance_papers_for_']")
    expect(papers_section).to_be_visible(timeout=15000)

    # At least one paper card must render inside the section
    paper_cards = papers_section.locator(".paper-card, .ot-paper-card, article")
    assert paper_cards.count() > 0, (
        "No paper cards found inside the school entrance papers section on Westminster profile"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/school_linked_papers.png")
    write_detail("test_school_profile_linked_papers", {
        "message": f"Westminster profile shows {paper_cards.count()} paper card(s) in entrance papers section",
        "screenshot": "screenshots/school_linked_papers.png",
    })
