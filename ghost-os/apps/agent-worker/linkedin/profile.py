"""LinkedIn profile viewing with content-aware dwell time.

Simulates a real professional reviewing someone's profile:
- Scrolls through sections at reading speed
- Pauses longer on "About" and "Experience"
- Extracts profile data for personalization
"""

import random

from human import (
    human_scroll,
    random_delay,
    dwell_on_content,
    idle_fidget,
)
from browser import wait_for_stable, take_screenshot
from accessibility import extract_act, find_by_text, get_page_structure


def view_profile(page, dwell=True):
    """View the currently loaded profile with realistic dwell behavior.

    Simulates a human reading through a LinkedIn profile naturally:
    - Quick scan of header (name, headline, photo)
    - Read "About" section more carefully
    - Scroll through Experience
    - Glance at Education and Skills

    Args:
        page: Playwright page (must be on a profile page).
        dwell: If True, simulate reading. If False, just extract data.

    Returns:
        dict: Extracted profile data.
    """
    wait_for_stable(page, timeout=5000)

    # 1. Initial scan — header area (name, headline, location)
    print("[Profile] 👀 Scanning profile header...")
    idle_fidget(page, random.uniform(1.5, 3.0))

    # 2. Extract profile data
    profile_data = extract_profile_data(page)
    name = profile_data.get("name", "Unknown")
    print(f"[Profile] Viewing: {name}")

    if not dwell:
        return profile_data

    # 3. Scroll through sections with content-aware dwell
    sections = [
        ("About", 0.7),       # High attention — read carefully
        ("Experience", 0.5),   # Medium attention — scan
        ("Education", 0.3),    # Quick glance
        ("Skills", 0.2),       # Brief look
    ]

    for section_name, attention_factor in sections:
        _scroll_to_and_read_section(page, section_name, attention_factor)

    # 4. Maybe scroll back up briefly (natural behavior)
    if random.random() < 0.3:
        human_scroll(page, "up", random.randint(200, 500))
        random_delay(1.0, 2.0)

    return profile_data


def extract_profile_data(page):
    """Extract structured profile data from the current LinkedIn profile page.

    Uses a combination of DOM extraction and text parsing to get:
    - Name, headline, location
    - About section
    - Current position
    - Recent posts (if visible)

    Returns:
        dict: Profile data for personalization.
    """
    try:
        data = page.evaluate("""() => {
            const result = {
                name: '',
                headline: '',
                location: '',
                about: '',
                current_position: '',
                company: '',
                connections: '',
                url: window.location.href,
            };

            // Name — usually an h1
            const h1 = document.querySelector('h1');
            if (h1) result.name = h1.innerText.trim();

            // Headline — typically right below the name
            const headlineEl = document.querySelector('.text-body-medium');
            if (headlineEl) result.headline = headlineEl.innerText.trim();

            // Location
            const locationEl = document.querySelector('.text-body-small.inline');
            if (locationEl) result.location = locationEl.innerText.trim();

            // About section
            const aboutSection = document.querySelector('#about');
            if (aboutSection) {
                const parentSection = aboutSection.closest('section');
                if (parentSection) {
                    const spans = parentSection.querySelectorAll('span[aria-hidden="true"]');
                    const texts = [];
                    spans.forEach(s => {
                        const t = s.innerText.trim();
                        if (t.length > 20) texts.push(t);
                    });
                    result.about = texts.join(' ');
                }
            }

            // Connections count
            const connectionsEl = document.querySelector('[href*="connections"], .t-bold');
            if (connectionsEl) {
                const text = connectionsEl.innerText.trim();
                if (text.includes('connection') || /\\d+/.test(text)) {
                    result.connections = text;
                }
            }

            // Current position — first experience entry
            const expSection = document.querySelector('#experience');
            if (expSection) {
                const parentSection = expSection.closest('section');
                if (parentSection) {
                    const items = parentSection.querySelectorAll('li');
                    if (items.length > 0) {
                        const firstExp = items[0];
                        const spans = firstExp.querySelectorAll('span[aria-hidden="true"]');
                        if (spans.length >= 2) {
                            result.current_position = spans[0]?.innerText?.trim() || '';
                            result.company = spans[1]?.innerText?.trim() || '';
                        }
                    }
                }
            }

            return result;
        }""")

        return data

    except Exception as e:
        print(f"[Profile] Error extracting profile data: {e}")
        return {"name": "", "headline": "", "url": page.url}


def extract_recent_posts(page):
    """Extract recent posts visible on a profile's Activity section.

    Returns:
        list[dict]: Recent posts with content and engagement.
    """
    try:
        posts = page.evaluate("""() => {
            const results = [];
            
            // Look for activity/posts section
            const activitySection = document.querySelector('#content_collections');
            if (!activitySection) return results;

            const postCards = activitySection.querySelectorAll('.feed-shared-update-v2');
            
            for (const card of Array.from(postCards).slice(0, 5)) {
                const textEl = card.querySelector('.feed-shared-text');
                const content = textEl ? textEl.innerText.trim() : '';
                
                if (content) {
                    results.push({
                        content: content.substring(0, 500),
                        word_count: content.split(/\\s+/).length,
                    });
                }
            }
            
            return results;
        }""")

        return posts

    except Exception as e:
        print(f"[Profile] Error extracting posts: {e}")
        return []


def _scroll_to_and_read_section(page, section_name, attention_factor):
    """Scroll to a profile section and simulate reading it.

    Args:
        page: Playwright page.
        section_name: Name to search for (e.g., "About", "Experience").
        attention_factor: 0-1, how carefully to "read" (affects dwell time).
    """
    try:
        # Try to find the section
        tree = extract_act(page)
        section_nodes = find_by_text(tree, section_name)

        if section_nodes:
            # Scroll down to find section
            human_scroll(page, "down", random.randint(250, 500))
            wait_for_stable(page, timeout=2000)

            # Dwell based on attention factor
            word_count = random.randint(30, 150)
            dwell_time = (word_count / 200) * 60 * attention_factor  # Scaled dwell
            dwell_time = max(1.0, min(dwell_time, 6.0))  # 1-6 seconds

            idle_fidget(page, dwell_time)

    except Exception:
        # Non-critical — just scroll down a bit
        human_scroll(page, "down", random.randint(200, 300))
        random_delay(0.5, 1.5)
