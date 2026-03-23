"""Human-like interaction engine for GhostAgent.

Simulates a real professional using LinkedIn:
- Bézier-curved mouse paths with micro-jitters and overshoot
- Click pressure simulation (variable mouse down/up timing)
- Realistic typing with variable speed, word pauses, and occasional typos
- Inertial scrolling that mimics trackpad physics
- Content-aware dwell time (reading simulation)
- Idle fidget movements during pauses
"""

import random
import time
import math

from config import (
    CLICK_DURATION_MIN_MS,
    CLICK_DURATION_MAX_MS,
    OVERSHOOT_PROBABILITY,
    OVERSHOOT_MIN_PX,
    OVERSHOOT_MAX_PX,
    MICRO_JITTER_PX,
    TYPING_WPM_MIN,
    TYPING_WPM_MAX,
    TYPO_PROBABILITY,
    WORD_PAUSE_MIN_MS,
    WORD_PAUSE_MAX_MS,
    PUNCTUATION_PAUSE_MIN_MS,
    PUNCTUATION_PAUSE_MAX_MS,
    READING_WPM_MIN,
    READING_WPM_MAX,
    DWELL_MIN_SECONDS,
    DWELL_MAX_SECONDS,
    SCROLL_SPEED_MIN,
    SCROLL_SPEED_MAX,
)


# ─── Random Delays ──────────────────────────────────────────────────────────

def random_delay(min_s=0.3, max_s=1.2):
    """Sleep for a random duration to break timing patterns."""
    time.sleep(random.uniform(min_s, max_s))


def reading_delay(word_count):
    """Calculate a realistic reading delay based on word count.

    Simulates a real professional scanning/reading content at
    a natural variable speed.

    Args:
        word_count: Number of words in the content.

    Returns:
        float: Seconds to "read" the content.
    """
    wpm = random.uniform(READING_WPM_MIN, READING_WPM_MAX)
    base_time = (word_count / wpm) * 60  # Convert to seconds
    # Add some variance — people don't read at constant speed
    jitter = random.uniform(-0.15, 0.25) * base_time
    result = max(DWELL_MIN_SECONDS, min(base_time + jitter, DWELL_MAX_SECONDS))
    return result


# ─── Mouse Movement ─────────────────────────────────────────────────────────

def _bezier_points(start, end, num_points=25):
    """Generate points along a cubic Bézier curve with micro-jitters.

    Creates a natural, curved mouse path between two points with
    small random perturbations to simulate hand tremor on a trackpad.
    """
    sx, sy = start
    ex, ey = end

    # Distance between points affects curve amplitude
    distance = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
    curve_amplitude = min(distance * 0.3, 80)  # Cap curve deviation

    dx = ex - sx
    dy = ey - sy

    # Two random control points for natural curvature
    cp1 = (
        sx + dx * random.uniform(0.2, 0.4) + random.uniform(-curve_amplitude, curve_amplitude),
        sy + dy * random.uniform(0.2, 0.4) + random.uniform(-curve_amplitude, curve_amplitude),
    )
    cp2 = (
        sx + dx * random.uniform(0.6, 0.8) + random.uniform(-curve_amplitude * 0.6, curve_amplitude * 0.6),
        sy + dy * random.uniform(0.6, 0.8) + random.uniform(-curve_amplitude * 0.6, curve_amplitude * 0.6),
    )

    points = []
    for i in range(num_points + 1):
        t = i / num_points
        u = 1 - t

        # Cubic Bézier formula
        x = u**3 * sx + 3 * u**2 * t * cp1[0] + 3 * u * t**2 * cp2[0] + t**3 * ex
        y = u**3 * sy + 3 * u**2 * t * cp1[1] + 3 * u * t**2 * cp2[1] + t**3 * ey

        # Add micro-jitters (hand tremor simulation)
        if 0 < i < num_points:  # Don't jitter start/end points
            x += random.uniform(-MICRO_JITTER_PX, MICRO_JITTER_PX)
            y += random.uniform(-MICRO_JITTER_PX, MICRO_JITTER_PX)

        points.append((int(x), int(y)))

    return points


def human_move_to(page, x, y):
    """Move the mouse to (x, y) along a natural curved path with jitter.

    Simulates real trackpad/mouse movement with:
    - Bézier curve path (not straight line)
    - Variable speed (fast in middle, slow at edges)
    - Micro-jitter during movement
    """
    # Get current mouse position
    try:
        current = page.evaluate("() => ({x: window._mouseX || 100, y: window._mouseY || 100})")
        start = (current["x"], current["y"])
    except Exception:
        start = (random.randint(50, 300), random.randint(50, 300))

    num_points = random.randint(18, 35)
    points = _bezier_points(start, (x, y), num_points=num_points)

    for i, (px, py) in enumerate(points):
        page.mouse.move(px, py)

        # Variable speed: slower at start and end, faster in the middle
        progress = i / len(points)
        if progress < 0.2 or progress > 0.8:
            # Slower at edges (acceleration / deceleration)
            time.sleep(random.uniform(0.008, 0.025))
        else:
            # Faster in the middle
            time.sleep(random.uniform(0.003, 0.012))

    # Track position for next call
    page.evaluate(f"() => {{ window._mouseX = {x}; window._mouseY = {y}; }}")


