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
import json

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

    # Store fingerprint per session to prevent LinkedIn's security detection
    fingerprint_file = os.path.join(user_data_dir, "fingerprint.json")
    if os.path.exists(fingerprint_file):
        try:
            with open(fingerprint_file, "r") as f:
                fp = json.load(f)
            width = fp.get("width", VIEWPORT_BASE_WIDTH)
            height = fp.get("height", VIEWPORT_BASE_HEIGHT)
            user_agent = fp.get("user_agent", random.choice(USER_AGENTS))
            print(f"[Browser] ℹ️ Loaded persistent fingerprint for this session.")
        except Exception as e:
            print(f"[Browser] ⚠️ Error loading fingerprint: {e}")
            width = VIEWPORT_BASE_WIDTH + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
            height = VIEWPORT_BASE_HEIGHT + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
            user_agent = random.choice(USER_AGENTS)
    else:
        # Create a new fingerprint for this fresh session
        width = VIEWPORT_BASE_WIDTH + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
        height = VIEWPORT_BASE_HEIGHT + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
        user_agent = random.choice(USER_AGENTS)
        try:
            with open(fingerprint_file, "w") as f:
                json.dump({"width": width, "height": height, "user_agent": user_agent}, f)
            print(f"[Browser] 🔒 Saved new device fingerprint for session persistence.")
        except Exception as e:
            print(f"[Browser] ⚠️ Error saving fingerprint: {e}")

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
        "bypass_csp": True,
        "ignore_https_errors": True,
    }

    # Add proxy if configured
    proxy_url = get_proxy_url()
    if proxy_url:
        launch_args["proxy"] = {"server": proxy_url}

    context = p.chromium.launch_persistent_context(**launch_args)

    # Set geolocation permissions
    context.grant_permissions(["geolocation"])

    page = context.pages[0] if context.pages else context.new_page()

    # Inject a visual cursor and mouse position tracking for Bézier curves
    # This runs on every page load automatically.
    context.add_init_script("""
        // Track mouse globally
        document.addEventListener('mousemove', (e) => {
            window._mouseX = e.clientX;
            window._mouseY = e.clientY;
        }, { capture: true });

        // Inject visual cursor when DOM is ready
        window.addEventListener('DOMContentLoaded', () => {
            if (document.getElementById('ghost-agent-cursor')) return;
            
            const cursor = document.createElement('div');
            cursor.id = 'ghost-agent-cursor';
            cursor.style.width = '16px';
            cursor.style.height = '16px';
            cursor.style.backgroundColor = 'rgba(255, 0, 0, 0.6)';
            cursor.style.border = '2px solid white';
            cursor.style.borderRadius = '50%';
            cursor.style.position = 'fixed';
            cursor.style.pointerEvents = 'none';
            cursor.style.zIndex = '2147483647';
            cursor.style.transform = 'translate(-50%, -50%)';
            cursor.style.transition = 'transform 0.05s linear, background-color 0.1s';
            // Start offscreen
            cursor.style.left = '-100px';
            cursor.style.top = '-100px';
            document.documentElement.appendChild(cursor);

            document.addEventListener('mousemove', (e) => {
                cursor.style.left = e.clientX + 'px';
                cursor.style.top = e.clientY + 'px';
            }, { capture: true });
            
            document.addEventListener('mousedown', () => {
                cursor.style.backgroundColor = 'rgba(0, 255, 0, 0.7)';
                cursor.style.transform = 'translate(-50%, -50%) scale(0.7)';
            }, { capture: true });
            
            document.addEventListener('mouseup', () => {
                cursor.style.backgroundColor = 'rgba(255, 0, 0, 0.6)';
                cursor.style.transform = 'translate(-50%, -50%) scale(1)';
            }, { capture: true });
        });
    """)

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
    """Wait for the page to become somewhat stable (fast execution).
    
    Speculative Execution: We wait for 'commit' rather than 'networkidle'
    to allow the vision agent to start acting before fully rendering.
    """
    try:
        page.wait_for_load_state("commit", timeout=timeout)
    except Exception:
        pass
        
    # Micro-wait for any JS rendering to start
    time.sleep(random.uniform(0.1, 0.3))


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
