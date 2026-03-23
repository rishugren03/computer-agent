"""GhostWriter — AI-powered message generation.

Generates hyper-personalized:
- Connection notes (referencing prospect's headline/posts)
- Comments on prospects' posts
- Inbox replies matching the user's persona
- Post content (future GhostWriter feature)

Uses DeepSeek for text generation with persona-aware prompts.
"""

import json
import time

from config import GEMINI_API_KEY, GEMINI_PRO_MODEL
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)

MAX_RETRIES = 3


def generate_connection_note(prospect_data, persona=None):
    """Generate a personalized LinkedIn connection note.

    Creates a genuine, non-spammy note referencing specific details
    from the prospect's profile.

    Args:
        prospect_data: Dict with name, headline, about, current_position, etc.
        persona: PersonaProfile for style matching. If None, uses default.

    Returns:
        str: Personalized connection note (max 300 chars for LinkedIn limit).
    """
    persona_desc = persona.to_prompt_description() if persona else "Professional, friendly tone."

    name = prospect_data.get("name", "")
    headline = prospect_data.get("headline", "")
    about = prospect_data.get("about", "")[:200]
    position = prospect_data.get("current_position", "")
    company = prospect_data.get("company", "")

    prompt = f"""Write a LinkedIn connection request note for {name}.

Their profile:
- Headline: {headline}
- Current role: {position} at {company}
- About: {about}

{persona_desc}

Rules:
1. Maximum 280 characters (LinkedIn limit is 300, leave buffer)
2. Reference something SPECIFIC about their profile
3. Be genuine — NOT salesy or pitch-like
4. No generic "I'd love to connect" without context
5. Sound like a real professional reaching out naturally
6. Don't mention being an AI
7. Match the writing style described above

Return ONLY the connection note text. No quotes, no explanation."""

    return _generate_text(prompt, max_tokens=150)


def generate_comment(post_content, persona=None, author_name=None, author_headline=None):
    """Generate a context-aware comment on a LinkedIn post.

    Creates a thoughtful, genuine comment that adds value
    to the conversation.

    Args:
        post_content: The text of the post to comment on.
        persona: PersonaProfile for style matching.
        author_name: Optional author name for personalized comments.
        author_headline: Optional author headline/role for contextual comments.

    Returns:
        str: Comment text.
    """
    persona_desc = persona.to_prompt_description() if persona else "Professional, friendly tone."

    # Build author context if available
    author_ctx = ""
    if author_name:
        author_ctx = f" by {author_name}"
        if author_headline:
            author_ctx += f" ({author_headline})"

    prompt = f"""Write a LinkedIn comment on this post{author_ctx}:

"{post_content[:500]}"

{persona_desc}

Rules:
1. 1-3 sentences max
2. Add genuine value — share a perspective, ask a thoughtful question, or relate a relevant experience
3. Don't just say "Great post!" or "Thanks for sharing!"
4. Sound natural and human
5. Match the writing style described above
6. Don't try to sell anything or pitch
7. If you know the author's name, you may reference them naturally (but don't force it)

Return ONLY the comment text. No quotes, no explanation."""

    return _generate_text(prompt, max_tokens=200)


def generate_reply(sender_name, message_text, intent, persona=None):
    """Generate a reply to an inbox message.

    Handles different intents differently:
    - "thanks": Reply with a personalized question to start conversation
    - "interested": Should NOT auto-reply (flagged for human)
    - "question": Provide helpful response (flagged for human review)

    Args:
        sender_name: Name of the sender.
        message_text: Their message.
        intent: Classification ("thanks", "interested", etc.)
        persona: PersonaProfile for style matching.

    Returns:
        str: Reply text (or empty string if shouldn't auto-reply).
    """
    if intent == "interested":
        return ""  # Don't auto-reply to leads

    persona_desc = persona.to_prompt_description() if persona else "Professional, friendly tone."

    if intent == "thanks":
        prompt = f"""Reply to this LinkedIn message from {sender_name}:

"{message_text}"

They're thanking you for connecting. Write a warm, personalized reply that:
1. Acknowledges the connection
2. Asks ONE specific, open-ended question to start a conversation
3. Is 2-3 sentences max
4. Doesn't try to sell or pitch anything
5. Sounds genuinely interested in them

{persona_desc}

Return ONLY the reply text. No quotes."""

    elif intent == "question":
        prompt = f"""Reply to this LinkedIn message from {sender_name}:

"{message_text}"

They asked a question. Write a brief, helpful reply:
1. Answer directly if possible
2. Be concise (2-4 sentences)
3. Offer to continue the conversation

{persona_desc}

Return ONLY the reply text. No quotes."""

    else:
        prompt = f"""Reply to this LinkedIn message from {sender_name}:

"{message_text}"

Write a brief, professional reply:
1. 1-2 sentences
2. Be friendly but not overly eager
3. Match the tone of their message

{persona_desc}

Return ONLY the reply text."""

    return _generate_text(prompt, max_tokens=200)


def generate_post(topic, persona=None):
    """Generate a LinkedIn post on a given topic.

    This is the "GhostWriter" feature for account authority building.

    Args:
        topic: What to write about.
        persona: PersonaProfile for style matching.

    Returns:
        str: LinkedIn post content.
    """
    persona_desc = persona.to_prompt_description() if persona else "Professional, thought-leadership tone."

    prompt = f"""Write a LinkedIn post about: {topic}

{persona_desc}

Rules:
1. 100-200 words (not too long for LinkedIn)
2. Start with a hook (controversial take, surprising stat, or personal story)
3. Use short paragraphs (2-3 sentences each)
4. End with a question or call-to-action to drive engagement
5. Include 2-4 relevant hashtags at the end
6. Sound authentic, NOT AI-generated
7. No corporate buzzword salad
8. Match the writing style described above

Return ONLY the post text."""

    return _generate_text(prompt, max_tokens=500)


def _generate_text(prompt, max_tokens=200):
    """Generate text using DeepSeek with retry logic.

    Returns:
        str: Generated text, or empty string on failure.
    """
    for attempt in range(MAX_RETRIES):
        try:
            prompt_content = f"You are a writing assistant that generates natural, human-sounding LinkedIn messages. Always match the specified writing style exactly.\n\n{prompt}"
            response = client.models.generate_content(
                model=GEMINI_PRO_MODEL,
                contents=prompt_content,
            )

            text = response.text.strip()

            # Clean up: remove surrounding quotes if present
            if (text.startswith('"') and text.endswith('"')) or \
               (text.startswith("'") and text.endswith("'")):
                text = text[1:-1]

            return text

        except Exception as e:
            print(f"[GhostWriter] Error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** (attempt + 1))

    return ""
