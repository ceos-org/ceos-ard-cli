import re
from pathlib import Path

import bibtexparser
import strictyaml

from ..utils.files import content_file, fix_path, read_file
from ..utils.yaml import read_yaml, skip_if_being_read
from .errors import ReferencedFileError, fail

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
    # strictyaml's default is the class name
    rule_description = "an id"

    def __init__(self, path_template, base_path, schema=None, resolve=True):
        self._path_template = path_template
        self._base_path = base_path
        self._schema = schema
        self._resolve = resolve

    def validate_scalar(self, chunk):
        content = None
        id = chunk.contents
        try:
            file = content_file(self._base_path, self._path_template.format(id=id))
        except ValueError:
            fail(chunk, f"'{id}' points outside of the content folder")
        path = fix_path(file.relative_to(Path(self._base_path).resolve()))
        if not file.exists():
            fail(chunk, f"'{id}' doesn't exist, there's no file {path}")
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
                raise ReferencedFileError(chunk, path, "isn't valid bibtex")
            elif len(library.entries) != 1:
                raise ReferencedFileError(chunk, path, f"must contain a single bibtex entry, found {count}")
            elif (key := library.entries[0].key) != file.stem:
                message = f"the bibtex key must be '{file.stem}' as the file name, found '{key}'"
                raise ReferencedFileError(chunk, path, message)
            elif problems := bibtex_field_problems(library.entries[0]):
                raise ReferencedFileError(chunk, path, f"invalid bibtex fields: {'; '.join(problems)}")
        else:
            content = read_file(file)

        if self._resolve:
            return content
        else:
            return chunk.contents

    def to_yaml(self, data):
        return data
