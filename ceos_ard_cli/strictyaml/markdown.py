import strictyaml


class Markdown(strictyaml.Str):
    def validate_scalar(self, chunk):
        # ToDo: Validate markdown

        return super().validate_scalar(chunk)
