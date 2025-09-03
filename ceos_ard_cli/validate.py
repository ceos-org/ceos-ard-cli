from pathlib import Path

from .utils.files import FILE_CACHE, get_all_files, get_all_folders
from .utils.pfs import read_pfs
from .utils.template import read_template


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
    # Get all files in the glossary, requirements, and sections
    all_files = get_all_files(
        [input_dir / "glossary", input_dir / "requirements", input_dir / "sections"]
    )
    # Print all files that are not refernced by any PFS
    for file in all_files:
        filepath = str(file.absolute())
        if filepath not in used_files:
            rel_path = file.relative_to(input_dir)
            print(f"- {rel_path}")
