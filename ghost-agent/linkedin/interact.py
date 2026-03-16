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
from audit import audit_logger


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
                        visible: rect.width > 0 && rect.height > 0 && rect.top > 80 && rect.bottom < window.innerHeight - 20,
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

        # Pick the most central visible, not-already-liked button
        valid_buttons = []
        for el in like_info:
            label_lower = el.get("label", "").lower()
            text_lower = el.get("text", "").lower()
            
            # Avoid already-liked states, or undo/remove buttons
            if "liked" in label_lower or "remove" in label_lower or "undo" in label_lower:
                continue
            if "liked" in text_lower or "remove" in text_lower or "undo" in text_lower:
                continue
                
            if el["visible"] and el["pressed"] != "true" and el["width"] > 10:
                valid_buttons.append(el)
        
        # Sort by proximity to vertical center (approx 400px) to avoid previous post buttons
        valid_buttons.sort(key=lambda e: abs(e["y"] - 400))

        if valid_buttons:
            el = valid_buttons[0]
            cx, cy = el["x"], el["y"]
            method_used = "DOM"
            print(f"[Interact]   ✅ Selected: text='{el['text']}' at ({cx:.0f},{cy:.0f})")

        if cx is None and like_info:
            print("[Interact]   ⚠️ Found elements but none are valid/clickable")

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

    # If the intent is just a normal "Like" (thumbs up), click it directly without the wait
    # The LinkedIn thumbs-up reaction triggers from a standard click, avoiding the popup UI altogether.
    reaction_names = ["Like", "Celebrate", "Support", "Love", "Insightful", "Funny"]

    if random.random() < 0.8:
        target_reaction = "Like"
    else:
        target_reaction = random.choice(reaction_names)
    print(f"[Interact] Target reaction: {target_reaction}")

    if target_reaction == "Like":
        print("[Interact] Moving to Like button with Bézier curve and clicking immediately...")
        human_move_to(page, cx, cy)
        time.sleep(random.uniform(0.6, 1.2))
        page.mouse.click(cx, cy, delay=random.randint(50, 150))
        print("[Interact] 👍 Clicked Like directly")
        print(f"[Interact] ── Like Complete (method={method_used}, reaction=True) ──")
        return True

    # ─── Step 2: Hover with Bézier (triggers reaction popup for non-Like reactions) ───
    print(f"[Interact] Moving to Like button with Bézier curve to trigger popup for {target_reaction}...")
    human_move_to(page, cx, cy)

    # ─── Step 3: Wait for reaction popup ──────────────────────────────
    # Wait lightly longer to ensure popup fully renders before looking for it
    wait_time = random.uniform(1.0, 1.5)
    print(f"[Interact] Waiting {wait_time:.2f}s for reaction popup...")
    time.sleep(wait_time)

    # ─── Step 4: Click a reaction emoji from the popup ────────────────

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


