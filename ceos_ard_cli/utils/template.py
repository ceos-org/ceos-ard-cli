import pathlib as path

from jinja2 import Environment
from .files import read_file
from .requirement import slugify

def read_template():
    file = path.Path(f"./templates/template.md")
    if not file.exists():
        raise ValueError(f"Template {file} does not exist.")

    tpl = read_file(file)

    env = Environment(
        block_start_string='~(', block_end_string=')~',
        variable_start_string='~{', variable_end_string='}~',
        comment_start_string='~#', comment_end_string='#~',
        trim_blocks=True,
    )
    env.filters['rstrip'] = lambda x: x.rstrip()
    env.filters['slugify'] = slugify
    return env.from_string(tpl)
