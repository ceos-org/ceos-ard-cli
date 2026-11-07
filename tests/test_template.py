import pytest
from jinja2 import UndefinedError

from ceos_ard_cli.utils.files import fix_path
from ceos_ard_cli.utils.template import (
    TEMPLATES_DIR,
    check_template,
    read_document_section,
    read_document_sections,
    read_template,
    template_file,
)

BUILT_IN = [
    "template.md",
    "template.html",
    "template.docx",
    "style.docx",
    "template.header.html",
    "template.footer.html",
    "no-sectionnumbers.lua",
    "pagebreak.lua",
    "changelog-table.lua",
    "toc.lua",
]


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def context(**overrides):
    data = {
        "id": "SR",
        "title": "Surface Reflectance",
        "type": "Optical",
        "version": "1.0.0",
        "stable": False,
        "combined": False,
        "editable": False,
        "authors": "- Jane Doe",
        "applies_to": "",
        "background": "",
        "glossary": [],
        "requirements": [],
        "introduction": [],
        "annexes": [],
        "changelog": None,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("name", BUILT_IN)
def test_built_in_templates_are_used_without_overrides(tmp_path, name):
    assert template_file(tmp_path, name) == TEMPLATES_DIR / name
    assert (TEMPLATES_DIR / name).is_file()


def test_templates_in_the_input_directory_replace_the_built_in_ones(tmp_path):
    override = write(tmp_path / "templates" / "toc.lua", "-- custom")

    assert template_file(tmp_path, "toc.lua") == override
    assert template_file(tmp_path, "pagebreak.lua") == TEMPLATES_DIR / "pagebreak.lua"


@pytest.mark.parametrize("heading", ["# Document Status", "## Document Status", "### Document Status ##"])
def test_document_sections_take_their_title_from_the_heading(tmp_path, heading):
    file = write(tmp_path / "status.md", f"{heading}\n\nSend revisions to [us](mailto:a@b.c).\n")

    section = read_document_section(file)

    assert section == {
        "filepath": fix_path(file),
        "title": "Document Status",
        "description": "Send revisions to [us](mailto:a@b.c).",
    }


def test_document_sections_must_start_with_a_heading(tmp_path):
    file = write(tmp_path / "status.md", "No heading here.\n")

    with pytest.raises(ValueError, match="must start with a heading"):
        read_document_section(file)


def test_missing_document_sections_are_none(tmp_path):
    write(tmp_path / "sections" / "document" / "definition.md", "## Definition\n\nText")

    sections = read_document_sections(tmp_path)

    assert sections["definition"]["title"] == "Definition"
    assert sections["draft"] is None
    assert sections["status"] is None
    assert sections["introduction"] is None


def test_document_sections_are_rendered_with_edit_links(tmp_path):
    folder = tmp_path / "sections" / "document"
    write(folder / "draft.md", "## Draft Version\n\nThis is a draft.")
    write(folder / "status.md", "## Document Status\n\nSend revisions to us.")
    write(folder / "definition.md", "## The Definition\n\n> ARD are ...")
    write(folder / "introduction.md", "## Introduction\n\nThis section aims to ...")
    sections = read_document_sections(tmp_path)

    markdown = read_template(tmp_path).render(**context(document=sections))

    for id, text in [
        ("draft", "This is a draft."),
        ("status", "Send revisions to us."),
        ("definition", "> ARD are ..."),
        ("introduction", "This section aims to ..."),
    ]:
        section = sections[id]
        assert f"## <!-- edit:{section['filepath']} -->{section['title']}\n" in markdown
        assert text in markdown
    assert "Product Family Specification, Optical, Surface Reflectance" in markdown


def test_stable_documents_have_no_draft_section(tmp_path):
    write(tmp_path / "sections" / "document" / "draft.md", "## Draft Version\n\nThis is a draft.")

    markdown = read_template(tmp_path).render(**context(stable=True, document=read_document_sections(tmp_path)))

    assert "Draft Version" not in markdown


def test_headings_remain_without_document_sections(tmp_path):
    markdown = read_template(tmp_path).render(**context(document=read_document_sections(tmp_path)))

    assert "## Document Status\n" in markdown
    assert "## Introduction\n" in markdown
    assert "Draft Version" not in markdown
    assert "<!-- edit:" not in markdown


def test_the_built_in_template_passes_the_check(tmp_path):
    check_template(tmp_path)


def test_overrides_can_include_their_own_and_the_built_in_templates(tmp_path):
    write(tmp_path / "templates" / "template.md", '~( include "part.md" )~~( include "template.html" )~')
    write(tmp_path / "templates" / "part.md", "Part ~{ title }~\n")

    check_template(tmp_path)
    markdown = read_template(tmp_path).render(title="SR")

    assert markdown.startswith("Part SR")
    assert "$body$" in markdown


@pytest.mark.parametrize(
    "template, message",
    [
        ('~( include "missing.md" )~', "references the missing template missing.md"),
        ('~( if false )~~( import "missing.md" as m )~~( endif )~', "references the missing template missing.md"),
        ("~( include name )~", "by a variable"),
        ("~{ title | unknown }~", "No filter named 'unknown'"),
        ("~( if title )~", "Unexpected end of template"),
    ],
)
def test_broken_templates_fail_the_check(tmp_path, template, message):
    write(tmp_path / "templates" / "template.md", template)

    with pytest.raises(Exception, match=message):
        check_template(tmp_path)


def test_strict_templates_fail_on_undefined_variables(tmp_path):
    write(tmp_path / "templates" / "template.md", "~{ titel }~")

    assert read_template(tmp_path).render(title="SR") == ""
    with pytest.raises(UndefinedError, match="'titel' is undefined"):
        read_template(tmp_path, strict=True).render(title="SR")
