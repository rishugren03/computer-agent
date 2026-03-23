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
from accessibility import extract_act, find_buttons, find_links, find_textboxes
from config import DETOUR_PROBABILITY, SCREENSHOT_DIR
from semantic_map import SemanticMap
from self_healing_bridge import heal_selector

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
    """Search LinkedIn using the search bar (never direct URL).

    Simulates: Click search → Type query → Press Enter
    Then waits for results naturally.
    """
    print(f"[Navigator] Searching for: {query}")

    # For LinkedIn search, the input is often a combobox, searchbox, or textbox.
    # We tell it to discover textboxes (which includes searchbox).
    clicked = _click_cached_or_discover(page, "search_input", "textbox", "Search", find_textboxes)

    if clicked:
        random_delay(0.3, 0.6)
        # Ensure we have focus! Playwright sometimes loses focus with synthetic mouse clicks.
        try:
            # Fallback to direct locator to ensure focus
            locators = [
                page.get_by_role("combobox", name="Search", exact=False),
                page.get_by_role("searchbox", name="Search", exact=False),
                page.get_by_role("textbox", name="Search", exact=False),
                page.get_by_placeholder("Search", exact=False)
            ]
            for loc in locators:
                if loc.count() > 0:
                    # click with force instead of soft focus to ensure it's active
                    loc.first.click(timeout=2000)
                    break
        except Exception as e:
            print(f"[Navigator] Warning: Could not explicitly focus search box: {e}")
            
        # Clear existing text and type new query
        page.keyboard.press("Control+a")
        random_delay(0.1, 0.2)
        page.keyboard.press("Backspace")
        random_delay(0.1, 0.2)
        
        human_type(page, query)
        random_delay(0.4, 0.8)
        page.keyboard.press("Enter")
    else:
        # Fallback: try clicking the search area by expected position
        human_click(page, 450, 25)  # Search bar is typically near top-center
        random_delay(0.5, 0.8)
        page.keyboard.press("Control+a")
        random_delay(0.1, 0.2)
        page.keyboard.press("Backspace")
        random_delay(0.1, 0.2)
        human_type(page, query)
        random_delay(0.4, 0.8)
        page.keyboard.press("Enter")

    wait_for_stable(page, timeout=8000)
    random_delay(1.0, 2.0)


def navigate_to_profile(page, name):
    """Navigate to someone's profile the way a human would.

    NEVER goes directly to /in/name. Instead:
    1. Maybe check feed first (random detour)
    2. Search for the name
    3. Click on "People" tab in results
    4. Find and click the right profile

    Args:
        page: Playwright page.
        name: Person's name to search for.
    """
    print(f"[Navigator] Finding profile: {name}")

    # Random detour (30% chance) — browse feed briefly first
    if random.random() < DETOUR_PROBABILITY:
        print("[Navigator] 📱 Quick detour: checking feed...")
        _organic_feed_browse(page, min_posts=1, max_posts=2)

    # Search for the person
    navigate_to_search(page, name)

    # Click "People" tab to filter results
    _click_people_tab(page)
    random_delay(1.0, 2.0)

    # Look for the profile in results
    # (The agent's vision/ACT system + LLM will handle clicking the right result)


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
    try:
        if not _click_cached_or_discover(page, "search_tab_people", "button", "People", find_buttons):
            # Try links too
            if not _click_cached_or_discover(page, "search_tab_people", "link", "People", find_links):
                print("[Navigator] Could not find People tab")
                return
        wait_for_stable(page)
    except Exception as e:
        print(f"[Navigator] Error clicking People tab: {e}")


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
