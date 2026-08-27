import time

import pytest
from playwright.sync_api import Page, expect
from utils.day_time_search import (
    UI_COL, UI_ROW, day_time_search_state, pick_search_visible_tutor_id, search_day_time_slot,
)
from utils.details import write_detail

TUTORS_URL = "/tutors/"


def _dismiss_cookies(page: Page):
    """Dismiss the cookie consent banner if it is present."""
    try:
        page.locator("#ot_local_storage_accept").click(timeout=3000)
    except Exception:
        pass  # banner not present or already dismissed


# ── Existing core tests ──────────────────────────────────────────────────────

@pytest.mark.search
def test_tutor_search_page_loads(page: Page, base_url: str):
    """Search page loads and the search form is visible."""
    page.goto(f"{base_url}{TUTORS_URL}")
    expect(page.locator("#tutorSearchForm")).to_be_visible()
    write_detail("test_tutor_search_page_loads", {
        "message": "Tutor search page loaded with form visible",
    })


@pytest.mark.search
@pytest.mark.critical
def test_tutor_search_returns_results(page: Page, base_url: str):
    """Tutor listing AJAX search returns results — at least one tutor card loads."""
    page.goto(f"{base_url}{TUTORS_URL}")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".add-to-cart", timeout=15000)
    expect(page.locator(".add-to-cart").first).to_be_visible()
    page.locator("#tutor_results").scroll_into_view_if_needed()
    write_detail("test_tutor_search_returns_results", {
        "message": "Tutor search returned results via AJAX",
    })


@pytest.mark.search
def test_tutor_profile_loads(page: Page, base_url: str):
    """A tutor profile page loads correctly from the search results."""
    page.goto(f"{base_url}{TUTORS_URL}")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("article.author-card", timeout=15000)
    page.locator("article.author-card a[href*='/tutor/']").first.click()
    expect(page.locator(".tutor-hero--profile")).to_be_visible(timeout=10000)
    write_detail("test_tutor_profile_loads", {
        "message": "Tutor profile page loaded successfully",
    })


# ── Option A: UI progressive reveal ─────────────────────────────────────────

@pytest.mark.search
def test_subject_with_levels_reveals_level_dropdown(page: Page, base_url: str):
    """Selecting a subject that has levels makes the level dropdown visible."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.select_option("#hero_subject", label="English")
    expect(page.locator("#hero_level_col")).to_be_visible()
    write_detail("test_subject_with_levels_reveals_level_dropdown", {
        "message": "Level dropdown appeared after selecting English",
    })


@pytest.mark.search
def test_school_entrance_subject_reveals_school_filter(page: Page, base_url: str):
    """Selecting a school-entrance subject promotes the school autocomplete into the hero row."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.select_option("#hero_subject", label="11 Plus")
    expect(page.locator("#hero_school_col")).to_be_visible()
    # Type a school name and select the first autocomplete result
    page.locator("#filter_school").fill("Westminster")
    page.wait_for_selector("#school_list a.dropdown-item", timeout=10000)
    page.locator("#school_list a.dropdown-item").first.click()
    write_detail("test_school_entrance_subject_reveals_school_filter", {
        "message": "School filter appeared and school selected after choosing 11 Plus",
    })


@pytest.mark.search
def test_home_delivery_reveals_location_filter(page: Page, base_url: str):
    """Clicking the Home delivery button makes the location autocomplete visible."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.select_option("#hero_subject", label="English")
    page.locator("button.js-mode[data-value='Home']").click()
    expect(page.locator("#hero_location_col")).to_be_visible()
    write_detail("test_home_delivery_reveals_location_filter", {
        "message": "Location filter appeared after selecting Home delivery",
    })


@pytest.mark.search
def test_detailed_filters_reveal_sen_and_badges(page: Page, base_url: str):
    """Clicking 'Show all search options' reveals the SEN and badges selects, which can be set."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.locator("#filters_toggle").click()
    expect(page.locator("#filter_item_sen")).to_be_visible()
    expect(page.locator("#filter_item_badges")).to_be_visible()
    page.select_option("#filter_sen", index=1)
    page.select_option("#filter_badge", index=1)
    write_detail("test_detailed_filters_reveal_sen_and_badges", {
        "message": "SEN and badges filters visible and filled via detailed panel",
    })


