import sys

import click

from .changelog import DEFAULT_GITHUB_REPO
from .check_changes import check_changes as check_changes_
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
    "--stable",
    "-r",
    is_flag=True,
    default=False,
    help="Removes the '-draft' suffix from the version number, e.g. 0.1.0-draft becomes 0.1.0",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enables debugging mode, e.g. outputs a JSON file for debugging purposes and gives a stacktrace",
)
@click.option(
    "--history",
    is_flag=True,
    default=False,
    help="Compiles the document history from the changes of all building blocks, grouped by GitHub release. "
    "Requires network access, a GitHub token can be provided via the GITHUB_TOKEN environment variable.",
)
@click.option(
    "--github-repo",
    default=DEFAULT_GITHUB_REPO,
    show_default=True,
    help="The GitHub repository (owner/name) to read the releases from for the document history",
)
def compile(pfs, output, input_dir, editable, stable, debug, history, github_repo):
    """
    Compiles the Markdown file for the given PFS.
    """
    pfs = list(pfs)
    print(f"CEOS-ARD CLI {__version__} - Compile {' + '.join(pfs)} as Markdown\n")

    if not output:
        output = "-".join(pfs)

    try:
        compile_(
            pfs,
            output,
            input_dir,
            editable=editable,
            stable=stable,
            debug=debug,
            history=history,
            github_repo=github_repo,
        )
    except Exception as e:
        if debug:
            raise e
        else:
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
@click.option("--pdf", is_flag=True, default=False, help="If provided, disables PDF generation")
@click.option("--docx", is_flag=True, default=False, help="If provided, disables Word (docx) generation")
@click.option(
    "--stable",
    "-r",
    is_flag=True,
    default=False,
    help="Removes the '-draft' suffix from the version number, e.g. 0.1.0-draft becomes 0.1.0",
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
@click.option(
    "--history",
    is_flag=True,
    default=False,
    help="Compiles the document history from the changes of all building blocks, grouped by GitHub release. "
    "Requires network access, a GitHub token can be provided via the GITHUB_TOKEN environment variable.",
)
@click.option(
    "--github-repo",
    default=DEFAULT_GITHUB_REPO,
    show_default=True,
    help="The GitHub repository (owner/name) to read the releases from for the document history",
)
def generate(
    pfs, output, input_dir, self_contained, pdf, docx, stable, id, title, version, pfs_type, history, github_repo
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
        generate_(
            pfs,
            output,
            input_dir,
            self_contained,
            pdf,
            docx,
            stable,
            metadata,
            history=history,
            github_repo=github_repo,
        )
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
@click.option("--pdf", is_flag=True, default=False, help="If provided, disables PDF generation")
@click.option("--docx", is_flag=True, default=False, help="If provided, disables Word (docx) generation")
@click.option(
    "--pfs",
    "-p",
    multiple=True,
    help="PFS to generate, if not specified all PFS will be generated",
)
@click.option(
    "--stable",
    "-r",
    is_flag=True,
    default=False,
    help="Removes the '-draft' suffix from the version number, e.g. 0.1.0-draft becomes 0.1.0",
)
@click.option(
    "--history",
    is_flag=True,
    default=False,
    help="Compiles the document history from the changes of all building blocks, grouped by GitHub release. "
    "Requires network access, a GitHub token can be provided via the GITHUB_TOKEN environment variable.",
)
@click.option(
    "--github-repo",
    default=DEFAULT_GITHUB_REPO,
    show_default=True,
    help="The GitHub repository (owner/name) to read the releases from for the document history",
)
def generate_all(output, input_dir, self_contained, pdf, docx, pfs, stable, history, github_repo):
    """
    Generates all files for all PFS.

    Requires that pandoc is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Generate all PFS\n")
    pfs = list(pfs) if pfs is not None else []
    try:
        errors = generate_all_(
            output,
            input_dir,
            self_contained,
            pdf,
            docx,
            pfs,
            stable,
            history=history,
            github_repo=github_repo,
        )
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


@click.command(name="check-changes")
@click.option(
    "--base",
    "-b",
    required=True,
    help="Git ref to compare against, e.g. main or origin/main",
)
@click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
def check_changes(base, input_dir):
    """
    Checks that all changed building blocks have a new entry in their changes.

    Compares the working tree against the merge base of the given git ref and HEAD.
    Requires that git is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Check changes against {base}\n")
    try:
        errors, checked = check_changes_(input_dir, base)
        print()
        if checked == 0:
            print("No building blocks have been changed")
        elif errors:
            print(f"{len(errors)} of {checked} changed building blocks have no new changelog entry")
            sys.exit(1)
        else:
            print(f"All {checked} changed building blocks have a new changelog entry")
    except Exception as e:
        print(e)
        sys.exit(1)


cli.add_command(compile)
cli.add_command(generate)
cli.add_command(generate_all)
cli.add_command(validate)
cli.add_command(check_changes)

if __name__ == "__main__":
    cli()
