"""Accessibility Tree (ACT) extraction for GhostAgent.

The Accessibility Tree is ~10x more stable than the DOM because
it's legally required for screen readers. LinkedIn can change CSS
classes and HTML structure, but the ACT roles and labels must remain
consistent for accessibility compliance.

This module extracts, flattens, and queries the ACT for semantic
element identification.
"""

import json


def extract_act(page):
    """Extract the Accessibility Tree from the page.

    Uses two strategies:
    1. CDP (Chrome DevTools Protocol) for the full AX tree
    2. Fallback: DOM-based ARIA attribute extraction

    Patchright doesn't expose page.accessibility, so we go
    through CDP or parse ARIA attributes directly.

    Returns:
        dict: The root ACT node with nested children.
    """
    # Strategy 1: Try CDP-based extraction
    try:
        cdp = page.context.new_cdp_session(page)
        result = cdp.send("Accessibility.getFullAXTree")
        cdp.detach()

        if result and "nodes" in result:
            return _cdp_nodes_to_tree(result["nodes"])
    except Exception:
        pass

    # Strategy 2: Fallback to DOM-based ARIA extraction
    try:
        return _extract_aria_from_dom(page)
    except Exception as e:
        print(f"[ACT] All extraction methods failed: {e}")
        return {}


def _cdp_nodes_to_tree(ax_nodes):
    """Convert CDP AX nodes flat list into a nested tree structure."""
    if not ax_nodes:
        return {}

    node_map = {}
    for node in ax_nodes:
        node_id = node.get("nodeId", "")
        role_obj = node.get("role", {})
        name_obj = node.get("name", {})

        tree_node = {
            "role": role_obj.get("value", "") if isinstance(role_obj, dict) else str(role_obj),
            "name": name_obj.get("value", "") if isinstance(name_obj, dict) else str(name_obj),
            "description": "",
            "children": [],
        }

        # Extract properties
        for prop in node.get("properties", []):
            pname = prop.get("name", "")
            pval = prop.get("value", {})
            value = pval.get("value", "") if isinstance(pval, dict) else str(pval)

            if pname == "description":
                tree_node["description"] = value
            elif pname == "disabled":
                tree_node["disabled"] = value
            elif pname == "focused":
                tree_node["focused"] = value
            elif pname == "checked":
                tree_node["checked"] = value

        node_map[node_id] = tree_node

    # Build tree from parent-child relationships
    root = None
    for node in ax_nodes:
        node_id = node.get("nodeId", "")
        child_ids = node.get("childIds", [])
        tree_node = node_map.get(node_id)

        if tree_node:
            for cid in child_ids:
                child = node_map.get(cid)
                if child:
                    tree_node["children"].append(child)

            if root is None:
                root = tree_node

    return root or {}


def _extract_aria_from_dom(page):
    """Fallback: extract ARIA roles and labels directly from the DOM.

    This doesn't give a full accessibility tree, but provides enough
    semantic info for navigation (buttons, links, textboxes, etc.).
    """
    nodes = page.evaluate("""() => {
        const SELECTORS = [
            '[role]', '[aria-label]', 'button', 'a[href]',
            'input', 'textarea', 'select', 'h1', 'h2', 'h3',
            '[contenteditable="true"]', 'nav', 'main', 'dialog',
        ].join(', ');

        function extractNode(el) {
            const role = el.getAttribute('role') || el.tagName.toLowerCase();
            const name = el.getAttribute('aria-label')
                || el.getAttribute('title')
                || el.getAttribute('placeholder')
                || (el.tagName === 'A' ? el.innerText?.trim() : '')
                || (el.tagName === 'BUTTON' ? el.innerText?.trim() : '')
                || (el.tagName.match(/^H[1-6]$/) ? el.innerText?.trim() : '')
                || '';

            return {
                role: role,
                name: name.substring(0, 100),
                description: el.getAttribute('aria-description') || '',
                value: el.value || '',
                disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                focused: document.activeElement === el,
                checked: el.checked || el.getAttribute('aria-checked') === 'true',
                children: [],
            };
        }

        const root = {
            role: 'RootWebArea',
            name: document.title,
            children: [],
        };

        const elements = document.querySelectorAll(SELECTORS);
        elements.forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return;

            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return;

            const node = extractNode(el);
            if (node.name || ['button', 'link', 'textbox', 'searchbox', 'combobox',
                'checkbox', 'radio', 'tab', 'menuitem', 'navigation', 'main',
                'dialog', 'heading', 'input', 'textarea', 'a', 'select'].includes(node.role)) {
                root.children.push(node);
            }
        });

        return root;
    }""")

    return nodes if nodes else {}



