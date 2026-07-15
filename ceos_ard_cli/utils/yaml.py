import strictyaml

from ..utils.files import read_file

# todo: We have some requirements that depend on each other in a circular way.
#       This is a very dirty hack to avoid recursion depth errors.
#       We should find a way avoid this hack and stop once a reference is resolved twice in a tree of references.
YAML_DEPTH = 0


def read_yaml(file, schema, base_path):
    global YAML_DEPTH
    if YAML_DEPTH > 5:
        return {}
    yaml = read_file(file)
    if not schema:
        raise (ValueError(f"Schema is not provided for {file}"))
    YAML_DEPTH += 1
    try:
        return to_py(strictyaml.load(yaml, schema(file, base_path)))
    finally:
        # always restore the depth, even if parsing fails,
        # so that a failed file doesn't affect subsequent reads
        YAML_DEPTH -= 1


def to_py(data):
    if isinstance(data, strictyaml.Map):
        return {k: to_py(v) for k, v in data.items()}
    elif isinstance(data, strictyaml.Seq):
        return [to_py(v) for v in data]
    else:
        if hasattr(data, "data"):
            return data.data
        else:
            return data
