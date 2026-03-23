"""Vision engine using Gemini + DeepSeek for page understanding.

Uses Gemini 2.0 Flash for visual analysis (screenshot → element detection)
and DeepSeek for text-based action decisions. No local VLM dependency.
"""

import os
import json
import time
from PIL import Image
from google import genai
from openai import OpenAI
from dotenv import load_dotenv

from config import (
    GEMINI_API_KEY,
    GEMINI_FAST_MODEL,
    SCREENSHOT_DIR,
)

load_dotenv()

# ─── Gemini Vision Client ───────────────────────────────────────────────────

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# (No DeepSeek client anymore - using Gemini for all interactions)

# ─── Retry Config ───────────────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # Exponential backoff multiplier


# ─── Vision: Screenshot Analysis ────────────────────────────────────────────

LINKEDIN_ELEMENT_DETECTION_PROMPT = """You are analyzing a LinkedIn page screenshot.
Identify all interactive UI elements visible on the page.

For EACH element, return:
- type: the element type (button, link, input, dropdown, tab, icon, etc.)
- label: the visible text or icon description
- x: approximate center x coordinate (in pixels from left)
- y: approximate center y coordinate (in pixels from top)
- purpose: what this element likely does (e.g., "send connection request", "open messaging", "search people")

Focus on these LinkedIn-specific elements:
- Navigation: Home, My Network, Jobs, Messaging, Notifications, Me
- Profile: Connect, Follow, Message, More, Pending
- Feed: Like, Comment, Repost, Send, Post creation
- Search: Search bar, filters, People/Posts/Companies tabs
- Messaging: Message input, send button, compose
- Modals: Connection note textarea, Send/Cancel buttons

Return ONLY valid JSON array. No explanation, no markdown.
Example:
[
  {"type": "button", "label": "Connect", "x": 450, "y": 320, "purpose": "send connection request"},
  {"type": "input", "label": "Search", "x": 640, "y": 45, "purpose": "search people/content"}
]
"""

PAGE_DESCRIPTION_PROMPT = """Describe this LinkedIn page screenshot concisely.

Include:
1. What page type is this? (feed, profile, search results, messaging, etc.)
2. Key content visible (names, headlines, post content summaries)
3. Current state (any modals open? dropdowns? notifications?)
4. Notable elements (connection status, pending invitations, new messages)

Be factual and specific. Focus on information useful for an agent navigating LinkedIn.
"""

POST_CONTENT_PROMPT = """Analyze this LinkedIn post screenshot.

Extract:
1. Author name and headline
2. Post content (full text)
3. Engagement metrics (likes, comments, reposts)
4. Time posted
5. Key topics or themes
6. Tone (professional, casual, inspirational, technical)

Return as JSON:
{"author": "", "headline": "", "content": "", "likes": 0, "comments": 0, "time": "", "topics": [], "tone": ""}
"""


def detect_elements(screenshot_path):
    """Use Gemini Vision to identify interactive elements in a screenshot.

    This is Layer 1 (The Eyes) of the Zero-Shot Brain.
    When the ACT/semantic cache misses, vision identifies elements
    by their visual appearance.

    Args:
        screenshot_path: Path to the screenshot image.

    Returns:
        list[dict]: Detected elements with type, label, x, y, purpose.
    """
    response_text = analyze_image(screenshot_path, LINKEDIN_ELEMENT_DETECTION_PROMPT)
    if not response_text:
        return []

    try:
        # Clean response — sometimes models wrap in ```json blocks
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        elements = json.loads(cleaned)
        return elements if isinstance(elements, list) else []
    except json.JSONDecodeError as e:
        print(f"[Vision] Failed to parse element detection response: {e}")
        return []


def describe_page(screenshot_path):
    """Get a natural language description of the current LinkedIn page.

    Used to give the LLM context about what's on screen.

    Returns:
        str: Page description.
    """
    return analyze_image(screenshot_path, PAGE_DESCRIPTION_PROMPT) or ""


def analyze_post(screenshot_path):
    """Extract structured data from a LinkedIn post screenshot.

    Returns:
        dict: Post data (author, content, engagement, etc.)
    """
    response_text = analyze_image(screenshot_path, POST_CONTENT_PROMPT)
    if not response_text:
        return {}

    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"content": response_text}


