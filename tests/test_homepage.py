from playwright.sync_api import Page, expect
from utils.details import write_detail
import pytest


@pytest.mark.content
def test_homepage_loads(page: Page, base_url: str, step):
    """Homepage loads and the hero section is visible."""
    page.goto(f"{base_url}/")
    with step("checking hero section visibility"):
        expect(page.locator(".tutor-hero--homepage")).to_be_visible()
    write_detail("test_homepage_loads", {
        "message": "Homepage loaded with hero section visible",
    })
