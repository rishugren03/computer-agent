import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from browser import open_browser, close_browser, wait_for_stable
from navigator import navigate_to_profile
from linkedin.auth import wait_for_login, is_logged_in, ensure_session

def test():
    print("Testing search...")
    page, context, playwright = open_browser("https://www.linkedin.com/feed/")
    
    try:
        wait_for_stable(page, timeout=10000)
        if not is_logged_in(page):
            print("Not logged in. Trying to log in...")
            if not wait_for_login(page):
                print("Could not log in")
                return
        ensure_session(page)
        
        from browser import take_screenshot
        take_screenshot(page, "before_profile.png")
        navigate_to_profile(page, "Utkarsh Kumar Bakhtiyarpur")
        take_screenshot(page, "after_profile.png")
        print("Done navigating")
    finally:
        close_browser(context, playwright)

if __name__ == "__main__":
    test()
