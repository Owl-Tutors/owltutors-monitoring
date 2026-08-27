from contextlib import contextmanager

from playwright.sync_api import Page

from utils.set_tutor_availability_state import set_tutor_availability_state

# UI grid cell -> search "slot" -> DB (dow, slot_index) mapping, verified directly
# against ot_slot_to_dow_and_range() and content-tutorSearch_v2_new.php:
#   data-row="Morning" data-col="0"  ==  search slot 1 (row 0 x dow 0 + 1)
#   ==  DB dow=0 (Monday), slot_index in [0, 29] (Daytime range)
# slot_index=10 sits safely inside that range.
DOW = 0
SLOT_INDEX = 10
UI_ROW = "Morning"
UI_COL = "0"


def pick_search_visible_tutor_id(page: Page, base_url: str) -> tuple:
    """Grabs a real tutor ID from the default /tutors/ search results, same
    'pick a real tutor rather than hardcode one' approach as the
    meet_now_eligible_tutor_id / availability_eligible_tutor_id fixtures
    (conftest.py) — this tutor is guaranteed to actually appear in search
    results (unlike e.g. TEST_MEET_NOW_TUTOR_ID, which is permanently
    excluded-listed).

    Also reads the tutor's own first subject straight off their card
    (p.mb-2.text-muted.small — verified directly against the DB's
    subject_list for that user) rather than assuming a fixed subject like
    "Maths": the first default-listing tutor may teach anything, and the
    day/time search requires a subject that actually matches for the tutor
    to appear at all, regardless of their availability outcome.

    Returns (tutor_id, subject).
    """
    page.goto(f"{base_url}/tutors/", wait_until="domcontentloaded")
    page.wait_for_selector(".add-to-cart", timeout=15000)
    card = page.locator("article.author-card").first
    tutor_id = card.locator(".add-to-cart").get_attribute("value")
    assert tutor_id, "No tutor cards found in default search results — cannot pick a candidate"
    subjects_text = card.locator("p.mb-2.text-muted.small").first.text_content() or ""
    subject = subjects_text.split("•")[0].strip()
    assert subject, f"Could not read a subject off the picked tutor's card (raw text: {subjects_text!r})"
    return tutor_id, subject


@contextmanager
def day_time_search_state(base_url, api_key, tutor_id, *, capacity, availability_updated_unix, date_free=""):
    """
    Forces a real tutor's entire saved-slot set to a single known slot
    (DOW/SLOT_INDEX above, matching UI_ROW/UI_COL) plus the given
    capacity/timestamp/date_free — the fields ot_tutor_availability_info_handler()
    (functions.php) uses to compute availability_outcome 1a/1b/2/3 — then
    restores the tutor's original slots/capacity/timestamp/date_free on exit.

    Only the outcome-determining fields vary between the different day/time
    search regression tests; the slot itself is always the same known cell so
    every test can search for it identically via search_day_time_slot() below.
    """
    result = set_tutor_availability_state(
        base_url, api_key, tutor_id,
        dow=DOW, slot_index=SLOT_INDEX,
        capacity=capacity, availability_updated_unix=availability_updated_unix,
        date_free=date_free,
    )
    previous = result["previous"]
    try:
        yield
    finally:
        set_tutor_availability_state(
            base_url, api_key, tutor_id,
            slots=previous["slots"], capacity=previous["capacity"],
            availability_updated_unix=previous["availability_updated_unix"],
            date_free=previous["date_free"],
        )


def search_day_time_slot(page: Page, base_url: str, subject: str):
    """
    Performs the front-end day/time search matching DOW/SLOT_INDEX above:
    selects a subject (required to reveal the availability grid), expands the
    accordion, clicks the Monday/Daytime cell, then clicks the #tutor_filter
    submit button — selecting fields alone doesn't trigger the AJAX search
    (verified directly: the captured POST body was just {"page":"1","offset":"0"}
    with no subject/availability keys until the submit button is clicked, same
    as test_full_search_subject_level_home_location's pipeline) — and waits for
    the AJAX search (action=ot_tutor_search_filter, ot_tutor_search_v2_new.js)
    to settle.
    """
    page.goto(f"{base_url}/tutors/", wait_until="domcontentloaded")
    page.select_option("#hero_subject", label=subject)
    page.locator("button[data-bs-target='#collapseOne']").click()
    page.wait_for_selector("#collapseOne.show", timeout=5000)
    page.locator(f"div.cell:has(.avail-cell[data-row='{UI_ROW}'][data-col='{UI_COL}'])").click()
    page.locator("#tutor_filter").click()
    page.wait_for_selector(
        "#tutor_results article.author-card, #tutor_results .alert-info",
        timeout=20000,
    )
    page.wait_for_load_state("networkidle")
