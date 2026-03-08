def execute(page, action, elements):

    el = elements[action["id"]]

    selector = el["selector"]
    tag = el.get("tag", "").upper()

    if action["action"] == "type":
        if tag in ("INPUT", "TEXTAREA"):
            page.locator(selector).first.fill(action["text"])
        else:
            # For non-input elements, click first then type via keyboard
            page.locator(selector).first.click()
            page.keyboard.type(action["text"])
        page.keyboard.press("Enter")

    if action["action"] == "click":
        page.locator(selector).first.click()