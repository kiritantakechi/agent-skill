"""Demote a standard's rules: to a lint-table row, into another rule, or out of it.

A rule whose whole content is one lint the shipped configuration enables is a row in its
chapter's `Decided by tools` table, not a rule. Demoting one is three edits that have to agree:
the rule and its contents line go, the row arrives, and the rename table records what the old ID
became. So they are one operation, and nothing is written unless every edit can be made.

It leaves two things. One is a gap in the chapter's numbering, which `agent-skill renumber`
closes. The other is any citation of a demoted ID, which it reports for a person to resolve:
whether a pointer to a rule that is now a lint should name the lint, the rule it merged into, or
nothing, is a reading decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .model import DECIDED, Skill
from .renumber import RenumberError, _corpus, _segments, carry, heading


class DemoteError(Exception):
    """The demotion cannot be done as asked, and nothing was written."""


@dataclass
class Demotion:
    skill: str
    #: demoted rule ID -> what the rename table now says it became
    dispositions: dict[str, str]
    #: path -> its rewritten text
    writes: dict[Path, str]
    #: citations of a demoted ID, for a person to resolve
    leftovers: list[str] = field(default_factory=list)


#: The four things a rule can become, each with the plan key that asks for it.
KINDS = ("rows", "lint", "merge", "remove")

LEAD = "A tool settles these on its own; the shipped configuration enables each at the level shown."


def plan(repo: Path, name: str, asked: dict[str, dict], profile=None) -> Demotion:
    """Everything the demotion would do, checked, and nothing done yet.

    `asked` maps each rule ID to one of: `{"rows": [[tool, lint, level, forbids], …]}`, the
    rows that replace it, the first of which it becomes; `{"lint": [tool, lint]}`, a row that
    already exists; `{"merge": "ID"}`, the rule it was folded into; or `{"remove": "reason"}`.
    """
    skill = Skill(repo / "skills" / name, profile)
    by_id = skill.by_id
    core = {rid for rid, _, _ in skill.core_rules}
    added = {(r[0], r[1]) for what in asked.values() for r in what.get("rows", [])}
    known = {(r.tool, r.lint) for r in skill.lint_rows} | added
    kept = (set(by_id) | core) - set(asked)

    dispositions: dict[str, str] = {}
    for rid, what in asked.items():
        if rid not in by_id:
            raise DemoteError(f"{name} has no chapter rule {rid}")
        if len(what) != 1 or (kind := next(iter(what))) not in KINDS:
            raise DemoteError(f"{rid}: say exactly one of {', '.join(KINDS)}")
        dispositions[rid] = _disposition(rid, kind, what[kind], kept, known)

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
            raise DemoteError(f"{chapter.name}: the edit would lose a rule it was not asked to")
        writes[chapter.path] = text

    migration = next((c for c in skill.chapters if c.path.stem == "migration"), None)
    if migration is None:
        raise DemoteError(f"{name} has no references/migration.md for its rename table")
    now = {rid: f"`{rid}`" for rid in by_id} | dispositions
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


def _disposition(rid: str, kind: str, value, kept: set[str], known: set) -> str:
    """What the rename table says `rid` became. A merge is into a rule this plan keeps."""
    if kind == "rows":
        if not value or any(len(row) != 4 for row in value):
            raise DemoteError(f"{rid}: rows are [tool, lint, level, forbids], and there is one")
        return f"lint `{value[0][0]}:{value[0][1]}`"
    if kind == "lint":
        if tuple(value) not in known:
            raise DemoteError(f"{rid}: no chapter lists the lint `{value[0]}:{value[1]}`")
        return f"lint `{value[0]}:{value[1]}`"
    if kind == "merge":
        if value not in kept:
            raise DemoteError(f"{rid}: {value} is not a rule this standard keeps")
        return f"`{value}`"
    if not str(value).strip():
        raise DemoteError(f"{rid}: a removal needs its reason")
    return f"removed — {value.strip()}"


def _drop(text: str, rid: str) -> str:
    """`text` without the rule `rid` and its contents line."""
    head = re.search(rf"^### {re.escape(rid)} \[", text, re.M)
    if head is None:
        raise DemoteError(f"{rid}: no heading to remove")
    nxt = re.compile(r"^#{2,3} ", re.M).search(text, head.end())
    text = text[: head.start()] + (text[nxt.start() :] if nxt else "")
    text, n = re.subn(rf"^[ \t]*- {re.escape(rid)} \[.*\n", "", text, count=1, flags=re.M)
    if n == 0:
        raise DemoteError(f"{rid}: no contents line to remove")
    return text.rstrip("\n") + "\n"


def _prune(text: str) -> str:
    """`text` without the sections its demotions emptied, and their contents entries."""
    while m := re.search(r"^## (?!Contents$)(.+)\n\s*(?=^## |\Z)", text, re.M):
        title = m.group(1)
        text = text[: m.start()] + text[m.end() :]
        entry = rf"^- \*\*{re.escape(title)}\*\*\n(?![ \t]+- )"
        text = re.sub(entry, "", text, count=1, flags=re.M)
    return text.rstrip("\n") + "\n"


def _add_rows(text: str, rows: list[list[str]]) -> str:
    """`text` with `rows` in its `Decided by tools` table, which is started if it has none.

    A new table goes before the rename tables, which close the migration chapter, and its
    contents line closes the contents list.
    """
    cells = [[c.replace("|", "\\|") for c in row] for row in rows]
    lines = [f"| {tool} | `{lint}` | {level} | {forbids} |" for tool, lint, level, forbids in cells]
    if table := re.search(rf"^## {DECIDED}\n", text, re.M):
        nxt = re.compile(r"^## ", re.M).search(text, table.end())
        body = text[table.end() : nxt.start() if nxt else len(text)]
        listed = set(re.findall(r"^\| (\S+) \| `([^`]+)` \|", body, re.M))
        lines = [ln for ln, row in zip(lines, rows, strict=True) if (row[0], row[1]) not in listed]
        end = table.end() + list(re.finditer(r"^\|.*\n", body, re.M))[-1].end()
        return text[:end] + "".join(f"{ln}\n" for ln in lines) + text[end:]

    section = f"## {DECIDED}\n\n{LEAD}\n\n| Tool | Lint | Level | Forbids |\n|---|---|---|---|\n"
    section += "".join(f"{ln}\n" for ln in lines)
    renamed = re.search(r"^## Rule IDs before the .+ revision$", text, re.M)
    if renamed:
        text = text[: renamed.start()] + section + "\n" + text[renamed.start() :]
    else:
        text = text.rstrip("\n") + "\n\n" + section
    head, sep, tail = text.partition("\n---\n")
    if not sep:
        raise DemoteError("the chapter has no contents list to name its new table in")
    return head.rstrip("\n") + f"\n- {DECIDED}\n\n---\n" + tail


def _headings(text: str) -> list[str]:
    return re.findall(r"^### ([A-Z]{2}-[A-Z]+-\d+[a-z]?) \[", text, re.M)


def _citations(repo: Path, demotion: Demotion):
    """Every citation of a demoted ID left in the repository, rename tables aside."""
    pattern = re.compile(rf"\b({'|'.join(map(re.escape, demotion.dispositions))})\b")
    for path in _corpus(repo):
        text = demotion.writes.get(path) or path.read_text()
        pos = 0
        for segment, protected in _segments(text):
            if not protected:
                for m in pattern.finditer(segment):
                    line = text[: pos + m.start()].count("\n") + 1
                    becomes = demotion.dispositions[m.group(1)]
                    where = path.relative_to(repo)
                    yield f"{where}:{line} cites {m.group(1)}, which is now {becomes}"
            pos += len(segment)
