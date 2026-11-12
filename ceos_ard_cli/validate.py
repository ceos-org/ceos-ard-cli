import copy
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from .compile import merge_bibtex, read_data, render_markdown
from .generate import pandoc_env, pandoc_errors
from .links import resolve_links, resolve_titles
from .problems import WARNING, Problem, content_problem, deprecation, to_problem
from .schema import DOCUMENT_SECTION_PATH, DOCUMENT_SECTIONS, GLOSSARY, REQUIREMENT, SECTION
from .utils.deprecation import describe, find_deprecated_blocks
from .utils.files import FILE_CACHE, check_no_symlinks, fix_path, get_all_files, get_all_folders
from .utils.template import FILTERS_DIR, check_template, read_document_section, used_document_sections
from .utils.yaml import read_yaml

# The filters that `generate` runs before and after citeproc to refuse content, see `run_pandoc`
SANITIZE_FILTERS = ["sanitize.lua"]
CHECK_FILTERS = ["links.lua"]
CHECK_TIMEOUT = 60

TEMPLATE_PATH = "templates/template.md"


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


def check_rendering(data: dict, input_dir: Path, pfs: str | None = None) -> list[tuple[str, Problem]]:
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
            errors.append((f"template ({kind}): {e}", Problem(pfs=pfs, message=f"template ({kind}): {e}")))
            continue
        # The editable document has all the content of the read-only one, and names the building blocks
        if editable and shutil.which("pandoc"):
            for line in check_content(markdown, input_dir, bibtex):
                errors.append((f"content: {line}", content_problem(line, input_dir, pfs)))
    return errors


def validate(input_dir, out: Callable[[str], None] = print) -> list[Problem]:
    """All problems in the order they were found, `out` gets the text output while validating."""
    input_dir = Path(input_dir).resolve()
    problems = []

    def check(id, error=None, file=None, pfs=None):
        out(f"- {id}: {'OK' if error is None else error}")
        if error is not None:
            problems.append(to_problem(error, input_dir, file, pfs))

    out("Checking for symbolic links")
    try:
        check_no_symlinks(input_dir)
    except Exception as e:
        check("content folder", e)
        # The other checks would read the files the links point to
        return problems
    check("content folder")

    out("Validating PFS template")
    try:
        check_template(input_dir)
    except Exception as e:
        check(TEMPLATE_PATH, e, file=TEMPLATE_PATH)
    else:
        check(TEMPLATE_PATH)

    out("Validating document sections")
    try:
        used = used_document_sections(input_dir)
    except Exception:
        # the template check above reports the problem
        used = set(DOCUMENT_SECTIONS)
    for id in DOCUMENT_SECTIONS:
        path = fix_path(Path(DOCUMENT_SECTION_PATH.format(id=id)))
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
        check(path, error, file=path)

    # Validate all PFS
    # This also validates all files that are used/referenced in the PFS
    out("Validating PFS")
    if not shutil.which("pandoc"):
        message = "pandoc not found: the content is only checked by `generate`"
        out(f"- {message}")
        problems.append(Problem(severity=WARNING, message=message))
    input_pfs_folder = input_dir / "pfs"
    all_pfs = get_all_folders(input_pfs_folder)
    all_read = True
    for folder in all_pfs:
        pfs = folder.stem
        errors = []
        deprecated = []
        try:
            # Read once: reading is by far the slowest part, so the checks below work on copies
            data = read_data([pfs], input_dir, warn=False)
            deprecated = find_deprecated_blocks(data)
            links = copy.deepcopy(data)
            # check that all @title: references point to existing building blocks
            link_errors = resolve_titles(links, input_dir)
            # check that all dependencies and sections links can be resolved
            link_errors += resolve_links(links, input_dir)
            errors = [(message, Problem(pfs=pfs, message=message)) for message in link_errors]
            if not errors:
                errors = check_rendering(data, input_dir, pfs)
        except Exception as e:
            all_read = False
            check(pfs, e, pfs=pfs)
        else:
            check(pfs)
        for text, problem in errors:
            out(f"  - ERROR: {text}")
            problems.append(problem)
        for block in deprecated:
            out(f"  - WARNING: {describe(block)} is deprecated")
            problems.append(deprecation(block, input_dir, pfs))

    out("Checking for files not referenced by any PFS")
    # A PFS that can't be read stops reading at the problem, so its other files would look unused
    if not all_read:
        out("- skipped, as not all PFS could be read")
    # The files that were read during PFS validation
    used_files = set(FILE_CACHE.keys())
    all_req_files = get_all_files(input_dir / "requirements")
    # The requirements are validated by the check for duplicate IDs below
    all_files = [(file, GLOSSARY) for file in get_all_files(input_dir / "glossary")]
    all_files += [(file, SECTION) for file in get_all_files(input_dir / "sections")]
    all_files += [(file, None) for file in all_req_files]
    for file, schema in all_files:
        if str(file.absolute()) in used_files:
            continue
        rel_path = file.relative_to(input_dir)
        # Templates for new building blocks, not meant to be used
        if all_read and file.name != "_template.yaml":
            out(f"- {rel_path}")
            problems.append(Problem(file=fix_path(rel_path), severity=WARNING, message="not referenced by any PFS"))
        if schema is None:
            continue
        try:
            read_yaml(file, schema, input_dir)
        except Exception as e:
            out(f"  - ERROR: {e}" if all_read else f"- {rel_path}: {e}")
            problems.append(to_problem(e, input_dir, file=fix_path(rel_path)))

    out("Checking for duplicate requirement IDs")
    ids = {}
    for file in all_req_files:
        # Before reading, so that a file that can't be read is reported under its own name
        rel_path = file.relative_to(input_dir)
        path = fix_path(rel_path)
        try:
            data = read_yaml(file, REQUIREMENT, input_dir)
            if not isinstance(data, dict):
                continue
            req_id = data.get("id")
            if not req_id:
                check(rel_path, "missing id", file=path)
                continue
            if req_id in ids:
                check(rel_path, f"duplicate id '{req_id}' (also in {ids[req_id]})", file=path)
            else:
                ids[req_id] = path
        except Exception as e:
            check(rel_path, e, file=path)
    return problems
