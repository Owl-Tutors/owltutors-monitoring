import re

from playwright.sync_api import Page


def complete_native_wc_checkout(page: Page, base_url: str, email: str) -> str:
    """
    Completes a real WooCommerce Blocks checkout (the site's actual checkout
    page, confirmed 2 Sept 2026 to run the Blocks/React checkout rather than
    the classic shortcode one -- see docs/woocommerce.md) using Stripe's test
    card 4242 4242 4242 4242 via the Stripe Payment Element.

    Payment renders inside an iframe with a stable title ("Secure payment
    input frame") but a dynamically-generated name/id that changes every
    page load -- targets by title, not name, for that reason.

    A logged-in user with an existing saved billing address (e.g. the test
    tutor) gets a collapsed read-only address summary instead of the open
    editable form a guest sees -- found while writing the DBS checkout test
    (only guests were exercised until then). Billing fields are only filled
    when they're actually visible; a collapsed summary means WC already has
    a usable address on file, so there's nothing to fill.

    Placing the order takes noticeably longer than a typical form submit
    (Stripe payment confirmation + WC order processing) -- a short wait
    after the click reads as "stuck" when it's actually still working, so
    this waits up to 30s for the real order-received redirect.

    Returns the created order ID (parsed from the /checkout/order-received/{id}/ URL).
    """
    page.goto(f"{base_url}/checkout/", wait_until="domcontentloaded")
    try:
        page.locator("#ot_local_storage_accept").click(timeout=3000)
    except Exception:
        pass
    page.wait_for_timeout(3000)  # Blocks checkout hydrates + Stripe Elements mount asynchronously

    email_field = page.locator("#email")
    if email_field.count() and email_field.is_visible():
        email_field.fill(email)

    first_name = page.locator("#billing-first_name")
    if first_name.count() and first_name.is_visible():
        first_name.fill("Owl")
        page.locator("#billing-last_name").fill("TestBot")
        for sel, val in [
            ("#billing-address_1", "1 Test Street"),
            ("#billing-city", "London"),
            ("#billing-postcode", "SW1A 1AA"),
        ]:
            loc = page.locator(sel)
            if loc.count():
                loc.fill(val)
    page.wait_for_timeout(2000)

    stripe_frame = page.frame_locator("iframe[title='Secure payment input frame']")
    stripe_frame.locator('[name="number"]').fill("4242424242424242")
    stripe_frame.locator('[name="expiry"]').fill("12/34")
    stripe_frame.locator('[name="cvc"]').fill("123")

    page.locator("button.wc-block-components-checkout-place-order-button").click()
    page.wait_for_url(lambda u: "order-received" in u, timeout=30000)

    match = re.search(r"order-received/(\d+)/", page.url)
    assert match, f"Expected an order ID in the order-received URL, got: {page.url}"
    return match.group(1)
