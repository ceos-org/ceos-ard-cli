import strictyaml
from pathlib import Path
from .yaml_util import read_yaml

class IdReference(strictyaml.ScalarValidator):
    def __init__(self, path_template, schema = None, resolve = True):
        self._path_template = path_template
        self._schema = schema
        self._resolve = resolve

    def validate_scalar(self, chunk):
        file = Path(self._path_template.format(id=chunk.contents))
        if not file.exists():
            chunk.expecting_but_found(f"expecting an existing file at {file} for id '{chunk.contents}'")

        if not self._resolve:
            return chunk.contents
        elif file.suffix == '.yaml':
            yaml = read_yaml(file, self._schema)
            if 'id' not in yaml or len(yaml['id']) == 0:
                yaml['id'] = chunk.contents
            return yaml
        else:
            with open(file, 'r', encoding="utf-8") as f:
                return f.read()

    def to_yaml(self, data):
        return data
