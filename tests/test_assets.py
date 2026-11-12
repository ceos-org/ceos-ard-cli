"""Tests for the copy of the assets folder next to the documents."""

import pytest

from ceos_ard_cli.utils.files import ASSETS_MARKER, sync_assets


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def tree(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.name != ASSETS_MARKER)


class TestAssets:
    def test_copies_new_and_changed_files_and_removes_the_others(self, tmp_path):
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

    def test_keeps_folders_that_the_cli_did_not_create(self, tmp_path):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "a")
        write(target / "theirs.txt", "important")
        with pytest.raises(ValueError, match="not created by the CLI"):
            sync_assets(source, target)
        assert tree(target) == ["theirs.txt"]

    def test_adopts_copies_of_earlier_versions(self, tmp_path):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "changed")
        write(source / "b.png", "b")
        write(target / "a.png", "old")
        sync_assets(source, target)
        assert tree(target) == ["a.png", "b.png"]
        assert (target / "a.png").read_text() == "changed"

    def test_without_assets(self, tmp_path):
        target = tmp_path / "out" / "assets"
        sync_assets(tmp_path / "assets", target)
        assert tree(target) == []
