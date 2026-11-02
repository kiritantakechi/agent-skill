"""Demote a standard's rules to lint-table rows, merges or removals.

A rule whose whole content is one lint the shipped configuration enables
is a row in its chapter's `Decided by tools` table, not a rule. Demoting
one is three edits that have to agree: the rule and its contents line
go, the row arrives, and the rename table records what the old ID
became. So they are one operation, and nothing is written unless every
edit can be made.

It leaves two things. One is a gap in the chapter's numbering, which
`agent-skill renumber` closes. The other is any citation of a demoted
ID, which it reports for a person to resolve: whether a citation of a
rule that is now a lint should name the lint, the rule it merged into,
or nothing, is a reading decision.
"""

import re
from dataclasses import dataclass, field
from typing import TypedDict
lazy from collections.abc import Iterator
lazy from pathlib import Path

from agent_skill.ids import rule_id
from agent_skill.layout import SKILLS
from agent_skill.model import DECIDED, FENCE, Skill, unfenced
from agent_skill.renumber import RenumberError, _corpus, _segments, carry, heading
lazy from agent_skill.profiles import Profile


class DemoteError(Exception):
    """The demotion cannot be done as asked, and nothing was written."""


@dataclass
class Demotion:
    """What a demotion will rewrite and report."""

    skill: str
    #: demoted rule ID -> what the rename table now says it became
    dispositions: dict[str, str]
    #: path -> its rewritten text
    writes: dict[Path, str]
    #: citations of a demoted ID, for a person to resolve
    leftovers: list[str] = field(default_factory=list)


#: The four things a rule can become, each with the plan key that asks
#: for it.
KINDS = ("rows", "lint", "merge", "remove")


class Entry(TypedDict, closed=True, total=False):
    """One rule's entry in a demotion plan, under exactly one key."""

    #: the rows that replace the rule, as [tool, lint, level, forbids]
    rows: list[list[str]]
    #: a row that already exists, as [tool, lint]
    lint: list[str]
    #: the rule it was folded into
    merge: str
    #: why it is gone
    remove: str


#: The cells of a lint-table row: tool, lint, level, forbids.
_ROW_CELLS = 4

LEAD = (
    "A tool settles these on its own; the shipped configuration enables each "
    "at the level shown."
)

#: The lead of a table whose rows a compiler decides. A compiler ships
#: no configuration, so nothing about its rows is "enabled".
COMPILER_LEAD = (
    "The compiler rejects each of these on its own; no setting turns one off."
)

#: Tools whose rows are errors the compiler always reports.
COMPILERS = frozenset({"zig"})


def plan(
    repo: Path, name: str, asked: dict[str, Entry], profile: Profile | None = None
) -> Demotion:
    """Everything the demotion would do, checked, and nothing done yet.

    `asked` maps each rule ID to one of:
    `{"rows": [[tool, lint, level, forbids], …]}`, the rows that replace
    it, the first of which it becomes; `{"lint": [tool, lint]}`, a row
    that already exists; `{"merge": "ID"}`, the rule it was folded into;
    or `{"remove": "reason"}`.
    """
    asked = entries(asked)
    skill = Skill(repo / SKILLS / name, profile)
    if not skill.skill_md.is_file():
        msg = f"there is no skill called {name}"
        raise DemoteError(msg)
    dispositions = _dispositions(skill, name, asked)
    writes = _chapter_writes(skill, asked)

    migration = next((c for c in skill.chapters if c.path.stem == "migration"), None)
    if migration is None:
        msg = f"{name} has no references/migration.md for its rename table"
        raise DemoteError(msg)
    now = {rid: f"`{rid}`" for rid in skill.by_id} | dispositions
    try:
        text = carry(writes.get(migration.path, migration.text), heading(skill), now)
    except RenumberError as e:
        raise DemoteError(str(e)) from None
    writes[migration.path] = text

    demotion = Demotion(name, dispositions, writes)
    demotion.leftovers = list(_citations(repo, demotion))
    return demotion


def apply(demotion: Demotion) -> None:
    """Write every rewritten file. `demotion` is already checked."""
    for path, text in demotion.writes.items():
        path.write_text(text)


def entries(raw: object) -> dict[str, Entry]:
    """`raw`, a plan as `json.loads` reads it, checked for shape.

    A plan maps each rule ID to an object holding one of `KINDS`, and
    that key holds what `Entry` says it does. Anything else stops here,
    before a rule is read: a string where an entry belongs raised
    `AttributeError`, and an empty plan built a pattern that matched at
    every word boundary.
    """
    if not isinstance(raw, dict) or not raw:
        msg = "a plan is a JSON object naming at least one rule"
        raise DemoteError(msg)
    out: dict[str, Entry] = {}
    for rid, what in raw.items():
        one = isinstance(what, dict) and len(what) == 1
        kind, value = next(iter(what.items())) if one else ("", "")
        entry = _entry(kind, value) if one else None
        if entry is None:
            shape = _SHAPES.get(str(kind), f"say exactly one of {', '.join(KINDS)}")
            msg = f"{rid}: {shape}"
            raise DemoteError(msg)
        out[str(rid)] = entry
    return out


