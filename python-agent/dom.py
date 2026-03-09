"""Comprehensive DOM extraction for browser automation."""


def get_elements(page):
    """Extract all visible interactive elements from the page DOM.
    
    Covers: inputs, textareas, buttons, links, selects, options,
    ARIA widgets (combobox, listbox, option, tab, menuitem, switch),
    contenteditable elements, labels, and custom dropdown items.
    """

    elements = page.evaluate("""
    () => {
        const items = []
        let id = 0

        const INTERACTIVE_SELECTORS = [
            'input', 'textarea', 'button', 'a[href]', 'select', 'option',
            '[role="button"]', '[role="checkbox"]', '[role="combobox"]',
            '[role="listbox"]', '[role="option"]', '[role="tab"]',
            '[role="menuitem"]', '[role="switch"]', '[role="radio"]',
            '[role="link"]', '[role="searchbox"]', '[role="textbox"]',
            '[contenteditable="true"]', '[contenteditable=""]',
            'label', 'details > summary',
            '[data-value]', '[onclick]',
            'li[class]'
        ].join(', ')

        const seen = new Set()

        document.querySelectorAll(INTERACTIVE_SELECTORS).forEach(el => {
            // Skip duplicates
            if (seen.has(el)) return
            seen.add(el)

            const rect = el.getBoundingClientRect()
            if (rect.width <= 0 || rect.height <= 0) return

            // Check actual visibility
            const style = window.getComputedStyle(el)
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return

            // Check if element is in viewport (with some buffer)
            const inViewport = (
                rect.top < window.innerHeight + 200 &&
                rect.bottom > -200 &&
                rect.left < window.innerWidth + 200 &&
                rect.right > -200
            )

            // Build a robust CSS selector
            let selector = el.tagName.toLowerCase()
            if (el.id) {
                selector = `#${CSS.escape(el.id)}`
            } else if (el.name) {
                selector += `[name="${CSS.escape(el.name)}"]`
            } else if (el.getAttribute('aria-label')) {
                selector += `[aria-label="${CSS.escape(el.getAttribute('aria-label'))}"]`
            } else if (el.placeholder) {
                selector += `[placeholder="${CSS.escape(el.placeholder)}"]`
            } else if (el.className && typeof el.className === 'string' && el.className.trim()) {
                const cls = el.className.trim().split(/\\s+/).slice(0, 2).map(c => '.' + CSS.escape(c)).join('')
                selector += cls
            }

            // Gather text content (truncated)
            let text = (el.innerText || el.textContent || '').trim()
            if (text.length > 100) text = text.substring(0, 100) + '...'

            const item = {
                id: id++,
                tag: el.tagName,
                text: text,
                type: el.type || '',
                role: el.getAttribute('role') || '',
                selector: selector,
                placeholder: el.placeholder || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                ariaExpanded: el.getAttribute('aria-expanded'),
                ariaSelected: el.getAttribute('aria-selected'),
                value: el.value || '',
                href: el.href || '',
                name: el.name || '',
                disabled: el.disabled || false,
                checked: el.checked || false,
                inViewport: inViewport,
                bbox: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height)
                }
            }

            items.push(item)
        })

        // Sort: in-viewport first, then by vertical position
        items.sort((a, b) => {
            if (a.inViewport && !b.inViewport) return -1
            if (!a.inViewport && b.inViewport) return 1
            return a.bbox.y - b.bbox.y
        })

        // Re-assign sequential IDs after sort
        items.forEach((item, idx) => { item.id = idx })

        // Cap at 80 elements to keep LLM context manageable
        return items.slice(0, 80)
    }
    """)

    return elements


def get_page_info(page):
    """Get current page URL, title, and basic metadata."""

    info = page.evaluate("""
    () => ({
        url: window.location.href,
        title: document.title,
        hasAlert: !!document.querySelector('[role="alert"], .alert, .error, .success'),
        alertText: (() => {
            const alert = document.querySelector('[role="alert"], .alert, .error, .success')
            return alert ? (alert.innerText || '').trim().substring(0, 200) : ''
        })(),
        loadingIndicators: document.querySelectorAll('.loading, .spinner, [aria-busy="true"]').length > 0
    })
    """)

    return info


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