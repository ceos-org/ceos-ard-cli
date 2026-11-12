"""Tests for the checks of the tools that generate the documents."""

import shutil
import tomllib
from pathlib import Path

import pytest

from ceos_ard_cli import toolchain
from ceos_ard_cli.generate import generate, run_playwright


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv(toolchain.SKIP_CHECK, raising=False)
    toolchain.check_tools.cache_clear()
    yield
    toolchain.check_tools.cache_clear()


def test_pinned_versions_come_from_the_pixi_dependencies():
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["tool"]["pixi"]["dependencies"]

    assert toolchain.pinned_versions() == {tool: dependencies[tool].removeprefix("==") for tool in toolchain.TOOLS}


def test_missing_tools_fail_the_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda tool: None)

    with pytest.raises(ValueError, match="pandoc and pandoc-crossref not found"):
        generate("SR", tmp_path / "out" / "SR", tmp_path)
    # before anything is written
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(("installed", "warns"), [("3.6.2", True), (None, False), ("pinned", False)])
def test_other_versions_are_warned_about(monkeypatch, capsys, installed, warns):
    pinned = {"pandoc": "3.13"}
    monkeypatch.setattr(shutil, "which", lambda tool: tool)
    monkeypatch.setattr(toolchain, "pinned_versions", lambda: pinned)
    monkeypatch.setattr(
        toolchain, "installed_version", lambda tool: pinned[tool] if installed == "pinned" else installed
    )

    toolchain.check_tools()

    output = capsys.readouterr().out
    assert ("pandoc 3.6.2 is used, but the CLI is tested with pandoc 3.13" in output) == warns


def test_checks_can_be_skipped(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise AssertionError("must not look for the tools")

    monkeypatch.setenv(toolchain.SKIP_CHECK, "1")
    monkeypatch.setattr(shutil, "which", fail)
    monkeypatch.setattr(toolchain, "installed_version", fail)

    toolchain.check_tools()

    assert capsys.readouterr().out == ""


@pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")
def test_installed_version():
    assert toolchain.installed_version("pandoc").count(".") >= 1
    assert toolchain.installed_version("not-a-tool") is None


def test_missing_browser_is_explained(tmp_path, monkeypatch):
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as p:
        browser_type = type(p.chromium)

    def launch(self, **kwargs):
        raise Error("BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium")

    monkeypatch.setattr(browser_type, "launch", launch)
    (tmp_path / "doc.html").write_text("<p>x</p>", encoding="utf-8")

    with pytest.raises(ValueError, match="pixi run install-browser"):
        run_playwright(tmp_path / "doc", tmp_path)
