"""Template diversity engine for GhostAgent.

Ensures no two outgoing messages are ever identical by:
- Varying greetings, closings, and phrasing
- Tracking all sent messages for similarity checking
- Regenerating messages that are too similar to recent ones

This is critical for anti-detection — LinkedIn flags accounts
that send templated messages.
"""

import json
import os
import re
import random

from config import SENT_MESSAGES_FILE, DATA_DIR, MIN_TEMPLATE_VARIANTS


class DiversityEngine:
    """Ensures every outgoing message is unique."""

    def __init__(self, history_file=None):
        self.history_file = history_file or SENT_MESSAGES_FILE
        self.sent_history = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r") as f:
                    self.sent_history = json.load(f)
        except Exception:
            self.sent_history = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.history_file) or DATA_DIR, exist_ok=True)
            with open(self.history_file, "w") as f:
                # Keep last 200 messages
                json.dump(self.sent_history[-200:], f, indent=2)
        except Exception:
            pass

    def ensure_unique(self, text, max_similarity=0.70, regenerate_fn=None):
        """Check if a message is unique compared to recent messages.

        If too similar to any recent message, either regenerate
        or apply variations until unique.

        Args:
            text: The candidate message.
            max_similarity: Maximum allowed similarity (0-1).
            regenerate_fn: Optional function to regenerate the message.
                Signature: () -> str

        Returns:
            str: The final unique message.
        """
        best = text
        attempts = 0
        max_attempts = 5

        while attempts < max_attempts:
            # Check against recent messages
            max_sim = self._max_similarity(best)
            if max_sim < max_similarity:
                return best  # It's unique enough

            # Try to regenerate or vary
            if regenerate_fn and attempts < 3:
                best = regenerate_fn()
            else:
                best = self._apply_variations(best)

            attempts += 1

        return best  # Return best effort

    def record_sent(self, text):
        """Record a message that was sent."""
        self.sent_history.append(text)
        self._save()

    def _max_similarity(self, text):
        """Find maximum similarity against last 50 sent messages."""
        recent = self.sent_history[-50:]
        if not recent:
            return 0.0

        max_sim = 0.0
        for sent in recent:
            sim = self.similarity_score(text, sent)
            max_sim = max(max_sim, sim)

        return max_sim

    @staticmethod
    def similarity_score(a, b):
        """Calculate Jaccard similarity between two texts.

        Uses word-level comparison with normalization.

        Returns:
            float: 0-1 similarity score.
        """
        words_a = set(re.findall(r'\w+', a.lower()))
        words_b = set(re.findall(r'\w+', b.lower()))

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union)

    def _apply_variations(self, text):
        """Apply random textual variations to make a message more unique."""
        result = text

        # Vary greeting
        result = vary_greeting(result)

        # Vary closing
        result = vary_closing(result)

        # Vary connector words
        result = _vary_connectors(result)

        return result

    def get_stats(self):
        """Get diversity statistics."""
        return {
            "total_sent": len(self.sent_history),
            "recent_50_avg_similarity": self._avg_recent_similarity(),
        }

    def _avg_recent_similarity(self):
        """Calculate average pairwise similarity of last 20 messages."""
        recent = self.sent_history[-20:]
        if len(recent) < 2:
            return 0.0

        total_sim = 0
        comparisons = 0
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                total_sim += self.similarity_score(recent[i], recent[j])
                comparisons += 1

        return total_sim / comparisons if comparisons else 0.0


# ─── Variation Functions ─────────────────────────────────────────────────────

GREETINGS = [
    "Hi", "Hey", "Hello", "Hey there",
    "Hi there", "Good to see your profile",
]

CLOSINGS = [
    "Best", "Cheers", "Looking forward to connecting",
    "Talk soon", "Best regards", "Hope to connect",
    "", # No closing (also natural)
]

CONNECTORS = {
    "also": ["additionally", "moreover", "plus"],
    "but": ["however", "though", "that said"],
    "really": ["truly", "genuinely", "definitely"],
    "great": ["excellent", "fantastic", "impressive"],
    "interesting": ["fascinating", "compelling", "insightful"],
    "I think": ["I believe", "I feel", "In my view"],
    "a lot": ["extensively", "significantly", "quite a bit"],
}


def vary_greeting(text):
    """Swap the greeting with a random alternative."""
    for greeting in sorted(GREETINGS, key=len, reverse=True):
        if text.startswith(greeting):
            replacement = random.choice([g for g in GREETINGS if g != greeting])
            return replacement + text[len(greeting):]
    return text


def vary_closing(text):
    """Swap the closing with a random alternative."""
    lines = text.strip().split("\n")
    last_line = lines[-1].strip()

    for closing in sorted(CLOSINGS, key=len, reverse=True):
        if closing and last_line.startswith(closing):
            replacement = random.choice([c for c in CLOSINGS if c != closing and c])
            lines[-1] = last_line.replace(closing, replacement, 1)
            return "\n".join(lines)

    return text


def _vary_connectors(text):
    """Replace common connector words with synonyms."""
    result = text
    # Only replace 1-2 connectors to keep it natural
    replacements_made = 0
    for word, alternatives in CONNECTORS.items():
        if word in result.lower() and replacements_made < 2:
            # Case-preserving replacement
            alt = random.choice(alternatives)
            if word[0].isupper():
                alt = alt.capitalize()
            result = result.replace(word, alt, 1)
            replacements_made += 1

    return result
