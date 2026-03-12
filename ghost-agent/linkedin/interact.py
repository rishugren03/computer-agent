"""LinkedIn post interaction engine.

Handles organic engagement with prospects' content:
- Like posts with natural scroll + click
- Leave context-aware comments
- Find recent posts from a profile
- Post-Interaction Hook: engage with prospect's post BEFORE connecting
"""

import random
import time

from human import (
    human_click,
    human_move_to,
    human_type,
    human_scroll,
    random_delay,
    dwell_on_content,
    idle_fidget,
)
from browser import wait_for_stable
from accessibility import extract_act, find_buttons, find_textboxes, find_by_text
from linkedin.auth import check_session_or_relogin


def _fast_click_like(page):
    """Click the Like button on LinkedIn, handling the reaction popup.

    Detection chain: DOM → Playwright Locator → ACT → Gemini Vision
    After finding the button, hovers with Bézier (triggering reaction popup),
    then clicks a reaction emoji from the popup.

    Returns:
        bool: True if a reaction was clicked.
    """
    print("[Interact] ── Like Button Search ──")
    cx, cy = None, None
    method_used = "none"

    # ─── Strategy 1: DOM querySelector ────────────────────────────────
    print("[Interact] [1/4] Trying DOM selectors...")
    try:
        like_info = page.evaluate("""() => {
            const results = [];

            // Scan ALL buttons and roles
            const allEls = document.querySelectorAll('button, [role="button"], span[class*="reaction"], div[class*="reaction"]');

            for (const el of allEls) {
                const text = (el.innerText || '').trim();
                const label = el.getAttribute('aria-label') || '';
                const pressed = el.getAttribute('aria-pressed');
                const rect = el.getBoundingClientRect();

                // Log what we find for debugging
                if (text.toLowerCase().includes('like') || label.toLowerCase().includes('like')) {
                    results.push({
                        text: text.substring(0, 50),
                        label: label.substring(0, 50),
                        pressed: pressed,
                        tag: el.tagName,
                        classes: el.className?.substring?.(0, 80) || '',
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2,
                        width: rect.width,
                        height: rect.height,
                        visible: rect.width > 0 && rect.height > 0 && rect.top > 0 && rect.top < window.innerHeight,
                    });
                }
            }

            return results;
        }""")

        print(f"[Interact]   DOM found {len(like_info)} elements containing 'like':")
        for i, el in enumerate(like_info):
            print(f"[Interact]     [{i}] tag={el['tag']} text='{el['text']}' label='{el['label']}' "
                  f"pressed={el['pressed']} visible={el['visible']} "
                  f"pos=({el['x']:.0f},{el['y']:.0f}) size={el['width']:.0f}x{el['height']:.0f}")
            print(f"[Interact]          classes='{el['classes']}'")

        # Pick the first visible, not-already-liked button
        for el in like_info:
            if el["visible"] and el["pressed"] != "true" and el["width"] > 10:
                cx, cy = el["x"], el["y"]
                method_used = "DOM"
                print(f"[Interact]   ✅ Selected: text='{el['text']}' at ({cx:.0f},{cy:.0f})")
                break

        if cx is None and like_info:
            print("[Interact]   ⚠️ Found elements but none are visible/clickable")

    except Exception as e:
        print(f"[Interact]   ❌ DOM search error: {e}")

    # ─── Strategy 2: Playwright role locator ──────────────────────────
    if cx is None:
        print("[Interact] [2/4] Trying Playwright role locator...")
        try:
            locator = page.get_by_role("button", name="Like", exact=True)
            count = locator.count()
            print(f"[Interact]   Found {count} elements with role=button, name='Like'")
            if count > 0:
                bbox = locator.first.bounding_box()
                if bbox:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    method_used = "Playwright"
                    print(f"[Interact]   ✅ Located at ({cx:.0f},{cy:.0f})")
                else:
                    print("[Interact]   ⚠️ Element exists but has no bounding box")
        except Exception as e:
            print(f"[Interact]   ❌ Locator error: {e}")

    # ─── Strategy 3: ACT (Accessibility Tree) ─────────────────────────
    if cx is None:
        print("[Interact] [3/4] Trying Accessibility Tree (ACT)...")
        try:
            tree = extract_act(page)
            like_btns = find_buttons(tree, "Like")
            print(f"[Interact]   ACT found {len(like_btns)} buttons matching 'Like':")
            for i, btn in enumerate(like_btns):
                print(f"[Interact]     [{i}] role={btn.get('role')} name='{btn.get('name')}' path={btn.get('path','')[:60]}")

            if like_btns:
                for btn in like_btns:
                    btn_name = btn.get("name", "Like")
                    try:
                        loc = page.get_by_role("button", name=btn_name)
                        if loc.count() > 0:
                            bbox = loc.first.bounding_box()
                            if bbox:
                                cx = bbox["x"] + bbox["width"] / 2
                                cy = bbox["y"] + bbox["height"] / 2
                                method_used = "ACT"
                                print(f"[Interact]   ✅ ACT → Located '{btn_name}' at ({cx:.0f},{cy:.0f})")
                                break
                    except Exception:
                        continue
        except Exception as e:
            print(f"[Interact]   ❌ ACT error: {e}")

    # ─── Strategy 4: Gemini Vision ────────────────────────────────────
    if cx is None:
        print("[Interact] [4/4] Trying Gemini Vision fallback...")
        try:
            from vision import find_element_by_vision
            result = find_element_by_vision(page, "Like button on a LinkedIn post (the thumbs-up Like button in the social action bar below a post)")
            if result:
                cx = result["x"]
                cy = result["y"]
                method_used = "Vision"
                print(f"[Interact]   ✅ Vision found: '{result.get('label', '')}' at ({cx:.0f},{cy:.0f})")
            else:
                print("[Interact]   ❌ Vision could not find Like button either")
        except Exception as e:
            print(f"[Interact]   ❌ Vision error: {e}")

    # ─── No method found the button ───────────────────────────────────
    if cx is None:
        print("[Interact] ❌ ALL 4 STRATEGIES FAILED — could not find Like button")
        return False

    print(f"[Interact] ── Clicking Like via {method_used} at ({cx:.0f},{cy:.0f}) ──")

    # ─── Step 2: Hover with Bézier (triggers reaction popup) ──────────
    print("[Interact] Moving to Like button with Bézier curve...")
    human_move_to(page, cx, cy)

    # ─── Step 3: Wait for reaction popup ──────────────────────────────
    wait_time = random.uniform(0.6, 0.9)
    print(f"[Interact] Waiting {wait_time:.2f}s for reaction popup...")
    time.sleep(wait_time)

    # ─── Step 4: Click a reaction emoji from the popup ────────────────
    reaction_names = ["Like", "Celebrate", "Support", "Love", "Insightful", "Funny"]

    if random.random() < 0.8:
        target_reaction = "Like"
    else:
        target_reaction = random.choice(reaction_names)
    print(f"[Interact] Target reaction: {target_reaction}")

    reaction_clicked = False

    # 4A: Try DOM selectors for popup emojis
    print("[Interact] [Popup 1/3] Searching for reaction popup via DOM...")
    try:
        popup_info = page.evaluate("""() => {
            const results = [];
            // Reaction popup buttons — they're usually in a floating bar above the Like button
            const candidates = document.querySelectorAll(
                'button[aria-label], [role="button"][aria-label], ' +
                '[class*="reaction"] button, [class*="reaction"] [role="button"]'
            );
            for (const el of candidates) {
                const label = el.getAttribute('aria-label') || '';
                const rect = el.getBoundingClientRect();
                if (label && rect.width > 0 && rect.height > 0 && rect.width < 80) {
                    results.push({
                        label: label,
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2,
                        width: rect.width,
                        height: rect.height,
                    });
                }
            }
            return results;
        }""")

        print(f"[Interact]   Found {len(popup_info)} popup candidates")
        for el in popup_info:
            print(f"[Interact]     label='{el['label']}' at ({el['x']:.0f},{el['y']:.0f})")

        # Filter to only elements near the Like button (reaction popup appears ~50-100px above)
        nearby = [el for el in popup_info if abs(el["y"] - cy) < 120 and el["x"] > cx - 200 and el["x"] < cx + 300]
        print(f"[Interact]   {len(nearby)} candidates near Like button (y≈{cy:.0f})")

        # Find the target reaction — use EXACT label match to avoid "Love" matching "Lovely"
        for name in [target_reaction] + reaction_names:
            for el in nearby:
                if el["label"].strip().lower() == name.lower():
                    rx, ry = el["x"], el["y"]
                    print(f"[Interact]   ✅ Clicking popup emoji '{el['label']}' at ({rx:.0f},{ry:.0f})")
                    page.mouse.move(rx, ry)
                    time.sleep(random.uniform(0.05, 0.15))
                    page.mouse.click(rx, ry)
                    reaction_clicked = True
                    print(f"[Interact] 👍 Reacted with: {el['label']}")
                    break
            if reaction_clicked:
                break

    except Exception as e:
        print(f"[Interact]   ❌ Popup DOM error: {e}")

    # 4B: ACT on the popup
    if not reaction_clicked:
        print("[Interact] [Popup 2/3] Searching popup via ACT...")
        try:
            tree = extract_act(page)
            for name in [target_reaction] + reaction_names:
                popup_btns = find_buttons(tree, name)
                if popup_btns:
                    btn = popup_btns[0]
                    btn_name = btn.get("name", name)
                    print(f"[Interact]   ACT found popup button: '{btn_name}'")
                    loc = page.get_by_role("button", name=btn_name)
                    if loc.count() > 0:
                        r_bbox = loc.first.bounding_box()
                        if r_bbox:
                            rx = r_bbox["x"] + r_bbox["width"] / 2
                            ry = r_bbox["y"] + r_bbox["height"] / 2
                            page.mouse.move(rx, ry)
                            time.sleep(random.uniform(0.05, 0.12))
                            page.mouse.click(rx, ry)
                            reaction_clicked = True
                            print(f"[Interact] 👍 Reacted with: {btn_name} (via ACT popup)")
                            break
        except Exception as e:
            print(f"[Interact]   ❌ Popup ACT error: {e}")

    # 4C: Vision on the popup
    if not reaction_clicked:
        print("[Interact] [Popup 3/3] Searching popup via Vision...")
        try:
            from vision import find_element_by_vision
            result = find_element_by_vision(page, "Like emoji (thumbs up) in the reaction popup that appeared above the Like button")
            if result:
                rx, ry = result["x"], result["y"]
                print(f"[Interact]   ✅ Vision found popup emoji at ({rx:.0f},{ry:.0f})")
                page.mouse.move(rx, ry)
                time.sleep(random.uniform(0.05, 0.12))
                page.mouse.click(rx, ry)
                reaction_clicked = True
                print(f"[Interact] 👍 Reacted via Vision popup")
        except Exception as e:
            print(f"[Interact]   ❌ Popup Vision error: {e}")

    # 4D: Last resort — just click the original Like button position
    if not reaction_clicked:
        print(f"[Interact] [Popup FALLBACK] Clicking original Like position ({cx:.0f},{cy:.0f})")
        page.mouse.click(cx, cy)
        reaction_clicked = True
        print("[Interact] 👍 Clicked Like (direct fallback)")

    random_delay(0.5, 1.5)
    print(f"[Interact] ── Like Complete (method={method_used}, reaction={reaction_clicked}) ──")
    return reaction_clicked


