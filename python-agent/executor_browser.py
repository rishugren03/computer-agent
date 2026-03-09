"""Execute browser actions with human-like behavior.

Supports: click, type, select_option, press_key, scroll, wait, hover, go_back, done.
"""

from human import human_click, human_type, random_delay
import time


def execute(page, action, elements):
    """Execute a browser action and return a result message.
    
    Returns:
        str: Description of what happened (success or error message).
    """

    action_type = action.get("action", "")

    try:
        if action_type == "click":
            return _do_click(page, action, elements)

        elif action_type == "type":
            return _do_type(page, action, elements)

        elif action_type == "select_option":
            return _do_select(page, action, elements)

        elif action_type == "press_key":
            return _do_press_key(page, action)

        elif action_type == "scroll":
            return _do_scroll(page, action)

        elif action_type == "wait":
            return _do_wait(action)

        elif action_type == "hover":
            return _do_hover(page, action, elements)

        elif action_type == "go_back":
            page.go_back(wait_until="domcontentloaded")
            return "Navigated back"

        elif action_type == "done":
            return f"Done: {action.get('reason', 'Goal achieved')}"

        else:
            return f"Unknown action type: {action_type}"

    except Exception as e:
        return f"Action '{action_type}' failed: {str(e)}"


def _get_element(action, elements):
    """Get the element dict by ID from the elements list."""
    element_id = action.get("id")
    if element_id is None:
        raise ValueError("No element ID provided")
    if element_id < 0 or element_id >= len(elements):
        raise ValueError(f"Element ID {element_id} out of range (0-{len(elements)-1})")
    return elements[element_id]


def _click_element(page, el):
    """Click an element using bbox coordinates (human-like) or fallback to selector."""
    bbox = el.get("bbox")
    if bbox and bbox.get("w", 0) > 0 and bbox.get("h", 0) > 0:
        center_x = bbox["x"] + bbox["w"] / 2
        center_y = bbox["y"] + bbox["h"] / 2
        human_click(page, center_x, center_y)
    else:
        page.locator(el["selector"]).first.click()


def _do_click(page, action, elements):
    """Handle click action."""
    el = _get_element(action, elements)
    _click_element(page, el)
    desc = el.get("text", "") or el.get("ariaLabel", "") or el.get("placeholder", "") or el["selector"]
    return f"Clicked '{desc[:50]}'"


def _do_type(page, action, elements):
    """Handle type action — click to focus, clear existing text, type new text.
    
    Does NOT press Enter automatically — the LLM should send a separate
    press_key action if Enter is needed.
    """
    el = _get_element(action, elements)
    text = action.get("text", "")
    bbox = el.get("bbox")

    if bbox and bbox.get("w", 0) > 0 and bbox.get("h", 0) > 0:
        # Human-like: click to focus, select all existing text, then type
        center_x = bbox["x"] + bbox["w"] / 2
        center_y = bbox["y"] + bbox["h"] / 2
        human_click(page, center_x, center_y)
        random_delay(0.2, 0.4)

        # Select all existing text and delete it
        page.keyboard.press("Control+a")
        random_delay(0.05, 0.1)
        page.keyboard.press("Backspace")
        random_delay(0.1, 0.2)

        # Type the new text with human-like delays
        human_type(page, text)
    else:
        # Fallback: use Playwright selectors
        tag = el.get("tag", "").upper()
        selector = el["selector"]
        if tag in ("INPUT", "TEXTAREA"):
            page.locator(selector).first.fill(text)
        else:
            page.locator(selector).first.click()
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
            page.keyboard.type(text)

    return f"Typed '{text}' into '{el.get('placeholder', '') or el.get('ariaLabel', '') or el['selector'][:30]}'"


def _do_select(page, action, elements):
    """Handle select_option action for <select> elements."""
    el = _get_element(action, elements)
    value = action.get("value", "")
    selector = el["selector"]

    # Try selecting by label text first
    try:
        page.locator(selector).first.select_option(label=value)
        return f"Selected '{value}'"
    except Exception:
        pass

    # Try selecting by value
    try:
        page.locator(selector).first.select_option(value=value)
        return f"Selected value '{value}'"
    except Exception as e:
        return f"select_option failed: {str(e)}"


def _do_press_key(page, action):
    """Handle press_key action."""
    key = action.get("key", "Enter")
    page.keyboard.press(key)
    return f"Pressed '{key}'"


def _do_scroll(page, action):
    """Handle scroll action."""
    direction = action.get("direction", "down")
    amount = action.get("amount", 300)

    if direction == "down":
        page.mouse.wheel(0, amount)
    elif direction == "up":
        page.mouse.wheel(0, -amount)

    return f"Scrolled {direction} by {amount}px"


def _do_wait(action):
    """Handle explicit wait action."""
    seconds = min(action.get("seconds", 2), 10)  # Cap at 10s
    time.sleep(seconds)
    return f"Waited {seconds}s"


def _do_hover(page, action, elements):
    """Handle hover action."""
    el = _get_element(action, elements)
    bbox = el.get("bbox")
    if bbox and bbox.get("w", 0) > 0 and bbox.get("h", 0) > 0:
        center_x = bbox["x"] + bbox["w"] / 2
        center_y = bbox["y"] + bbox["h"] / 2
        page.mouse.move(center_x, center_y)
    else:
        page.locator(el["selector"]).first.hover()

    desc = el.get("text", "") or el.get("ariaLabel", "") or el["selector"]
    return f"Hovered over '{desc[:50]}'"