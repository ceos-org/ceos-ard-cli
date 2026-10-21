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

    def test_check_changes_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check-changes", "--help"])

        assert result.exit_code == 0
        assert "--base" in result.output
