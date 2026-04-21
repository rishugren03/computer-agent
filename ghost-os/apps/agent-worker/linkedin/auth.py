"""LinkedIn session management for GhostAgent.

Handles:
- Session persistence via Patchright's persistent context
- Login state detection
- Session health checks
- Identity confirmation handling
"""

from browser import wait_for_stable, get_current_url, broadcast_screen
from human import random_delay
import redis
import json
import os
import time
from db import update_account_session


def is_logged_in(page):
    """Check if the user is currently logged into LinkedIn.

    Uses multiple indicators:
    1. URL patterns (feed, mynetwork, messaging, etc.)
    2. Presence of authenticated UI elements (nav bar, search bar, profile photo)
    """
    try:
        url = get_current_url(page)

        # Explicit login/signup URLs are definitely "not logged in"
        if any(p in url for p in ["/login", "/signup", "/uno-reg"]):
            return False

        # Check for multiple indicators of an active session
        is_auth = page.evaluate("""() => {
            const markers = [
                // Top nav bar
                '#global-nav', '.global-nav',
                // Me profile photo
                '.global-nav__me-photo',
                // Feed container
                '[data-control-name="feed"]', '.feed-shared-update',
                // Identity/Profile elements
                '.identity-block', 
                // Global search bar
                '.search-global-typeahead__input',
                // Home/Messaging links
                '[data-test-global-nav-link-home]', '[data-test-global-nav-link-messaging]'
            ];
            
            return markers.some(selector => !!document.querySelector(selector));
        }""")

        # If we see authenticated elements, we're logged in
        if is_auth:
            return True

        # Fallback: if we are on the feed or network page, we are likely logged in
        if any(p in url for p in ["/feed", "/mynetwork", "/in/", "/messaging"]):
            return True

        return False

    except Exception as e:
        print(f"[Auth] Error checking login state: {e}")
        return False


def ensure_session(page):
    """Verify session is alive and handle any interruptions.

    Checks for:
    - Logged-in state
    - "Confirm your identity" security prompts
    - "Session expired" modals
    - CAPTCHA challenges

    Returns:
        bool: True if session is healthy, False if manual intervention needed.
    """
    wait_for_stable(page, timeout=5000)

    if not is_logged_in(page):
        print("[Auth] ⚠️  Not logged in — manual login required.")
        print("[Auth] Please log in to LinkedIn in the browser window.")
        return False

    # Check for security challenges
    challenge = _detect_security_challenge(page)
    if challenge:
        print(f"[Auth] ⚠️  Security challenge detected: {challenge}")
        print("[Auth] Please resolve this in the browser window.")
        return False

    return True


