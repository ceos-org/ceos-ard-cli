def find_deprecated(data):
    """
    Recursively collect the deprecated building blocks that are used in a PFS document.

    Works on both unresolved (read_pfs) and resolved (resolve_refs/bubble_up) documents.
    Returns a list of human-readable descriptors, one per building block.
    """
    found = {}
    _find_deprecated(data, found)
    return list(found.values())


def _find_deprecated(data, found):
    if isinstance(data, dict):
        if data.get("deprecated"):
            # deduplicate building blocks that are used multiple times
            key = data.get("filepath", id(data))
            if key not in found:
                found[key] = describe(data)
        for v in data.values():
            _find_deprecated(v, found)
    elif isinstance(data, list):
        for v in data:
            _find_deprecated(v, found)


def describe(data):
    if "term" in data:
        kind = "glossary term"
        name = data["term"]
    elif "version" in data:
        kind = "PFS"
        name = data.get("title", data.get("id", ""))
    elif isinstance(data.get("requirements"), dict):
        kind = "requirement"
        name = data.get("title", data.get("id", ""))
    else:
        kind = "section"
        name = data.get("title", data.get("id", ""))

    filepath = data.get("filepath")
    location = f" ({filepath})" if filepath else ""
    return f"{kind} '{name}'{location}"
