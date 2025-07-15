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

    def test_cli_version(self):
        """Test that the CLI version command returns the correct version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output
