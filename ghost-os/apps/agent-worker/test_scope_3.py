import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from browser import open_browser, close_browser, wait_for_stable

page, context, p = open_browser("https://www.linkedin.com/feed/")
print("Navigated to feed.")
try:
    wait_for_stable(page, timeout=5000)
    
    script = """() => {
        const posts = document.querySelectorAll('div[role="listitem"], .feed-shared-update-v2, [data-urn*="activity"]');
        let results = [];
        for (let i = 0; i < Math.min(3, posts.length); i++) {
            const el = posts[i];
            
            // Check if any child has "Like" in text
            const hasLikeText = el.innerText && el.innerText.toLowerCase().includes('like');
            
            // Collect all button elements in this wrapper
            const btns = Array.from(el.querySelectorAll('button, div[role="button"]'));
            const btnTexts = btns.map(b => (b.innerText || '').trim().substring(0, 20)).filter(t => t.length > 0);
            
            // If the element has a parent, check parent's buttons too
            let parentBtns = [];
            if (el.parentElement) {
                const pb = Array.from(el.parentElement.querySelectorAll('button, div[role="button"]'));
                parentBtns = pb.map(b => (b.innerText || '').trim().substring(0, 20)).filter(t => t.length > 0);
            }

            // Check parent's parent
            let ppBtns = [];
            if (el.parentElement && el.parentElement.parentElement) {
                const pb = Array.from(el.parentElement.parentElement.querySelectorAll('button, div[role="button"]'));
                ppBtns = pb.map(b => (b.innerText || '').trim().substring(0, 20)).filter(t => t.length > 0);
            }
            
            results.push({
                index: i,
                hasLikeTextInInner: hasLikeText,
                buttonCountInside: btnTexts.length,
                insideButtonSamples: btnTexts.slice(0, 10),
                parentButtonSamples: parentBtns.slice(0, 10),
                grandParentButtonSamples: ppBtns.slice(0, 10)
            });
        }
        return results;
    }"""
    result = page.evaluate(script)
    for r in result:
        print(r)
        
except Exception as e:
    print("Error:", e)
finally:
    close_browser(context, p)
