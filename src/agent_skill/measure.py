"""How far each standard is from the normal form, counted.

`normalize-the-standards` moves these counts a standard at a time: its
task 1.1 records them before any standard is normalised, and 7.2 after
all four are. What a check of the normal form decides is counted by
running that check over the standard read as normalised, so a count is
what the check will report there, not a second reading of the property;
the rest are read from the chapter layer and the shipped configuration,
each as its function says.
"""

import re
from collections import Counter
from dataclasses import replace
lazy from collections.abc import Iterable, Iterator, Sequence

from agent_skill import shared, vocabulary
from agent_skill.checks import anatomy, citations, prose, skeleton
from agent_skill.checks.frontmatter import described
from agent_skill.doc import Heading, Table, entry, text_of, walk
from agent_skill.doc.chapter import Element, citing
from agent_skill.doc.normal import qualified, quoted, runs
from agent_skill.ids import cited, leading
from agent_skill.model import Skill
lazy from agent_skill.ids import Branch

#: What each branch of the normal form counts, in the order of task 1.1.
_BRANCHES: tuple[tuple[str, Branch], ...] = (
    ("chapter titles carrying a family code", skeleton.TITLE_CODE),
    ("chapters with no `Scope:` paragraph", skeleton.NO_SCOPE),
    ("chapters with a section after `Decided by tools`", skeleton.DECIDED_LAST),
    ("chapters named outside §6 and a `Scope:`, no ID after", skeleton.CHAPTER_NAMED),
)
_RULES: tuple[tuple[str, Branch], ...] = (
    ("rules with their elements out of order", anatomy.ELEMENT_ORDER),
    ("rules holding a block no element holds", anatomy.STRAY),
    ("restated titles", anatomy.RESTATED_TITLE),
    ("rules with more than one GOOD or BAD", anatomy.POLARITY),
    ("relaxed forms on a rule that is not `[M!]`", anatomy.RELAXED_TIER),
)
_CITATIONS: tuple[tuple[str, Branch], ...] = (
    ("citations quoted", anatomy.QUOTED_CITATION),
    ("citations behind a chapter's path", anatomy.PATH_CITATION),
    ('prose "grep" Checks', anatomy.PROSE_GREP),
    ("rules restating the `[M!]` scope", anatomy.LOCAL_SCOPE),
    ("`[M]` and `[M!]` titles in the mood of advice", anatomy.ADVICE_TITLE),
)
_ROWS: tuple[tuple[str, Branch], ...] = (
    ("rows of a lint not set one by one, saying no reason", citations.ROW_REASON),
    ("rows of a lint another row, or the anchor's, lists", citations.ROWED_TWICE),
)
_REALITY: tuple[tuple[str, Branch], ...] = (
    ("section 2 laid out otherwise than 2.1-2.3", skeleton.REALITY_SECTIONS),
    ("a 2.2 subsection that is not its rendering", skeleton.REALITY_DRIFT),
    ("section 2 items naming no rule", skeleton.REALITY_OWNER),
)


def found(skill: Skill) -> Counter[Branch]:
    """What the normal form's checks find in `skill`, read as normal.

    `anatomy` and `skeleton`, and the lint bijection of `citations`:
    the checks that need no tool to say it.
    """
    normal = Skill(skill.root, replace(skill.profile, normalized=True))
    findings = (
        *anatomy.anatomy.each(normal),
        *skeleton.skeleton.each(normal),
        *citations.bijection(normal),
        *prose.dated(normal),
    )
    return Counter(f.branch for f in findings)


def measured(skill: Skill) -> dict[str, str]:
    """Each count, by what it counts, for one standard."""
    by = found(skill)

    def counted(rows: Iterable[tuple[str, Branch]]) -> dict[str, str]:
        return {label: str(by[branch]) for label, branch in rows}

    coded = [c for c in skill.chapters if vocabulary.code_for(c.path.stem)]
    statuses, declared, doubled = _migration(skill)
    subsections, lines = _reality(skill)
    return {
        "chapters with a family code": str(len(coded)),
        **counted(_BRANCHES),
        "rules": str(len(skill.chapter_rules)),
        "distinct element orders": str(_orders(skill)),
        **counted(_RULES),
        "citations bare": str(_bare(skill)),
        **counted(_CITATIONS),
        "core rules": str(len(skill.core)),
        "core rules at another tier than a rule they cite": str(_core_tiers(skill)),
        "lints the configuration sets one by one with no row": _lints(skill),
        "rules whose Check is only a lint": str(_only_lints(skill)),
        **counted(_ROWS),
        "migration status values used (declared)": f"{statuses} ({declared})",
        "old spellings in two migration rows": str(doubled),
        "section 2 subsections, lines": f"{subsections}, {lines}",
        **counted(_REALITY),
        "description characters": str(
            len(described(skill.doc.frontmatter or "") or "")
        ),
        "SKILL.md lines": str(len(skill.text.splitlines())),
        "statements dated by their writing": str(by[prose.DATED]),
    }


def table(skills: Sequence[Skill]) -> str:
    """Every count, a row each, a column per standard, as markdown."""
    columns = [measured(s) for s in skills]
    head = ["Measure", *(s.name for s in skills)]
    lines = [_row(head), _row(["---"] * len(head))]
    lines += [_row([label, *(c[label] for c in columns)]) for label in columns[0]]
    return "\n".join(lines)


