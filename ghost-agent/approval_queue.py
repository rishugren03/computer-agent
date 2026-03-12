"""Tinder-style approval queue for connection requests.

Every morning, the user reviews AI-generated connection notes.
They "approve" (accept as-is), "edit" (modify), or "reject" (skip).

Once the AI achieves 90%+ approval rate, it enters Auto-Pilot mode
where approved messages are sent without human review.
"""

import json
import os
import time

from config import APPROVAL_QUEUE_FILE, DATA_DIR


class ApprovalQueue:
    """Manages pending connection notes for user review."""

    def __init__(self, queue_file=None):
        self.queue_file = queue_file or APPROVAL_QUEUE_FILE
        self.pending = []          # Items awaiting review
        self.approved = []         # Approved and ready to send
        self.rejected = []         # Rejected items (for learning)
        self.history = []          # All past decisions for approval rate
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, "r") as f:
                    data = json.load(f)
                    self.pending = data.get("pending", [])
                    self.approved = data.get("approved", [])
                    self.rejected = data.get("rejected", [])
                    self.history = data.get("history", [])
        except Exception as e:
            print(f"[Queue] Load error: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.queue_file) or DATA_DIR, exist_ok=True)
            with open(self.queue_file, "w") as f:
                json.dump({
                    "pending": self.pending,
                    "approved": self.approved,
                    "rejected": self.rejected,
                    "history": self.history[-200:],  # Keep last 200 decisions
                }, f, indent=2)
        except Exception as e:
            print(f"[Queue] Save error: {e}")

    def add(self, prospect_data, note):
        """Add a new connection note to the queue for review.

        Args:
            prospect_data: Dict with name, headline, etc.
            note: AI-generated connection note.
        """
        item = {
            "id": int(time.time() * 1000),
            "prospect": prospect_data,
            "note": note,
            "created_at": time.time(),
            "status": "pending",
        }
        self.pending.append(item)
        self._save()

    def get_pending(self, limit=15):
        """Get pending items for review (morning batch).

        Returns:
            list: Up to `limit` pending items.
        """
        return self.pending[:limit]

    def approve(self, item_id):
        """Approve a connection note as-is."""
        item = self._find_and_remove_pending(item_id)
        if item:
            item["status"] = "approved"
            item["approved_at"] = time.time()
            self.approved.append(item)
            self.history.append({"id": item_id, "decision": "approved", "time": time.time()})
            self._save()
            return True
        return False

    def reject(self, item_id):
        """Reject a connection note."""
        item = self._find_and_remove_pending(item_id)
        if item:
            item["status"] = "rejected"
            item["rejected_at"] = time.time()
            self.rejected.append(item)
            self.history.append({"id": item_id, "decision": "rejected", "time": time.time()})
            self._save()
            return True
        return False

    def edit(self, item_id, new_note):
        """Edit a connection note and approve it."""
        item = self._find_and_remove_pending(item_id)
        if item:
            item["original_note"] = item["note"]
            item["note"] = new_note
            item["status"] = "edited"
            item["approved_at"] = time.time()
            self.approved.append(item)
            self.history.append({"id": item_id, "decision": "edited", "time": time.time()})
            self._save()
            return True
        return False

    def get_approved(self):
        """Get all approved items ready to send."""
        return self.approved.copy()

    def mark_sent(self, item_id):
        """Mark an approved item as sent (remove from approved queue)."""
        self.approved = [i for i in self.approved if i["id"] != item_id]
        self._save()

    @property
    def approval_rate(self):
        """Calculate the current approval rate.

        Returns:
            float: 0-100 percentage of approved/edited vs rejected.
        """
        if not self.history:
            return 0.0

        recent = self.history[-50:]  # Based on last 50 decisions
        approved_count = sum(
            1 for h in recent
            if h["decision"] in ("approved", "edited")
        )
        return (approved_count / len(recent)) * 100

    @property
    def auto_pilot_eligible(self):
        """Check if the AI has earned enough trust for auto-pilot.

        Requires:
        - At least 20 decisions in history
        - 90%+ approval rate
        """
        return len(self.history) >= 20 and self.approval_rate >= 90.0

    def get_stats(self):
        """Get queue statistics."""
        return {
            "pending": len(self.pending),
            "approved_unsent": len(self.approved),
            "rejected_total": len(self.rejected),
            "approval_rate": round(self.approval_rate, 1),
            "auto_pilot_eligible": self.auto_pilot_eligible,
            "total_decisions": len(self.history),
        }

    def _find_and_remove_pending(self, item_id):
        """Find an item by ID and remove it from pending."""
        for i, item in enumerate(self.pending):
            if item["id"] == item_id:
                return self.pending.pop(i)
        return None
