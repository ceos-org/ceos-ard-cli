import json
import re
import sys
from collections.abc import Callable
from contextlib import contextmanager, redirect_stdout
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path

from jinja2 import TemplateSyntaxError
from strictyaml.ruamel.error import MarkedYAMLError

from .strictyaml.errors import ReferencedFileError, explain
from .utils.deprecation import describe_kind
from .utils.files import fix_path

ERROR = "error"
WARNING = "warning"
BIBLIOGRAPHY_ENTRY = re.compile(r"bibliography entry '(.+)'")

# The problems of the running command, if they are reported as data instead of text
_COLLECTED: ContextVar[list | None] = ContextVar("problems", default=None)


@dataclass(frozen=True, kw_only=True)
class Problem:
    file: str | None = None
    pfs: str | None = None
    line: int | None = None
    column: int | None = None
    severity: str = ERROR
    message: str

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


class MultipleErrors(ValueError):
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


def to_problem(error, input_dir: Path, file: str | None = None, pfs: str | None = None) -> Problem:
    if isinstance(error, ReferencedFileError):
        # Not at the reference: each file that references it would report it separately
        return Problem(file=error.file, message=error.message)
    if isinstance(error, MarkedYAMLError):
        message, name, line, column = explain(error)
        # YAML errors are raised in the file that has the problem, which can be one that the checked file references
        if name is not None and (input_dir / name).is_file():
            return Problem(file=name, line=line, column=column, message=message)
        return Problem(file=file, pfs=pfs, message=message)
    if isinstance(error, TemplateSyntaxError) and error.name and (input_dir / "templates" / error.name).is_file():
        return Problem(file=f"templates/{error.name}", line=error.lineno, message=error.message)
    return Problem(file=file, pfs=pfs, message=str(error))


def to_problems(error, input_dir: Path, file: str | None = None, pfs: str | None = None) -> list[Problem]:
    if isinstance(error, MultipleErrors):
        return [content_problem(message, input_dir, pfs) for message in error.errors]
    return [to_problem(error, input_dir, file, pfs)]


def content_problem(line: str, input_dir: Path, pfs: str | None = None) -> Problem:
    # The filters prefix a problem with its building block, see problems.lua
    source, separator, message = line.partition(": ")
    if separator:
        if entry := BIBLIOGRAPHY_ENTRY.fullmatch(source):
            source = f"references/{entry.group(1)}.bib"
        file = relative_path(Path(input_dir) / source, input_dir)
        if file and (Path(input_dir) / file).is_file():
            return Problem(file=file, message=message)
    return Problem(pfs=pfs, message=line)


def deprecation(block: dict, input_dir: Path, pfs: str) -> Problem:
    kind, name = describe_kind(block)
    file = relative_path(block["filepath"], input_dir) if block.get("filepath") else None
    return Problem(file=file, pfs=None if file else pfs, severity=WARNING, message=f"{kind} '{name}' is deprecated")


def unique(problems: list[Problem]) -> list[Problem]:
    return list(dict.fromkeys(problems))


def relative_path(path, input_dir: Path) -> str | None:
    try:
        return fix_path(Path(path).resolve().relative_to(Path(input_dir).resolve()))
    except ValueError:
        return None


def report(text: str, *problems: Problem):
    # The text for the text output, the problems for the JSON output
    collected = _COLLECTED.get()
    if collected is None:
        print(text)
    else:
        collected.extend(problems)


@contextmanager
def collect():
    problems = []
    token = _COLLECTED.set(problems)
    try:
        yield problems
    finally:
        _COLLECTED.reset(token)


def exit_with_json(task: Callable, input_dir, pfs: str | None = None):
    # The problems that are reported while running, and the ones the task returns
    with collect() as problems:
        try:
            # The JSON is the only output on stdout
            with redirect_stdout(sys.stderr):
                result = task()
            if isinstance(result, list):
                problems.extend(result)
        except Exception as e:
            problems.extend(to_problems(e, Path(input_dir).resolve(), pfs=pfs))
    problems = unique(problems)
    print(json.dumps([problem.to_dict() for problem in problems], indent=2))
    sys.exit(1 if any(problem.severity == ERROR for problem in problems) else 0)
