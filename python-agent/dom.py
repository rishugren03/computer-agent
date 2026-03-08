def get_elements(page):

    elements = page.evaluate("""
    () => {
        const items = []
        let i = 0

        document.querySelectorAll('input, textarea, button, a').forEach(el => {

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
                    selector: selector
                })
            }
        })

        return items
    }
    """)

    return elements