@pytest.mark.search
def test_availability_grid_appears_and_accepts_input(page: Page, base_url: str):
    """Selecting a subject reveals the availability grid; slots can be checked."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.select_option("#hero_subject", label="English")
    expect(page.locator("#hero_availability_col")).to_be_visible()
    # Grid is inside a collapsed Bootstrap accordion — expand it first
    page.locator("button[data-bs-target='#collapseOne']").click()
    page.wait_for_selector("#collapseOne.show", timeout=5000)
    page.locator("div.cell:has(.avail-cell[data-row='Morning'][data-col='0'])").click()
    page.locator("div.cell:has(.avail-cell[data-row='Evening'][data-col='4'])").click()
    write_detail("test_availability_grid_appears_and_accepts_input", {
        "message": "Availability grid appeared and Monday morning + Friday evening selected",
    })


# ── Option B: full pipeline search ──────────────────────────────────────────

@pytest.mark.search
def test_full_search_subject_level_home_location(page: Page, base_url: str):
    """Full pipeline: English + GCSE + Home delivery + London location → AJAX results render."""
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)

    # Subject
    page.select_option("#hero_subject", label="English")
    expect(page.locator("#hero_level_col")).to_be_visible()

    # Level
    page.select_option("select.subject_level[data-subject='English']", index=1)

    # Home delivery
    page.locator("button.js-mode[data-value='Home']").click()
    expect(page.locator("#hero_location_col")).to_be_visible()

    # Location autocomplete
    page.locator("#filter_location").fill("Balham")
    page.wait_for_selector("#location_list a.dropdown-item", timeout=10000)
    page.locator("#location_list a.dropdown-item").first.click()

    # Submit
    page.locator("#tutor_filter").click()

    # Wait for either tutor cards or the no-results alert
    page.wait_for_selector(
        "#tutor_results article.author-card, #tutor_results .alert-info",
        timeout=20000,
    )

    page.locator("#tutor_results").scroll_into_view_if_needed()
    write_detail("test_full_search_subject_level_home_location", {
        "message": "Full pipeline search ran: English, Home delivery, Balham",
    })


# ── Meet Now buttons ──────────────────────────────────────────────────────────

@pytest.mark.search
def test_meet_now_button_visible_on_eligible_tutor(page: Page, base_url: str, meet_now_eligible_tutor_id):
    """
    A real tutor card in the default search results has a 'Connect now' button
    linking to /contact-us?job_type=meet_now&tutor_id=ID, once that tutor's
    eligibility flags are forced true by the meet_now_eligible_tutor_id fixture.

    docs/TESTING_REBUILD_SPEC.md Days 9-10: this test had two compounding root
    causes, neither a timing flake. (1) auto_swap_active is a real side effect
    of meet-now job creation (flipped to false, no automatic reset) — a prior
    test run leaves the fixture tutor ineligible. (2) The dedicated
    TEST_MEET_NOW_TUTOR_ID account is permanently on the site's
    excluded_tutors blocklist, so it can never appear in real search results
    regardless of its flags — forcing them true had no effect. The fixture
    now picks a real, non-excluded tutor from actual search results instead
    and restores their original flags afterward.
    Covers: 'Meet Now button visible on eligible tutor card'.
    """
    page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
    _dismiss_cookies(page)
    page.wait_for_selector(".add-to-cart", timeout=15000)

    meet_now_link = page.locator(
        f"a[href*='job_type=meet_now'][href*='tutor_id={meet_now_eligible_tutor_id}']"
    )
    expect(meet_now_link).to_be_visible(timeout=10000)

    write_detail("test_meet_now_button_visible_on_eligible_tutor", {
        "message": f"Meet Now button visible on eligible tutor {meet_now_eligible_tutor_id}'s card",
    })


@pytest.mark.search
def test_meet_now_button_absent_on_ineligible_tutor(page: Page, base_url: str):
    """
    Tutor cards for ineligible tutors have no 'Connect now' button.
    Finds any card that lacks a meet-now link and verifies it truly has none.
    Covers: 'Meet Now button absent on ineligible tutor card'.
    """
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.wait_for_selector("article.author-card", timeout=15000)

    # Cards without a meet-now link are the ineligible ones
    non_eligible = page.locator("article.author-card").filter(
        has_not=page.locator("a[href*='job_type=meet_now']")
    )
    assert non_eligible.count() > 0, (
        "Every tutor card has a meet-now button — expected at least one ineligible tutor"
    )
    first_card = non_eligible.first
    assert first_card.locator("a[href*='job_type=meet_now']").count() == 0, (
        "Found a meet-now link on a card filtered as ineligible"
    )

    write_detail("test_meet_now_button_absent_on_ineligible_tutor", {
        "message": "No Meet Now button on ineligible tutor card",
    })


# ── Batch K — availability summary ──────────────────────────────────────────

@pytest.mark.search
def test_availability_summary_on_profile(page: Page, base_url: str, availability_eligible_tutor_id: str):
    """
    A tutor card renders a button.tutor_availability that opens a Bootstrap
    tooltip (owltheme/js/availability_popovers.js) on hover/focus. Its HTML
    content -- including p.availability_slots_summary, built by
    render_slots_summary() (functions.php) for tutors with saved availability
    slots (availability_outcome 1a/1b) -- lives entirely in the button's
    data-bs-title attribute and is only injected into the DOM once the tooltip
    is actually triggered, so it can never be found by a plain page-load scan
    (the original version of this test always skipped for this reason, even
    when qualifying tutors existed). The availability_eligible_tutor_id
    fixture forces a real tutor's confirmation timestamp fresh so
    availability_outcome computes 1a/1b for the duration of this test.
    Covers: 'Availability summary renders correctly on public tutor profile'.
    """
    page.goto(f"{base_url}{TUTORS_URL}")
    _dismiss_cookies(page)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(".add-to-cart", timeout=15000)

    card = page.locator(f"article.author-card:has(.add-to-cart[value='{availability_eligible_tutor_id}'])")
    card.locator("button.tutor_availability").hover()
    tooltip_summary = page.locator(".tooltip.tutor-tooltip p.availability_slots_summary")
    expect(tooltip_summary).to_be_visible(timeout=5000)
    summary_text = (tooltip_summary.text_content() or "").strip()
    assert summary_text, (
        "p.availability_slots_summary is present but empty — render_slots_summary() may have broken"
    )

    write_detail("test_availability_summary_on_profile", {
        "message": f"Availability summary renders: {summary_text[:80]!r}",
    })


# ── Batch — day/time-filtered search (v10.2.25 regression) ──────────────────
#
# ot_tutor_search_db_handler() (tutor-mgmt.php) matches a searched day/time
# slot against raw tutor_search_slots rows, then re-checks each match against
# ot_tutor_availability_info_handler()'s availability_outcome — only 1a/1b
# pass; 2 (capacity=0, future date_free) and 3 (stale confirmation, or no
# capacity/date_free at all) are filtered out even though the raw slot still
# matches. Before v10.2.25 that outcome re-check didn't happen, so tutors who
# were actually unavailable could appear for a specific day/time search.
# Every test below forces the SAME tutor onto the SAME known slot (Monday,
# Daytime — day_time_search.py) and only varies capacity/timestamp/date_free,
# so a plain "does this tutor's card appear after searching that exact slot"
# check is enough to prove inclusion/exclusion either way.

@pytest.mark.search
@pytest.mark.critical
def test_day_time_search_excludes_outcome_2(page: Page, base_url: str, api_key: str):
    """Tutor with capacity=0 and a future date_free (outcome 2) is excluded
    from a search matching their raw saved slot, despite the slot matching.
    Covers: 'Day/time-filtered search excludes tutor with capacity=0 (outcome 2)'."""
    tutor_id, subject = pick_search_visible_tutor_id(page, base_url)
    future_date = time.strftime("%Y-%m-%d", time.localtime(time.time() + 30 * 86400))

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=0, availability_updated_unix=int(time.time()), date_free=future_date,
    ):
        search_day_time_slot(page, base_url, subject)
        card = page.locator(f".add-to-cart[value='{tutor_id}']")
        expect(card).to_have_count(0)

    write_detail("test_day_time_search_excludes_outcome_2", {
        "message": f"Tutor {tutor_id} (capacity=0, future date_free) correctly absent from matching day/time search",
    })


@pytest.mark.search
@pytest.mark.critical
def test_day_time_search_excludes_outcome_3(page: Page, base_url: str, api_key: str):
    """Tutor whose availability confirmation is >30 days stale (outcome 3) is
    excluded from a search matching their raw saved slot, despite the slot
    matching. Covers: 'Day/time-filtered search excludes tutor not confirmed
    within 30 days (outcome 3)'."""
    tutor_id, subject = pick_search_visible_tutor_id(page, base_url)
    stale_timestamp = int(time.time()) - 31 * 86400

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=5, availability_updated_unix=stale_timestamp,
    ):
        search_day_time_slot(page, base_url, subject)
        card = page.locator(f".add-to-cart[value='{tutor_id}']")
        expect(card).to_have_count(0)

    write_detail("test_day_time_search_excludes_outcome_3", {
        "message": f"Tutor {tutor_id} (31-day-stale confirmation) correctly absent from matching day/time search",
    })


