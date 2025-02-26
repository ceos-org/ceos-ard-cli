from pathlib import Path

FILE_CACHE = {}

def read_file(file):
    filepath = Path(file)
    key = str(filepath.absolute())
    if key in FILE_CACHE:
        return FILE_CACHE[key]

    with open(filepath, 'r', encoding="utf-8") as f:
        content = f.read()
        FILE_CACHE[key] = content
        return content

def write_file(file, content):
    with open(file, 'w', encoding="utf-8") as f:
        return f.write(content)

def get_all_folders(folder, deep = True):
    folders = []
    for f in Path(folder).iterdir():
        if f.is_dir():
            folders.append(f)
            if deep:
                folders += get_all_folders(f)

    return folders

def get_all_files(folder, ext = '.yaml', deep = True):
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
