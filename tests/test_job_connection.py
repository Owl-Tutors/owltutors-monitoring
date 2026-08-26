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

@pytest.mark.jobs
@pytest.mark.critical
def test_stage3_job_renders_applicant_cards(
    page: Page, base_url: str, stage3_job
):
    """
    Logged-in client on a Stage 3 job sees applicant cards, the sort dropdown,
    and at least one 'Connect with tutor' button.
    Covers: 'Stage 3 job page renders applicant cards and sort dropdown'
    and 'Logged-in client on Stage 3 job sees tutors to review dashboard state'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    expect(page.locator(".applicants")).to_be_visible()
    expect(page.locator(".applicant_box").first).to_be_visible()
    expect(page.locator("#ot_change_tutor_order")).to_be_visible()
    expect(page.locator("button.connect_with_tutor").first).to_be_visible()

    write_detail("test_stage3_job_renders_applicant_cards", {
        "message": f"Stage 3 job {stage3_job['job_id']} rendered applicant cards and sort dropdown",
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — connect-with-tutor button triggers modal
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
@pytest.mark.critical
def test_connect_with_tutor_triggers_modal(
    page: Page, base_url: str, stage3_job
):
    """
    Clicking the 'Connect with tutor' button fires the ot_job_identify_modal
    AJAX and renders a modal (accept-terms, payment, or login depending on state).
    Covers: '"Connect with tutor" button present, triggers ot_job_identify_modal AJAX'.
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

    write_detail("test_connect_with_tutor_triggers_modal", {
        "message": (
            f"ot_job_identify_modal fired for job {job_id_attr} / tutor {tutor_id_attr}"
        ),
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — modal renders with content
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
def test_accept_terms_modal_renders(
    page: Page, base_url: str, stage3_job
):
    """
    The modal that appears after clicking 'Connect with tutor' has rendered
    content — either an accept-terms checkbox + tutor details, or a payment /
    login form.  Checks the modal is non-empty and contains a recognisable
    interactive element.
    Covers: 'Accept-terms modal renders with tutor photo, name, and rate'.
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

    write_detail("test_accept_terms_modal_renders", {
        "message": f"Stage 3 modal rendered with content for job {stage3_job['job_id']}",
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — logged-out client sees login modal
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
def test_logged_out_stage3_sees_login_modal(
    page: Page, base_url: str, stage3_job
):
    """
    A logged-out visitor on a Stage 3 job page sees the inline login form.
    Logging in via that form redirects back to the job and shows the applicant cards.
    Covers: 'Logged-out client on Stage 3 job sees inline login form and can
    authenticate to reach their job view'.
    """
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/")

    # Logged-out visitors see an inline login form, not the applicant cards
    expect(page.locator("#ot_login")).to_be_visible(timeout=10000)

    # Log in using the stage3_job client credentials (password set during fixture setup)
    page.locator("#ot_login_name").fill(stage3_job["client_email"])
    page.locator("#pw1").fill(stage3_job["client_password"])
    page.locator("#login_submit").click()

    # The inline #ot_login form does a real full-page POST to wp-login.php
    # (recaptcha_verify.js calls the form's own .submit()), which then
    # redirects back here via the redirect_to hidden field -- a two-hop
    # navigation, not an AJAX call. Waiting for "URL no longer contains
    # /login/" (the pattern _login() uses elsewhere in this file) doesn't
    # work here: this test never visits /login/ at all -- neither this job
    # page's URL nor wp-login.php's contains that substring -- so that check
    # was already satisfied before the click even happened, and the
    # assertion below used to run before the redirect had actually
    # completed. Wait for the known final destination instead.
    page.wait_for_url(f"**{JOB_URL}{stage3_job['job_id']}/**", timeout=90000)

    # This login path is genuinely slower than a normal page load: it goes
    # through reCAPTCHA v3 twice (client-side grecaptcha.execute() calling
    # Google, then server-side verify_recaptcha() in ot_redirect_authenticate()
    # calling Google again) before wp-login.php's redirect even fires -- see
    # docs/client-tutor-connection.md's Login.php handling section. Confirmed
    # by direct reproduction: settling can take up to ~20s locally, well past
    # expect()'s 5s default. Applicant cards themselves are rendered
    # server-side synchronously (no AJAX, same doc) -- once this settles,
    # they're just there, not something to keep polling for separately.
    page.wait_for_load_state("networkidle")

    # Now logged in, the job page should render with applicant cards
    expect(page.locator(".applicants")).to_be_visible(timeout=30000)
    expect(page.locator("button.connect_with_tutor").first).to_be_visible()

    write_detail("test_logged_out_stage3_sees_login_modal", {
        "message": f"Logged-out user logged in via inline form and reached Stage 3 job {stage3_job['job_id']}",
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stripe return — modal auto-triggers on page load
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
@pytest.mark.critical
def test_stripe_return_auto_triggers_modal(
    page: Page, base_url: str, stage3_job
):
    """
    Navigating to a Stage 3 job with ?payment_method_added=true&from_stripe=true
    auto-triggers the connect modal without any click.
    Covers: 'Stripe-return flow — page load with payment_method_added=true&
    from_stripe=true auto-triggers modal without click'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(
        f"{base_url}{JOB_URL}{stage3_job['job_id']}/"
        f"?payment_method_added=true&from_stripe=true&tutor_id={stage3_job['tutor_id']}"
    )
    # Modal should open automatically — no button click required
    page.wait_for_selector(".modal.show, .dash_modal.show", timeout=15000)

    write_detail("test_stripe_return_auto_triggers_modal", {
        "message": (
            f"Stripe-return params auto-opened modal on job {stage3_job['job_id']}"
        ),
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 → Stage 4 — accept terms (MUST run last among Stage 3 tests:
# advances the shared stage3_job one-way to Stage 4)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
@pytest.mark.critical
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

    Covers: 'Accept terms advancing to Stage 4'.
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

    # Wait for any modal overlay to clear before checking the tutor section.
    page.wait_for_selector(".modal.show", state="hidden", timeout=5000)
    connected_section.scroll_into_view_if_needed()
    write_detail("test_accept_terms_advances_to_stage4", {
        "message": f"Job {stage3_job['job_id']} advanced to Stage 4 after accepting terms",
        "job_id": stage3_job["job_id"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Magic link — auto-login
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
@pytest.mark.critical
def test_magic_link_auto_login(page: Page, base_url: str, magic_link_params):
    """
    A magic link URL (/jobs/{id}/?job={crc32}&email={email}) logs the client in
    silently and redirects to the job page.
    Covers: 'Magic link auto-login — /jobs/{id}/?job={crc32}&email={email}
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

    write_detail("test_magic_link_auto_login", {
        "message": f"Magic link authenticated for job {job_id}",
        "job_id": job_id,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — client sees connected tutor
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.jobs
def test_client_stage4_job_shows_connected_tutor(
    page: Page, base_url: str, stage3_job
):
    """
    Logged-in client on a Stage 4 job sees the 'Your chosen tutor' section with
    connected tutor details.

    Uses the same dynamically created job/client as the Stage 3 tests. By the
    time this test runs, test_accept_terms_advances_to_stage4 has already
    advanced that job to Stage 4, so no permanent client account is needed.

    Covers: 'Logged-in client on Stage 4 job sees tutor selected dashboard state'.
    """
    _login(page, base_url, stage3_job["client_email"], stage3_job["client_password"])
    page.goto(f"{base_url}{JOB_URL}{stage3_job['job_id']}/", wait_until="domcontentloaded")

    connected_section = page.locator(
        "section[aria-label='Connected tutor information']"
    )
    expect(connected_section).to_be_visible()
    expect(connected_section.locator("h2")).to_contain_text("Your chosen tutor")

    write_detail("test_client_stage4_job_shows_connected_tutor", {
        "message": (
            f"Stage 4 job {stage3_job['job_id']} shows 'Your chosen tutor' section"
        ),
        "job_id": stage3_job["job_id"],
    })
