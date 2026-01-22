import shutil
from pathlib import Path
from typing import Union
from collections import defaultdict

from .schema import REFERENCE_PATH
from .utils.files import read_file, write_file
from .utils.pfs import read_pfs
from .utils.requirement import slugify
from .utils.template import read_template


def topological_sort_requirements(
    requirements_by_pfs: list[list[str]],
    equivalence_groups: dict[str, str] = None
) -> list[str]:
    """
    Topologically sort requirements while preserving relative order from each PFS document.

    Args:
        requirements_by_pfs: List of requirement ID lists, one per PFS document.
                            Each inner list represents the order of requirements in that PFS.
        equivalence_groups: Optional mapping from requirement ID to a group key.
                           Requirements with the same group key are considered equivalent
                           for ordering purposes and will be placed together.
                           If None, each requirement is its own group.

    Returns:
        A merged list of all unique requirement IDs, sorted to respect the relative
        ordering from all input documents. Requirements in the same equivalence group
        are placed consecutively.

    Example:
        Input: [['A', 'B', 'C', 'D', 'E'], ['A', 'C', 'E', 'F', 'X'], ['A', 'A2', 'B', 'E', 'F']]
        With equivalence_groups={'A': 'grp1', 'A2': 'grp1'}
        Output: ['A', 'A2', 'B', 'C', 'D', 'E', 'F', 'X']  (A and A2 stay together)
    """
    if equivalence_groups is None:
        equivalence_groups = {}

    def get_group(req_id: str) -> str:
        return equivalence_groups.get(req_id, req_id)

    # Build a graph of ordering constraints between GROUPS
    # If group(A) appears before group(B) in any document, we add an edge group(A) -> group(B)
    graph = defaultdict(set)  # group -> set of groups that must come after
    in_degree = defaultdict(int)  # count of incoming edges per group
    all_groups = set()
    group_members = defaultdict(list)  # group -> list of requirement IDs in this group (ordered by first appearance)
    seen_members = set()

    for pfs_reqs in requirements_by_pfs:
        for i, req_id in enumerate(pfs_reqs):
            group = get_group(req_id)
            all_groups.add(group)

            # Track members of each group (preserve first-appearance order)
            if req_id not in seen_members:
                group_members[group].append(req_id)
                seen_members.add(req_id)

            # Add edges to all subsequent GROUPS in this document
            for j in range(i + 1, len(pfs_reqs)):
                successor = pfs_reqs[j]
                successor_group = get_group(successor)

                # Don't add edge within the same group
                if group != successor_group and successor_group not in graph[group]:
                    graph[group].add(successor_group)
                    in_degree[successor_group] += 1

    # Initialize in_degree for groups with no incoming edges
    for group in all_groups:
        if group not in in_degree:
            in_degree[group] = 0

    # Kahn's algorithm for topological sort on groups
    queue = [group for group in all_groups if in_degree[group] == 0]
    queue.sort()

    sorted_groups = []
    while queue:
        group = queue.pop(0)
        sorted_groups.append(group)

        successors = sorted(graph[group])
        for successor in successors:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                import bisect
                bisect.insort(queue, successor)

    # Check for cycles
    if len(sorted_groups) != len(all_groups):
        # Fall back to simple ordering by first appearance if cycle detected
        seen = set()
        sorted_groups = []
        for pfs_reqs in requirements_by_pfs:
            for req_id in pfs_reqs:
                group = get_group(req_id)
                if group not in seen:
                    seen.add(group)
                    sorted_groups.append(group)

    # Expand groups back to individual requirement IDs
    result = []
    for group in sorted_groups:
        result.extend(group_members[group])

    return result


def unique_merge(existing, additional, key=None):
    if key is None:
        return list(set(existing + additional))
    else:
        existing_keys = [e[key] for e in existing]
        for a in additional:
            if a[key] not in existing_keys:
                existing.append(a)
        return existing


def bubble_up(root):
    return _bubble_up(root, root)


def _bubble_up(data, root):
    if isinstance(data, dict):
        if "glossary" in data:
            root["glossary"] = unique_merge(root["glossary"], data["glossary"], "term")
        if "references" in data:
            root["references"] = unique_merge(root["references"], data["references"])
        for v in data.values():
            _bubble_up(v, root)
    elif isinstance(data, list):
        for v in data:
            _bubble_up(v, root)
    return root