def act_to_flat_list(tree, parent_context=""):
    """Flatten the ACT tree into a list of actionable nodes.

    Each node gets a unique path-like identifier based on its
    hierarchy, making it easy to find specific elements.

    Args:
        tree: ACT node (dict with role, name, children, etc.)
        parent_context: Parent path for building unique identifiers.

    Returns:
        list[dict]: Flat list of nodes with:
            - role: ARIA role (button, link, textbox, etc.)
            - name: Accessible name / aria-label
            - description: Accessible description
            - value: Current value (for inputs)
            - path: Hierarchical path (e.g. "main/section/button:Connect")
            - focused: Whether the element is focused
            - disabled: Whether the element is disabled
    """
    nodes = []

    if not tree or not isinstance(tree, dict):
        return nodes

    role = tree.get("role", "")
    name = tree.get("name", "")

    # Build path identifier
    node_id = f"{role}:{name}" if name else role
    path = f"{parent_context}/{node_id}" if parent_context else node_id

    # Only include actionable / interesting nodes
    actionable_roles = {
        "button", "link", "textbox", "searchbox", "combobox",
        "checkbox", "radio", "switch", "tab", "menuitem",
        "option", "slider", "spinbutton", "heading",
        "img", "dialog", "alert", "status",
    }

    if role.lower() in actionable_roles or name:
        node = {
            "role": role,
            "name": name,
            "description": tree.get("description", ""),
            "value": tree.get("value", ""),
            "path": path,
            "focused": tree.get("focused", False),
            "disabled": tree.get("disabled", False),
            "checked": tree.get("checked", None),
            "selected": tree.get("selected", None),
            "level": tree.get("level", None),
        }
        nodes.append(node)

    # Recurse into children
    for child in tree.get("children", []):
        nodes.extend(act_to_flat_list(child, parent_context=path))

    return nodes


def find_node_by_role_and_name(tree, role, name=None, partial_match=True):
    """Find ACT nodes matching a specific role and optional name.

    This is the primary lookup method — more resilient than DOM selectors
    because ARIA roles and labels are standardized and stable.

    Args:
        tree: ACT tree (dict).
        role: ARIA role to search for (e.g. "button", "link").
        name: Optional name/label to match.
        partial_match: If True, match if name is contained in node name.

    Returns:
        list[dict]: Matching nodes from the flat tree.
    """
    flat = act_to_flat_list(tree)
    results = []

    for node in flat:
        if node["role"].lower() != role.lower():
            continue

        if name is None:
            results.append(node)
        elif partial_match and name.lower() in node["name"].lower():
            results.append(node)
        elif not partial_match and node["name"].lower() == name.lower():
            results.append(node)

    return results


def find_buttons(tree, label=None):
    """Find button elements in the ACT. Optionally filter by label."""
    return find_node_by_role_and_name(tree, "button", label)


def find_links(tree, label=None):
    """Find link elements in the ACT. Optionally filter by label."""
    return find_node_by_role_and_name(tree, "link", label)


def find_textboxes(tree, label=None):
    """Find text input elements in the ACT. Optionally filter by label."""
    results = find_node_by_role_and_name(tree, "textbox", label)
    results.extend(find_node_by_role_and_name(tree, "searchbox", label))
    return results


def find_by_text(tree, text, partial_match=True):
    """Find any ACT node containing specific text in its name.

    Useful when you know the text on screen but not the element type.
    """
    flat = act_to_flat_list(tree)
    results = []

    for node in flat:
        node_name = node.get("name", "")
        if not node_name:
            continue

        if partial_match and text.lower() in node_name.lower():
            results.append(node)
        elif not partial_match and text.lower() == node_name.lower():
            results.append(node)

    return results


def get_page_structure(tree, max_depth=3):
    """Get a simplified structural overview of the page ACT.

    Useful for the LLM to understand the page layout without
    seeing every single node. Returns a compact representation.

    Args:
        tree: ACT tree.
        max_depth: Maximum depth to traverse.

    Returns:
        str: Indented text representation of the page structure.
    """
    lines = []
    _build_structure(tree, lines, depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _build_structure(node, lines, depth, max_depth):
    """Recursively build the structure string."""
    if not node or depth > max_depth:
        return

    role = node.get("role", "")
    name = node.get("name", "")
    indent = "  " * depth

    # Compact representation
    if name:
        lines.append(f"{indent}{role}: {name[:60]}")
    elif role in {"heading", "button", "link", "textbox", "dialog"}:
        lines.append(f"{indent}{role}")

    for child in node.get("children", []):
        _build_structure(child, lines, depth + 1, max_depth)


def get_interactive_elements_act(page):
    """Get interactive elements via ACT (complement to DOM extraction).

    This is the ACT-based version of dom.py's get_elements().
    More resilient to UI changes because it uses semantic roles
    instead of CSS selectors.

    Returns:
        list[dict]: Interactive elements with role, name, and context.
    """
    tree = extract_act(page)
    if not tree:
        return []

    interactive_roles = {
        "button", "link", "textbox", "searchbox", "combobox",
        "checkbox", "radio", "switch", "tab", "menuitem", "option",
    }

    flat = act_to_flat_list(tree)
    elements = [
        node for node in flat
        if node["role"].lower() in interactive_roles
        and not node.get("disabled", False)
    ]

    return elements
