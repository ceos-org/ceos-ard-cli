import shutil

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
