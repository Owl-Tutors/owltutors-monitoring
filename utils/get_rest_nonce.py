from playwright.sync_api import Page


def get_rest_nonce(page: Page, base_url: str, api_key: str) -> str:
    """
    Call owl_get_rest_nonce (via the browser's own authenticated cookie
    session — page.request carries whatever cookies the page currently has)
    to get a valid wp_rest nonce for the currently logged-in user.

    Required for any page.request call against a core WP REST API route
    (e.g. /wp-json/main/v1/ot_data_endpoint) made *as* a logged-in user:
    WordPress's cookie-auth REST check (rest_cookie_check_errors()) ignores
    the login cookie entirely without an X-WP-Nonce header, so
    current_user_can() inside the route's permission_callback would
    otherwise evaluate as if nobody were logged in — even with a perfectly
    valid session. Not needed for admin-ajax.php calls (a separate nonce
    system, check_ajax_referer(), used only where a callback explicitly
    calls it).
    """
    resp = page.request.post(
        f"{base_url}/wp-admin/admin-ajax.php",
        form={"action": "owl_get_rest_nonce", "api_key": api_key},
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"owl_get_rest_nonce failed: {data}")
    if not data.get("logged_in"):
        raise RuntimeError(
            "owl_get_rest_nonce succeeded but logged_in=False — the page's "
            "browser context has no authenticated session"
        )
    return data["nonce"]
