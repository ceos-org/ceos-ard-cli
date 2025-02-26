import strictyaml

from ..utils.files import read_file

def read_yaml(file, schema):
    yaml = read_file(file)
    if not schema:
        raise(ValueError(f"Schema is not provided for {file}"))
    return to_py(strictyaml.load(yaml, schema(file)))

def to_py(data):
    if isinstance(data, strictyaml.Map):
        return {k: to_py(v) for k, v in data.items()}
    elif isinstance(data, strictyaml.Seq):
        return [to_py(v) for v in data]
    else:
        if hasattr(data, 'data'):
            return data.data
        else:
            return data
