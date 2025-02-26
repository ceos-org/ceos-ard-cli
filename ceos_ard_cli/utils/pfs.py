import pathlib as path

from ..schema import AUTHORS, PFS_DOCUMENT, REQUIREMENTS
from .yaml import read_yaml

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
