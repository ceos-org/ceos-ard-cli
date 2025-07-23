import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

from .compile import compile
from .utils.files import read_file


def generate_all(output, input_dir, self_contained=True, pdf=True, docx=True, pfs_list=None):
    pfs_list = list(pfs_list) if pfs_list is not None else []
    # read all folders from the pfs folder
    input_dir = Path(input_dir or ".")
    input_pfs_folder = input_dir / "pfs"
    errors = 0
    for folder in input_pfs_folder.iterdir():
        if folder.is_dir():
            pfs = folder.stem
            if len(pfs_list) > 0 and pfs not in pfs_list:
                continue
            print(pfs)
            try:
                generate(pfs, output, input_dir, self_contained, pdf, docx,)
            except Exception as e:
                print(f"Error generating {folder}: {e}")
                errors += 1

    return errors


def generate(pfs, output, input_dir, self_contained=True, pdf=True, docx=True):
    input_dir = Path(input_dir or ".")
    output_pfs_folder = (Path(output) / pfs).absolute()

    if docx:
        print("- Generating editable Markdown")
        compile(pfs, output_pfs_folder, input_dir, True)

        print("- Generating Word")
        run_pandoc(output_pfs_folder, "docx", input_dir, self_contained)

    print("- Generating read-only Markdown")
    compile(pfs, output_pfs_folder, input_dir, False)

    print("- Generating HTML")
    run_pandoc(output_pfs_folder, "html", input_dir, self_contained)

    if pdf:
        print("- Generating PDF")
        run_playwright(output_pfs_folder, input_dir)


def run_playwright(out, input_dir):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        absolute_path = Path(f"{out}.html").absolute()
        page.goto(f"file://{absolute_path}")
        page.pdf(
            path=f"{out}.pdf",
            format="A4",
            display_header_footer=True,
            header_template=read_file(f"{input_dir}/templates/template.header.html"),
            footer_template=read_file(f"{input_dir}/templates/template.footer.html"),
        )
        browser.close()


def run_pandoc(out, format, input_dir: Path, self_contained: bool=True):
    cmd = [
        "pandoc",
        f"{out}.md",  # input file
        "-s",  # standalone
        "-o",
        f"{out}.{format}",  # output file
        "-t",
        format,  # output format
        "-F",
        "pandoc-crossref",  # enable cross-references, must be before -C: https://lierdakil.github.io/pandoc-crossref/#citeproc-and-pandoc-crossref
        "-C",  # enable citation processing
        f"--bibliography={out}.bib",  # bibliography file
        "-L",
        "templates/no-sectionnumbers.lua",  # remove section numbers from reference links
        "-L",
        "templates/pagebreak.lua",  # page breaks
        f"--template=templates/template.{format}",  # template
    ]

    if format == "html":
        cmd.append("--mathml")
        if self_contained:
            cmd.append("--embed-resources=true")
    elif format == "docx":
        cmd.append(f"--reference-doc={input_dir}/templates/style.docx")
    else:
        raise ValueError(f"Unsupported format {format}")

    subprocess.run(cmd, cwd=input_dir)
