"""Sleep/wake cycle scheduler synced to user timezone.

Ensures the agent only operates during natural waking hours
and takes realistic breaks between sessions.
"""

import random
import time
from datetime import datetime

from config import (
    ACTIVE_HOURS_START,
    ACTIVE_HOURS_END,
    SESSION_MIN_MINUTES,
    SESSION_MAX_MINUTES,
    BREAK_MIN_MINUTES,
    BREAK_MAX_MINUTES,
    BREAK_PROBABILITY,
    USER_TIMEZONE,
)


def get_local_hour():
    """Get the current hour in the user's timezone.

    Returns:
        int: Hour (0-23) in user's local time.
    """
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(USER_TIMEZONE)
        now = datetime.now(tz)
        return now.hour
    except Exception:
        # Fallback: use system local time
        return datetime.now().hour


def is_active_hours():
    """Check if it's currently within active operating hours.

    The agent should only run between ACTIVE_HOURS_START and
    ACTIVE_HOURS_END in the user's timezone.

    Returns:
        bool: True if within active hours.
    """
    hour = get_local_hour()
    return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END


def get_sleep_duration():
    """Calculate how many seconds until the next active window.

    Returns:
        int: Seconds to sleep. 0 if currently in active hours.
    """
    if is_active_hours():
        return 0

    hour = get_local_hour()

    if hour >= ACTIVE_HOURS_END:
        # After active hours — sleep until tomorrow morning
        hours_until_active = (24 - hour) + ACTIVE_HOURS_START
    else:
        # Before active hours (e.g., 3 AM) — sleep until start
        hours_until_active = ACTIVE_HOURS_START - hour

    # Add some randomness (±30 min) to avoid exact timing
    base_seconds = hours_until_active * 3600
    jitter = random.randint(-1800, 1800)

    return max(0, base_seconds + jitter)


def random_session_duration():
    """Generate a random session duration.

    Each GhostAgent session lasts 15-45 minutes, mimicking
    a professional checking LinkedIn during a work break.

    Returns:
        int: Session duration in seconds.
    """
    minutes = random.uniform(SESSION_MIN_MINUTES, SESSION_MAX_MINUTES)
    return int(minutes * 60)


def should_take_break():
    """Determine if the agent should take a micro-break right now.

    15% probability after each action cycle.

    Returns:
        bool: True if a break should be taken.
    """
    return random.random() < BREAK_PROBABILITY


def get_break_duration():
    """Get the duration of a micro-break.

    Returns:
        int: Break duration in seconds (2-5 minutes).
    """
    minutes = random.uniform(BREAK_MIN_MINUTES, BREAK_MAX_MINUTES)
    return int(minutes * 60)


def wait_for_active_hours():
    """Block until active hours begin.

    Prints countdown updates every 30 minutes.
    """
    sleep_seconds = get_sleep_duration()

    if sleep_seconds <= 0:
        return

    print(f"[Scheduler] 😴 Sleeping for {sleep_seconds // 3600}h {(sleep_seconds % 3600) // 60}m")
    print(f"[Scheduler] Will resume at ~{ACTIVE_HOURS_START}:00 {USER_TIMEZONE}")

    while sleep_seconds > 0:
        chunk = min(sleep_seconds, 1800)  # Update every 30 min
        time.sleep(chunk)
        sleep_seconds -= chunk

        if sleep_seconds > 0:
            print(f"[Scheduler] ⏰ {sleep_seconds // 3600}h {(sleep_seconds % 3600) // 60}m remaining...")

    print("[Scheduler] 🌅 Active hours! Starting session...")


def get_schedule_info():
    """Get current schedule status for display.

    Returns:
        dict: Schedule info.
    """
    return {
        "current_hour": get_local_hour(),
        "timezone": USER_TIMEZONE,
        "is_active": is_active_hours(),
        "active_window": f"{ACTIVE_HOURS_START}:00 - {ACTIVE_HOURS_END}:00",
        "sleep_seconds": get_sleep_duration(),
    }
