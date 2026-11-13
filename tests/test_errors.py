"""Tests for the messages and positions of the problems in YAML files.

Some messages are recognized by the wording of strictyaml: these tests fail if it changes."""

import pytest
import strictyaml

from ceos_ard_cli.problems import to_problem, unique
from ceos_ard_cli.schema import REQUIREMENT
from ceos_ard_cli.utils import files, yaml
from ceos_ard_cli.utils.yaml import read_yaml
from ceos_ard_cli.validate import validate

HEAD = "id: a\ntitle: Title\n"
PART = "requirements:\n  threshold:\n    description: Text\n"
CHANGE = "changes:\n  - date: {date}\n    author: A\n    change: C\n    reason: R\n    level: minor\n"


@pytest.fixture(autouse=True)
def empty_caches():
    yaml.YAML_CACHE.clear()
    files.FILE_CACHE.clear()


def problem(tmp_path, text, file="requirements/a.yaml"):
    for folder in ("requirements", "glossary", "references"):
        (tmp_path / folder).mkdir(exist_ok=True)
    (tmp_path / "glossary" / "g.yaml").write_text("term: G\ndescription: Text\n", encoding="utf-8")
    (tmp_path / "requirements" / "a.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(Exception) as error:
        read_yaml(tmp_path / "requirements" / "a.yaml", REQUIREMENT, tmp_path)
    result = to_problem(error.value, tmp_path.resolve())
    assert result.file == file
    return result.message, result.line, result.column


@pytest.mark.parametrize(
    "text, message, line, column",
    [
        # Recognized by the wording of strictyaml
        ("id: a\n" + PART, "required key(s) 'title' not found", 1, 1),
        (
            HEAD + "requirements:\n  threshold:\n    notes:\n      - n\n",
            "required key(s) 'description' not found",
            4,
            3,
        ),
        (HEAD + "descripton: x\n" + PART, "unknown key 'descripton'", 3, 1),
        (HEAD + PART + "glossary: g\n", "expecting a list with one '- ' item per line, found text", 6, 11),
        (HEAD + PART + "references: r\n", "expecting a list with one '- ' item per line, found text", 6, 13),
        # Recognized by the type of error
        (HEAD + PART + "glossary: [g]\n", "brackets ([...] or {...}) aren't supported", 6, 12),
        (HEAD + "title: Again\n" + PART, "the key 'title' is used more than once", 3, 6),
        (HEAD + PART + "remarks: *bold* text\n", "text that starts with & or * must be in quotes", 6, 10),
        (HEAD + PART + "remarks: &a text\n", "text that starts with & or * must be in quotes", 6, 12),
        (HEAD + PART + "remarks: !a text\n", "tags (!) aren't supported", 6, 10),
        (HEAD + "requirements:\n\tthreshold: x\n", "tabs aren't allowed, indent with spaces", 4, 1),
        (HEAD + PART + "remarks: see: this\n", "text that contains ': ' must be in quotes", 6, 13),
        (HEAD + PART + "   remarks: text\n", "the indentation doesn't fit the lines above", 6, 4),
        # Our own validators
        (HEAD + PART + "glossary:\n  - nope\n", "'nope' doesn't exist, there's no file glossary/nope.yaml", 7, 5),
        (HEAD + PART + "glossary:\n  - g\n  - g\n", "'g' is listed more than once", 8, 5),
        (HEAD + PART + "references:\n  - ../../x\n", "'../../x' points outside of the content folder", 7, 5),
        (HEAD + PART + "glossary:\n  - a#b\n", "'a#b' must not contain '#'", 7, 5),
        (HEAD + PART + "glossary:\n  - a: b\n", "when expecting an id\nfound a mapping", 7, 5),
        (HEAD + PART + CHANGE.format(date="1.1.2026"), "expecting a date as YYYY-MM-DD", 7, 11),
        (HEAD + PART + CHANGE.format(date="2026-02-30"), "expecting a date as YYYY-MM-DD", 7, 11),
        ("id: a\ntitle:\n" + PART, "expecting text, found an empty value", 2, 1),
        ("id: a\ntitle: '  '\n" + PART, "expecting text, found an empty value", 2, 8),
        (HEAD + "requirements:\n  threshold:\n    description:\n", "expecting text, found an empty value", 5, 5),
    ],
)
def test_messages_and_positions(tmp_path, text, message, line, column):
    actual, actual_line, actual_column = problem(tmp_path, text)

    assert actual.startswith(message)
    assert (actual_line, actual_column) == (line, column)


def test_other_messages_are_kept(tmp_path):
    message, line, _ = problem(tmp_path, HEAD + PART + "deprecated: maybe\n")

    assert message.startswith("when expecting a boolean value")
    assert line == 6


@pytest.mark.parametrize(
    "bibtex, message",
    [
        ("@misc{r, title={T}", "isn't valid bibtex"),
        ("@misc{r, title={T}}\n@misc{s, title={T}}", "must contain a single bibtex entry, found 2"),
        ("@misc{s, title={T}}", "the bibtex key must be 'r' as the file name, found 's'"),
        ("@misc{r, doi={https://doi.org/10.1/x}}", "invalid bibtex fields: 'doi' must be a bare DOI"),
    ],
)
def test_bibtex_problems_are_in_the_bibtex_file(tmp_path, bibtex, message):
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "r.bib").write_text(bibtex, encoding="utf-8")

    actual, line, column = problem(tmp_path, HEAD + PART + "references:\n  - r\n", file="references/r.bib")

    assert actual.startswith(message)
    # The position of the reference is in another file
    assert (line, column) == (None, None)


def test_bibtex_problems_name_the_file_in_the_text(tmp_path):
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "r.bib").write_text("@misc{s, title={T}}", encoding="utf-8")
    (tmp_path / "requirements").mkdir()
    file = tmp_path / "requirements" / "a.yaml"
    file.write_text(HEAD + PART + "references:\n  - r\n", encoding="utf-8")

    with pytest.raises(strictyaml.YAMLValidationError) as error:
        read_yaml(file, REQUIREMENT, tmp_path)

    assert "references/r.bib: the bibtex key must be 'r'" in str(error.value)
    assert 'in "requirements/a.yaml", line 7' in str(error.value)


def test_bibtex_problems_are_reported_once(tmp_path):
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "r.bib").write_text("@misc{s, title={T}}", encoding="utf-8")
    for name in ("requirements", "glossary", "sections", "pfs"):
        (tmp_path / name).mkdir(exist_ok=True)
    for id in ("a", "b"):
        text = HEAD.replace("id: a", f"id: {id}") + PART + "references:\n  - r\n"
        (tmp_path / "requirements" / f"{id}.yaml").write_text(text, encoding="utf-8")

    problems = [p for p in unique(validate(tmp_path, out=lambda _: None)) if p.file == "references/r.bib"]

    assert len(problems) == 1


def test_empty_optional_text_is_allowed(tmp_path):
    (tmp_path / "requirements").mkdir()
    file = tmp_path / "requirements" / "a.yaml"
    file.write_text(HEAD + PART + "remarks:\ndescription:\n", encoding="utf-8")

    assert read_yaml(file, REQUIREMENT, tmp_path)["remarks"] == ""