def like_post(page, scroll_first=True):
    """Like the post currently in view.

    LinkedIn-specific: The Like button shows a reaction emoji popup
    when hovered for >500ms. We use a FAST direct click to avoid
    triggering the popup. If it still appears, we click the 👍 emoji.

    Args:
        page: Playwright page.
        scroll_first: If True, scroll down a bit before liking.

    Returns:
        bool: True if like was successful.
    """
    if scroll_first:
        human_scroll(page, "down", random.randint(100, 200))
        wait_for_stable(page, timeout=2000)

    # "Read" the post before liking (don't just spam likes)
    dwell_on_content(page, random.randint(30, 120))

    return _fast_click_like(page)


def comment_on_post(page, comment_text):
    """Leave a comment on the post currently in view.

    Flow: Click "Comment" → Wait for input → Type comment → Post
    Includes natural reading dwell before commenting.

    Args:
        page: Playwright page.
        comment_text: The comment to leave.

    Returns:
        bool: True if comment was posted.
    """
    # Read the post first (humans read before commenting)
    dwell_on_content(page, random.randint(50, 150))

    # 1. Click the Comment button to open the comment input
    tree = extract_act(page)
    comment_buttons = find_buttons(tree, "Comment")

    if not comment_buttons:
        print("[Interact] Could not find Comment button")
        return False

    from navigator import _click_act_element
    _click_act_element(page, comment_buttons[0])
    random_delay(0.8, 1.5)
    wait_for_stable(page, timeout=3000)

    # 2. Find the comment input — targeted search to avoid the search bar
    comment_input_found = False

    # 2A: DOM — look for the comment box specifically
    print("[Interact] [Comment] Searching for comment input via DOM...")
    try:
        # LinkedIn comment boxes are contenteditable divs with specific ARIA labels
        selectors = [
            '[role="textbox"][aria-label*="comment" i]',
            '[role="textbox"][aria-placeholder*="comment" i]',
            '[contenteditable="true"][aria-label*="comment" i]',
            '.ql-editor[contenteditable="true"]',
            '[role="textbox"][aria-label*="Add a comment" i]',
            'div.editor-content[contenteditable="true"]',
        ]
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                bbox = locator.first.bounding_box()
                if bbox and bbox["width"] > 10 and bbox["height"] > 5:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    print(f"[Interact] [Comment] ✅ DOM found comment input at ({cx:.0f},{cy:.0f}) via '{selector}'")
                    human_click(page, cx, cy)
                    comment_input_found = True
                    break
    except Exception as e:
        print(f"[Interact] [Comment] DOM search error: {e}")

    # 2B: ACT — search for textboxes with "comment" in the name
    if not comment_input_found:
        print("[Interact] [Comment] Searching via ACT...")
        tree = extract_act(page)
        # First try textboxes with "comment" label
        comment_inputs = find_textboxes(tree, "comment")
        if not comment_inputs:
            comment_inputs = find_by_text(tree, "Add a comment")
        if not comment_inputs:
            # Last resort: get all textboxes but SKIP searchbox role elements
            from accessibility import find_node_by_role_and_name
            comment_inputs = find_node_by_role_and_name(tree, "textbox", None)
            # Filter out anything that looks like a search bar
            comment_inputs = [
                inp for inp in comment_inputs
                if "search" not in (inp.get("name", "") or "").lower()
            ]

        if comment_inputs:
            print(f"[Interact] [Comment] ACT found {len(comment_inputs)} candidate(s)")
            _click_act_element(page, comment_inputs[0])
            comment_input_found = True

    if not comment_input_found:
        print("[Interact] Could not find comment input")
        return False

    random_delay(0.3, 0.5)

    # 3. Type the comment with natural speed
    human_type(page, comment_text)
    random_delay(0.5, 1.0)

    # 4. Submit the comment
    submitted = False

    # 4A: Try DOM — find the comment submit button specifically
    print("[Interact] [Comment] Submitting comment...")
    try:
        submit_selectors = [
            'button.comments-comment-box__submit-button',
            'button[class*="comments-comment-box"][type="submit"]',
            'button[data-control-name="comment_submit"]',
            'form.comments-comment-box button[type="submit"]',
        ]
        for selector in submit_selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                bbox = locator.first.bounding_box()
                if bbox and bbox["width"] > 5:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    print(f"[Interact] [Comment] ✅ Found submit button via DOM at ({cx:.0f},{cy:.0f})")
                    human_click(page, cx, cy)
                    submitted = True
                    break
    except Exception as e:
        print(f"[Interact] [Comment] DOM submit search error: {e}")

    # 4B: Ctrl+Enter — the most reliable way to submit a LinkedIn comment
    if not submitted:
        print("[Interact] [Comment] Using Ctrl+Enter to submit...")
        page.keyboard.press("Control+Enter")
        submitted = True

    wait_for_stable(page, timeout=3000)

    # 4C: Verify the comment was submitted by checking if the text input cleared
    try:
        # After a successful post, the comment input is usually cleared or collapsed
        verify_selectors = [
            '[role="textbox"][aria-label*="comment" i]',
            '[contenteditable="true"][aria-label*="comment" i]',
        ]
        for selector in verify_selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                content = locator.first.text_content() or ""
                if comment_text[:20] in content:
                    # Comment text is still there — submit might have failed
                    print("[Interact] [Comment] ⚠️ Text still in input — retrying with Ctrl+Enter...")
                    locator.first.focus()
                    random_delay(0.2, 0.4)
                    page.keyboard.press("Control+Enter")
                    wait_for_stable(page, timeout=3000)
                break
    except Exception:
        pass  # Verification is best-effort

    print("[Interact] 💬 Comment posted!")
    return True


