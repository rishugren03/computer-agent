"""LinkedIn session management for GhostAgent.

Handles:
- Session persistence via Patchright's persistent context
- Login state detection
- Session health checks
- Identity confirmation handling
"""

from browser import wait_for_stable, get_current_url
from human import random_delay


def is_logged_in(page):
    """Check if the user is currently logged into LinkedIn.

    Looks for feed content or profile nav elements that only
    appear when authenticated.

    Returns:
        bool: True if logged in, False if on login/signup page.
    """
    try:
        url = get_current_url(page)

        # If redirected to login page, not logged in
        if "/login" in url or "/signup" in url or "login" in url.split("?")[0]:
            return False

        # Check for authenticated nav elements
        has_feed = page.evaluate("""() => {
            // Check for the main nav bar (only shows when logged in)
            const nav = document.querySelector('nav, [role="navigation"]');
            const feed = document.querySelector('[data-control-name="feed"], .feed-shared-update');
            const globalNav = document.querySelector('.global-nav, #global-nav');
            return !!(nav || feed || globalNav);
        }""")

        return has_feed

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


def wait_for_login(page, timeout_seconds=300):
    """Wait for the user to complete manual login.

    Used during first-time setup when no session cookies exist.
    Polls every 5 seconds for up to `timeout_seconds`.

    Returns:
        bool: True if login detected, False if timeout.
    """
    import time

    print("[Auth] ⏳ Waiting for manual LinkedIn login...")
    print(f"[Auth] Please log in within {timeout_seconds // 60} minutes.")

    start = time.time()
    while time.time() - start < timeout_seconds:
        if is_logged_in(page):
            print("[Auth] ✅ Login detected!")
            random_delay(1.0, 2.0)
            return True
        time.sleep(5)

    print("[Auth] ❌ Login timeout reached.")
    return False


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
