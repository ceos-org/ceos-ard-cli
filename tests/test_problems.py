"""Tests for reporting problems as data: the JSON output of generate, generate-all and compile."""

import json
import subprocess

import pytest
from click.testing import CliRunner

from ceos_ard_cli import cli
from ceos_ard_cli.compile import read_data
from ceos_ard_cli.generate import run_pandoc
from ceos_ard_cli.problems import MultipleErrors, Problem, collect, content_problem, report, to_problems
from ceos_ard_cli.utils import files, yaml

VALID = "id: {id}\ntitle: Title\nrequirements:\n  threshold:\n    description: Text\n"
INVALID = "id: {id}\nrequirements:\n  threshold:\n    description: Text\n"


@pytest.fixture(autouse=True)
def empty_caches():
    yaml.YAML_CACHE.clear()
    files.FILE_CACHE.clear()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def content(tmp_path, requirements):
    (tmp_path / "assets").mkdir(exist_ok=True)
    write(tmp_path / "sections" / "requirement-categories" / "general.yaml", "title: General\ndescription: Text\n")
    for name, text in requirements.items():
        write(tmp_path / "requirements" / f"{name}.yaml", text.format(id=name))
        write(
            tmp_path / "pfs" / name.upper() / "document.yaml",
            "title: X\nversion: 1.0.0\ntype: Optical\nauthors:\nintroduction:\n"
            f"requirements:\n  - category: general\n    requirements:\n      - {name}\n"
            "glossary:\nreferences:\nannexes:\nchanges:\n",
        )
    return tmp_path


def run_json(*args):
    result = CliRunner().invoke(cli, [*args, "--format", "json"])
    return result.exit_code, json.loads(result.stdout)


def test_report_prints_the_text_unless_collecting(capsys):
    problem = Problem(message="Data")

    report("Text", problem)
    with collect() as problems:
        report("Hidden", problem)

    assert capsys.readouterr().out == "Text\n"
    assert problems == [problem]


def test_content_problems_name_their_file(tmp_path):
    write(tmp_path / "requirements" / "a.yaml", "")
    write(tmp_path / "pfs" / "X" / "document.yaml", "")
    write(tmp_path / "references" / "key.bib", "")
    absolute = (tmp_path / "requirements" / "a.yaml").resolve().as_posix()

    assert content_problem(f"{absolute}: Broken", tmp_path, "X") == Problem(
        file="requirements/a.yaml", message="Broken"
    )
    assert content_problem("pfs/X/document.yaml: Broken", tmp_path) == Problem(
        file="pfs/X/document.yaml", message="Broken"
    )
    assert content_problem("bibliography entry 'key': Broken", tmp_path) == Problem(
        file="references/key.bib", message="Broken"
    )
    # Not a file of the content folder
    assert content_problem("missing.yaml: Broken", tmp_path, "X") == Problem(pfs="X", message="missing.yaml: Broken")
    assert content_problem("No source", tmp_path, "X") == Problem(pfs="X", message="No source")


def test_pandoc_failures_are_one_problem_each(tmp_path):
    write(tmp_path / "requirements" / "a.yaml", "")
    error = MultipleErrors("Generating failed", ["requirements/a.yaml: One", "Two"])

    assert to_problems(error, tmp_path, pfs="X") == [
        Problem(file="requirements/a.yaml", message="One"),
        Problem(pfs="X", message="Two"),
    ]


def test_pandoc_warnings_are_one_problem_each(tmp_path, monkeypatch):
    stderr = "[WARNING] First\n  continued\n[INFO] Second\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", stderr))
    write(tmp_path / "out" / "doc.md", "")

    with collect() as problems:
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, pfs="X")

    assert [(p.pfs, p.severity, p.message) for p in problems] == [
        ("X", "warning", "[WARNING] First\n  continued"),
        ("X", "warning", "[INFO] Second"),
    ]


def test_deprecated_building_blocks_are_reported(tmp_path):
    content(tmp_path, {"a": VALID + "deprecated: true\n"})

    with collect() as problems:
        read_data(["A"], tmp_path)

    assert problems == [
        Problem(file="requirements/a.yaml", severity="warning", message="requirement 'Title' is deprecated")
    ]


@pytest.mark.parametrize("command", ["generate", "compile"])
def test_json_output(tmp_path, command):
    content(tmp_path, {"a": INVALID})

    exit_code, problems = run_json(command, "A", "-i", str(tmp_path), "-o", str(tmp_path / "out" / "A"))

    assert exit_code == 1
    assert problems == [
        {
            "file": "requirements/a.yaml",
            "line": 1,
            "column": 1,
            "severity": "error",
            "message": "required key(s) 'title' not found",
        }
    ]


def test_json_output_of_generate_all(tmp_path):
    content(tmp_path, {"a": INVALID, "b": INVALID.replace("{id}", "b")})

    exit_code, problems = run_json("generate-all", "-i", str(tmp_path), "-o", str(tmp_path / "out"))

    assert exit_code == 1
    assert sorted(problem["file"] for problem in problems) == ["requirements/a.yaml", "requirements/b.yaml"]


@pytest.mark.parametrize("command", ["generate", "compile"])
def test_json_output_has_one_problem_per_broken_link(tmp_path, command):
    content(tmp_path, {"a": VALID.replace("description: Text", "description: See @title:nope and @title:none")})

    exit_code, problems = run_json(command, "A", "-i", str(tmp_path), "-o", str(tmp_path / "out" / "A"))

    assert exit_code == 1
    assert [(p["pfs"], "nope" in p["message"], "none" in p["message"]) for p in problems] == [
        ("A", True, False),
        ("A", False, True),
    ]


def test_json_output_of_problems_without_a_file(tmp_path):
    exit_code, problems = run_json("generate", "MISSING", "-i", str(tmp_path), "-o", str(tmp_path / "out" / "X"))

    assert exit_code == 1
    assert len(problems) == 1
    assert problems[0]["pfs"] == "MISSING"
    assert problems[0]["severity"] == "error"
