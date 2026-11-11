import re
import shutil
import zipfile

import pytest

from ceos_ard_cli.generate import run_pandoc

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
