"""Non-linear navigation engine for GhostAgent.

A real LinkedIn user NEVER navigates directly to URLs.
They browse organically: scroll the feed, check notifications,
use the search bar, click through profiles naturally.

This module creates "human path" navigation that makes the
agent's browsing pattern indistinguishable from a professional
checking LinkedIn during a work break.
"""

import random
import time
import json
import sys
import os

# Add local directory to sys.path for IDEs and static analysis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from human import (
    human_click,
    human_scroll,
    human_type,
    random_delay,
    reading_delay,
    idle_fidget,
    dwell_on_content,
)
from browser import take_screenshot, wait_for_stable
from accessibility import extract_act, find_buttons, find_links, find_textboxes, get_ax_snapshot, assign_agent_ids
from config import DETOUR_PROBABILITY, SCREENSHOT_DIR
from semantic_map import SemanticMap
from self_healing_bridge import heal_selector
from vision import describe_page, decide_action_orchestrated, verify_action_async

# Module-level semantic cache singleton
_smap = SemanticMap()


# ─── Core Navigation ────────────────────────────────────────────────────────

def navigate_to_feed(page):
    """Navigate to the LinkedIn home feed naturally.

    Clicks the Home button in the nav bar (doesn't type a URL).
    Then scrolls a bit and dwells like a real user.
    """
    print("[Navigator] Going to home feed...")

    if not _click_cached_or_discover(page, "nav_home", "link", "Home", find_links):
        # Fallback: navigate directly (less ideal but functional)
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")

    wait_for_stable(page)

    # Natural behavior: scroll the feed a bit, pause on 1-2 posts
    _organic_feed_browse(page, min_posts=1, max_posts=3)


def navigate_to_search(page, query):
    """Search LinkedIn using the search bar naturally, with a reliable URL fallback.

    Simulates: Click search → Type query → Press Enter
    Then waits for results naturally.
    """
    print(f"[Navigator] Searching for: {query}")
    import urllib.parse

    success = False
    
    # 1. High-level reliable locators for LinkedIn search bar
    locators = [
        page.locator("input.search-global-typeahead__input"),
        page.get_by_placeholder("Search", exact=False),
        page.get_by_role("combobox", name="Search", exact=False),
        page.get_by_role("searchbox", name="Search", exact=False)
    ]
    
    # Try semantic map first if available
    cached = _smap.lookup("search_input")
    if cached and cached.get("role") == "selector":
        locators.insert(0, page.locator(cached.get("name")))

    for loc in locators:
        try:
            # Only interact with a visible search input avoiding the hidden mobile bar
            visible_input = loc.filter(state="visible").first
            # Expect it to appear quickly if it is the right one
            visible_input.wait_for(state="visible", timeout=1000)
            
            print("[Navigator] Found visible search input, clicking and typing...")
            visible_input.click(timeout=1000)
            visible_input.fill("") # Clear reliably
            
            # Type organically but bind exactly to this element so we never type into the void
            delay_ms = random.randint(30, 90)
            visible_input.type(query, delay=delay_ms)
            
            random_delay(0.2, 0.5)
            visible_input.press("Enter")
            success = True
            break
        except Exception:
            continue
            
    # 2. Most reliable fallback: navigate to search URI directly if UI changes drastically
    if not success:
        print("[Navigator] ⚠️ Organic search failed. Using highly reliable URL fallback...")
        encoded_query = urllib.parse.quote(query)
        page.goto(f"https://www.linkedin.com/search/results/all/?keywords={encoded_query}", wait_until="domcontentloaded")

    wait_for_stable(page, timeout=8000)
    random_delay(1.0, 2.0)


def navigate_to_profile(page, name, url: str = None):
    """Navigate to someone's profile the way a human would.

    If a LinkedIn URL is provided, navigates via search first then falls back
    to the URL (never jumps straight to /in/name from outside LinkedIn).

    Args:
        page: Playwright page.
        name: Person's name to search for.
        url: Optional LinkedIn profile URL as fallback.
    """
    print(f"[Navigator] Finding profile: {name}")

    # Random detour (30% chance) — browse feed briefly first
    if random.random() < DETOUR_PROBABILITY:
        print("[Navigator] 📱 Quick detour: checking feed...")
        _organic_feed_browse(page, min_posts=1, max_posts=2)

    # Search for the person organically first
    navigate_to_search(page, name)
    _click_people_tab(page)
    random_delay(1.0, 2.0)

    # If we have a URL and search didn't land us on the right profile, use it
    # (only as fallback — direct URL is less suspicious coming from search context)
    if url and url.startswith("https://www.linkedin.com/in/"):
        from browser import get_current_url
        current = get_current_url(page)
        if "/search/results/" in current or "/in/" not in current:
            page.goto(url, wait_until="domcontentloaded")
            from browser import wait_for_stable
            wait_for_stable(page, timeout=8000)


