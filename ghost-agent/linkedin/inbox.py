"""Smart LinkedIn inbox management.

Handles:
- Reading unread messages
- Classifying message intent (thanks, interested, not interested, question)
- Auto-replying to routine messages
- Flagging actual leads for human follow-up
"""

import random

from human import human_type, human_click, random_delay, dwell_on_content
from browser import wait_for_stable
from navigator import navigate_to_messaging
from accessibility import extract_act, find_by_text, find_buttons, find_textboxes
from vision import describe_page


# Message classification categories
INTENT_THANKS = "thanks"
INTENT_INTERESTED = "interested"
INTENT_NOT_INTERESTED = "not_interested"
INTENT_QUESTION = "question"
INTENT_UNKNOWN = "unknown"

# Keywords for basic classification (LLM handles complex cases)
THANKS_KEYWORDS = [
    "thanks for connecting", "thank you for connecting",
    "thanks for the connection", "great connecting",
    "nice to connect", "pleased to connect",
    "happy to connect", "glad to connect",
]

INTERESTED_KEYWORDS = [
    "interested", "tell me more", "would love to",
    "let's chat", "let's schedule", "free for a call",
    "sounds great", "available", "how can you help",
    "what do you offer", "pricing",
]

NOT_INTERESTED_KEYWORDS = [
    "not interested", "no thanks", "no thank you",
    "please remove", "unsubscribe", "stop messaging",
    "not looking", "don't contact",
]


def get_unread_messages(page):
    """Navigate to inbox and extract unread message threads.

    Returns:
        list[dict]: Unread threads with sender, preview, and status.
    """
    navigate_to_messaging(page)
    wait_for_stable(page, timeout=5000)
    random_delay(1.0, 2.0)

    # Extract message threads
    try:
        threads = page.evaluate("""() => {
            const results = [];
            
            // LinkedIn messaging thread list
            const threadItems = document.querySelectorAll(
                '.msg-conversation-listitem, [data-control-name="overlay.list_conversation"]'
            );
            
            for (const item of Array.from(threadItems).slice(0, 20)) {
                const nameEl = item.querySelector('h3, .msg-conversation-listitem__participant-names');
                const previewEl = item.querySelector('p, .msg-conversation-listitem__message-snippet');
                const unreadIndicator = item.querySelector('.msg-conversation-listitem__unread-count, .notification-badge');
                
                const name = nameEl ? nameEl.innerText.trim() : '';
                const preview = previewEl ? previewEl.innerText.trim() : '';
                const isUnread = !!unreadIndicator;
                
                if (name) {
                    results.push({
                        name: name,
                        preview: preview.substring(0, 200),
                        is_unread: isUnread,
                    });
                }
            }
            
            return results;
        }""")

        unread = [t for t in threads if t.get("is_unread", False)]
        print(f"[Inbox] Found {len(unread)} unread messages (of {len(threads)} total)")
        return unread

    except Exception as e:
        print(f"[Inbox] Error extracting messages: {e}")
        return []


def classify_message(message_text):
    """Classify a message's intent using keyword matching.

    For complex cases, the ghostwriter LLM handles classification.

    Args:
        message_text: The message content.

    Returns:
        str: One of INTENT_* categories.
    """
    lower = message_text.lower().strip()

    # Check for "thanks for connecting" patterns (most common)
    for keyword in THANKS_KEYWORDS:
        if keyword in lower:
            return INTENT_THANKS

    # Check for interest signals
    for keyword in INTERESTED_KEYWORDS:
        if keyword in lower:
            return INTENT_INTERESTED

    # Check for rejection signals
    for keyword in NOT_INTERESTED_KEYWORDS:
        if keyword in lower:
            return INTENT_NOT_INTERESTED

    # Check if it's a question
    if "?" in message_text:
        return INTENT_QUESTION

    return INTENT_UNKNOWN


