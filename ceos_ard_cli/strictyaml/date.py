import re
from datetime import date

import strictyaml

from .errors import fail

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class Date(strictyaml.ScalarValidator):
    def validate_scalar(self, chunk):
        text = chunk.contents
        try:
            # fromisoformat alone also accepts other forms, e.g. 20260131
            valid = ISO_DATE.fullmatch(text) is not None and date.fromisoformat(text) is not None
        except ValueError:
            valid = False
        if not valid:
            fail(chunk, f"expecting a date as YYYY-MM-DD (e.g. 2026-01-31), found '{text}'")
        return text

    def to_yaml(self, data):
        return data
