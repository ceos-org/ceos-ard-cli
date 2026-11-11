import bibtexparser
import strictyaml

from ..utils.files import content_file, read_file
from ..utils.yaml import read_yaml


class IdReference(strictyaml.ScalarValidator):
    def __init__(self, path_template, base_path, schema=None, resolve=True):
        self._path_template = path_template
        self._base_path = base_path
        self._schema = schema
        self._resolve = resolve

    def validate_scalar(self, chunk):
        content = None
        try:
            file = content_file(self._base_path, self._path_template.format(id=chunk.contents))
        except ValueError:
            chunk.expecting_but_found(f"expecting an id inside of the content folder, found '{chunk.contents}'")
        if not file.exists():
            chunk.expecting_but_found(f"expecting an existing file at {file} for id '{chunk.contents}'")
        elif file.suffix == ".yaml":
            content = read_yaml(file, self._schema, self._base_path)
            if "id" not in content or len(content["id"]) == 0:
                content["id"] = chunk.contents
        elif file.suffix == ".bib":
            content = read_file(file)
            library = bibtexparser.parse_string(content)
            count = len(library.entries)
            if len(library.failed_blocks) > 0:
                chunk.expecting_but_found(f"expecting a valid bibtex entry at {file}")
            elif len(library.entries) != 1:
                chunk.expecting_but_found(f"expecting a single bibtex entry per file in {file}, found {count}")
            elif library.entries[0].key != file.stem:
                chunk.expecting_but_found(f"expecting bibtex identifier to match file name in {file}")
        else:
            content = read_file(file)

        if self._resolve:
            return content
        else:
            return chunk.contents

    def to_yaml(self, data):
        return data
