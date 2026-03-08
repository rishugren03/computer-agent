def get_elements(page):
    """Extract visible interactive elements from the page DOM."""

    elements = page.evaluate("""
    () => {
        const items = []
        let i = 0

        document.querySelectorAll('input, textarea, button, a, [role="button"], [role="checkbox"]').forEach(el => {

            const rect = el.getBoundingClientRect()

            if(rect.width > 0 && rect.height > 0){

                let selector = el.tagName.toLowerCase()

                if(el.name) selector += `[name="${el.name}"]`
                else if(el.id) selector += `#${el.id}`
                else if(el.placeholder) selector += `[placeholder="${el.placeholder}"]`

                items.push({
                    id: i++,
                    tag: el.tagName,
                    text: el.innerText || "",
                    placeholder: el.placeholder || "",
                    selector: selector,
                    role: el.getAttribute("role") || "",
                    type: el.type || "",
                    bbox: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    }
                })
            }
        })

        return items
    }
    """)

    return elements


def detect_recaptcha(page):
    """
    Detect reCAPTCHA iframes on the page.
    Returns a dict with:
      - 'found': bool
      - 'checkbox_frame': frame handle for the checkbox iframe (or None)
      - 'challenge_frame': frame handle for the image challenge iframe (or None)
    """

    result = {"found": False, "checkbox_frame": None, "challenge_frame": None}

    for frame in page.frames:
        url = frame.url
        if "recaptcha/api2/anchor" in url or "recaptcha/enterprise/anchor" in url:
            result["found"] = True
            result["checkbox_frame"] = frame
        elif "recaptcha/api2/bframe" in url or "recaptcha/enterprise/bframe" in url:
            result["found"] = True
            result["challenge_frame"] = frame

    return result