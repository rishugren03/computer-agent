import base64
import redis
import os

_redis_client = None

def broadcast_screen(page):
    global _redis_client
    try:
        if page and not page.is_closed():
            if _redis_client is None:
                _redis_client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
            screenshot_bytes = page.screenshot(type="jpeg", quality=40)
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            _redis_client.publish("live_view", b64)
    except Exception:
        pass
