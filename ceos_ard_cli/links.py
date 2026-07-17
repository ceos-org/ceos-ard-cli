import re
from pathlib import Path

from .utils.files import fix_path
from .utils.requirement import slugify


# make uid unique so that it can be used in multiple categories
def create_uid(block, req_id):
    return slugify(block["category"]["id"] + "-" + req_id)


def path_to_id(filepath, input_dir, folder):
    """Convert an absolute building block file path to its folder-relative id (without extension)."""
    base_dir = Path(input_dir) / folder
    rel_path = fix_path(Path(filepath).relative_to(base_dir))
    if rel_path.endswith(".yaml"):
        rel_path = rel_path[:-5]
    return rel_path


def resolve_links(data, input_dir):
    """
    Resolve the `dependencies` (requirements) and `sections` (introduction, annexes,
    requirement categories) aliases of all building blocks in a resolved PFS document.

    Replaces the @alias references in the Markdown fields with the @sec: anchors
    that the template generates for pandoc-crossref.

    Returns a list of human-readable error messages (empty if everything resolved).
    """
    input_dir = Path(input_dir).resolve()
    errors = []

    # make a dict of the requirements per category and overall for efficient dependency lookup,
    # and a dict of all sections (by sections/-relative path) mapping to their anchors
    all_requirements = {}
    local_requirements = {}
    sections = {}
    for block in data["requirements"]:
        category = block["category"]
        cid = category["id"]
        # the anchor of a requirement category is its (short) id
        sections[path_to_id(category["filepath"], input_dir, "sections")] = cid
        local_requirements[cid] = {}
        for req in block["requirements"]:
            # make uid unique if it can be used in multiple categories
            req["uid"] = create_uid(block, req["id"])
            rel_path = path_to_id(req["filepath"], input_dir, "requirements")
            local_requirements[cid][rel_path] = req["uid"]
            all_requirements[rel_path] = req["uid"]
    # the anchor prefixes must match the ones generated in the template
    for annex in data["annexes"]:
        sections[path_to_id(annex["filepath"], input_dir, "sections")] = "annex-" + slugify(annex["id"])
    for section in data["introduction"]:
        sections[path_to_id(section["filepath"], input_dir, "sections")] = "intro-" + slugify(section["id"])

    def resolve_requirement(target, cid):
        """Resolve a requirement path (or list of candidate paths) to a requirement UID.

        The first candidate present in the compiled document is selected,
        requirements in the same category (if any) take precedence.
        """
        candidates = target if isinstance(target, list) else [target]
        for candidate in candidates:
            if cid is not None and candidate in local_requirements.get(cid, {}):
                return local_requirements[cid][candidate]
            if candidate in all_requirements:
                return all_requirements[candidate]
        return None

    def resolve_section(target):
        """Resolve a section path (or list of candidate paths) to a section anchor."""
        candidates = target if isinstance(target, list) else [target]
        for candidate in candidates:
            if candidate in sections:
                return sections[candidate]
        return None

    def resolve_container(container, cid, where):
        """Resolve all aliases of a single building block and rewrite its texts."""
        dependencies = container.get("dependencies") or {}
        links = container.get("sections") or {}
        if not isinstance(dependencies, dict) or not isinstance(links, dict):
            return  # already resolved (e.g. shared section in a combined document)

        for alias in set(dependencies) & set(links):
            errors.append(f"Alias '{alias}' is defined in both 'dependencies' and 'sections' in {where}")

        resolved_deps = []
        resolved_sections = []
        for alias, target in {**links, **dependencies}.items():
            if alias in dependencies:
                anchor = resolve_requirement(target, cid)
                kind, resolved = "dependency", resolved_deps
            else:
                anchor = resolve_section(target)
                kind, resolved = "section dependency", resolved_sections
            if anchor is None:
                candidates = target if isinstance(target, list) else [target]
                errors.append(f"Unmet {kind} '{' / '.join(candidates)}' in {where}")
                continue
            resolved.append(anchor)
            update_references(container, alias, anchor)

        if "dependencies" in container:
            container["dependencies"] = resolved_deps
        if "sections" in container:
            container["sections"] = resolved_sections

    for block in data["requirements"]:
        cid = block["category"]["id"]
        resolve_container(block["category"], cid, f"category '{cid}'")
        for req in block["requirements"]:
            resolve_container(req, cid, f"requirement '{req['id']}' in category '{cid}'")
    for section in data["introduction"] + data["annexes"]:
        resolve_container(section, None, f"section '{section.get('id') or section.get('title')}'")
    resolve_container(data, None, f"PFS document '{data.get('id') or data.get('title')}'")

    return errors


# replace all @alias references in the texts of a building block with the resolved @sec: anchor
def update_references(container, alias, anchor):
    # the negative lookahead prevents replacing aliases that are a prefix
    # of another alias (e.g. @time in @time-sar)
    pattern = re.compile("@" + re.escape(alias) + r"(?![A-Za-z0-9_-])")
    replacement = f"@sec:{anchor}"

    def replace(value):
        if isinstance(value, str):
            return pattern.sub(replacement, value)
        elif isinstance(value, list):
            return [replace(v) for v in value]
        elif isinstance(value, dict):
            # e.g. the applies_to / background fields of a combined document
            return {k: replace(v) for k, v in value.items()}
        else:
            return value

    for field in ("description", "background", "applies_to"):
        if field in container:
            container[field] = replace(container[field])

    parts = container.get("requirements")
    if isinstance(parts, dict):
        for part in parts.values():
            update_part_references(part, replace)
    for key in ("threshold", "goal"):
        if container.get(key):
            update_part_references(container[key], replace)


def update_part_references(part, replace):
    part["description"] = replace(part["description"])
    part["notes"] = replace(part.get("notes", []))
