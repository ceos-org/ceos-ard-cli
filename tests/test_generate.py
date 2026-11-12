import importlib
import re
import shutil
import zipfile
from pathlib import Path

import pytest

from ceos_ard_cli.generate import generate, pandoc_errors, run_pandoc

needs_pandoc = pytest.mark.skipif(
    not (shutil.which("pandoc") and shutil.which("pandoc-crossref")), reason="needs pandoc and pandoc-crossref"
)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@needs_pandoc
def test_pandoc_failures_fail_the_generation(tmp_path):
    # A template that pandoc can't compile
    write(tmp_path / "templates" / "template.html", "$if(title)$\n$body$\n")
    write(tmp_path / "out" / "doc.md", "# Title\n")
    write(tmp_path / "out" / "doc.bib", "")

    with pytest.raises(ValueError, match="html file failed"):
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=False)


@needs_pandoc
@pytest.mark.parametrize("format", ["html", "docx"])
def test_toc_lists_the_headings_after_it(tmp_path, format):
    write(tmp_path / "out" / "doc.md", "## Before\n\n::: {#toc}\n:::\n\n## After\n\n### Nested\n")
    write(tmp_path / "out" / "doc.bib", "")

    run_pandoc(tmp_path / "out" / "doc", format, tmp_path, self_contained=False)

    if format == "html":
        html = (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")
        toc = re.search(r'<div id="toc".*?</div>', html, re.S).group(0)
        assert re.findall(r"<a [^>]*>([^<]*)</a>", toc) == ["After", "Nested"]
    else:
        xml = zipfile.ZipFile(tmp_path / "out" / "doc.docx").read("word/document.xml").decode("utf-8")
        toc = re.search(r"<w:sdt>.*?</w:sdt>", xml, re.S).group(0)
        assert re.findall(r"<w:t[^>]*>([^<]*)</w:t>", toc) == ["After", "Nested"]
        # Word only lists the headings in this bookmark when the field is updated
        assert "\\b _TocRange" in toc
        start, end = xml.index('w:name="_TocRange"'), xml.index('<w:bookmarkEnd w:id="999999"/>')
        # The headings themselves, not their entries in the table of contents
        headings = [xml.index(f">{text}<", xml.index("</w:sdt>")) for text in ("After", "Nested")]
        assert start < headings[0] < headings[1] < end
        assert xml.index(">Before<") < start


@needs_pandoc
def test_pandoc_failures_report_the_reason(tmp_path, capfd):
    write(tmp_path / "templates" / "template.html", "$body$")
    write(tmp_path / "out" / "doc.md", "---\ntitle: [unclosed\n---\n\n# Title\n")
    write(tmp_path / "out" / "doc.bib", "")

    with pytest.raises(ValueError, match="html file failed: .*YAML") as error:
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=False)

    assert "\n" not in str(error.value)
    # the reason is in the error, not printed by pandoc out of order
    assert "YAML" not in "".join(capfd.readouterr())


@needs_pandoc
def test_failed_builds_leave_no_files(tmp_path, monkeypatch):
    target = tmp_path / "out" / "doc"

    def compile_files(*args, **kwargs):
        write(tmp_path / "templates" / "template.html", "$if(title)$\n$body$\n")
        write(target.with_suffix(".md"), "# Title\n")
        write(target.with_suffix(".bib"), "")

    module = importlib.import_module("ceos_ard_cli.generate")
    monkeypatch.setattr(module, "prepare", lambda *args, **kwargs: ({}, target))
    monkeypatch.setattr(module, "compile_files", compile_files)
    # the PDF is never printed, so no browser is needed
    monkeypatch.setattr(module, "check_browser", lambda: None)
    # from an earlier run, it would look like the result of this one
    write(target.with_suffix(".pdf"), "old")

    with pytest.raises(ValueError, match="html file failed"):
        generate("doc", target, tmp_path, self_contained=False, no_docx=True)

    assert list((tmp_path / "out").iterdir()) == []


@pytest.mark.parametrize(
    ("stderr", "messages"),
    [
        (
            (
                "Error running filter C:\\cli\\toc.lua:\n\nattempt to index a nil value\n\n"
                "stack traceback:\n\ttoc.lua:17: in function 'Pandoc'\n"
            ),
            ["attempt to index a nil value"],
        ),
        ("[WARNING] Something\nError running filter x.lua:\nBroken\n", ["Broken"]),
        ("Error running filter links.lua:\n\na.yaml: First\nb.yaml: Second\n", ["a.yaml: First", "b.yaml: Second"]),
        (
            "Error parsing YAML metadata at doc.md:\nYAML parse exception at line 2\n",
            ["Error parsing YAML metadata at doc.md: YAML parse exception at line 2"],
        ),
        ("", ["pandoc failed"]),
    ],
)
def test_pandoc_errors_keep_only_the_reasons(stderr, messages):
    assert pandoc_errors(stderr) == messages


