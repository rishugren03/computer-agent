"""Centralized configuration for GhostAgent.

All hard-coded anti-ban limits live here. These CANNOT be overridden
by user config — they are safety guardrails to prevent LinkedIn jail.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Anti-Ban Guardrails (HARD LIMITS — NOT CONFIGURABLE) ───────────────────

MAX_CONNECTIONS_PER_DAY = 25       # Stay under LinkedIn's ~35 threshold
MAX_PROFILE_VIEWS_PER_DAY = 80     # Recruiter-level search without scraping flags
MAX_MESSAGES_PER_DAY = 50          # Outbound messages cap
MAX_LIKES_PER_DAY = 30             # Organic engagement ceiling
MAX_COMMENTS_PER_DAY = 15          # High-effort actions are suspicious at scale
MIN_TEMPLATE_VARIANTS = 10         # No two messages can ever be identical

# ─── Warmup ──────────────────────────────────────────────────────────────────

WARMUP_DURATION_HOURS = 48         # Ghost Mode: zero outreach for first 48 hours
WARMUP_STATE_FILE = "warmup_state.json"

# ─── Session Timing ─────────────────────────────────────────────────────────

INACTIVITY_HOURS = 8               # Agent sleeps during user's nighttime
ACTIVE_HOURS_START = 8             # 8 AM local time
ACTIVE_HOURS_END = 23              # 11 PM local time
SESSION_MIN_MINUTES = 15           # Minimum session duration
SESSION_MAX_MINUTES = 45           # Maximum session duration
BREAK_MIN_MINUTES = 2              # Micro-break minimum
BREAK_MAX_MINUTES = 5              # Micro-break maximum
BREAK_PROBABILITY = 0.15           # 15% chance of a micro-break after each action cycle

# ─── Human Behavior Tuning ──────────────────────────────────────────────────

READING_WPM_MIN = 180              # Minimum "reading speed" (words per minute)
READING_WPM_MAX = 280              # Maximum "reading speed"
SCROLL_SPEED_MIN = 200             # Minimum scroll pixels per action
SCROLL_SPEED_MAX = 500             # Maximum scroll pixels per action
DWELL_MIN_SECONDS = 2.0            # Minimum time spent on a section
DWELL_MAX_SECONDS = 8.0            # Maximum time spent on a section
DETOUR_PROBABILITY = 0.30          # 30% chance of "distraction" navigation

# ─── Mouse Simulation ───────────────────────────────────────────────────────

CLICK_DURATION_MIN_MS = 50         # Minimum click hold (micro-hesitation minimum)
CLICK_DURATION_MAX_MS = 150        # Maximum click hold (micro-hesitation maximum)
OVERSHOOT_PROBABILITY = 0.20       # 20% of clicks overshoot then correct
OVERSHOOT_MIN_PX = 5
OVERSHOOT_MAX_PX = 15
MICRO_JITTER_PX = 2                # Max jitter during mouse movement

# ─── Typing Simulation ──────────────────────────────────────────────────────

TYPING_WPM_MIN = 45                # Minimum typing speed
TYPING_WPM_MAX = 85                # Maximum typing speed
TYPO_PROBABILITY = 0.03            # 3% chance of a typo + backspace correction
WORD_PAUSE_MIN_MS = 100            # Extra pause between words
WORD_PAUSE_MAX_MS = 350
PUNCTUATION_PAUSE_MIN_MS = 200     # Extra pause after punctuation
PUNCTUATION_PAUSE_MAX_MS = 600

# ─── LLM Configuration ──────────────────────────────────────────────────────

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
GEMINI_FAST_MODEL = os.getenv("GEMINI_FAST_MODEL", "gemini-1.5-flash") # gemini-3.1-flash-lite placeholder
GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-1.5-pro")   # gemini-3.1-pro placeholder

# ─── Proxy Configuration ────────────────────────────────────────────────────

PROXY_HOST = os.getenv("PROXY_HOST", "")
PROXY_PORT = os.getenv("PROXY_PORT", "")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")

def get_proxy_url():
    """Build proxy URL from components. Returns None if not configured."""
    if not PROXY_HOST or not PROXY_PORT:
        return None
    if PROXY_USER and PROXY_PASS:
        return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    return f"http://{PROXY_HOST}:{PROXY_PORT}"

# ─── Geolocation Spoofing ───────────────────────────────────────────────────

USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
USER_LATITUDE = float(os.getenv("USER_LAT", "25.6"))
USER_LONGITUDE = float(os.getenv("USER_LON", "84.9"))
USER_LOCALE = os.getenv("USER_LOCALE", "en-US")

# ─── Browser Settings ───────────────────────────────────────────────────────

BROWSER_DATA_DIR = os.getenv("BROWSER_DATA_DIR", "ghost_browser_data")
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "/tmp/ghost_screenshots")
VIEWPORT_BASE_WIDTH = 1280
VIEWPORT_BASE_HEIGHT = 720
VIEWPORT_JITTER = 20              # ±px randomization per session

# ─── User Agent Pool (real Chrome on Linux UA strings) ───────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# ─── Data Persistence ───────────────────────────────────────────────────────

DATA_DIR = os.getenv("GHOST_DATA_DIR", "ghost_data")
GUARDRAILS_DB = os.path.join(DATA_DIR, "guardrails.db")
APPROVAL_QUEUE_FILE = os.path.join(DATA_DIR, "approval_queue.json")
SEMANTIC_CACHE_FILE = os.path.join(DATA_DIR, "semantic_cache.json")
PERSONA_FILE = os.path.join(DATA_DIR, "persona.json")
SENT_MESSAGES_FILE = os.path.join(DATA_DIR, "sent_messages.json")
