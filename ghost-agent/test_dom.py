from browser import open_browser, close_browser, wait_for_stable
import time
from linkedin.auth import ensure_session, wait_for_login, is_logged_in

def run():
    page, context, playwright = open_browser("https://www.linkedin.com/search/results/all/?keywords=Utkarsh%20Kumar%20Bakhtiyarpur")
    wait_for_stable(page, timeout=10000)
    
    if not is_logged_in(page):
        print("Not logged in.")
        return
        
    page.wait_for_timeout(3000)
    
    # Dump elements that have 'People' text inside
    elements = page.locator("button:has-text('People'), a:has-text('People')").all()
    for i, el in enumerate(elements):
        try:
            print(f"--- Element {i} ---")
            print("Tag:", el.evaluate("e => e.tagName"))
            print("Class:", el.evaluate("e => e.className"))
            print("Text:", repr(el.evaluate("e => e.innerText")))
            print("Accessible Name:", el.evaluate("e => e.getAttribute('aria-label')"))
            print("HTML:", el.evaluate("e => e.outerHTML"))
        except Exception:
            pass
            
    close_browser(context, playwright)

run()