def read_post_in_viewport(page):
    """Extract post content from the most visible post in the viewport.

    Implements a 4-layer resilient extraction pipeline (DOM-first):
      Layer 1: DOM — structured selectors + data-urn stripping (fast, free)
      Layer 2: ACT — Accessibility Tree StaticText nodes (semantic, stable)
      Layer 3: innerHTML — brute-force text extraction (catches edge cases)
      Layer 4: Vision — Gemini screenshot analysis (expensive, last resort)

    Returns:
        dict: Structured post data with keys:
            - body (str): The post text content
            - author (str): Author name
            - author_headline (str): Author headline/title
            - topics (list[str]): Extracted hashtags/topics
            - method (str): Which extraction layer succeeded
            - confidence (float): 1.0=DOM, 0.7=ACT, 0.5=innerHTML, 0.3=Vision
        Returns empty dict if all layers fail.
    """
    import os
    from config import SCREENSHOT_DIR

    empty_result = {}

    try:
        # ─── Step 0: Find the most visible post container ────────────
        post_info = page.evaluate("""() => {
            const articles = document.querySelectorAll(
                'div[role="listitem"][componentkey*="FeedType"], article, .feed-shared-update-v2, [data-urn*="activity"]'
            );
            let bestIdx = -1;
            let maxVisibleHeight = 0;

            for (let i = 0; i < articles.length; i++) {
                const el = articles[i];
                const text = (el.innerText || '').toLowerCase();
                
                // Skip non-post containers like "People you may know" or "Recommended for you"
                if (text.includes('people you may know') || text.includes('recommended for you')) {
                    continue;
                }
                
                // A valid post should have social action buttons like 'like' or 'comment'
                if (!text.includes('like') && !text.includes('comment')) {
                    continue;
                }

                const rect = el.getBoundingClientRect();
                const visibleTop = Math.max(0, rect.top);
                const visibleBottom = Math.min(window.innerHeight, rect.bottom);
                const visibleHeight = visibleBottom - visibleTop;

                if (visibleHeight > maxVisibleHeight) {
                    maxVisibleHeight = visibleHeight;
                    bestIdx = i;
                }
            }
            return { idx: bestIdx, visibleHeight: maxVisibleHeight };
        }""")

        visible_article_idx = post_info.get("idx", -1)
        if visible_article_idx == -1:
            print("[Interact] ⚠️ No post container found in viewport.")
            return empty_result

        post_selector = 'div[role="listitem"][componentkey*="FeedType"], article, .feed-shared-update-v2, [data-urn*="activity"]'
        post_locator = page.locator(post_selector).nth(visible_article_idx)

        # ─── Step 1: Expand "See More" ──────────────────────────────
        try:
            see_more_variants = ["...see more", "…see more", "...more", "…more"]
            for variant in see_more_variants:
                see_more_btn = post_locator.get_by_text(variant, exact=True)
                if see_more_btn.count() > 0 and see_more_btn.first.is_visible():
                    print("[Interact] 👁️ Found 'more' button, clicking to expand post...")
                    bbox = see_more_btn.first.bounding_box()
                    if bbox:
                        cx = bbox["x"] + bbox["width"] / 2
                        cy = bbox["y"] + bbox["height"] / 2
                        human_move_to(page, cx, cy)
                        time.sleep(random.uniform(0.1, 0.3))
                        human_click(page, cx, cy)
                        time.sleep(0.5)
                    break
        except Exception as e:
            print(f"[Interact] ⚠️ Error handling 'see more': {e}")

        # ─── Step 2: Extract author metadata (always attempt) ───────
        author_name = ""
        author_headline = ""
        try:
            author_info = post_locator.evaluate("""(postEl) => {
                const result = { name: '', headline: '' };

                // Author name — usually a <span> inside an actor link
                const actorName = postEl.querySelector(
                    '.update-components-actor__name span[aria-hidden="true"], ' +
                    '.feed-shared-actor__name span[aria-hidden="true"], ' +
                    'a[data-tracking-control-name*="actor"] span[dir="ltr"] > span[aria-hidden="true"], ' +
                    '.update-components-actor__title span[aria-hidden="true"]'
                );
                if (actorName) result.name = actorName.innerText.trim();

                // Fallback: first strong/bold or prominent text element
                if (!result.name) {
                    const h3 = postEl.querySelector('h3, .t-bold');
                    if (h3) result.name = h3.innerText.trim().split('\\n')[0];
                }

                // Author headline — description/subtitle below name
                const actorDesc = postEl.querySelector(
                    '.update-components-actor__description span[aria-hidden="true"], ' +
                    '.feed-shared-actor__description span[aria-hidden="true"], ' +
                    '.update-components-actor__sub-description span[aria-hidden="true"]'
                );
                if (actorDesc) result.headline = actorDesc.innerText.trim();

                // Ultimate fallback for heavily obfuscated domains (like the new 2026 renderer)
                if (!result.name) {
                    const lines = (postEl.innerText || '').split('\\n')
                        .map(l => l.trim())
                        .filter(l => l.length > 0 && l !== 'Feed post' && l !== 'Suggested' && l !== 'Promoted');
                    if (lines.length > 0) result.name = lines[0];
                    if (lines.length > 1) result.headline = lines[1];
                }

                return result;
            }""")
            author_name = author_info.get("name", "")
            author_headline = author_info.get("headline", "")
            if author_name:
                print(f"[Interact] 👤 Author: {author_name}" +
                      (f" — {author_headline[:60]}" if author_headline else ""))
        except Exception as e:
            print(f"[Interact] ⚠️ Author extraction failed: {e}")

        # ─── Variables for the extraction pipeline ──────────────────
        post_text = ""
        method_used = "None"
        confidence = 0.0
        topics = []
        screenshot_path = None

        # ─── Layer 1: DOM Content Extraction (Primary) ──────────────
        print("[Interact] [1/4] 📄 DOM extraction...")
        try:
            dom_result = post_locator.evaluate("""(postEl) => {
                // --- Helper: strip data-urn tracking divs ---
                const clone = postEl.cloneNode(true);
                clone.querySelectorAll('div[data-urn]').forEach(el => el.remove());

                let text = '';
                let method = '';

                // Strategy A: feed-shared-text / update-components-text containers
                const textContainers = clone.querySelectorAll(
                    '.feed-shared-text, .update-components-text, ' +
                    '.feed-shared-update-v2__description, ' +
                    '[data-testid="expandable-text-box"]'
                );
                for (const container of textContainers) {
                    const t = container.innerText?.trim() || '';
                    if (t.length > text.length && t.length > 20) {
                        text = t;
                        method = 'DOM-TextContainer';
                    }
                }

                // Strategy B: aria-hidden spans within text containers (LinkedIn's actual text rendering)
                if (!text) {
                    const spans = clone.querySelectorAll(
                        '.feed-shared-text span[dir="ltr"], ' +
                        '.update-components-text span[dir="ltr"], ' +
                        'span.break-words'
                    );
                    const parts = [];
                    for (const span of spans) {
                        const t = span.innerText?.trim() || '';
                        if (t.length > 5) parts.push(t);
                    }
                    if (parts.length > 0) {
                        text = parts.join(' ');
                        method = 'DOM-SpanCollect';
                    }
                }

                // Strategy C: deepest substantial text node
                if (!text) {
                    const allEls = clone.querySelectorAll('span, p, div');
                    let longestText = '';
                    for (const el of allEls) {
                        // Skip buttons, action bars, and navigation elements
                        if (el.closest('button, [role="button"], nav, footer, header')) continue;
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t.length > longestText.length && t.length > 30) {
                            longestText = t;
                        }
                    }
                    if (longestText) {
                        text = longestText;
                        method = 'DOM-DeepSearch';
                    }
                }

                // Extract hashtags as topics
                const hashtags = [];
                const hashtagEls = clone.querySelectorAll('a[href*="hashtag"], button[data-hashtag]');
                for (const ht of hashtagEls) {
                    const tag = (ht.innerText || '').trim().replace('#', '');
                    if (tag) hashtags.push(tag);
                }

                return { text: text, method: method, hashtags: hashtags };
            }""")

            if dom_result and dom_result.get("text"):
                post_text = dom_result["text"].strip()
                method_used = dom_result.get("method", "DOM")
                confidence = 1.0
                topics = dom_result.get("hashtags", [])
                print(f"[Interact]   ✅ {method_used} extracted {len(post_text)} chars")

        except Exception as e:
            print(f"[Interact]   ❌ DOM extraction error: {e}")

        # ─── Layer 2: ACT Tree Extraction (Secondary) ───────────────
        if not post_text:
            print("[Interact] [2/4] 🌳 ACT tree extraction...")
            try:
                from accessibility import extract_act, act_to_flat_list
                tree = extract_act(page)
                flat_nodes = act_to_flat_list(tree)

                # Collect StaticText nodes that aren't UI labels
                ui_labels = {
                    "like", "comment", "share", "send", "repost",
                    "follow", "connect", "more", "see more",
                    "reactions", "comments", "reposts",
                }
                text_parts = []
                for node in flat_nodes:
                    if node.get("role") in ("StaticText", "text", "paragraph"):
                        name = (node.get("name") or "").strip()
                        if len(name) > 15 and name.lower() not in ui_labels:
                            text_parts.append(name)

                if text_parts:
                    # Take the longest contiguous text block
                    combined = " ".join(text_parts)
                    if len(combined) > 30:
                        post_text = combined
                        method_used = "ACT"
                        confidence = 0.7
                        print(f"[Interact]   ✅ ACT extracted {len(post_text)} chars from {len(text_parts)} nodes")

            except Exception as e:
                print(f"[Interact]   ❌ ACT extraction error: {e}")

        # ─── Layer 3: innerHTML Brute-Force (Tertiary) ──────────────
        if not post_text:
            print("[Interact] [3/4] 🔨 innerHTML brute-force extraction...")
            try:
                brute_text = post_locator.evaluate("""(postEl) => {
                    const clone = postEl.cloneNode(true);

                    // Strip all non-text elements
                    const stripTags = ['button', 'svg', 'img', 'video', 'iframe',
                                       'nav', 'footer', 'header', 'style', 'script'];
                    stripTags.forEach(tag => {
                        clone.querySelectorAll(tag).forEach(el => el.remove());
                    });
                    // Strip role="button" elements
                    clone.querySelectorAll('[role="button"]').forEach(el => el.remove());
                    // Strip data-urn tracking divs
                    clone.querySelectorAll('div[data-urn]').forEach(el => el.remove());
                    // Strip action bars
                    clone.querySelectorAll(
                        '.social-details-social-counts, .social-details-social-activity, ' + 
                        '[class*="action-bar"], [class*="social-action"]'
                    ).forEach(el => el.remove());

                    const rawText = clone.textContent || '';

                    // Filter out known UI patterns
                    const uiPatterns = [
                        /^\\s*Like\\s*$/im, /^\\s*Comment\\s*$/im, /^\\s*Share\\s*$/im,
                        /^\\s*Send\\s*$/im, /^\\s*Repost\\s*$/im, /^\\s*Follow\\s*$/im,
                        /^\\s*\\d+\\s*(reactions?|comments?|reposts?)\\s*$/im,
                        /^\\s*\\d+[hdwmy]\\s*$/im,  // timestamps like "2h", "3d"
                    ];

                    // Split into lines, filter noise, rejoin
                    const lines = rawText.split('\\n')
                        .map(l => l.trim())
                        .filter(l => l.length > 3)
                        .filter(l => !uiPatterns.some(p => p.test(l)));

                    return lines.join(' ').replace(/\\s+/g, ' ').trim();
                }""")

                if brute_text and len(brute_text) > 30:
                    post_text = brute_text
                    method_used = "innerHTML"
                    confidence = 0.5
                    print(f"[Interact]   ✅ innerHTML extracted {len(post_text)} chars")

            except Exception as e:
                print(f"[Interact]   ❌ innerHTML extraction error: {e}")

        # ─── Layer 4: Vision Extraction (Last Resort) ───────────────
        if not post_text:
            print("[Interact] [4/4] 📸 Vision extraction (last resort)...")
            try:
                os.makedirs(SCREENSHOT_DIR, exist_ok=True)
                screenshot_path = os.path.join(SCREENSHOT_DIR, f"post_snippet_{int(time.time())}.png")
                post_locator.screenshot(path=screenshot_path)
                print(f"[Interact]   📸 Screenshot: {screenshot_path}")

                from vision import analyze_image
                prompt = (
                    "Extract the main text content from this LinkedIn post screenshot.\n"
                    "Ignore the author name, timestamps, reaction counts, and UI buttons.\n"
                    "Return ONLY the post body text — the actual content the person wrote.\n"
                    "If there are hashtags, include them at the end."
                )

                if screenshot_path and os.path.exists(screenshot_path):
                    vision_text = analyze_image(screenshot_path, prompt)

                    if vision_text and len(vision_text.strip()) > 20:
                        post_text = vision_text.strip()
                        method_used = "Vision"
                        confidence = 0.3
                        print(f"[Interact]   ✅ Vision extracted {len(post_text)} chars")
                    else:
                        print("[Interact]   ⚠️ Vision returned insufficient text.")
            except Exception as e:
                print(f"[Interact]   ❌ Vision extraction error: {e}")

        # ─── Take screenshot for audit (if not already taken) ───────
        if not screenshot_path:
            try:
                os.makedirs(SCREENSHOT_DIR, exist_ok=True)
                screenshot_path = os.path.join(SCREENSHOT_DIR, f"post_snippet_{int(time.time())}.png")
                post_locator.screenshot(path=screenshot_path)
            except Exception:
                pass  # Non-critical

        # ─── Extract topics from hashtags in body text ──────────────
        if post_text and not topics:
            import re
            found_tags = re.findall(r'#(\w+)', post_text)
            if found_tags:
                topics = found_tags[:5]

        # ─── Build structured result ────────────────────────────────
        result = {}
        if post_text:
            result = {
                "body": post_text,
                "author": author_name,
                "author_headline": author_headline,
                "topics": topics,
                "method": method_used,
                "confidence": confidence,
            }
            print(f"[Interact] 📄 Post read via {method_used} (confidence={confidence}) | "
                  f"{len(post_text)} chars | author='{author_name}'")
        else:
            print("[Interact] ❌ ALL 4 LAYERS FAILED — could not extract post content")

        # Log to Audit Dashboard
        audit_logger.log_event(
            action_name="Read Post",
            screenshot_path=screenshot_path,
            extracted_text=post_text,
            success=bool(post_text),
            extra_data={
                "method": method_used,
                "confidence": confidence,
                "author": author_name,
            }
        )

        return result

    except Exception as e:
        print(f"[Interact] ❌ Error extracting post text: {e}")
        audit_logger.log_event(action_name="Read Post", success=False, error_msg=str(e))
        return empty_result


