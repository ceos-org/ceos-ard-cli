import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .changelog import DEFAULT_GITHUB_REPO
from .compile import compile_files, prepare, remove_outputs
from .problems import WARNING, MultipleErrors, Problem, report, to_problems
from .toolchain import BROWSER_MISSING, check_browser, check_tools
from .utils.files import read_file
from .utils.pfs import list_pfs
from .utils.template import FILTERS_DIR, TEMPLATES_DIR, template_file, template_metadata_keys

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


# The fonts of the documents: file name => (weight, style)
FONT_FAMILY = "Carlito"
FONTS = {
    "Carlito-Regular.woff2": ("normal", "normal"),
    "Carlito-Bold.woff2": ("bold", "normal"),
    "Carlito-Italic.woff2": ("normal", "italic"),
    "Carlito-BoldItalic.woff2": ("bold", "italic"),
}


def font_styles(folder: Path | None = None) -> str:
    """The fonts as a style element: embedded, or linked to copies of the files in the `fonts` folder of `folder`."""
    rules = []
    for name, (weight, style) in FONTS.items():
        source = TEMPLATES_DIR / "fonts" / name
        if folder:
            (folder / "fonts").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, folder / "fonts" / name)
            # The license must be distributed with the fonts
            shutil.copyfile(source.with_name("OFL.txt"), folder / "fonts" / "OFL.txt")
            url = f"fonts/{name}"
        else:
            url = "data:font/woff2;base64," + base64.b64encode(source.read_bytes()).decode("ascii")
        rules.append(
            f"@font-face {{ font-family: {FONT_FAMILY}; font-weight: {weight}; font-style: {style}; "
            f"src: url({url}) format('woff2'); }}"
        )
    return "<style>\n" + "\n".join(rules) + "\n</style>\n"


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
    pfs_list: list | None = None,
    stable: bool = False,
    history: bool = False,
    github_repo: str = DEFAULT_GITHUB_REPO,
    patch_changes: bool = False,
    offline: bool = False,
):
    input_dir = Path(input_dir).resolve()
    output = Path(output)
    errors = 0
    for pfs in pfs_list or list_pfs(input_dir):
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
                offline=offline,
            )
        except Exception as e:
            report(f"Error generating {pfs}: {e}", *to_problems(e, input_dir, pfs=pfs))
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
    metadata: dict | None = None,
    history: bool = False,
    github_repo: str = DEFAULT_GITHUB_REPO,
    patch_changes: bool = False,
    offline: bool = False,
):
    if isinstance(pfs, str):
        pfs = [pfs]

    check_tools()
    if not no_pdf:
        check_browser()
    input_dir = Path(input_dir).resolve()
    output = Path(output).resolve()
    history = {"history": history, "github_repo": github_repo, "patch_changes": patch_changes, "offline": offline}

    # Problems of a combined document can't be assigned to one PFS
    label = pfs[0] if len(pfs) == 1 else None
    # Once for the editable and the read-only document
    data, target = prepare(pfs, output, input_dir, stable, metadata)
    try:
        if not no_docx:
            print("- Generating editable Markdown")
            compile_files(data, target, pfs, input_dir, editable=True, **history)

            print("- Generating Word")
            run_pandoc(target, "docx", input_dir, self_contained, pfs=label)

        print("- Generating read-only Markdown")
        compile_files(data, target, pfs, input_dir, editable=False, **history)

        print("- Generating HTML")
        run_pandoc(target, "html", input_dir, self_contained, pfs=label)

        if not no_pdf:
            print("- Generating PDF")
            run_playwright(target, input_dir)
    except Exception:
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
                raise ValueError(BROWSER_MISSING) from e
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


def run_pandoc(out: Path, format: str, input_dir: Path, self_contained: bool = True, pfs: str | None = None):
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
        str(FILTERS_DIR / "bibliography.lua"),  # edit markers for the entries of the bibliography
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
    with tempfile.TemporaryDirectory() as folder:
        if format == "html":
            fonts = Path(folder) / "fonts.html"
            fonts.write_text(font_styles(None if self_contained else Path(out).resolve().parent), encoding="utf-8")
            cmd.append(f"--include-in-header={fonts}")
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
        raise MultipleErrors(f"Generating the {format} file failed:{details}", errors)
    if result.stderr.strip():
        # One per message of pandoc, e.g. [WARNING] ...
        messages = re.split(r"\n(?=\[[A-Z]+\])", result.stderr.strip())
        report(result.stderr.rstrip(), *(Problem(pfs=pfs, severity=WARNING, message=m.strip()) for m in messages))