def _row(cells: Iterable[str]) -> str:
    """One row of a markdown table."""
    return "| " + " | ".join(cells) + " |"


def _orders(skill: Skill) -> int:
    """How many orders the rules state their elements in.

    A run of one element counts once: two examples are one place.
    """
    return len({tuple(_runs(p.element for p in r.parts)) for r in skill.chapter_rules})


def _runs(elements: Iterable[Element]) -> Iterator[Element]:
    """`elements`, each run of one element once."""
    last: Element | None = None
    for element in elements:
        if element is not last:
            yield element
        last = element


def _bare(skill: Skill) -> int:
    """How many citations name a rule by its bare ID.

    A heading, a contents entry and a core rule's bold label name their
    own rule rather than cite one, and an ID after a chapter's path is
    the path's.
    """
    count = 0
    for doc in skill.docs.values():
        for block in citing(doc):
            for _, run in runs(block):
                skipped = {i + 1 for i, _, _ in qualified(run)}
                if entry(run) is not None or _labels(run):
                    skipped.add(0)
                for k, word in enumerate(run):
                    if k not in skipped:
                        count += len(list(cited(word))) - len(list(quoted(word)))
    return count


def _labels(run: Sequence[str]) -> bool:
    """Does `run` open with a core rule's bold label, `**ZS-CORE-01`?"""
    return bool(run) and run[0].startswith("**") and leading(run[0][2:]) is not None


def _core_tiers(skill: Skill) -> int:
    """How many core rules carry a tier other than a rule they cite."""
    tiers = {r.id: r.tier for r in skill.chapter_rules}
    return sum(
        1
        for core in skill.core
        if any(
            tiers.get(rid, core.tier) is not core.tier
            for rid in cited(text_of(core.body), skill.prefix)
        )
    )


def _lints(skill: Skill) -> str:
    """The lints owed a row that no row lists (`citations.unrowed`).

    "n of m", where m is every lint the configuration sets one by one
    to fail a run and this standard owes a row — a delta none it sets as
    its anchor does; "none" for a standard owed none.
    """
    missing, due = citations.unrowed(skill)
    return f"{missing} of {due}" if due else "none"


def _only_lints(skill: Skill) -> int:
    """How many rules have a Check that is a lint and nothing more.

    `citations.only_lint`: such a rule is that lint's row (decision 8).
    """
    return sum(1 for rule in skill.chapter_rules if citations.only_lint(rule))


#: The tables of a migration chapter that map nothing: what its tiers
#: or statuses mean, what a release added, and the tool rows.
_LEGENDS = frozenset({"Tier", "Status", "Feature", "API", "Since", "Tool"})

#: The header of the column a migration table keeps its old spelling in,
#: when it is not the first.
_OLD = "Not this"


def _migration(skill: Skill) -> tuple[int, int, int]:
    """The migration chapter's statuses, and old spellings given twice.

    How many status values it uses and declares, and how many old
    spellings two of its rows give. A status is a cell under `Status`;
    one is declared by a row of a table that opens with `Status`. An
    old spelling is the first code span of a row's old column — the
    first, or `Not this` — in every table that maps something.
    """
    chapter = next((c for c in skill.chapters if c.path.stem == "migration"), None)
    if chapter is None:
        return 0, 0, 0
    used: set[str] = set()
    declared: set[str] = set()
    olds: Counter[str] = Counter()
    for table in (b for b in walk(chapter.doc.blocks) if isinstance(b, Table)):
        header = [h.strip("`* ") for h in table.header]
        if "Status" in header:
            column = header.index("Status")
            states = {_plain(row[column]) for row in table.rows if len(row) > column}
            (declared if column == 0 else used).update(states)
        if header[0] in _LEGENDS:
            continue
        old = header.index(_OLD) if _OLD in header else 0
        for row in table.rows:
            if len(row) > old and (spelled := _spelling(row[old])):
                olds[spelled] += 1
    return len(used), len(declared), sum(1 for n in olds.values() if n > 1)


def _plain(cell: str) -> str:
    """A cell as a status is compared: no emphasis, no case."""
    return " ".join(cell.replace("*", "").replace("`", "").split()).lower()


def _spelling(cell: str) -> str:
    """The first code span of `cell`, or the cell when it has none."""
    m = re.search(r"`([^`]+)`", cell)
    return cell[m.start(1) : m.end(1)] if m else cell.strip()


def _reality(skill: Skill) -> tuple[int, int]:
    """Section 2's subsections, and the lines it runs to in the file."""
    title = shared.skill_sections(skill)[2]
    sections = skill.typed.sections
    at = next((i for i, s in enumerate(sections) if s.title == title), None)
    if at is None:
        return 0, 0
    section = sections[at]
    subsections = sum(
        1 for b in section.lead if isinstance(b, Heading) and b.level == _SUBSECTION
    )
    last = len(skill.text.splitlines()) + 1
    end = sections[at + 1].line if at + 1 < len(sections) else last
    return subsections, end - section.line


#: The level of a subsection's heading.
_SUBSECTION = 3
