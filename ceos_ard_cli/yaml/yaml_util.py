import strictyaml

def read_yaml(file, schema):
    with open(file, 'r', encoding="utf-8") as f:
        return to_py(strictyaml.load(f.read(), schema(file)))

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