@pytest.mark.search
@pytest.mark.critical
def test_day_time_search_includes_outcome_1(page: Page, base_url: str, api_key: str):
    """Golden path: tutor with capacity>0 and a fresh (<30 day) confirmation
    (outcome 1b) IS included in a search matching their raw saved slot —
    confirms the outcome fix doesn't over-exclude genuinely available tutors.
    Covers: 'Day/time-filtered search includes tutor with outcome 1a/1b'."""
    tutor_id, subject = pick_search_visible_tutor_id(page, base_url)

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=5, availability_updated_unix=int(time.time()),
    ):
        search_day_time_slot(page, base_url, subject)
        card = page.locator(f".add-to-cart[value='{tutor_id}']")
        expect(card).to_have_count(1)

    write_detail("test_day_time_search_includes_outcome_1", {
        "message": f"Tutor {tutor_id} (capacity>0, fresh confirmation) correctly present in matching day/time search",
    })


@pytest.mark.search
def test_day_time_search_total_count_reflects_exclusion(page: Page, base_url: str, api_key: str):
    """
    ot_tutor_search_db_handler() subtracts $count_reduction from $total after
    the outcome re-check, separately from the returned tutor_ids page — a
    bug here would show the right cards but a wrong "N tutors found" count /
    pagination state. Forces the same known-matching tutor through outcome 3
    (excluded) then outcome 1b (included) and checks the response's own
    `total` field each time, not just card presence.
    Covers: 'Day/time-filtered search result count/pagination stays consistent
    with the filtered set'.
    """
    tutor_id, subject = pick_search_visible_tutor_id(page, base_url)

    def _search_and_get_total():
        page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
        page.select_option("#hero_subject", label=subject)
        page.locator("button[data-bs-target='#collapseOne']").click()
        page.wait_for_selector("#collapseOne.show", timeout=5000)
        page.locator(f"div.cell:has(.avail-cell[data-row='{UI_ROW}'][data-col='{UI_COL}'])").click()
        with page.expect_response(
            lambda r: "admin-ajax.php" in r.url and r.request.method == "POST", timeout=15000
        ) as resp_info:
            page.locator("#tutor_filter").click()
        return resp_info.value.json().get("total")

    stale_timestamp = int(time.time()) - 31 * 86400
    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=5, availability_updated_unix=stale_timestamp,
    ):
        excluded_total = _search_and_get_total()

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=5, availability_updated_unix=int(time.time()),
    ):
        included_total = _search_and_get_total()

    assert included_total == excluded_total + 1, (
        f"Expected total to increase by exactly 1 tutor once outcome flips to 1b — "
        f"excluded total={excluded_total}, included total={included_total}"
    )

    write_detail("test_day_time_search_total_count_reflects_exclusion", {
        "message": f"total correctly reflects exclusion/inclusion: {excluded_total} -> {included_total}",
    })


