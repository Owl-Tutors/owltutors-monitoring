from playwright.sync_api import Page, expect
from utils.details import write_detail
import pytest

LOGIN_URL   = "/login/"
DASHBOARD_URL = "/dashboard/"


def _login(page: Page, base_url: str, email: str, password: str):
    """Fill and submit the login form, wait for redirect away from /login/."""
    page.goto(f"{base_url}{LOGIN_URL}")
    expect(page.locator("#ot_login")).to_be_visible()
    page.wait_for_load_state("networkidle")
    page.locator("#ot_login_name").fill(email)
    page.locator("#pw1").fill(password)
    page.locator("#login_submit").click()
    page.wait_for_url(lambda url: "/login/" not in url, timeout=30000)


@pytest.mark.auth
@pytest.mark.critical
def test_client_login(page: Page, base_url: str, client_credentials):
    """Valid credentials are accepted and the client lands on the dashboard."""
    _login(page, base_url, client_credentials["email"], client_credentials["password"])
    expect(page.locator("#client-dashboard-page")).to_be_visible()
    write_detail("test_client_login", {
        "message": "Login accepted, client landed on dashboard",
    })


@pytest.mark.auth
def test_client_dashboard(page: Page, base_url: str, client_credentials):
    """Client dashboard loads with the main sections visible."""
    _login(page, base_url, client_credentials["email"], client_credentials["password"])
    page.goto(f"{base_url}{DASHBOARD_URL}")
    expect(page.locator("#client-dashboard-page")).to_be_visible()
    expect(page.locator("#dashboard-tutors-heading")).to_be_visible()
    expect(page.locator("#dashboard-billing-heading")).to_be_visible()
    write_detail("test_client_dashboard", {
        "message": "Clients can log in and see the dashboard",
    })
