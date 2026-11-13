"""Tests for the copy of the assets folder next to the documents."""

import pytest

from ceos_ard_cli.compile import ASSETS_MARKER, sync_assets


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def tree(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.name != ASSETS_MARKER)


def test_copies_new_and_changed_files_and_removes_the_others(tmp_path):
    source, target = tmp_path / "assets", tmp_path / "out" / "assets"
    write(source / "a.png", "a")
    write(source / "sub" / "b.png", "b")
    sync_assets(source, target)
    assert tree(target) == ["a.png", "sub", "sub/b.png"]

    write(source / "a.png", "changed")
    (source / "sub" / "b.png").unlink()
    (source / "sub").rmdir()
    write(source / "c.png", "c")
    sync_assets(source, target)
    assert tree(target) == ["a.png", "c.png"]
    assert (target / "a.png").read_text() == "changed"


def test_keeps_folders_that_the_cli_did_not_create(tmp_path):
    source, target = tmp_path / "assets", tmp_path / "out" / "assets"
    write(source / "a.png", "ours")
    write(target / "a.png", "theirs")
    write(target / "notes.txt", "theirs")
    with pytest.raises(ValueError, match="not created by the CLI"):
        sync_assets(source, target)
    assert (target / "a.png").read_text() == "theirs"
    assert tree(target) == ["a.png", "notes.txt"]


def test_uses_empty_folders(tmp_path):
    source, target = tmp_path / "assets", tmp_path / "out" / "assets"
    write(source / "a.png", "a")
    target.mkdir(parents=True)
    sync_assets(source, target)
    assert tree(target) == ["a.png"]
