"""Tests for the check-changes command."""

import os
import shutil
import subprocess

import pytest

from ceos_ard_cli.check_changes import check_changes, check_file, is_building_block

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}

REQUIREMENT = """id: {id}
title: {title}
requirements:
  threshold:
    description: {description}
changes:
{changes}
history:
  - SR 1.2
"""

CHANGE = """  - date: {date}
    author: Jane Doe
    level: {level}
    change: {change}
    reason: Test
"""


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=GIT_ENV)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def requirement(id, description="Test", changes=(CHANGE.format(date="2026-01-01", level="patch", change="Initial"),)):
    return REQUIREMENT.format(id=id, title=id.title(), description=description, changes="".join(changes) or "")


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path / "requirements" / "a.yaml", requirement("a"))
    write(tmp_path / "requirements" / "b.yaml", requirement("b"))
    write(tmp_path / "requirements" / "c.yaml", requirement("c"))
    write(tmp_path / "requirements" / "e.yaml", requirement("e"))
    write(tmp_path / "requirements" / "_template.yaml", requirement("template"))
    write(tmp_path / "pfs" / "X" / "document.yaml", "title: X\nversion: 1.0.0\nchanges:\n")
    write(tmp_path / "README.md", "readme\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    return tmp_path


class TestHelpers:
    def test_is_building_block(self):
        assert is_building_block("requirements/metadata/time.yaml")
        assert is_building_block("sections/annexes/examples.yaml")
        assert is_building_block("glossary/st.yaml")
        assert is_building_block("pfs/ST/document.yaml")
        assert not is_building_block("requirements/_template.yaml")
        assert not is_building_block("README.md")
        assert not is_building_block("templates/template.md")
        assert not is_building_block("references/li2013.bib")
        assert not is_building_block("pfs/ST/other.yaml")

    def test_check_file(self):
        old = requirement("a")
        assert check_file(old, old) is None
        # content changed without a new entry
        assert check_file(old, requirement("a", description="Changed")) is not None
        # content changed with a new entry
        new = requirement(
            "a",
            description="Changed",
            changes=(
                CHANGE.format(date="2026-09-01", level="minor", change="Update"),
                CHANGE.format(date="2026-01-01", level="patch", change="Initial"),
            ),
        )
        assert check_file(old, new) is None
        # new file without entry
        assert check_file("", requirement("a", changes=())) is not None
        # new file with entry
        assert check_file("", requirement("a")) is None
        # only the changes / history edited
        assert check_file(old, old.replace("Initial", "Initial edit").replace("SR 1.2", "SR 1.3")) is None


class TestCheckChanges:
    def test_reports_missing_entries(self, repo):
        # a: changed with a new entry -> OK
        write(
            repo / "requirements" / "a.yaml",
            requirement(
                "a",
                description="Changed",
                changes=(
                    CHANGE.format(date="2026-09-01", level="minor", change="Update"),
                    CHANGE.format(date="2026-01-01", level="patch", change="Initial"),
                ),
            ),
        )
        # b: changed without a new entry -> error
        write(repo / "requirements" / "b.yaml", requirement("b", description="Changed"))
        # c: only the changes entry edited -> OK
        write(repo / "requirements" / "c.yaml", requirement("c").replace("Initial", "Initial (edited)"))
        # d: added without an entry -> error
        write(repo / "requirements" / "d.yaml", requirement("d", changes=()))
        # template and readme: ignored
        write(repo / "requirements" / "_template.yaml", requirement("template", description="Changed"))
        write(repo / "README.md", "changed\n")
        # PFS document changed without entry -> error
        write(repo / "pfs" / "X" / "document.yaml", "title: X\nversion: 1.1.0\nchanges:\n")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "changes")

        errors, checked = check_changes(repo, "main")
        assert checked == 5
        assert sorted(e.split(":")[0] for e in errors) == [
            "pfs/X/document.yaml",
            "requirements/b.yaml",
            "requirements/d.yaml",
        ]

    def test_uncommitted_changes_are_checked(self, repo):
        write(repo / "requirements" / "b.yaml", requirement("b", description="Changed"))
        errors, checked = check_changes(repo, "main")
        assert checked == 1
        assert len(errors) == 1

    def test_renamed_file(self, repo):
        git(repo, "mv", "requirements/e.yaml", "requirements/renamed.yaml")
        git(repo, "commit", "-q", "-m", "rename")
        # a pure rename doesn't change the content
        errors, checked = check_changes(repo, "main")
        assert checked == 1
        assert errors == []

    def test_non_ascii_filenames(self, repo):
        # git quotes such paths unless NUL-delimited output is used
        write(repo / "requirements" / "café.yaml", requirement("cafe", changes=()))
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "added")
        write(repo / "requirements" / "thé.yaml", requirement("the", changes=()))
        errors, checked = check_changes(repo, "main")
        assert checked == 2
        assert sorted(e.split(":")[0] for e in errors) == ["requirements/café.yaml", "requirements/thé.yaml"]

    def test_no_changes(self, repo):
        errors, checked = check_changes(repo, "main")
        assert checked == 0
        assert errors == []

    def test_subfolder_input_dir(self, tmp_path):
        # the input directory is a subfolder of the git repository
        git(tmp_path, "init", "-q", "-b", "main")
        sub = tmp_path / "workspace"
        write(sub / "requirements" / "a.yaml", requirement("a"))
        git(tmp_path, "add", ".")
        git(tmp_path, "commit", "-q", "-m", "base")
        write(sub / "requirements" / "a.yaml", requirement("a", description="Changed"))
        errors, checked = check_changes(sub, "main")
        assert checked == 1
        assert errors[0].startswith("requirements/a.yaml")
