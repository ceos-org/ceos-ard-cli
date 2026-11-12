from pathlib import Path

from ..schema import PFS_DOCUMENT
from .files import content_file, fix_path
from .yaml import read_yaml


def check_pfs_name(pfs):
    # The name of a folder in pfs, not a path that could lead elsewhere (e.g. C:x is relative to a drive)
    if not pfs or pfs in (".", "..") or any(character in pfs for character in "/\\:"):
        raise ValueError(f"Invalid PFS '{pfs}', expected the name of a folder in 'pfs'")


def list_pfs(input_dir):
    folder = Path(input_dir) / "pfs"
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))


def check_input(input_dir, pfs=()):
    """Checks the input folder and the names of the given PFS, before anything is written."""
    folder = Path(input_dir) / "pfs"
    if not folder.is_dir():
        raise ValueError(
            f"'{fix_path(input_dir)}' has no 'pfs' folder: run the command in the folder with the CEOS-ARD "
            "building blocks or pass it with --input-dir"
        )
    for name in pfs:
        check_pfs_name(name)
        if not (folder / name).is_dir():
            raise ValueError(f"Unknown PFS '{name}', expected one of: {', '.join(list_pfs(input_dir))}")


def read_pfs(pfs, input_dir: Path):
    base_path = Path(input_dir)
    check_pfs_name(pfs)
    pfs_folder = content_file(base_path, f"pfs/{pfs}")

    if not pfs_folder.exists():
        raise ValueError(f"PFS base directory '{pfs_folder}' does not exist.")

    document = pfs_folder / "document.yaml"
    if not document.exists():
        raise ValueError(f"PFS document '{pfs}' does not exist at '{document}'.")

    data = read_yaml(document, PFS_DOCUMENT, base_path)
    data["id"] = pfs
    return data
