import click
import sys

from .compile import compile as compile_
from .generate import generate as generate_, generate_all as generate_all_
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
@click.argument('pfs', nargs=1)
@click.option('--output', '-o', default=None, help='Output file without file extension, defaults to the name of the given PFS')
@click.option('--editable', '-e', is_flag=True, default=False, help="Adds an 'Assessment' section to the requirements (for editable Word documents)")
def compile(pfs, output, editable):
    """
    Compiles the Markdown file for the given PFS.
    """
    print(f"CEOS-ARD CLI {__version__} - Compile {pfs} as Markdown\n")

    if not output:
        output = pfs

    try:
        compile_(pfs, output, editable)
    except Exception as e:
        print(e)
        sys.exit(1)

@click.command()
@click.argument('pfs', nargs=1)
@click.option('--output', '-o', default=None, help='Output file without file extension, defaults to the name of the given PFS')
@click.option('--self-contained', '-s', is_flag=True, default=False, help='Generate self-contained HTML files')
@click.option('--pdf', is_flag=True, default=True, help='Enable/disable PDF generation')
def generate(pfs, output, self_contained, pdf):
    """
    Generates the Word and HTML files for the given PFS.

    Requires that pandoc is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Generate {pfs}\n")

    if not output:
        output = pfs

    try:
        generate_(pfs, output, self_contained, pdf)
    except Exception as e:
        print(e)
        sys.exit(1)

@click.command()
@click.option('--output', '-o', default="", help='Output folder, defaults to the current folder')
@click.option('--self-contained', '-s', is_flag=True, default=False, help='Generate self-contained HTML files')
@click.option('--pdf', is_flag=True, default=True, help='Enable/disable PDF generation')
def generate_all(output, self_contained, pdf):
    """
    Generates all files for all PFS.

    Requires that pandoc is installed.
    """
    print(f"CEOS-ARD CLI {__version__} - Generate all PFS\n")
    try:
        errors = generate_all_(output, self_contained, pdf)
        print()
        print(f"Done with {errors} errors")
        sys.exit(errors)
    except Exception as e:
        print(e)
        sys.exit(1)

@click.command()
def validate():
    """
    Validates (most of) the building blocks.
    """
    print(f"CEOS-ARD CLI {__version__} - Validate building blocks\n")
    try:
        validate_()
    except Exception as e:
        print(e)
        sys.exit(1)

cli.add_command(compile)
cli.add_command(generate)
cli.add_command(generate_all)
cli.add_command(validate)

if __name__ == '__main__':
    cli()
