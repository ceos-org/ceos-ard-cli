from pathlib import Path

from .schema import REQUIREMENT
from .utils.files import FILE_CACHE, get_all_files, get_all_folders
from .utils.pfs import read_pfs
from .utils.template import read_template
from .utils.yaml import read_yaml


def log(id, error=None):
    message = str(error) if error is not None else "OK"
    print(f"- {id}: {message}")


def validate(input_dir):
    input_dir = Path(input_dir).resolve()
    # Validate PFS template
    print("Validating PFS template (basic checks only)")
    error = None
    try:
        # todo: check more, this check is only very high-level jinja-based
        read_template(input_dir)
    except Exception as e:
        error = e
    finally:
        log("templates/template.md", error)

    # Validate all PFS
    # This also validates all files that are used/referenced in the PFS
    print("Validating PFS")
    input_pfs_folder = input_dir / "pfs"
    all_pfs = get_all_folders(input_pfs_folder)
    for folder in all_pfs:
        pfs = folder.stem
        error = None
        try:
            read_pfs(pfs, input_dir)
        except Exception as e:
            error = e
        finally:
            log(pfs, error)

    # todo: check all files, even if unused
    print("Checking for files not referenced by any PFS (none of them gets validated)")
    # Get a list of all files that were read during PFS validation
    used_files = list(FILE_CACHE.keys())
    all_req_files = get_all_files(input_dir / "requirements")
    # Get all files in the glossary, requirements, and sections
    all_files = get_all_files([input_dir / "glossary", input_dir / "sections"])
    all_files.extend(all_req_files)
    # Print all files that are not refernced by any PFS
    for file in all_files:
        filepath = str(file.absolute())
        if filepath not in used_files:
            rel_path = file.relative_to(input_dir)
            print(f"- {rel_path}")

    # Check for duplicate requirement IDs
    print("Checking for duplicate requirement IDs")
    ids = {}
    for file in all_req_files:
        try:
            data = read_yaml(file, REQUIREMENT, input_dir)
            if not isinstance(data, dict):
                continue
            req_id = data.get("id")
            rel_path = file.relative_to(input_dir)
            if not req_id:
                log(rel_path, "missing id")
                continue
            if req_id in ids:
                log(rel_path, f"duplicate id '{req_id}' (also in {ids[req_id]})")
            else:
                ids[req_id] = rel_path
        except Exception as e:
            log(rel_path, e)
