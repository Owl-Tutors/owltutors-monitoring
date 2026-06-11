import base64
import os
import re
import uuid as _uuid
import pytest
from playwright.sync_api import Browser


_LIVE_DOMAIN   = "owltutors.co.uk"
_ALLOW_LIVE_ENV = "OWL_TEST_ALLOW_LIVE"


@pytest.fixture(scope="session")
def base_url():
    raw = os.environ["TEST_BASE_URL"]
    # Hard block: prevent accidental form-submission tests against production.
    # The PHP dev gate lets form submissions through on live (jobs/users are created for real)
    # but silently skips test-flagging and rejects cleanup — leaving real data behind.
    # Set OWL_TEST_ALLOW_LIVE=1 only when running read-only tests (e.g. GA4) against live.
    if _LIVE_DOMAIN in raw and not os.environ.get(_ALLOW_LIVE_ENV):
        raise RuntimeError(
            f"\n\n*** SAFETY BLOCK — production site detected ***\n"
            f"TEST_BASE_URL contains '{_LIVE_DOMAIN}'.\n"
            f"Form-submission tests create real jobs and user accounts on production;\n"
            f"the PHP cleanup endpoint is dev-only so they cannot be deleted.\n\n"
            f"To run READ-ONLY tests against the live site (e.g. GA4 checks only):\n"
            f"  set {_ALLOW_LIVE_ENV}=1 and pass -k 'ga4' to restrict to those tests.\n"
            f"Never run the full suite against the live site.\n"
        )
    # Strip user:pass@ from the URL. Embedding credentials in the navigation URL
    # causes Chrome to include them when resolving relative paths, so fetch('/wp-admin/admin-ajax.php')
    # resolves to https://user:pass@host/... and Chrome refuses to construct the Request.
    # Auth is handled separately by http_credentials + inject_basic_auth.
    return re.sub(r"(https?://)[^:@]+:[^@]+@", r"\1", raw)


