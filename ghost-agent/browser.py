"""Enhanced stealth browser for GhostAgent.

Built on Patchright (undetected Playwright fork) with:
- Static residential proxy integration
- GPS / geolocation spoofing
- Viewport randomization per session
- User-agent rotation
- Timezone + locale sync
"""

from patchright.sync_api import sync_playwright
import random
import os
import time

from config import (
    BROWSER_DATA_DIR,
    SCREENSHOT_DIR,
    VIEWPORT_BASE_WIDTH,
    VIEWPORT_BASE_HEIGHT,
    VIEWPORT_JITTER,
    USER_AGENTS,
    USER_TIMEZONE,
    USER_LATITUDE,
    USER_LONGITUDE,
    USER_LOCALE,
    get_proxy_url,
)


def open_browser(url="https://www.linkedin.com"):
    """Launch a stealth Chromium browser with full anti-detection config.

    Returns:
        tuple: (page, context, playwright) — caller must manage lifecycle.
    """
    p = sync_playwright().start()

    user_data_dir = os.path.join(os.getcwd(), BROWSER_DATA_DIR)
    os.makedirs(user_data_dir, exist_ok=True)

    # Randomize viewport dimensions slightly per session
    width = VIEWPORT_BASE_WIDTH + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
    height = VIEWPORT_BASE_HEIGHT + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)

    # Pick a random user agent
    user_agent = random.choice(USER_AGENTS)

    # Build launch options
    launch_args = {
        "user_data_dir": user_data_dir,
        "headless": False,
        "viewport": {"width": width, "height": height},
        "user_agent": user_agent,
        "locale": USER_LOCALE,
        "timezone_id": USER_TIMEZONE,
        "args": [
            "--disable-blink-features=AutomationControlled",
            f"--lang={USER_LOCALE}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-popup-blocking",
        ],
        "permissions": ["geolocation"],
        "geolocation": {
            "latitude": USER_LATITUDE,
            "longitude": USER_LONGITUDE,
        },
    }

    # Add proxy if configured
    proxy_url = get_proxy_url()
    if proxy_url:
        launch_args["proxy"] = {"server": proxy_url}

    context = p.chromium.launch_persistent_context(**launch_args)

    # Set geolocation permissions
    context.grant_permissions(["geolocation"])

    page = context.pages[0] if context.pages else context.new_page()

    # Inject mouse position tracking for Bézier curves
    page.evaluate("""() => {
        document.addEventListener('mousemove', (e) => {
            window._mouseX = e.clientX;
            window._mouseY = e.clientY;
        });
    }""")

    page.goto(url, wait_until="domcontentloaded")

    return page, context, p


def take_screenshot(page, path=None):
    """Take a screenshot of the visible viewport.

    Args:
        page: Playwright page instance.
        path: File path for the screenshot. Defaults to SCREENSHOT_DIR/screenshot.png.

    Returns:
        str: Absolute path to the saved screenshot.
    """
    if path is None:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOT_DIR, "screenshot.png")
    else:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    page.screenshot(path=path, full_page=False)
    return path


def wait_for_stable(page, timeout=5000):
    """Wait for the page to become stable (network idle + DOM settle).

    Uses a two-phase approach:
    1. Wait for network idle (or timeout gracefully)
    2. Brief additional wait for JS rendering
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # Network didn't go idle (long-polling, websockets) — just wait briefly
        time.sleep(1.5)

    # Brief additional wait for any JS rendering to complete
    time.sleep(random.uniform(0.3, 0.8))


def get_current_url(page):
    """Get the current page URL."""
    return page.evaluate("() => window.location.href")


def get_page_title(page):
    """Get the current page title."""
    return page.evaluate("() => document.title")


def is_linkedin(page):
    """Check if the current page is on LinkedIn."""
    url = get_current_url(page)
    return "linkedin.com" in url


def close_browser(context, playwright):
    """Gracefully close the browser and cleanup."""
    try:
        context.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
