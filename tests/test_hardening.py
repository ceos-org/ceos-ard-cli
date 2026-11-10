"""Tests that content can't run code or reach files outside of the content folder."""

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
class TestPandoc:
    def build(self, tmp_path, markdown):
        write(tmp_path / "templates" / "template.html", "$body$")
        write(tmp_path / "out" / "doc.md", markdown)
        write(tmp_path / "out" / "doc.bib", "")
        write(tmp_path / "assets" / "logo.png", "")
        write(tmp_path / "outside.png", "secret")
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=False)
        return (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")

    def test_ignores_lua_filters_of_the_input_directory(self, tmp_path):
        write(tmp_path / "templates" / "pagebreak.lua", "error('content code ran')")
        write(tmp_path / "templates" / "toc.lua", "error('content code ran')")
        assert "Title" in self.build(tmp_path, "# Title\n")
