import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from browser import open_browser, close_browser, wait_for_stable
import time

page, context, p = open_browser("https://www.linkedin.com/feed/")
print("Navigated to feed.")
try:
    wait_for_stable(page, timeout=10000)
    
    script = """() => {
        const articles = document.querySelectorAll('div[role="listitem"][componentkey*="FeedType"], article, .feed-shared-update-v2, [data-urn*="activity"]');
        return Array.from(articles).map(el => {
            const text = (el.innerText || '').toLowerCase();
            return {
                text_start: text.substring(0, 100).replace(/\\n/g, ' '),
                has_like: text.includes('like'),
                has_people_you_may_know: text.includes('people you may know'),
                is_promoted: text.includes('promoted'),
                is_suggested: text.includes('suggested')
            };
        });
    }"""
    result = page.evaluate(script)
    import json
    print("Post containers found:", json.dumps(result, indent=2))
    
except Exception as e:
    print("Error:", e)
finally:
    close_browser(context, p)
