from strictyaml import  Map, Str, Seq, UniqueSeq, EmptyList, Optional, NullNone, EmptyDict
from .yaml.id_reference import IdReference
from .yaml.md_reference import MdReference
from .yaml.markdown import Markdown

REFERENCE_PATH = "./references/{id}.bib"
GLOSSARY_PATH = "./glossary/{id}.yaml"
INTRODUCTION_PATH = "./sections/introduction/{id}.yaml"
ANNEX_PATH = "./sections/annexes/{id}.yaml"
REQUIREMENT_CATEGORY_PATH = "./sections/requirement-categories/{id}.yaml"
REQUIREMENT_PATH = "./requirements/{id}.yaml"

_REFS = lambda path, schema: EmptyList() | UniqueSeq(IdReference(path, schema))
_SECTION_IDS = lambda path: _REFS(path, SECTION)
_REFERENCE_IDS = EmptyList() | UniqueSeq(IdReference(REFERENCE_PATH))

# The order is important
_MARKDOWN = lambda file: Markdown() | MdReference(file)

_REQUIREMENT_PART = lambda file: NullNone() | Map({
    'description': _MARKDOWN(file),
    Optional('notes', default = []): EmptyList() | Seq(_MARKDOWN(file)),
})

AUTHORS = lambda file: Seq(Map({
    'name': Str(),
    Optional('country', default = ''): Str(),
    'members': UniqueSeq(Str()),
}))

GLOSSARY = lambda file: Map({
    'term': Str(),
    'description': _MARKDOWN(file),
})
_GLOSSARY_IDS = _REFS(GLOSSARY_PATH, GLOSSARY)

SECTION = lambda file: Map({
    Optional('id', default = ""): Str(),
    'title': Str(),
    'description': _MARKDOWN(file),
    Optional('glossary', default = []): _GLOSSARY_IDS,
    Optional('references', default = []): _REFERENCE_IDS,
})

PFS_DOCUMENT = lambda file: Map({
    'id': Str(),
    'title': Str(),
    'type': Str(),
    'applies_to': _MARKDOWN(file),
    Optional('introduction', default = []): _SECTION_IDS(INTRODUCTION_PATH),
    Optional('glossary', default = []): _GLOSSARY_IDS,
    Optional('references', default = []): _REFERENCE_IDS,
    Optional('annexes', default = []): _SECTION_IDS(ANNEX_PATH),
})

REQUIREMENT = lambda file: Map({
    'title': Str(),
    Optional('description', default = ""): Str(),
    'threshold': _REQUIREMENT_PART(file),
    "goal": _REQUIREMENT_PART(file),
    Optional('glossary', default = []): _GLOSSARY_IDS,
    Optional('references', default = []): _REFERENCE_IDS,
    Optional('metadata', default = {}): EmptyDict(), # todo: add metadata schema
    Optional('legacy', default = None): EmptyDict() | Map({
        'optical': NullNone() | Str(),
        'sar': NullNone() | Str(),
    })
})

REQUIREMENTS = lambda file: Seq(Map({
    'category': IdReference(REQUIREMENT_CATEGORY_PATH, SECTION),
    'requirements': UniqueSeq(IdReference(REQUIREMENT_PATH, REQUIREMENT)),
}))
