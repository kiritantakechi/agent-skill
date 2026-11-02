"""Every standard has the same shape.

Four standards written at different times shared a shape because each
copied the last, which held until it did not: a fifth section numbered
and titled differently in one of them, a §7 missing from another, a
review protocol in three of four, two conventions for naming a chapter,
and family codes of three letters in one standard and four in the next
for the same concept. A reader who knows one standard should find their
way around any other by position alone.

What is checked is position and naming — the H1, the H2s and their
order, chapter names and family codes, the review protocol's sections
and severity model, and the agreement between §5 and the protocol's
review order. The words of the shared passages belong to `shared-text`.
"""

import re
lazy from collections.abc import Iterator

from agent_skill import shared, vocabulary
from agent_skill.checks import check, per_skill
from agent_skill.ids import Branch
from agent_skill.model import SKILL_MD
from agent_skill.report import fail
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

#: The reference map's columns, in order.
MAP_HEADER = "| File | Rule IDs | Covers |"

#: The chapter that keeps the rename tables.
MIGRATION = "migration.md"

# The branches a finding of this check comes from.
TITLE = Branch("skeleton", "title")
SECTION = Branch("skeleton", "section")
EXTRA_SECTION = Branch("skeleton", "extra_section")
MAP_COLUMNS = Branch("skeleton", "map_columns")
REVIEW_ORDER = Branch("skeleton", "review_order")
CHAPTER_NAME = Branch("skeleton", "chapter_name")
FAMILY = Branch("skeleton", "family")
REQUIRED_CHAPTER = Branch("skeleton", "required_chapter")
REVIEW_TITLE = Branch("skeleton", "review_title")
REVIEW_SECTIONS = Branch("skeleton", "review_sections")
SEVERITY = Branch("skeleton", "severity")
RENAME_SELF = Branch("skeleton", "rename_self")
RENAME_TARGET = Branch("skeleton", "rename_target")
RENAME_LINT = Branch("skeleton", "rename_lint")
RENAME_REASON = Branch("skeleton", "rename_reason")
RENAME_SHAPE = Branch("skeleton", "rename_shape")
NO_RANGES = Branch("skeleton", "no_ranges")
UNCHANGED_GONE = Branch("skeleton", "unchanged_gone")


@check("skeleton", "every standard has the same shape")
@per_skill
def skeleton(skill: Skill) -> Iterator[Finding]:
    """Departures from the shared shape."""
    yield from _skill_md(skill)
    yield from _chapters(skill)
    yield from _review(skill)
    yield from _renames(skill)
    yield from _unchanged(skill)


def _renames(skill: Skill) -> Iterator[Finding]:
    """Every rename row leads somewhere a reader can follow."""
    rows = {(row.tool, row.lint) for row in skill.lint_rows}
    ids = set(skill.by_id) | {rid for rid, _, _ in skill.core_rules}
    where = skill.at(MIGRATION)
    for r in skill.renames:
        if r.target == r.before:
            yield fail(
                f"{r.before} is listed as becoming itself; an unchanged ID has no row",
                where,
                RENAME_SELF,
            )
        elif r.target:
            if r.target not in ids:
                yield fail(
                    f"{r.before} is renamed to {r.target}, which no rule carries",
                    where,
                    RENAME_TARGET,
                )
        elif lint := r.lint:
            if lint not in rows:
                named = f"`{lint[0]}:{lint[1]}`"
                yield fail(
                    f"{r.before} became the lint {named}, which no chapter lists",
                    where,
                    RENAME_LINT,
                )
        elif r.removed is not None:
            if not r.removed:
                yield fail(
                    f"{r.before} was removed and the table gives no reason",
                    where,
                    RENAME_REASON,
                )
        else:
            yield fail(
                f"{r.before} became `{r.now}`; a rename is a rule ID, "
                f"lint `tool:name`, or removed — reason",
                where,
                RENAME_SHAPE,
            )


def _unchanged(skill: Skill) -> Iterator[Finding]:
    """A table states its ranges, and an unlisted ID in range is a rule.

    An ID in range without a row is still a rule: the table says that ID
    is unchanged.
    """
    ids = set(skill.by_id) | {rid for rid, _, _ in skill.core_rules}
    where = skill.at(MIGRATION)
    for table in skill.rename_tables:
        if not table.ranges:
            yield fail(
                f"`{table.heading}` states no ranges, "
                "so an unlisted ID reads as unchanged",
                where,
                NO_RANGES,
            )
        for rid in table.unchanged:
            if rid not in ids:
                yield fail(
                    f"{rid} has no row, so the table says it is unchanged, "
                    "and no rule carries it",
                    where,
                    UNCHANGED_GONE,
                )