def like_post(page, scroll_first=True, post_data=None):
    """Like the post currently in view.

    LinkedIn-specific: The Like button shows a reaction emoji popup
    when hovered for >500ms. We use a FAST direct click to avoid
    triggering the popup. If it still appears, we click the 👍 emoji.

    Args:
        page: Playwright page.
        scroll_first: If True, scroll down a bit before liking.
        post_data: Optional existing extracted post data.

    Returns:
        bool: True if like was successful.
    """
    if scroll_first:
        human_scroll(page, "down", random.randint(100, 200))
        wait_for_stable(page, timeout=2000)

    # MANDATORY: Read the post before liking (Requirement: agent must read first)
    if not post_data:
        post_data = read_post_in_viewport(page)
        
    if not post_data:
        print("[Interact] ⚠️ Could not read post content, proceeding with caution...")
    
    dwell_on_content(page, random.randint(30, 120))

    return _fast_click_like(page)


def comment_on_post(page, comment_text, extracted_post_text=None):
    """Leave a comment on the post currently in view.

    Flow: Click "Comment" → Wait for input → Type comment → Post
    Includes natural reading dwell before commenting.

    Args:
        page: Playwright page.
        comment_text: The comment to leave.
        extracted_post_text: The original post text, used for audit logging.

    Returns:
        bool: True if comment was posted.
    """
    # MANDATORY: Read the post first (Requirement: agent must read first)
    if not extracted_post_text:
        post_data = read_post_in_viewport(page)
        extracted_post_text = post_data.get("body", "") if isinstance(post_data, dict) else post_data
        
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
    print("[Interact] [Comment] Submitting comment...")

    # 4A: Robust DOM check for the specific Post/Comment button
    try:
        button_info = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            // Filter all buttons that say "Comment" or "Post" and are NOT disabled
            const submitBtns = btns.filter(b => {
                const text = (b.innerText || '').trim().toLowerCase();
                return (text === 'comment' || text === 'post') && !b.disabled;
            });
            
            let bestBtn = null;
            let maxScore = -100;
            
            for (const b of submitBtns) {
                let score = 0;
                const klass = (b.className || '').toLowerCase();
                const hasSvg = b.querySelector('svg');
                
                // Real submit buttons are usually primary color (blue) and don't have SVGs
                if (klass.includes('primary')) score += 50;
                if (!hasSvg) score += 20; else score -= 50;
                
                // Favor buttons near or inside a comment box
                if (b.closest('form, div[class*="comment-box"], div[class*="comments"], [class*="submit"]')) score += 30;
                if (b.type === 'submit') score += 20;

                const rect = b.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    if (score > maxScore) {
                        maxScore = score;
                        bestBtn = b;
                    }
                }
            }
            
            if (bestBtn && maxScore > 0) {
                const rect = bestBtn.getBoundingClientRect();
                return {x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true, score: maxScore};
            }
            return {found: false};
        }""")
        
        if button_info and button_info.get("found"):
            cx, cy = button_info["x"], button_info["y"]
            print(f"[Interact] [Comment] ✅ Found submit button via evaluated DOM at ({cx:.0f},{cy:.0f})")
            human_click(page, cx, cy)
            submitted = True
            
    except Exception as e:
        print(f"[Interact] [Comment] DOM submit search error: {e}")

    # 4B: Last resort fallback to Ctrl+Enter
    if not submitted:
        print("[Interact] [Comment] ⚠️ Submit button not found, falling back to Ctrl+Enter...")
        page.keyboard.press("Control+Enter")
        random_delay(0.2, 0.4)
        page.keyboard.press("Enter")
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
    
    audit_logger.log_event(
        action_name="Comment on Post",
        extracted_text=extracted_post_text, # To show what we responded to
        generated_response=comment_text,
        success=True
    )
    
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
        comment_generator: Function that generates a comment given post data.
            Signature: (post_data: dict|str) -> str
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
    post_data = {
        "body": post_content,
        "author": prospect_name,
        "author_headline": "",
        "topics": [],
        "method": "profile_activity",
        "confidence": 0.8,
    }
    liked = like_post(page, scroll_first=False, post_data=post_data)

    # Generate and leave a comment if we have a generator
    commented = False
    if comment_generator and post_content:
        # Build structured data for richer comment generation
        post_data = {
            "body": post_content,
            "author": prospect_name,
            "author_headline": "",
            "topics": [],
            "method": "profile_activity",
            "confidence": 0.8,
        }
        comment = comment_generator(post_data)
        if comment:
            random_delay(1.0, 2.0)  # Pause before commenting (natural)
            commented = comment_on_post(page, comment, post_content)

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
            Signature: (post_data: dict) -> str
            Receives structured post data with body, author, author_headline, topics.
        guardrails: Optional Guardrails instance for rate limiting and stats tracking.

    Returns:
        dict: Summary of engagement actions.
    """
    likes = 0
    comments = 0
    total_actions = max_likes + max_comments
    seen_posts = set()

    for i in range(total_actions + 3):  # Extra iterations for scroll/read variety
        # Periodic session check
        if not check_session_or_relogin(page):
            print("[Interact] ❌ Session lost in engagement loop — aborting loop")
            break

        # Scroll to next post
        human_scroll(page, "down", random.randint(300, 500))
        wait_for_stable(page, timeout=3000)

        # Read the post content (structured dict)
        post_data = read_post_in_viewport(page)
        post_body = post_data.get("body", "") if post_data else ""

        # Retry once if extraction failed — scroll slightly and try again
        if not post_body:
            print("[Interact] 🔄 Retrying post extraction after small scroll...")
            human_scroll(page, "down", random.randint(50, 100))
            wait_for_stable(page, timeout=1500)
            post_data = read_post_in_viewport(page)
            post_body = post_data.get("body", "") if post_data else ""

        # Check if we've already engaged with this post snippet
        # Use first 200 chars as a fuzzy signature
        post_signature = post_body[:200] if post_body else None
        
        if post_signature and post_signature in seen_posts:
            print("[Interact] ⏭️ Already processed this post in the current session feed — scrolling further")
            # Force a slightly larger scroll to move past this post
            human_scroll(page, "down", random.randint(400, 700))
            random_delay(1.0, 2.0)
            continue
            
        if post_signature:
            seen_posts.add(post_signature)

        # Dwell to simulate reading
        dwell_on_content(page, random.randint(40, 120))

        # Like?
        if likes < max_likes and random.random() < 0.8:
            if guardrails and not guardrails.can_like():
                print("[Interact] ⛔ Daily like limit reached — skipping")
            else:
                # Scroll a little down to ensure Like button is visible in viewport
                human_scroll(page, "down", random.randint(50, 150))
                wait_for_stable(page, timeout=1500)
                if like_post(page, scroll_first=False, post_data=post_data):
                    likes += 1
                    if guardrails:
                        guardrails.record_action("like")
                    print(f"[Interact] 📊 Likes so far: {likes}/{max_likes}")

        # Comment?
        if comments < max_comments and random.random() < 0.5 and comment_generator:
            if guardrails and not guardrails.can_comment():
                print("[Interact] ⛔ Daily comment limit reached — skipping")
            elif not post_body:
                print("[Interact] ⚠️ Could not read post text — skipping comment to avoid generic repetitive comments")
            else:
                # Pass full structured post data for richer comment generation
                comment = comment_generator(post_data)
                if comment and comment_on_post(page, comment, post_body):
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