def _basic_auth_token() -> str | None:
    """Return a Basic Auth token, or None if no credentials are configured.
    Prefers TEST_HTTP_USER/TEST_HTTP_PASS over URL-embedded credentials to
    avoid regex breakage when the password contains special characters like '@'.
    """
    user = os.environ.get("TEST_HTTP_USER", "")
    pw   = os.environ.get("TEST_HTTP_PASS", "")
    if user and pw:
        return base64.b64encode(f"{user}:{pw}".encode()).decode()
    raw = os.environ.get("TEST_BASE_URL", "")
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        return base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
    return None


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Supply http_credentials so Playwright can respond to any 401 challenges."""
    user = os.environ.get("TEST_HTTP_USER", "")
    pw   = os.environ.get("TEST_HTTP_PASS", "")
    if not (user and pw):
        raw = os.environ.get("TEST_BASE_URL", "")
        match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
        if match:
            user, pw = match.group(1), match.group(2)
    if user and pw:
        return {**browser_context_args, "http_credentials": {"username": user, "password": pw}}
    return browser_context_args


@pytest.fixture(autouse=True)
def inject_basic_auth(page):
    """Intercept every request from the page and add the Authorization header.

    http_credentials alone is insufficient: WP Engine password protection can
    block JS-initiated XHR/fetch calls before issuing a 401 challenge, so the
    browser never gets a chance to retry with credentials. page.route() fires
    before the request leaves the browser and injects the header proactively,
    covering admin-ajax.php AJAX calls as well as normal navigations."""
    token = _basic_auth_token()
    if token:
        auth_header = f"Basic {token}"
        page.route(
            "**/*",
            lambda route: route.continue_(
                headers={**route.request.headers, "Authorization": auth_header}
            ),
        )

@pytest.fixture(autouse=True)
def log_ajax(page, request):
    """Comprehensive network + JS diagnostics for every test.

    Captures:
    - admin-ajax.php responses (status + body)
    - admin-ajax.php requests that fail/abort before getting a response
    - all browser console messages (all levels)
    - unhandled JS page errors
    - a DOM snapshot after the test (ajaxurl value + key element presence)
    """
    responses = []
    failed_requests = []
    console_msgs = []
    page_errors = []

    def on_response(response):
        if "admin-ajax.php" in response.url:
            try:
                body = response.text()
            except Exception:
                body = "<unreadable>"
            responses.append(f"  [response {response.status}] {response.url} -> {body[:300]}")

    def on_requestfailed(req):
        if "admin-ajax.php" in req.url:
            failed_requests.append(f"  [FAILED] {req.url} — {req.failure}")

    page.on("response", on_response)
    page.on("requestfailed", on_requestfailed)
    page.on("console", lambda msg: console_msgs.append(f"  [console:{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: page_errors.append(f"  [pageerror] {err}"))

    yield

    # DOM snapshot — only meaningful if page navigated somewhere
    dom = {}
    try:
        dom = page.evaluate("""() => ({
            ajaxurl:      window.ajaxurl || null,
            formEl:       !!document.getElementById('tutorSearchForm'),
            resultsEl:    !!document.getElementById('tutor_results'),
            listingsCheck:!!document.getElementById('tutor-listings-page'),
            url:          window.location.href,
        })""")
    except Exception:
        pass

    lines = responses + failed_requests
    if lines or page_errors or dom:
        print(f"\n[diag: {request.node.name}]")
        for line in lines:
            print(line)
        for line in page_errors:
            print(line)
        if dom:
            print(f"  [dom] {dom}")
    # Always print console — filter to errors/warnings to keep output manageable
    for msg in console_msgs:
        if any(t in msg for t in ("[console:error]", "[console:warning]")):
            print(msg)


@pytest.fixture
def returning_client_login(page, base_url):
    """
    Submits the contact form once as a fresh UUID-email client, leaving the
    browser logged in via the auto-login ?new_client=true redirect.
    Because this fixture shares the same function-scoped `page` as the test
    that requests it, subsequent gotos in the test run as the authenticated
    client — no password or magic link needed.
    Both the setup job and any test job are flagged _ot_test_post=1 for cleanup.

    The PHP auto-login (wp_set_auth_cookie inside window.location.href redirect)
    may not propagate the cookie reliably in all environments. If the auto-login
    didn't take, the fixture falls back to the ot_test_force_login endpoint
    (job-mgmt.php) which sets the cookie via a normal HTTP redirect.
    """
    import urllib.parse

    fresh_email = f"testbot.client.{_uuid.uuid4().hex[:8]}@owltutors.co.uk"

    page.goto(f"{base_url}/contact-us/", wait_until="domcontentloaded")
    page.locator("select[name='acf[field_64997c72bef9f]']").select_option(
        label="A tutor to provide tuition services"
    )
    # Wait for Maths specifically — the first DOM checkbox is "7 Plus" which is
    # hidden below the fold, so waiting for the generic selector times out.
    page.wait_for_selector(
        "div[data-name='subject_list'] input[type='checkbox'][value='Maths']",
        timeout=15000,
    )
    page.locator(
        "div[data-name='subject_list'] input[type='checkbox'][value='Maths']"
    ).check()
    page.locator("div[data-name='tuition_requirements_original'] textarea").fill(
        "Setup submission for client login test — automated"
    )
    page.locator("div[data-name='timing_details_-_original'] textarea").fill("Flexible")
    page.locator("input[name='acf[field_5edf8887fb5e7]']").fill("Owl")
    page.locator("input[name='acf[field_5edf8899fb5e8]']").fill("TestBot")
    page.locator("input[name='acf[field_5edf889ffb5e9]']").fill(fresh_email)
    page.locator("input[name='acf[field_5a573454bb670]']").fill("07700900000")
    page.locator(
        "div[data-name='i_confirm_there_are_no_health_and_safety_issues'] input[type='checkbox']"
    ).check()
    _key = os.environ.get("OWL_TEST_API_KEY", "")
    page.evaluate(
        """(k) => {
            document.getElementById('ot_test_post').value = '1';
            var i = document.createElement('input');
            i.type = 'hidden'; i.name = 'ot_test_api_key'; i.value = k;
            document.getElementById('tutor_request_form').appendChild(i);
        }""",
        _key,
    )
    page.locator("#contact_form_submit").click()
    page.wait_for_url(re.compile(r".*/jobs/"), timeout=90000)
    page.wait_for_load_state("domcontentloaded")

    # Verify the auto-login cookie was set. If not (e.g. returning_client path,
    # or the window.location.href Set-Cookie didn't propagate in this environment),
    # fall back to the ot_test_force_login endpoint which sets the cookie via a
    # normal wp_safe_redirect so the browser stores it reliably.
    if page.locator("a[href*='logout'], a[href*='log-out']").count() == 0:
        force_url = (
            f"{base_url}/?ot_test_force_login=1"
            f"&email={urllib.parse.quote(fresh_email)}"
            f"&key={urllib.parse.quote(_key)}"
        )
        page.goto(force_url, wait_until="domcontentloaded")
        page.wait_for_selector(
            "a[href*='logout'], a[href*='log-out']",
            timeout=10000,
        )

    yield {"email": fresh_email}


@pytest.fixture(scope="session")
def client_credentials():
    return {
        "email": os.environ["TEST_CLIENT_EMAIL"],
        "password": os.environ["TEST_CLIENT_PASSWORD"],
    }

@pytest.fixture(scope="session")
def api_key():
    return os.environ.get("OWL_TEST_API_KEY", "")

@pytest.fixture(scope="session")
def tutor_ids():
    """Pipe-separated WP user IDs of test tutors on the dev site (e.g. '123|456').
    Tests using this fixture are skipped when the env var is not set."""
    raw = os.environ.get("TEST_TUTOR_IDS", "")
    if not raw:
        pytest.skip("TEST_TUTOR_IDS not configured — skipping requested-tutors test")
    return [int(x.strip()) for x in raw.split("|") if x.strip().isdigit()]


def _new_authed_page(browser: Browser):
    """Create an independent browser context + page with Basic Auth injected.
    Used by session fixtures that need two simultaneous logged-in users
    (e.g. client creating a job while tutor applies in a separate window).
    Mirrors the auth setup in browser_context_args / inject_basic_auth."""
    raw = os.environ.get("TEST_BASE_URL", "")
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    ctx_args = {}
    token = None
    if match:
        ctx_args["http_credentials"] = {
            "username": match.group(1),
            "password": match.group(2),
        }
        token = base64.b64encode(
            f"{match.group(1)}:{match.group(2)}".encode()
        ).decode()
    ctx = browser.new_context(**ctx_args)
    page = ctx.new_page()
    if token:
        auth_header = f"Basic {token}"
        page.route(
            "**/*",
            lambda route: route.continue_(
                headers={**route.request.headers, "Authorization": auth_header}
            ),
        )
    return ctx, page


@pytest.fixture(scope="session")
def tutor_credentials():
    """Login credentials for the test tutor (same person as TEST_MEET_NOW_TUTOR_ID).
    Needed for the real end-to-end Stage 3 flow: the tutor logs in and applies
    via the job URL so the applicant card is genuinely present.
    Set TEST_TUTOR_EMAIL and TEST_TUTOR_PASSWORD."""
    email    = os.environ.get("TEST_TUTOR_EMAIL", "")
    password = os.environ.get("TEST_TUTOR_PASSWORD", "")
    if not (email and password):
        pytest.skip(
            "TEST_TUTOR_EMAIL/PASSWORD not set — skipping Stage 3 end-to-end tests"
        )
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def applicant_credentials():
    """Login credentials for a permanent applicant account on the dev site.
    Required for applicant form section tests (profile text, profile photo).
    Set TEST_APPLICANT_EMAIL and TEST_APPLICANT_PASSWORD in .env / GitHub Secrets."""
    email    = os.environ.get("TEST_APPLICANT_EMAIL", "")
    password = os.environ.get("TEST_APPLICANT_PASSWORD", "")
    if not (email and password):
        pytest.skip(
            "TEST_APPLICANT_EMAIL/PASSWORD not set — skipping applicant form section tests"
        )
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def meet_now_tutor_id():
    """WP user ID of a test tutor configured for meet-now:
    auto_swap_active=true, include_tutor_in_auto_swap=true, online delivery,
    availability outcome 1b.
    This ID is also used as the applicant in dynamically created Stage 3/4 test jobs.
    Set TEST_MEET_NOW_TUTOR_ID."""
    val = os.environ.get("TEST_MEET_NOW_TUTOR_ID", "")
    if not val:
        pytest.skip("TEST_MEET_NOW_TUTOR_ID not set — skipping meet-now and Stage 3/4 tests")
    return val


@pytest.fixture(scope="session")
def stage3_job(
    browser, base_url, api_key,
    tutor_credentials, meet_now_tutor_id,
):
    """Creates a Stage 3 test job via the realistic end-to-end flow.

    1. A logged-OUT client submits the contact form using a freshly generated
       UUID email, creating a brand-new WP account (client_created_job_no_pw_login=true,
       _ot_test_user=1). The job lands on 'Stage 2 - Ready no tutors'.
    2. The test tutor logs in in a separate browser context and submits the
       two-step application form.
    3. owl_advance_test_job marks the applicant as forwarded and sets Stage 3.
    4. The magic link is used once in a setup page to auto-login the new client
       and complete the #passwordModal set-password step, establishing a known
       password. Tests then use _login() with client_email + client_password.

    Yields a dict: {"job_id": str, "client_email": str, "client_password": str}.
    """
    import re as _re
    import uuid as _uuid
    import binascii
    from utils.advance_job import advance_test_job

    LOGIN_URL = "/login/"
    CLIENT_PASSWORD = "Owl1Tutor!Test2026"
    client_email = f"testbot.stage3.{_uuid.uuid4().hex[:8]}@owltutors.co.uk"

    # ── Step 1: logged-out client submits contact form ────────────────────
    client_ctx, client_page = _new_authed_page(browser)

    client_page.goto(f"{base_url}/contact-us/")
    client_page.locator("select[name='acf[field_64997c72bef9f]']").select_option(
        label="A tutor to provide tuition services"
    )
    client_page.wait_for_selector(
        "div[data-name='subject_list'] input[type='checkbox']", timeout=10000
    )

    # Japanese — may be below the fold
    japanese_cb = client_page.locator(
        "div[data-name='subject_list'] input[type='checkbox'][value='Japanese']"
    )
    if not japanese_cb.is_visible():
        client_page.locator(".below-fold-divider").click()
    japanese_cb.check()

    # IB Standard Level
    level_cb = client_page.locator(
        "div[data-name='japanese_level'] input[type='checkbox'][value='IB Standard Level']"
    )
    level_cb.wait_for(state="visible", timeout=5000)
    level_cb.check()

    # Online delivery
    client_page.locator(
        "div[data-name='tuition_delivery'] input[type='checkbox'][value='Online']"
    ).check()

    client_page.locator(
        "div[data-name='tuition_requirements_original'] textarea"
    ).fill("Test requirements for automated end-to-end monitoring test -- Japanese IB")
    client_page.locator(
        "div[data-name='timing_details_-_original'] textarea"
    ).fill("Flexible timing")

    # Personal info — generated email creates a fresh account
    client_page.locator("input[name='acf[field_5edf8887fb5e7]']").fill("Owl")
    client_page.locator("input[name='acf[field_5edf8899fb5e8]']").fill("TestBot")
    client_page.locator("input[name='acf[field_5edf889ffb5e9]']").fill(client_email)
    client_page.locator("input[name='acf[field_5a573454bb670]']").fill("07700900000")
    client_page.locator(
        "div[data-name='i_confirm_there_are_no_health_and_safety_issues'] input[type='checkbox']"
    ).check()

    # Inject ot_test_post flag (suppresses emails, flags job and user for cleanup)
    client_page.evaluate(
        """(k) => {
            document.getElementById('ot_test_post').value = '1';
            const i = document.createElement('input');
            i.type = 'hidden'; i.name = 'ot_test_api_key'; i.value = k;
            document.getElementById('tutor_request_form').appendChild(i);
        }""",
        os.environ.get("OWL_TEST_API_KEY", ""),
    )

    client_page.locator("#contact_form_submit").click()
    client_page.wait_for_url(_re.compile(r".*/jobs/"), timeout=90000)
    job_id = _re.search(r"/jobs/(\d+)/", client_page.url).group(1)
    print(f"\n[stage3_job] job created: {job_id} (client: {client_email})")
    client_ctx.close()

    # ── Step 2: tutor logs in and applies in a separate context ───────────
    tutor_ctx, tutor_page = _new_authed_page(browser)

    tutor_page.goto(f"{base_url}{LOGIN_URL}")
    tutor_page.wait_for_selector("#ot_login")
    tutor_page.wait_for_load_state("domcontentloaded")
    tutor_page.locator("#ot_login_name").fill(tutor_credentials["email"])
    tutor_page.locator("#pw1").fill(tutor_credentials["password"])
    tutor_page.locator("#login_submit").click()
    tutor_page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=90000)

    tutor_page.goto(f"{base_url}/jobs/{job_id}/")

    tutor_page.locator("p.applyforrole a").click()
    tutor_page.wait_for_selector("div.app_form_wrapper", state="visible", timeout=10000)

    tutor_page.locator("textarea#stage2_why_am_i_suitable").fill(
        "Experienced Japanese IB tutor. Automated test application."
    )
    tutor_page.locator("select#stage2_delivery").select_option("Online")

    # Step 1: review — POSTs form, PHP re-renders review page
    tutor_page.locator("input.tutor_job_app_form_presubmit").click(timeout=90000)
    tutor_page.wait_for_load_state("domcontentloaded", timeout=30000)

    # Step 2: submit — checkbox must change to trigger the JS enable handler
    agree = tutor_page.locator("input#agree_terms")
    if agree.count() > 0:
        if not agree.is_checked():
            agree.check()
        else:
            agree.uncheck()
            agree.check()

    submit = tutor_page.locator("input.tutor_job_app_form_submit")
    submit.wait_for(state="visible", timeout=10000)
    submit.click(timeout=90000)
    tutor_page.wait_for_load_state("domcontentloaded", timeout=30000)
    tutor_ctx.close()
    print(f"\n[stage3_job] tutor applied to job {job_id}")

    # ── Step 3: advance to Stage 3 via monitoring endpoint ────────────────
    advance_test_job(base_url, api_key, job_id, meet_now_tutor_id)
    print(f"\n[stage3_job] job {job_id} advanced to Stage 3")

    # ── Step 4: use the connect button to set a known password ───────────
    # The wp_login action hook (owltheme/functions.php) fires during job creation
    # auto-login and sets last_login immediately, so the magic link skips
    # auto-login and renders the informational Stage 3 view instead. That view
    # still shows the "Connect with tutor" button; clicking it fires
    # ot_job_identify_modal which returns the set-password form because
    # using_default_pw=true on the fresh client. Fill it here to establish
    # known credentials that tests can then use with _login().
    crc32_val = binascii.crc32(str(job_id).encode()) & 0xffffffff
    magic_link_url = f"{base_url}/jobs/{job_id}/?job={crc32_val}&email={client_email}"

    setup_ctx, setup_page = _new_authed_page(browser)
    setup_page.goto(magic_link_url)
    setup_page.wait_for_selector("button.connect_with_tutor", timeout=15000)
    setup_page.locator("button.connect_with_tutor").first.click()
    setup_page.wait_for_selector("#passwordModal.show, .dash_modal.show", timeout=15000)
    setup_page.locator("#inlinepassword").fill(CLIENT_PASSWORD)
    setup_page.locator("#passwordModal button[type='submit']").click()
    setup_page.wait_for_url(lambda url: "client_set_pw=true" in url, timeout=30000)
    setup_ctx.close()
    print(f"\n[stage3_job] password set for {client_email}")

    # ── Step 5: set client_status=Active ──────────────────────────────────
    # New clients are Inactive by default. Active status causes
    # ot_job_identify_modal to return the accept-terms form rather than the
    # add-payment-method form, enabling the full Stage 4 connect flow.
    import requests as _requests
    token = _basic_auth_token()
    _headers = {"User-Agent": "Mozilla/5.0 (compatible; owltutors-monitoring/1.0)"}
    if token:
        _headers["Authorization"] = f"Basic {token}"
    _resp = _requests.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        data={"action": "owl_set_client_active", "api_key": api_key, "email": client_email},
        headers=_headers,
        timeout=15,
    )
    _resp.raise_for_status()
    import json as _json
    _data = _json.loads(_resp.content.decode("utf-8-sig"))
    if not _data.get("success"):
        raise RuntimeError(f"owl_set_client_active failed: {_data}")
    print(f"\n[stage3_job] client {client_email} set to Active")

    yield {"job_id": job_id, "client_email": client_email, "client_password": CLIENT_PASSWORD, "tutor_id": meet_now_tutor_id}


@pytest.fixture(scope="session")
def stage4_job_id(base_url, api_key, meet_now_tutor_id, client_credentials):
    """Dynamically creates a Stage 4 test job via the owl_create_test_job endpoint.

    Same tutor and client as stage3_job_id.  Creates an independent job so
    Stage 3 and Stage 4 tests can run in parallel without interference."""
    from utils.create_test_job import create_test_job
    result = create_test_job(
        base_url=base_url,
        api_key=api_key,
        stage=4,
        tutor_id=meet_now_tutor_id,
        client_email=client_credentials["email"],
    )
    return result["job_id"]


@pytest.fixture(scope="session")
def magic_link_params(base_url, api_key, meet_now_tutor_id):
    """Dynamically creates a Stage 3 test job with an auto-generated never-logged-in
    test client, then computes the magic link params in Python.

    The magic link formula (from single-jobs.php) is:
        ?job=crc32(job_id)&email={client_email}
    Python equivalent: binascii.crc32(str(job_id).encode()) & 0xffffffff

    The fresh client is flagged _ot_test_user=1 (cleanup endpoint deletes them).
    No TEST_MAGIC_LINK_* env vars needed — fully self-contained."""
    import binascii
    from utils.create_test_job import create_test_job
    # Pass empty client_email so the endpoint auto-creates a never-logged-in client
    result = create_test_job(
        base_url=base_url,
        api_key=api_key,
        stage=3,
        tutor_id=meet_now_tutor_id,
        client_email="",
    )
    job_id       = result["job_id"]
    client_email = result["client_email"]
    crc32_val    = binascii.crc32(str(job_id).encode()) & 0xffffffff
    return {"job_id": job_id, "crc32": str(crc32_val), "email": client_email}


@pytest.fixture(scope="session")
def preapplicant_credentials(browser, base_url, api_key):
    """Create a fresh pre-applicant for this test session via the registration form.

    Does NOT set _ot_test_user=1. This is a session fixture — flagging the user
    would cause cleanup_after (used by per-test fixtures like test_tutor_registration_submits)
    to delete the account mid-session, breaking all tests that depend on this fixture.
    UUID-based emails accumulate on the dev site; clean up old testbot.preapp.* accounts
    manually via WP admin when needed.
    No TEST_PREAPPLICANT_EMAIL/PASSWORD env vars required.
    """
    import uuid as _uuid

    APPLICATION_URL = "/tutor-section/application/"
    email    = f"testbot.preapp.{_uuid.uuid4().hex[:8]}@owltutors.co.uk"
    password = "Owl1Tutor!Test2026"

    ctx, reg_page = _new_authed_page(browser)
    reg_page.goto(f"{base_url}{APPLICATION_URL}")
    reg_page.wait_for_selector("#signupform", state="visible", timeout=10000)
    reg_page.locator("#email").fill(email)
    reg_page.locator("#pw1").fill(password)
    reg_page.evaluate("document.getElementById('signupform').submit()")
    reg_page.wait_for_url(re.compile(r".*/tutor-section/application/"), timeout=30000)
    assert "register-errors" not in reg_page.url, (
        f"preapplicant_credentials: registration failed — {reg_page.url}"
    )
    ctx.close()

    yield {"email": email, "password": password}
