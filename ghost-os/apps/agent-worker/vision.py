"""Vision engine using OpenAI for page understanding and action decisions."""

import os
import json
import time
import base64
import hashlib
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

from config import (
    OPENAI_API_KEY,
    OPENAI_VISION_MODEL,
    SCREENSHOT_DIR,
)

load_dotenv()

# ─── Clients ─────────────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

MAX_RETRIES = 3
RETRY_BACKOFF = 2


# ─── Prompts ─────────────────────────────────────────────────────────────────

LINKEDIN_ELEMENT_DETECTION_PROMPT = """You are analyzing a LinkedIn page screenshot.
Identify all interactive UI elements visible on the page.

For EACH element return:
- type: button | link | input | dropdown | tab | icon
- label: visible text or icon description
- x: approximate center x coordinate (pixels from left)
- y: approximate center y coordinate (pixels from top)
- purpose: what this element does

Focus on: Connect, Follow, Message, Like, Comment, Search bar, navigation tabs,
connection note modal (textarea + Send button), More dropdown.

Return ONLY a valid JSON array. No markdown, no explanation.
Example:
[{"type":"button","label":"Connect","x":450,"y":320,"purpose":"send connection request"}]
"""

PAGE_DESCRIPTION_PROMPT = """Describe this LinkedIn page concisely.
1. Page type (feed, profile, search results, messaging, etc.)
2. Key content visible (names, headlines, post summaries)
3. Current UI state (modals open? dropdowns? alerts?)
4. Notable elements (connection status, unread messages, pending invites)
Be factual. Focus on what an agent needs to navigate LinkedIn."""

POST_CONTENT_PROMPT = """Analyze this LinkedIn post screenshot.
Return ONLY JSON:
{"author":"","headline":"","content":"","likes":0,"comments":0,"time":"","topics":[],"tone":""}"""


# ─── Core Vision Call ─────────────────────────────────────────────────────────

def analyze_image(image_path: str, prompt: str) -> str:
    """Send screenshot + prompt to OpenAI vision.

    Returns model response text, or empty string on total failure.
    """
    return _openai_vision(image_path, prompt)


