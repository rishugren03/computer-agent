"""The Ghost Inbox Monitor — High-speed Kill Switch.

Polls the LinkedIn messaging thread in the background using Vision.
If a new message indicator is detected via Gemini Flash-Lite, it triggers
an immediate abort of all automation.
"""

import threading
import time
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision import analyze_image
from config import SCREENSHOT_DIR

# Global Kill Switch State
ABORT_AUTOMATION = False

def ghost_inbox_monitor_loop(context):
    """Background polling loop for the kill switch."""
    global ABORT_AUTOMATION
    
    print("[Kill Switch] 🛡️ Starting Ghost Inbox Monitor thread...")
    
    try:
        # Open a hidden page for inbox monitoring
        page = context.new_page()
        page.goto("https://www.linkedin.com/messaging/", wait_until="commit")
        
        while not ABORT_AUTOMATION:
            try:
                # Refresh sporadically to get new messages
                time.sleep(15) 
                
                # Take screenshot
                screenshot_path = os.path.join(SCREENSHOT_DIR, "inbox_monitor.png")
                page.screenshot(path=screenshot_path)
                
                # Use Gemini Flash-Lite to detect unread markers
                prompt = "Look at this LinkedIn inbox screenshot. Are there any 'New Message' indicators (like a green dot or unread count badge) visible? Return ONLY a JSON object: {\"unread_detected\": true/false}."
                
                response_text = analyze_image(screenshot_path, prompt)
                
                if response_text:
                    cleaned = response_text.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.split("\n", 1)[1]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    
                    try:
                        result = json.loads(cleaned)
                        if result.get("unread_detected"):
                            print("\n[Kill Switch] 🚨 NEW MESSAGE DETECTED BY VISION! INITIATING IMMEDIATE ABORT 🚨")
                            ABORT_AUTOMATION = True
                            break
                    except json.JSONDecodeError:
                        pass
                
                page.reload(wait_until="commit")
                
            except Exception as e:
                # Page closed or context destroyed
                print(f"[Kill Switch] Loop error: {e}")
                break
                
    except Exception as e:
        print(f"[Kill Switch] Failed to initialize: {e}")
        
def start_monitor(context):
    """Launch the Ghost Inbox Monitor in a background thread."""
    thread = threading.Thread(target=ghost_inbox_monitor_loop, args=(context,), daemon=True)
    thread.start()
    return thread
