import os
import re
import shutil
import subprocess
import tomllib
from functools import cache
from pathlib import Path

from .problems import WARNING, Problem, report

PACKAGE = Path(__file__).parent
PACKAGE_NAME = "ceos-ard-cli"
TOOLS = ["pandoc", "pandoc-crossref"]
# Set to skip the checks where the environment is known to be right, e.g. on a server
SKIP_CHECK = "CEOS_ARD_SKIP_TOOL_CHECK"
BROWSER_MISSING = "The browser for the PDF is not installed: run `pixi run install-browser`"


@cache
def pinned_versions() -> dict[str, str]:
    """The versions of the tools that this release is tested with, from the pixi dependencies in pyproject.toml."""
    # Part of the package in a wheel, next to it in a checkout
    for file in (PACKAGE / "pyproject.toml", PACKAGE.parent / "pyproject.toml"):
        if not file.is_file():
            continue
        pyproject = tomllib.loads(file.read_text(encoding="utf-8"))
        if pyproject.get("project", {}).get("name") != PACKAGE_NAME:
            continue
        dependencies = pyproject.get("tool", {}).get("pixi", {}).get("dependencies", {})
        return {
            tool: version.removeprefix("==")
            for tool in TOOLS
            if isinstance(version := dependencies.get(tool), str) and version.startswith("==")
        }
    return {}


def installed_version(tool: str) -> str | None:
    try:
        result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\d+(?:\.\d+)+", result.stdout.partition("\n")[0])
    return match.group(0) if match else None


@cache
def check_tools() -> None:
    """Fails without the tools that generate the documents and warns about versions the CLI isn't tested with."""
    if os.environ.get(SKIP_CHECK):
        return
    missing = [tool for tool in TOOLS if not shutil.which(tool)]
    if missing:
        raise ValueError(f"{' and '.join(missing)} not found: run the CLI in its pixi environment, see the README")
    for tool, pinned in pinned_versions().items():
        installed = installed_version(tool)
        if installed and installed != pinned:
            message = f"{tool} {installed} is used, but the CLI is tested with {tool} {pinned}"
            report(f"WARNING: {message}", Problem(severity=WARNING, message=message))


@cache
def check_browser() -> None:
    """Fails without the browser that prints the PDF, before the other documents are generated."""
    if os.environ.get(SKIP_CHECK):
        return
    # Only loaded for PDFs, as it takes a while
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as p:
        # Launched as for the PDF, as Playwright picks one of several browser builds
        try:
            p.chromium.launch().close()
        except Error as e:
            if "Executable doesn't exist" in str(e):
                raise ValueError(BROWSER_MISSING) from e
            raise
