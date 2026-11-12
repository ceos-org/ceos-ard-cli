# CEOS-ARD CLI <!-- omit in toc -->

Validates the [CEOS-ARD building blocks](https://github.com/ceos-org/ceos-ard) and generates the PFS documents from them as HTML, Word and PDF.

> [!TIP]
> Most people won't need to install this tool.
> The [CEOS-ARD Editor](https://editor.ceos-ard.moregeo.it) edits the building blocks and generates the documents in the browser.

- [Getting started](#getting-started)
  - [Install](#install)
  - [Run](#run)
  - [GitHub Actions](#github-actions)
- [Commands](#commands)
  - [`generate`](#generate)
  - [`generate-all`](#generate-all)
  - [`compile`](#compile)
  - [`validate`](#validate)
  - [`check-changes`](#check-changes)
- [Document history](#document-history)
- [Content rules](#content-rules)
- [Templates](#templates)
- [Development](#development)

## Getting started

### Install

The CLI runs in a [Pixi](https://pixi.sh/) environment, which provides the versions of Python, pandoc and pandoc-crossref that it is tested with. Other setups are not supported.

1. [Install Pixi](https://pixi.sh/latest/#installation). The single command in the "Installation" section is enough.
2. Clone the CLI and the building blocks next to each other:
   ```bash
   git clone https://github.com/ceos-org/ceos-ard-cli
   git clone https://github.com/ceos-org/ceos-ard
   ```
3. Install the CLI:
   ```bash
   cd ceos-ard-cli
   pixi install
   pixi run install-browser  # only needed for PDFs
   ```

### Run

In the `ceos-ard-cli` folder:

```bash
pixi shell                    # activates the environment
cd ../ceos-ard                # the folder with the building blocks
ceos-ard generate-all -o build
```

Add `--pdf` to skip the PDFs if you didn't install the browser.

### GitHub Actions

The repository provides an action that installs the CLI with the pandoc, pandoc-crossref and Python versions that the release locks:

```yaml
- uses: ceos-org/ceos-ard-cli@v0.8.0
  with:
    browser: false # optional, skips the browser that the PDF generation needs
    requirements-file: requirements.txt # optional, fails unless it requires the same CLI version
```

The [CEOS-ARD Editor](https://editor.ceos-ard.moregeo.it) uses the CLI version in the `requirements.txt` of the content repository,
so pass it as `requirements-file` to generate the documents with the same version (required with `~=` or `==`).

## Commands

| Command | What it does |
| --- | --- |
| [`ceos-ard generate`](#generate) | Creates the HTML, Word and PDF documents of a PFS |
| [`ceos-ard generate-all`](#generate-all) | Creates the documents of all PFSes |
| [`ceos-ard compile`](#compile) | Creates only the Markdown file of a PFS |
| [`ceos-ard validate`](#validate) | Checks the building blocks |
| [`ceos-ard check-changes`](#check-changes) | Checks that changed building blocks have a changelog entry |

All commands read the building blocks from the current folder. Pass `-i <folder>` to read them from another folder.
`ceos-ard <command> --help` lists all options.

### `generate`

```bash
ceos-ard generate SR
```

Creates `SR.html`, `SR.docx` and `SR.pdf` for the PFS in `pfs/SR`, together with the intermediate `SR.md` and `SR.bib`.

| Option | Effect |
| --- | --- |
| `-o`, `--output` | Output file without file extension, e.g. `-o build/SR`. Defaults to the name of the PFS. |
| `--pdf` | **Skips** the PDF |
| `--docx` | **Skips** the Word document |
| `-s`, `--self-contained` | Embeds images and styles into the HTML file |
| `-r`, `--stable` | Removes the `-draft` suffix from the version and adds the version to the file name, e.g. `SR-v1.0.0.html` |
| `--id`, `--title`, `--version`, `--pfs-type` | Override the metadata of the document |
| `--history`, `--patch-changes`, `--github-repo` | See [Document history](#document-history) |

The HTML document is always created.

**Combined documents.** Several PFSes are merged into a single document:

```bash
ceos-ard generate NRB POL ORB GSLC -o build/Combined-SAR --id SAR --title "Combined Synthetic Aperture Radar" --pfs-type SAR
```

### `generate-all`

```bash
ceos-ard generate-all -o build
```

Runs `generate` for every PFS in the `pfs` folder and writes the documents to the given folder.
Pass `-p <PFS>` (repeatable) to limit it to some of them.
`--pdf`, `--docx`, `--self-contained`, `--stable` and the options for the document history work as for `generate`.

### `compile`

```bash
ceos-ard compile SR
```

Creates only the Markdown file (`SR.md`) and the bibliography (`SR.bib`) that the documents are generated from.

Like `generate`, it also copies the `assets` folder next to the output file and removes all other files from that copy.

| Option | Effect |
| --- | --- |
| `-o`, `--output` | Output file without file extension |
| `-e`, `--editable` | Adds an "Assessment" section to the requirements, as in the Word documents |
| `-r`, `--stable` | As for `generate` |
| `--debug` | Writes the data of the template as `SR.debug.json` and shows stack traces |

### `validate`

```bash
ceos-ard validate
```

Checks the template, the document sections, all PFSes with the building blocks they use, and the IDs of the requirements.
It also lists the building blocks that no PFS uses.

If pandoc is available, the content is checked as well (see [Content rules](#content-rules)), as `generate` does.

### `check-changes`

```bash
ceos-ard check-changes --base main
```

Fails if a building block was changed without a new entry in its `changes`. Made for CI, requires git.

- The working tree is compared against the merge base of the given git ref and `HEAD`.
- Files that only differ in `changes` or `history` need no new entry.

## Document history

The documents can list what changed between the releases of a PFS. This is off by default, as it needs the git history and the releases:

```bash
ceos-ard generate ST --history --stable
```

**Requirements**

- The input folder is a git checkout with the full history and the release tags, e.g. `fetch-depth: 0` for `actions/checkout`, or `git fetch --tags` locally.
- The releases are read from GitHub (`ceos-org/ceos-ard`, or the repository given with `--github-repo`). Set the `GITHUB_TOKEN` environment variable to avoid rate limits.

**What is listed**

- The `changes` of the PFS document and of all building blocks that the PFS uses, as one table per version with one row per building block.
- Versions are the GitHub releases of the PFS (tags `<PFS>-v<major>.<minor>.<patch>`). Draft releases and pre-releases are ignored.
- Only the versions back to the previous major version. If older versions exist, the document history refers to them.
- Only minor and major changes. Pass `--patch-changes` to also list patch-level (editorial) changes; they always count for the change level of a version.
- For each release, only the building blocks that were part of the PFS in that release, including their glossary terms. Renamed files are followed, and deleted ones are read from the release tag.
- Changes that are not released yet, under the draft version, together with the next version number they suggest.

**How changes are assigned to releases**

Releases are created from `main`. A change belongs to a release if the commit that merged it into `main` is an ancestor of the release tag.
Edited changes and changes in renamed files keep their original commit.

**Special cases**

- If `HEAD` has a release tag for the PFS, its version must match the version of the PFS document.
- A PFS without any release has no document history.
- Combined documents never have a document history.

## Content rules

The building blocks are written by many people, so the CLI limits what their content can do.
Content that breaks a rule fails `generate` and `validate` with a list of all problems and the building block each one is in.

**Links** must

- use one of the schemes `http`, `https`, `mailto`, `ftp`, `ftps`, `sftp` or `s3`,
- point to an anchor (e.g. `#sec:x`), or
- point to an existing file in the `assets` folder, the only folder that is published with the documents.

This also applies to the bibliography, e.g. `url` fields. A link like `www.example.com` without `https://` is refused.

**Images** must be existing files in the `assets` folder or `data:` URIs.

**Not allowed**

- Raw HTML and other raw output (e.g. ` ```{=html} `), except for HTML comments.
- Attributes other than `width` and `height` (e.g. `{width=50%}` on an image), and `label`, `columns` and `widths`, which the template uses.
- Metadata other than the front matter of `template.md`, so the content can't add e.g. `css`.
- IDs and `@title:` references that point outside of the input folder.
- Symbolic links in the input folder. Only top-level folders that start with a dot (e.g. `.venv`) and `node_modules` may contain links.

**While generating**

- The Markdown template is rendered in Jinja's sandbox, so it can't reach Python internals or change the data.
- Only the pandoc Lua filters of the CLI are used, not filters from the input folder.
- Chromium renders the PDF without JavaScript and only loads files from the output folder.

## Templates

The layout of the documents is part of the CLI, see the [templates](ceos_ard_cli/templates) folder:
the Markdown template, the pandoc templates for HTML and Word, and the header and footer of the PDF.

- A file with the same name in the `templates` folder of the input folder replaces the built-in one.
  Replaced HTML, Word and PDF templates are trusted and not checked.
- The pandoc Lua filters in the [filters](ceos_ard_cli/filters) folder can't be replaced.
- A `::: {#toc}` div in the Markdown template is replaced by a table of contents of the headings that follow it.

The texts that all PFSes share are Markdown files in `sections/document` of the input folder:

| File | Text |
| --- | --- |
| `draft.md` | Shown at the top of draft versions |
| `status.md` | The document status |
| `definition.md` | The CEOS-ARD definition |
| `introduction.md` | The introduction before the introductory sections of the PFS |

Each file starts with a heading of any level, which becomes the section title, followed by plain Markdown.
The texts follow the [content rules](#content-rules) and can't use template variables.
A missing file leaves its text out of the documents.

## Development

1. Fork and clone the repository, then follow the [installation](#install).
2. Activate the development environment: `pixi shell -e dev`
3. Change the code. The CLI is installed in editable mode, so `ceos-ard` runs your changes.
4. Run the linter, the formatter and the tests: `pixi run -e dev check-all`

Optionally, run `pre-commit install` to lint and format on each commit.
