"""What a chapter may be called, and the family code its rules carry.

One table for every standard, so that a reader who knows where
`rust-style` keeps its errors knows where `python-style` keeps them too.
Before it, two standards written a year apart spelled the same chapter
`errors.md` and `errors-and-control-flow.md`, and coded the same family
in three letters in one and four in the next, because each copied
whichever sibling its author had open.

A chapter name is one word. A check cannot tell `free-threading` (one
concept) from `traits-generics` (two), but a table can, so the table is
the rule.

Rows are only ever added. Renaming one would rename a chapter in every
standard that has it, which is a renumbering, not an edit to this file.
"""

#: chapter stem -> rule family code
CHAPTERS: dict[str, str] = {
    "naming": "NAME",
    "api": "API",
    "errors": "ERR",
    "functional": "FUNC",
    "ownership": "OWN",
    "traits": "TRAIT",
    "types": "TYPE",
    "data": "DATA",
    "modules": "MOD",
    "concurrency": "CONC",
    "async": "ASYNC",
    "output": "OUT",
    "performance": "PERF",
    "testing": "TEST",
    "documentation": "DOC",
    "build": "BUILD",
    "unsafe": "UNSAFE",
    "cli": "CLI",
    "macros": "MACRO",
    "migration": "MIG",
    "architecture": "ARCH",
    "ecs": "ECS",
    "scheduling": "SCHED",
    "events": "EVENT",
    "state": "STATE",
    "assets": "ASSET",
    "view": "VIEW",
    "assertions": "ASSERT",
    "comptime": "COMPTIME",
    "memory": "MEM",
    "interop": "INTEROP",
}

#: The family of the rules `SKILL.md` states itself.
CORE = "CORE"

#: The one chapter outside the table: it owns no rules, so it has no
#: code.
REVIEW = "review-checklist"

#: Chapters every standard ships.
REQUIRED: tuple[str, ...] = ("migration", REVIEW)


def code_for(stem: str) -> str:
    """The family code of a chapter.

    "" for a chapter the table does not name.
    """
    return CHAPTERS.get(stem, "")


def allowed(stem: str) -> bool:
    """May a chapter file be called this?"""
    return stem in CHAPTERS or stem == REVIEW
