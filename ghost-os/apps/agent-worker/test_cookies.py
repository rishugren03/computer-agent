from patchright.sync_api import sync_playwright
from db import get_session_cookies

def test_login():
    cookies = get_session_cookies()
    if not cookies or not cookies.get('li_at'):
        print("No li_at cookie found in DB!")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # Test the improved cookie logic
        jsessionid = cookies['JSESSIONID']
        
        print(f"Injecting JSESSIONID format: {jsessionid}")
        
        context.add_cookies([
            {"name": "li_at", "value": cookies['li_at'], "domain": ".www.linkedin.com", "path": "/", "secure": True},
            {"name": "JSESSIONID", "value": f'"{jsessionid}"', "domain": ".www.linkedin.com", "path": "/", "secure": True},
            {"name": "li_at", "value": cookies['li_at'], "domain": ".linkedin.com", "path": "/", "secure": True},
            {"name": "JSESSIONID", "value": f'"{jsessionid}"', "domain": ".linkedin.com", "path": "/", "secure": True}
        ])
        
        page = context.new_page()
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        
        title = page.title()
        url = page.url
        print(f"PAGE TITLE: {title}")
        print(f"PAGE URL: {url}")
        
        # Check if #global-nav is found
        nav = page.query_selector("#global-nav")
        if nav:
            print("SUCCESS! #global-nav found.")
        else:
            print("FAILED! #global-nav missing, likely redirected to login.")
            
        browser.close()

if __name__ == "__main__":
    test_login()
