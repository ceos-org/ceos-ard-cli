import os
import shutil
import stat
from pathlib import Path

FILE_CACHE = {}


def _is_junction(path):
    # Windows junctions are links as well; the same check as os.path.isjunction, which needs Python 3.12.
    # Only Windows has reparse tags (and the constant).
    tag = getattr(os.lstat(path), "st_reparse_tag", None)
    return tag is not None and tag == stat.IO_REPARSE_TAG_MOUNT_POINT


def fix_path(path):
    return str(path).replace("\\", "/")


def content_file(base, relative):
    base = Path(base).resolve()
    file = (base / relative).resolve()
    if not file.is_relative_to(base):
        raise ValueError(f"{relative} is outside of the content folder")
    return file


def check_no_symlinks(input_dir):
    # They could lead the documents to files outside of the input folder: images and other
    # relative paths can point anywhere inside of it, so the whole folder is checked
    input_dir = Path(input_dir)
    found = []
    for root, dirs, files in os.walk(input_dir):
        if Path(root) == input_dir and ".git" in dirs:
            dirs.remove(".git")
        for name in dirs + files:
            path = Path(root, name)
            if os.path.islink(path) or _is_junction(path):
                found.append(path)
    if found:
        paths = ", ".join(str(path.relative_to(input_dir)) for path in found[:5])
        raise ValueError(f"Symbolic links are not supported in the input folder: {paths}")


def read_file(file):
    filepath = Path(file)
    key = str(filepath.absolute())
    if key in FILE_CACHE:
        return FILE_CACHE[key]

    with open(filepath, encoding="utf-8") as f:
        content = f.read()
        FILE_CACHE[key] = content
        return content


def write_file(file, content):
    with open(file, "w", encoding="utf-8") as f:
        return f.write(content)


def get_all_folders(folder, deep=True):
    folders = []
    for f in Path(folder).iterdir():
        if f.is_dir():
            folders.append(f)
            if deep:
                folders += get_all_folders(f)

    return folders


def get_all_files(folder, ext=".yaml", deep=True):
    if isinstance(folder, list):
        files = []
        for f in folder:
            files += get_all_files(f, ext, deep)
        return files

    files = []
    for f in Path(folder).iterdir():
        if f.is_file() and f.name.endswith(ext):
            files.append(f)
        elif f.is_dir() and deep:
            files += get_all_files(f, ext)

    return files


# Marks an assets folder in the output as a copy made by the CLI, which may be purged
ASSETS_MARKER = ".ceos-ard-cli"


def _same_file(source, target):
    if not target.is_file():
        return False
    a, b = source.stat(), target.stat()
    return a.st_size == b.st_size and a.st_mtime_ns == b.st_mtime_ns


def sync_assets(source, target):
    """Make `target` a copy of `source`: copy new and changed files, remove all others."""
    source, target = Path(source), Path(target)
    wanted = {path.relative_to(source) for path in source.rglob("*")} if source.is_dir() else set()
    marker = target / ASSETS_MARKER
    if target.exists() and not marker.is_file():
        # A copy made by an earlier version has no marker, but also no files of its own
        if not target.is_dir() or any(path.relative_to(target) not in wanted for path in target.rglob("*")):
            raise ValueError(
                f"'{fix_path(target)}' was not created by the CLI and its files would be removed: "
                "choose another output folder or remove it"
            )
    target.mkdir(parents=True, exist_ok=True)
    marker.touch()
    # Folders before their files
    for path in sorted(wanted):
        src, dst = source / path, target / path
        if src.is_dir():
            if dst.is_file():
                dst.unlink()
            dst.mkdir(exist_ok=True)
        elif not _same_file(src, dst):
            if dst.is_dir():
                shutil.rmtree(dst)
            shutil.copy2(src, dst)
    # Files before their folders
    for path in sorted(target.rglob("*"), reverse=True):
        if path.relative_to(target) not in wanted and path != marker:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