def navigate_to_notifications(page):
    """Check notifications naturally."""
    print("[Navigator] Checking notifications...")

    if not _click_cached_or_discover(page, "nav_notifications", "link", "Notifications", find_links):
        page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded")

    wait_for_stable(page)
    random_delay(1.5, 3.0)

    # Scroll through a few notifications
    for _ in range(random.randint(1, 3)):
        human_scroll(page, "down")
        random_delay(1.0, 2.5)


def navigate_to_messaging(page):
    """Go to messaging inbox naturally."""
    print("[Navigator] Opening messaging...")

    if not _click_cached_or_discover(page, "nav_messaging", "link", "Messaging", find_links):
        page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded")

    wait_for_stable(page)
    random_delay(1.0, 2.0)


def navigate_to_my_network(page):
    """Go to My Network page naturally."""
    print("[Navigator] Going to My Network...")

    if not _click_cached_or_discover(page, "nav_network", "link", "My Network", find_links):
        page.goto("https://www.linkedin.com/mynetwork/", wait_until="domcontentloaded")

    wait_for_stable(page)
    random_delay(1.0, 2.0)


# ─── Detours & Organic Behavior ─────────────────────────────────────────────

def random_detour(page):
    """Take a random "distraction" detour like a real user would.

    30% chance of being called. Simulates a professional who
    gets briefly distracted while using LinkedIn.

    Possible detours:
    - Scroll feed and read a post
    - Check notifications
    - Glance at messaging
    """
    detour_type = random.choice([
        "feed_scroll",
        "feed_scroll",  # Double weight — most common behavior
        "check_notifications",
        "glance_messaging",
    ])

    if detour_type == "feed_scroll":
        print("[Navigator] 📱 Detour: scrolling feed...")
        _organic_feed_browse(page, min_posts=1, max_posts=2)

    elif detour_type == "check_notifications":
        print("[Navigator] 🔔 Detour: checking notifications...")
        navigate_to_notifications(page)

    elif detour_type == "glance_messaging":
        print("[Navigator] 💬 Detour: glancing at messages...")
        navigate_to_messaging(page)
        random_delay(2.0, 4.0)  # Just a quick glance


def _organic_feed_browse(page, min_posts=1, max_posts=3):
    """Simulate organically browsing the LinkedIn feed.

    Scrolls through posts, pauses to "read" some, maybe likes one.
    """
    num_posts_to_read = random.randint(min_posts, max_posts)
    print(f"[Navigator] 📖 Browsing feed — reading {num_posts_to_read} posts")

    for i in range(num_posts_to_read):
        # Scroll to next post
        scroll_amount = random.randint(300, 600)
        print(f"[Navigator]   Post {i+1}/{num_posts_to_read}: scrolling {scroll_amount}px down")
        human_scroll(page, "down", scroll_amount)
        wait_for_stable(page, timeout=3000)

        # Simulate reading the post
        word_count = random.randint(30, 200)  # Estimate
        print(f"[Navigator]   Dwelling on content (~{word_count} words)")
        dwell_on_content(page, word_count)

        # 20% chance of liking a post during browsing
        roll = random.random()
        if roll < 0.20:
            print(f"[Navigator]   🎲 Roll={roll:.2f} < 0.20 — attempting like")
            _try_like_current_post(page)
        else:
            print(f"[Navigator]   🎲 Roll={roll:.2f} >= 0.20 — skipping like")


def _try_like_current_post(page):
    """Attempt to like whatever post is currently in view."""
    print("[Navigator] 👍 Attempting to like current post...")
    try:
        from linkedin.interact import _fast_click_like
        result = _fast_click_like(page)
        if result:
            print("[Navigator] ✅ Like successful")
        else:
            print("[Navigator] ⚠️ Like unsuccessful")
    except Exception as e:
        print(f"[Navigator] ❌ Like error: {e}")


