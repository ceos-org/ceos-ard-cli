import os
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


# The folders the CLI reads files from; ids and @title: references are confined by content_file
CONTENT_FOLDERS = ["assets", "glossary", "pfs", "references", "requirements", "sections", "templates"]


def _is_link(path):
    return os.path.islink(path) or (os.path.lexists(path) and _is_junction(path))


def check_no_symlinks(input_dir):
    # They could lead the documents to files outside of the input folder. Only the content folders are
    # checked: nothing else is read, and e.g. .venv or node_modules are full of links
    input_dir = Path(input_dir)
    found = []
    for folder in CONTENT_FOLDERS:
        folder = input_dir / folder
        if _is_link(folder):
            found.append(folder)
            continue
        for root, dirs, files in os.walk(folder):
            for name in dirs + files:
                path = Path(root, name)
                if _is_link(path):
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
