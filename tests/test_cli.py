"""Tests for the CEOS-ARD CLI."""

import pytest
from click.testing import CliRunner

from ceos_ard_cli import cli
from ceos_ard_cli.version import __version__


class TestCLI:
    """Test cases for the main CLI functionality."""

    def test_cli_help(self):
        """Test that the CLI help command returns successfully."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "The CEOS ARD CLI." in result.output
        assert "Commands:" in result.output
        assert "compile" in result.output
        assert "generate" in result.output
        assert "validate" in result.output
        assert "check-changes" in result.output

    def test_cli_version(self):
        """Test that the CLI version command returns the correct version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output

    @pytest.mark.parametrize("command", ["compile", "generate", "generate-all"])
    def test_history_option(self, command):
        """Test that the document history can be enabled for all generating commands."""
        runner = CliRunner()
        result = runner.invoke(cli, [command, "--help"])

        assert result.exit_code == 0
        assert "--history" in result.output
        assert "--github-repo" in result.output
        assert "--patch-changes" in result.output
        assert "--offline" in result.output

    @pytest.mark.parametrize("command", ["compile", "generate"])
    def test_pfs_is_required(self, command):
        result = CliRunner().invoke(cli, [command])

        assert result.exit_code == 2
        assert "Missing argument" in result.output

    @pytest.mark.parametrize("command", [["compile", "SR"], ["generate-all"]])
    def test_input_must_be_a_content_folder(self, command, tmp_path):
        result = CliRunner().invoke(cli, [*command, "-i", str(tmp_path), "-o", str(tmp_path / "out" / "x")])

        assert result.exit_code == 1
        assert "has no 'pfs' folder" in result.output

    def test_check_changes_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check-changes", "--help"])

        assert result.exit_code == 0
        assert "--base" in result.output

    @pytest.mark.parametrize(
        ("command", "message"),
        [
            (["compile", "../requirements"], "Invalid PFS '../requirements'"),
            (["generate", "TYPO"], "Unknown PFS 'TYPO', expected one of: SR"),
            (["generate-all", "--pfs", "TYPO"], "Unknown PFS 'TYPO', expected one of: SR"),
        ],
    )
    def test_pfs_are_checked_before_anything_is_written(self, command, message, tmp_path):
        (tmp_path / "content" / "pfs" / "SR").mkdir(parents=True)
        (tmp_path / "content" / "assets").mkdir()
        (tmp_path / "requirements.md").write_text("theirs", encoding="utf-8")
        output = [] if command[0] == "compile" else ["-o", str(tmp_path / "out" / "x")]

        result = CliRunner().invoke(cli, [*command, "-i", str(tmp_path / "content"), *output])

        assert result.exit_code == 1
        assert message in result.output
        assert sorted(p.name for p in tmp_path.iterdir()) == ["content", "requirements.md"]
