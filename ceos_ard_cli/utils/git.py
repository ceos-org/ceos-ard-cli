import subprocess


def run_git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def read_objects(names, cwd):
    """Read the given objects (e.g. blob ids or `<rev>:<path>`), None for objects that don't exist."""
    if not names:
        return {}
    request = "".join(f"{name}\n" for name in names).encode("utf-8")
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=cwd, input=request, capture_output=True)
    if result.returncode != 0:
        raise ValueError(f"git cat-file failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    out = result.stdout
    objects = {}
    pos = 0
    # the responses are in the order of the requests
    for name in names:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if len(header) < 3:
            objects[name] = None
            continue
        size = int(header[2])
        objects[name] = out[pos : pos + size].decode("utf-8")
        pos += size + 1
    return objects
