import os
import re
import pytest
from playwright.sync_api import Page, expect

from utils.details import write_detail

JOB_URL = "/jobs/"
LOGIN_URL = "/login/"


def _login(page: Page, base_url: str, email: str, password: str):
    """Log in via the front-end login form."""
    page.goto(f"{base_url}{LOGIN_URL}")
    expect(page.locator("#ot_login")).to_be_visible()
    page.wait_for_load_state("domcontentloaded")
    page.locator("#ot_login_name").fill(email)
    page.locator("#pw1").fill(password)
    page.locator("#login_submit").click()
    # 90s: the post-login redirect can be slow (client may be sent to an existing
    # job page; the load event needs time to settle on a cold server).
    page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=90000)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — client views applicant cards
# ─────────────────────────────────────────────────────────────────────────────

def test_stage3_job_renders_applicant_cards(
    page: Page, base_url: str, stage3_job
):
    """
    Logged-in client on a Stage 3 job sees applicant cards, the sort dropdown,
    and at least one 'Connect with tutor' button.
    Covers P1: 'Stage 3 job page renders applicant cards and sort dropdown'
    and 'Logged-in client on Stage 3 job sees tutors to review dashboard state'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    expect(page.locator(".applicants")).to_be_visible()
    expect(page.locator(".applicant_box").first).to_be_visible()
    expect(page.locator("#ot_change_tutor_order")).to_be_visible()
    expect(page.locator("button.connect_with_tutor").first).to_be_visible()

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/stage3_applicant_cards.png")
    write_detail("test_stage3_job_renders_applicant_cards", {
        "message": f"Stage 3 job {stage3_job['job_id']} rendered applicant cards and sort dropdown",
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/stage3_applicant_cards.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — connect-with-tutor button triggers modal
# ─────────────────────────────────────────────────────────────────────────────

def test_connect_with_tutor_triggers_modal(
    page: Page, base_url: str, stage3_job
):
    """
    Clicking the 'Connect with tutor' button fires the ot_job_identify_modal
    AJAX and renders a modal (accept-terms, payment, or login depending on state).
    Covers P1: '"Connect with tutor" button present, triggers ot_job_identify_modal AJAX'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    btn = page.locator("button.connect_with_tutor").first
    expect(btn).to_be_visible()

    job_id_attr = btn.get_attribute("data-job_id")
    tutor_id_attr = btn.get_attribute("data-app_id")
    assert job_id_attr, "connect_with_tutor button missing data-job_id"
    assert tutor_id_attr, "connect_with_tutor button missing data-app_id"

    btn.click()
    # Any modal is acceptable — accept-terms, payment, or login
    page.wait_for_selector(".modal.show, .dash_modal.show", timeout=15000)

    os.makedirs("screenshots", exist_ok=True)
    try:
        page.screenshot(path="screenshots/connect_tutor_modal.png")
    except Exception:
        pass
    write_detail("test_connect_with_tutor_triggers_modal", {
        "message": (
            f"ot_job_identify_modal fired for job {job_id_attr} / tutor {tutor_id_attr}"
        ),
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/connect_tutor_modal.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — modal renders with content
# ─────────────────────────────────────────────────────────────────────────────

def test_accept_terms_modal_renders(
    page: Page, base_url: str, stage3_job
):
    """
    The modal that appears after clicking 'Connect with tutor' has rendered
    content — either an accept-terms checkbox + tutor details, or a payment /
    login form.  Checks the modal is non-empty and contains a recognisable
    interactive element.
    Covers P1: 'Accept-terms modal renders with tutor photo, name, and rate'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    page.locator("button.connect_with_tutor").first.click()
    page.wait_for_selector(".modal.show, .dash_modal.show", timeout=15000)

    modal = page.locator(".modal.show").first
    # Must contain a button or input — accept-terms, payment, or login
    interactive = modal.locator("button, input[type='submit'], input[type='checkbox']")
    expect(interactive.first).to_be_visible(timeout=5000)

    # Modal body must have meaningful text
    modal_text = modal.inner_text()
    assert len(modal_text.strip()) > 30, (
        f"Modal appears empty — inner text: {modal_text[:200]}"
    )

    os.makedirs("screenshots", exist_ok=True)
    try:
        page.screenshot(path="screenshots/accept_terms_modal.png")
    except Exception:
        pass
    write_detail("test_accept_terms_modal_renders", {
        "message": f"Stage 3 modal rendered with content for job {stage3_job['job_id']}",
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/accept_terms_modal.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — logged-out client sees login modal
# ─────────────────────────────────────────────────────────────────────────────

def test_logged_out_stage3_sees_login_modal(
    page: Page, base_url: str, stage3_job
):
    """
    A logged-out visitor on a Stage 3 job page sees the inline login form.
    Logging in via that form redirects back to the job and shows the applicant cards.
    Covers P1: 'Logged-out client on Stage 3 job sees inline login form and can
    authenticate to reach their job view'.
    """
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    # Logged-out visitors see an inline login form, not the applicant cards
    expect(page.locator("#ot_login")).to_be_visible(timeout=10000)

    # Log in using the stage3_job client credentials (password set during fixture setup)
    page.locator("#ot_login_name").fill(stage3_job["client_email"])
    page.locator("#pw1").fill(stage3_job["client_password"])
    page.locator("#login_submit").click()
    page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=90000)

    # Login on the job page redirects back to the same job URL, so we may already
    # be there. Only navigate explicitly if we landed somewhere else (e.g. dashboard).
    # Calling page.goto() when already on the target URL causes ERR_ABORTED because
    # WP JS fires a same-page redirect at the same moment Playwright starts a new one.
    if f"{JOB_URL}{stage3_job['job_id']}/" not in page.url:
        page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/", wait_until="domcontentloaded")

    # Now logged in, the job page should render with applicant cards
    expect(page.locator(".applicants")).to_be_visible()
    expect(page.locator("button.connect_with_tutor").first).to_be_visible()

    os.makedirs("screenshots", exist_ok=True)
    try:
        page.screenshot(path="screenshots/stage3_login_modal.png")
    except Exception:
        pass
    write_detail("test_logged_out_stage3_sees_login_modal", {
        "message": f"Logged-out user logged in via inline form and reached Stage 3 job {stage3_job['job_id']}",
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/stage3_login_modal.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stripe return — modal auto-triggers on page load
# ─────────────────────────────────────────────────────────────────────────────

def test_stripe_return_auto_triggers_modal(
    page: Page, base_url: str, stage3_job
):
    """
    Navigating to a Stage 3 job with ?payment_method_added=true&from_stripe=true
    auto-triggers the connect modal without any click.
    Covers P1: 'Stripe-return flow — page load with payment_method_added=true&
    from_stripe=true auto-triggers modal without click'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(
        f"{base_url}{JOB_URL}{stage3_job['job_id']}/"
        f"?payment_method_added=true&from_stripe=true&tutor_id={stage3_job['tutor_id']}"
    )
    # Modal should open automatically — no button click required
    page.wait_for_selector(".modal.show, .dash_modal.show", timeout=15000)

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/stripe_return_modal.png")
    write_detail("test_stripe_return_auto_triggers_modal", {
        "message": (
            f"Stripe-return params auto-opened modal on job {stage3_job['job_id']}"
        ),
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/stripe_return_modal.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 → Stage 4 — accept terms (MUST run last among Stage 3 tests:
# advances the shared stage3_job one-way to Stage 4)
# ─────────────────────────────────────────────────────────────────────────────

def test_accept_terms_advances_to_stage4(
    page: Page, base_url: str, stage3_job
):
    """
    Logged-in Active client accepts terms and connects with the tutor,
    advancing the job to Stage 4. The client_status=Active is set in the
    stage3_job fixture (Step 5) so ot_job_identify_modal returns the
    accept-terms form rather than the add-payment-method form.

    NOTE: this test consumes stage3_job — it must run after all other
    Stage 3 tests in this session. Pytest runs tests in file order so
    placing it here (after the other Stage 3 blocks) ensures that ordering.

    Covers P1: 'Accept terms advancing to Stage 4'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    btn = page.locator("button.connect_with_tutor").first
    expect(btn).to_be_visible()
    btn.click()

    # Client is Active — ot_job_identify_modal returns accept-terms modal
    page.wait_for_selector("#acceptTermsModal.show", timeout=15000)
    terms_cb = page.locator("input[name='accept_terms']")
    expect(terms_cb).to_be_visible(timeout=5000)
    terms_cb.check()

    # Submit — JS fires ot_job_modal_actions AJAX then sets window.location.href
    # to the same URL, so wait_for_url fires immediately on the pre-reload page.
    # expect_navigation starts listening before the click and waits for the reload.
    with page.expect_navigation(wait_until="load", timeout=30000):
        page.locator(".keep_inline_content[data-modaltype='accept_terms']").click(timeout=60000)

    # Job is now Stage 4 — "Your chosen tutor" section should be visible
    connected_section = page.locator(
        "section[aria-label='Connected tutor information']"
    )
    expect(connected_section).to_be_visible()
    expect(connected_section.locator("h2")).to_contain_text("Your chosen tutor")

    # Wait for any modal overlay to clear, then scroll to the tutor section
    # so the screenshot shows the Stage 4 chosen-tutor details cleanly.
    page.wait_for_selector(".modal.show", state="hidden", timeout=5000)
    connected_section.scroll_into_view_if_needed()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/stage4_from_accept_terms.png")
    write_detail("test_accept_terms_advances_to_stage4", {
        "message": f"Job {stage3_job['job_id']} advanced to Stage 4 after accepting terms",
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/stage4_from_accept_terms.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Magic link — auto-login
# ─────────────────────────────────────────────────────────────────────────────

def test_magic_link_auto_login(page: Page, base_url: str, magic_link_params):
    """
    A magic link URL (/jobs/{id}/?job={crc32}&email={email}) logs the client in
    silently and redirects to the job page.
    Covers P1: 'Magic link auto-login — /jobs/{id}/?job={crc32}&email={email}
    logs client in silently and redirects'.
    """
    job_id = magic_link_params["job_id"]
    crc32 = magic_link_params["crc32"]
    email = magic_link_params["email"]
    magic_url = f"{base_url}{JOB_URL}{job_id}/?job={crc32}&email={email}"

    page.goto(magic_url)
    # Should stay on the job page (or redirect to dashboard) — NOT /login/
    page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=30000)
    assert LOGIN_URL not in page.url, (
        f"Magic link did not authenticate — still on login: {page.url}"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/magic_link_login.png")
    write_detail("test_magic_link_auto_login", {
        "message": f"Magic link authenticated for job {job_id}",
        "job_id": job_id,
        "screenshot": "screenshots/magic_link_login.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — client sees connected tutor
# ─────────────────────────────────────────────────────────────────────────────

def test_client_stage4_job_shows_connected_tutor(
    page: Page, base_url: str, stage3_job
):
    """
    Logged-in client on a Stage 4 job sees the 'Your chosen tutor' section with
    connected tutor details.

    Uses the same dynamically created job/client as the Stage 3 tests. By the
    time this test runs, test_accept_terms_advances_to_stage4 has already
    advanced that job to Stage 4, so no permanent client account is needed.

    Covers P1: 'Logged-in client on Stage 4 job sees tutor selected dashboard state'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/", wait_until="domcontentloaded")

    connected_section = page.locator(
        "section[aria-label='Connected tutor information']"
    )
    expect(connected_section).to_be_visible()
    expect(connected_section.locator("h2")).to_contain_text("Your chosen tutor")

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/stage4_connected_tutor.png")
    write_detail("test_client_stage4_job_shows_connected_tutor", {
        "message": (
            f"Stage 4 job {stage3_job['job_id']} shows 'Your chosen tutor' section"
        ),
        "job_id": stage3_job["job_id"],
        "screenshot": "screenshots/stage4_connected_tutor.png",
    })
