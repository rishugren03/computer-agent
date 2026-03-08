"""
reCAPTCHA v2 solver using vision LLM + human-like interactions.

Flow:
  1. Detect reCAPTCHA on page
  2. Click the checkbox with human-like movement
  3. If image challenge appears, screenshot → vision LLM → click tiles → verify
  4. Retry up to MAX_RETRIES times
"""

import time
import random
import os

from dom import detect_recaptcha
from human import human_click, random_delay, human_move_to
from llm import analyze_image


MAX_RETRIES = 5
SCREENSHOT_DIR = "/tmp/recaptcha_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def solve_recaptcha(page):
    """
    Main entry point: detect and solve reCAPTCHA on the given page.
    Returns True if solved, False if failed.
    """

    print("[reCAPTCHA] Checking for reCAPTCHA on page...")
    random_delay(1.0, 2.0)

    recaptcha = detect_recaptcha(page)

    if not recaptcha["found"]:
        print("[reCAPTCHA] No reCAPTCHA detected.")
        return False

    print("[reCAPTCHA] reCAPTCHA detected! Attempting to solve...")

    # Phase 1: Click the checkbox
    success = _click_checkbox(page, recaptcha)

    if success:
        print("[reCAPTCHA] ✓ Solved by checkbox click alone!")
        return True

    # Phase 2: Solve image challenge
    for attempt in range(MAX_RETRIES):
        print(f"[reCAPTCHA] Image challenge attempt {attempt + 1}/{MAX_RETRIES}")

        # Re-detect frames since they may have reloaded
        recaptcha = detect_recaptcha(page)

        if not recaptcha["challenge_frame"]:
            # Check if already solved
            if _is_checkbox_checked(page, recaptcha):
                print("[reCAPTCHA] ✓ Already solved!")
                return True
            print("[reCAPTCHA] No challenge frame found, waiting...")
            random_delay(2.0, 3.0)
            continue

        solved = _solve_image_challenge(page, recaptcha)

        if solved:
            print("[reCAPTCHA] ✓ Image challenge solved!")
            return True

        random_delay(1.5, 3.0)

    print("[reCAPTCHA] ✗ Failed after all retries.")
    return False


def _click_checkbox(page, recaptcha):
    """Click the 'I am not a robot' checkbox. Returns True if that alone solved it."""

    # If the frame was detached, re-detect
    checkbox_frame = recaptcha.get("checkbox_frame")
    if not checkbox_frame:
        print("[reCAPTCHA] No checkbox frame found, re-detecting...")
        recaptcha = detect_recaptcha(page)
        checkbox_frame = recaptcha.get("checkbox_frame")

    if not checkbox_frame:
        print("[reCAPTCHA] Still no checkbox frame.")
        return False

    for attempt in range(2):
        try:
            # Wait for the checkbox to be ready
            checkbox = checkbox_frame.wait_for_selector(
                "#recaptcha-anchor", timeout=8000
            )

            if not checkbox:
                print("[reCAPTCHA] Checkbox element not found.")
                return False

            # Get the bounding box (already in page coordinates from patchright)
            bbox = checkbox.bounding_box()
            if not bbox:
                print("[reCAPTCHA] Could not get checkbox bounding box.")
                return False

            center_x = bbox["x"] + bbox["width"] / 2
            center_y = bbox["y"] + bbox["height"] / 2

            print(f"[reCAPTCHA] Clicking checkbox at ({center_x:.0f}, {center_y:.0f})")

            # Small pre-movement wiggle
            human_move_to(page, center_x - random.randint(50, 150), center_y + random.randint(-30, 30))
            random_delay(0.3, 0.8)
            human_click(page, center_x, center_y)

            # Wait and check if solved
            random_delay(2.0, 4.0)

            return _is_checkbox_checked(page, recaptcha)

        except Exception as e:
            error_str = str(e)
            if "detached" in error_str.lower() and attempt == 0:
                print(f"[reCAPTCHA] Frame detached, re-detecting frames...")
                random_delay(1.0, 2.0)
                recaptcha = detect_recaptcha(page)
                checkbox_frame = recaptcha.get("checkbox_frame")
                if not checkbox_frame:
                    print("[reCAPTCHA] Could not find checkbox frame after re-detect.")
                    return False
                continue
            print(f"[reCAPTCHA] Checkbox click error: {e}")
            return False

    return False


