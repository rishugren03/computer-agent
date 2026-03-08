from openai import OpenAI
from dotenv import load_dotenv
from google import genai
from PIL import Image
import os
import json
import time

load_dotenv()

# --- DeepSeek text LLM (for deciding page actions) ---

deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def decide_action(goal, elements):
    """Ask the text LLM what action to take given a goal and visible elements."""

    prompt = f"""
Goal: {goal}

Available elements:
{elements}

Choose an action.

Return JSON like this:

{{ "action":"type","id":0,"text":"OpenAI" }}

or

{{ "action":"click","id":1 }}
"""

    response = deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content

    return json.loads(content)


# --- Gemini Vision LLM (for analyzing screenshots / images) ---

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

VISION_MODEL = "gemini-2.0-flash"
MAX_VISION_RETRIES = 3


def analyze_image(image_path, prompt):
    """
    Send a screenshot + text prompt to Gemini Vision.
    Returns parsed JSON from the model response.
    Includes retry with exponential backoff for rate limits.
    """

    img = Image.open(image_path)

    for attempt in range(MAX_VISION_RETRIES):
        try:
            response = gemini_client.models.generate_content(
                model=VISION_MODEL,
                contents=[prompt, img],
                config={
                    "response_mime_type": "application/json",
                },
            )

            text = response.text.strip()

            # Try to parse JSON from the response
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                return json.loads(text)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                wait_time = (2 ** attempt) * 15  # 15s, 30s, 60s
                print(f"[Vision LLM] Rate limited (attempt {attempt + 1}/{MAX_VISION_RETRIES}), waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise

    raise Exception(f"Vision LLM failed after {MAX_VISION_RETRIES} retries due to rate limiting")