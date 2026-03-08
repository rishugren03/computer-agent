from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)
def decide_action(goal, elements):

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

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content

    return json.loads(content)