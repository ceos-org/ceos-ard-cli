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
  - [`ceos-ard check-changes`: Check for missing changelog entries](#ceos-ard-check-changes-check-for-missing-changelog-entries)
  - [Document History](#document-history)
- [Development](#development)

## Getting Started

In order to make working with CEOS-ARD easier we have developed command-line interface (CLI) tools.

> [!TIP]
> Most people won't need to install this tool.
> Instead, you can use the [CEOS-ARD Editor](https://editor.ceos-ard.moregeo.it)
> to edit and/or generate the CEOS-ARD PFS documents.

### Installation

[Pixi](https://pixi.sh/) is a modern package management tool that handles both conda and PyPI dependencies.

1. Install Pixi by following the [installation instructions](https://pixi.sh/latest/#installation) (don't follow the "Get Started" instructions, you only need to run the single command provided in the "Installation" section).
2. Clone this repository and the ceos-ard repository:
   - `git clone https://github.com/ceos-org/ceos-ard`
   - `git clone https://github.com/ceos-org/ceos-ard-cli`
3. Navigate to the directory: `cd ceos-ard-cli`
4. Install dependencies: `pixi install`
5. Install browser for PDF rendering: `pixi run install-browser`

### Run the CLI

1. Run `pixi shell`
2. Switch into the folder that contains the contents of the `ceos-ard` repository: `cd ../ceos-ard`
3. Run `ceos-ard` with the command you want to execute, e.g. `ceos-ard generate-all -o build`

See the [available commands](#commands) for further details.

## Commands

### `ceos-ard compile`: Compile PFS document to a Markdown file

To compile a PFS document to a Markdown file, run:

- With Pixi: `ceos-ard compile SR`
- With traditional setup: `ceos-ard compile SR`

The last part is the PFS to create, e.g. `SR` or `NRB`.

Check `ceos-ard compile --help` (or `ceos-ard compile --help`) for more details.

### `ceos-ard generate`: Create Word/HTML/PDF documents for a single PFS

To create the Word, HTML, and PDF versions of a single PFS, run:

- With Pixi: `ceos-ard generate SR`
- With traditional setup: `ceos-ard generate SR`

The last part is the PFS to create, e.g. `SR` or `NRB`.

To create a combined PFS, e.g. SAR, the following command can be used:
`ceos-ard generate NRB POL ORB GSLC -o ../ceos-ard/build/Combined-SAR -i ../ceos-ard --title="Combined Synthetic Aperture Radar" --pfs-type="SAR" --id="SAR"`

By default, HTML, PDF, and Word documents are generated.
Pass `--pdf` to skip the PDF output and/or `--docx` to skip the Word output; the HTML version is always generated.

Check `ceos-ard generate --help` (or `ceos-ard generate --help`) for more details.

### `ceos-ard generate-all`: Create Word/HTML/PDF documents for all PFSes

To create the Word, HTML, and PDF versions for all PFSes, run:

- With Pixi: `ceos-ard generate-all`
- With traditional setup: `ceos-ard generate-all`

As with `ceos-ard generate`, pass `--pdf` and/or `--docx` to skip the PDF and/or Word outputs.

Check `ceos-ard generate-all --help` (or `ceos-ard generate-all --help`) for more details.

### `ceos-ard validate`: Validate CEOS-ARD components

To validate (most of) the building blocks, run:

- With Pixi: `ceos-ard validate`
- With traditional setup: `ceos-ard validate`

Check `ceos-ard validate --help` (or `ceos-ard validate --help`) for more details.

### `ceos-ard check-changes`: Check for missing changelog entries

To check that all building blocks that have been changed compared to a git branch have a new entry in their `changes`, run:

- With Pixi: `ceos-ard check-changes --base main`
- With traditional setup: `ceos-ard check-changes --base main`

The working tree is compared against the merge base of the given git ref and `HEAD`.
Files that only differ in `changes` or `history` don't need a new entry.
Requires that git is installed. The command exits with a non-zero exit code if entries are missing, so it can be used in CI.

Check `ceos-ard check-changes --help` for more details.

### Document History

By default, the generated documents don't include the document history as compiling it requires the git history and network access.
Pass `--history` to `ceos-ard compile`, `ceos-ard generate`, or `ceos-ard generate-all` to compile it, e.g. `ceos-ard generate ST --history --stable`.
The input directory must be a git checkout with the full history and the release tags (e.g. `fetch-depth: 0` for `actions/checkout`, or `git fetch --tags` locally).

The document history is compiled from the `changes` of the PFS document and of all building blocks that are used by the PFS.
The changes are grouped by the GitHub releases of the PFS (tags `<PFS>-v<major>.<minor>.<patch>`), draft releases and pre-releases are ignored.
As releases are always created from main, a change is part of a release if the commit that merged it into main
(the first commit in the first-parent history of `HEAD` that contains the change) is an ancestor of the release tag.
Edited changes and changes in renamed files keep their original commit.
Changes that are not part of a release are listed for the draft version, together with the next version number that the changes suggest.
This also applies if the version of the PFS document has been released already.
Only the changes back to the previous major version are listed.
For each of these releases, only the changes of building blocks that were part of the PFS in that release are listed,
including the glossary terms that were referenced by them and following renamed files.
Building blocks that have been deleted since are read from the release tag.

If `HEAD` has a release tag for the PFS, its version must match the version of the PFS document.

If no previous release exists on GitHub, no document history is generated.
Combined documents never include a document history.

The history is rendered as a table per version with one row per building block (document first, then sections, requirements and glossary terms in document order), listing its changes from the oldest to the newest and the highest change level. As Markdown tables can't contain lists or multiple paragraphs, the template emits the rows as fenced divs and the pandoc Lua filter `templates/changelog-table.lua` from the `ceos-ard` repository converts them into a table. The filter is only loaded if the file exists.

The releases are read from the GitHub repository `ceos-org/ceos-ard`, which can be changed with `--github-repo`.
A GitHub token can be provided through the `GITHUB_TOKEN` environment variable to avoid rate limits.

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
