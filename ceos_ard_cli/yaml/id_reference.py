import strictyaml
from pathlib import Path
from .yaml_util import read_yaml

class IdReference(strictyaml.ScalarValidator):
    def __init__(self, path_template, schema = None):
        self._path_template = path_template
        self._schema = schema

    def validate_scalar(self, chunk):
        file = Path(self._path_template.format(id=chunk.contents))
        if not file.exists():
            chunk.expecting_but_found(f"expecting an existing file at {file} for id '{chunk.contents}'")

        if file.suffix == '.yaml':
            yaml = read_yaml(file, self._schema)
            if 'id' not in yaml or len(yaml['id']) == 0:
                yaml['id'] = chunk.contents
            return yaml
        elif file.suffix == '.bib':
            # don't load bibtex files, they are handled by pandoc
            return chunk.contents
        else:
            with open(file, 'r', encoding="utf-8") as f:
                return f.read()

    def to_yaml(self, data):
        return data
