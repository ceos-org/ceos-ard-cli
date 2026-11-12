import sys

import click

from .changelog import DEFAULT_GITHUB_REPO
from .check_changes import check_changes as check_changes_
from .compile import compile as compile_
from .generate import generate as generate_
from .generate import generate_all as generate_all_
from .utils.pfs import check_input
from .validate import validate as validate_
from .version import __version__


def options(*decorators):
    """Combines options that several commands share into a single decorator."""

    def decorate(command):
        for decorator in reversed(decorators):
            command = decorator(command)
        return command

    return decorate


input_dir_option = click.option(
    "--input-dir",
    "-i",
    default=".",
    help="Input directory for PFS files, defaults to the current folder",
)
output_file_option = click.option(
    "--output",
    "-o",
    default=None,
    help="Output file without file extension, defaults to the name of the given PFS",
)
stable_option = click.option(
    "--stable",
    "-r",
    is_flag=True,
    default=False,
    help="Removes the '-draft' suffix from the version number, e.g. 0.1.0-draft becomes 0.1.0",
)
format_options = options(
    click.option("--self-contained", "-s", is_flag=True, default=False, help="Generate self-contained HTML files"),
    click.option("--pdf", is_flag=True, default=False, help="If provided, disables PDF generation"),
    click.option("--docx", is_flag=True, default=False, help="If provided, disables Word (docx) generation"),
)
history_options = options(
    click.option(
        "--history",
        is_flag=True,
        default=False,
        help="Compiles the document history from the changes of all building blocks, grouped by GitHub release. "
        "Requires a git checkout with the full history and network access, "
        "a GitHub token can be provided via the GITHUB_TOKEN environment variable.",
    ),
    click.option(
        "--github-repo",
        default=DEFAULT_GITHUB_REPO,
        show_default=True,
        help="The GitHub repository (owner/name) to read the releases from for the document history",
    ),
    click.option(
        "--patch-changes",
        is_flag=True,
        default=False,
        help="Also lists the patch-level (editorial) changes in the document history",
    ),
)


def fail(error):
    print(error)
    sys.exit(1)


@click.group()
@click.version_option(version=__version__)
def cli():
    """
    The CEOS ARD CLI.
    """
    pass


@click.command()
@click.argument("pfs", nargs=-1, required=True)
@output_file_option
@input_dir_option
@click.option(
    "--editable",
    "-e",
    is_flag=True,
    default=False,
    help="Adds an 'Assessment' section to the requirements (for editable Word documents)",
)
@stable_option
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enables debugging mode, e.g. outputs a JSON file for debugging purposes and gives a stacktrace",
)
@history_options
def compile(pfs, output, input_dir, editable, stable, debug, **history):
    """
    Compiles the Markdown file for the given PFS.
    """
    pfs = list(pfs)
    print(f"CEOS-ARD CLI {__version__} - Compile {' + '.join(pfs)} as Markdown\n")

    try:
        check_input(input_dir, pfs)
        compile_(pfs, output or "-".join(pfs), input_dir, editable=editable, stable=stable, debug=debug, **history)
    except Exception as e:
        if debug:
            raise
        fail(e)


@click.command()
@click.argument("pfs", nargs=-1, required=True)
@output_file_option
@input_dir_option
@format_options
@stable_option
@click.option("--id", default=None, help="Overrides the ID of the document")
@click.option("--title", default=None, help="Overrides the title of the document")
@click.option("--version", default=None, help="Overrides the version number of the document")
@click.option("--pfs-type", default=None, help="Overrides the PFS type of the document")
@history_options
def generate(pfs, output, input_dir, self_contained, pdf, docx, stable, id, title, version, pfs_type, **history):
    """
    Generates the Word and HTML files for the given PFS.

    Requires that pandoc is installed.
    """
    pfs = list(pfs)
    print(f"CEOS-ARD CLI {__version__} - Generate {' + '.join(pfs)}\n")

    metadata = {"id": id, "title": title, "version": version, "type": pfs_type}
    output = output or id or "-".join(pfs)
    try:
        check_input(input_dir, pfs)
        generate_(pfs, output, input_dir, self_contained, pdf, docx, stable, metadata, **history)
    except Exception as e:
        fail(e)


@click.command()
@click.option(
    "--output",
    "-o",
    default=".",
    help="Output directory for PFS files, defaults to the current folder",
)
@input_dir_option
@format_options
@click.option(
    "--pfs",
    "-p",
    multiple=True,
    help="PFS to generate, if not specified all PFS will be generated",
)
@stable_option
@history_options
def generate_all(output, input_dir, self_contained, pdf, docx, pfs, stable, **history):
    """
    Generates all files for all PFS.

    Requires that pandoc is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Generate all PFS\n")
    try:
        check_input(input_dir, pfs)
        errors = generate_all_(output, input_dir, self_contained, pdf, docx, list(pfs), stable, **history)
    except Exception as e:
        fail(e)
    print()
    print(f"Done with {errors} errors")
    sys.exit(1 if errors else 0)


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
        errors = validate_(input_dir)
    except Exception as e:
        print(e)
        sys.exit(1)
    if errors:
        print(f"\nFound {errors} error(s)")
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
