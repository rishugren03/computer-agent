"""LLM decision engine for browser automation.

Uses DeepSeek for action planning and Gemini Vision for screenshot analysis.
"""

from openai import OpenAI
from dotenv import load_dotenv
from google import genai
from PIL import Image
import os
import json
import time

load_dotenv()

# --- DeepSeek text LLM (for deciding page actions) ---

deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# Track action history for multi-step reasoning
_action_history = []


SYSTEM_PROMPT = """You are a general-purpose browser automation agent. You are given:
1. A goal to accomplish
2. The current page URL and title  
3. A list of visible interactive elements on the page
4. A description of what the page looks like (from a screenshot)
5. History of actions already taken

You must decide the SINGLE next action to take toward the goal.

## Available Actions

```json
{"action": "click", "id": <element_id>}
{"action": "type", "id": <element_id>, "text": "<text_to_type>"}
{"action": "select_option", "id": <element_id>, "value": "<option_text>"}
{"action": "press_key", "key": "<key_name>"}
{"action": "scroll", "direction": "up|down", "amount": 300}
{"action": "wait", "seconds": 2}
{"action": "hover", "id": <element_id>}
{"action": "go_back"}
{"action": "done", "reason": "<why the goal is achieved or impossible>"}
```

## Key Names for press_key
Enter, Tab, Escape, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, Backspace, Delete, Space

## Strategy Rules

1. **Auto-complete / Suggestion dropdowns**: After typing in a search field or autocomplete input, look for dropdown options that appear. If you see elements with role="option" or list items matching your search, CLICK on the correct option instead of pressing Enter.

2. **Date pickers**: Look for calendar widgets, date inputs, or date-related elements. Click on specific dates rather than trying to type dates.

3. **Select dropdowns**: Use "select_option" for HTML <select> elements. Use "click" for custom styled dropdowns.

4. **Form filling**: Fill fields one at a time. After filling one field, check if a dropdown appeared before moving to the next field.

5. **Page loading**: If the screenshot description mentions loading spinners or the page seems to be loading, use "wait" to let it finish.

6. **Scrolling**: If you need to interact with elements that are not visible (inViewport: false), scroll down first to bring them into view.

7. **Navigation**: If you're on the wrong page, use links or go_back to navigate.

8. **Completion**: When the goal is clearly achieved (e.g., search results are displayed, a form is submitted, information is visible), use "done".

9. **Error recovery**: If previous actions failed, try alternative approaches (different elements, different selectors).

10. **Never repeat the same failing action**. If an action was tried and failed, try something different.

## Response Format
Return ONLY valid JSON. No explanation, no markdown, no extra text.
"""


def decide_action(goal, elements, page_info=None, screenshot_description=None):
    """Ask the LLM what action to take given a goal, visible elements, and page context."""

    # Build history string
    history_str = ""
    if _action_history:
        history_str = "\nActions already taken:\n"
        for i, h in enumerate(_action_history, 1):
            history_str += f"  {i}. {h}\n"
        history_str += "\nDo NOT repeat failed actions. Decide the NEXT logical step.\n"

    # Build page context
    page_ctx = ""
    if page_info:
        page_ctx = f"\nCurrent Page: {page_info.get('title', 'Unknown')} ({page_info.get('url', 'Unknown')})\n"
        if page_info.get('alertText'):
            page_ctx += f"Page Alert: {page_info['alertText']}\n"
        if page_info.get('loadingIndicators'):
            page_ctx += "Note: Page appears to be loading.\n"

    # Build screenshot context
    screenshot_ctx = ""
    if screenshot_description:
        screenshot_ctx = f"\nWhat the page currently looks like:\n{screenshot_description}\n"

    # Simplify elements to reduce token count — only send relevant fields
    simplified = []
    for el in elements:
        item = {"id": el["id"], "tag": el["tag"]}
        if el.get("text"): item["text"] = el["text"]
        if el.get("type"): item["type"] = el["type"]
        if el.get("role"): item["role"] = el["role"]
        if el.get("placeholder"): item["placeholder"] = el["placeholder"]
        if el.get("ariaLabel"): item["ariaLabel"] = el["ariaLabel"]
        if el.get("value"): item["value"] = el["value"]
        if el.get("ariaExpanded"): item["ariaExpanded"] = el["ariaExpanded"]
        if el.get("disabled"): item["disabled"] = True
        if el.get("href"): item["href"] = el["href"][:80]
        if not el.get("inViewport"): item["inViewport"] = False
        simplified.append(item)

    user_prompt = f"""Goal: {goal}
{page_ctx}{screenshot_ctx}{history_str}
Available elements:
{json.dumps(simplified, indent=2)}

Return ONLY the JSON action.
"""

    response = deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3].strip()

    result = json.loads(content)

    # Record this action in history
    _record_action(result, elements)

    return result


