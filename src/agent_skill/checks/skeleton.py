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
lazy from collections.abc import Iterable, Iterator

from agent_skill import shared, vocabulary
from agent_skill.checks import check, per_skill
from agent_skill.doc import ListBlock, Paragraph, Table, printed
from agent_skill.doc.chapter import CONTENTS, Demoted, Removed
from agent_skill.ids import RuleId
from agent_skill.model import SKILL_MD
from agent_skill.report import Level, declare, fail
lazy from agent_skill.doc.chapter import Section
lazy from agent_skill.model import Chapter, Skill
lazy from agent_skill.report import Finding

#: The reference map's columns, in order.
MAP_HEADER = ("File", "Rule IDs", "Covers")

#: The chapter that keeps the rename tables.
MIGRATION = "migration.md"

# The branches a finding of this check comes from.
TITLE = declare("skeleton", "title", Level.FAIL)
SECTION = declare("skeleton", "section", Level.FAIL)
EXTRA_SECTION = declare("skeleton", "extra_section", Level.FAIL)
MAP_COLUMNS = declare("skeleton", "map_columns", Level.FAIL)
REVIEW_ORDER = declare("skeleton", "review_order", Level.FAIL)
CHAPTER_NAME = declare("skeleton", "chapter_name", Level.FAIL)
UNREAD = declare("skeleton", "unread", Level.FAIL)
FAMILY = declare("skeleton", "family", Level.FAIL)
REQUIRED_CHAPTER = declare("skeleton", "required_chapter", Level.FAIL)
REVIEW_TITLE = declare("skeleton", "review_title", Level.FAIL)
REVIEW_SECTIONS = declare("skeleton", "review_sections", Level.FAIL)
SEVERITY = declare("skeleton", "severity", Level.FAIL)
RENAME_SELF = declare("skeleton", "rename_self", Level.FAIL)
RENAME_TARGET = declare("skeleton", "rename_target", Level.FAIL)
RENAME_LINT = declare("skeleton", "rename_lint", Level.FAIL)
RENAME_REASON = declare("skeleton", "rename_reason", Level.FAIL)
RENAME_SHAPE = declare("skeleton", "rename_shape", Level.FAIL)
NO_RANGES = declare("skeleton", "no_ranges", Level.FAIL)
UNCHANGED_GONE = declare("skeleton", "unchanged_gone", Level.FAIL)


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
    rows = {(row.tool, row.lint) for c in skill.chapters for row in c.typed.tools}
    where = skill.at(MIGRATION)
    for table in (t for c in skill.chapters for t in c.typed.renames):
        for r in table.rows:
            match r.now:
                case RuleId() as target if target == r.before:
                    yield fail(
                        f"{r.before} is listed as becoming itself; "
                        "an unchanged ID has no row",
                        where,
                        RENAME_SELF,
                    )
                case RuleId() as target if target not in skill.ids:
                    yield fail(
                        f"{r.before} is renamed to {target}, which no rule carries",
                        where,
                        RENAME_TARGET,
                    )
                case Demoted(tool, lint) if (tool, lint) not in rows:
                    yield fail(
                        f"{r.before} became the lint `{tool}:{lint}`, "
                        "which no chapter lists",
                        where,
                        RENAME_LINT,
                    )
                case Removed(reason) if not reason:
                    yield fail(
                        f"{r.before} was removed and the table gives no reason",
                        where,
                        RENAME_REASON,
                    )
        for before, now in table.unread:
            yield fail(
                f"{before.strip('`')} became `{now}`; a rename is a rule ID, "
                f"lint `tool:name`, or removed — reason",
                where,
                RENAME_SHAPE,
            )


def _unchanged(skill: Skill) -> Iterator[Finding]:
    """A table states its ranges, and an unlisted ID in range is a rule.

    An ID in range without a row is still a rule: the table says that ID
    is unchanged.
    """
    where = skill.at(MIGRATION)
    for table in (t for c in skill.chapters for t in c.typed.renames):
        if not table.ranges:
            yield fail(
                f"`## {table.heading}` states no ranges, "
                "so an unlisted ID reads as unchanged",
                where,
                NO_RANGES,
            )
        for rid in table.unchanged:
            if rid not in skill.ids:
                yield fail(
                    f"{rid} has no row, so the table says it is unchanged, "
                    "and no rule carries it",
                    where,
                    UNCHANGED_GONE,
                )


