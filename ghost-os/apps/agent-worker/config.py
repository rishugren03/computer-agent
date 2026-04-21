"""Centralized configuration for GhostAgent.

Hard-coded anti-ban limits CANNOT be overridden by user config.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Anti-Ban Guardrails (HARD LIMITS — NOT CONFIGURABLE) ───────────────────

MAX_CONNECTIONS_PER_DAY = 25
MAX_PROFILE_VIEWS_PER_DAY = 80
MAX_MESSAGES_PER_DAY = 50
MAX_LIKES_PER_DAY = 30
MAX_COMMENTS_PER_DAY = 15
MIN_TEMPLATE_VARIANTS = 10

# ─── Warmup ──────────────────────────────────────────────────────────────────

WARMUP_DURATION_HOURS = 48
WARMUP_STATE_FILE = "warmup_state.json"

# ─── Session Timing ──────────────────────────────────────────────────────────

INACTIVITY_HOURS = 8
ACTIVE_HOURS_START = 8
ACTIVE_HOURS_END = 23
SESSION_MIN_MINUTES = 15
SESSION_MAX_MINUTES = 45
BREAK_MIN_MINUTES = 2
BREAK_MAX_MINUTES = 5
BREAK_PROBABILITY = 0.15

# ─── Human Behavior ──────────────────────────────────────────────────────────

READING_WPM_MIN = 180
READING_WPM_MAX = 280
SCROLL_SPEED_MIN = 200
SCROLL_SPEED_MAX = 500
DWELL_MIN_SECONDS = 2.0
DWELL_MAX_SECONDS = 8.0
DETOUR_PROBABILITY = 0.30

# ─── Mouse Simulation ────────────────────────────────────────────────────────

CLICK_DURATION_MIN_MS = 50
CLICK_DURATION_MAX_MS = 150
OVERSHOOT_PROBABILITY = 0.20
OVERSHOOT_MIN_PX = 5
OVERSHOOT_MAX_PX = 15
MICRO_JITTER_PX = 2

# ─── Typing Simulation ───────────────────────────────────────────────────────

TYPING_WPM_MIN = 45
TYPING_WPM_MAX = 85
TYPO_PROBABILITY = 0.03
WORD_PAUSE_MIN_MS = 100
WORD_PAUSE_MAX_MS = 350
PUNCTUATION_PAUSE_MIN_MS = 200
PUNCTUATION_PAUSE_MAX_MS = 600

# ─── LLM Configuration ───────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")   # gpt-5.4-mini when available

# ─── Proxy ───────────────────────────────────────────────────────────────────

PROXY_HOST = os.getenv("PROXY_HOST", "")
PROXY_PORT = os.getenv("PROXY_PORT", "")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")

def get_proxy_url():
    if not PROXY_HOST or not PROXY_PORT:
        return None
    if PROXY_USER and PROXY_PASS:
        return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    return f"http://{PROXY_HOST}:{PROXY_PORT}"

# ─── Geolocation ─────────────────────────────────────────────────────────────

USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
USER_LATITUDE = float(os.getenv("USER_LAT", "25.6"))
USER_LONGITUDE = float(os.getenv("USER_LON", "84.9"))
USER_LOCALE = os.getenv("USER_LOCALE", "en-US")

# ─── Browser ─────────────────────────────────────────────────────────────────

BROWSER_DATA_DIR = os.getenv("BROWSER_DATA_DIR", "ghost_browser_data")
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "/tmp/ghost_screenshots")
VIEWPORT_BASE_WIDTH = 1280
VIEWPORT_BASE_HEIGHT = 720
VIEWPORT_JITTER = 20

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# ─── Data Persistence ────────────────────────────────────────────────────────

DATA_DIR = os.getenv("GHOST_DATA_DIR", "ghost_data")
GUARDRAILS_DB = os.path.join(DATA_DIR, "guardrails.db")
APPROVAL_QUEUE_FILE = os.path.join(DATA_DIR, "approval_queue.json")
SEMANTIC_CACHE_FILE = os.path.join(DATA_DIR, "semantic_cache.json")
PERSONA_FILE = os.path.join(DATA_DIR, "persona.json")
SENT_MESSAGES_FILE = os.path.join(DATA_DIR, "sent_messages.json")