def wait_for_login(page, timeout_seconds=300, account_id: str = None):
    """Wait for the user to complete manual login via dashboard.

    OAuth flows like "Sign in with Google" are handled by having agent_login.py
    override window.open() to redirect in the same tab, so everything stays on
    one page and no popup tracking is needed here.

    Uses a single persistent Redis connection for the entire wait so we don't
    pay TCP handshake overhead on every screenshot frame (~8fps target).
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.Redis.from_url(redis_url)
    pubsub = r.pubsub()
    input_channel = f"agent_input_{account_id}" if account_id else "agent_input"
    status_channel = f"agent_status_{account_id}" if account_id else "agent_status"
    pubsub.subscribe(input_channel)

    print("[Auth] ⏳ Waiting for manual LinkedIn login via dashboard...")
    r.publish(status_channel, "manual_login_required")

    start = time.time()
    tick = 0
    try:
        while time.time() - start < timeout_seconds:
            tick += 1

            # Check login state every 5 ticks (~0.6s) — page.evaluate() blocks
            if tick % 5 == 0 and is_logged_in(page):
                print("[Auth] ✅ Login detected!")
                r.publish(status_channel, "running")

                cookies = page.context.cookies()
                li_at = next((c['value'] for c in cookies if c['name'] == 'li_at'), None)
                jsessionid = next((c['value'] for c in cookies if c['name'] == 'JSESSIONID'), None)

                if li_at and jsessionid and account_id:
                    update_account_session(account_id, li_at, jsessionid)
                    print("[Auth] 🍪 Session cookies saved to database.")

                random_delay(1.0, 2.0)
                return True

            # Process pending interactions from dashboard
            message = pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                try:
                    data = json.loads(message['data'])
                    _handle_dashboard_interaction(page, data)
                except Exception as e:
                    print(f"[Auth] Error handling interaction: {e}")

            # Keep the live view updated — reuse persistent r to skip TCP setup
            try:
                broadcast_screen(page, account_id=account_id, r=r)
            except Exception:
                pass

            time.sleep(0.12)  # ~8fps
    finally:
        pubsub.unsubscribe(input_channel)
        r.publish(status_channel, "running")
        r.close()

    print("[Auth] ❌ Login timeout reached.")
    return False


def _handle_dashboard_interaction(page, data):
    """Execute mouse/keyboard interactions received from the dashboard."""
    action_type = data.get("type")
    
    if action_type == "click":
        x, y = data.get("x"), data.get("y")
        if x is not None and y is not None:
            page.mouse.click(x, y)
            print(f"[Auth] 🖱️ Manual click at ({x}, {y})")
            
    elif action_type == "key":
        key = data.get("key")
        if key:
            page.keyboard.press(key)
            print(f"[Auth] ⌨️ Manual key press: {key}")
            
    elif action_type == "type":
        text = data.get("text")
        if text:
            page.keyboard.type(text)
            print(f"[Auth] ⌨️ Manual typing: {text}")


def check_session_or_relogin(page, timeout_seconds=300):
    """Check if still logged in mid-session. If not, wait for re-login.

    Call this periodically during long-running operations (feed engagement,
    inbox processing, etc.) to handle unexpected logouts gracefully.

    The agent resumes from where it left off after re-login.

    Returns:
        bool: True if session is OK (or re-login succeeded), False if timeout.
    """
    try:
        if is_logged_in(page):
            return True
    except Exception:
        pass  # Page might be in a bad state during logout

    # Logout detected!
    print("\n[Auth] ⚠️  SESSION LOST — Logged out mid-session!")
    print("[Auth] ⏳ Waiting for manual re-login...")
    print(f"[Auth] Please log back in within {timeout_seconds // 60} minutes.")
    print("[Auth] The agent will resume from where it left off.\n")

    logged_back_in = wait_for_login(page, timeout_seconds=timeout_seconds)

    if logged_back_in:
        print("[Auth] ✅ Re-login successful — resuming session...")
        # Give the page a moment to fully load after re-login
        from browser import wait_for_stable
        wait_for_stable(page, timeout=8000)
        return True

    print("[Auth] ❌ Re-login timeout — aborting session.")
    return False


def _detect_security_challenge(page):
    """Detect if LinkedIn is showing a security/identity challenge.

    Returns:
        str | None: Description of the challenge, or None if clear.
    """
    try:
        challenge_info = page.evaluate("""() => {
            const body = document.body.innerText || '';
            const lower = body.toLowerCase();

            if (lower.includes('confirm your identity') || lower.includes('verify your identity')) {
                return 'identity_verification';
            }
            if (lower.includes('security verification') || lower.includes('security check')) {
                return 'security_check';
            }
            if (lower.includes('session has expired') || lower.includes('session expired')) {
                return 'session_expired';
            }
            if (lower.includes('unusual activity') || lower.includes('restricted')) {
                return 'account_restricted';
            }

            return null;
        }""")

        return challenge_info

    except Exception:
        return None


def get_session_info(page):
    """Get basic session information for debugging.

    Returns:
        dict: Session info including URL, logged_in status, etc.
    """
    return {
        "url": get_current_url(page),
        "logged_in": is_logged_in(page),
        "challenge": _detect_security_challenge(page),
    }
