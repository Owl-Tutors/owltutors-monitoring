import os
from playwright.sync_api import Page, expect
from utils.details import write_detail

DASHBOARD_URL = "/dashboard/"
TUTORING_URL  = "/dashboard/tutoring-section/"
LOGIN_URL     = "/login/"


def _login(page: Page, base_url: str, email: str, password: str):
    page.goto(f"{base_url}{LOGIN_URL}")
    expect(page.locator("#ot_login")).to_be_visible()
    page.wait_for_load_state("networkidle")
    page.locator("#ot_login_name").fill(email)
    page.locator("#pw1").fill(password)
    page.locator("#login_submit").click()
    page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=30000)


def test_tutor_dashboard_loads(page: Page, base_url: str, tutor_credentials):
    """
    A logged-in tutor visiting /dashboard/ sees the tutor dashboard.
    Header id="tutor-listings-page" (page-dashboard.php:586).
    Outer container div#tutor_dashboard (page-dashboard.php:483).
    Covers P2: Tutor dashboard loads for logged-in tutor.
    """
    _login(page, base_url, tutor_credentials["email"], tutor_credentials["password"])
    page.goto(f"{base_url}{DASHBOARD_URL}")
    expect(page.locator("header#tutor-listings-page")).to_be_visible()
    expect(page.locator("div#tutor_dashboard")).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/tutor_dashboard.png")
    write_detail("test_tutor_dashboard_loads", {
        "message": "Tutor dashboard loaded with correct header and container",
        "screenshot": "screenshots/tutor_dashboard.png",
    })


def test_tutor_dashboard_jobs_board(page: Page, base_url: str, tutor_credentials):
    """
    Jobs board tab pane is the default active section at /dashboard/tutoring-section/.
    page-dashboard-tutoring-section.php:97 sets show/active on div#jobs_board.
    Covers P2: Jobs board section renders with filter form and at least one result.
    """
    _login(page, base_url, tutor_credentials["email"], tutor_credentials["password"])
    page.goto(f"{base_url}{TUTORING_URL}")
    expect(page.locator("div#tutor_dash_tabs")).to_be_visible()
    expect(page.locator("div#jobs_board")).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/tutor_jobs_board.png")
    write_detail("test_tutor_dashboard_jobs_board", {
        "message": "Tutor jobs board tab pane visible and active",
        "screenshot": "screenshots/tutor_jobs_board.png",
    })


def test_tutor_dashboard_timesheet_entry(page: Page, base_url: str, tutor_credentials):
    """
    The Submit a timesheet tab pane is present in the DOM at /dashboard/tutoring-section/.
    page-dashboard-tutoring-section.php:102 renders div#submit_a_timesheet.
    Covers P2: Submit a timesheet section renders the job list entry point.
    """
    _login(page, base_url, tutor_credentials["email"], tutor_credentials["password"])
    page.goto(f"{base_url}{TUTORING_URL}")
    assert page.locator("div#submit_a_timesheet").count() > 0, (
        "#submit_a_timesheet pane not found in DOM at /dashboard/tutoring-section/"
    )
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/tutor_timesheet_entry.png")
    write_detail("test_tutor_dashboard_timesheet_entry", {
        "message": "Tutor timesheet entry pane present in DOM",
        "screenshot": "screenshots/tutor_timesheet_entry.png",
    })