def to_id_dict(data):
    d = {}
    for item in data:
        d[item["id"]] = item
    return d


def combine_pfs(multi_pfs):
    data = {
        "combined": True,
        "id": [],
        "title": [],
        "version": "",
        "type": set(),
        "applies_to": {},
        "introduction": {},
        "glossary": {},
        "references": set(),
        "annexes": {},
        "authors": {},
        "requirements": [],
    }
    categories = {}
    requirements = {}
    # Track requirement order per category per PFS for topological sorting
    requirement_orders = defaultdict(list)  # cat_id -> list of [req_id lists per pfs]
    # Track equivalence groups: requirements with the same title should be grouped together
    equivalence_groups = defaultdict(dict)  # cat_id -> {req_id: group_key}
    title_to_group = defaultdict(dict)  # cat_id -> {title: group_key}

    for pfs in multi_pfs.values():
        data["id"].append(pfs["id"])
        data["title"].append(pfs["title"])
        data["type"].add(pfs["type"])
        data["applies_to"][pfs["title"]] = pfs["applies_to"]
        data["introduction"] = to_id_dict(pfs["introduction"])
        data["glossary"] = to_id_dict(pfs["glossary"])
        data["references"].update(pfs["references"])
        data["annexes"] = to_id_dict(pfs["annexes"])

        for organization in pfs["authors"]:
            key = organization["name"] + organization.get("country", "")
            if key not in data["authors"]:
                data["authors"][key] = organization
            else:
                existing = data["authors"][key]["members"]
                for member in organization["members"]:
                    if member not in existing:
                        existing.append(member)

        for block in pfs["requirements"]:
            cat_id = block["category"]["id"]
            if cat_id not in categories:
                categories[cat_id] = block["category"]
                requirements[cat_id] = {}

            # Collect the order of requirements for this PFS
            pfs_req_order = []
            for item in block["requirements"]:
                req_id = item["id"]
                req_title = item.get("title", "")
                pfs_req_order.append(req_id)

                # Build equivalence groups based on title
                # Requirements with the same title get the same group key
                if req_title:
                    if req_title in title_to_group[cat_id]:
                        # Use existing group key for this title
                        equivalence_groups[cat_id][req_id] = title_to_group[cat_id][req_title]
                    else:
                        # Create new group with this req_id as the group key
                        title_to_group[cat_id][req_title] = req_id
                        equivalence_groups[cat_id][req_id] = req_id

                # Store which PFS this requirement applies to
                if req_id not in requirements[cat_id]:
                    item = item.copy()
                    item["applies_to"] = [pfs["id"]]
                    requirements[cat_id][req_id] = item
                else:
                    requirements[cat_id][req_id]["applies_to"].append(pfs["id"])

            requirement_orders[cat_id].append(pfs_req_order)

    data["id"] = "+".join(data["id"])
    data["title"] = "Combined: " + " / ".join(data["title"])
    data["type"] = "Fusion" if len(data["type"]) > 1 else data["type"].pop()
    data["introduction"] = list(data["introduction"].values())
    data["glossary"] = list(data["glossary"].values())
    data["references"] = list(data["references"])
    data["annexes"] = list(data["annexes"].values())
    data["authors"] = list(data["authors"].values())

    for value in categories.values():
        cat_id = value["id"]
        # Use topological sort to merge requirements from all PFS documents
        # Pass equivalence groups so requirements with same title stay together
        sorted_req_ids = topological_sort_requirements(
            requirement_orders[cat_id],
            equivalence_groups.get(cat_id, {})
        )
        sorted_requirements = [requirements[cat_id][req_id] for req_id in sorted_req_ids]

        data["requirements"].append(
            {
                "category": value,
                "requirements": sorted_requirements,
            }
        )

    return data


