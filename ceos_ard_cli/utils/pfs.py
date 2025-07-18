import pathlib as path

from ..schema import AUTHORS, PFS_DOCUMENT, REQUIREMENTS
from .yaml import read_yaml


def check_pfs(pfs, input_dir: path):
    pfs_folder = path.Path(input_dir) / "pfs" / pfs

    if not pfs_folder.exists():
        raise ValueError(f"PFS base directory {pfs_folder} does not exist.")
    
    document = pfs_folder / "document.yaml"
    if not document.exists():
        raise ValueError(f"PFS document {pfs} does not exist at {document}.")

    requirements = pfs_folder / "requirements.yaml"
    if not requirements.exists():
        raise ValueError(f"PFS requirements {pfs} do not exist at {requirements}.")

    authors = pfs_folder / "authors.yaml"
    if not authors.exists():
        raise ValueError(f"PFS authors {pfs} do not exist at {authors}.")

    return document, authors, requirements


def read_pfs(pfs, input_dir: path):
    document, authors, requirements = check_pfs(pfs, input_dir)

    data = read_yaml(document, PFS_DOCUMENT)
    data["authors"] = read_yaml(authors, AUTHORS)
    data["requirements"] = read_yaml(requirements, REQUIREMENTS)
    return data
