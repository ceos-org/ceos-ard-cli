import strictyaml

from ..utils.files import read_file

class MdReference(strictyaml.ScalarValidator):
    def __init__(self, file):
        self._base_path = file.parent

    def validate_scalar(self, chunk):
        if not chunk.contents.startswith('include:'):
            chunk.expecting_but_found(f"when expecting an include")

        name = chunk.contents[8:]
        file = self._base_path.joinpath(name + ".md")

        if not file.exists():
            chunk.expecting_but_found(f"when expecting a file at {file} for include '{name}'")

        return read_file(file) # todo: validate markdown

    def to_yaml(self, data):
        return data
