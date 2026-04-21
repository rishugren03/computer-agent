"""Stealth browser for GhostAgent.

Per-account Redis channels: live_view_{account_id} and agent_status_{account_id}
so multiple users can have independent live view streams.
"""

from patchright.sync_api import sync_playwright
import random
import os
import time
import json
import base64
import threading
import redis

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


def open_browser(url="https://www.linkedin.com", cookies: dict = None, account_id: str = None):
    """Launch a stealth Chromium browser.

    Args:
        url: Initial URL to navigate to.
        cookies: Optional {li_at, JSESSIONID} to inject immediately.
        account_id: Used to isolate browser data dir and Redis channels per user.

    Returns:
        tuple: (page, context, playwright)
    """
    p = sync_playwright().start()

    # Per-account browser data dir so sessions don't bleed between users
    base_dir = os.path.join(os.getcwd(), BROWSER_DATA_DIR)
    if account_id:
        user_data_dir = os.path.join(base_dir, f"account_{account_id}")
    else:
        user_data_dir = base_dir
    os.makedirs(user_data_dir, exist_ok=True)

    # Persistent fingerprint per account
    fingerprint_file = os.path.join(user_data_dir, "fingerprint.json")
    if os.path.exists(fingerprint_file):
        try:
            fp = json.loads(open(fingerprint_file).read())
            width = fp.get("width", VIEWPORT_BASE_WIDTH)
            height = fp.get("height", VIEWPORT_BASE_HEIGHT)
            user_agent = fp.get("user_agent", random.choice(USER_AGENTS))
        except Exception:
            width = VIEWPORT_BASE_WIDTH + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
            height = VIEWPORT_BASE_HEIGHT + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
            user_agent = random.choice(USER_AGENTS)
    else:
        width = VIEWPORT_BASE_WIDTH + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
        height = VIEWPORT_BASE_HEIGHT + random.randint(-VIEWPORT_JITTER, VIEWPORT_JITTER)
        user_agent = random.choice(USER_AGENTS)
        try:
            with open(fingerprint_file, "w") as f:
                json.dump({"width": width, "height": height, "user_agent": user_agent}, f)
        except Exception:
            pass

    launch_args = {
        "user_data_dir": user_data_dir,
        "headless": True,
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
        "geolocation": {"latitude": USER_LATITUDE, "longitude": USER_LONGITUDE},
    }

    proxy_url = get_proxy_url()
    if proxy_url:
        launch_args["proxy"] = {"server": proxy_url}

    context = p.chromium.launch_persistent_context(**launch_args)
    context.grant_permissions(["geolocation"])

    # Inject cookies (from DB or caller)
    if cookies and cookies.get("li_at"):
        print("[Browser] 🍪 Injecting session cookies")
        context.add_cookies([
            {"name": "li_at", "value": cookies["li_at"], "domain": ".www.linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": cookies.get("JSESSIONID", ""), "domain": ".www.linkedin.com", "path": "/"},
        ])
    elif not cookies and not account_id:
        # Legacy: try old DB function
        try:
            from db import get_session_cookies
            legacy = get_session_cookies()
            if legacy and legacy.get("li_at"):
                context.add_cookies([
                    {"name": "li_at", "value": legacy["li_at"], "domain": ".www.linkedin.com", "path": "/"},
                    {"name": "JSESSIONID", "value": legacy.get("JSESSIONID", ""), "domain": ".www.linkedin.com", "path": "/"},
                ])
        except Exception:
            pass

    page = context.pages[0] if context.pages else context.new_page()

    # Ghost macros + visual cursor
    context.add_init_script("""
        document.addEventListener('mousemove', (e) => {
            window._mouseX = e.clientX;
            window._mouseY = e.clientY;
        }, { capture: true });

        window.addEventListener('DOMContentLoaded', () => {
            if (document.getElementById('ghost-agent-cursor')) return;
            const cursor = document.createElement('div');
            cursor.id = 'ghost-agent-cursor';
            Object.assign(cursor.style, {
                width: '14px', height: '14px',
                backgroundColor: 'rgba(255,0,0,0.6)',
                border: '2px solid white',
                borderRadius: '50%',
                position: 'fixed',
                pointerEvents: 'none',
                zIndex: '2147483647',
                transform: 'translate(-50%,-50%)',
                transition: 'transform 0.05s linear, background-color 0.1s',
                left: '-100px', top: '-100px',
            });
            document.documentElement.appendChild(cursor);
            document.addEventListener('mousemove', e => {
                cursor.style.left = e.clientX + 'px';
                cursor.style.top = e.clientY + 'px';
            }, { capture: true });
            document.addEventListener('mousedown', () => {
                cursor.style.backgroundColor = 'rgba(0,255,0,0.7)';
                cursor.style.transform = 'translate(-50%,-50%) scale(0.7)';
            }, { capture: true });
            document.addEventListener('mouseup', () => {
                cursor.style.backgroundColor = 'rgba(255,0,0,0.6)';
                cursor.style.transform = 'translate(-50%,-50%) scale(1)';
            }, { capture: true });

            window.ghost_macros = {
                sendInviteMacro: async (note) => {
                    const connectBtn = Array.from(document.querySelectorAll('button'))
                        .find(b => b.innerText.includes('Connect') || b.getAttribute('aria-label')?.includes('Connect'));
                    if (!connectBtn) return { success: false, reason: "Connect button not found" };
                    connectBtn.click();
                    let start = Date.now();
                    while (Date.now() - start < 2000) {
                        const addNoteBtn = Array.from(document.querySelectorAll('button'))
                            .find(b => b.innerText.includes('Add a note'));
                        if (addNoteBtn) { addNoteBtn.click(); break; }
                        const sendNow = Array.from(document.querySelectorAll('button'))
                            .find(b => b.innerText.includes('Send without a note'));
                        if (sendNow && !note) { sendNow.click(); return { success: true, method: "direct" }; }
                        await new Promise(r => setTimeout(r, 100));
                    }
                    if (note) {
                        start = Date.now();
                        while (Date.now() - start < 1500) {
                            const ta = document.querySelector('textarea#custom-message,textarea[name="message"]');
                            if (ta) {
                                ta.value = note;
                                ta.dispatchEvent(new Event('input', { bubbles: true }));
                                break;
                            }
                            await new Promise(r => setTimeout(r, 100));
                        }
                    }
                    const sendBtn = Array.from(document.querySelectorAll('button'))
                        .find(b => b.innerText.includes('Send') || b.getAttribute('aria-label')?.includes('Send invitation'));
                    if (sendBtn) { sendBtn.click(); return { success: true }; }
                    return { success: false, reason: "Send button not found" };
                },
                organicScroll: async (amount = 500) => {
                    window.scrollBy({ top: amount, behavior: 'smooth' });
                    return { success: true };
                }
            };
        });
    """)

    page.goto(url, wait_until="domcontentloaded")
    return page, context, p


