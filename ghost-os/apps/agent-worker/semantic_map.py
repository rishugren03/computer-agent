"""Semantic Map — The persistent memory of GhostAgent.

Maps semantic labels (like "connect_button", "search_input") to ACT nodes
so the agent can find elements instantly on repeat visits. If a cached
mapping fails, triggers vision-based rediscovery (self-heal).

This is Layer 2 + Layer 3 of the Zero-Shot Brain:
- Layer 2 (Memory): Store discovered element → ACT node mappings
- Layer 3 (Speed): Cache lookups for instant element finding
"""

import json
import os
import time

from config import SEMANTIC_CACHE_FILE, DATA_DIR


class SemanticMap:
    """Persistent semantic element cache with self-healing.

    Usage:
        smap = SemanticMap()

        # Try cache first
        node = smap.lookup("connect_button")
        if node:
            # Use cached element
            click(node)
        else:
            # Vision-based discovery, then cache it
            node = discover_via_vision(...)
            smap.store("connect_button", node)
    """

    def __init__(self, cache_file=None):
        self.cache_file = cache_file or SEMANTIC_CACHE_FILE
        self.cache = {}
        self._hit_count = {}      # Track cache hits per label
        self._miss_count = {}     # Track cache misses per label
        self._last_updated = {}   # Timestamps for staleness detection
        self._load()

    def _load(self):
        """Load the semantic cache from disk."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    self.cache = data.get("mappings", {})
                    self._hit_count = data.get("hits", {})
                    self._miss_count = data.get("misses", {})
                    self._last_updated = data.get("updated", {})
                print(f"[SemanticMap] Loaded {len(self.cache)} cached mappings")
        except Exception as e:
            print(f"[SemanticMap] Failed to load cache: {e}")
            self.cache = {}

    def save(self):
        """Persist the semantic cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_file) or DATA_DIR, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump({
                    "mappings": self.cache,
                    "hits": self._hit_count,
                    "misses": self._miss_count,
                    "updated": self._last_updated,
                }, f, indent=2)
        except Exception as e:
            print(f"[SemanticMap] Failed to save cache: {e}")

    def lookup(self, label):
        """Look up a cached semantic mapping.

        Args:
            label: Semantic label (e.g., "connect_button", "search_input").

        Returns:
            dict | None: Cached ACT node data, or None if not found.
        """
        if label in self.cache:
            self._hit_count[label] = self._hit_count.get(label, 0) + 1
            return self.cache[label]

        self._miss_count[label] = self._miss_count.get(label, 0) + 1
        return None

    def store(self, label, node_data):
        """Store a semantic mapping.

        Args:
            label: Semantic label.
            node_data: ACT node data dict (role, name, description, etc.)
        """
        self.cache[label] = node_data
        self._last_updated[label] = time.time()
        self.save()

    def invalidate(self, label):
        """Mark a mapping as stale (triggers rediscovery next lookup)."""
        if label in self.cache:
            del self.cache[label]
            self._miss_count[label] = self._miss_count.get(label, 0) + 1
            self.save()

    def invalidate_all(self):
        """Clear the entire cache (e.g., after a major UI change)."""
        self.cache.clear()
        self.save()

    def get_stats(self):
        """Get cache performance statistics."""
        total_hits = sum(self._hit_count.values())
        total_misses = sum(self._miss_count.values())
        total = total_hits + total_misses

        return {
            "total_mappings": len(self.cache),
            "total_lookups": total,
            "hit_rate": (total_hits / total * 100) if total > 0 else 0,
            "hits": total_hits,
            "misses": total_misses,
            "stale_entries": self._count_stale(),
        }

    def _count_stale(self, max_age_hours=24):
        """Count entries older than max_age_hours."""
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        return sum(
            1 for ts in self._last_updated.values()
            if ts < cutoff
        )

    def cleanup_stale(self, max_age_hours=48):
        """Remove entries older than max_age_hours."""
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        stale_labels = [
            label for label, ts in self._last_updated.items()
            if ts < cutoff
        ]
        for label in stale_labels:
            self.invalidate(label)
        if stale_labels:
            print(f"[SemanticMap] Cleaned {len(stale_labels)} stale entries")

    # ─── LinkedIn-Specific Semantic Labels ───────────────────────────────

    # Standard labels for common LinkedIn UI elements
    LABELS = {
        # Navigation
        "nav_home": "Home navigation button",
        "nav_network": "My Network navigation button",
        "nav_jobs": "Jobs navigation button",
        "nav_messaging": "Messaging navigation button",
        "nav_notifications": "Notifications navigation button",
        "nav_me": "Me profile dropdown",

        # Search
        "search_input": "Main search input",
        "search_button": "Search submit button",
        "search_tab_people": "People tab in search results",
        "search_tab_posts": "Posts tab in search results",

        # Profile
        "profile_connect": "Connect button on profile",
        "profile_follow": "Follow button on profile",
        "profile_message": "Message button on profile",
        "profile_more": "More actions dropdown on profile",
        "profile_pending": "Pending connection indicator",

        # Connection Modal
        "connect_add_note": "Add a note button in connect modal",
        "connect_note_input": "Connection note text area",
        "connect_send": "Send connection request button",
        "connect_cancel": "Cancel connection modal button",

        # Feed
        "feed_post_input": "Start a post input",
        "feed_like_button": "Like button on a post",
        "feed_comment_button": "Comment button on a post",
        "feed_comment_input": "Comment text input",
        "feed_comment_submit": "Post comment button",

        # Messaging
        "msg_compose": "Start a new message button",
        "msg_input": "Message text input",
        "msg_send": "Send message button",
    }
