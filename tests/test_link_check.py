"""Tests for the links filter, which refuses links and images that are broken in the documents."""

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
    write(tmp_path / "assets" / "logo.png")
    write(tmp_path / "requirements" / "README.md")
    write(tmp_path / "outside.png")
    return tmp_path


def problems(markdown, folder, bibtex=""):
    return "\n".join(check_content(markdown, folder, bibtex))


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
        "![logo](assets/logo.png) and ![inline](data:image/png;base64,AAAA)",
    ],
)
def test_allowed(content, markdown):
    assert check_content(markdown, content) == []


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
        ("![x](outside.png)", "Images must be files in the assets folder, found 'outside.png'"),
        ("![x](../secret)", "Images must be files in the assets folder, found '../secret'"),
        ("![x](/etc/passwd)", "Images must be files in the assets folder"),
        ("![x](https://example.com/tracker.png)", "Images must be files in the assets folder"),
        ("![x](assets/missing.png)", "The image doesn't exist: 'assets/missing.png'"),
    ],
)
def test_refused(content, markdown, message):
    assert message in problems(markdown, content)


def test_no_hint_for_file_names(content):
    assert "did you mean" not in problems("[x](report.pdf)", content)


def test_reports_all_problems_with_their_building_block(content):
    markdown = (
        "## <!-- edit:requirements/a.yaml -->A\n\n[x](www.example.com) and ![y](assets/missing.png)\n\n"
        "<!-- edit:glossary/b.yaml -->\nTerm\n:   See [z](htps://x.org).\n"
    )
    assert check_content(markdown, content) == [
        "requirements/a.yaml: Links must point to a file in the assets folder, found 'www.example.com' "
        "(did you mean 'https://www.example.com'?)",
        "requirements/a.yaml: The image doesn't exist: 'assets/missing.png'",
        "glossary/b.yaml: Links must use one of the schemes http, https, mailto, ftp, ftps, sftp, s3, found 'htps://x.org'",
    ]


def test_without_building_blocks_points_to_validate(content):
    assert check_content("[x](www.example.com)", content)[-1] == (
        "`ceos-ard validate` names the building blocks with these problems"
    )


def test_checks_the_links_of_the_bibliography(content):
    markdown = "---\nnocite: '@*'\n---\n\n## <!-- edit:a.yaml -->A\n\nText\n\n::: {#refs}\n:::\n"
    # citeproc adds https:// to URLs without a scheme, e.g. www.example.com, but keeps a typo
    bibtex = (
        "@misc{typo, title={Typo}, url={htps://x.org}}\n"
        "@misc{domain, title={Domain}, url={www.example.com}}\n"
        "@misc{ok, title={Fine}, url={https://x.org}}\n"
    )
    assert check_content(markdown, content, bibtex) == [
        "bibliography entry 'typo': Links must use one of the schemes http, https, mailto, ftp, ftps, sftp, s3, "
        "found 'htps://x.org'",
    ]


@pytest.mark.skipif(not shutil.which("pandoc-crossref"), reason="needs pandoc-crossref")
def test_generation_fails_on_broken_links_and_images(content):
    write(content / "templates" / "template.html", "$body$")
    write(content / "out" / "doc.md", "[site](www.example.com) ![x](assets/missing.png)\n")
    write(content / "out" / "doc.bib")

    with pytest.raises(ValueError) as error:
        run_pandoc(content / "out" / "doc", "html", content, self_contained=False)

    assert str(error.value) == (
        "Generating the html file failed:\n"
        "- Links must point to a file in the assets folder, found 'www.example.com' "
        "(did you mean 'https://www.example.com'?)\n"
        "- The image doesn't exist: 'assets/missing.png'\n"
        "- `ceos-ard validate` names the building blocks with these problems"
    )