def human_click(page, x, y):
    """Click with realistic behavior: move → optional overshoot → press with variable duration.

    Simulates:
    - Natural mouse movement to target
    - 20% chance of overshooting then correcting (trackpad behavior)
    - Variable click hold duration (75-200ms) to simulate finger pressure
    - Small random offset from exact coordinates
    """
    # Small random offset — humans don't click pixel-perfect
    offset_x = random.randint(-4, 4)
    offset_y = random.randint(-4, 4)
    target_x = x + offset_x
    target_y = y + offset_y

    # Overshoot simulation (20% of the time)
    if random.random() < OVERSHOOT_PROBABILITY:
        overshoot_px = random.randint(OVERSHOOT_MIN_PX, OVERSHOOT_MAX_PX)
        overshoot_dir_x = random.choice([-1, 1])
        overshoot_dir_y = random.choice([-1, 1])

        overshoot_x = target_x + overshoot_px * overshoot_dir_x
        overshoot_y = target_y + overshoot_px * overshoot_dir_y

        # Move to overshoot position first
        human_move_to(page, overshoot_x, overshoot_y)
        time.sleep(random.uniform(0.05, 0.12))

        # Then correct to actual target (short, quick movement)
        page.mouse.move(target_x, target_y)
        time.sleep(random.uniform(0.03, 0.08))
    else:
        human_move_to(page, target_x, target_y)

    random_delay(0.05, 0.15)

    # Click pressure simulation: variable hold duration
    click_duration_ms = random.uniform(CLICK_DURATION_MIN_MS, CLICK_DURATION_MAX_MS)
    page.mouse.down()
    time.sleep(click_duration_ms / 1000)  # Convert ms to seconds
    page.mouse.up()

    random_delay(0.08, 0.25)


def human_double_click(page, x, y):
    """Double-click with realistic timing between clicks."""
    human_click(page, x, y)
    time.sleep(random.uniform(0.05, 0.12))
    # Second click is faster — just press/release at current position
    click_duration_ms = random.uniform(CLICK_DURATION_MIN_MS, CLICK_DURATION_MAX_MS * 0.7)
    page.mouse.down()
    time.sleep(click_duration_ms / 1000)
    page.mouse.up()
    random_delay(0.1, 0.3)


# ─── Typing ──────────────────────────────────────────────────────────────────

def human_type(page, text):
    """Type text with realistic variable speed, word pauses, and occasional typos.

    Simulates a professional typing:
    - Variable inter-key delays based on character pairs
    - Extra pauses at word boundaries
    - Longer pauses after punctuation
    - Occasional typos with immediate backspace correction (3% chance)
    """
    # Calculate base delay from typing WPM
    wpm = random.uniform(TYPING_WPM_MIN, TYPING_WPM_MAX)
    chars_per_second = (wpm * 5) / 60  # Average 5 chars per word
    base_delay = 1 / chars_per_second

    for i, char in enumerate(text):
        # Occasional typo simulation
        if random.random() < TYPO_PROBABILITY and char.isalpha():
            # Type a wrong character
            nearby_keys = _get_nearby_keys(char)
            if nearby_keys:
                wrong_char = random.choice(nearby_keys)
                page.keyboard.type(wrong_char)
                time.sleep(random.uniform(0.1, 0.3))  # "Notice" the typo
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.05, 0.15))

        # Type the correct character
        page.keyboard.type(char)

        # Variable inter-key delay
        delay = base_delay * random.uniform(0.6, 1.5)

        # Extra pause at word boundaries (space)
        if char == " ":
            delay += random.uniform(WORD_PAUSE_MIN_MS, WORD_PAUSE_MAX_MS) / 1000

        # Extra pause after punctuation
        elif char in ".!?,;:":
            delay += random.uniform(PUNCTUATION_PAUSE_MIN_MS, PUNCTUATION_PAUSE_MAX_MS) / 1000

        # Slight pause before capital letters (shift key)
        elif char.isupper() and i > 0:
            delay += random.uniform(0.02, 0.06)

        time.sleep(delay)


