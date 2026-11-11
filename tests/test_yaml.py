"""Tests for reading the YAML files: each file is parsed once, and circular references end."""

import pytest
import strictyaml
from strictyaml import Map, Optional, Str

from ceos_ard_cli.schema import REQUIREMENT
from ceos_ard_cli.strictyaml.id_reference import IdReference
from ceos_ard_cli.utils import files, yaml
from ceos_ard_cli.utils.yaml import copy_data, read_yaml


@pytest.fixture(autouse=True)
def empty_caches():
    yaml.YAML_CACHE.clear()
    files.FILE_CACHE.clear()
    yield
    yaml.YAML_CACHE.clear()
    files.FILE_CACHE.clear()


def requirement(tmp_path, name, dependencies=(), valid=True):
    deps = "".join(f"\n  {dep}: {dep}" for dep in dependencies)
    title = "title: Title\n" if valid else ""
    file = tmp_path / "requirements" / f"{name}.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        f"id: {name}\n{title}requirements:\n  threshold:\n    description: Text\ndependencies:{deps}\n",
        encoding="utf-8",
    )
    return file


def read(tmp_path, name):
    return read_yaml(tmp_path / "requirements" / f"{name}.yaml", REQUIREMENT, tmp_path)


def test_files_are_parsed_once(tmp_path, monkeypatch):
    requirement(tmp_path, "a", ["b"])
    requirement(tmp_path, "b")
    parsed = []
    load = strictyaml.load
    monkeypatch.setattr(yaml.strictyaml, "load", lambda *args: parsed.append(1) or load(*args))

    read(tmp_path, "a")
    read(tmp_path, "a")
    read(tmp_path, "b")

    assert len(parsed) == 2


def test_each_read_gets_its_own_copy(tmp_path):
    requirement(tmp_path, "a")

    first = read(tmp_path, "a")
    first["requirements"]["threshold"]["description"] = "Changed"
    first["dependencies"]["x"] = "y"
    second = read(tmp_path, "a")

    assert second["requirements"]["threshold"]["description"] == "Text"
    assert second["dependencies"] == {}
    assert second is not first


def test_requirements_can_depend_on_each_other(tmp_path):
    requirement(tmp_path, "a", ["b"])
    requirement(tmp_path, "b", ["c"])
    requirement(tmp_path, "c", ["a"])

    assert read(tmp_path, "a")["dependencies"] == {"b": "b"}
    assert read(tmp_path, "c")["dependencies"] == {"a": "a"}


@pytest.mark.parametrize("order", [["a", "b", "c"], ["c", "b", "a"], ["b", "a", "c"]])
def test_invalid_dependencies_are_reported_in_any_order(tmp_path, order):
    # a and b depend on each other, b depends on the invalid c
    requirement(tmp_path, "a", ["b"])
    requirement(tmp_path, "b", ["a", "c"])
    requirement(tmp_path, "c", valid=False)

    for name in order:
        with pytest.raises(strictyaml.YAMLValidationError):
            read(tmp_path, name)


def test_circular_references_that_are_resolved_fail(tmp_path):
    def schema(file, base_path):
        return Map({"name": Str(), Optional("next"): IdReference("./{id}.yaml", base_path, schema)})

    (tmp_path / "a.yaml").write_text("name: A\nnext: b\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("name: B\nnext: a\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Circular reference: a.yaml -> b.yaml -> a.yaml"):
        read_yaml(tmp_path / "a.yaml", schema, tmp_path)


def test_copies_refuse_unknown_types():
    assert copy_data({"a": [1, 2.5, True, None, "x"]}) == {"a": [1, 2.5, True, None, "x"]}
    with pytest.raises(TypeError, match="set"):
        copy_data({"a": {1, 2}})
