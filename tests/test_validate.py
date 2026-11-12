"""Tests for the validate command."""

import json

import pytest
from click.testing import CliRunner

from ceos_ard_cli import cli
from ceos_ard_cli.utils import files, yaml
from ceos_ard_cli.problems import unique
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


def errors(problems):
    return [problem for problem in problems if problem.severity == "error"]


def test_errors_are_counted(tmp_path):
    (tmp_path / "valid").mkdir()
    (tmp_path / "duplicate").mkdir()
    # The minimal content misses the template and the document sections, which are errors too
    count = len(errors(validate(content(tmp_path / "valid", {"a": VALID}))))
    assert count > 0
    duplicate = validate(content(tmp_path / "duplicate", {"a": VALID, "b": VALID.replace("{id}", "a")}))
    assert len(errors(duplicate)) == count + 1


def test_the_command_fails_on_errors(tmp_path):
    content(tmp_path, {"a": VALID, "b": VALID.replace("{id}", "a")})

    result = CliRunner().invoke(cli, ["validate", "-i", str(tmp_path)])

    assert result.exit_code == 1
    assert "duplicate id 'a'" in result.output
    assert result.output.rstrip().endswith("error(s)")


def pfs(tmp_path, name, requirement):
    (tmp_path / "pfs" / name).mkdir(parents=True)
    (tmp_path / "pfs" / name / "document.yaml").write_text(
        "title: X\nversion: 1.0.0\ntype: Optical\nauthors:\nintroduction:\n"
        f"requirements:\n  - category: general\n    requirements:\n      - {requirement}\n"
        "glossary:\nreferences:\nannexes:\nchanges:\n",
        encoding="utf-8",
    )
    (tmp_path / "sections" / "requirement-categories").mkdir(exist_ok=True)
    (tmp_path / "sections" / "requirement-categories" / "general.yaml").write_text(
        "title: General\ndescription: Text\n", encoding="utf-8"
    )


def complete(tmp_path, requirements):
    content(tmp_path, requirements)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "template.md").write_text("Custom", encoding="utf-8")
    (tmp_path / "sections" / "document").mkdir()
    for id in ("draft", "status", "definition", "introduction"):
        (tmp_path / "sections" / "document" / f"{id}.md").write_text("# Title\n", encoding="utf-8")
    return tmp_path


def problems_of(problems, file):
    return [problem.to_dict() for problem in problems if problem.file == file]


def test_problems_name_the_file_that_has_them(tmp_path):
    content(tmp_path, {"a": VALID + "glossary:\n  - g\n"})
    (tmp_path / "glossary" / "g.yaml").write_text("term: G\ndescription: Text\nfoo: bar\n", encoding="utf-8")
    pfs(tmp_path, "X", "a")
    pfs(tmp_path, "Y", "a")

    problems = validate(tmp_path, out=lambda _: None)

    # Once for each PFS and once by the check for duplicate ids
    assert len(problems_of(problems, "glossary/g.yaml")) == 3
    assert problems_of(unique(problems), "glossary/g.yaml") == [
        {
            "file": "glossary/g.yaml",
            "line": 3,
            "column": 1,
            "severity": "error",
            "message": "unknown key 'foo'",
        }
    ]


def test_text_output_names_the_file_of_yaml_errors(tmp_path, capsys):
    content(tmp_path, {"a": INVALID})
    pfs(tmp_path, "X", "a")

    validate(tmp_path)

    assert 'in "requirements/a.yaml", line 1' in capsys.readouterr().out


def test_unused_files_are_validated(tmp_path):
    content(tmp_path, {"a": VALID})
    (tmp_path / "sections" / "s.yaml").write_text("title: S\n", encoding="utf-8")

    problems = validate(tmp_path, out=lambda _: None)

    assert [p.severity for p in problems if p.file == "sections/s.yaml"] == ["warning", "error"]
    assert problems_of(problems, "requirements/a.yaml") == [
        {"file": "requirements/a.yaml", "severity": "warning", "message": "not referenced by any PFS"}
    ]


def test_templates_are_validated_but_not_unused(tmp_path):
    content(tmp_path, {"a": VALID, "_template": VALID})
    (tmp_path / "glossary" / "_template.yaml").write_text("term: G\n", encoding="utf-8")

    problems = validate(tmp_path, out=lambda _: None)

    assert problems_of(problems, "requirements/_template.yaml") == []
    assert [p.severity for p in problems if p.file == "glossary/_template.yaml"] == ["error"]


def test_unused_files_are_unknown_if_a_pfs_cant_be_read(tmp_path, capsys):
    content(tmp_path, {"a": INVALID, "b": VALID})
    (tmp_path / "glossary" / "g.yaml").write_text("term: G\n", encoding="utf-8")
    pfs(tmp_path, "X", "a")

    problems = validate(tmp_path)

    assert not [p for p in problems if p.message == "not referenced by any PFS"]
    assert [p.severity for p in problems if p.file == "glossary/g.yaml"] == ["error"]
    assert "skipped, as not all PFS could be read" in capsys.readouterr().out


def test_deprecated_building_blocks_are_warnings(tmp_path):
    content(tmp_path, {"a": VALID + "deprecated: true\n"})
    pfs(tmp_path, "X", "a")

    problems = validate(tmp_path, out=lambda _: None)

    assert problems_of(problems, "requirements/a.yaml") == [
        {"file": "requirements/a.yaml", "severity": "warning", "message": "requirement 'Title' is deprecated"}
    ]


def test_template_errors_have_a_line(tmp_path):
    complete(tmp_path, {"a": VALID})
    (tmp_path / "templates" / "template.md").write_text("Text\n~( if )~\n", encoding="utf-8")

    problems = validate(tmp_path, out=lambda _: None)

    assert [(p.file, p.line) for p in errors(problems)] == [("templates/template.md", 2)]


def run_json(*args):
    result = CliRunner().invoke(cli, ["validate", "--format", "json", *args])
    return result.exit_code, json.loads(result.stdout)


def test_json_output(tmp_path):
    content(tmp_path, {"a": VALID, "b": VALID.replace("{id}", "a")})

    exit_code, problems = run_json("-i", str(tmp_path))

    assert exit_code == 1
    assert {
        "file": "requirements/b.yaml",
        "severity": "error",
        "message": "duplicate id 'a' (also in requirements/a.yaml)",
    } in problems


def test_json_output_with_warnings_only(tmp_path):
    complete(tmp_path, {"a": VALID})

    exit_code, problems = run_json("-i", str(tmp_path))

    assert exit_code == 0
    assert {"file": "requirements/a.yaml", "severity": "warning", "message": "not referenced by any PFS"} in problems
    assert all(problem["severity"] == "warning" for problem in problems)


def test_json_output_of_unexpected_errors(tmp_path):
    exit_code, problems = run_json("-i", str(tmp_path / "missing"))

    assert exit_code == 1
    assert len(problems) == 1
    assert problems[0]["severity"] == "error"