def open_thread(page, sender_name):
    """Open a specific message thread by sender name.

    Args:
        page: Playwright page (should be on messaging).
        sender_name: Name of the person to open thread with.

    Returns:
        bool: True if thread was opened.
    """
    tree = extract_act(page)
    thread_links = find_by_text(tree, sender_name)

    if thread_links:
        from navigator import _click_act_element
        _click_act_element(page, thread_links[0])
        wait_for_stable(page, timeout=3000)
        random_delay(1.0, 2.0)
        return True

    # Try scrolling down to find the thread
    for _ in range(3):
        from human import human_scroll
        human_scroll(page, "down", random.randint(200, 300))
        wait_for_stable(page, timeout=2000)

        tree = extract_act(page)
        thread_links = find_by_text(tree, sender_name)
        if thread_links:
            _click_act_element(page, thread_links[0])
            wait_for_stable(page, timeout=3000)
            return True

    print(f"[Inbox] Could not find thread with {sender_name}")
    return False


def auto_reply(page, reply_text):
    """Send a reply in the currently open message thread.

    Args:
        page: Playwright page (should have a thread open).
        reply_text: The reply message.

    Returns:
        bool: True if reply was sent.
    """
    # "Read" the conversation first
    dwell_on_content(page, random.randint(20, 50))

    # Find the message input
    tree = extract_act(page)
    msg_inputs = find_textboxes(tree, None)

    # Filter for the message input (usually labeled "Write a message...")
    msg_input = None
    for inp in msg_inputs:
        name = inp.get("name", "").lower()
        if "message" in name or "write" in name:
            msg_input = inp
            break

    if not msg_input and msg_inputs:
        msg_input = msg_inputs[-1]  # Last textbox is usually the message input

    if msg_input:
        from navigator import _click_act_element
        _click_act_element(page, msg_input)
        random_delay(0.3, 0.5)

        human_type(page, reply_text)
        random_delay(0.5, 1.0)

        # Send the message
        page.keyboard.press("Enter")
        wait_for_stable(page, timeout=3000)
        print("[Inbox] ✉️  Reply sent!")
        return True

    print("[Inbox] Could not find message input")
    return False


def process_inbox(page, reply_generator=None, guardrails=None):
    """Process all unread messages in the inbox.

    - Auto-reply to "thanks" messages with a personalized question
    - Flag interested replies for human follow-up
    - Skip/ignore not-interested messages
    - Queue unknown messages for human review

    Args:
        page: Playwright page.
        reply_generator: Function to generate replies.
            Signature: (sender_name: str, message: str, intent: str) -> str | None
        guardrails: Guardrails instance for limit checking.

    Returns:
        dict: Processing summary.
    """
    summary = {
        "total": 0,
        "auto_replied": 0,
        "flagged_leads": [],
        "skipped": 0,
    }

    unread = get_unread_messages(page)
    summary["total"] = len(unread)

    if not unread:
        print("[Inbox] No unread messages")
        return summary

    for thread in unread:
        name = thread["name"]
        preview = thread["preview"]
        intent = classify_message(preview)

        print(f"[Inbox] {name}: [{intent}] {preview[:50]}...")

        # Check message rate limit
        if guardrails and not guardrails.can_message():
            print("[Inbox] Daily message limit reached, stopping")
            break

        if intent == INTENT_THANKS:
            # Auto-reply with a personalized question
            if reply_generator:
                reply = reply_generator(name, preview, intent)
                if reply and open_thread(page, name):
                    if auto_reply(page, reply):
                        summary["auto_replied"] += 1
                        if guardrails:
                            guardrails.record_action("message")
                    # Go back to inbox
                    navigate_to_messaging(page)
                    random_delay(1.0, 2.0)

        elif intent == INTENT_INTERESTED:
            # Flag for human follow-up — don't auto-reply
            summary["flagged_leads"].append({
                "name": name,
                "preview": preview,
                "intent": intent,
            })
            print(f"[Inbox] 🎯 LEAD FLAGGED: {name}")

        elif intent == INTENT_NOT_INTERESTED:
            # Skip — don't reply
            summary["skipped"] += 1

        elif intent == INTENT_QUESTION:
            # Flag for human review (questions need thoughtful answers)
            summary["flagged_leads"].append({
                "name": name,
                "preview": preview,
                "intent": intent,
            })

        random_delay(1.0, 3.0)

    return summary
