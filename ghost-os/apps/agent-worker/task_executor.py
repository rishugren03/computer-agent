"""Free-form task executor — vision-based agentic loop for LinkedIn.

Given a natural language instruction, executes it by repeatedly:
1. Taking a screenshot
2. Asking the LLM what to do next
3. Executing the action
"""

import json
import time
import base64

MAX_STEPS = 25

_DECISION_PROMPT = """You are controlling a browser to complete a task on LinkedIn.

Task: {task}

Current URL: {url}

Decide the NEXT SINGLE action. Return ONLY valid JSON, no markdown:
{{
  "action": "click" | "type" | "navigate" | "scroll" | "wait" | "done" | "failed",
  "x": <pixel x, required for click>,
  "y": <pixel y, required for click>,
  "text": "<text to type, required for type>",
  "url": "<full URL, required for navigate>",
  "direction": "up" | "down",
  "amount": <pixels, for scroll>,
  "reason": "<one line explanation>",
  "result": "<summary, only for done/failed>"
}}

Rules:
- ONE action per turn
- Use "done" when the task is complete
- Use "failed" if impossible to complete
- Click coordinates are pixel positions on the screenshot
"""


def run_task(page, instruction: str, on_step=None) -> dict:
    """Execute a free-form task using a vision+action loop.

    Returns dict: {status: completed|failed, result: str, steps: list}
    """
    steps = []

    for step_num in range(1, MAX_STEPS + 1):
        screenshot_bytes = page.screenshot()
        current_url = page.url

        prompt = _DECISION_PROMPT.format(task=instruction, url=current_url)

        try:
            decision = _ask_llm(screenshot_bytes, prompt)
        except Exception as e:
            return {"status": "failed", "result": f"LLM error: {e}", "steps": steps}

        action = decision.get("action", "failed")
        reason = decision.get("reason", "")
        steps.append({"step": step_num, "action": action, "reason": reason})

        if on_step:
            on_step(step_num, action, reason)

        if action == "done":
            return {"status": "completed", "result": decision.get("result", "Task completed"), "steps": steps}

        if action == "failed":
            return {"status": "failed", "result": decision.get("result", "Task could not be completed"), "steps": steps}

        try:
            _execute(page, decision)
        except Exception as e:
            steps[-1]["error"] = str(e)
            print(f"[TaskExecutor] Action error at step {step_num}: {e}")

        time.sleep(1.5)

    return {"status": "failed", "result": "Max steps reached without completing task", "steps": steps}


def _ask_llm(screenshot_bytes: bytes, prompt: str) -> dict:
    from config import OPENAI_API_KEY, OPENAI_VISION_MODEL
    from openai import OpenAI

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for task execution")

    image_b64 = base64.b64encode(screenshot_bytes).decode()
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
        timeout=25,
    )

    text = (response.choices[0].message.content or "").strip()
    # Strip markdown code blocks if present
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:].strip()

    return json.loads(text)


def _execute(page, decision: dict):
    action = decision["action"]

    if action == "click":
        x, y = int(decision["x"]), int(decision["y"])
        page.mouse.click(x, y)

    elif action == "type":
        text = decision.get("text", "")
        page.keyboard.type(text, delay=50)

    elif action == "navigate":
        url = decision["url"]
        page.goto(url, wait_until="domcontentloaded", timeout=20000)

    elif action == "scroll":
        direction = decision.get("direction", "down")
        amount = int(decision.get("amount", 400))
        page.mouse.wheel(0, amount if direction == "down" else -amount)

    elif action == "wait":
        time.sleep(2)
