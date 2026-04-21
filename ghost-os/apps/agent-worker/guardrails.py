"""Anti-ban guardrails backed by Postgres (atomic, race-condition-free).

Hard-coded safety limits that CANNOT be overridden by user config.
Uses SELECT FOR UPDATE so two concurrent workers cannot both pass the same limit.
"""

from datetime import datetime, timezone
import db
from config import (
    MAX_CONNECTIONS_PER_DAY,
    MAX_PROFILE_VIEWS_PER_DAY,
    MAX_MESSAGES_PER_DAY,
    MAX_LIKES_PER_DAY,
    MAX_COMMENTS_PER_DAY,
)


class Guardrails:
    def __init__(self, account_id: str):
        self.account_id = account_id

    def _check(self, column: str, limit: int, label: str) -> bool:
        allowed = db.guardrail_check_and_increment(self.account_id, column, limit)
        if not allowed:
            counts = db.get_guardrail_counts(self.account_id)
            current = counts.get(column.replace("Count", "s").lower(), "?")
            print(f"[Guardrails] ⛔ {label} limit reached ({current}/{limit})")
        return allowed

    def can_connect(self) -> bool:
        return self._check("connectionsCount", MAX_CONNECTIONS_PER_DAY, "Connection")

    def can_view_profile(self) -> bool:
        return self._check("profileViewsCount", MAX_PROFILE_VIEWS_PER_DAY, "Profile view")

    def can_message(self) -> bool:
        return self._check("messagesCount", MAX_MESSAGES_PER_DAY, "Message")

    def can_like(self) -> bool:
        return self._check("likesCount", MAX_LIKES_PER_DAY, "Like")

    def can_comment(self) -> bool:
        return self._check("commentsCount", MAX_COMMENTS_PER_DAY, "Comment")

    def get_daily_stats(self) -> dict:
        counts = db.get_guardrail_counts(self.account_id)
        return {
            "connections": {"used": counts.get("connections", 0), "limit": MAX_CONNECTIONS_PER_DAY},
            "profile_views": {"used": counts.get("profileViews", 0), "limit": MAX_PROFILE_VIEWS_PER_DAY},
            "messages": {"used": counts.get("messages", 0), "limit": MAX_MESSAGES_PER_DAY},
            "likes": {"used": counts.get("likes", 0), "limit": MAX_LIKES_PER_DAY},
            "comments": {"used": counts.get("comments", 0), "limit": MAX_COMMENTS_PER_DAY},
            "date": counts.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        }

    def print_daily_stats(self):
        stats = self.get_daily_stats()
        print("\n📊 Daily Usage:")
        print(f"  Connections:   {stats['connections']['used']}/{stats['connections']['limit']}")
        print(f"  Profile Views: {stats['profile_views']['used']}/{stats['profile_views']['limit']}")
        print(f"  Messages:      {stats['messages']['used']}/{stats['messages']['limit']}")
        print(f"  Likes:         {stats['likes']['used']}/{stats['likes']['limit']}")
        print(f"  Comments:      {stats['comments']['used']}/{stats['comments']['limit']}")

    # Legacy compatibility shims — agent code calls record_action() in some paths
    def record_action(self, action_type: str, metadata: str = ""):
        pass  # Now handled atomically in can_* methods