def _skill_md(skill: Skill) -> Iterator[Finding]:
    """`SKILL.md`'s title, sections, reference map and review order."""
    text = skill.text
    where = skill.at(SKILL_MD)
    h1 = next((ln for ln in _outside_fences(text) if ln.startswith("# ")), "")
    if h1 != (want := shared.title(skill)):
        yield fail(f"the title is `{h1}`, expected `{want}`", where, TITLE)
    found = shared.h2s(text)
    expected = shared.skill_sections(skill)
    for i, title in enumerate(expected):
        got = found[i] if i < len(found) else "nothing"
        if got != title:
            yield fail(
                f"section {i + 1} of 8 should be `## {title}`, found `{got}`",
                where,
                SECTION,
            )
            break
    if len(found) > len(expected):
        yield fail(
            f"a section after the eighth: `## {found[len(expected)]}`",
            where,
            EXTRA_SECTION,
        )

    if span := shared.section(text, "6. Reference map"):
        table = [ln for ln in text.split("\n")[span[0] : span[1]] if ln.startswith("|")]
        if table and shared.normal(table[0]) != MAP_HEADER:
            yield fail(
                f"the reference map's columns are `{table[0]}`, "
                f"expected `{MAP_HEADER}`",
                where,
                MAP_COLUMNS,
            )

    review = skill.root / shared.REVIEW
    if review.is_file():
        stages = _items(review.read_text(), "Review order")
        listed = _items(text, "5. Review checklist")
        if stages != listed:
            yield fail(
                f"section 5 lists {listed} and the protocol's review order is "
                f"{stages}; section 5 is that order",
                where,
                REVIEW_ORDER,
            )


def _chapters(skill: Skill) -> Iterator[Finding]:
    """Chapters are named from the vocabulary and hold their family."""
    stems = {c.path.stem for c in skill.chapters}
    for chapter in skill.chapters:
        stem = chapter.path.stem
        if not vocabulary.allowed(stem):
            yield fail(
                f"`{chapter.name}` is not a chapter name in the shared vocabulary",
                chapter.where(),
                CHAPTER_NAME,
            )
            continue
        code = vocabulary.code_for(stem)
        for rule in chapter.rules:
            if rule.id.split("-")[1] != code:
                yield fail(
                    f"{rule.id} lives in `{chapter.name}`, whose family is `{code}`",
                    rule.where,
                    FAMILY,
                )
    for stem in vocabulary.REQUIRED:
        if stem not in stems:
            yield fail(
                f"every standard ships `references/{stem}.md`",
                skill.at(),
                REQUIRED_CHAPTER,
            )


def _review(skill: Skill) -> Iterator[Finding]:
    """The review protocol's title, sections and severity model."""
    path = skill.root / shared.REVIEW
    if not path.is_file():
        return
    text = path.read_text()
    where = skill.at(shared.REVIEW)
    h1 = next((ln for ln in _outside_fences(text) if ln.startswith("# ")), "")
    if h1 != "# Review protocol":
        yield fail(
            f"the review protocol's title is `{h1}`, expected `# Review protocol`",
            where,
            REVIEW_TITLE,
        )
    if (found := tuple(shared.h2s(text))) != shared.REVIEW_SECTIONS:
        expected = list(shared.REVIEW_SECTIONS)
        yield fail(
            f"the protocol's sections are {list(found)}, expected {expected}",
            where,
            REVIEW_SECTIONS,
        )
    rows = _severity_rows(text)
    if rows != list(shared.SEVERITIES):
        yield fail(
            "the severity model is "
            f"{[label for label, _ in rows]}, "
            f"expected {[label for label, _ in shared.SEVERITIES]} "
            "with the shared meanings",
            where,
            SEVERITY,
        )


def _severity_rows(text: str) -> list[tuple[str, str]]:
    span = shared.section(text, "Severity model")
    if span is None:
        return []
    return [
        (m.group(1), m.group(2).strip())
        for line in text.split("\n")[span[0] : span[1]]
        if (m := re.match(r"^\| \*\*(\w+)\*\* \| ([^|]+) \|", line))
    ]


def _items(text: str, heading: str) -> list[str]:
    """The bold titles of a section's numbered items.

    `1. **Soundness.**` -> `Soundness.`.
    """
    span = shared.section(text, heading)
    if span is None:
        return []
    lines = text.split("\n")[span[0] : span[1]]
    return [m.group(1) for ln in lines if (m := re.match(r"^\d+\. \*\*(.+?)\*\*", ln))]


def _outside_fences(text: str) -> Iterator[str]:
    fenced = False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield line
