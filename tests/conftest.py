import base64
import os
import re
import pytest
from playwright.sync_api import Browser


@pytest.fixture(scope="session")
def base_url():
    raw = os.environ["TEST_BASE_URL"]
    # Strip user:pass@ from the URL. Embedding credentials in the navigation URL
    # causes Chrome to include them when resolving relative paths, so fetch('/wp-admin/admin-ajax.php')
    # resolves to https://user:pass@host/... and Chrome refuses to construct the Request.
    # Auth is handled separately by http_credentials + inject_basic_auth.
    return re.sub(r"(https?://)[^:@]+:[^@]+@", r"\1", raw)


def _basic_auth_token() -> str | None:
    """Return a Basic Auth token from TEST_BASE_URL credentials, or None."""
    raw = os.environ.get("TEST_BASE_URL", "")
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        return base64.b64encode(f"{match.group(1)}:{match.group(2)}".encode()).decode()
    return None


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Supply http_credentials so Playwright can respond to any 401 challenges."""
    raw = os.environ.get("TEST_BASE_URL", "")
    match = re.match(r"https?://([^:@]+):([^@]+)@", raw)
    if match:
        return {
            **browser_context_args,
            "http_credentials": {"username": match.group(1), "password": match.group(2)},
        }
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
            responses.append(f"  [response {response.status}] {response.url} → {body[:300]}")

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
def stage3_job_id(
    browser, base_url, api_key,
    client_credentials, tutor_credentials, meet_now_tutor_id,
):
    """
    Real end-to-end Stage 3 job — mirrors exactly how users actually use the site:

    1. Client logs in and submits the contact form (Japanese, IB Standard Level,
       Online delivery) with the ot_test_post flag so emails are suppressed.
    2. Tutor logs in in a separate browser context, navigates to the job URL,
       and submits the two-step application form.
    3. owl_advance_test_job marks the applicant as forwarded and sets Stage 3.

    The job carries _ot_test_post=1 and is cleaned up by the cleanup_after fixture
    in test_meet_now.py or test_recruitment.py (whichever runs last in the session).

    Requires: TEST_TUTOR_EMAIL, TEST_TUTOR_PASSWORD, TEST_MEET_NOW_TUTOR_ID,
              TEST_CLIENT_EMAIL, TEST_CLIENT_PASSWORD, OWL_TEST_API_KEY.
    """
    import re as _re
    from utils.advance_job import advance_test_job

    LOGIN_URL = "/login/"

    # ── Step 1: client creates job via contact form ────────────────────────
    client_ctx, client_page = _new_authed_page(browser)

    client_page.goto(f"{base_url}{LOGIN_URL}")
    client_page.wait_for_selector("#ot_login")
    client_page.wait_for_load_state("networkidle")
    client_page.locator("#ot_login_name").fill(client_credentials["email"])
    client_page.locator("#pw1").fill(client_credentials["password"])
    client_page.locator("#login_submit").click()
    client_page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=30000)

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
    ).fill("Test requirements for automated end-to-end monitoring test — Japanese IB")
    client_page.locator(
        "div[data-name='timing_details_-_original'] textarea"
    ).fill("Flexible timing")

    # Client info fields
    client_page.locator("input[name='acf[field_5edf8887fb5e7]']").fill("Owl")
    client_page.locator("input[name='acf[field_5edf8899fb5e8]']").fill("TestBot")
    client_page.locator("input[name='acf[field_5edf889ffb5e9]']").fill("testbot@owltutors.co.uk")
    client_page.locator("input[name='acf[field_5a573454bb670]']").fill("07700900000")
    client_page.locator(
        "div[data-name='i_confirm_there_are_no_health_and_safety_issues'] input[type='checkbox']"
    ).check()

    # Inject ot_test_post flag (suppresses emails, flags job for cleanup)
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
    print(f"\n[stage3_job_id] job created: {job_id}")

    # ── Step 2: tutor applies in a separate browser context ────────────────
    tutor_ctx, tutor_page = _new_authed_page(browser)

    tutor_page.goto(f"{base_url}{LOGIN_URL}")
    tutor_page.wait_for_selector("#ot_login")
    tutor_page.wait_for_load_state("networkidle")
    tutor_page.locator("#ot_login_name").fill(tutor_credentials["email"])
    tutor_page.locator("#pw1").fill(tutor_credentials["password"])
    tutor_page.locator("#login_submit").click()
    tutor_page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=30000)

    tutor_page.goto(f"{base_url}/jobs/{job_id}/")

    # Click "Apply to this job" — reveals the hidden form wrapper
    tutor_page.locator("p.applyforrole a").click()
    tutor_page.wait_for_selector("div.app_form_wrapper", state="visible", timeout=10000)

    # Fill the application form
    tutor_page.locator("textarea#stage2_why_am_i_suitable").fill(
        "Experienced Japanese IB tutor. Automated test application."
    )
    tutor_page.locator("select#stage2_delivery").select_option("Online")

    # Step 1 submit: "Review application" — POSTs form, PHP re-renders review page
    tutor_page.locator("input.tutor_job_app_form_presubmit").click()
    tutor_page.wait_for_load_state("networkidle", timeout=30000)

    # Step 2 submit: "Submit application" — on review page, enabled by #agree_terms
    # The checkbox starts checked by default; click it to trigger the JS enable handler
    agree = tutor_page.locator("input#agree_terms")
    if agree.count() > 0:
        if not agree.is_checked():
            agree.check()
        else:
            # Checkbox is already checked but the JS enable handler fires on change —
            # uncheck and recheck to guarantee the submit button is enabled
            agree.uncheck()
            agree.check()

    submit = tutor_page.locator("input.tutor_job_app_form_submit")
    submit.wait_for(state="visible", timeout=10000)
    submit.click()
    tutor_page.wait_for_load_state("networkidle", timeout=30000)
    tutor_ctx.close()
    print(f"\n[stage3_job_id] tutor applied to job {job_id}")

    # ── Step 3: advance to Stage 3 via monitoring endpoint ────────────────
    advance_test_job(base_url, api_key, job_id, meet_now_tutor_id)
    print(f"\n[stage3_job_id] job {job_id} advanced to Stage 3")

    yield job_id

    client_ctx.close()


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
def preapplicant_credentials():
    """Credentials for a permanent test pre-applicant account on the dev site.
    Set TEST_PREAPPLICANT_EMAIL and TEST_PREAPPLICANT_PASSWORD."""
    email    = os.environ.get("TEST_PREAPPLICANT_EMAIL", "")
    password = os.environ.get("TEST_PREAPPLICANT_PASSWORD", "")
    if not (email and password):
        pytest.skip(
            "TEST_PREAPPLICANT_EMAIL/PASSWORD not set — skipping pre-applicant tests"
        )
    return {"email": email, "password": password}
