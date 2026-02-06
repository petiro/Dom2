"""
DOM Scanner - Reads page structure and extracts element metadata.
Used by the auto-learning system to understand site layout without screenshots.
"""


def scan_dom(page, max_elements=400):
    """
    Scan the current page DOM and return structured element data.

    Args:
        page: Playwright page object
        max_elements: Maximum number of elements to scan

    Returns:
        List of dicts with tag, text, class, id, role, type, href, data attributes
    """
    elements = page.query_selector_all(
        "button, input, a, select, textarea, "
        "[role='button'], [data-testid], "
        "div.bet, div.market, span.odds, "
        ".sac-ParticipantOddsOnly80_Odds, "
        ".rcl-ParticipantFixtureDetails_TeamNames, "
        ".bs-BetslipContent, .bs-StakeBox"
    )

    dom_data = []
    for el in elements[:max_elements]:
        try:
            entry = {
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "text": (el.inner_text() or "")[:80].strip(),
                "class": el.get_attribute("class") or "",
                "id": el.get_attribute("id") or "",
                "role": el.get_attribute("role") or "",
                "type": el.get_attribute("type") or "",
                "href": el.get_attribute("href") or "",
                "placeholder": el.get_attribute("placeholder") or "",
                "data_testid": el.get_attribute("data-testid") or "",
            }
            # Only include elements with useful info
            if entry["text"] or entry["class"] or entry["id"] or entry["data_testid"]:
                dom_data.append(entry)
        except Exception:
            continue

    return dom_data


def build_selector_for_element(element_data):
    """
    Build a CSS selector from element metadata.

    Args:
        element_data: dict from scan_dom

    Returns:
        Best CSS selector string
    """
    tag = element_data.get("tag", "")
    cls = element_data.get("class", "")
    el_id = element_data.get("id", "")
    data_testid = element_data.get("data_testid", "")
    text = element_data.get("text", "")

    # Priority: data-testid > id > class > text
    if data_testid:
        return f'[data-testid="{data_testid}"]'
    if el_id:
        return f"#{el_id}"
    if cls:
        # Use most specific class (usually the longest unique one)
        classes = cls.split()
        if classes:
            best = max(classes, key=len)
            return f"{tag}.{best}"
    if text and len(text) < 40:
        return f'{tag}:has-text("{text}")'

    return ""