def find_recent_posts(page, profile_url=None):
    """Find recent posts from a profile's Activity section.

    Used for the "Post-Interaction Hook" — we comment on a
    prospect's recent post before sending a connection request.

    Args:
        page: Playwright page (should be on the profile).
        profile_url: Optional URL — if provided, navigates there first.

    Returns:
        list[dict]: Recent posts with content snippets.
    """
    if profile_url:
        page.goto(profile_url, wait_until="domcontentloaded")
        wait_for_stable(page)

    # Scroll down to find Activity section
    for _ in range(5):
        human_scroll(page, "down", random.randint(300, 500))
        wait_for_stable(page, timeout=2000)

        tree = extract_act(page)
        activity_nodes = find_by_text(tree, "Activity")
        if activity_nodes:
            break

        random_delay(0.5, 1.0)

    # Try to extract posts from the Activity section
    from linkedin.profile import extract_recent_posts
    posts = extract_recent_posts(page)

    return posts


def pre_connection_engagement(page, prospect_name, comment_generator=None):
    """The "Post-Interaction Hook" — engage BEFORE connecting.

    Dramatically increases connection acceptance rates by:
    1. Finding the prospect's recent post
    2. Liking it
    3. Leaving a genuine, context-aware comment
    4. Only THEN sending a connection request

    Args:
        page: Playwright page.
        prospect_name: Name of the prospect.
        comment_generator: Function that generates a comment given post content.
            Signature: (post_content: str) -> str
            If None, just likes without commenting.

    Returns:
        dict: Engagement result with status.
    """
    print(f"[Interact] 🎯 Pre-connection engagement with {prospect_name}")

    # Try to find their recent posts
    posts = find_recent_posts(page)

    if not posts:
        print("[Interact] No recent posts found — skipping engagement")
        return {"status": "no_posts", "name": prospect_name}

    # Pick the most recent post
    post = posts[0]
    post_content = post.get("content", "")

    # Like the post
    liked = like_post(page, scroll_first=False)

    # Generate and leave a comment if we have a generator
    commented = False
    if comment_generator and post_content:
        comment = comment_generator(post_content)
        if comment:
            random_delay(1.0, 2.0)  # Pause before commenting (natural)
            commented = comment_on_post(page, comment)

    return {
        "status": "engaged",
        "name": prospect_name,
        "liked": liked,
        "commented": commented,
        "post_snippet": post_content[:100],
    }


