import re
from pathlib import Path

from .changelog import parse_yaml
from .utils.git import parse_name_status, run_git

BLOCK_PATTERN = re.compile(r"^(requirements|sections|glossary)/.+\.yaml$")
PFS_PATTERN = re.compile(r"^pfs/[^/]+/document\.yaml$")
TEMPLATE_FILENAME = "_template.yaml"
# keys that can be changed without requiring a new changelog entry
IGNORED_KEYS = ("changes", "history")


def is_building_block(path):
    path = str(path).replace("\\", "/")
    if Path(path).name == TEMPLATE_FILENAME:
        return False
    return bool(BLOCK_PATTERN.match(path) or PFS_PATTERN.match(path))


def strip_ignored(data):
    return {k: v for k, v in data.items() if k not in IGNORED_KEYS}


def count_changes(data):
    changes = data.get("changes")
    return len(changes) if isinstance(changes, list) else 0


def check_file(old_text, new_text):
    old = parse_yaml(old_text) if old_text.strip() else {}
    new = parse_yaml(new_text) if new_text.strip() else {}
    if strip_ignored(old) == strip_ignored(new):
        # only the changes / history have been edited
        return None
    if count_changes(new) > count_changes(old):
        return None
    return "content changed, but no new entry was added to 'changes'"


def changed_files(input_dir, base):
    input_dir = Path(input_dir).resolve()
    merge_base = run_git(["merge-base", base, "HEAD"], input_dir).strip()
    output = run_git(["diff", "--name-status", "-z", "--relative", "--diff-filter=AMRC", merge_base], input_dir)
    files = [(path, None if status.startswith("A") else old) for status, path, old in parse_name_status(output)]
    untracked = run_git(["ls-files", "-z", "--others", "--exclude-standard"], input_dir)
    files += [(path, None) for path in untracked.split("\0") if path]
    return merge_base, files


def check_changes(input_dir, base):
    input_dir = Path(input_dir).resolve()
    merge_base, files = changed_files(input_dir, base)
    errors = []
    checked = 0
    for path, old_path in files:
        if not is_building_block(path):
            continue
        checked += 1
        file = input_dir / path
        new_text = file.read_text(encoding="utf-8") if file.is_file() else ""
        old_text = ""
        if old_path is not None:
            # the ./ prefix makes the path relative to the current working directory
            old_text = run_git(["show", f"{merge_base}:./{old_path}"], input_dir)
        try:
            message = check_file(old_text, new_text)
        except Exception as e:
            message = f"failed to parse: {e}"
        print(f"- {path}: {message or 'OK'}")
        if message:
            errors.append(f"{path}: {message}")
    return errors, checked
