"""Anti-ban guardrails for GhostAgent.

These are HARD-CODED safety limits that CANNOT be overridden by user config.
They prevent LinkedIn from flagging the account as automated.

All limits are tracked in SQLite for reliable cross-session persistence.
"""

import sqlite3
import os
import time
from datetime import datetime, timezone

from config import (
    GUARDRAILS_DB,
    DATA_DIR,
    MAX_CONNECTIONS_PER_DAY,
    MAX_PROFILE_VIEWS_PER_DAY,
    MAX_MESSAGES_PER_DAY,
    MAX_LIKES_PER_DAY,
    MAX_COMMENTS_PER_DAY,
)


class Guardrails:
    """Rate limiter that prevents exceeding LinkedIn's detection thresholds.

    All checks are mandatory. The agent MUST call can_* methods
    before performing any action.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or GUARDRAILS_DB
        os.makedirs(os.path.dirname(self.db_path) or DATA_DIR, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database for action tracking."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                date_key TEXT NOT NULL,
                metadata TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_actions_date 
            ON actions(date_key, action_type)
        """)
        conn.commit()
        conn.close()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _today_key(self):
        """Get today's date key in YYYY-MM-DD format (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _get_daily_count(self, action_type):
        """Get today's count for an action type."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT COUNT(*) FROM actions WHERE date_key = ? AND action_type = ?",
            (self._today_key(), action_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ─── Permission Checks ───────────────────────────────────────────────

    def can_connect(self):
        """Check if a connection request can be sent.

        Returns:
            bool: True if under the daily limit of {MAX_CONNECTIONS_PER_DAY}.
        """
        count = self._get_daily_count("connection")
        allowed = count < MAX_CONNECTIONS_PER_DAY
        if not allowed:
            print(f"[Guardrails] ⛔ Connection limit reached ({count}/{MAX_CONNECTIONS_PER_DAY})")
        return allowed

    def can_view_profile(self):
        """Check if a profile view is allowed.

        Returns:
            bool: True if under the daily limit of {MAX_PROFILE_VIEWS_PER_DAY}.
        """
        count = self._get_daily_count("profile_view")
        allowed = count < MAX_PROFILE_VIEWS_PER_DAY
        if not allowed:
            print(f"[Guardrails] ⛔ Profile view limit reached ({count}/{MAX_PROFILE_VIEWS_PER_DAY})")
        return allowed

    def can_message(self):
        """Check if a message can be sent.

        Returns:
            bool: True if under the daily limit of {MAX_MESSAGES_PER_DAY}.
        """
        count = self._get_daily_count("message")
        allowed = count < MAX_MESSAGES_PER_DAY
        if not allowed:
            print(f"[Guardrails] ⛔ Message limit reached ({count}/{MAX_MESSAGES_PER_DAY})")
        return allowed

    def can_like(self):
        """Check if a like action is allowed."""
        count = self._get_daily_count("like")
        return count < MAX_LIKES_PER_DAY

    def can_comment(self):
        """Check if a comment can be posted."""
        count = self._get_daily_count("comment")
        return count < MAX_COMMENTS_PER_DAY

    # ─── Action Recording ────────────────────────────────────────────────

    def record_action(self, action_type, metadata=""):
        """Record that an action was performed.

        Args:
            action_type: One of: connection, profile_view, message, like, comment
            metadata: Optional extra info (e.g., prospect name)
        """
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO actions (action_type, timestamp, date_key, metadata) VALUES (?, ?, ?, ?)",
            (action_type, time.time(), self._today_key(), metadata)
        )
        conn.commit()
        conn.close()

    # ─── Stats ───────────────────────────────────────────────────────────

    def get_daily_stats(self):
        """Get today's action counts for all types.

        Returns:
            dict: Counts and limits for each action type.
        """
        return {
            "connections": {
                "used": self._get_daily_count("connection"),
                "limit": MAX_CONNECTIONS_PER_DAY,
            },
            "profile_views": {
                "used": self._get_daily_count("profile_view"),
                "limit": MAX_PROFILE_VIEWS_PER_DAY,
            },
            "messages": {
                "used": self._get_daily_count("message"),
                "limit": MAX_MESSAGES_PER_DAY,
            },
            "likes": {
                "used": self._get_daily_count("like"),
                "limit": MAX_LIKES_PER_DAY,
            },
            "comments": {
                "used": self._get_daily_count("comment"),
                "limit": MAX_COMMENTS_PER_DAY,
            },
            "date": self._today_key(),
        }

    def get_weekly_stats(self):
        """Get action counts for the past 7 days."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT date_key, action_type, COUNT(*) 
            FROM actions 
            WHERE timestamp > ?
            GROUP BY date_key, action_type
            ORDER BY date_key DESC
        """, (time.time() - 7 * 86400,))

        rows = cursor.fetchall()
        conn.close()

        stats = {}
        for date_key, action_type, count in rows:
            if date_key not in stats:
                stats[date_key] = {}
            stats[date_key][action_type] = count

        return stats

    def print_daily_stats(self):
        """Print a formatted daily stats summary."""
        stats = self.get_daily_stats()
        print("\n📊 Daily Usage:")
        print(f"  Connections:   {stats['connections']['used']}/{stats['connections']['limit']}")
        print(f"  Profile Views: {stats['profile_views']['used']}/{stats['profile_views']['limit']}")
        print(f"  Messages:      {stats['messages']['used']}/{stats['messages']['limit']}")
        print(f"  Likes:         {stats['likes']['used']}/{stats['likes']['limit']}")
        print(f"  Comments:      {stats['comments']['used']}/{stats['comments']['limit']}")
