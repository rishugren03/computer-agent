"""Browser launch, screenshot, and wait utilities."""

from patchright.sync_api import sync_playwright
import random
import os
import time


def open_browser(url="https://google.com"):
    """Launch a stealth Chromium browser using patchright (undetected Playwright fork)."""

    p = sync_playwright().start()

    user_data_dir = os.path.join(os.getcwd(), "agent_browser_data")

    context = p.chromium.launch_persistent_context(
        user_data_dir,
        headless=False,
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="Asia/Kolkata",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US,en",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto(url, wait_until="domcontentloaded")

    return page


def take_screenshot(page, path="screenshot.png"):
    """Take a screenshot of the current page and return the file path."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    page.screenshot(path=path, full_page=False)
    return path


def wait_for_stable(page, timeout=5000):
    """Wait for the page to become stable (network idle + brief DOM settle).
    
    Tries networkidle first, falls back to a short fixed wait if it times out.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # Network didn't go idle (e.g., long-polling, websockets) — just wait briefly
        time.sleep(1.5)
    
    # Brief additional wait for any JS rendering to complete
    time.sleep(0.5)