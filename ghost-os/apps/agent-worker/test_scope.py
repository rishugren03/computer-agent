import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from browser import open_browser, close_browser, wait_for_stable
import time

page, context, p = open_browser("https://www.linkedin.com/feed/")
print("Navigated to feed.")
try:
    wait_for_stable(page, timeout=5000)
    
    script = """() => {
        const articles = document.querySelectorAll('div[role="listitem"][componentkey*="FeedType"], article, .feed-shared-update-v2, [data-urn*="activity"]');
        let results = [];
        for (let i = 0; i < Math.min(3, articles.length); i++) {
            const el = articles[i];
            const hasLike = el.querySelector('button[aria-label^="Like"], [role="button"][aria-label^="Like"]') !== null;
            const hasComment = el.querySelector('button[aria-label^="Comment"], .comment-button') !== null;
            
            // let's look for the bounding box of the article vs button on page
            results.push({
                index: i,
                hasLikeInside: hasLike,
                hasCommentInside: hasComment,
                tag: el.tagName,
                classes: el.className
            });
        }
        return results;
    }"""
    result = page.evaluate(script)
    print("Post scope debug:")
    for r in result:
        print(r)
        
except Exception as e:
    print("Error:", e)
finally:
    close_browser(context, p)
