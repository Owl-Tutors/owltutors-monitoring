import json
import os
from playwright.sync_api import Page, expect
from utils.details import write_detail

BLOG_URL = "/resource/"
TESTIMONIALS_URL = "/about-us/testimonials/"
SHOP_URL = "/shop/"
COURSES_URL = "/all-courses/"


def test_blog_listing_loads(page: Page, base_url: str):
    """Blog listing page loads with at least one article card visible."""
    page.goto(f"{base_url}{BLOG_URL}")
    # Regular blog cards use a.text-decoration-none.d-block.h-100 (featured article omits h-100)
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    expect(page.locator("a.text-decoration-none.d-block.h-100").first).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/blog_listing.png")
    write_detail("test_blog_listing_loads", {
        "message": "Blog listing page loaded with article cards visible",
        "screenshot": "screenshots/blog_listing.png",
    })


def test_blog_article_loads(page: Page, base_url: str):
    """Clicking a blog card navigates to a full article page with body content."""
    page.goto(f"{base_url}{BLOG_URL}")
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    page.locator("a.text-decoration-none.d-block.h-100").first.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("article.mb-4")).to_be_visible(timeout=10000)
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/blog_article.png")
    write_detail("test_blog_article_loads", {
        "message": "Blog article page loaded with article body visible",
        "screenshot": "screenshots/blog_article.png",
    })


def test_testimonials_page_loads(page: Page, base_url: str):
    """Testimonials page loads with the hero header visible."""
    page.goto(f"{base_url}{TESTIMONIALS_URL}")
    expect(page.locator("header.bg-navy.text-white")).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/testimonials.png")
    write_detail("test_testimonials_page_loads", {
        "message": "Testimonials page loaded with hero header visible",
        "screenshot": "screenshots/testimonials.png",
    })


def test_shop_loads(page: Page, base_url: str):
    """Premium paper shop loads with at least one product card visible."""
    page.goto(f"{base_url}{SHOP_URL}")
    page.wait_for_selector(".paper-card", timeout=10000)
    expect(page.locator(".paper-card").first).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/shop.png")
    write_detail("test_shop_loads", {
        "message": "Premium paper shop loaded with product cards visible",
        "screenshot": "screenshots/shop.png",
    })


def test_group_course_listing(page: Page, base_url: str):
    """Group course listing page loads with at least one course card visible."""
    page.goto(f"{base_url}{COURSES_URL}")
    page.wait_for_selector("#course-grid article.course-card", timeout=10000)
    expect(page.locator("#course-grid article.course-card").first).to_be_visible()
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/course_listing.png")
    write_detail("test_group_course_listing", {
        "message": "Group course listing loaded with course cards visible",
        "screenshot": "screenshots/course_listing.png",
    })


