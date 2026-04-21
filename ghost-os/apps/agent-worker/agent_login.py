"""LinkedIn browser-controlled login flow.

Spawned by worker.py when user clicks "Connect LinkedIn" in dashboard.
Opens a visible Chromium browser, navigates to LinkedIn, waits for user to log in,
captures cookies, saves to DB, then closes.

The live view stream (Redis live_view_{account_id}) is active during this flow
so the dashboard can show the browser to the user.
"""

import time
import db
from browser import open_browser, wait_for_stable, close_browser
from linkedin.auth import is_logged_in, wait_for_login


def run_login_flow(account_id: str, timeout_secs: int = 300):
    print(f"[Login] Starting LinkedIn login flow for account {account_id}")

    page, context, playwright = open_browser(
        "https://www.linkedin.com/login",
        account_id=account_id,
    )
    wait_for_stable(page, timeout=10000)

    # Redirect all window.open() calls to the same tab.
    # "Sign in with Google" (and similar OAuth buttons) normally open a popup;
    # Google's OAuth redirect flow works identically in the same tab, and this
    # avoids popup-tracking issues in a headless/live-view setup.
    context.add_init_script("""
        (function() {
            const _open = window.open.bind(window);
            window.open = function(url, target, features) {
                if (url && url !== 'about:blank') {
                    window.location.href = url;
                    return null;
                }
                return _open(url, target, features);
            };
        })();
    """)
    # Reload so the init script takes effect on the current login page.
    page.reload(wait_until="domcontentloaded")
    wait_for_stable(page, timeout=8000)

    logged_in = wait_for_login(page, timeout_seconds=timeout_secs, account_id=account_id)

    if logged_in:
        print("[Login] ✅ Login detected, saving cookies...")
        try:
            cookies = context.cookies()
            li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)
            jsessionid = next((c["value"] for c in cookies if c["name"] == "JSESSIONID"), None)
            if li_at:
                db.update_account_session(account_id, li_at, jsessionid or "")
                print("[Login] ✅ Cookies saved to DB")

                # Extract basic profile info
                try:
                    from linkedin.profile import extract_profile_data
                    wait_for_stable(page, timeout=5000)
                    profile = extract_profile_data(page)
                    db.update_account_profile(
                        account_id,
                        name=profile.get("name"),
                        url=profile.get("linkedin_url"),
                        headline=profile.get("headline"),
                    )
                except Exception as e:
                    print(f"[Login] Profile extract warning: {e}")
            else:
                print("[Login] ⚠️ li_at cookie not found after login")
        except Exception as e:
            print(f"[Login] Cookie save error: {e}")
    else:
        print("[Login] ❌ Login timed out or failed")

    close_browser(context, playwright)
    print("[Login] Browser closed")
