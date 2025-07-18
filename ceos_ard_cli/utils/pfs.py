import pathlib as path

from ..schema import AUTHORS, PFS_DOCUMENT, REQUIREMENTS
from .yaml import read_yaml


def check_pfs(pfs, input_dir=None):
    base = path.Path(input_dir) if input_dir is not None else path.Path("./pfs")
    if not base.exists():
        raise ValueError(f"PFS base directory {base} does not exist.")
    
    document = base / pfs / "document.yaml"
    if not document.exists():
        raise ValueError(f"PFS document {pfs} does not exist at {document}.")

    requirements = base / pfs / "requirements.yaml"
    if not requirements.exists():
        raise ValueError(f"PFS requirements {pfs} do not exist at {requirements}.")

    authors = base / pfs / "authors.yaml"
    if not authors.exists():
        raise ValueError(f"PFS authors {pfs} do not exist at {authors}.")

    return document, authors, requirements


def read_pfs(pfs, input_dir=None):
    document, authors, requirements = check_pfs(pfs, input_dir=input_dir)
    data = read_yaml(document, PFS_DOCUMENT)
    data["authors"] = read_yaml(authors, AUTHORS)
    data["requirements"] = read_yaml(requirements, REQUIREMENTS)
    return data