def _click_people_tab(page):
    """Click the 'People' tab in search results."""
    import re
    try:
        # Give page a tiny bit of extra time to render search results
        page.wait_for_timeout(2000)

        # 1. Try direct Playwright locators for common LinkedIn tab structures
        locators = [
            page.locator("button.search-reusables__filter-pill-button").filter(has_text=re.compile(r"^\s*People\s*$", re.IGNORECASE)),
            page.locator("button.artdeco-pill").filter(has_text=re.compile(r"^\s*People\s*$", re.IGNORECASE)),
            page.get_by_role("button", name=re.compile(r"^\s*People\s*$", re.IGNORECASE)),
            page.get_by_role("link", name=re.compile(r"^\s*People\s*$", re.IGNORECASE)),
            page.locator("xpath=//button[normalize-space()='People']"),
            page.locator("xpath=//a[normalize-space()='People']")
        ]
        
        for loc in locators:
            try:
                # Wait briefly for this specific locator to appear (1.5s per locator)
                loc.first.wait_for(state="visible", timeout=1500)
                print(f"[Navigator] Clicking People tab via direct DOM locator...")
                loc.first.click(timeout=3000)
                wait_for_stable(page)
                return
            except Exception:
                continue

        # 2. Fallback: High-level most reliable URL navigation if DOM clicking fails
        print("[Navigator] Direct locators failed. Using highly reliable URL fallback for People tab...")
        
        # Extract the query from the current URL if possible
        current_url = page.url
        import urllib.parse
        query = ""
        if "keywords=" in current_url:
            try:
                query = current_url.split("keywords=")[1].split("&")[0]
            except Exception:
                pass
                
        if query:
            print(f"[Navigator] Reliable query parsed: {urllib.parse.unquote(query)}")
            page.goto(f"https://www.linkedin.com/search/results/people/?keywords={query}", wait_until="domcontentloaded")
            wait_for_stable(page)
        else:
            print("[Navigator] Could not parse query for URL fallback.")
    except Exception as e:
        print(f"[Navigator] Error navigating to People tab: {e}")


# ─── SemanticMap-Accelerated Element Interaction ─────────────────────────────

def _click_cached_or_discover(page, label, role, name, discover_fn):
    """Try to click an element using SemanticMap cache first, then discover.

    This is the core integration point for SemanticMap. On the first
    interaction, it discovers the element via ACT and caches it. On
    subsequent interactions, it skips ACT extraction entirely and uses
    the cached role/name for instant Playwright lookup.

    If a cached element fails (stale), it self-heals by invalidating
    the cache and rediscovering.

    Args:
        page: Playwright page.
        label: Semantic label (e.g., "nav_home", "search_input").
        role: Expected ARIA role (e.g., "link", "button", "textbox").
        name: Expected accessible name (e.g., "Home", "Search").
        discover_fn: ACT discovery function (e.g., find_links, find_buttons).

    Returns:
        bool: True if the element was found and clicked.
    """
    # 1. Try cache first (instant)
    cached = _smap.lookup(label)
    if cached:
        c_role = cached.get("role", role)
        c_name = cached.get("name", name)
        try:
            # Direct selector handling (healed elements)
            if c_role == "selector":
                print(f"[Navigator] ⚡ Cache hit (Direct Selector): '{label}' → {c_name}")
                page.click(c_name, timeout=5000)
                return True

            locator = page.get_by_role(c_role, name=c_name)
            if locator.count() > 0:
                bbox = locator.first.bounding_box()
                if bbox:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    print(f"[Navigator] ⚡ Cache hit: '{label}' → {c_role}:'{c_name}' at ({cx:.0f},{cy:.0f})")
                    human_click(page, cx, cy)
                    return True
        except Exception:
            pass
        # Cache stale — invalidate and rediscover
        print(f"[Navigator] 🔄 Cache stale for '{label}' — rediscovering...")
        _smap.invalidate(label)

    # 2. Discover via ACT (slower but reliable)
    tree = extract_act(page)
    elements = discover_fn(tree, name)

    if elements:
        element = elements[0]
        # Cache the discovered element for next time
        _smap.store(label, {
            "role": element.get("role", role),
            "name": element.get("name", name),
        })
        _click_act_element(page, element)
        return True

    # 3. Last Resort: Self-Healing via LLM (Gemini)
    print(f"[Navigator] ⚠️ Discovery failed for '{label}' — triggering self-healing...")
    html_content = page.content()
    # Construct intent from role and name
    intent = f"Click the {name} {role}"
    
    healing_result = heal_selector(intent, html_content)
    
    if healing_result.get("status") == "fixed" and healing_result.get("newSelector"):
        new_selector = healing_result["newSelector"]
        print(f"[Navigator] 🩹 Self-healing found new selector: {new_selector}")
        
        try:
            # Attempt to click with the new selector
            page.click(new_selector, timeout=5000)
            print(f"[Navigator] ✅ Self-healing success! Updating cache for '{label}'")
            
            # Store the new selector (as a direct selector if possible, or mapping to dummy role/name)
            # For now, we store the new selector as a special type if SemanticMap supports it
            # Or just store it as name for lookup
            _smap.store(label, {
                "role": "selector", # Special role to indicate direct click
                "name": new_selector,
            })
            return True
        except Exception as e:
            print(f"[Navigator] ❌ Retry click failed: {e}")
            
    return False


