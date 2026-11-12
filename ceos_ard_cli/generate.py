import os
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .changelog import DEFAULT_GITHUB_REPO
from .compile import compile, remove_outputs
from .toolchain import check_tools
from .utils.files import read_file
from .utils.template import FILTERS_DIR, template_file, template_metadata_keys

# Chromium only gets the output folder, served from an address that doesn't exist
ORIGIN = "https://ceos-ard.invalid"


def pandoc_errors(stderr: str) -> list[str]:
    """The reasons pandoc failed, without the stack traceback of a filter: one per line of the filter's message."""
    text = stderr.split("stack traceback:")[0]
    # A filter's own message follows the line that names the filter
    _, found, message = text.partition("Error running filter")
    if found:
        return [line.strip() for line in message.partition("\n")[2].splitlines() if line.strip()] or ["pandoc failed"]
    return [" ".join(line.strip() for line in text.splitlines() if line.strip()) or "pandoc failed"]


def pandoc_env(input_dir: Path) -> dict[str, str]:
    """The environment for pandoc, with the metadata that the sanitize filter allows."""
    keys = [*template_metadata_keys(input_dir), "bibliography"]
    return {**os.environ, "CEOS_ARD_METADATA": ",".join(keys)}


def generate_all(
    output: Path | str,
    input_dir: Path | str,
    self_contained: bool = True,
    no_pdf: bool = False,
    no_docx: bool = False,
    pfs_list: list = [],
    stable: bool = False,
    history: bool = False,
    github_repo: str = DEFAULT_GITHUB_REPO,
    patch_changes: bool = False,
):
    # read all folders from the pfs folder
    input_dir = Path(input_dir).resolve()
    input_pfs_folder = input_dir / "pfs"
    output = Path(output)
    errors = 0
    for folder in input_pfs_folder.iterdir():
        if folder.is_dir():
            pfs = folder.stem
            if len(pfs_list) > 0 and pfs not in pfs_list:
                continue
            print(pfs)
            try:
                generate(
                    pfs,
                    output / pfs,
                    input_dir,
                    self_contained,
                    no_pdf,
                    no_docx,
                    stable,
                    history=history,
                    github_repo=github_repo,
                    patch_changes=patch_changes,
                )
            except Exception as e:
                print(f"Error generating {folder}: {e}")
                errors += 1

    return errors


def generate(
    pfs: list[str] | str,
    output: Path | str,
    input_dir: Path | str,
    self_contained: bool = True,
    no_pdf: bool = False,
    no_docx: bool = False,
    stable: bool = False,
    metadata: dict = {},
    history: bool = False,
    github_repo: str = DEFAULT_GITHUB_REPO,
    patch_changes: bool = False,
):
    if isinstance(pfs, str):
        pfs = [pfs]

    check_tools()
    input_dir = Path(input_dir).resolve()
    output = Path(output).resolve()
    options = {
        "stable": stable,
        "metadata": metadata,
        "history": history,
        "github_repo": github_repo,
        "patch_changes": patch_changes,
    }

    target = None
    try:
        if not no_docx:
            print("- Generating editable Markdown")
            target = compile(pfs, output, input_dir, editable=True, **options)

            print("- Generating Word")
            run_pandoc(target, "docx", input_dir, self_contained)

        print("- Generating read-only Markdown")
        target = compile(pfs, output, input_dir, editable=False, **options)

        print("- Generating HTML")
        run_pandoc(target, "html", input_dir, self_contained)

        if not no_pdf:
            print("- Generating PDF")
            run_playwright(target, input_dir)
    except Exception:
        # compile cleans up after its own failures, before the name of the document is known here
        if target is not None:
            remove_outputs(target)
        raise


def local_file(folder: Path, url: str) -> Path | None:
    if not url.startswith(f"{ORIGIN}/"):
        return None
    file = (folder / unquote(urlsplit(url).path).lstrip("/")).resolve()
    return file if file.is_relative_to(folder) and file.is_file() else None


def run_playwright(out: Path, input_dir: Path):
    # Only loaded for PDFs, as it takes a while
    from playwright.sync_api import Error, sync_playwright

    html = Path(f"{out}.html").resolve()
    folder = html.parent

    def route(route):
        file = local_file(folder, route.request.url)
        if file:
            route.fulfill(path=file)
        else:
            route.abort()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error as e:
            if "Executable doesn't exist" in str(e):
                raise ValueError("The browser for the PDF is not installed: run `pixi run install-browser`") from e
            raise
        page = browser.new_page(java_script_enabled=False)
        page.route("**/*", route)
        # Encoded, so that e.g. a # in the file name isn't read as the start of a fragment
        page.goto(f"{ORIGIN}/{quote(html.name)}")
        page.pdf(
            path=f"{out}.pdf",
            format="A4",
            display_header_footer=True,
            header_template=read_file(template_file(input_dir, "template.header.html")),
            footer_template=read_file(template_file(input_dir, "template.footer.html")),
        )
        browser.close()


def run_pandoc(out: Path, format: str, input_dir: Path, self_contained: bool = True):
    cmd = [
        "pandoc",
        f"{out}.md",  # input file
        "-s",  # standalone
        "-o",
        f"{out}.{format}",  # output file
        "-t",
        format,  # output format
        "-L",
        str(FILTERS_DIR / "sanitize.lua"),  # refuse raw output, attributes and metadata, must be first
        "-F",
        "pandoc-crossref",  # enable cross-references, must be before -C: https://lierdakil.github.io/pandoc-crossref/#citeproc-and-pandoc-crossref
        "-C",  # enable citation processing
        f"--bibliography={out}.bib",  # bibliography file
        "-L",
        str(FILTERS_DIR / "links.lua"),  # refuse broken links and images, also the ones from the bibliography
        "-L",
        str(FILTERS_DIR / "no-sectionnumbers.lua"),  # remove section numbers from reference links
        "-L",
        str(FILTERS_DIR / "pagebreak.lua"),  # page breaks
        "-L",
        str(FILTERS_DIR / "changelog-table.lua"),  # document history
        "-L",
        str(FILTERS_DIR / "toc.lua"),  # table of contents
        f"--template={template_file(input_dir, f'template.{format}')}",
    ]

    if format == "html":
        cmd.append("--math-method=mathml")
        if self_contained:
            cmd.append("--embed-resources=true")
    elif format == "docx":
        cmd.append(f"--reference-doc={template_file(input_dir, 'style.docx')}")
    else:
        raise ValueError(f"Unsupported format {format}")

    # Captured, so that the messages appear in order with the progress and without the filters' stack traces
    result = subprocess.run(
        cmd,
        cwd=input_dir,
        env=pandoc_env(input_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        errors = pandoc_errors(result.stderr)
        details = f" {errors[0]}" if len(errors) == 1 else "".join(f"\n- {error}" for error in errors)
        raise ValueError(f"Generating the {format} file failed:{details}")
    if result.stderr.strip():
        print(result.stderr.rstrip())