#: What each kind of entry holds, said as the refusal of anything else.
_SHAPES = {
    "rows": "rows are [tool, lint, level, forbids], and there is one",
    "lint": "a lint is [tool, lint]",
    "merge": "a merge names the rule it went into",
    "remove": "a removal needs its reason",
}


def _entry(kind: object, value: object) -> Entry | None:
    """`{kind: value}` as an `Entry`, or None when it is not one."""
    if kind == "rows" and isinstance(value, list):
        rows = [
            cells for row in value if (cells := _strings(row, _ROW_CELLS)) is not None
        ]
        if rows and len(rows) == len(value):
            return {"rows": rows}
    elif kind == "lint" and (lint := _strings(value, 2)) is not None:
        return {"lint": lint}
    elif kind == "merge" and isinstance(value, str):
        return {"merge": value}
    elif kind == "remove" and isinstance(value, str) and value.strip():
        return {"remove": value}
    return None


def _strings(value: object, n: int) -> list[str] | None:
    """`value` as a list of `n` strings, or None when it is not one."""
    if not isinstance(value, list):
        return None
    cells = [c for c in value if isinstance(c, str)]
    return cells if len(cells) == len(value) == n else None


def _dispositions(skill: Skill, name: str, asked: dict[str, Entry]) -> dict[str, str]:
    """What the rename table will say each rule in `asked` became.

    Every entry is checked before any chapter is touched: the rule must
    be a chapter rule, and what it becomes must be there to become.
    """
    by_id = skill.by_id
    core = {rid for rid, _, _ in skill.core_rules}
    added = {(r[0], r[1]) for what in asked.values() for r in what.get("rows", [])}
    known = {(r.tool, r.lint) for r in skill.lint_rows} | added
    kept = (set(by_id) | core) - set(asked)

    dispositions: dict[str, str] = {}
    for rid, what in asked.items():
        if rid not in by_id:
            msg = f"{name} has no chapter rule {rid}"
            raise DemoteError(msg)
        dispositions[rid] = _disposition(rid, next(iter(what)), what, kept, known)
    return dispositions


def _chapter_writes(skill: Skill, asked: dict[str, Entry]) -> dict[Path, str]:
    """Each chapter that holds a rule in `asked`, rewritten without it.

    The rows that replace a rule join the chapter's `Decided by tools`
    table, and an edit that would lose any other rule stops the run.
    """
    by_id = skill.by_id
    writes: dict[Path, str] = {}
    for chapter in skill.chapters:
        mine = [rid for rid in asked if by_id[rid].file == chapter.name]
        if not mine:
            continue
        text = chapter.text
        for rid in mine:
            text = _drop(text, rid)
        text = _prune(text)
        new_rows = [r for rid in mine for r in asked[rid].get("rows", [])]
        if new_rows:
            text = _add_rows(text, new_rows)
        kept = [r.id for r in chapter.rules if r.id not in mine]
        if _headings(text) != kept:
            msg = f"{chapter.name}: the edit would lose a rule it was not asked to"
            raise DemoteError(msg)
        if len(FENCE.findall(text)) % 2:
            msg = f"{chapter.name}: the edit would leave an example's fence open"
            raise DemoteError(msg)
        writes[chapter.path] = text
    return writes


def _disposition(
    rid: str, kind: str, what: Entry, kept: set[str], known: set[tuple[str, str]]
) -> str:
    """What the rename table says `rid` became.

    `what` is already the shape `entries` checks. A merge is into a rule
    this plan keeps.
    """
    if kind == "rows":
        rows = what["rows"]
        return f"lint `{rows[0][0]}:{rows[0][1]}`"
    if kind == "lint":
        lint = what["lint"]
        if tuple(lint) not in known:
            msg = f"{rid}: no chapter lists the lint `{lint[0]}:{lint[1]}`"
            raise DemoteError(msg)
        return f"lint `{lint[0]}:{lint[1]}`"
    if kind == "merge":
        into = what["merge"]
        if into not in kept:
            msg = f"{rid}: {into} is not a rule this standard keeps"
            raise DemoteError(msg)
        return f"`{into}`"
    return f"removed — {what['remove'].strip()}"


