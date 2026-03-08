from browser import open_browser
from dom import get_elements
from llm import decide_action
from executor_browser import execute
import time

goal = "Search OpenAI on google"

page = open_browser()

time.sleep(3)

for step in range(5):

    elements = get_elements(page)

    action = decide_action(goal, elements)

    print("AI action:", action)

    execute(page, action, elements)

    time.sleep(2)