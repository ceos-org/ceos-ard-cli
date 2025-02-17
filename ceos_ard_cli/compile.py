import shutil

from pathlib import Path
from .util import read_pfs, read_template, slugify
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
    # with open(f"{out}.debug.json", 'w', encoding="utf-8") as f:
    #     f.write(json.dumps(data, indent=2))
    # create the markfown template
    compile_markdown(data, f"{out}.md", editable)
    # write bibtex file to disk
    compile_bibtex(data, f"{out}.bib")

def compile_bibtex(data, out):
    references = []
    # Read references form disk
    for ref in data["references"]:
        filepath = REFERENCE_PATH.format(id=ref)
        with open(filepath, 'r', encoding="utf-8") as f:
            references.append(f.read())
    # Merge into a single string
    bibtex = "\n".join(references)
    # Write a single bibtex file back to disk
    with open(out, 'w', encoding="utf-8") as f:
        f.write(bibtex)

def compile_markdown(data, out, editable):
    # create a copy of the data for the template
    context = data.copy()
    context["editable"] = editable
    # sort glossary
    context["glossary"] = sorted(context["glossary"], key = lambda x: x['term'].lower())
    # todo: implement automatic creation of history based on git logs?
    context["history"] = "Not available yet"
    # generate uid for each requirement
    for block in context["requirements"]:
        for req in block["requirements"]:
            if "/" not in req['id']:
                # make uid unique if it can be used in multiple categories
                req['uid'] = slugify(block['category']['id'] + "-" + req['id'])
            else:
                req['uid'] = slugify(req['id'])
    # fill the template
    template = read_template()
    markdown = template.render(**context)
    # write markdown file to disk
    with open(out, 'w', encoding="utf-8") as f:
        f.write(markdown)
