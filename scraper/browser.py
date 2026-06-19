from playwright.sync_api import sync_playwright


def start_browser(headless=True):

    p = sync_playwright().start()

    browser = p.chromium.launch(
        headless=headless
    )

    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        java_script_enabled=True
    )

    page = context.new_page()

    return p, browser, page
