"""Ghost Inbox Monitor — background kill switch.

Polls LinkedIn messaging on a hidden page using vision.
If a new message is detected, sets ABORT_AUTOMATION = True and signals the stop event.

Hardened version:
- Accepts a threading.Event for clean shutdown (no daemon thread races)
- Full exception handling inside the poll loop — one vision error doesn't kill the monitor
- Page-closed detection exits gracefully
"""

import threading
import time
import os
import json
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision import analyze_image
from config import SCREENSHOT_DIR

ABORT_AUTOMATION = False

_POLL_INTERVAL = 15  # seconds between inbox checks
_INBOX_MONITOR_PROMPT = (
    "Look at this LinkedIn inbox screenshot. "
    "Are there any unread message indicators (green dot, bold name, unread count badge) visible? "
    'Return ONLY JSON: {"unread_detected": true} or {"unread_detected": false}'
)


def ghost_inbox_monitor_loop(context, stop_event: threading.Event):
    """Poll LinkedIn inbox for new messages until stop_event is set.

    Designed to be re-entrant: if an exception occurs, the caller (agent.py's
    _robust_inbox_monitor) can restart this function safely.
    """
    global ABORT_AUTOMATION

    print("[KillSwitch] 🛡️ Inbox monitor started")
    page = None

    try:
        page = context.new_page()
        page.goto("https://www.linkedin.com/messaging/", wait_until="commit", timeout=15000)
    except Exception as e:
        print(f"[KillSwitch] Could not open messaging page: {e}")
        return

    try:
        while not stop_event.is_set() and not ABORT_AUTOMATION:
            if stop_event.wait(timeout=_POLL_INTERVAL):
                break  # stop_event was set during sleep

            try:
                screenshot_path = os.path.join(SCREENSHOT_DIR, "inbox_monitor.png")
                os.makedirs(SCREENSHOT_DIR, exist_ok=True)
                page.screenshot(path=screenshot_path)

                response_text = analyze_image(screenshot_path, _INBOX_MONITOR_PROMPT)
                if response_text:
                    cleaned = response_text.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.split("\n", 1)[1].rstrip("`").strip()
                    try:
                        result = json.loads(cleaned)
                        if result.get("unread_detected"):
                            print("[KillSwitch] 🚨 NEW MESSAGE — aborting automation")
                            ABORT_AUTOMATION = True
                            stop_event.set()
                            break
                    except json.JSONDecodeError:
                        pass  # Vision returned something unparseable — not fatal

                # Reload page to get fresh state
                page.reload(wait_until="commit", timeout=10000)

            except Exception as e:
                # Page closed or context destroyed — stop monitoring
                if "Target page, context or browser has been closed" in str(e):
                    break
                print(f"[KillSwitch] Poll error (continuing): {e}")

    finally:
        try:
            page.close()
        except Exception:
            pass
        print("[KillSwitch] Monitor stopped")


def start_monitor(context, stop_event: threading.Event = None) -> threading.Thread:
    """Launch the inbox monitor in a background thread.

    Args:
        context: Playwright browser context.
        stop_event: Optional threading.Event to stop the monitor from outside.
                    If not provided, a new one is created and returned via the thread.

    Returns:
        The monitor thread (already started).
    """
    if stop_event is None:
        stop_event = threading.Event()

    thread = threading.Thread(
        target=ghost_inbox_monitor_loop,
        args=(context, stop_event),
        daemon=False,  # Not daemon — we want clean shutdown via stop_event
        name="GhostKillSwitch",
    )
    thread.start()
    return thread
