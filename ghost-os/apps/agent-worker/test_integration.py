from patchright.sync_api import sync_playwright
import os
import sys
from pathlib import Path

# Add current dir to sys.path
sys.path.append(str(Path(__file__).parent))

from navigator import _click_cached_or_discover, _smap
from accessibility import find_buttons

def test_integration():
    print("Starting integration test...")
    with sync_playwright() as p:
        print("Playwright started...")
        # Launch a headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Create a dummy test page
        test_html = """
        <html>
        <body>
            <h1>Integration Test</h1>
            <button id="real-btn-789">Correct Button (Connect)</button>
        </body>
        </html>
        """
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp.write(test_html)
            tmp_path = tmp.name
            
        try:
            page.goto(f"file://{tmp_path}")
            
            # Clear cache for this label to ensure we trigger discovery/healing
            _smap.invalidate("test_btn")
            
            print("--- Step 1: Triggering Healing ---")
            # This should:
            # 1. Try cache (fail)
            # 2. Try ACT discovery with name="Wrong Label" (fail)
            # 3. Trigger self-healing with intent="Click the Correct Button button"
            # 4. Gemini should find "#real-btn-789"
            # 5. Succeed and cache
            
            # Wait, my discover_fn expects find_buttons
            # I'll pass a name that is WRONG but gives enough context for Gemini
            success = _click_cached_or_discover(page, "test_btn", "button", "Connect", find_buttons)
            
            if success:
                print("Step 1 Success!")
            else:
                print("Step 1 Failed!")

            print("--- Step 2: Verifying Cache ---")
            # Should use the cached selector directly
            success2 = _click_cached_or_discover(page, "test_btn", "button", "Connect", find_buttons)
            if success2:
                print("Step 2 Success!")
            
        finally:
            browser.close()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    test_integration()