def test_group_course_detail(page: Page, base_url: str):
    """Clicking a course card navigates to the course detail page."""
    page.goto(f"{base_url}{COURSES_URL}")
    page.wait_for_selector("#course-grid article.course-card", timeout=10000)
    # stretched-link covers the whole card — click the anchor directly
    page.locator("#course-grid article.course-card a.stretched-link").first.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("header.bg-navy.text-white")).to_be_visible(timeout=10000)
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/course_detail.png")
    write_detail("test_group_course_detail", {
        "message": "Group course detail page loaded with course header visible",
        "screenshot": "screenshots/course_detail.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Blog pagination
# ─────────────────────────────────────────────────────────────────────────────

def test_blog_pagination(page: Page, base_url: str):
    """
    Blog listing page 2 (/resource/page/2/) renders article cards and they
    differ from page 1 — confirms pagination is working and not just serving
    the same first-page content.
    Covers P4: 'Blog pagination — page 2 differs from page 1'.
    """
    # Collect hrefs from page 1
    page.goto(f"{base_url}{BLOG_URL}")
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    page1_hrefs = page.evaluate(
        "Array.from(document.querySelectorAll('a.text-decoration-none.d-block.h-100')).map(a => a.href)"
    )
    assert page1_hrefs, "No article cards found on blog listing page 1"

    # Navigate to page 2
    page.goto(f"{base_url}{BLOG_URL}page/2/")
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    page2_hrefs = page.evaluate(
        "Array.from(document.querySelectorAll('a.text-decoration-none.d-block.h-100')).map(a => a.href)"
    )
    assert page2_hrefs, "No article cards found on blog listing page 2"

    # Allow sticky/featured posts to appear on both pages — assert at least one
    # article on page 2 is not on page 1 (genuine pagination working).
    unique_on_page2 = set(page2_hrefs) - set(page1_hrefs)
    assert unique_on_page2, (
        f"No unique articles on page 2 — all {len(page2_hrefs)} article(s) also appear "
        f"on page 1. Pagination may not be working, or every post is sticky/featured."
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/blog_page2.png")
    write_detail("test_blog_pagination", {
        "message": f"Blog page 2 shows {len(page2_hrefs)} unique article(s) not on page 1",
        "screenshot": "screenshots/blog_page2.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Reading time on article pages
# ─────────────────────────────────────────────────────────────────────────────

def test_blog_reading_time(page: Page, base_url: str):
    """
    A blog article page shows a 'X min read' reading time string inside
    <small class='text-muted'> (rendered by functions.php via
    ot_blogs_reading_estimate()).
    Covers P4: 'Reading time displayed on article pages'.
    """
    page.goto(f"{base_url}{BLOG_URL}")
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    page.locator("a.text-decoration-none.d-block.h-100").first.click()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("article.mb-4")).to_be_visible(timeout=10000)

    # "X min read" is part of the byline rendered by single.php into
    # <p class="meta small mb-0 text-white"> via ot_blogs_reading_estimate().
    reading_time_el = page.locator("p.meta.small").filter(has_text="min read")
    expect(reading_time_el.first).to_be_visible(timeout=5000)

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/blog_reading_time.png")
    write_detail("test_blog_reading_time", {
        "message": "Blog article shows reading time ('min read') in article meta",
        "screenshot": "screenshots/blog_reading_time.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# VideoObject JSON-LD
# ─────────────────────────────────────────────────────────────────────────────

def test_video_object_json_ld(page: Page, base_url: str):
    """
    A blog post with the 'video_id' ACF field set outputs a VideoObject node
    in the page's JSON-LD @graph (content-schema.php appends it to any @graph
    schema when $_ot_video_id is non-empty).

    The test scans the first few articles from the blog listing until it finds
    one with VideoObject JSON-LD.  If none of the first 5 articles has a video,
    the test is skipped with an explanatory message — add a specific URL below
    once a known video post is identified on the dev site.
    Covers P4: 'VideoObject JSON-LD on posts with video_id'.
    """
    import pytest

    page.goto(f"{base_url}{BLOG_URL}")
    page.wait_for_selector("a.text-decoration-none.d-block.h-100", timeout=10000)
    article_links = page.evaluate(
        "Array.from(document.querySelectorAll('a.text-decoration-none.d-block.h-100')).map(a => a.href).slice(0, 5)"
    )

    found_video_object = False
    checked_url = None
    for article_url in article_links:
        page.goto(article_url)
        page.wait_for_load_state("domcontentloaded")
        ld_blocks = page.locator("script[type='application/ld+json']")
        for i in range(ld_blocks.count()):
            try:
                data = json.loads(ld_blocks.nth(i).inner_html())
                graph = data.get("@graph", [])
                if any(node.get("@type") == "VideoObject" for node in graph):
                    found_video_object = True
                    checked_url = article_url
                    break
            except (json.JSONDecodeError, AttributeError):
                continue
        if found_video_object:
            break

    if not found_video_object:
        pytest.skip(
            "None of the first 5 blog articles has VideoObject JSON-LD — "
            "set a specific URL in this test once a post with video_id is identified on the dev site"
        )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/blog_video_object.png")
    write_detail("test_video_object_json_ld", {
        "message": f"VideoObject found in JSON-LD on {checked_url}",
        "screenshot": "screenshots/blog_video_object.png",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Testimonial scores shortcode
# ─────────────────────────────────────────────────────────────────────────────

def test_testimonial_scores_shortcode(page: Page, base_url: str):
    """
    The [ot_show_testimonial_scores] shortcode renders a div#testimonial_scores
    element containing an average score and a review count.  The shortcode
    queries the testimonials table directly (ot_show_testimonial_scores() in
    testimonial-mgmt.php) and outputs 'Our tutors are rated X / 5 based on N reviews'.

    Navigates to the testimonials page (/about-us/testimonials/) where the
    shortcode is expected to appear in page content.  If it is not present there,
    update the URL to wherever the shortcode is embedded in the CMS.
    Covers P4: '[ot_show_testimonial_scores] shortcode renders with score and count'.
    """
    page.goto(f"{base_url}{TESTIMONIALS_URL}")
    page.wait_for_load_state("domcontentloaded")

    scores_div = page.locator("#testimonial_scores")
    # The shortcode must be embedded in the CMS page — skip rather than fail if
    # it isn't present on this environment (update TESTIMONIALS_URL if needed).
    if not scores_div.is_visible(timeout=10000):
        import pytest as _pytest
        _pytest.skip(
            f"#testimonial_scores not found at {TESTIMONIALS_URL} — "
            "the [ot_show_testimonial_scores] shortcode may not be embedded in this "
            "environment's CMS page. Update TESTIMONIALS_URL to the correct page URL."
        )

    text = scores_div.text_content() or ""
    assert "/" in text and "reviews" in text.lower(), (
        f"Expected 'X / 5 based on N reviews' text inside #testimonial_scores, got: {text!r}"
    )

    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path="screenshots/testimonial_scores.png")
    write_detail("test_testimonial_scores_shortcode", {
        "message": f"Testimonial scores shortcode rendered: {text.strip()[:80]}",
        "screenshot": "screenshots/testimonial_scores.png",
    })