@pytest.mark.search
def test_admin_day_time_search_applies_same_outcome_filter(page: Page, base_url: str, api_key: str):
    """
    ot_admin_tutor_search_filter_callback() (functions.php) shares
    ot_tutor_search_db_handler() with the front-end search — confirms the
    v10.2.25 outcome fix isn't front-end-only by exercising the admin AJAX
    action directly (it's registered wp_ajax_nopriv, so no admin session is
    needed to reach the same code path) with the same tutor/slot forced
    through a bad outcome, then a good one.
    Covers: 'Admin tutor search applies the same day/time outcome filter'.
    """
    tutor_id, subject = pick_search_visible_tutor_id(page, base_url)

    def _admin_search_ids():
        resp = page.request.get(
            f"{base_url}/wp-admin/admin-ajax.php",
            params={
                "action": "ot_admin_tutor_search_filter",
                "search[subject]": subject,
                "search[availability]": "AQAA",  # slot 1 == UI_ROW/UI_COL (Monday, Daytime)
                "search[page]": "1",
                "search[offset]": "0",
            },
        )
        assert resp.status == 200, f"Admin search AJAX returned {resp.status}"
        return [str(x) for x in resp.json().get("output_ids", [])]

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=0, availability_updated_unix=int(time.time()), date_free="",
    ):
        excluded_ids = _admin_search_ids()
        assert tutor_id not in excluded_ids, (
            f"Tutor {tutor_id} (outcome 2, capacity=0) unexpectedly present in admin search results"
        )

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=5, availability_updated_unix=int(time.time()),
    ):
        included_ids = _admin_search_ids()
        assert tutor_id in included_ids, (
            f"Tutor {tutor_id} (outcome 1b, capacity>0) unexpectedly absent from admin search results"
        )

    write_detail("test_admin_day_time_search_applies_same_outcome_filter", {
        "message": f"Admin search correctly excludes/includes tutor {tutor_id} matching the front-end outcome filter",
    })


