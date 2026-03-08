from human import human_click, human_type, random_delay


def execute(page, action, elements):
    """Execute a browser action with human-like behavior."""

    el = elements[action["id"]]

    selector = el["selector"]
    tag = el.get("tag", "").upper()
    bbox = el.get("bbox")

    if action["action"] == "type":
        if bbox:
            # Use human-like click to focus the element first
            center_x = bbox["x"] + bbox["w"] / 2
            center_y = bbox["y"] + bbox["h"] / 2
            human_click(page, center_x, center_y)
            random_delay(0.2, 0.5)
            human_type(page, action["text"])
        else:
            # Fallback: use Playwright selectors
            if tag in ("INPUT", "TEXTAREA"):
                page.locator(selector).first.fill(action["text"])
            else:
                page.locator(selector).first.click()
                page.keyboard.type(action["text"])

        page.keyboard.press("Enter")

    if action["action"] == "click":
        if bbox:
            center_x = bbox["x"] + bbox["w"] / 2
            center_y = bbox["y"] + bbox["h"] / 2
            human_click(page, center_x, center_y)
        else:
            page.locator(selector).first.click()