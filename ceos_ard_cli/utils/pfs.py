from pathlib import Path

from ..schema import AUTHORS, PFS_DOCUMENT, REQUIREMENTS
from .yaml import read_yaml


def check_pfs(pfs, base_path: Path):
    pfs_folder = base_path / "pfs" / pfs

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


def read_pfs(pfs, input_dir: Path):
    base_path = Path(input_dir)
    document, authors, requirements = check_pfs(pfs, base_path)

    data = read_yaml(document, PFS_DOCUMENT, base_path)
    data["authors"] = read_yaml(authors, AUTHORS, base_path)
    data["requirements"] = read_yaml(requirements, REQUIREMENTS, base_path)
    return data