def analyze_image(image_path, prompt):
    """Send a screenshot + text prompt to Gemini Vision.

    Includes retry with exponential backoff for rate limits.

    Args:
        image_path: Path to the image file.
        prompt: Text prompt for analysis.

    Returns:
        str: Model's text response, or empty string on failure.
    """
    for attempt in range(MAX_RETRIES):
        try:
            img = Image.open(image_path)
            response = gemini_client.models.generate_content(
                model=GEMINI_FAST_MODEL,
                contents=[prompt, img],
            )
            return response.text
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF ** (attempt + 1)
                print(f"[Vision] Retry {attempt + 1}/{MAX_RETRIES} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"[Vision] Failed after {MAX_RETRIES} attempts: {e}")
                return ""


def find_element_by_vision(page, element_description):
    """Use Gemini Vision to find a specific element on the page.

    Takes a screenshot and asks the vision model to locate the element.
    This is the fallback when DOM/ACT selectors fail.

    Args:
        page: Playwright page.
        element_description: What to find (e.g., "Like button", "Connect button").

    Returns:
        dict | None: {x, y, label} if found, None if not.
    """
    from browser import take_screenshot

    screenshot_path = take_screenshot(page, os.path.join(SCREENSHOT_DIR, "vision_find.png"))

    prompt = f"""Look at this LinkedIn page screenshot.
Find the "{element_description}" element.

Return ONLY a JSON object with the element's center coordinates:
{{"x": <pixels from left>, "y": <pixels from top>, "label": "<what you found>", "found": true}}

If the element is NOT visible on the page, return:
{{"found": false, "reason": "<why not found>"}}

Return ONLY valid JSON. No explanation."""

    response_text = analyze_image(screenshot_path, prompt)
    if not response_text:
        return None

    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        result = json.loads(cleaned)
        if result.get("found", False):
            return result
    except json.JSONDecodeError:
        print(f"[Vision] Could not parse response for '{element_description}'")
        return None

def get_element_coordinates_fast(screenshot_path, target_description):
    """Vision-Coordinate Module for Speculative Execution.
    
    Downscales screenshot to 720p to save tokens and latency, then
    asks Flash-Lite for coordinates.
    """
    # Downscale image to 720p height (maintaining aspect ratio)
    try:
        img = Image.open(screenshot_path)
        # Calculate aspect ratio
        w, h = img.size
        # Limit height to 720p
        target_h = 720
        if h > target_h:
            target_w = int(w * (target_h / h))
            img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            img.save(screenshot_path)
    except Exception as e:
        print(f"[Vision] Error downscaling screenshot: {e}")

    prompt = f"Return ONLY the [x, y] center coordinates of the {target_description} in JSON format: {{'x': 123, 'y': 456}}."
    
    response_text = analyze_image(screenshot_path, prompt)
    if not response_text:
        return None

    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        result = json.loads(cleaned)
        if "x" in result and "y" in result:
            return {"x": result["x"], "y": result["y"], "label": target_description, "found": True}
        return None
    except json.JSONDecodeError:
        return None


# ─── DeepSeek Text: Action Decisions ────────────────────────────────────────

LINKEDIN_SYSTEM_PROMPT = """You are GhostAgent, an intelligent LinkedIn navigation assistant.
You receive:
1. The current goal/objective
2. A description of the current page (from vision)
3. A list of interactive elements (from ACT + vision)
4. History of recent actions

Your job is to decide the SINGLE NEXT ACTION to take.

## Available Actions
```json
{"action": "click", "element": "<element label or description>", "x": <x>, "y": <y>}
{"action": "type", "element": "<element label>", "text": "<text to type>", "x": <x>, "y": <y>}
{"action": "scroll", "direction": "down|up", "amount": <pixels>}
{"action": "wait", "seconds": <1-5>}
{"action": "press_key", "key": "Enter|Tab|Escape|ArrowDown|ArrowUp"}
{"action": "navigate", "url": "<url>"}
{"action": "done", "reason": "<why the goal is achieved or impossible>"}
```

## Rules for LinkedIn
1. Prioritize **Speed of Action**. Do not wait for images to load if the buttons are visible.
2. If a modal pops up (e.g., 'Verification' or 'Feedback'), handle it instantly using Vision rather than crashing.
3. Keep the conversation history short. Clear the token buffer every 5 actions to keep latency at 'Flash-Lite' peak performance.
4. NEVER go directly to a profile URL. Always use search → click.
5. Before connecting, always VIEW the profile first (scroll through it).
6. When typing connection notes, be genuine and personalized.
7. Prefer using visible element labels over coordinates when possible.
8. If stuck, try scrolling or pressing Escape to dismiss overlays.

## Response Format
Return ONLY valid JSON. No explanation, no markdown, no extra text.
"""


def decide_action(goal, page_description, elements, action_history=None):
    """Ask DeepSeek to decide the next action based on current context.

    This is the decision brain of GhostAgent — it looks at the page,
    understands the goal, and picks the most natural next step.

    Args:
        goal: Current objective (e.g., "connect with John Doe").
        page_description: Vision-generated page description.
        elements: List of interactive elements (ACT + vision merged).
        action_history: List of recent actions taken.

    Returns:
        dict: Action to execute.
    """
    # Build the user prompt with current context
    elements_text = json.dumps(elements[:40], indent=2) if elements else "No elements detected"

    history_text = ""
    if action_history:
        recent = action_history[-8:]  # Last 8 actions
        history_text = "\n".join([f"  {i+1}. {json.dumps(a)}" for i, a in enumerate(recent)])

    user_prompt = f"""## Current Goal
{goal}

## Current Page
{page_description}

## Interactive Elements
{elements_text}

## Recent Action History
{history_text if history_text else "No actions yet (starting fresh)"}

What is the SINGLE next action to take? Return ONLY JSON."""

    for attempt in range(MAX_RETRIES):
        try:
            prompt_content = f"{LINKEDIN_SYSTEM_PROMPT}\n\n{user_prompt}"
            response = gemini_client.models.generate_content(
                model=GEMINI_FAST_MODEL,
                contents=prompt_content,
            )

            text = response.text.strip()

            # Clean JSON from markdown blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            print(f"[LLM] Invalid JSON from DeepSeek: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                return {"action": "wait", "seconds": 2}
        except Exception as e:
            print(f"[LLM] DeepSeek error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF ** (attempt + 1))
            else:
                return {"action": "wait", "seconds": 2}
