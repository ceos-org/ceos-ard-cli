import strictyaml


class Markdown(strictyaml.Str):
    # The content is checked by the sanitize filter, with pandoc's parser, see `ceos-ard validate`
    pass
