import re
from functools import cache
from pathlib import Path

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    TemplateNotFound,
    Undefined,
    nodes,
)
from jinja2.sandbox import ImmutableSandboxedEnvironment

from ..schema import DOCUMENT_SECTION_PATH, DOCUMENT_SECTIONS
from .files import fix_path, read_file
from .requirement import slugify

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
FILTERS_DIR = Path(__file__).parent.parent / "filters"


def template_file(input_dir: Path, name: str) -> Path:
    """A file in the templates folder of the input directory replaces the built-in one."""
    override = Path(input_dir) / "templates" / name
    return override if override.is_file() else TEMPLATES_DIR / name


def template_environment(input_dir: Path, strict: bool = False) -> Environment:
    """Templates load from the templates folder of the input directory first, then from the built-in ones."""
    # Shared, so that each template is compiled once; Jinja recompiles templates whose files changed
    return _template_environment(Path(input_dir), strict)


@cache
def _template_environment(input_dir: Path, strict: bool) -> Environment:
    # The sandbox keeps templates from reaching Python internals or modifying the data
    env = ImmutableSandboxedEnvironment(
        loader=ChoiceLoader([FileSystemLoader(input_dir / "templates"), FileSystemLoader(TEMPLATES_DIR)]),
        undefined=StrictUndefined if strict else Undefined,
        block_start_string="~(",
        block_end_string=")~",
        variable_start_string="~{",
        variable_end_string="}~",
        comment_start_string="~#",
        comment_end_string="#~",
        trim_blocks=True,
    )
    env.filters["rstrip"] = lambda x: x.rstrip()
    env.filters["slugify"] = slugify
    env.globals["table_cell"] = table_cell
    return env


def table_cell(text: str) -> str:
    """Text for a cell of a pipe table, which a line break or an unescaped | would end."""
    # a pipe after an odd number of backslashes is already escaped
    return re.sub(r"(?<!\\)((?:\\\\)*)\|", r"\1\\|", " ".join(str(text).split()))


def read_template(input_dir: Path, strict: bool = False) -> Template:
    """With `strict`, undefined variables raise instead of rendering as empty."""
    return template_environment(input_dir, strict).get_template("template.md")


def check_template(input_dir: Path) -> None:
    """Parse template.md and every template it includes, imports or extends, also in branches no data reaches."""
    env = template_environment(input_dir)
    pending = ["template.md"]
    checked = set()
    while pending:
        name = pending.pop()
        if name in checked:
            continue
        checked.add(name)
        source = env.loader.get_source(env, name)[0]
        ast = env.parse(source, name)
        # compiles it, which catches unknown filters and tests
        env.compile(ast, name)
        for node in ast.find_all((nodes.Include, nodes.Import, nodes.FromImport, nodes.Extends)):
            candidates = _template_names(node.template)
            optional = getattr(node, "ignore_missing", False)
            if candidates is None:
                if optional:
                    continue
                raise ValueError(f"{name} references a template by a variable, which can't be checked")
            # Of a list, the first existing template is used
            found = next((c for c in candidates if _exists(env, c)), None)
            if found is not None:
                pending.append(found)
            elif not optional:
                raise ValueError(f"{name} references the missing template {' or '.join(candidates)}")


def _template_names(node: nodes.Node) -> list[str] | None:
    """The template names of a reference, None if they come from a variable."""
    if isinstance(node, nodes.Const):
        value = node.value
        values = value if isinstance(value, (list, tuple)) else [value]
    elif isinstance(node, (nodes.List, nodes.Tuple)) and all(isinstance(item, nodes.Const) for item in node.items):
        values = [item.value for item in node.items]
    else:
        return None
    return list(values) if all(isinstance(value, str) for value in values) else None


def _exists(env: Environment, name: str) -> bool:
    try:
        env.loader.get_source(env, name)
        return True
    except TemplateNotFound:
        return False


def read_document_sections(input_dir: Path) -> dict:
    """The document sections by id; None for a missing file, which the template then leaves out."""
    sections = {}
    for id in DOCUMENT_SECTIONS:
        file = (Path(input_dir) / DOCUMENT_SECTION_PATH.format(id=id)).resolve()
        sections[id] = read_document_section(file) if file.is_file() else None
    return sections


def read_document_section(file: Path) -> dict:
    """A Markdown file whose first line is a heading of any level: the heading is the title, the rest the text."""
    content = read_file(file)
    # A closing sequence of #s needs a space before it, so `## C#` keeps its #
    match = re.match(r"\s*#+[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*(?:\r?\n|$)", content)
    if not match:
        raise ValueError(f"{fix_path(file)} must start with a heading")
    return {
        "filepath": fix_path(file),
        "title": match.group(1),
        # Only blank lines are removed at the start, the indentation of the first line can matter (e.g. code)
        "description": re.sub(r"^(?:[ \t]*\r?\n)+", "", content[match.end() :]).rstrip(),
    }
