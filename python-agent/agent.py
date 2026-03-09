"""General-purpose browser automation agent.

Usage:
    python agent.py <url> <goal>
    python agent.py "https://www.irctc.co.in/" "search trains from bettiah to delhi on April 10"
    python agent.py "https://www.google.com/" "search for python programming and click the first result"
"""

from browser import open_browser, take_screenshot, wait_for_stable
from dom import get_elements, get_page_info, detect_recaptcha
from llm import decide_action, describe_screenshot, record_error
from executor_browser import execute
from recaptcha import solve_recaptcha
from human import random_delay
import time
import sys
import os

# --- Configuration ---
DEFAULT_GOAL = "tweet - hello I am autonomous computer agent created by codewave labs. can you stop me? Haha... I'm a bot."
DEFAULT_URL = "https://x.com/"
MAX_STEPS = 30
SCREENSHOT_DIR = "/tmp/agent_screenshots"

# Parse CLI arguments
url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
goal = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_GOAL

print(f"🎯 Goal: {goal}")
print(f"🌐 URL:  {url}")
print(f"📊 Max steps: {MAX_STEPS}")
print()

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Launch browser
page = open_browser(url)

# Wait for initial page load
print("[Agent] Waiting for page to fully load...")
wait_for_stable(page, timeout=8000)

# Take initial screenshot for context
screenshot_path = os.path.join(SCREENSHOT_DIR, "step_0.png")
take_screenshot(page, screenshot_path)

# Get initial visual description
try:
    screenshot_desc = describe_screenshot(screenshot_path)
    print(f"[Agent] Initial page: {screenshot_desc[:120]}...")
except Exception as e:
    print(f"[Agent] Vision analysis skipped: {e}")
    screenshot_desc = None

for step in range(MAX_STEPS):
    print(f"\n{'='*60}")
    print(f"--- Step {step + 1}/{MAX_STEPS} ---")
    print(f"{'='*60}")

    # Check for reCAPTCHA before normal DOM interaction
    recaptcha_info = detect_recaptcha(page)

    if recaptcha_info["found"]:
        print("[Agent] 🔒 reCAPTCHA detected — handing off to solver...")
        solved = solve_recaptcha(page)

        if solved:
            print("[Agent] ✅ reCAPTCHA solved! Continuing with goal...")
        else:
            print("[Agent] ⏳ reCAPTCHA not solved yet, will retry next step.")

        random_delay(1.0, 2.0)
        continue

    # 1. Get page context
    page_info = get_page_info(page)
    print(f"[Agent] Page: {page_info['title']} ({page_info['url'][:60]}...)")

    # 2. Extract interactive elements
    elements = get_elements(page)
    print(f"[Agent] Found {len(elements)} interactive elements")

    if not elements:
        print("[Agent] No interactive elements found. Waiting for page to load...")
        wait_for_stable(page, timeout=3000)
        continue

    # 3. Ask LLM for the next action
    try:
        action = decide_action(
            goal=goal,
            elements=elements,
            page_info=page_info,
            screenshot_description=screenshot_desc,
        )
        print(f"[Agent] 🤖 Action: {action}")
    except Exception as e:
        print(f"[Agent] ❌ LLM decision error: {e}")
        record_error(f"LLM error: {e}")
        random_delay(1.0, 2.0)
        continue

    # 4. Check for 'done' action
    if action.get("action") == "done":
        print(f"\n[Agent] ✅ Goal achieved: {action.get('reason', 'completed')}")
        break

    # 5. Execute the action
    try:
        result = execute(page, action, elements)
        print(f"[Agent] 📋 Result: {result}")
    except Exception as e:
        error_msg = f"Execution error: {e}"
        print(f"[Agent] ❌ {error_msg}")
        record_error(error_msg)
        random_delay(1.0, 2.0)
        continue

    # 6. Wait for page to settle after the action
    random_delay(1.0, 2.0)
    wait_for_stable(page, timeout=5000)

    # 7. Take a screenshot and analyze what happened
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"step_{step + 1}.png")
    try:
        take_screenshot(page, screenshot_path)
        screenshot_desc = describe_screenshot(screenshot_path)
        print(f"[Agent] 👁️  Page now: {screenshot_desc[:120]}...")
    except Exception as e:
        print(f"[Agent] Vision analysis skipped: {e}")
        screenshot_desc = None

else:
    print(f"\n[Agent] ⚠️  Reached maximum steps ({MAX_STEPS}) without completing the goal.")

print("\n[Agent] Done.")