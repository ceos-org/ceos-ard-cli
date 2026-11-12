import strictyaml

from .errors import fail


class Markdown(strictyaml.Str):
    # The content is checked by the sanitize filter, with pandoc's parser, see `ceos-ard validate`

    def __init__(self, allow_empty=True):
        self._allow_empty = allow_empty

    def validate_scalar(self, chunk):
        text = super().validate_scalar(chunk)
        if not self._allow_empty and not text.strip():
            fail(chunk, "expecting text, found an empty value")
        return text
