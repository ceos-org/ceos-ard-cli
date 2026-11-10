import os
from pathlib import Path

FILE_CACHE = {}
# Windows junctions are links as well, Python < 3.12 can't detect them
_is_junction = getattr(os.path, "isjunction", lambda path: False)


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

    with open(filepath, "r", encoding="utf-8") as f:
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
