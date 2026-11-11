"""Tests for the links filter, which refuses links that are broken in the documents."""

import shutil

import pytest

from ceos_ard_cli.generate import run_pandoc
from ceos_ard_cli.validate import check_content

pytestmark = pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")


def write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def content(tmp_path):
    write(tmp_path / "assets" / "doc.pdf")
    write(tmp_path / "assets" / "my file.pdf")
    write(tmp_path / "requirements" / "README.md")
    return tmp_path


@pytest.mark.parametrize(
    "markdown",
    [
        "[web](https://ceos.org) and [plain](http://ceos.org) and <https://ceos.org>",
        "[upper case](HTTPS://ceos.org) and [mail](mailto:a@b.c)",
        "[ftp](ftp://example.com/x) [ftps](ftps://example.com/x) [sftp](sftp://example.com/x)",
        "[bucket](s3://bucket/key)",
        "[anchor](#sec:x) and [top](#)",
        "[document](assets/doc.pdf) and [same](./assets/doc.pdf)",
        "[page](assets/doc.pdf?page=2#intro) and [encoded](assets/my%20file.pdf)",
    ],
)
def test_allowed(content, markdown):
    assert check_content(markdown, content) is None


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        (
            "[typo](htps://ceos.org)",
            "Links must use one of the schemes http, https, mailto, ftp, ftps, sftp, s3, found",
        ),
        ("[cloud](gs://bucket/key)", "Links must use one of the schemes"),
        ("[x](javascript:alert(1))", "Links must use one of the schemes"),
        ("[x](file:///etc/passwd)", "Links must use one of the schemes"),
        (
            "[site](www.example.com)",
            "Links must point to a file in the assets folder, found 'www.example.com' "
            "(did you mean 'https://www.example.com'?)",
        ),
        ("[site](docs.example.org/page)", "(did you mean 'https://docs.example.org/page'?)"),
        ("[readme](requirements/README.md)", "Links must point to a file in the assets folder"),
        ("[up](../outside.pdf)", "Links must point to a file in the assets folder"),
        ("[up](assets/../requirements/README.md)", "Links must point to a file in the assets folder"),
        ("[root](/etc/passwd)", "Links must point to a file in the assets folder"),
        ("[missing](assets/missing.pdf)", "The linked file doesn't exist: 'assets/missing.pdf'"),
        ("[empty]()", "Links need a target, found one for 'empty'"),
    ],
)
def test_refused(content, markdown, message):
    assert message in (check_content(markdown, content) or "")


def test_no_hint_for_file_names(content):
    assert "did you mean" not in check_content("[x](report.pdf)", content)


@pytest.mark.skipif(not shutil.which("pandoc-crossref"), reason="needs pandoc-crossref")
def test_generation_fails_on_broken_links(content):
    write(content / "templates" / "template.html", "$body$")
    write(content / "out" / "doc.md", "[site](www.example.com)\n")
    write(content / "out" / "doc.bib")

    with pytest.raises(ValueError, match="html file failed: Links must point to a file in the assets folder"):
        run_pandoc(content / "out" / "doc", "html", content, self_contained=False)
