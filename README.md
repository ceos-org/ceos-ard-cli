# CEOS-ARD CLI <!-- omit in toc -->

CLI for working with the [CEOS-ARD building blocks and PFSes](https://github.com/ceos-org/ceos-ard).

- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Run the CLI](#run-the-cli)
- [Commands](#commands)
  - [`ceos-ard compile`: Compile PFS document to a Markdown file](#ceos-ard-compile-compile-pfs-document-to-a-markdown-file)
  - [`ceos-ard generate`: Create Word/HTML/PDF documents for a single PFS](#ceos-ard-generate-create-wordhtmlpdf-documents-for-a-single-pfs)
  - [`ceos-ard generate-all`: Create Word/HTML/PDF documents for all PFSes](#ceos-ard-generate-all-create-wordhtmlpdf-documents-for-all-pfses)
  - [`ceos-ard validate`: Validate CEOS-ARD components](#ceos-ard-validate-validate-ceos-ard-components)
- [Development](#development)

## Getting Started

In order to make working with CEOS-ARD easier we have developed command-line interface (CLI) tools.

### Installation

[Pixi](https://pixi.sh/) is a modern package management tool that handles both conda and PyPI dependencies.

1. Install Pixi by following the [installation instructions](https://pixi.sh/latest/#installation)
2. Clone this repository: `git clone https://github.com/ceos-org/ceos-ard-cli`
3. Navigate to the directory: `cd ceos-ard-cli`
4. Install dependencies: `pixi install`
5. Install browser for PDF rendering: `pixi run install-browser`

### Run the CLI

1. Run `pixi shell`
2. Switch into the folder that contains the contents of the `ceos-ard` repository
3. Run `ceos-ard` with the command you want to execute, e.g. `ceos-ard generate-all -o build`

See the [available commands](#commands) for further details.

## Commands

### `ceos-ard compile`: Compile PFS document to a Markdown file

To compile a PFS document to a Markdown file, run:

- With Pixi: `ceos-ard compile SR`
- With traditional setup: `ceos-ard compile SR`

The last part is the PFS to create, e.g. `SR` or `SAR-NRB`.

Check `ceos-ard compile --help` (or `ceos-ard compile --help`) for more details.

### `ceos-ard generate`: Create Word/HTML/PDF documents for a single PFS

To create the Word, HTML, and PDF versions of a single PFS, run:

- With Pixi: `ceos-ard generate SR`
- With traditional setup: `ceos-ard generate SR`

The last part is the PFS to create, e.g. `SR` or `SAR-NRB`.

To create a combined PFS, e.g. SAR, the following command can be used:
`ceos-ard generate SAR-NRB SAR-POL SAR-ORB SAR-GSLC -o ../ceos-ard-spec/build/ -i ../ceos-ard-spec --docx --title="Combined Synthetic Aperture Radar" --version="1.1" --pfs-type="SAR" --id="SAR"`

Check `ceos-ard generate --help` (or `ceos-ard generate --help`) for more details.

### `ceos-ard generate-all`: Create Word/HTML/PDF documents for all PFSes

To create the Word, HTML, and PDF versions for all PFSes, run:

- With Pixi: `ceos-ard generate-all`
- With traditional setup: `ceos-ard generate-all`

Check `ceos-ard generate-all --help` (or `ceos-ard generate-all --help`) for more details.

### `ceos-ard validate`: Validate CEOS-ARD components

To validate (most of) the building blocks, run:

- With Pixi: `ceos-ard validate`
- With traditional setup: `ceos-ard validate`

Check `ceos-ard validate --help` (or `ceos-ard validate --help`) for more details.

## Development

1. Fork this repository if you plan to change the code or create pull requests.
2. Clone either your forked repository or this repository, e.g. `git clone https://github.com/ceos-org/ceos-ard-cli`
3. Switch into the newly created folder: `cd ceos-ard-cli`
4. Follow the [Installation instructions above](#installation)
5. Install dependencies and set up the development environment: `pixi run -e dev install-dev`
6. Switch into the development envionment: `pixi shell -e dev`
7. You can now run the CLI in development mode as normal.
8. Run the checks (lint, format, tests) through `pixi run check-all`
9. Optionally, you can install pre-commit hooks (`pre-commit install`) to run lint and format automatically for each commit.
