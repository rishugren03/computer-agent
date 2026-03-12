"""48-Hour Ghost Mode Warm-Up Sequence.

When GhostAgent first connects to a LinkedIn account, it does ZERO
outreach for 48 hours. This builds a natural hardware fingerprint
in LinkedIn's detection systems.

Warm-up activities (all organic, zero outreach):
- Day 1: Scroll feed, view own profile, like 2-3 posts
- Day 2: View 5-10 profiles in own network, read articles, like 3-5 posts
"""

import json
import os
import time
import random

from config import WARMUP_DURATION_HOURS, DATA_DIR
from human import random_delay, dwell_on_content, human_scroll
from navigator import (
    navigate_to_feed,
    navigate_to_notifications,
    navigate_to_my_network,
    _organic_feed_browse,
)
from browser import wait_for_stable


WARMUP_STATE_FILE = os.path.join(DATA_DIR, "warmup_state.json")


class WarmupSequence:
    """Manages the 48-hour warm-up progression.

    State is persisted to disk so it survives restarts.
    """

    def __init__(self):
        self.state = {
            "started_at": None,
            "completed": False,
            "sessions": [],        # List of session timestamps
            "total_likes": 0,
            "total_scrolls": 0,
            "total_profile_views": 0,
            "total_feed_reads": 0,
            "phase": "not_started",  # not_started → day_1 → day_2 → completed
        }
        self._load()

    def _load(self):
        """Load warm-up state from disk."""
        try:
            if os.path.exists(WARMUP_STATE_FILE):
                with open(WARMUP_STATE_FILE, "r") as f:
                    saved = json.load(f)
                    self.state.update(saved)
                    print(f"[Warmup] Resumed — Phase: {self.state['phase']}")
        except Exception as e:
            print(f"[Warmup] Could not load state: {e}")

    def _save(self):
        """Persist warm-up state to disk."""
        try:
            os.makedirs(os.path.dirname(WARMUP_STATE_FILE) or DATA_DIR, exist_ok=True)
            with open(WARMUP_STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[Warmup] Could not save state: {e}")

    @property
    def is_complete(self):
        """Check if the warm-up period has passed."""
        if self.state["completed"]:
            return True

        if self.state["started_at"] is None:
            return False

        elapsed_hours = (time.time() - self.state["started_at"]) / 3600
        if elapsed_hours >= WARMUP_DURATION_HOURS:
            self.state["completed"] = True
            self.state["phase"] = "completed"
            self._save()
            return True

        return False

    @property
    def hours_remaining(self):
        """How many hours until warm-up is complete."""
        if self.is_complete:
            return 0
        if self.state["started_at"] is None:
            return WARMUP_DURATION_HOURS

        elapsed = (time.time() - self.state["started_at"]) / 3600
        return max(0, WARMUP_DURATION_HOURS - elapsed)

    @property
    def current_phase(self):
        """Determine current phase based on elapsed time."""
        if self.state["completed"]:
            return "completed"
        if self.state["started_at"] is None:
            return "not_started"

        elapsed_hours = (time.time() - self.state["started_at"]) / 3600
        if elapsed_hours < 24:
            return "day_1"
        elif elapsed_hours < 48:
            return "day_2"
        else:
            return "completed"

    def run_session(self, page):
        """Execute one warm-up session appropriate for the current phase.

        Each session is 10-20 minutes of organic activity.

        Args:
            page: Playwright page (must be logged in).
        """
        # Start tracking if this is the first session
        if self.state["started_at"] is None:
            self.state["started_at"] = time.time()
            self.state["phase"] = "day_1"
            self._save()
            print("[Warmup] 🚀 Starting 48-hour warm-up sequence!")

        if self.is_complete:
            print("[Warmup] ✅ Warm-up already complete!")
            return

        phase = self.current_phase
        self.state["phase"] = phase
        session_start = time.time()

        print(f"[Warmup] 📋 Running {phase} session ({self.hours_remaining:.1f}h remaining)")

        if phase == "day_1":
            self._day_1_session(page)
        elif phase == "day_2":
            self._day_2_session(page)

        # Record session
        self.state["sessions"].append({
            "timestamp": time.time(),
            "phase": phase,
            "duration_minutes": (time.time() - session_start) / 60,
        })
        self._save()

    def _day_1_session(self, page):
        """Day 1: Very light activity. Establishing presence.

        Activities:
        - Scroll through feed (5-10 posts)
        - View own profile
        - Like 2-3 posts
        """
        print("[Warmup] Day 1: Light browsing session")

        # 1. Browse the feed
        navigate_to_feed(page)
        _organic_feed_browse(page, min_posts=3, max_posts=6)

        # 2. Like a couple of posts
        from linkedin.interact import _fast_click_like
        for _ in range(random.randint(1, 3)):
            human_scroll(page, "down", random.randint(200, 400))
            wait_for_stable(page, timeout=3000)
            liked = _fast_click_like(page)
            if liked:
                self.state["total_likes"] += 1
            random_delay(2.0, 5.0)

        # 3. View own profile
        _view_own_profile(page)
        self.state["total_profile_views"] += 1

        # 4. Maybe check notifications
        if random.random() < 0.5:
            navigate_to_notifications(page)
            random_delay(3.0, 6.0)

    def _day_2_session(self, page):
        """Day 2: Moderate activity. Building engagement.

        Activities:
        - Browse feed (8-12 posts)
        - View 5-10 profiles in own network
        - Like 3-5 posts
        - Check notifications
        """
        print("[Warmup] Day 2: Moderate engagement session")

        # 1. Browse the feed more actively
        navigate_to_feed(page)
        _organic_feed_browse(page, min_posts=4, max_posts=8)

        # 2. Like more posts
        from linkedin.interact import _fast_click_like
        for _ in range(random.randint(2, 4)):
            human_scroll(page, "down", random.randint(250, 450))
            wait_for_stable(page, timeout=3000)
            liked = _fast_click_like(page)
            if liked:
                self.state["total_likes"] += 1
            random_delay(2.0, 4.0)

        # 3. Go to My Network and view some profiles
        navigate_to_my_network(page)
        random_delay(2.0, 4.0)

        num_profiles = random.randint(3, 6)
        for _ in range(num_profiles):
            # Scroll to find profile suggestions
            human_scroll(page, "down", random.randint(200, 400))
            wait_for_stable(page, timeout=3000)
            random_delay(1.5, 3.0)
            self.state["total_profile_views"] += 1

        # 4. Check notifications
        navigate_to_notifications(page)
        random_delay(3.0, 6.0)

    def get_summary(self):
        """Get a human-readable summary of warm-up progress."""
        return {
            "phase": self.current_phase,
            "hours_remaining": round(self.hours_remaining, 1),
            "total_sessions": len(self.state["sessions"]),
            "total_likes": self.state["total_likes"],
            "total_profile_views": self.state["total_profile_views"],
            "completed": self.is_complete,
        }


def _view_own_profile(page):
    """Navigate to and view your own LinkedIn profile.

    Uses the direct /in/me/ URL which auto-redirects to the
    user's profile. ACT search for "Me" was matching "Messaging"
    due to partial matching, so we use the URL approach instead.
    """
    print("[Warmup] Viewing own profile...")

    page.goto("https://www.linkedin.com/in/me/", wait_until="domcontentloaded")
    wait_for_stable(page)
    random_delay(2.0, 4.0)

    # Scroll through own profile like checking it
    for _ in range(random.randint(2, 4)):
        human_scroll(page, "down", random.randint(200, 400))
        random_delay(1.5, 3.0)
