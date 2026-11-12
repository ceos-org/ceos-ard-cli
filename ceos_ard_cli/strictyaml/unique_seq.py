import strictyaml

from .errors import fail


class UniqueSeq(strictyaml.UniqueSeq):
    def validate(self, chunk):
        existing_items = set()
        for item in chunk.expect_sequence("when expecting a unique sequence"):
            # First, as only a valid item (a scalar) can be compared
            item.process(self._validator(item))
            if item.contents in existing_items:
                fail(item, f"'{item.contents}' is listed more than once")
            existing_items.add(item.contents)