@pytest.fixture
def failing_compile(tmp_path, monkeypatch):
    """A compilation that writes the Markdown file and then fails, or fails right away when reading the data."""
    module = importlib.import_module("ceos_ard_cli.compile")
    (tmp_path / "assets").mkdir()

    def fail(*args, **kwargs):
        raise ValueError("broken")

    monkeypatch.setattr(module, "read_data", lambda *args, **kwargs: {"version": "1.0.0"})
    monkeypatch.setattr(module, "compile_markdown", lambda data, out, *args, **kwargs: write(Path(out), "x"))
    monkeypatch.setattr(module, "compile_bibtex", fail)
    return module, fail


@pytest.mark.parametrize("stable, name", [(False, "SR"), (True, "SR-v1.0.0")])
def test_failed_compilations_leave_no_files(tmp_path, failing_compile, stable, name):
    module, _ = failing_compile
    out = tmp_path / "out"
    write(out / "SR.html", "draft")
    write(out / "SR-v1.0.0.html", "stable")
    write(out / f"{name}.pdf", "from an earlier run")

    with pytest.raises(ValueError, match="broken"):
        module.compile("SR", out / "SR", tmp_path, stable=stable)

    remaining = sorted(p.name for p in out.iterdir() if p.is_file())
    assert remaining == (["SR-v1.0.0.html"] if not stable else ["SR.html"])


def test_failed_stable_compilations_keep_all_files_without_a_version(tmp_path, failing_compile, monkeypatch):
    module, fail = failing_compile
    monkeypatch.setattr(module, "read_data", fail)
    write(tmp_path / "out" / "SR.html", "draft")

    with pytest.raises(ValueError, match="broken"):
        module.compile("SR", tmp_path / "out" / "SR", tmp_path, stable=True)

    assert (tmp_path / "out" / "SR.html").is_file()


def test_stable_documents_keep_dots_in_their_name(tmp_path, failing_compile, monkeypatch):
    module, _ = failing_compile
    monkeypatch.setattr(module, "compile_bibtex", lambda *args, **kwargs: None)

    assert module.compile("SR", tmp_path / "out" / "SR-1.5", tmp_path, stable=True).name == "SR-1.5-v1.0.0"


@pytest.mark.parametrize("pfs", ["../requirements", "a/b", "a\\b", "..", "", "C:", "C:x"])
def test_pfs_must_be_a_folder_name(tmp_path, pfs):
    from ceos_ard_cli.utils.pfs import read_pfs

    write(tmp_path / "requirements" / "document.yaml", "title: Secret\n")
    with pytest.raises(ValueError, match="Invalid PFS"):
        read_pfs(pfs, tmp_path)


def test_generating_prepares_the_document_once(tmp_path, monkeypatch):
    module = importlib.import_module("ceos_ard_cli.generate")
    compilation = importlib.import_module("ceos_ard_cli.compile")
    calls = []
    (tmp_path / "assets").mkdir()

    def count(name, result=None):
        return lambda *args, **kwargs: calls.append(name) or result

    monkeypatch.setattr(module, "check_tools", lambda: None)
    monkeypatch.setattr(module, "run_pandoc", count("pandoc"))
    monkeypatch.setattr(compilation, "check_no_symlinks", count("symlinks"))
    monkeypatch.setattr(compilation, "sync_assets", count("assets"))
    monkeypatch.setattr(compilation, "read_data", count("data", {"version": "1.0.0"}))
    monkeypatch.setattr(compilation, "compile_markdown", count("markdown"))
    monkeypatch.setattr(compilation, "compile_bibtex", count("bibtex"))

    generate("SR", tmp_path / "out" / "SR", tmp_path, no_pdf=True)

    assert calls == ["symlinks", "assets", "data", "markdown", "bibtex", "pandoc", "markdown", "bibtex", "pandoc"]


def test_stable_documents_get_a_file_name_for_any_version(tmp_path, failing_compile, monkeypatch):
    module, _ = failing_compile
    # the version of combined documents
    monkeypatch.setattr(module, "read_data", lambda *args, **kwargs: {"version": "n/a"})
    monkeypatch.setattr(module, "compile_bibtex", lambda *args, **kwargs: None)
    write(tmp_path / "out" / "A-B.md", "draft")

    assert module.compile(["A", "B"], tmp_path / "out" / "A-B", tmp_path, stable=True).name == "A-B-vn-a"
    assert (tmp_path / "out" / "A-B.md").read_text(encoding="utf-8") == "draft"