def _is_checkbox_checked(page, recaptcha=None):
    """Check if the reCAPTCHA checkbox is showing the green checkmark."""

    if recaptcha is None:
        recaptcha = detect_recaptcha(page)

    checkbox_frame = recaptcha.get("checkbox_frame")
    if not checkbox_frame:
        return False

    try:
        # The checkbox gets aria-checked="true" when solved
        is_checked = checkbox_frame.evaluate("""
            () => {
                const anchor = document.querySelector('#recaptcha-anchor');
                return anchor && anchor.getAttribute('aria-checked') === 'true';
            }
        """)
        return is_checked
    except Exception:
        return False


def _solve_image_challenge(page, recaptcha):
    """Solve the image grid challenge using vision LLM."""

    challenge_frame = recaptcha.get("challenge_frame")
    if not challenge_frame:
        return False

    try:
        # Wait for challenge content to load
        challenge_frame.wait_for_selector(".rc-imageselect-challenge", timeout=8000)
        random_delay(1.0, 2.0)

        # Get the challenge instruction text
        instruction = challenge_frame.evaluate("""
            () => {
                const strong = document.querySelector('.rc-imageselect-desc-wrapper');
                return strong ? strong.innerText : '';
            }
        """)

        print(f"[reCAPTCHA] Challenge instruction: {instruction}")

        if not instruction:
            print("[reCAPTCHA] Could not read challenge instruction.")
            return False

        # Take screenshot of the challenge area
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"challenge_{int(time.time())}.png")

        # Screenshot the challenge image area
        challenge_table = challenge_frame.query_selector(".rc-imageselect-target")
        if challenge_table:
            challenge_table.screenshot(path=screenshot_path)
        else:
            # Fallback: screenshot the entire challenge
            challenge_frame.locator(".rc-imageselect-challenge").screenshot(
                path=screenshot_path
            )

        print(f"[reCAPTCHA] Challenge screenshot saved: {screenshot_path}")

        # Determine grid size
        grid_size = _detect_grid_size(challenge_frame)
        print(f"[reCAPTCHA] Grid size: {grid_size}x{grid_size}")

        # Ask vision LLM which tiles to click
        tiles_to_click = _ask_vision_llm(screenshot_path, instruction, grid_size)

        if not tiles_to_click:
            print("[reCAPTCHA] Vision LLM returned no tiles to click.")
            # Click reload button to get a new challenge
            _click_reload(page, challenge_frame)
            return False

        print(f"[reCAPTCHA] Vision LLM says click tiles: {tiles_to_click}")

        # Click the identified tiles
        _click_tiles(page, challenge_frame, tiles_to_click, grid_size)

        random_delay(0.5, 1.0)

        # Click verify button
        _click_verify(page, challenge_frame)

        random_delay(2.0, 4.0)

        # Check if solved
        recaptcha_updated = detect_recaptcha(page)
        if _is_checkbox_checked(page, recaptcha_updated):
            return True

        # Check if new tiles appeared (dynamic challenge) — the challenge is still open
        challenge_still_visible = False
        try:
            challenge_still_visible = challenge_frame.evaluate("""
                () => {
                    const el = document.querySelector('.rc-imageselect-challenge');
                    return el && el.offsetParent !== null;
                }
            """)
        except Exception:
            pass

        if challenge_still_visible:
            print("[reCAPTCHA] Challenge still visible, may need more tile selections...")
            return False

        return False

    except Exception as e:
        print(f"[reCAPTCHA] Image challenge error: {e}")
        return False


