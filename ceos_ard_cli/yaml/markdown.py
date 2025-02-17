import strictyaml

class Markdown(strictyaml.Str):

    def validate_scalar(self, chunk):
        if chunk.contents.startswith('include:'):
            chunk.expecting_but_found(f"when NOT expecting an include")

        # ToDo: Validate markdown

        return super().validate_scalar(chunk)
