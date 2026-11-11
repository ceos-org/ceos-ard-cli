import os
import shutil
import subprocess

import pytest
from jinja2 import UndefinedError

from ceos_ard_cli.utils.files import fix_path
from ceos_ard_cli.utils.template import (
    FILTERS_DIR,
    TEMPLATES_DIR,
    check_template,
    read_document_section,
    read_document_sections,
    read_template,
    table_cell,
    template_file,
    used_document_sections,
)
from ceos_ard_cli.validate import validate

BUILT_IN = [
    "template.md",
    "template.html",
    "template.docx",
    "style.docx",
    "template.header.html",
    "template.footer.html",
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
    override = write(tmp_path / "templates" / "template.html", "$body$")

    assert template_file(tmp_path, "template.html") == override
    assert template_file(tmp_path, "style.docx") == TEMPLATES_DIR / "style.docx"


@pytest.mark.parametrize("heading", ["# Document Status", "## Document Status", "### Document Status ##"])
def test_document_sections_take_their_title_from_the_heading(tmp_path, heading):
    file = write(tmp_path / "status.md", f"{heading}\n\nSend revisions to [us](mailto:a@b.c).\n")

    section = read_document_section(file)

    assert section == {
        "filepath": fix_path(file),
        "title": "Document Status",
        "description": "Send revisions to [us](mailto:a@b.c).",
    }


@pytest.mark.parametrize(
    "heading, title",
    [("## C#", "C#"), ("## Heading# #", "Heading#"), ("## Heading #1", "Heading #1"), ("## Heading ###  ", "Heading")],
)
def test_document_section_titles_keep_hashes_that_belong_to_them(tmp_path, heading, title):
    file = write(tmp_path / "status.md", f"{heading}\n\nText")

    assert read_document_section(file)["title"] == title


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


@pytest.mark.parametrize("stable, draft", [(True, False), (False, True)])
def test_only_drafts_say_that_drafts_have_no_history(tmp_path, stable, draft):
    markdown = read_template(tmp_path).render(**context(stable=stable, document=read_document_sections(tmp_path)))

    assert ("not included in the draft versions" in markdown) == draft
    assert ("not included in this document" in markdown) == (not draft)


def test_headings_remain_without_document_sections(tmp_path):
    markdown = read_template(tmp_path).render(**context(document=read_document_sections(tmp_path)))

    assert "## Document Status\n" in markdown
    assert "## Introduction\n" in markdown
    assert "Draft Version" not in markdown
    assert "sections/document" not in markdown


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
    "template",
    [
        '~( include ["missing.md", "part.md"] )~',
        '~( include ("missing.md", "part.md") )~',
        '~( include "missing.md" ignore missing )~',
        "~( include name ignore missing )~",
    ],
)
def test_fallback_and_optional_includes_pass_the_check(tmp_path, template):
    write(tmp_path / "templates" / "template.md", template)
    write(tmp_path / "templates" / "part.md", "Part")

    check_template(tmp_path)


@pytest.mark.parametrize(
    "template, message",
    [
        ('~( include "missing.md" )~', "references the missing template missing.md"),
        ('~( include ["a.md", "b.md"] )~', "references the missing template a.md or b.md"),
        ('~( include "broken.md" )~', "Unexpected end of template"),
        ('~( if false )~~( import "missing.md" as m )~~( endif )~', "references the missing template missing.md"),
        ("~( include name )~", "by a variable"),
        ("~{ title | unknown }~", "No filter named 'unknown'"),
        ("~( if title )~", "Unexpected end of template"),
    ],
)
def test_broken_templates_fail_the_check(tmp_path, template, message):
    write(tmp_path / "templates" / "template.md", template)
    write(tmp_path / "templates" / "broken.md", "~( if title )~")

    with pytest.raises(Exception, match=message):
        check_template(tmp_path)


def test_strict_templates_fail_on_undefined_variables(tmp_path):
    write(tmp_path / "templates" / "template.md", "~{ titel }~")

    assert read_template(tmp_path).render(title="SR") == ""
    with pytest.raises(UndefinedError, match="'titel' is undefined"):
        read_template(tmp_path, strict=True).render(title="SR")


ALL_SECTIONS = {"draft", "status", "definition", "introduction"}


@pytest.mark.parametrize(
    "template, used",
    [
        (None, ALL_SECTIONS),
        ("No sections", set()),
        ("~{ document.status.title }~ ~( if document['draft'] )~x~( endif )~", {"status", "draft"}),
        ('~( include "part.md" )~', {"definition"}),
        ("~( macro m(d) )~~( endmacro )~~{ m(document) }~", ALL_SECTIONS),
        ("~( for s in document.values() )~~( endfor )~", ALL_SECTIONS),
        ("~{ document[name] }~", ALL_SECTIONS),
        ("~( include name ignore missing )~", ALL_SECTIONS),
    ],
)
def test_used_document_sections(tmp_path, template, used):
    if template is not None:
        write(tmp_path / "templates" / "template.md", template)
    write(tmp_path / "templates" / "part.md", "~{ document.definition.description }~")

    assert used_document_sections(tmp_path) == used


@pytest.mark.parametrize("template, message", [(None, "its text is left out"), ("Custom", "not used by the template")])
def test_validation_only_warns_about_missing_sections_that_are_used(tmp_path, capsys, template, message):
    if template is not None:
        write(tmp_path / "templates" / "template.md", template)
    for folder in ["pfs", "requirements", "glossary", "sections"]:
        (tmp_path / folder).mkdir()

    validate(tmp_path)

    lines = [line for line in capsys.readouterr().out.splitlines() if "sections/document/" in line]
    assert len(lines) == 4
    assert all(message in line for line in lines)


