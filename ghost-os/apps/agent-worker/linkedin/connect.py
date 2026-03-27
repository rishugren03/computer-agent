"""LinkedIn connection request workflow.

The full connection flow for a real professional:
1. Navigate to profile (via search, never direct URL)
2. View profile with natural dwell time
3. Click "Connect" → "Add a note" → Type personalized note → Send
4. Respect all guardrails before executing
"""

import random

from human import human_click, human_type, random_delay
from browser import wait_for_stable
from navigator import navigate_to_profile
from linkedin.profile import view_profile, extract_profile_data
from accessibility import extract_act, find_buttons, find_textboxes


def send_connection(page, name, note, guardrails=None):
    """Execute the full connection request workflow.

    Args:
        page: Playwright page (logged in).
        name: Person's name to connect with.
        note: Personalized connection note.
        guardrails: Guardrails instance (for limit checking).

    Returns:
        dict: Result with status and details.
    """
    # Check guardrails
    if guardrails and not guardrails.can_connect():
        return {
            "status": "blocked",
            "reason": "Daily connection limit reached",
        }

    print(f"[Connect] 🤝 Connecting with {name}...")

    # 1. Navigate to their profile (via search)
    navigate_to_profile(page, name)
    wait_for_stable(page, timeout=8000)
    random_delay(1.0, 2.0)

    # 2. View profile with dwell time (builds natural pattern)
    profile_data = view_profile(page, dwell=True)

    # 3. Click the "Connect" button
    success = _click_connect_button(page)
    if not success:
        return {
            "status": "failed",
            "reason": "Could not find Connect button (may already be connected)",
            "profile": profile_data,
        }

    random_delay(0.8, 1.5)

    # 4. Add a note (click "Add a note" button)
    note_added = _add_connection_note(page, note)
    if not note_added:
        # If we can't add a note, still send without one
        print("[Connect] ⚠️  Could not add note, sending without...")
        _click_send_button(page)
    else:
        # 5. Send the request
        random_delay(0.5, 1.0)
        _click_send_button(page)

    # Record the action
    if guardrails:
        guardrails.record_action("connection")

    random_delay(1.0, 2.0)

    return {
        "status": "sent",
        "name": name,
        "note": note,
        "profile": profile_data,
    }


def _click_connect_button(page):
    """Find and click the Connect button on a profile.

    Handles multiple variations:
    - Primary "Connect" button
    - "More" dropdown → "Connect" option
    - "Follow" (already following, need different path)

    Returns:
        bool: True if Connect button was clicked.
    """
    tree = extract_act(page)

    # Try direct "Connect" button first
    connect_buttons = find_buttons(tree, "Connect")
    if connect_buttons:
        from navigator import _click_act_element
        _click_act_element(page, connect_buttons[0])
        wait_for_stable(page, timeout=3000)
        return True

    # Try "More" dropdown which might contain Connect
    more_buttons = find_buttons(tree, "More")
    if more_buttons:
        from navigator import _click_act_element
        _click_act_element(page, more_buttons[0])
        random_delay(0.5, 1.0)
        wait_for_stable(page, timeout=2000)

        # Re-extract ACT after dropdown opens
        tree = extract_act(page)
        connect_items = find_buttons(tree, "Connect")
        if connect_items:
            _click_act_element(page, connect_items[0])
            wait_for_stable(page, timeout=3000)
            return True

    # Check if "Pending" is shown (already sent request)
    pending = find_buttons(tree, "Pending")
    if pending:
        print("[Connect] ⏳ Connection request already pending")
        return False

    # Check if "Message" is shown (already connected)
    message = find_buttons(tree, "Message")
    if message:
        print("[Connect] ✅ Already connected")
        return False

    print("[Connect] ❌ Could not find Connect button")
    return False


def _add_connection_note(page, note):
    """Click 'Add a note' and type the personalized connection message.

    Returns:
        bool: True if note was successfully added.
    """
    tree = extract_act(page)

    # Find "Add a note" button in the connection modal
    add_note_buttons = find_buttons(tree, "Add a note")
    if not add_note_buttons:
        add_note_buttons = find_buttons(tree, "add a note")

    if add_note_buttons:
        from navigator import _click_act_element
        _click_act_element(page, add_note_buttons[0])
        random_delay(0.5, 1.0)
        wait_for_stable(page, timeout=2000)

        # Find the note text area
        tree = extract_act(page)
        textboxes = find_textboxes(tree, None)

        if textboxes:
            _click_act_element(page, textboxes[0])
            random_delay(0.3, 0.5)
            human_type(page, note)
            return True
        else:
            # Fallback: try typing directly (modal might auto-focus)
            human_type(page, note)
            return True

    return False


def _click_send_button(page):
    """Click the Send button to submit the connection request."""
    tree = extract_act(page)

    send_buttons = find_buttons(tree, "Send")
    if not send_buttons:
        send_buttons = find_buttons(tree, "Send now")

    if send_buttons:
        from navigator import _click_act_element
        _click_act_element(page, send_buttons[0])
        wait_for_stable(page, timeout=3000)
        print("[Connect] ✅ Connection request sent!")
        return True

    # Fallback: press Enter (some modals accept Enter to submit)
    page.keyboard.press("Enter")
    random_delay(0.5, 1.0)
    return True
