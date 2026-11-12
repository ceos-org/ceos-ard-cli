import copy
import shutil
import subprocess
import tempfile
from pathlib import Path

from .compile import merge_bibtex, read_data, render_markdown
from .generate import pandoc_env, pandoc_errors
from .links import resolve_links, resolve_titles
from .schema import DOCUMENT_SECTION_PATH, DOCUMENT_SECTIONS, REQUIREMENT
from .utils.deprecation import find_deprecated
from .utils.files import FILE_CACHE, check_no_symlinks, fix_path, get_all_files, get_all_folders
from .utils.template import FILTERS_DIR, check_template, read_document_section, used_document_sections
from .utils.yaml import read_yaml

# The filters that `generate` runs before and after citeproc to refuse content, see `run_pandoc`
SANITIZE_FILTERS = ["sanitize.lua"]
CHECK_FILTERS = ["links.lua"]
CHECK_TIMEOUT = 60


def log(id, error=None) -> bool:
    message = str(error) if error is not None else "OK"
    print(f"- {id}: {message}")
    return error is not None


def check_content(markdown: str, input_dir: Path, bibtex: str = "") -> list[str]:
    """The problems the check filters find in a document, parsed by pandoc as `generate` does,
    including the links that citeproc creates from the bibliography."""
    with tempfile.TemporaryDirectory() as folder:
        bibliography = Path(folder) / "references.bib"
        bibliography.write_text(bibtex, encoding="utf-8")
        args = [arg for name in SANITIZE_FILTERS for arg in ("-L", str(FILTERS_DIR / name))]
        args += ["-C", f"--bibliography={bibliography}"]
        args += [arg for name in CHECK_FILTERS for arg in ("-L", str(FILTERS_DIR / name))]
        return _run_pandoc(args, markdown, input_dir)


def _run_pandoc(args: list[str], markdown: str, input_dir: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "native", *args],
            input=markdown,
            # The filters resolve relative paths from the input folder, as in `generate`
            cwd=input_dir,
            env=pandoc_env(input_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CHECK_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return [f"pandoc took longer than {CHECK_TIMEOUT} seconds"]
    return [] if result.returncode == 0 else pandoc_errors(result.stderr)


def check_rendering(data: dict, input_dir: Path) -> list[str]:
    """Render the read-only and the editable document, failing on undefined variables, missing templates and
    content that the check filters refuse."""
    errors = []
    bibtex = merge_bibtex(data, input_dir)
    for editable in (False, True):
        kind = "editable" if editable else "read-only"
        try:
            # Rendering changes the data, and copying it is much faster than reading it again
            markdown = render_markdown(copy.deepcopy(data), editable, input_dir, strict=True)
        except Exception as e:
            errors.append(f"template ({kind}): {e}")
            continue
        # The editable document has all the content of the read-only one, and names the building blocks
        if editable and shutil.which("pandoc"):
            errors += [f"content: {problem}" for problem in check_content(markdown, input_dir, bibtex)]
    return errors


def validate(input_dir) -> int:
    input_dir = Path(input_dir).resolve()
    errors = 0
    print("Checking for symbolic links")
    error = None
    try:
        check_no_symlinks(input_dir)
    except Exception as e:
        error = e
    finally:
        errors += log("content folder", error)
    if error is not None:
        # The other checks would read the files the links point to
        return errors

    # Validate PFS template
    print("Validating PFS template")
    error = None
    try:
        check_template(input_dir)
    except Exception as e:
        error = e
    finally:
        errors += log("templates/template.md", error)

    print("Validating document sections")
    try:
        used = used_document_sections(input_dir)
    except Exception:
        # the template check above reports the problem
        used = set(DOCUMENT_SECTIONS)
    for id in DOCUMENT_SECTIONS:
        path = DOCUMENT_SECTION_PATH.format(id=id)
        file = input_dir / path
        error = None
        try:
            if file.is_file():
                read_document_section(file)
            elif id in used:
                error = "missing, its text is left out of the documents"
            else:
                error = "missing, not used by the template"
        except Exception as e:
            error = e
        finally:
            errors += log(fix_path(Path(path)), error)

    # Validate all PFS
    # This also validates all files that are used/referenced in the PFS
    print("Validating PFS")
    if not shutil.which("pandoc"):
        print("- pandoc not found: the content is only checked by `generate`")
    input_pfs_folder = input_dir / "pfs"
    all_pfs = get_all_folders(input_pfs_folder)
    for folder in all_pfs:
        pfs = folder.stem
        error = None
        deprecated = []
        link_errors = []
        render_errors = []
        try:
            # Read once: reading is by far the slowest part, so the checks below work on copies
            data = read_data([pfs], input_dir, warn=False)
            deprecated = find_deprecated(data)
            links = copy.deepcopy(data)
            # check that all @title: references point to existing building blocks
            link_errors = resolve_titles(links, input_dir)
            # check that all dependencies and sections links can be resolved
            link_errors += resolve_links(links, input_dir)
            if not link_errors:
                render_errors = check_rendering(data, input_dir)
        except Exception as e:
            error = e
        finally:
            errors += log(pfs, error) + len(link_errors) + len(render_errors)
            for message in link_errors:
                print(f"  - ERROR: {message}")
            for message in render_errors:
                print(f"  - ERROR: {message}")
            for descriptor in deprecated:
                print(f"  - WARNING: {descriptor} is deprecated")

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
        # Before reading, so that a file that can't be read is reported under its own name
        rel_path = file.relative_to(input_dir)
        try:
            data = read_yaml(file, REQUIREMENT, input_dir)
            if not isinstance(data, dict):
                continue
            req_id = data.get("id")
            if not req_id:
                errors += log(rel_path, "missing id")
                continue
            if req_id in ids:
                errors += log(rel_path, f"duplicate id '{req_id}' (also in {ids[req_id]})")
            else:
                ids[req_id] = rel_path
        except Exception as e:
            errors += log(rel_path, e)
    return errors
