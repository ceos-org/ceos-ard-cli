import shutil

from pathlib import Path
from .utils.files import read_file, write_file
from .utils.pfs import read_pfs
from .utils.requirement import slugify
from .utils.template import read_template
from .schema import REFERENCE_PATH

def unique_merge(existing, additional, key = None):
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

def compile(pfs, out, editable = False):
    folder = Path(out).parent
    # create folder if needed
    folder.mkdir(parents=True, exist_ok=True)
    # copy assets if needed
    assets = folder / "assets"
    if not assets.exists():
        shutil.copytree(Path("assets"), assets)
    # read the PFS information
    data = read_pfs(pfs)
    # move the glossary and references to the top level
    data = bubble_up(data)
    # write a json file for debugging
    # import json
    # write_file(f"{out}.debug.json", json.dumps(data, indent=2))
    # create the markfown template
    compile_markdown(data, f"{out}.md", editable)
    # write bibtex file to disk
    compile_bibtex(data, f"{out}.bib")

def compile_bibtex(data, out):
    references = []
    # Read references form disk
    for ref in data["references"]:
        filepath = REFERENCE_PATH.format(id=ref)
        bibtex = read_file(filepath)
        references.append(bibtex)
    # Merge into a single string
    merged_bibtex = "\n".join(references)
    # Write a single bibtex file back to disk
    write_file(out, merged_bibtex)

# make uid unique so that it can be used in multiple categories
def create_uid(block, req_id):
    return slugify(block['category']['id'] + "." + req_id)

def compile_markdown(data, out, editable):
    # create a copy of the data for the template
    context = data.copy()

    context["editable"] = editable
    # sort glossary
    context["glossary"] = sorted(context["glossary"], key = lambda x: x['term'].lower())
    # todo: implement automatic creation of history based on git logs?
    # todo: alternatively, add changelog to the individual files with a timestamp and compile it from there
    context["history"] = "Not available yet"

    # make a dict of all requirements for efficient dependency lookup
    all_requirements = {}
    # generate uid for each requirement and fill dependency lookups
    for block in context["requirements"]:
        # make a dict of the requirements in this category for efficient dependency lookup
        local_requirements = {}
        for req in block["requirements"]:
            # make uid unique if it can be used in multiple categories
            req['uid'] = create_uid(block, req['id'])
            local_requirements[req['id']] = req['uid']
            all_requirements[req['id']] = req['uid']

    # resolve dependencies
    for block in context["requirements"]:
        for req in block["requirements"]:
            for i, id in enumerate(req['dependencies']):
                # 1. Check to the requirement in the same requirement category.
                if id in local_requirements:
                    ref_id = local_requirements[id]
                # 2. Refers to the requirement in any other category.
                elif id in all_requirements:
                    ref_id = all_requirements[id]
                else:
                    raise ValueError(f"Unmet dependency {id} for requirement {req['uid']}")

                req['dependencies'][i] = ref_id
                # Update the requirements in the texts
                update_requirement_references(req, id, ref_id)

    # read, fill and write the template
    template = read_template()
    markdown = template.render(**context)
    write_file(out, markdown)

# replace all requirement references in the texts with the resolved references
def update_requirement_references(req, old_id, new_id):
    req['description'] = update_requirement_reference(req['description'], old_id, new_id)
    if req['threshold'] is not None:
        req['threshold']['description'] = update_requirement_reference(req['threshold']['description'], old_id, new_id)
        req['threshold']['notes'] = update_requirement_reference(req['threshold']['notes'], old_id, new_id)
    if req['goal'] is not None:
        req['goal']['description'] = update_requirement_reference(req['goal']['description'], old_id, new_id)
        req['goal']['notes'] = update_requirement_reference(req['goal']['notes'], old_id, new_id)

# replace all requirement references in the given texts with the resolved references
def update_requirement_reference(req, old_id, new_id):
    if isinstance(req, list):
        return [update_requirement_reference(r, old_id, new_id) for r in req]
    elif isinstance(req, str):
        # todo: this can probably be improved with a regex to minimmize false positives
        return req.replace(f"@{old_id}", f"@sec:{new_id}")
    else:
        return req
