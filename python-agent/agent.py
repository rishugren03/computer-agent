from browser import open_browser
from dom import get_elements, detect_recaptcha
from llm import decide_action
from executor_browser import execute
from recaptcha import solve_recaptcha
from human import random_delay
import time
import sys

# --- Configuration ---
goal = "search openai"
url = "https://www.google.com/"
max_steps = 10

# Allow overrides from command line
if len(sys.argv) > 1:
    url = sys.argv[1]
if len(sys.argv) > 2:
    goal = sys.argv[2]

print(f"Goal: {goal}")
print(f"URL:  {url}")
print()

page = open_browser(url)

# Wait for page + reCAPTCHA iframes to fully load before starting
print("[Agent] Waiting for page to fully load...")
time.sleep(5)

for step in range(max_steps):
    print(f"\n--- Step {step + 1}/{max_steps} ---")

    # Check for reCAPTCHA before normal DOM interaction
    recaptcha_info = detect_recaptcha(page)

    if recaptcha_info["found"]:
        print("[Agent] reCAPTCHA detected — handing off to solver...")
        solved = solve_recaptcha(page)

        if solved:
            print("[Agent] reCAPTCHA solved! Continuing with goal...")
        else:
            print("[Agent] reCAPTCHA not solved yet, will retry next step.")

        random_delay(1.0, 2.0)
        continue

    # Normal agent loop: extract elements → ask LLM → execute
    elements = get_elements(page)

    if not elements:
        print("[Agent] No interactive elements found. Waiting...")
        time.sleep(2)
        continue

    try:
        action = decide_action(goal, elements)
        print(f"[Agent] AI action: {action}")
        execute(page, action, elements)
    except Exception as e:
        print(f"[Agent] Action error: {e}")

    random_delay(1.5, 3.0)

print("\n[Agent] Done.")