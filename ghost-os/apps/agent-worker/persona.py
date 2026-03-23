"""Persona cloning engine.

Analyzes the user's past LinkedIn posts and messages to clone
their writing style. This ensures AI-generated content matches
the user's natural voice.

Extracts:
- Tone (professional, casual, friendly)
- Emoji usage frequency
- Average sentence length
- Common phrases and filler words
- Punctuation style (oxford comma, exclamation marks, etc.)
"""

import json
import os
import re
from collections import Counter

from config import PERSONA_FILE, DATA_DIR


class PersonaProfile:
    """Represents a cloned writing style."""

    def __init__(self):
        self.tone = "professional"       # professional | casual | friendly
        self.emoji_frequency = 0.0       # 0.0 to 1.0 (per sentence)
        self.avg_sentence_length = 15    # Words per sentence
        self.avg_message_length = 50     # Words per message
        self.common_phrases = []         # ["looking forward", "happy to", ...]
        self.common_emojis = []          # ["🚀", "💡", "👋"]
        self.greeting_style = "Hi"       # "Hi" | "Hey" | "Hello" | name-only
        self.closing_style = "Best"      # "Best" | "Cheers" | "Thanks" | none
        self.uses_exclamation = True     # Frequent ! usage
        self.uses_questions = True       # Ends with questions for engagement
        self.uses_line_breaks = True     # Uses line breaks between thoughts
        self.formality_score = 0.7       # 0=very casual, 1=very formal

    def to_dict(self):
        return self.__dict__.copy()

    def from_dict(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def to_prompt_description(self):
        """Generate a prompt description of this persona's writing style."""
        desc = f"""Writing Style Profile:
- Tone: {self.tone}
- Formality: {'very formal' if self.formality_score > 0.8 else 'formal' if self.formality_score > 0.5 else 'casual'}
- Greeting style: "{self.greeting_style}"
- Closing style: "{self.closing_style}"
- Average sentence length: {self.avg_sentence_length} words
- Uses emojis: {'frequently' if self.emoji_frequency > 0.3 else 'occasionally' if self.emoji_frequency > 0.1 else 'rarely'}
- Common emojis: {', '.join(self.common_emojis[:5]) if self.common_emojis else 'none'}
- Uses exclamation marks: {'yes' if self.uses_exclamation else 'no'}
- Ends with questions: {'yes' if self.uses_questions else 'no'}
- Uses line breaks between thoughts: {'yes' if self.uses_line_breaks else 'no'}
- Common phrases: {', '.join(f'"{p}"' for p in self.common_phrases[:5])}"""
        return desc


def clone_persona(texts):
    """Analyze a list of writing samples to extract a persona.

    Feed this the user's last 20 LinkedIn posts and messages.

    Args:
        texts: List of text samples (posts, messages, comments).

    Returns:
        PersonaProfile: The cloned writing style.
    """
    persona = PersonaProfile()

    if not texts:
        return persona

    all_text = " ".join(texts)
    all_sentences = _split_sentences(all_text)

    # Analyze sentence length
    sentence_lengths = [len(s.split()) for s in all_sentences if len(s.split()) > 2]
    if sentence_lengths:
        persona.avg_sentence_length = sum(sentence_lengths) // len(sentence_lengths)

    # Analyze message length
    msg_lengths = [len(t.split()) for t in texts]
    if msg_lengths:
        persona.avg_message_length = sum(msg_lengths) // len(msg_lengths)

    # Emoji analysis
    emoji_count = sum(_count_emojis(t) for t in texts)
    total_sentences = max(len(all_sentences), 1)
    persona.emoji_frequency = min(emoji_count / total_sentences, 1.0)
    persona.common_emojis = _find_common_emojis(all_text)

    # Tone analysis
    persona.tone = _analyze_tone(texts)
    persona.formality_score = _analyze_formality(texts)

    # Greeting/closing analysis
    persona.greeting_style = _analyze_greetings(texts)
    persona.closing_style = _analyze_closings(texts)

    # Punctuation habits
    exclamation_count = all_text.count("!")
    question_count = all_text.count("?")
    persona.uses_exclamation = exclamation_count > len(texts) * 0.3
    persona.uses_questions = question_count > len(texts) * 0.2

    # Line break usage
    line_break_count = sum(t.count("\n") for t in texts)
    persona.uses_line_breaks = line_break_count > len(texts) * 0.5

    # Common phrases
    persona.common_phrases = _find_common_phrases(texts)

    return persona


def save_persona(persona, path=None):
    """Save a persona to disk."""
    path = path or PERSONA_FILE
    os.makedirs(os.path.dirname(path) or DATA_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(persona.to_dict(), f, indent=2)


def load_persona(path=None):
    """Load a persona from disk."""
    path = path or PERSONA_FILE
    if not os.path.exists(path):
        return PersonaProfile()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return PersonaProfile().from_dict(data)
    except Exception:
        return PersonaProfile()


def apply_persona(text, persona):
    """Transform AI-generated text to match a persona's style.

    Adjusts:
    - Greeting style
    - Emoji usage
    - Sentence length
    - Exclamation marks
    - Line breaks

    Args:
        text: Raw AI-generated text.
        persona: PersonaProfile to match.

    Returns:
        str: Text adjusted to match persona style.
    """
    result = text

    # Adjust greeting
    greetings = ["Hi", "Hey", "Hello", "Dear"]
    for g in greetings:
        if result.startswith(g):
            result = result.replace(g, persona.greeting_style, 1)
            break

    # Add/remove emojis based on persona
    if persona.emoji_frequency < 0.05:
        # Remove emojis
        result = _remove_emojis(result)
    elif persona.emoji_frequency > 0.3 and persona.common_emojis:
        # Maybe add an emoji at the end
        if not _has_emoji(result) and persona.common_emojis:
            result = result.rstrip() + " " + persona.common_emojis[0]

    # Adjust exclamation usage
    if not persona.uses_exclamation:
        result = result.replace("!", ".")
    elif persona.uses_exclamation and result.count("!") == 0:
        # Add one exclamation if the persona uses them
        if result.endswith("."):
            result = result[:-1] + "!"

    return result


# ─── Analysis Helpers ────────────────────────────────────────────────────────

def _split_sentences(text):
    """Split text into sentences."""
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _count_emojis(text):
    """Count emoji characters in text."""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff]+",
        flags=re.UNICODE
    )
    return len(emoji_pattern.findall(text))


