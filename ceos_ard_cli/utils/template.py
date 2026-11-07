import re
from pathlib import Path

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    TemplateNotFound,
    Undefined,
    meta,
)

from ..schema import DOCUMENT_SECTION_PATH, DOCUMENT_SECTIONS
from .files import fix_path, read_file
from .requirement import slugify

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def template_file(input_dir: Path, name: str) -> Path:
    """A file in the templates folder of the input directory replaces the built-in one."""
    override = Path(input_dir) / "templates" / name
    return override if override.is_file() else TEMPLATES_DIR / name


def template_environment(input_dir: Path, strict: bool = False) -> Environment:
    """Templates load from the templates folder of the input directory first, then from the built-in ones."""
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(Path(input_dir) / "templates"), FileSystemLoader(TEMPLATES_DIR)]),
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
    return env


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
        for referenced in meta.find_referenced_templates(ast):
            if referenced is None:
                raise ValueError(f"{name} references a template by a variable, which can't be checked")
            if referenced not in checked:
                try:
                    env.loader.get_source(env, referenced)
                except TemplateNotFound:
                    raise ValueError(f"{name} references the missing template {referenced}") from None
                pending.append(referenced)


def read_document_sections(input_dir: Path) -> dict:
    """The document sections by id; None for a missing file, which the template then leaves out."""
    sections = {}
    for id in DOCUMENT_SECTIONS:
        file = (Path(input_dir) / DOCUMENT_SECTION_PATH.format(id=id)).resolve()
        sections[id] = read_document_section(file) if file.is_file() else None
    return sections


def read_document_section(file: Path) -> dict:
    """A Markdown file whose first line is a heading of any level: the heading is the title, the rest the text."""
    content = read_file(file).strip()
    match = re.match(r"#+[ \t]+(.+?)[ \t#]*(?:\n|$)", content)
    if not match:
        raise ValueError(f"{fix_path(file)} must start with a heading")
    return {
        "filepath": fix_path(file),
        "title": match.group(1),
        "description": content[match.end() :].strip(),
    }
