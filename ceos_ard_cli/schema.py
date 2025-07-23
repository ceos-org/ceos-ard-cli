from strictyaml import (
    EmptyDict,
    EmptyList,
    Map,
    NullNone,
    Optional,
    Seq,
    Str,
    UniqueSeq,
)

from .strictyaml.id_reference import IdReference
from .strictyaml.markdown import Markdown
from .strictyaml.md_reference import MdReference

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

_MARKDOWN = lambda file, base_path: Markdown() | MdReference(
    file, base_path
)  # The order is important

_REQUIREMENT_PART = lambda file, base_path: NullNone() | Map(
    {
        "description": _MARKDOWN(file, base_path),
        Optional("notes", default=[]): EmptyList()
        | Seq(_MARKDOWN(file, base_path) | MdReference(file, base_path)),
    }
)

AUTHORS = lambda file, base_path: Seq(
    Map(
        {
            "name": Str(),
            Optional("country", default=""): Str(),
            "members": UniqueSeq(Str()),
        }
    )
)

GLOSSARY = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        "term": Str(),
        "description": _MARKDOWN(file, base_path),
    }
)
_RESOLVED_GLOSSARY = lambda base_path: _RESOLVED_REFS(
    GLOSSARY_PATH, base_path, GLOSSARY
)

SECTION = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        Optional("id", default=""): Str(),
        "title": Str(),
        "description": _MARKDOWN(file, base_path),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
    }
)

PFS_DOCUMENT = lambda file, base_path: Map(
    {
        "id": Str(),
        "title": Str(),
        "version": Str(),
        "type": Str(),
        "applies_to": _MARKDOWN(file, base_path),
        Optional("introduction", default=[]): _RESOLVED_SECTIONS(
            INTRODUCTION_PATH, base_path
        ),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
        Optional("annexes", default=[]): _RESOLVED_SECTIONS(ANNEX_PATH, base_path),
    }
)

REQUIREMENT = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        "title": Str(),
        Optional("description", default=""): Str(),
        "threshold": _REQUIREMENT_PART(file, base_path),
        "goal": _REQUIREMENT_PART(file, base_path),
        Optional("dependencies", default=[]): _REFS(
            REQUIREMENT_PATH, base_path, REQUIREMENT
        ),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
        Optional("metadata", default={}): EmptyDict(),  # todo: add metadata schema
        Optional("legacy", default=None): EmptyDict()
        | Map(
            {
                "optical": NullNone() | Str(),
                "sar": NullNone() | Str(),
            }
        ),
    }
)

REQUIREMENTS = lambda file, base_path: Seq(
    Map(
        {
            "category": IdReference(REQUIREMENT_CATEGORY_PATH, base_path, SECTION),
            "requirements": UniqueSeq(
                IdReference(REQUIREMENT_PATH, base_path, REQUIREMENT)
            ),
        }
    )
)
