"""Tests for the validate command."""

import pytest

from ceos_ard_cli.utils import files, yaml
from ceos_ard_cli.validate import validate

VALID = "id: {id}\ntitle: Title\nrequirements:\n  threshold:\n    description: Text\n"
INVALID = "id: {id}\nrequirements:\n  threshold:\n    description: Text\n"


@pytest.fixture(autouse=True)
def empty_caches():
    yaml.YAML_CACHE.clear()
    files.FILE_CACHE.clear()


def content(tmp_path, requirements):
    for folder in ("pfs", "glossary", "sections"):
        (tmp_path / folder).mkdir()
    (tmp_path / "requirements").mkdir()
    for name, text in requirements.items():
        (tmp_path / "requirements" / f"{name}.yaml").write_text(text.format(id=name), encoding="utf-8")
    return tmp_path


def requirement_lines(output):
    return [line for line in output.splitlines() if line.startswith("- requirements")]


def test_unreadable_requirements_are_reported_under_their_own_name(tmp_path, capsys):
    validate(content(tmp_path, {"a": VALID, "b": INVALID, "c": VALID}))

    lines = requirement_lines(capsys.readouterr().out.split("Checking for duplicate requirement IDs")[1])
    assert len(lines) == 1
    assert lines[0].startswith("- requirements/b.yaml: ") or lines[0].startswith("- requirements\\b.yaml: ")


def test_an_unreadable_first_requirement_is_reported(tmp_path, capsys):
    # Used by a PFS, so that it isn't listed as unused (which also logs a file name)
    content(tmp_path, {"a": INVALID})
    (tmp_path / "pfs" / "X").mkdir()
    (tmp_path / "pfs" / "X" / "document.yaml").write_text(
        "title: X\nversion: 1.0.0\ntype: Optical\nauthors:\nintroduction:\n"
        "requirements:\n  - category: general\n    requirements:\n      - a\n",
        encoding="utf-8",
    )
    (tmp_path / "sections" / "requirement-categories").mkdir()
    (tmp_path / "sections" / "requirement-categories" / "general.yaml").write_text(
        "title: General\ndescription: Text\n", encoding="utf-8"
    )

    validate(tmp_path)

    lines = requirement_lines(capsys.readouterr().out.split("Checking for duplicate requirement IDs")[1])
    assert len(lines) == 1
    assert "a.yaml" in lines[0]


def test_duplicate_ids_are_reported(tmp_path, capsys):
    validate(content(tmp_path, {"a": VALID, "b": VALID.replace("{id}", "a")}))

    output = capsys.readouterr().out.split("Checking for duplicate requirement IDs")[1]
    assert "duplicate id 'a'" in output