@pytest.mark.parametrize("combined, expected", [(False, 3), (True, 0)])
def test_only_single_pfs_documents_link_to_their_document_yaml(tmp_path, combined, expected):
    markdown = read_template(tmp_path).render(**context(combined=combined, document=read_document_sections(tmp_path)))

    assert markdown.count("<!-- edit:pfs/SR/document.yaml -->") == expected


MULTI = "First paragraph.\n\nSecond paragraph.\n\n- item"


def test_multiline_glossary_descriptions_stay_in_their_definition(tmp_path):
    glossary = [
        {"term": "One", "description": "Wrapped\nline.", "filepath": "one.yaml"},
        {"term": "Two", "description": MULTI, "filepath": "two.yaml"},
    ]

    markdown = read_template(tmp_path).render(**context(glossary=glossary, document=read_document_sections(tmp_path)))

    assert "One\n:   Wrapped\n    line.\n" in markdown
    assert "Two\n\n:   First paragraph.\n\n    Second paragraph.\n\n    - item\n" in markdown


def test_multiline_notes_stay_in_their_list_item(tmp_path):
    notes = [f"Note {i}." for i in range(1, 10)] + [MULTI]
    requirement = {
        "uid": "x",
        "title": "Title\nwith a break",
        "description": "",
        "filepath": "x.yaml",
        "threshold": {"description": "Threshold.", "notes": notes},
        "goal": None,
    }
    category = {"id": "c", "title": "Category", "description": "", "filepath": "c.yaml"}
    data = context(editable=True, requirements=[{"category": category, "requirements": [requirement]}])

    markdown = read_template(tmp_path).render(**data, document=read_document_sections(tmp_path))

    assert "10. First paragraph.\n\n    Second paragraph.\n\n    - item\n" in markdown
    assert "| `x` | Title with a break |" in markdown


def test_multiline_applies_to_of_combined_documents_stays_in_its_list_item(tmp_path):
    data = context(combined=True, applies_to={"A": MULTI, "B": "Single."})

    markdown = read_template(tmp_path).render(**data, document=read_document_sections(tmp_path))

    assert "- **A**: First paragraph.\n\n  Second paragraph.\n\n  - item\n- **B**: Single.\n" in markdown


def test_titles_are_read_as_a_single_line():
    import strictyaml

    from ceos_ard_cli.strictyaml.single_line import SingleLine

    data = strictyaml.load(
        "title: |-\n  Spatial\n  resolution  of\n\n  bands\n", strictyaml.Map({"title": SingleLine()})
    )

    assert data.data["title"] == "Spatial resolution of bands"


def test_table_cells_escape_pipes(tmp_path):
    requirement = {
        "uid": "x",
        "title": "Spatial | Spectral",
        "description": "",
        "filepath": "x.yaml",
        "threshold": {"description": "Threshold.", "notes": []},
        "goal": None,
    }
    category = {"id": "c", "title": "Category", "description": "", "filepath": "c.yaml"}
    data = context(editable=True, requirements=[{"category": category, "requirements": [requirement]}])

    markdown = read_template(tmp_path).render(**data, document=read_document_sections(tmp_path))

    assert r"| `x` | Spatial \| Spectral |" in markdown


@pytest.mark.parametrize(
    "text, cell",
    [
        ("a | b", r"a \| b"),
        (r"a \| b", r"a \| b"),
        (r"a \\| b", r"a \\\| b"),
        (r"a \\\| b", r"a \\\| b"),
        ("|a|", r"\|a\|"),
        ("a\n  b", "a b"),
    ],
)
def test_table_cell_escapes_only_unescaped_pipes(text, cell):
    assert table_cell(text) == cell


def test_document_sections_keep_the_indentation_of_their_text(tmp_path):
    file = write(tmp_path / "status.md", "\n## Status\n\n\n    code block\n\nText  \n\n")

    assert read_document_section(file)["description"] == "    code block\n\nText"


@pytest.mark.skipif(not shutil.which("pandoc-crossref"), reason="requires pandoc and pandoc-crossref")
def test_section_links_show_the_full_label_of_their_target():
    markdown = (
        "---\nlinkReferences: true\nsecPrefixTemplate: $$i$$\n---\n\n"
        '### Category {#sec:c label="|Category"}\n\n'
        '#### A|B and C | D {#sec:r label="|Category: A|B and C | D"}\n\n'
        "See @sec:r, @sec:c and [custom text](#sec:c).\n"
    )
    cmd = ["pandoc", "-F", "pandoc-crossref", "-L", str(FILTERS_DIR / "no-sectionnumbers.lua"), "-t", "plain"]

    text = subprocess.run(cmd, input=markdown, capture_output=True, text=True, encoding="utf-8", check=True).stdout

    assert "See Category: A|B and C | D, Category and custom text." in text


def test_templates_are_compiled_once(tmp_path):
    assert read_template(tmp_path) is read_template(tmp_path)
    assert read_template(tmp_path, strict=True) is not read_template(tmp_path)


def test_changed_templates_are_compiled_again(tmp_path):
    file = write(tmp_path / "templates" / "template.md", "First")
    assert read_template(tmp_path).render() == "First"

    file.write_text("Second", encoding="utf-8")
    # Jinja compares the modification time, which can have a low resolution
    stat = file.stat()
    os.utime(file, (stat.st_atime, stat.st_mtime + 10))

    assert read_template(tmp_path).render() == "Second"


def test_overrides_added_or_removed_later_are_used(tmp_path):
    assert "Contributing Authors" in read_template(tmp_path).render(**context(document={}))

    override = write(tmp_path / "templates" / "template.md", "Override")
    assert read_template(tmp_path).render() == "Override"

    override.unlink()
    assert "Contributing Authors" in read_template(tmp_path).render(**context(document={}))
