"""Tests that the Markdown template can't run code."""

import pytest
from jinja2.exceptions import SecurityError

from ceos_ard_cli.utils.template import read_template


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_template_can_not_reach_python(tmp_path):
    write(tmp_path / "templates" / "template.md", "~{ ''.__class__.__mro__[1].__subclasses__() }~")
    with pytest.raises(SecurityError):
        read_template(tmp_path).render()


def test_template_can_not_modify_data(tmp_path):
    write(tmp_path / "templates" / "template.md", "~( set _ = items.append(1) )~")
    with pytest.raises(SecurityError):
        read_template(tmp_path).render(items=[])


def test_template_renders_the_usual_constructs(tmp_path):
    write(
        tmp_path / "templates" / "template.md",
        "~{ ', '.join(ids) }~ ~( for k, v in m.items() )~~{ k }~=~{ v | rstrip }~~( endfor )~ ~{ 'a/b' | slugify }~",
    )
    assert read_template(tmp_path).render(ids=["A", "B"], m={"x": "y  "}) == "A, B x=y a-b"
