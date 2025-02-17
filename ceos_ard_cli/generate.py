import subprocess
import weasyprint

from pathlib import Path
from .compile import compile

def generate_all(out, pdf = True):
    # read all folders from the pfs folder
    pfs_folder = Path("pfs")
    errors = 0
    for folder in pfs_folder.iterdir():
        if folder.is_dir():
            pfs = folder.stem
            print(pfs)
            try:
                pfs_folder = Path(out) / pfs
                generate(pfs, pfs_folder, pdf)
            except Exception as e:
                print(f"Error generating {folder}: {e}")
                errors += 1

    return errors

def generate(pfs, out, pdf = True):
    print("- Generating editable Markdown")
    compile(pfs, out, True)

    print("- Generating Word")
    run_pandoc(out, "docx")

    print("- Generating read-only Markdown")
    compile(pfs, out, False)

    print("- Generating HTML")
    run_pandoc(out, "html")

    if pdf:
        print("- Generating PDF")
        weasyprint.HTML(f"{out}.html").write_pdf(f"{out}.pdf")

def run_pandoc(out, format):
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
        cmd.append("--mathml") # alternative: --webtex for image rendering
    elif format == "docx":
        cmd.append("--reference-doc=templates/style.docx")
    else:
        raise ValueError(f"Unsupported format {format}")

    subprocess.run(cmd)