def _skill_md(skill: Skill) -> Iterator[Finding]:
    """`SKILL.md`'s title, sections, reference map and review order."""
    md = skill.typed
    where = skill.at(SKILL_MD)
    h1 = f"# {md.title}" if md.title else ""
    if h1 != (want := shared.title(skill)):
        yield fail(f"the title is `{h1}`, expected `{want}`", where, TITLE)
    found = [s.title for s in md.sections]
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

    table = next(_tables(_section(md.sections, "6. Reference map")), None)
    if table is not None and table.header != MAP_HEADER:
        yield fail(
            f"the reference map's columns are `{printed(table)[0]}`, "
            f"expected `| {' | '.join(MAP_HEADER)} |`",
            where,
            MAP_COLUMNS,
        )

    if (review := _protocol(skill)) is not None:
        stages = _items(_section(review.typed.sections, "Review order"))
        listed = _items(_section(md.sections, "5. Review checklist"))
        if stages != listed:
            yield fail(
                f"section 5 lists {listed} and the protocol's review order is "
                f"{stages}; section 5 is that order",
                where,
                REVIEW_ORDER,
            )


def _chapters(skill: Skill) -> Iterator[Finding]:
    """Each chapter reads as one, has a shared name, holds its family.

    A chapter the chapter layer refuses reads as one with no rules, so
    every other check passes over it; this is where the run fails.
    """
    stems = {c.path.stem for c in skill.chapters}
    for chapter in skill.chapters:
        if chapter.refused is not None:
            yield fail(
                f"`{chapter.name}` does not read as a chapter: {chapter.refused}",
                chapter.where(),
                UNREAD,
            )
        stem = chapter.path.stem
        if not vocabulary.allowed(stem):
            yield fail(
                f"`{chapter.name}` is not a chapter name in the shared vocabulary",
                chapter.where(),
                CHAPTER_NAME,
            )
            continue
        code = vocabulary.code_for(stem)
        for rule in chapter.typed.rules:
            if rule.id.family != code:
                yield fail(
                    f"{rule.id} lives in `{chapter.name}`, whose family is `{code}`",
                    chapter.where(rule.line),
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
    if (review := _protocol(skill)) is None:
        return
    protocol = review.typed
    where = skill.at(shared.REVIEW)
    h1 = f"# {protocol.title}" if protocol.title else ""
    if h1 != "# Review protocol":
        yield fail(
            f"the review protocol's title is `{h1}`, expected `# Review protocol`",
            where,
            REVIEW_TITLE,
        )
    contents = (CONTENTS,) if protocol.contents is not None else ()
    found = (*contents, *(s.title for s in protocol.sections))
    if found != shared.REVIEW_SECTIONS:
        expected = list(shared.REVIEW_SECTIONS)
        yield fail(
            f"the protocol's sections are {list(found)}, expected {expected}",
            where,
            REVIEW_SECTIONS,
        )
    rows = _severity_rows(_section(protocol.sections, "Severity model"))
    if rows != list(shared.SEVERITIES):
        yield fail(
            "the severity model is "
            f"{[label for label, _ in rows]}, "
            f"expected {[label for label, _ in shared.SEVERITIES]} "
            "with the shared meanings",
            where,
            SEVERITY,
        )


def _protocol(skill: Skill) -> Chapter | None:
    """The skill's review protocol, if it ships one."""
    path = skill.root / shared.REVIEW
    return next((c for c in skill.chapters if c.path == path), None)


def _section(sections: Iterable[Section], title: str) -> Section | None:
    """The section titled `title`, if there is one."""
    return next((s for s in sections if s.title == title), None)


def _tables(section: Section | None) -> Iterator[Table]:
    """Each table a section holds before its first rule."""
    if section is not None:
        yield from (b for b in section.lead if isinstance(b, Table))


def _severity_rows(section: Section | None) -> list[tuple[str, str]]:
    """Each severity a table states: its bold label, and its meaning."""
    return [
        (m.group(1), row[1])
        for table in _tables(section)
        for row in table.rows
        if len(row) > 1 and (m := re.fullmatch(r"\*\*(\w+)\*\*", row[0]))
    ]


def _items(section: Section | None) -> list[str]:
    """The bold titles of a section's numbered items.

    `1. **Soundness.**` -> `Soundness.`.
    """
    if section is None:
        return []
    return [
        m.group(1)
        for block in section.lead
        if isinstance(block, ListBlock) and block.start is not None
        for item in block.items
        if item.blocks and isinstance(lead := item.blocks[0], Paragraph)
        if (m := re.match(r"\*\*(.+?)\*\*", lead.text))
    ]
