from strictyaml import (
    Bool,
    EmptyDict,
    EmptyList,
    Enum,
    Map,
    MapPattern,
    Optional,
    Regex,
    Seq,
    Str,
    UniqueSeq,
)

from .strictyaml.id_reference import IdReference
from .strictyaml.markdown import Markdown
from .utils.files import fix_path

REFERENCE_PATH = "./references/{id}.bib"
GLOSSARY_PATH = "./glossary/{id}.yaml"
INTRODUCTION_PATH = "./sections/introduction/{id}.yaml"
ANNEX_PATH = "./sections/annexes/{id}.yaml"
REQUIREMENT_CATEGORY_PATH = "./sections/requirement-categories/{id}.yaml"
REQUIREMENT_PATH = "./requirements/{id}.yaml"


_REFS = lambda path, base_path, schema=None, resolve=False: (
    EmptyList() | UniqueSeq(IdReference(path, base_path, schema, resolve))
)
_RESOLVED_REFS = lambda path, base_path, schema: _REFS(path, base_path, schema, resolve=True)
_RESOLVED_SECTIONS = lambda path, base_path: _RESOLVED_REFS(path, base_path, SECTION)
_REFERENCE_IDS = lambda base_path: _REFS(REFERENCE_PATH, base_path)
_DEPS = lambda path, base_path, schema=None: (
    EmptyDict() | MapPattern(Str(), IdReference(path, base_path, schema, resolve=False))
)

_REQUIREMENT_PART = Map(
    {
        "description": Markdown(),
        Optional("notes", default=[]): EmptyList() | Seq(Markdown()),
        Optional("metadata", default={}): EmptyDict(),  # todo: add metadata schema
        Optional("optional", default=False): Bool(),
    }
)

_REQUIREMENT_PART_OVERRIDE = Map(
    {
        Optional("description"): Markdown(),
        Optional("notes"): EmptyList() | Seq(Markdown()),
        Optional("metadata"): EmptyDict(),  # todo: add metadata schema
        Optional("optional"): Bool(),
    }
)


def get_empty_requirement_part():
    return {
        "description": "",
        "notes": [],
        "metadata": {},
    }


_CHANGES = EmptyList() | Seq(
    Map(
        {
            "date": Regex(r"\d{4}-\d{2}-\d{2}"),  # ISO date format
            "author": Str(),
            "change": Markdown(),
            "reason": Str(),
            "level": Enum(["major", "minor", "patch"]),
        }
    )
)

GLOSSARY = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        "term": Str(),
        "description": Markdown(),
    }
)
_RESOLVED_GLOSSARY = lambda base_path: _RESOLVED_REFS(GLOSSARY_PATH, base_path, GLOSSARY)

SECTION = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        Optional("id", default=""): Str(),
        "title": Str(),
        "description": Markdown(),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
        Optional("changes", default=[]): _CHANGES,
    }
)

PARTIAL_SECTION = lambda file, base_path: Map(
    {
        Optional("title"): Str(),
        Optional("description"): Markdown(),
        Optional("glossary"): _RESOLVED_GLOSSARY(base_path),
        Optional("references"): _REFERENCE_IDS(base_path),
        Optional("changes"): _CHANGES,
    }
)

REQUIREMENT = lambda file, base_path: Map(
    {
        Optional("filepath", default=fix_path(file)): Str(),
        "id": Str(),
        "title": Str(),
        Optional("description", default=""): Markdown(),
        "requirements": MapPattern(Str(), _REQUIREMENT_PART),
        Optional("dependencies", default={}): _DEPS(REQUIREMENT_PATH, base_path, REQUIREMENT),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
        Optional("changes", default=[]): _CHANGES,
        Optional("history", default=[]): EmptyList() | Seq(Str()),
    }
)

PARTIAL_REQUIREMENT = lambda file, base_path: Map(
    {
        Optional("title"): Str(),
        Optional("description"): Markdown(),
        Optional("requirements"): MapPattern(Str(), _REQUIREMENT_PART_OVERRIDE),
        Optional("dependencies"): _DEPS(REQUIREMENT_PATH, base_path, REQUIREMENT),
        Optional("glossary"): _RESOLVED_GLOSSARY(base_path),
        Optional("references"): _REFERENCE_IDS(base_path),
        Optional("changes"): _CHANGES,
        Optional("history"): Seq(Str()),
    }
)

PFS_DOCUMENT = lambda file, base_path: Map(
    {
        "title": Str(),
        "version": Str(),
        "type": Str(),
        "applies_to": Markdown(),
        "authors": Markdown() | Seq(Str()),
        Optional("introduction", default=[]): _RESOLVED_SECTIONS(INTRODUCTION_PATH, base_path),
        "requirements": Seq(
            Map(
                {
                    "category": Map(
                        {
                            "ref": IdReference(REQUIREMENT_CATEGORY_PATH, base_path, SECTION),
                            Optional("replace", default={}): EmptyDict() | PARTIAL_SECTION(file, base_path),
                            Optional("append", default={}): EmptyDict() | PARTIAL_SECTION(file, base_path),
                        }
                    )
                    | IdReference(REQUIREMENT_CATEGORY_PATH, base_path, SECTION),
                    "requirements": Seq(
                        Map(
                            {
                                "ref": IdReference(REQUIREMENT_PATH, base_path, REQUIREMENT),
                                Optional("replace", default={}): EmptyDict() | PARTIAL_REQUIREMENT(file, base_path),
                                Optional("append", default={}): EmptyDict() | PARTIAL_REQUIREMENT(file, base_path),
                            }
                        )
                        | IdReference(REQUIREMENT_PATH, base_path, REQUIREMENT)
                    ),
                }
            )
        ),
        Optional("glossary", default=[]): _RESOLVED_GLOSSARY(base_path),
        Optional("references", default=[]): _REFERENCE_IDS(base_path),
        Optional("annexes", default=[]): _RESOLVED_SECTIONS(ANNEX_PATH, base_path),
        Optional("changes", default=[]): _CHANGES,
    }
)
