from strictyaml.exceptions import (
    AnchorTokenDisallowed,
    DuplicateKeysDisallowed,
    FlowMappingDisallowed,
    InconsistentIndentationDisallowed,
    TagTokenDisallowed,
    YAMLValidationError,
)
from strictyaml.ruamel.composer import ComposerError
from strictyaml.ruamel.error import MarkedYAMLError
from strictyaml.ruamel.parser import ParserError
from strictyaml.ruamel.scanner import ScannerError

SEQUENCE = ("when expecting a sequence", "when expecting a unique sequence")
FOUND = {"found arbitrary text": "found text", "found a mapping": "found keys with values"}


def fail(chunk, message):
    # Without the "expecting ... found ..." pair of `chunk.expecting_but_found`
    raise YAMLValidationError(None, message, chunk)


# A problem in the content of a referenced file that isn't YAML, e.g. a bibliography entry
class ReferencedFileError(YAMLValidationError):
    def __init__(self, chunk, file: str, message: str):
        # The text names the file, at the position of the reference
        super().__init__(None, f"{file}: {message}", chunk)
        self.file = file
        self.message = message


def explain(error: MarkedYAMLError) -> tuple[str, str | None, int | None, int | None]:
    # Anything not recognized keeps the message of strictyaml.
    # Its wording is only matched for a few validation errors, each covered by a test.
    if isinstance(error, YAMLValidationError):
        line, column = _position(error)
        return _explain_validation(error) or _join(error), error.context_mark.name, line, column
    mark = error.problem_mark or error.context_mark
    if isinstance(error, FlowMappingDisallowed):
        message = (
            "brackets ([...] or {...}) aren't supported: write a list with one '- ' item per line, or quote the text"
        )
    elif isinstance(error, DuplicateKeysDisallowed):
        key = _line(mark).split(":", 1)[0].strip()
        message = f"the key '{key}' is used more than once" if key else "a key is used more than once"
    elif isinstance(error, AnchorTokenDisallowed) or (isinstance(error, ComposerError) and _char(mark) == "*"):
        # e.g. Markdown emphasis at the start of a value
        message = "text that starts with & or * must be in quotes"
    elif isinstance(error, TagTokenDisallowed):
        message = "tags (!) aren't supported: quote text that starts with !"
    elif isinstance(error, InconsistentIndentationDisallowed):
        message = "the indentation is inconsistent"
    elif isinstance(error, ScannerError) and _char(mark) == "\t":
        message = "tabs aren't allowed, indent with spaces"
    elif isinstance(error, ScannerError) and _char(mark) == ":":
        message = "text that contains ': ' must be in quotes"
    elif isinstance(error, ParserError):
        message = "the indentation doesn't fit the lines above"
    else:
        message = _join(error)
    if mark is None:
        return message, None, None, None
    return message, mark.name, mark.line + 1, mark.column + 1


def _explain_validation(error: YAMLValidationError) -> str | None:
    problem = error.problem or ""
    if error.context == "while parsing a mapping":
        if problem.startswith("required key(s) "):
            return problem
        if problem.startswith("unexpected key not in schema "):
            return f"unknown key {problem.removeprefix('unexpected key not in schema ')}"
    if error.context in SEQUENCE and problem in FOUND:
        return f"expecting a list with one '- ' item per line, {FOUND[problem]}"
    return None


def _position(error: YAMLValidationError) -> tuple[int, int | None]:
    # strictyaml counts the lines of a partial dump of the document, which can be off, and has no column.
    # The parsed document has the positions in the source, at the path that strictyaml keeps (internally).
    try:
        node = error._chunk._ruamelparsed
        path = [(kind, index[0] if kind in ("key", "val") else index) for kind, index in error._chunk._pointer._indices]
        if not path:
            return 1, 1
        for _, index in path[:-1]:
            node = node[index]
        kind, index = path[-1]
        if kind == "index":
            line, column = node.lc.item(index)
        elif kind == "key" or isinstance(node[index], (dict, list)) or node[index] in ("", None):
            # A list or mapping as a value starts on the line after its key, an empty value at the next token
            line, column = node.lc.key(index)
        else:
            line, column = node.lc.value(index)
        return line + 1, column + 1
    except Exception:
        return error.context_mark.line + 1, None


def _join(error: MarkedYAMLError) -> str:
    return "\n".join(str(part).strip() for part in (error.context, error.problem, error.note) if part)


def _line(mark) -> str:
    lines = (getattr(mark, "buffer", None) or "").splitlines()
    return lines[mark.line] if mark is not None and mark.line < len(lines) else ""


def _char(mark) -> str | None:
    buffer, pointer = getattr(mark, "buffer", None), getattr(mark, "pointer", None)
    if buffer is None or pointer is None or pointer >= len(buffer):
        return None
    return buffer[pointer]