def _drop(text: str, rid: str) -> str:
    """`text` without the rule `rid` and its contents line.

    The rule runs to the next heading outside its examples.
    """
    heading = re.compile(rf"^### {re.escape(rid)} \[", re.MULTILINE)
    head = next(unfenced(heading, text), None)
    if head is None:
        msg = f"{rid}: no heading to remove"
        raise DemoteError(msg)
    nxt = next(unfenced(_HEADING, text, head.end()), None)
    text = text[: head.start()] + (text[nxt.start() :] if nxt else "")
    text, n = re.subn(
        rf"^[ \t]*- {re.escape(rid)} \[.*\n", "", text, count=1, flags=re.MULTILINE
    )
    if n == 0:
        msg = f"{rid}: no contents line to remove"
        raise DemoteError(msg)
    return text.rstrip("\n") + "\n"


#: A section or rule heading: where a rule ends.
_HEADING = re.compile(r"^#{2,3} ", re.MULTILINE)

#: A section with nothing left under it.
_EMPTIED = re.compile(r"^## (?!Contents$)(.+)\n\s*(?=^## |\Z)", re.MULTILINE)


def _prune(text: str) -> str:
    """`text` without the sections its demotions emptied.

    Their contents entries go with them.
    """
    while m := next(unfenced(_EMPTIED, text), None):
        title = m.group(1)
        text = text[: m.start()] + text[m.end() :]
        entry = rf"^- \*\*{re.escape(title)}\*\*\n(?![ \t]+- )"
        text = re.sub(entry, "", text, count=1, flags=re.MULTILINE)
    return text.rstrip("\n") + "\n"


def _add_rows(text: str, rows: list[list[str]]) -> str:
    """`text` with `rows` in its `Decided by tools` table.

    The table is started if there is none — in a section of its own, or
    under a `Decided by tools` heading that has no table yet. A new
    section goes before the rename tables, which close the migration
    chapter, and its contents line closes the contents list.
    """
    cells = [[c.replace("|", "\\|") for c in row] for row in rows]
    lines = [
        f"| {tool} | `{lint}` | {level} | {forbids} |"
        for tool, lint, level, forbids in cells
    ]
    lead = COMPILER_LEAD if rows[0][0] in COMPILERS else LEAD
    header = "| Tool | Lint | Level | Forbids |\n|---|---|---|---|\n"
    if table := re.search(rf"^## {DECIDED}\n", text, re.MULTILINE):
        nxt = re.compile(r"^## ", re.MULTILINE).search(text, table.end())
        body = text[table.end() : nxt.start() if nxt else len(text)]
        listed = set(re.findall(r"^\| (\S+) \| `([^`]+)` \|", body, re.MULTILINE))
        new = "".join(
            f"{ln}\n"
            for ln, row in zip(lines, rows, strict=True)
            if (row[0], row[1]) not in listed
        )
        piped = list(re.finditer(r"^\|.*\n", body, re.MULTILINE))
        if piped:
            end = table.end() + piped[-1].end()
            return text[:end] + new + text[end:]
        # A heading with no table under it: the table follows whatever
        # the section says, or the lead when it says nothing.
        said = text[: table.end()] + (body.rstrip("\n") or f"\n{lead}")
        rest = text[table.end() + len(body) :]
        return f"{said}\n\n{header}{new}" + (f"\n{rest}" if rest else "")

    section = f"## {DECIDED}\n\n{lead}\n\n{header}"
    section += "".join(f"{ln}\n" for ln in lines)
    renamed = re.search(r"^## Rule IDs before the .+ revision$", text, re.MULTILINE)
    if renamed:
        text = text[: renamed.start()] + section + "\n" + text[renamed.start() :]
    else:
        text = text.rstrip("\n") + "\n\n" + section
    head, sep, tail = text.partition("\n---\n")
    if not sep:
        msg = "the chapter has no contents list to name its new table in"
        raise DemoteError(msg)
    return head.rstrip("\n") + f"\n- {DECIDED}\n\n---\n" + tail


def _headings(text: str) -> list[str]:
    """The rule ID of every heading in `text`, in order."""
    heading = re.compile(rf"^### ({rule_id()}) \[", re.MULTILINE)
    return [m.group(1) for m in unfenced(heading, text)]


def _citations(repo: Path, demotion: Demotion) -> Iterator[str]:
    """Every citation of a demoted ID left in the repository.

    The skill's own rename tables are left out: they cite old IDs on
    purpose. Another skill's table cites it to say what replaced a rule
    of its own, and is read like any other text.
    """
    pattern = re.compile(rf"\b({'|'.join(map(re.escape, demotion.dispositions))})\b")
    root = repo / SKILLS / demotion.skill
    for path in _corpus(repo):
        text = demotion.writes.get(path) or path.read_text()
        own = root in path.parents
        pos = 0
        for segment, protected in _segments(text):
            if not (protected and own):
                for m in pattern.finditer(segment):
                    line = text[: pos + m.start()].count("\n") + 1
                    becomes = demotion.dispositions[m.group(1)]
                    where = path.relative_to(repo)
                    yield f"{where}:{line} cites {m.group(1)}, which is now {becomes}"
            pos += len(segment)
