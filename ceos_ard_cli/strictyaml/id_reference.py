import re

import bibtexparser
import strictyaml

from ..utils.files import content_file, read_file
from ..utils.yaml import read_yaml, skip_if_being_read

# The styles print the DOI after https://doi.org/, so the field must not contain the URL
DOI = re.compile(r"10\.\d{4,9}/\S+")


def bibtex_field_problems(entry) -> list[str]:
    problems = []
    for field in entry.fields:
        if isinstance(field.value, str) and field.value != field.value.strip():
            problems.append(f"'{field.key}' has leading or trailing whitespace")
        elif field.key.lower() == "doi" and not DOI.fullmatch(field.value):
            problems.append(f"'doi' must be a bare DOI such as 10.1234/abc, found '{field.value}'")
    return problems


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
            # A dependency on a file that is being read (e.g. requirements that depend on each other)
            # is validated by that read already
            if self._resolve or not skip_if_being_read(file):
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
            elif problems := bibtex_field_problems(library.entries[0]):
                chunk.expecting_but_found(f"expecting valid bibtex fields in {file}: {'; '.join(problems)}")
        else:
            content = read_file(file)

        if self._resolve:
            return content
        else:
            return chunk.contents

    def to_yaml(self, data):
        return data
