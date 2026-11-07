import strictyaml


class SingleLine(strictyaml.Str):
    """Plain text that ends up in headings, labels or table cells: line breaks and runs of whitespace become a space."""

    def validate_scalar(self, chunk):
        return " ".join(super().validate_scalar(chunk).split())