def _detect_grid_size(challenge_frame):
    """Detect whether the challenge is a 3x3 or 4x4 grid."""
    try:
        rows = challenge_frame.evaluate("""
            () => {
                const table = document.querySelector('.rc-imageselect-target table');
                if (!table) return 3;
                const rows = table.querySelectorAll('tr');
                return rows.length;
            }
        """)
        return rows if rows in (3, 4) else 3
    except Exception:
        return 3


def _ask_vision_llm(screenshot_path, instruction, grid_size):
    """
    Send the challenge screenshot to Gemini Vision and ask which tiles match.
    Returns a list of tile indices (0-indexed, left-to-right, top-to-bottom).
    """

    total_tiles = grid_size * grid_size

    prompt = f"""You are solving an image recognition challenge. 

The image shows a {grid_size}x{grid_size} grid of image tiles, numbered 0 to {total_tiles - 1} from left-to-right, top-to-bottom.

The challenge instruction is: "{instruction}"

Analyze each tile in the grid carefully. Identify which tiles match the challenge instruction.

Return a JSON object with a single key "tiles" containing an array of tile indices (0-indexed) that match.

Example response: {{"tiles": [0, 3, 6]}}

If no tiles match, return: {{"tiles": []}}

Be thorough — it's better to include a tile you're uncertain about than to miss one.
"""

    try:
        result = analyze_image(screenshot_path, prompt)

        if isinstance(result, dict) and "tiles" in result:
            tiles = result["tiles"]
            # Validate: only keep valid indices
            return [t for t in tiles if isinstance(t, int) and 0 <= t < total_tiles]

        return []

    except Exception as e:
        print(f"[reCAPTCHA] Vision LLM error: {e}")
        return []


def _click_tiles(page, challenge_frame, tile_indices, grid_size):
    """Click the specified tiles in the image grid using human-like clicks."""

    try:
        # Get all tile elements
        tiles = challenge_frame.query_selector_all(".rc-imageselect-tile")

        if not tiles:
            # Try alternative selector
            tiles = challenge_frame.query_selector_all("td.rc-imageselect-tile")

        if not tiles:
            print("[reCAPTCHA] Could not find tile elements.")
            return

        for idx in tile_indices:
            if idx >= len(tiles):
                print(f"[reCAPTCHA] Tile index {idx} out of range (only {len(tiles)} tiles)")
                continue

            tile = tiles[idx]
            bbox = tile.bounding_box()

            if not bbox:
                continue

            center_x = bbox["x"] + bbox["width"] / 2
            center_y = bbox["y"] + bbox["height"] / 2

            print(f"[reCAPTCHA] Clicking tile {idx} at ({center_x:.0f}, {center_y:.0f})")
            human_click(page, center_x, center_y)
            random_delay(0.3, 0.8)

    except Exception as e:
        print(f"[reCAPTCHA] Tile click error: {e}")


def _click_verify(page, challenge_frame):
    """Click the Verify / Next button."""
    try:
        verify_btn = challenge_frame.query_selector("#recaptcha-verify-button")
        if verify_btn:
            bbox = verify_btn.bounding_box()
            if bbox:
                center_x = bbox["x"] + bbox["width"] / 2
                center_y = bbox["y"] + bbox["height"] / 2
                print(f"[reCAPTCHA] Clicking Verify at ({center_x:.0f}, {center_y:.0f})")
                human_click(page, center_x, center_y)
    except Exception as e:
        print(f"[reCAPTCHA] Verify click error: {e}")


def _click_reload(page, challenge_frame):
    """Click the reload button to get a new challenge."""
    try:
        reload_btn = challenge_frame.query_selector("#recaptcha-reload-button")
        if reload_btn:
            bbox = reload_btn.bounding_box()
            if bbox:
                center_x = bbox["x"] + bbox["width"] / 2
                center_y = bbox["y"] + bbox["height"] / 2
                print(f"[reCAPTCHA] Clicking Reload at ({center_x:.0f}, {center_y:.0f})")
                human_click(page, center_x, center_y)
                random_delay(1.5, 3.0)
    except Exception as e:
        print(f"[reCAPTCHA] Reload click error: {e}")
