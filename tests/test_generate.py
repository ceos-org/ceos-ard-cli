import importlib
import re
import shutil
import zipfile

import pytest

from ceos_ard_cli.generate import generate, pandoc_error, run_pandoc

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

    def compile(*args, **kwargs):
        write(tmp_path / "templates" / "template.html", "$if(title)$\n$body$\n")
        write(target.with_suffix(".md"), "# Title\n")
        write(target.with_suffix(".bib"), "")
        return target

    # the package exports the click command of the same name, not the module
    monkeypatch.setattr(importlib.import_module("ceos_ard_cli.generate"), "compile", compile)
    # from an earlier run, it would look like the result of this one
    write(target.with_suffix(".pdf"), "old")

    with pytest.raises(ValueError, match="html file failed"):
        generate("doc", target, tmp_path, self_contained=False, no_docx=True)

    assert list((tmp_path / "out").iterdir()) == []


@pytest.mark.parametrize(
    ("stderr", "message"),
    [
        (
            (
                "Error running filter C:\\cli\\toc.lua:\n\nattempt to index a nil value\n\n"
                "stack traceback:\n\ttoc.lua:17: in function 'Pandoc'\n"
            ),
            "attempt to index a nil value",
        ),
        ("[WARNING] Something\nError running filter x.lua:\nBroken\n", "Broken"),
        (
            "Error parsing YAML metadata at doc.md:\nYAML parse exception at line 2\n",
            "Error parsing YAML metadata at doc.md: YAML parse exception at line 2",
        ),
        ("", "pandoc failed"),
    ],
)
def test_pandoc_errors_keep_only_the_reason(stderr, message):
    assert pandoc_error(stderr) == message
