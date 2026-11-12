import strictyaml

from .errors import fail


class SingleLine(strictyaml.Str):
    """Plain text that ends up in headings, labels or table cells: line breaks and runs of whitespace become a space."""

    def validate_scalar(self, chunk):
        text = " ".join(super().validate_scalar(chunk).split())
        if not text:
            fail(chunk, "expecting text, found an empty value")
        return text