# ── Tutor card availability tooltip — outcome-specific states ───────────────
#
# NOTE: the original doc row for this pair ("Outcome 1a shows an 'available
# from' state") didn't match the actual code — verified directly against
# owltheme/functions.php (author-card availability tooltip block, ~line 1548):
# outcome 1a and 1b render IDENTICALLY (both just show p.availability_slots_summary
# via render_slots_summary()); the "available from {date}" message
# (p.availability_futuredate) is actually part of outcome 2's tooltip, not 1a's.
# These two tests cover the real distinguishable states instead: outcome 2's
# waitlist+date message, and the generic "Contact us for availability"
# fallback every other outcome (3, or no data at all) gets.

def _hover_and_get_tooltip_html(page: Page, tutor_id: str) -> str:
    card = page.locator(f"article.author-card:has(.add-to-cart[value='{tutor_id}'])")
    card.locator("button.tutor_availability").hover()
    tooltip = page.locator(".tooltip.tutor-tooltip")
    expect(tooltip).to_be_visible(timeout=5000)
    html = tooltip.inner_html()
    page.mouse.move(0, 0)
    return html


@pytest.mark.search
def test_outcome_2_shows_waitlist_and_future_date_on_tutor_card(page: Page, base_url: str, api_key: str):
    """
    A tutor with capacity=0 and a future date_free (outcome 2) shows the
    waitlist message plus 'This tutor will have more availability from
    {date}' (p.availability_futuredate) in their card's availability tooltip,
    instead of the normal slots summary.
    Covers the real behaviour behind the doc's (mislabeled) 'Outcome 1a shows
    available-from state' row — see note above.
    """
    tutor_id, _ = pick_search_visible_tutor_id(page, base_url)
    future_date = time.strftime("%Y-%m-%d", time.localtime(time.time() + 30 * 86400))

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=0, availability_updated_unix=int(time.time()), date_free=future_date,
    ):
        page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
        page.wait_for_selector(".add-to-cart", timeout=15000)
        html = _hover_and_get_tooltip_html(page, tutor_id)

    assert "availability_waitlist" in html, f"Expected waitlist message in tooltip, got: {html!r}"
    assert "availability_futuredate" in html, f"Expected future-date message in tooltip, got: {html!r}"

    write_detail("test_outcome_2_shows_waitlist_and_future_date_on_tutor_card", {
        "message": f"Tutor {tutor_id} (outcome 2) shows waitlist + future-availability-date tooltip",
    })


@pytest.mark.search
def test_outcome_3_shows_generic_fallback_on_tutor_card(page: Page, base_url: str, api_key: str):
    """
    A tutor with no usable availability data (capacity=0, no date_free —
    outcome 3) shows the generic 'Contact us for availability' fallback
    message in their card's tooltip, not the normal slots summary or the
    outcome-2 waitlist message.
    Covers the real behaviour behind the doc's (mislabeled) 'Outcome 2/3
    suppresses availability display' row — see note above.
    """
    tutor_id, _ = pick_search_visible_tutor_id(page, base_url)

    with day_time_search_state(
        base_url, api_key, tutor_id,
        capacity=0, availability_updated_unix=int(time.time()), date_free="",
    ):
        page.goto(f"{base_url}{TUTORS_URL}", wait_until="domcontentloaded")
        page.wait_for_selector(".add-to-cart", timeout=15000)
        html = _hover_and_get_tooltip_html(page, tutor_id)

    assert "Contact us for availability" in html, f"Expected generic fallback message in tooltip, got: {html!r}"
    assert "availability_waitlist" not in html, f"Did not expect waitlist message in tooltip, got: {html!r}"

    write_detail("test_outcome_3_shows_generic_fallback_on_tutor_card", {
        "message": f"Tutor {tutor_id} (outcome 3) shows generic 'Contact us for availability' fallback tooltip",
    })