def _click_act_element(page, act_node):
    """Click an element identified by its ACT node.

    Since ACT nodes don't have direct coordinates, we use the
    accessible name to locate the element via Playwright's
    role-based selectors.

    Falls back to aria-label or text content matching.
    """
    role = act_node.get("role", "").lower()
    name = act_node.get("name", "")

    try:
        # Use Playwright's role-based locator (most reliable)
        if role and name:
            locator = page.get_by_role(role, name=name)
            if locator.count() > 0:
                # Get bounding box for human-like click
                bbox = locator.first.bounding_box()
                if bbox:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    human_click(page, cx, cy)
                    return
                else:
                    locator.first.click()
                    return
        
        # Fallback: search by accessible name
        if name:
            locator = page.get_by_text(name, exact=False)
            if locator.count() > 0:
                bbox = locator.first.bounding_box()
                if bbox:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    human_click(page, cx, cy)
                    return

        print(f"[Navigator] Could not locate element: {role}:{name}")

    except Exception as e:
        print(f"[Navigator] Error clicking ACT element ({role}:{name}): {e}")


def autonomous_move(page, goal, action_history=None):
    """Execute a single autonomous move using Navigator-Pilot orchestration.
    
    1. Perception: AXTree Snapshot (with IDs) + Screenshot Description.
    2. Orchestration: Navigator (Strategy) + Pilot (Execution).
    3. Action: Execute the Pilot's decision.
    """
    print(f"[Navigator] 🤖 Autonomous Move | Goal: {goal}")
    
    # ─── 1. Perception ──────────────────────────────────────────────────────
    
    # Assign agent IDs to the DOM
    assign_agent_ids(page)
    
    # Take snapshot (YAML)
    ax_tree_yaml = get_ax_snapshot(page)
    
    # Describe page (Screenshot)
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"auto_move_{int(time.time())}.png")
    take_screenshot(page, screenshot_path)
    page_desc = describe_page(screenshot_path)
    
    # ─── 2. Orchestration ────────────────────────────────────────────────────
    
    action = decide_action_orchestrated(goal, ax_tree_yaml, page_desc, action_history)
    print(f"[Navigator] 🎯 Action Decided: {json.dumps(action)}")
    
    # ─── 3. Action ──────────────────────────────────────────────────────────
    
    if not action:
        return None
        
    act = action.get("action")
    agent_id = action.get("id")
    
    try:
        if act == "click" and agent_id:
            loc = page.locator(f'[data-agent-id="{agent_id}"]').first
            bbox = loc.bounding_box()
            if bbox:
                cx = bbox["x"] + bbox["width"] / 2
                cy = bbox["y"] + bbox["height"] / 2
                human_click(page, cx, cy)
            else:
                loc.click()
                
        elif act == "type" and agent_id:
            text = action.get("text", "")
            loc = page.locator(f'[data-agent-id="{agent_id}"]').first
            loc.click() # Focus
            human_type(page, text)
            
        elif act == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 500)
            human_scroll(page, direction, amount)
            
        elif act == "wait":
            seconds = action.get("seconds", 2)
            time.sleep(seconds)
            
        elif act == "done":
            print(f"[Navigator] ✅ Goal Achieved: {action.get('reason', 'completed')}")
            return action
            
        # Record action in history
        if action_history is not None:
            action_history.append(action)
            
        # ─── 4. Asynchronous Verification (Blocking loop for security) ──────
        
        # We verify the action immediately after execution for high-fidelity safety
        verification = verify_action_async(page, action, f"Executed {act} on {agent_id or 'page'}")
        if verification.get("roadblock"):
            print(f"[Navigator] 🛑 ROADBLOCK DETECTED: {verification.get('details')}")
            # In a real system, this would trigger an AbortController or high-priority interrupt
            return {"action": "interrupt", "reason": "roadblock", "details": verification.get("details")}
            
        return action
        
    except Exception as e:
        print(f"[Navigator] ❌ Action Execution Failed: {e}")
        return {"action": "error", "error": str(e)}


def fast_connect(page, profile_url, note=None):
    """Execute the high-speed LinkedIn connection macro.
    
    This uses the 'ghost_macros.sendInviteMacro' injected in browser.py
    to handle the multi-step connection flow in a single JS execution.
    """
    print(f"[Navigator] 🚀 Fast-Connect Macro | Target: {profile_url}")
    
    # Ensure we are on the profile page
    if profile_url not in page.url:
        page.goto(profile_url, wait_until="domcontentloaded")
        wait_for_stable(page)
        
    # Apply stealth jitter before the macro
    from human import apply_interaction_jitter
    apply_interaction_jitter(page)
    
    # Execute the macro
    result = page.evaluate(f"window.ghost_macros.sendInviteMacro(`{note or ''}`)")
    print(f"[Navigator] 🏁 Macro Result: {json.dumps(result)}")
    
    return result
