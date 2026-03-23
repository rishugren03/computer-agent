import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from browser import open_browser, close_browser, wait_for_stable

page, context, p = open_browser("https://www.linkedin.com/feed/")
print("Navigated to feed.")
try:
    wait_for_stable(page, timeout=5000)
    
    script = """() => {
        let results = [];
        // Find a Like button
        const likeBtn = document.querySelector('button[aria-label^="Like"], [role="button"][aria-label^="Like"], span[class*="reaction"]');
        if (!likeBtn) return ["No like button found"];
        
        let curr = likeBtn;
        let depth = 0;
        
        while (curr && curr !== document.body && depth < 20) {
            let role = curr.getAttribute('role');
            let ds = curr.dataset ? Object.keys(curr.dataset).map(k => k + '=' + curr.dataset[k]).join(', ') : '';
            let isParentOfBody = curr.querySelector('.feed-shared-update-v2__description, .update-components-text, [data-urn]') !== null;
            
            results.push({
                depth: depth,
                tag: curr.tagName,
                classes: curr.className,
                role: role,
                dataset: ds,
                containsPostBody: isParentOfBody
            });
            
            if (isParentOfBody) {
                // We found the common ancestor!
                results.push("SUCCESS: Common ancestor found at depth " + depth);
                break;
            }
            curr = curr.parentElement;
            depth++;
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
