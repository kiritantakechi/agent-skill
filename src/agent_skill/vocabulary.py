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

#: The review protocol: a chapter outside the table, which owns no
#: rules, so it has no code.
REVIEW = "review-checklist"

#: The rename history: every rule ID a revision changed, and what it
#: became. Not a chapter at all — it owns no rules and nothing on the
#: reading path loads it — but it ships beside them, so it is named here
#: rather than allowed by a second list somewhere else.
RENAMES = "renames"

#: The files under `references/` that have no family code, because none
#: owns a rule.
UNCODED: tuple[str, ...] = (REVIEW, RENAMES)

#: Chapters every standard ships. The rename history is not one: a
#: standard no revision has renumbered has none.
REQUIRED: tuple[str, ...] = ("migration", REVIEW)


def code_for(stem: str) -> str:
    """The family code of a chapter.

    "" for a chapter the table does not name.
    """
    return CHAPTERS.get(stem, "")


def allowed(stem: str) -> bool:
    """May a file under `references/` be called this?"""
    return stem in CHAPTERS or stem in UNCODED