def _record_action(result, elements):
    """Record an action in history for multi-step context."""
    action = result.get("action", "unknown")

    if action == "type":
        el_desc = _find_element_desc(elements, result.get("id"))
        _action_history.append(f"Typed '{result.get('text', '')}' into {el_desc}")
    elif action == "click":
        el_desc = _find_element_desc(elements, result.get("id"))
        _action_history.append(f"Clicked {el_desc}")
    elif action == "select_option":
        el_desc = _find_element_desc(elements, result.get("id"))
        _action_history.append(f"Selected '{result.get('value', '')}' in {el_desc}")
    elif action == "press_key":
        _action_history.append(f"Pressed key '{result.get('key', '')}'")
    elif action == "scroll":
        _action_history.append(f"Scrolled {result.get('direction', 'down')} by {result.get('amount', 300)}px")
    elif action == "wait":
        _action_history.append(f"Waited {result.get('seconds', 2)}s")
    elif action == "hover":
        el_desc = _find_element_desc(elements, result.get("id"))
        _action_history.append(f"Hovered over {el_desc}")
    elif action == "go_back":
        _action_history.append("Navigated back")
    elif action == "done":
        _action_history.append(f"Done: {result.get('reason', '')}")


def record_error(error_msg):
    """Record an error in action history so the LLM can learn from it."""
    _action_history.append(f"ERROR: {error_msg}")


def _find_element_desc(elements, element_id):
    """Build a human-readable description of an element for history."""
    if element_id is None:
        return "unknown element"
    for el in elements:
        if el["id"] == element_id:
            parts = [el.get("tag", "")]
            if el.get("text"):
                parts.append(f"'{el['text'][:40]}'")
            elif el.get("placeholder"):
                parts.append(f"[{el['placeholder']}]")
            elif el.get("ariaLabel"):
                parts.append(f"[{el['ariaLabel']}]")
            return f"element {element_id} ({' '.join(parts)})"
    return f"element {element_id}"


# --- Gemini Vision LLM (for analyzing screenshots / images) ---

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

VISION_MODEL = "gemini-2.0-flash"
MAX_VISION_RETRIES = 3


SCREENSHOT_PROMPT = """Describe what this web page shows in 2-3 sentences. Focus on:
- What type of page is this (search results, form, login, article, etc.)?
- What is the main content visible?
- Are there any popups, dropdowns, modals, error messages, or loading indicators?
- Are there any form fields that appear filled or empty?

Be concise and factual. Do not guess — only describe what you can see."""


def describe_screenshot(image_path):
    """Analyze a screenshot and return a text description of what the page shows."""
    return analyze_image(image_path, SCREENSHOT_PROMPT)


def analyze_image(image_path, prompt):
    """
    Send a screenshot + text prompt to Gemini Vision.
    Returns the model's text response.
    Includes retry with exponential backoff for rate limits.
    """

    img = Image.open(image_path)

    for attempt in range(MAX_VISION_RETRIES):
        try:
            response = gemini_client.models.generate_content(
                model=VISION_MODEL,
                contents=[prompt, img],
            )

            text = response.text.strip()
            return text

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                wait_time = (2 ** attempt) * 15  # 15s, 30s, 60s
                print(f"[Vision LLM] Rate limited (attempt {attempt + 1}/{MAX_VISION_RETRIES}), waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise

    raise Exception(f"Vision LLM failed after {MAX_VISION_RETRIES} retries due to rate limiting")