def take_screenshot(page, path=None):
    if path is None:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOT_DIR, "screenshot.png")
    else:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
    page.screenshot(path=path, full_page=False)
    return path


def wait_for_stable(page, timeout=5000):
    try:
        page.wait_for_load_state("commit", timeout=timeout)
    except Exception:
        time.sleep(1.5)
    time.sleep(random.uniform(0.3, 0.8))


def get_current_url(page):
    return page.evaluate("() => window.location.href")


def get_page_title(page):
    return page.evaluate("() => document.title")


def is_linkedin(page):
    return "linkedin.com" in get_current_url(page)


def close_browser(context, playwright):
    try:
        context.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass


def _screenshot_thread_safe(page, **kwargs) -> bytes:
    """Take a screenshot from any thread.

    patchright's sync API uses greenlets bound to the creating thread.
    Calling page.screenshot() from a background thread raises
    greenlet.error: Cannot switch to a different thread.

    This bypasses the greenlet layer by submitting the async coroutine
    directly to the Playwright event loop via asyncio.run_coroutine_threadsafe,
    which is designed for cross-thread coroutine submission.
    """
    import asyncio
    future = asyncio.run_coroutine_threadsafe(
        page._impl_obj.screenshot(**kwargs),
        page._loop,
    )
    return future.result(timeout=10)


def broadcast_screen(page, account_id: str = None, r=None):
    """Publish a JPEG screenshot to Redis for the dashboard live view.

    Pass a persistent Redis client via `r` to avoid reconnecting every frame.
    Falls back to creating a one-shot connection when `r` is None.
    """
    _owned = r is None
    if _owned:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url)
    try:
        screenshot_bytes = _screenshot_thread_safe(page, type="jpeg", quality=60)
        b64_data = base64.b64encode(screenshot_bytes).decode()
        channel = f"live_view_{account_id}" if account_id else "live_view"
        r.publish(channel, b64_data)
    except Exception:
        pass
    finally:
        if _owned:
            r.close()


def start_screen_broadcast(page, account_id: str = None, fps: float = 2.0) -> threading.Event:
    """Spawn a daemon thread that streams screenshots to Redis at `fps`.

    Returns a stop Event — set it before closing the browser so the thread
    exits cleanly and the Redis connection is released.
    """
    stop = threading.Event()
    interval = 1.0 / fps

    def _loop():
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url)
        try:
            while not stop.is_set():
                try:
                    broadcast_screen(page, account_id=account_id, r=r)
                except Exception:
                    pass
                stop.wait(interval)
        finally:
            try:
                r.close()
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True, name=f"broadcast-{account_id or 'legacy'}")
    t.start()
    return stop


def publish_agent_status(status: str, account_id: str = None):
    """Publish agent status string to Redis for the dashboard."""
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(redis_url)
        channel = f"agent_status_{account_id}" if account_id else "agent_status"
        r.publish(channel, status)
        r.close()
    except Exception:
        pass
