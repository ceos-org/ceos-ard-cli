from pathlib import Path

from .compile import read_data, render_markdown, resolve_refs
from .links import resolve_links, resolve_titles
from .schema import DOCUMENT_SECTION_PATH, DOCUMENT_SECTIONS, REQUIREMENT
from .utils.deprecation import find_deprecated
from .utils.files import FILE_CACHE, fix_path, get_all_files, get_all_folders
from .utils.pfs import read_pfs
from .utils.template import check_template, read_document_section
from .utils.yaml import read_yaml


def log(id, error=None):
    message = str(error) if error is not None else "OK"
    print(f"- {id}: {message}")


def check_rendering(pfs: list[str], input_dir: Path) -> list[str]:
    """Render the read-only and the editable document, failing on undefined variables and missing templates."""
    errors = []
    for editable in (False, True):
        try:
            render_markdown(read_data(pfs, input_dir, warn=False), editable, input_dir, strict=True)
        except Exception as e:
            kind = "editable" if editable else "read-only"
            errors.append(f"template ({kind}): {e}")
    return errors


def validate(input_dir):
    input_dir = Path(input_dir).resolve()
    # Validate PFS template
    print("Validating PFS template")
    error = None
    try:
        check_template(input_dir)
    except Exception as e:
        error = e
    finally:
        log("templates/template.md", error)

    print("Validating document sections")
    for id in DOCUMENT_SECTIONS:
        path = DOCUMENT_SECTION_PATH.format(id=id)
        file = input_dir / path
        error = None
        try:
            if file.is_file():
                read_document_section(file)
            else:
                error = "missing, its text is left out of the documents"
        except Exception as e:
            error = e
        finally:
            log(fix_path(Path(path)), error)

    # Validate all PFS
    # This also validates all files that are used/referenced in the PFS
    print("Validating PFS")
    input_pfs_folder = input_dir / "pfs"
    all_pfs = get_all_folders(input_pfs_folder)
    for folder in all_pfs:
        pfs = folder.stem
        error = None
        deprecated = []
        link_errors = []
        render_errors = []
        try:
            data = read_pfs(pfs, input_dir)
            deprecated = find_deprecated(data)
            # check that all @title: references point to existing building blocks
            link_errors = resolve_titles(data, input_dir)
            # check that all dependencies and sections links can be resolved
            link_errors += resolve_links(resolve_refs(data), input_dir)
            if not link_errors:
                render_errors = check_rendering([pfs], input_dir)
        except Exception as e:
            error = e
        finally:
            log(pfs, error)
            for message in link_errors:
                print(f"  - ERROR: {message}")
            for message in render_errors:
                print(f"  - ERROR: {message}")
            for descriptor in deprecated:
                print(f"  - WARNING: {descriptor} is deprecated")

    # Covers the template's branches for combined documents
    if len(all_pfs) > 1:
        print("Validating a combined PFS of all PFS")
        errors = check_rendering([folder.stem for folder in all_pfs], input_dir)
        log("combined", "; ".join(errors) if errors else None)

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
