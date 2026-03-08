from patchright.sync_api import sync_playwright
import random


def open_browser(url="https://google.com"):
    """Launch a stealth Chromium browser using patchright (undetected Playwright fork)."""

    p = sync_playwright().start()

    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US,en",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
    )

    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")

    return page