def compile(
    pfs: Union[list[str], str],
    out: Union[Path, str],
    input_dir: Union[Path, str],
    editable: bool = False,
    metadata: dict = {},
    debug: bool = False,
):
    if isinstance(pfs, str):
        pfs = [pfs]

    folder = Path(out).parent
    # create folder if needed
    folder.mkdir(parents=True, exist_ok=True)
    # copy assets if needed
    assets_target = folder / "assets"
    input_dir = Path(input_dir).resolve()
    assets_source = input_dir / "assets"
    if not assets_target.exists() and assets_source != assets_target:
        shutil.copytree(assets_source, assets_target)

    multi_pfs = {}
    for p in pfs:
        # read the PFS information and
        # move the glossary and references to the top level
        multi_pfs[p] = bubble_up(read_pfs(p, input_dir))

    if len(pfs) > 1:
        data = combine_pfs(multi_pfs)
    else:
        data = multi_pfs[pfs[0]]

    # Override metadata if provided
    data["id"] = metadata.get("id") or data["id"]
    data["title"] = metadata.get("title") or data["title"]
    data["version"] = metadata.get("version") or data["version"]
    data["type"] = metadata.get("type") or data["type"]

    # write a json file for debugging
    if debug:
        import json

        write_file(f"{out}.debug.json", json.dumps(data, indent=2))

    # create the markfown template
    compile_markdown(data, f"{out}.md", editable, input_dir)
    # write bibtex file to disk
    compile_bibtex(data, f"{out}.bib", input_dir)


def compile_bibtex(data, out, input_dir: Path):
    input_dir = Path(input_dir).resolve()
    references = []
    # Read references form disk
    for ref in data["references"]:
        filepath = input_dir / REFERENCE_PATH.format(id=ref)
        bibtex = read_file(filepath)
        references.append(bibtex)
    # Merge into a single string
    merged_bibtex = "\n".join(references)
    # Write a single bibtex file back to disk
    write_file(out, merged_bibtex)


# make uid unique so that it can be used in multiple categories
def create_uid(block, req_id):
    return slugify(block["category"]["id"] + "." + req_id)


def compile_markdown(data, out, editable, input_dir: Path):
    input_dir = Path(input_dir).resolve()
    # create a copy of the data for the template
    context = data.copy()

    context["editable"] = editable
    # sort glossary
    context["glossary"] = sorted(context["glossary"], key=lambda x: x["term"].lower())
    # todo: implement automatic creation of history based on git logs?
    # todo: alternatively, add changelog to the individual files with a timestamp and compile it from there
    context["history"] = "Not available yet"

    # make a dict of all requirements for efficient dependency lookup
    all_requirements = {}
    # make a dict of the requirements in this category for efficient dependency lookup
    local_requirements = {}
    # generate uid for each requirement and fill dependency lookups
    for block in context["requirements"]:
        cid = block["category"]["id"]
        local_requirements[cid] = {}
        for req in block["requirements"]:
            # make uid unique if it can be used in multiple categories
            req["uid"] = create_uid(block, req["id"])
            local_requirements[cid][req["id"]] = req["uid"]
            all_requirements[req["id"]] = req["uid"]

    # resolve dependencies
    for block in context["requirements"]:
        cid = block["category"]["id"]
        for req in block["requirements"]:
            for i, id in enumerate(req["dependencies"]):
                # 1. Check to the requirement in the same requirement category.
                if id in local_requirements[cid]:
                    ref_id = local_requirements[cid][id]
                # 2. Refers to the requirement in any other category.
                elif id in all_requirements:
                    ref_id = all_requirements[id]
                else:
                    raise ValueError(
                        f"Unmet dependency {id} for requirement {req['uid']}"
                    )

                req["dependencies"][i] = ref_id
                # Update the requirements in the texts
                update_requirement_references(req, id, ref_id)

    # read, fill and write the template
    template = read_template(input_dir)
    markdown = template.render(**context)
    write_file(out, markdown)


# replace all requirement references in the texts with the resolved references
def update_requirement_references(req, old_id, new_id):
    req["description"] = update_requirement_reference(
        req["description"], old_id, new_id
    )
    if req["threshold"] is not None:
        req["threshold"]["description"] = update_requirement_reference(
            req["threshold"]["description"], old_id, new_id
        )
        req["threshold"]["notes"] = update_requirement_reference(
            req["threshold"]["notes"], old_id, new_id
        )
    if req["goal"] is not None:
        req["goal"]["description"] = update_requirement_reference(
            req["goal"]["description"], old_id, new_id
        )
        req["goal"]["notes"] = update_requirement_reference(
            req["goal"]["notes"], old_id, new_id
        )


# replace all requirement references in the given texts with the resolved references
def update_requirement_reference(req, old_id, new_id):
    if isinstance(req, list):
        return [update_requirement_reference(r, old_id, new_id) for r in req]
    elif isinstance(req, str):
        # todo: this can probably be improved with a regex to minimmize false positives
        return req.replace(f"@{old_id}", f"@sec:{new_id}")
    else:
        return req
