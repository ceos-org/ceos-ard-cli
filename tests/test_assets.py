"""Tests for the copy of the assets folder next to the documents."""

import os
from pathlib import Path

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

    def test_keeps_folders_with_the_same_files(self, tmp_path):
        # The same names don't make it a copy of the CLI
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "ours")
        write(target / "a.png", "theirs")
        with pytest.raises(ValueError, match="not created by the CLI"):
            sync_assets(source, target)
        assert (target / "a.png").read_text() == "theirs"

    def test_uses_empty_folders(self, tmp_path):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "a")
        target.mkdir(parents=True)
        sync_assets(source, target)
        assert tree(target) == ["a.png"]

    def test_copies_files_with_the_same_size_and_time(self, tmp_path):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "old")
        sync_assets(source, target)
        # compares the unchanged files, which must not be remembered
        sync_assets(source, target)
        times = (source / "a.png").stat()
        write(source / "a.png", "new")
        os.utime(source / "a.png", ns=(times.st_atime_ns, times.st_mtime_ns))
        sync_assets(source, target)
        assert (target / "a.png").read_text() == "new"

    @pytest.mark.parametrize("link", ["a.png", "sub"])
    def test_links_in_the_copy_are_refused(self, tmp_path, link):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "ours")
        write(source / "sub" / "b.png", "ours")
        sync_assets(source, target)
        write(tmp_path / "outside" / "a.png", "theirs")
        write(tmp_path / "outside" / "sub" / "b.png", "theirs")
        if link == "sub":
            (target / "sub" / "b.png").unlink()
            (target / "sub").rmdir()
        else:
            (target / "a.png").unlink()
        try:
            os.symlink(tmp_path / "outside" / link, target / link, target_is_directory=link == "sub")
        except OSError:
            pytest.skip("can't create symlinks")
        with pytest.raises(ValueError, match="Symbolic links are not supported"):
            sync_assets(source, target)
        assert (tmp_path / "outside" / "a.png").read_text() == "theirs"
        assert (tmp_path / "outside" / "sub" / "b.png").read_text() == "theirs"

    def test_renames_that_only_change_the_case(self, tmp_path):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "sub" / "logo.png", "logo")
        sync_assets(source, target)
        (source / "sub" / "logo.png").rename(source / "sub" / "Logo.png")
        (source / "sub").rename(source / "Sub")
        sync_assets(source, target)
        assert tree(target) == ["Sub", "Sub/Logo.png"]

    @pytest.mark.parametrize("name", [ASSETS_MARKER, ASSETS_MARKER.upper()])
    def test_the_name_of_the_marker_is_reserved(self, tmp_path, name):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "a.png", "a")
        sync_assets(source, target)
        write(source / name / "b.png", "b")
        with pytest.raises(ValueError, match="is reserved"):
            sync_assets(source, target)
        assert tree(target) == ["a.png"]

    def test_unreadable_folders_fail_before_files_are_removed(self, tmp_path, monkeypatch):
        source, target = tmp_path / "assets", tmp_path / "out" / "assets"
        write(source / "sub" / "a.png", "a")
        sync_assets(source, target)
        walk = os.walk

        def unreadable(top, onerror=None):
            if Path(top) == source and onerror:
                onerror(PermissionError("denied"))
            return walk(top, onerror=onerror)

        monkeypatch.setattr(os, "walk", unreadable)
        with pytest.raises(PermissionError):
            sync_assets(source, target)
        assert tree(target) == ["sub", "sub/a.png"]

    def test_without_assets(self, tmp_path):
        target = tmp_path / "out" / "assets"
        sync_assets(tmp_path / "assets", target)
        assert tree(target) == []