def _openai_vision(image_path: str, prompt: str) -> str:
    if not openai_client:
        return ""
    for attempt in range(MAX_RETRIES):
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            response = openai_client.chat.completions.create(
                model=OPENAI_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",
                            }},
                        ],
                    }
                ],
                max_tokens=1500,
                timeout=25,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF ** (attempt + 1)
                print(f"[Vision/OpenAI] Retry {attempt+1}/{MAX_RETRIES} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"[Vision/OpenAI] Failed after {MAX_RETRIES} attempts: {e}")
    return ""


def _parse_json_response(text: str):
    """Strip markdown fences and parse JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("\n", 1)
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


# ─── High-Level Vision Functions ─────────────────────────────────────────────

def detect_elements(screenshot_path: str) -> list:
    text = analyze_image(screenshot_path, LINKEDIN_ELEMENT_DETECTION_PROMPT)
    if not text:
        return []
    try:
        result = _parse_json_response(text)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError as e:
        print(f"[Vision] Element detection parse error: {e}")
        return []


def describe_page(screenshot_path: str) -> str:
    return analyze_image(screenshot_path, PAGE_DESCRIPTION_PROMPT) or ""


def analyze_post(screenshot_path: str) -> dict:
    text = analyze_image(screenshot_path, POST_CONTENT_PROMPT)
    if not text:
        return {}
    try:
        return _parse_json_response(text)
    except json.JSONDecodeError:
        return {"content": text}


def find_element_by_vision(page, element_description: str) -> dict | None:
    from browser import take_screenshot
    path = take_screenshot(page, os.path.join(SCREENSHOT_DIR, "vision_find.png"))
    prompt = f"""Look at this LinkedIn page screenshot.
Find the "{element_description}" element.
Return ONLY JSON:
{{"x": <pixels from left>, "y": <pixels from top>, "label": "<what you found>", "found": true}}
If NOT visible: {{"found": false, "reason": "<why>"}}"""

    text = analyze_image(path, prompt)
    if not text:
        return None
    try:
        result = _parse_json_response(text)
        if result.get("found"):
            return result
        print(f"[Vision] '{element_description}' not found: {result.get('reason', '')}")
        return None
    except json.JSONDecodeError:
        return None


def get_element_coordinates_fast(screenshot_path: str, target_description: str) -> dict | None:
    """Downscale to 720p then find element coordinates (fast path)."""
    try:
        img = Image.open(screenshot_path)
        w, h = img.size
        if h > 720:
            img = img.resize((int(w * 720 / h), 720), Image.Resampling.LANCZOS)
            img.save(screenshot_path, quality=75)
    except Exception as e:
        print(f"[Vision] Downscale error: {e}")

    prompt = f'Return ONLY the center coordinates of "{target_description}" as JSON: {{"x": 123, "y": 456}}'
    text = analyze_image(screenshot_path, prompt)
    if not text:
        return None
    try:
        result = _parse_json_response(text)
        if "x" in result and "y" in result:
            return {"x": result["x"], "y": result["y"], "label": target_description, "found": True}
    except json.JSONDecodeError:
        pass
    return None


# ─── Orchestration: Navigator x Pilot ────────────────────────────────────────

LINKEDIN_SYSTEM_PROMPT = """You are GhostAgent, an intelligent LinkedIn navigation assistant.
Decide the SINGLE NEXT ACTION given the current goal, page state, and element tree.

Available actions:
{"action":"click","element":"<label>","x":<x>,"y":<y>}
{"action":"type","element":"<label>","text":"<text>","x":<x>,"y":<y>}
{"action":"scroll","direction":"down|up","amount":<pixels>}
{"action":"wait","seconds":<1-5>}
{"action":"press_key","key":"Enter|Tab|Escape|ArrowDown|ArrowUp"}
{"action":"navigate","url":"<url>"}
{"action":"done","reason":"<why complete or impossible>"}

Rules: Never go directly to profile URLs. Always search → click. View profile before connecting.
Return ONLY valid JSON. No explanation."""

_ax_cache: dict = {"hash": "", "strategy": ""}


def decide_action_orchestrated(goal, ax_tree_yaml, page_description, action_history=None):
    current_hash = hashlib.md5(ax_tree_yaml.encode()).hexdigest()
    if _ax_cache["hash"] == current_hash and _ax_cache["strategy"]:
        print("[Vision] ⚡ Cache hit — skipping Navigator")
        strategy = _ax_cache["strategy"]
    else:
        strategy = _get_navigator_strategy(goal, ax_tree_yaml, page_description, action_history)
        _ax_cache["hash"] = current_hash
        _ax_cache["strategy"] = strategy

    return _execute_pilot_action(strategy, ax_tree_yaml, action_history)


def _get_navigator_strategy(goal, ax_tree_yaml, page_description, action_history=None) -> str:
    history_text = ""
    if action_history:
        history_text = "\n".join([f"  - {json.dumps(a)}" for a in action_history[-8:]])

    prompt = f"""You are the Navigator (Strategy Engine).
Objective: {goal}
Page: {page_description}
History:\n{history_text or "None"}
AXTree:\n{ax_tree_yaml}

Define the NEXT STRATEGIC STEP in one sentence."""

    result = _openai_text(prompt, max_tokens=200)
    if result:
        return result

    return f"Attempt to reach objective: {goal}"


def _execute_pilot_action(strategy, ax_tree_yaml, action_history=None) -> dict:
    prompt = f"""You are the Pilot (Execution Engine).
Strategy: {strategy}
AXTree:\n{ax_tree_yaml}

Pick the exact element from the AXTree. Return ONLY valid JSON action:
{{"action":"click","id":"agent-N"}} or {{"action":"type","id":"agent-N","text":"..."}} etc."""

    for attempt in range(MAX_RETRIES):
        result = _openai_text(prompt, max_tokens=200)
        if result:
            try:
                return _parse_json_response(result)
            except json.JSONDecodeError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)

    return {"action": "wait", "seconds": 2}


def verify_action_async(page, action, expected_outcome) -> dict:
    """Post-action visual verification using OpenAI vision."""
    from browser import take_screenshot
    path = os.path.join(SCREENSHOT_DIR, f"verify_{int(time.time())}.png")
    take_screenshot(page, path)

    prompt = f"""Action taken: {json.dumps(action)}
Expected: {expected_outcome}
Did the action succeed? Any roadblock (modal, error, popup)?
Return ONLY JSON: {{"success":true,"roadblock":false,"details":"..."}}"""

    text = analyze_image(path, prompt)
    if not text:
        return {"success": True, "roadblock": False, "error": "no response"}
    try:
        return _parse_json_response(text)
    except Exception:
        return {"success": True, "roadblock": False, "error": "parse failed"}


def decide_action(goal, page_description, elements, action_history=None) -> dict:
    """Simple single-model action decision."""
    elements_text = json.dumps(elements[:40], indent=2) if elements else "None"
    history_text = "\n".join([f"  {i+1}. {json.dumps(a)}" for i, a in enumerate((action_history or [])[-8:])])

    user_prompt = f"""Goal: {goal}
Page: {page_description}
Elements: {elements_text}
History: {history_text or "None"}
What is the SINGLE next action? Return ONLY JSON."""

    for attempt in range(MAX_RETRIES):
        result = _openai_text(
            user_prompt,
            system_prompt=LINKEDIN_SYSTEM_PROMPT,
            max_tokens=200,
        )
        if result:
            try:
                return _parse_json_response(result)
            except json.JSONDecodeError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)

    return {"action": "wait", "seconds": 2}


def _openai_text(prompt: str, system_prompt: str | None = None, max_tokens: int = 300) -> str:
    if not openai_client:
        return ""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(MAX_RETRIES):
        try:
            resp = openai_client.chat.completions.create(
                model=OPENAI_VISION_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                timeout=20,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[OpenAI/Text] Error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF ** (attempt + 1))

    return ""
