import pathlib as path

from jinja2 import Environment
from .schema import AUTHORS, PFS_DOCUMENT, REQUIREMENTS
from .yaml.yaml_util import read_yaml

def check_pfs(pfs):
    document = path.Path(f"./pfs/{pfs}/document.yaml")
    if not document.exists():
        raise ValueError(f"PFS document {pfs} does not exist at {document}.")

    requirements = path.Path(f"./pfs/{pfs}/requirements.yaml")
    if not requirements.exists():
        raise ValueError(f"PFS requirements {pfs} do not exist at {requirements}.")

    authors = path.Path(f"./pfs/{pfs}/authors.yaml")
    if not authors.exists():
        raise ValueError(f"PFS authors {pfs} do not exist at {authors}.")

    return document, authors, requirements

def read_pfs(pfs):
    document, authors, requirements = check_pfs(pfs)
    data = read_yaml(document, PFS_DOCUMENT)
    data['authors'] = read_yaml(authors, AUTHORS)
    data['requirements'] = read_yaml(requirements, REQUIREMENTS)
    return data

def read_template():
    file = path.Path(f"./templates/template.md")
    if not file.exists():
        raise ValueError(f"Template {file} does not exist.")

    with open(file, 'r', encoding="utf-8") as f:
        tpl = f.read()

    env = Environment(
        block_start_string='~(', block_end_string=')~',
        variable_start_string='~{', variable_end_string='}~',
        comment_start_string='~#', comment_end_string='#~',
        trim_blocks=True,
    )
    env.filters['rstrip'] = lambda x: x.rstrip()
    env.filters['slugify'] = slugify
    return env.from_string(tpl)

def slugify(text):
    return text.replace("/", "-")
