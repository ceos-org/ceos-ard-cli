from pathlib import Path

from ..schema import PFS_DOCUMENT
from .files import content_file, fix_path
from .yaml import read_yaml


def check_content_folder(input_dir):
    if not (Path(input_dir) / "pfs").is_dir():
        raise ValueError(
            f"'{fix_path(input_dir)}' has no 'pfs' folder: run the command in the folder with the CEOS-ARD "
            "building blocks or pass it with --input-dir"
        )


def read_pfs(pfs, input_dir: Path):
    base_path = Path(input_dir)
    # The name of a folder in pfs, not a path that could lead elsewhere
    if not pfs or pfs in (".", "..") or "/" in pfs or "\\" in pfs:
        raise ValueError(f"Invalid PFS '{pfs}', expected the name of a folder in 'pfs'")
    pfs_folder = content_file(base_path, f"pfs/{pfs}")

    if not pfs_folder.exists():
        raise ValueError(f"PFS base directory '{pfs_folder}' does not exist.")

    document = pfs_folder / "document.yaml"
    if not document.exists():
        raise ValueError(f"PFS document '{pfs}' does not exist at '{document}'.")

    data = read_yaml(document, PFS_DOCUMENT, base_path)
    data["id"] = pfs
    return data