def _find_common_emojis(text, top_n=5):
    """Find the most commonly used emojis."""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff]",
        flags=re.UNICODE
    )
    emojis = emoji_pattern.findall(text)
    if not emojis:
        return []
    counter = Counter(emojis)
    return [emoji for emoji, _ in counter.most_common(top_n)]


def _has_emoji(text):
    return _count_emojis(text) > 0


def _remove_emojis(text):
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()


def _analyze_tone(texts):
    """Determine overall tone from writing samples."""
    casual_markers = 0
    formal_markers = 0

    for text in texts:
        lower = text.lower()
        # Casual markers
        if any(w in lower for w in ["hey", "lol", "btw", "gonna", "wanna", "haha"]):
            casual_markers += 1
        if _count_emojis(text) > 0:
            casual_markers += 0.5

        # Formal markers
        if any(w in lower for w in ["regarding", "furthermore", "consequently", "i would like"]):
            formal_markers += 1
        if text.count("!") == 0:
            formal_markers += 0.3

    if casual_markers > formal_markers * 1.5:
        return "casual"
    elif formal_markers > casual_markers * 1.5:
        return "professional"
    else:
        return "friendly"


def _analyze_formality(texts):
    """Return a 0-1 formality score."""
    scores = []
    for text in texts:
        lower = text.lower()
        score = 0.5
        if any(w in lower for w in ["dear", "sincerely", "regarding", "please find"]):
            score += 0.2
        if any(w in lower for w in ["hey", "lol", "gonna", "wanna"]):
            score -= 0.2
        if _count_emojis(text) > 2:
            score -= 0.1
        scores.append(max(0, min(1, score)))
    return sum(scores) / len(scores) if scores else 0.5


def _analyze_greetings(texts):
    """Determine preferred greeting style."""
    greetings = Counter()
    for text in texts:
        first_word = text.strip().split()[0] if text.strip() else ""
        if first_word in ("Hi", "Hey", "Hello", "Dear"):
            greetings[first_word] += 1
    if greetings:
        return greetings.most_common(1)[0][0]
    return "Hi"


def _analyze_closings(texts):
    """Determine preferred closing style."""
    closings = Counter()
    closing_words = ["Best", "Cheers", "Thanks", "Regards", "Talk soon"]
    for text in texts:
        last_line = text.strip().split("\n")[-1].strip()
        for closing in closing_words:
            if last_line.startswith(closing):
                closings[closing] += 1
    if closings:
        return closings.most_common(1)[0][0]
    return "Best"


def _find_common_phrases(texts, top_n=10):
    """Find frequently used 2-3 word phrases."""
    phrase_counter = Counter()

    for text in texts:
        words = text.lower().split()
        # Bigrams
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if len(phrase) > 5:  # Skip tiny phrases
                phrase_counter[phrase] += 1
        # Trigrams
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            if len(phrase) > 8:
                phrase_counter[phrase] += 1

    # Filter out generic phrases
    generic = {"in the", "of the", "to the", "and the", "it is", "i am", "on the"}
    filtered = [(p, c) for p, c in phrase_counter.items() if p not in generic and c > 1]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return [p for p, _ in filtered[:top_n]]