def _get_nearby_keys(char):
    """Get keyboard-adjacent keys for realistic typo simulation."""
    keyboard_proximity = {
        'a': ['s', 'q', 'w', 'z'],
        'b': ['v', 'g', 'h', 'n'],
        'c': ['x', 'd', 'f', 'v'],
        'd': ['s', 'e', 'r', 'f', 'c', 'x'],
        'e': ['w', 'r', 'd', 's'],
        'f': ['d', 'r', 't', 'g', 'v', 'c'],
        'g': ['f', 't', 'y', 'h', 'b', 'v'],
        'h': ['g', 'y', 'u', 'j', 'n', 'b'],
        'i': ['u', 'o', 'k', 'j'],
        'j': ['h', 'u', 'i', 'k', 'n', 'm'],
        'k': ['j', 'i', 'o', 'l', 'm'],
        'l': ['k', 'o', 'p'],
        'm': ['n', 'j', 'k'],
        'n': ['b', 'h', 'j', 'm'],
        'o': ['i', 'p', 'l', 'k'],
        'p': ['o', 'l'],
        'q': ['w', 'a'],
        'r': ['e', 't', 'f', 'd'],
        's': ['a', 'w', 'e', 'd', 'x', 'z'],
        't': ['r', 'y', 'g', 'f'],
        'u': ['y', 'i', 'j', 'h'],
        'v': ['c', 'f', 'g', 'b'],
        'w': ['q', 'e', 's', 'a'],
        'x': ['z', 's', 'd', 'c'],
        'y': ['t', 'u', 'h', 'g'],
        'z': ['a', 's', 'x'],
    }
    lower = char.lower()
    return keyboard_proximity.get(lower, [])


# ─── Scrolling ───────────────────────────────────────────────────────────────

def human_scroll(page, direction="down", amount=None):
    """Scroll with inertial physics (fast start, gradual deceleration).

    Simulates trackpad scrolling where the page accelerates then
    gradually slows to a stop.
    """
    if amount is None:
        amount = random.randint(SCROLL_SPEED_MIN, SCROLL_SPEED_MAX)

    if direction == "up":
        amount = -amount

    # Ensure mouse is over the scrollable content area so wheel events work
    try:
        vw = page.evaluate("() => window.innerWidth")
        vh = page.evaluate("() => window.innerHeight")
        # Move to center of viewport (over feed content, not nav bar)
        cx = vw // 2 + random.randint(-50, 50)
        cy = vh // 2 + random.randint(-30, 30)
        page.mouse.move(cx, cy)
        time.sleep(random.uniform(0.05, 0.12))
    except Exception:
        pass  # Best effort — proceed with scroll anyway

    # Split into multiple small scrolls with decreasing magnitude (inertia)
    num_steps = random.randint(4, 8)
    remaining = amount

    for i in range(num_steps):
        # Each step scrolls a decreasing portion (inertial decay)
        fraction = (num_steps - i) / sum(range(1, num_steps + 1))
        step_amount = int(remaining * fraction)
        if step_amount == 0:
            break

        page.mouse.wheel(0, step_amount)
        remaining -= step_amount

        # Inter-scroll delay increases (deceleration)
        time.sleep(random.uniform(0.02, 0.05) * (1 + i * 0.3))

    # Scroll any remaining pixels
    if remaining != 0:
        page.mouse.wheel(0, remaining)

    random_delay(0.2, 0.5)


def scroll_to_element(page, bbox):
    """Scroll an element into view with natural-looking scroll behavior.

    Instead of jumping directly, scrolls in smooth increments.
    """
    viewport_height = page.evaluate("() => window.innerHeight")
    element_y = bbox["y"]
    current_scroll = page.evaluate("() => window.scrollY")

    # Calculate how much to scroll
    target_scroll = element_y - viewport_height * random.uniform(0.3, 0.5)
    scroll_delta = target_scroll - current_scroll

    if abs(scroll_delta) < 50:
        return  # Already in view

    # Scroll in the right direction
    direction = "down" if scroll_delta > 0 else "up"
    human_scroll(page, direction, abs(int(scroll_delta)))


# ─── Idle / Fidget ───────────────────────────────────────────────────────────

def idle_fidget(page, duration_seconds=None):
    """Simulate idle behavior — tiny random mouse movements while "reading".

    Real users don't keep the mouse perfectly still while reading.
    This adds small, slow movements around the current position.
    """
    if duration_seconds is None:
        duration_seconds = random.uniform(1.0, 3.0)

    try:
        current = page.evaluate("() => ({x: window._mouseX || 400, y: window._mouseY || 300})")
        cx, cy = current["x"], current["y"]
    except Exception:
        return  # Can't fidget without knowing position

    end_time = time.time() + duration_seconds

    while time.time() < end_time:
        # Small random movement (1-5px)
        dx = random.randint(-5, 5)
        dy = random.randint(-5, 5)
        page.mouse.move(cx + dx, cy + dy)
        time.sleep(random.uniform(0.3, 0.8))
        cx += dx // 2  # Drift slightly
        cy += dy // 2


def dwell_on_content(page, word_count):
    """Simulate a human reading content: idle fidget for reading_delay duration."""
    delay = reading_delay(word_count)
    idle_fidget(page, delay)

# Antigravity Specific Alias
smooth_move_and_click = human_click
