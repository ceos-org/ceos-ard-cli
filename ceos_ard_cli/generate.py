import subprocess
from playwright.sync_api import sync_playwright

from pathlib import Path
from .compile import compile
from .utils.files import read_file

def generate_all(out, self_contained = True, pdf = True):
    # read all folders from the pfs folder
    pfs_folder = Path("pfs")
    errors = 0
    for folder in pfs_folder.iterdir():
        if folder.is_dir():
            pfs = folder.stem
            print(pfs)
            try:
                pfs_folder = Path(out) / pfs
                generate(pfs, pfs_folder, self_contained, pdf)
            except Exception as e:
                print(f"Error generating {folder}: {e}")
                errors += 1

    return errors

def generate(pfs, out, self_contained = True, pdf = True):
    print("- Generating editable Markdown")
    compile(pfs, out, True)

    print("- Generating Word")
    run_pandoc(out, "docx", self_contained)

    print("- Generating read-only Markdown")
    compile(pfs, out, False)

    print("- Generating HTML")
    run_pandoc(out, "html", self_contained)

    if pdf:
        print("- Generating PDF")
        run_playwright(out)

def run_playwright(out):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        absolute_path = Path(f"{out}.html").absolute()
        page.goto(f"file://{absolute_path}")
        page.pdf(
            path=f"{out}.pdf",
            format="A4",
            display_header_footer=True,
            header_template=read_file("./templates/template.header.html"),
            footer_template=read_file("./templates/template.footer.html"),
        )
        browser.close()

def run_pandoc(out, format, self_contained = True):
    cmd = [
        "pandoc",
        f"{out}.md", # input file
        "-s", # standalone
        "-o", f"{out}.{format}", # output file
        "-t", format, # output format
        "-F", "pandoc-crossref", # enable cross-references, must be before -C: https://lierdakil.github.io/pandoc-crossref/#citeproc-and-pandoc-crossref
        "-C", # enable citation processing
        f"--bibliography={out}.bib", # bibliography file
        "-L", "templates/no-sectionnumbers.lua", # remove section numbers from reference links
        "-L", "templates/pagebreak.lua", # page breaks
        f"--template=templates/template.{format}", # template
    ]

    if format == "html":
        cmd.append("--mathml")
        if self_contained:
            cmd.append("--embed-resources=true")
    elif format == "docx":
        cmd.append("--reference-doc=templates/style.docx")
    else:
        raise ValueError(f"Unsupported format {format}")

    subprocess.run(cmd)
