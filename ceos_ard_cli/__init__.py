import sys

import click

from .compile import compile as compile_
from .generate import generate as generate_
from .generate import generate_all as generate_all_
from .validate import validate as validate_
from .version import __version__


@click.group()
@click.version_option(version=__version__)
def cli():
    """
    The CEOS ARD CLI.
    """
    pass


@click.command()
@click.argument("pfs", nargs=-1)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file without file extension, defaults to the name of the given PFS",
)
@click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
@click.option(
    "--editable",
    "-e",
    is_flag=True,
    default=False,
    help="Adds an 'Assessment' section to the requirements (for editable Word documents)",
)
@click.option(
    "--json",
    is_flag=True,
    default=False,
    help="Outputs a JSON file for debugging purposes",
)
def compile(pfs, output, input_dir, editable, json):
    """
    Compiles the Markdown file for the given PFS.
    """
    pfs = list(pfs)
    print(f"CEOS-ARD CLI {__version__} - Compile {' + '.join(pfs)} as Markdown\n")

    if not output:
        output = "-".join(pfs)

    try:
        compile_(pfs, output, input_dir, editable=editable, debug=json)
    except Exception as e:
        print(e)
        sys.exit(1)


@click.command()
@click.argument("pfs", nargs=-1)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file without file extension, defaults to the name of the given PFS",
)
@click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
@click.option(
    "--self-contained",
    "-s",
    is_flag=True,
    default=False,
    help="Generate self-contained HTML files",
)
@click.option("--pdf", is_flag=True, default=True, help="Enable/disable PDF generation")
@click.option(
    "--docx", is_flag=True, default=True, help="Enable/disable Word (docx) generation"
)
@click.option(
    "--id",
    default=None,
    help="Overrides the ID of the document",
)
@click.option(
    "--title",
    default=None,
    help="Overrides the title of the document",
)
@click.option(
    "--version",
    default=None,
    help="Overrides the version number of the document",
)
@click.option(
    "--pfs-type",
    default=None,
    help="Overrides the PFS type of the document",
)
def generate(
    pfs, output, input_dir, self_contained, pdf, docx, id, title, version, pfs_type
):
    """
    Generates the Word and HTML files for the given PFS.

    Requires that pandoc is installed.
    """
    pfs = list(pfs)
    print(f"CEOS-ARD CLI {__version__} - Generate {' + '.join(pfs)}\n")

    if not output:
        output = id or "-".join(pfs)

    metadata = {
        "id": id,
        "title": title,
        "version": version,
        "type": pfs_type,
    }

    try:
        generate_(pfs, output, input_dir, self_contained, pdf, docx, metadata)
    except Exception as e:
        print(e)
        sys.exit(1)


@click.command()
@click.option(
    "--output",
    "-o",
    default=".",
    help="Output directory for PFS files, defaults to the current folder",
)
@click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
@click.option(
    "--self-contained",
    "-s",
    is_flag=True,
    default=False,
    help="Generate self-contained HTML files",
)
@click.option("--pdf", is_flag=True, default=True, help="Enable/disable PDF generation")
@click.option(
    "--docx", is_flag=True, default=True, help="Enable/disable Word (docx) generation"
)
@click.option(
    "--pfs",
    "-p",
    multiple=True,
    help="PFS to generate, if not specified all PFS will be generated",
)
def generate_all(output, input_dir, self_contained, pdf, docx, pfs):
    """
    Generates all files for all PFS.

    Requires that pandoc is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Generate all PFS\n")
    pfs = list(pfs) if pfs is not None else []
    try:
        errors = generate_all_(output, input_dir, self_contained, pdf, docx, pfs)
        print()
        print(f"Done with {errors} errors")
        sys.exit(errors)
    except Exception as e:
        print(e)
        sys.exit(1)


@click.command()
@click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
def validate(input_dir):
    """
    Validates (most of) the building blocks.
    """
    print(f"CEOS-ARD CLI {__version__} - Validate building blocks\n")
    try:
        validate_(input_dir)
    except Exception as e:
        print(e)
        sys.exit(1)


cli.add_command(compile)
cli.add_command(generate)
cli.add_command(generate_all)
cli.add_command(validate)

if __name__ == "__main__":
    cli()