def organic_feed_engagement(page, max_likes=3, max_comments=1, comment_generator=None, guardrails=None):
    """Do organic feed engagement — like and comment on feed posts.

    Used during warm-up and regular sessions to build engagement
    signals.

    Args:
        page: Playwright page (should be on the feed).
        max_likes: Maximum posts to like.
        max_comments: Maximum posts to comment on.
        comment_generator: Optional function to generate comments.
        guardrails: Optional Guardrails instance for rate limiting and stats tracking.

    Returns:
        dict: Summary of engagement actions.
    """
    likes = 0
    comments = 0
    total_actions = max_likes + max_comments

    for i in range(total_actions + 3):  # Extra iterations for scroll/read variety
        # Periodic session check
        if not check_session_or_relogin(page):
            print("[Interact] ❌ Session lost in engagement loop — aborting loop")
            break

        # Scroll to next post
        human_scroll(page, "down", random.randint(300, 500))
        wait_for_stable(page, timeout=3000)

        # Read the post
        dwell_on_content(page, random.randint(40, 120))

        # Like?
        if likes < max_likes and random.random() < 0.8:
            if guardrails and not guardrails.can_like():
                print("[Interact] ⛔ Daily like limit reached — skipping")
            else:
                # Scroll a little to ensure Like button is visible in viewport
                human_scroll(page, "up", random.randint(50, 150))
                wait_for_stable(page, timeout=1500)
                if like_post(page, scroll_first=False):
                    likes += 1
                    if guardrails:
                        guardrails.record_action("like")
                    print(f"[Interact] 📊 Likes so far: {likes}/{max_likes}")

        # Comment?
        if comments < max_comments and random.random() < 0.5 and comment_generator:
            if guardrails and not guardrails.can_comment():
                print("[Interact] ⛔ Daily comment limit reached — skipping")
            else:
                comment = comment_generator("general engagement")
                if comment and comment_on_post(page, comment):
                    comments += 1
                    if guardrails:
                        guardrails.record_action("comment")
                    print(f"[Interact] 📊 Comments so far: {comments}/{max_comments}")

        # Stop early if all targets met
        if likes >= max_likes and comments >= max_comments:
            print(f"[Interact] ✅ All engagement targets met ({likes} likes, {comments} comments)")
            break

        random_delay(1.0, 3.0)

    return {"likes": likes, "comments": comments}
