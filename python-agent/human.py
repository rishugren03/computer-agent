"""Human-like interaction utilities to evade bot detection."""

import random
import time
import math


def random_delay(min_s=0.3, max_s=1.2):
    """Sleep for a random duration to break timing patterns."""
    time.sleep(random.uniform(min_s, max_s))


def _bezier_points(start, end, num_points=25):
    """Generate points along a cubic Bézier curve between start and end."""
    sx, sy = start
    ex, ey = end

    # Two random control points to make the path curved and natural
    dx = ex - sx
    dy = ey - sy
    cp1 = (
        sx + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
        sy + dy * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
    )
    cp2 = (
        sx + dx * random.uniform(0.6, 0.8) + random.uniform(-30, 30),
        sy + dy * random.uniform(0.6, 0.8) + random.uniform(-30, 30),
    )

    points = []
    for i in range(num_points + 1):
        t = i / num_points
        u = 1 - t
        # Cubic Bézier formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
        x = u**3 * sx + 3 * u**2 * t * cp1[0] + 3 * u * t**2 * cp2[0] + t**3 * ex
        y = u**3 * sy + 3 * u**2 * t * cp1[1] + 3 * u * t**2 * cp2[1] + t**3 * ey
        points.append((int(x), int(y)))

    return points


def human_move_to(page, x, y):
    """Move the mouse to (x, y) along a natural curved path."""
    # Get current mouse position (default to a random starting area)
    try:
        current = page.evaluate("() => ({x: window._mouseX || 100, y: window._mouseY || 100})")
        start = (current["x"], current["y"])
    except Exception:
        start = (random.randint(50, 200), random.randint(50, 200))

    points = _bezier_points(start, (x, y), num_points=random.randint(15, 30))

    for px, py in points:
        page.mouse.move(px, py)
        time.sleep(random.uniform(0.005, 0.02))

    # Track position for next call
    page.evaluate(f"() => {{ window._mouseX = {x}; window._mouseY = {y}; }}")


def human_click(page, x, y):
    """Move to a position with slight random offset, then click with human-like timing."""
    # Add small random offset to avoid pixel-perfect clicks
    offset_x = random.randint(-3, 3)
    offset_y = random.randint(-3, 3)
    target_x = x + offset_x
    target_y = y + offset_y

    human_move_to(page, target_x, target_y)
    random_delay(0.05, 0.15)
    page.mouse.click(target_x, target_y)
    random_delay(0.1, 0.3)


def human_type(page, text):
    """Type text character by character with variable inter-key delays."""
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.18))
