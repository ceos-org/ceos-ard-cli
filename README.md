# CEOS-ARD CLI <!-- omit in toc -->

CLI for working with the [CEOS-ARD building blocks and PFSes](https://github.com/ceos-org/ceos-ard).

- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Execute a command](#execute-a-command)
- [Commands](#commands)
  - [`ceos-ard compile`: Compile PFS document to a Markdown file](#ceos-ard-compile-compile-pfs-document-to-a-markdown-file)
  - [`ceos-ard generate`: Create Word/HTML/PDF documents for a single PFS](#ceos-ard-generate-create-wordhtmlpdf-documents-for-a-single-pfs)
  - [`ceos-ard generate-all`: Create Word/HTML/PDF documents for all PFSes](#ceos-ard-generate-all-create-wordhtmlpdf-documents-for-all-pfses)
  - [`ceos-ard validate`: Validate CEOS-ARD components](#ceos-ard-validate-validate-ceos-ard-components)
- [Development](#development)

## Getting Started

In order to make working with CEOS-ARD easier we have developed command-line interface (CLI) tools.

### Installation

You will need to have **Python 3.9** or any later version installed.

For the `generate` and `generate-all` commands you also need the following software installed:

- [pandoc](https://pandoc.org/) v3.6.2 (for Word + HTML generation)
- [pandoc-crossref](https://github.com/lierdakil/pandoc-crossref) [v0.3.18.1a](https://github.com/lierdakil/pandoc-crossref/releases/tag/v0.3.18.1a) or later (for table/image/section references)

> ![NOTE]
> The following command doesn't work yet as the package as not been published on pypi yet.
> Please continue with the [Development](#development) instructions for now.

Run `pip install ceos-ard-cli` in the CLI to install the tool.

Afterwards, we also need to install a browser for PDF rendering: `playwright install chromium --with-deps`

### Execute a command

After the installation you should be able to run the following command: `ceos-ard`

You should see usage instructions and [available commands](#commands) for the CLI.

## Commands

### `ceos-ard compile`: Compile PFS document to a Markdown file

To compile a PFS document to a Markdown file, run: `ceos-ard compile SR`

The last part is the PFS to create, e.g. `SR` or `SAR-NRB`.

Check `ceos-ard compile --help` for more details.

### `ceos-ard generate`: Create Word/HTML/PDF documents for a single PFS

To create the Word, HTML, and PDF versions of a single PFS, run: `ceos-ard generate SR`

The last part is the PFS to create, e.g. `SR` or `SAR-NRB`.

Check `ceos-ard generate --help` for more details.

### `ceos-ard generate-all`: Create Word/HTML/PDF documents for all PFSes

To create the Word, HTML, and PDF versions for all PFSes, run: `ceos-ard generate-all`

Check `ceos-ard generate-all --help` for more details.

### `ceos-ard validate`: Validate CEOS-ARD components

To validate (most of) the building blocks, run: `ceos-ard validate`

Check `ceos-ard validate --help` for more details.

## Development

1. Install the dependencies as indicated in [Installation](#installation)
2. Fork this repository if you plan to change the code or create pull requests.
3. Clone either your forked repository or this repository, e.g. `git clone https://github.com/ceos-org/ceos-ard-cli`
4. Switch into the newly created folder: `cd ceos-ard-cli`
5. Install this package in development mode: `pip install -e .`
