from pathlib import Path

from ..schema import PFS_DOCUMENT
from .yaml import read_yaml


def read_pfs(pfs, input_dir: Path):
    base_path = Path(input_dir)
    pfs_folder = base_path / "pfs" / pfs

    if not pfs_folder.exists():
        raise ValueError(f"PFS base directory '{pfs_folder}' does not exist.")

    document = pfs_folder / "document.yaml"
    if not document.exists():
        raise ValueError(f"PFS document '{pfs}' does not exist at '{document}'.")

    data = read_yaml(document, PFS_DOCUMENT, base_path)
    data["id"] = pfs
    return data
