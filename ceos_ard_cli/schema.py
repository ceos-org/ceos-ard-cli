from strictyaml import (
    EmptyDict,
    EmptyList,
    Enum,
    Map,
    NullNone,
    Optional,
    Seq,
    Str,
    UniqueSeq,
)

from .strictyaml.id_reference import IdReference
from .strictyaml.markdown import Markdown

REFERENCE_PATH = "./references/{id}.bib"
GLOSSARY_PATH = "./glossary/{id}.yaml"
INTRODUCTION_PATH = "./sections/introduction/{id}.yaml"
ANNEX_PATH = "./sections/annexes/{id}.yaml"
REQUIREMENT_CATEGORY_PATH = "./sections/requirement-categories/{id}.yaml"
REQUIREMENT_PATH = "./requirements/{id}.yaml"


def fix_path(path):
    return str(path).replace("\\", "/")


_REFS = lambda path, base_path, schema=None, resolve=False: EmptyList() | UniqueSeq(
    IdReference(path, base_path, schema, resolve)
)
_RESOLVED_REFS = lambda path, base_path, schema: _REFS(
    path, base_path, schema, resolve=True
)
_RESOLVED_SECTIONS = lambda path, base_path: _RESOLVED_REFS(path, base_path, SECTION)
_REFERENCE_IDS = lambda base_path: _REFS(REFERENCE_PATH, base_path)

_REQUIREMENT_PART = NullNone() | Map({
    "description": Markdown(),
    Optional("notes", default=[]): EmptyList()
    | Seq(Markdown()),
})

_CHANGES = EmptyList() | Seq(Map({
    "date": Str(),
    "author": Str(),
    "change": Str(),
    "reason": Str(),
    "level": Enum(["major", "minor", "patch"]),
}))

GLOSSARY = lambda file, base_path: Map({
    Optional("filepath", default=fix_path(file)): Str(),
    "term": Str(),
    "description": Markdown(),
})
_RESOLVED_GLOSSARY = lambda base_path: _RESOLVED_REFS(
    GLOSSARY_PATH, base_path, GLOSSARY
)

SECTION = lambda file, base_path: Map({
    Optional("filepath", default=fix_path(file)): Str(),
    Optional("id", default=""): Str(),
    "title": Str(),
    "description": Markdown(),
    Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
    Optional("references", default=[]): _REFERENCE_IDS(base_path),
    Optional("changes", default=[]): _CHANGES,
})

PFS_DOCUMENT = lambda file, base_path: Map({
    "title": Str(),
    "version": Str(),
    "type": Str(),
    "applies_to": Markdown(),
    "authors": Markdown() | Seq(Str()),
    Optional("introduction", default=[]): _RESOLVED_SECTIONS(
        INTRODUCTION_PATH, base_path
    ),
    "requirements": Seq(Map({
        "category": IdReference(REQUIREMENT_CATEGORY_PATH, base_path, SECTION),
        "requirements": UniqueSeq(
            IdReference(REQUIREMENT_PATH, base_path, REQUIREMENT)
        ),
    })),
    Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
    Optional("references", default=[]): _REFERENCE_IDS(base_path),
    Optional("annexes", default=[]): _RESOLVED_SECTIONS(ANNEX_PATH, base_path),
    Optional("changes", default=[]): _CHANGES,
})

REQUIREMENT = lambda file, base_path: Map({
    Optional("filepath", default=fix_path(file)): Str(),
    "title": Str(),
    Optional("description", default=""): Str(),
    "threshold": _REQUIREMENT_PART,
    "goal": _REQUIREMENT_PART,
    Optional("dependencies", default=[]): _REFS(
        REQUIREMENT_PATH, base_path, REQUIREMENT
    ),
    Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
    Optional("references", default=[]): _REFERENCE_IDS(base_path),
    Optional("metadata", default={}): EmptyDict(),  # todo: add metadata schema
    Optional("changes", default=[]): _CHANGES,
    Optional("history", default=[]): EmptyList() | Seq(Str()),
})
