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
lazy from collections.abc import Iterable, Iterator, Sequence

from agent_skill import shared, vocabulary
from agent_skill.checks import check, per_skill
from agent_skill.doc import (
    Fence,
    Heading,
    ListBlock,
    Paragraph,
    Table,
    printed,
    text_of,
)
from agent_skill.doc.chapter import (
    CONTENTS,
    DECIDED,
    PROJECTED,
    RENAMED,
    STATUSES,
    Demoted,
    Entry,
    Removed,
    history,
    migration_header,
    migrations,
    reality_header,
)
from agent_skill.doc.normal import generated, listed, projection, reality, stated
from agent_skill.ids import RuleId, Version, cited, leading
from agent_skill.model import REFERENCES, RENAMES_MD, SKILL_MD
from agent_skill.report import Level, declare, fail
lazy from agent_skill.doc import Block, Doc
lazy from agent_skill.doc.chapter import Migration, RenameTable, Section
lazy from agent_skill.doc.normal import Mapped
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Chapter, Skill
lazy from agent_skill.report import Finding

#: The reference map's columns, in order.
MAP_HEADER = ("File", "Rule IDs", "Covers")

#: The file every rename table lives in, as a location names it.
RENAMES = f"{REFERENCES}/{RENAMES_MD}"

#: The chapter a reader holding an old ID opens, which names `RENAMES`.
MIGRATION = "migration.md"

#: The review protocol's title.
PROTOCOL = "Review protocol"

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
RENAME_ELSEWHERE = declare("skeleton", "rename_elsewhere", Level.FAIL)
RENAMES_NAMED = declare("skeleton", "renames_named", Level.FAIL)
RENAMES_ON_PATH = declare("skeleton", "renames_on_path", Level.FAIL)

# The branches of the normal form (`_normal_form`).
TITLE_CODE = declare("skeleton", "title_code", Level.FAIL)
NO_SCOPE = declare("skeleton", "no_scope", Level.FAIL)
DECIDED_LAST = declare("skeleton", "decided_last", Level.FAIL)
CHAPTER_NAMED = declare("skeleton", "chapter_named", Level.FAIL)
REALITY_SECTIONS = declare("skeleton", "reality_sections", Level.FAIL)
REALITY_OWNER = declare("skeleton", "reality_owner", Level.FAIL)
CORE_RULE = declare("skeleton", "core_rule", Level.FAIL)
CORE_DRIFT = declare("skeleton", "core_drift", Level.FAIL)
MIGRATION_TABLE = declare("skeleton", "migration_table", Level.FAIL)
MIGRATION_ROW = declare("skeleton", "migration_row", Level.FAIL)
MIGRATION_TWICE = declare("skeleton", "migration_twice", Level.FAIL)
MIGRATION_COMMAND = declare("skeleton", "migration_command", Level.FAIL)
CHANGED_DRIFT = declare("skeleton", "changed_drift", Level.FAIL)
GONE_DRIFT = declare("skeleton", "gone_drift", Level.FAIL)
SKILL_MD_LINES = declare("skeleton", "skill_md_lines", Level.FAIL)

#: `SKILL.md` is under this many lines: it is loaded whole, every time
#: the standard is, and a chapter is loaded only when it is needed.
SKILL_MD_BOUND = 500


@check("skeleton", "every standard has the same shape")
@per_skill
def skeleton(skill: Skill) -> Iterator[Finding]:
    """Departures from the shared shape."""
    yield from _skill_md(skill)
    yield from _chapters(skill)
    yield from _review(skill)
    yield from _home(skill)
    yield from _renames(skill)
    yield from _unchanged(skill)
    yield from _normal_form(skill)


def _history(skill: Skill) -> tuple[RenameTable, ...]:
    """The rename tables `renames.md` holds; none when there is none.

    A table anywhere else is read by nothing but `_home`, which says
    where it belongs: `revise` carries only these through a revision.
    """
    found = (c.typed.renames for c in skill.chapters if c.path == skill.renames_md)
    return next(found, ())


def _home(skill: Skill) -> Iterator[Finding]:
    """Every rename table is in `renames.md`, named once, off the path.

    The rename history was most of a migration chapter, loaded on every
    lookup of an old spelling. It lives apart now: the migration chapter
    names it once, for a reader holding an old ID, and `SKILL.md` never,
    so nothing on the reading path loads it.
    """
    for c in skill.chapters:
        if c.path != skill.renames_md and c.typed.renames:
            yield fail(
                f"`{c.name}` holds a rename table; every one lives in `{RENAMES}`",
                c.where(),
                RENAME_ELSEWHERE,
            )
    if any(RENAMED.fullmatch(s.title) for s in skill.typed.sections):
        yield fail(
            f"`{SKILL_MD}` holds a rename table; every one lives in `{RENAMES}`",
            skill.at(SKILL_MD),
            RENAME_ELSEWHERE,
        )
    migration = next((c for c in skill.chapters if c.name == MIGRATION), None)
    named = migration.text.count(RENAMES_MD) if migration is not None else 1
    if skill.renames_md.is_file() and named != 1:
        yield fail(
            f"`{MIGRATION}` names `{RENAMES_MD}` {named} times; once tells a reader "
            "holding an old ID where to look",
            skill.at(f"{REFERENCES}/{MIGRATION}"),
            RENAMES_NAMED,
        )
    if (at := skill.text.find(RENAMES_MD)) >= 0:
        yield fail(
            f"`{SKILL_MD}` names `{RENAMES_MD}`, which nothing on the reading path "
            "loads; the migration chapter names it",
            skill.at(SKILL_MD, skill.text.count("\n", 0, at) + 1),
            RENAMES_ON_PATH,
        )


def _rows(skill: Skill) -> set[tuple[str, str]]:
    """The lint rows a rename may lead to: its own, and its anchor's.

    A lint a delta sets as its anchor does is the anchor's row, one
    lint and one owner (normalize-the-standards, decision 8), so a delta
    rule demoted to it before is found there, as a reader finds it.
    """
    rows = {(row.tool, row.lint) for c in skill.chapters for row in c.typed.tools}
    if anchor := skill.profile.anchor:
        theirs = Skill(skill.root.parent / anchor, skill.profile)
        rows |= {(row.tool, row.lint) for c in theirs.chapters for row in c.typed.tools}
    return rows


def _renames(skill: Skill) -> Iterator[Finding]:
    """Every rename row leads somewhere a reader can follow."""
    rows = _rows(skill)
    where = skill.at(RENAMES)
    for table in _history(skill):
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
    where = skill.at(RENAMES)
    for table in _history(skill):
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
    if md.title != (want := shared.title(skill)).text:
        yield fail(
            f"the title is `{_h1(md.title)}`, expected `{_h1(want.text)}`",
            where,
            TITLE,
        )
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

    table = next(_tables(_section(md.sections, shared.MAP)), None)
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
    if protocol.title != PROTOCOL:
        yield fail(
            f"the review protocol's title is `{_h1(protocol.title)}`, "
            f"expected `{_h1(PROTOCOL)}`",
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


def _h1(title: str) -> str:
    """`title` as the file's first line spells it, "" for none."""
    return printed(Heading(1, title))[0] if title else ""


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


# ------------------------------------------------------------------
# the normal form (normalize-the-standards, decisions 1, 5, 7, 9 and 13)


def _normal_form(skill: Skill) -> Iterator[Finding]:
    """One chapter template, and sections 2 and 4 as projections."""
    yield from _template(skill)
    yield from _named(skill)
    yield from _reality(skill)
    yield from _core(skill)
    yield from _migration(skill)
    if (lines := len(skill.text.splitlines())) >= SKILL_MD_BOUND:
        yield fail(
            f"`{SKILL_MD}` runs {lines} lines; it is under {SKILL_MD_BOUND}, and what "
            "does not fit is a chapter's",
            skill.at(SKILL_MD),
            SKILL_MD_LINES,
        )


#: What a chapter's scope opens with.
SCOPE = "Scope:"


def _template(skill: Skill) -> Iterator[Finding]:
    """Each chapter opens with its concept and its scope (decision 1).

    A title, with no family code: the code is the file's, through the
    vocabulary. Then a `Scope:` paragraph; then the contents and the
    sections, `Decided by tools` last. The review protocol and the
    rename history own no rules and have no code, so they are not
    chapters of this template; a chapter the layer refuses is reported
    by `unread` and read no further.
    """
    for chapter in skill.chapters:
        code = vocabulary.code_for(chapter.path.stem)
        if not code or chapter.refused is not None:
            continue
        typed = chapter.typed
        if _coded(typed.title, skill.prefix):
            yield fail(
                f"`{chapter.name}` opens `{_h1(typed.title)}`; a title names the "
                f"chapter's concept, and `{skill.prefix}-{code}` is the file's",
                chapter.where(1),
                TITLE_CODE,
            )
        if not (typed.scope and _is_scope(typed.scope[0])):
            yield fail(
                f"`{chapter.name}` does not open with a `{SCOPE}` paragraph saying "
                "what it owns and which chapters neighbour it",
                chapter.where(),
                NO_SCOPE,
            )
        titles = [s.title for s in typed.sections]
        if DECIDED in titles and titles[-1] != DECIDED:
            yield fail(
                f"`{chapter.name}` puts `## {titles[-1]}` after `## {DECIDED}`, "
                "which is last",
                chapter.where(),
                DECIDED_LAST,
            )


def _coded(title: str, prefix: str) -> bool:
    """Does `title` open with a family code: `RS-BUILD — Cargo`?"""
    first = title.split(maxsplit=1)[0] if title else ""
    standard, dash, family = first.partition("-")
    codes = {*vocabulary.CHAPTERS.values(), vocabulary.CORE}
    return bool(dash) and standard == prefix and family in codes


def _is_scope(block: Block) -> bool:
    """Is `block` the paragraph that scopes a chapter?"""
    return isinstance(block, Paragraph) and block.text.startswith(SCOPE)


#: A chapter named by its file: `` `references/errors.md` ``, or
#: `` `errors.md` ``. Which stems are chapters is the vocabulary's.
_FILE = re.compile(r"`(?:references/)?(?P<stem>[a-z0-9-]+)\.md`")


def _named(skill: Skill) -> Iterator[Finding]:
    """A chapter is named only in section 6 and in a `Scope:` paragraph.

    Section 6 maps each family to its file, which is the one place a
    reader needs the path; a scope says which chapters neighbour this
    one. Anywhere else a citation is a bare rule ID (decision 3), and a
    chapter named in passing is a second map. A path a rule ID follows
    is a citation's, which `anatomy` reports and `fmt` drops, so it is
    not reported twice.
    """
    for path, doc in skill.docs.items():
        for block in _naming(doc, skill_md=path == skill.skill_md):
            text = text_of((block,))
            for m in _FILE.finditer(text):
                cites = leading(text[m.end() :].lstrip().removeprefix("`"))
                if vocabulary.code_for(m["stem"]) and cites is None:
                    line = block.line + text.count("\n", 0, m.start())
                    yield fail(
                        f"names the chapter {m.group(0)}; outside section 6 and a "
                        f"`{SCOPE}` paragraph a rule is cited by its ID",
                        skill.at(path, line),
                        CHAPTER_NAMED,
                    )


def _naming(doc: Doc, *, skill_md: bool) -> Iterator[Block]:
    """Each top-level block of `doc` in which naming a chapter is one.

    Every block but an example, the history a rename table keeps,
    `SKILL.md`'s section 6, and a chapter's `Scope:` paragraph.
    """
    section = ""
    for block, held in history(doc):
        if isinstance(block, Heading) and block.level == SECTION_LEVEL:
            section = block.text
        if held or isinstance(block, Fence):
            continue
        if (skill_md and section == shared.MAP) or (not skill_md and _is_scope(block)):
            continue
        yield block


#: The level of a section's heading, and of a subsection's.
SECTION_LEVEL, SUBSECTION_LEVEL = 2, 3


def target(skill: Skill) -> str:
    """What the standard is for, as section 2 names it.

    The language and the series its pin belongs to: `Python 3.15`.
    """
    return f"{skill.profile.language} {skill.profile.target}"


def reality_titles(skill: Skill) -> tuple[str, str, str]:
    """Section 2's three subsections, in their order (decision 5)."""
    return (
        "2.1 Compiles, and behaves differently",
        "2.2 No longer compiles",
        f"2.3 What {target(skill)} gained",
    )


def _reality(skill: Skill) -> Iterator[Finding]:
    """Section 2 is three subsections, and indexes the chapters.

    What compiles and behaves differently, what no longer compiles, what
    the target gained, in that order (decision 5). Sections 2.1 and 2.2
    are the migration table's `changed` and `gone` rows the target made,
    rendered from it (decision 9), so they hold nothing a person writes;
    each item of 2.3 names the rule that owns it, so section 2 holds
    nothing of its own — every item of the section outside the two
    projections, under whichever subsection or none, so a section still
    to be laid out is read too.
    """
    title = shared.skill_sections(skill)[2]
    section = next((s for s in skill.typed.sections if s.title == title), None)
    if section is None:
        return  # `section` reports a missing or misnamed section 2
    where = skill.at(SKILL_MD, section.line)
    before, parts = subsections(section.lead)
    want = reality_titles(skill)
    found = [heading.text for heading, _ in parts]
    if before or found != list(want):
        yield fail(
            f"section 2 holds {found or 'no subsection'}"
            f"{' after text of its own' if before else ''}; it is "
            f"{list(want)}, and nothing before them",
            where,
            REALITY_SECTIONS,
        )
    rendered = reality_rendered(skill)
    projected = dict(zip(want, PROJECTED, strict=False))
    for heading, blocks in parts:
        status = projected.get(heading.text)
        if rendered is None or status is None or blocks == rendered[heading.text]:
            continue
        yield _drifted(skill, heading, blocks, rendered[heading.text], status)
    written = (
        b for heading, blocks in parts if heading.text not in projected for b in blocks
    )
    yield from _owned(skill, (*before, *written))


def reality_rendered(skill: Skill) -> dict[str, tuple[Block, ...]] | None:
    """Sections 2.1 and 2.2, each as the migration table renders it.

    Each by its title: the rows of the status it projects (`PROJECTED`)
    whose Since is the target's — the series its pin belongs to, or its
    edition (`Profile.since`) — under the migration table's columns
    less Status and Since, then the line saying where the rest are.
    None while the migration chapter holds no one table to render from,
    which `migration_table` reports.
    """
    found = _migration_rows(skill)
    if found is None:
        return None
    family = f"{skill.prefix}-{vocabulary.code_for(MIGRATION_STEM)}"
    header = reality_header(target(skill))
    since = skill.profile.since
    return {
        title: reality(found[1], since, header, family, status)
        for title, status in zip(reality_titles(skill), PROJECTED, strict=False)
    }


#: The branch each projected subsection drifts through, by its status.
_DRIFT = {"changed": CHANGED_DRIFT, "gone": GONE_DRIFT}


def _drifted(
    skill: Skill,
    heading: Heading,
    held: Sequence[Block],
    rendered: Sequence[Block],
    status: str,
) -> Finding:
    """A projected subsection is not its rendering: say how, where."""
    rows = {tuple(r) for b in held if isinstance(b, Table) for r in b.rows}
    want = {tuple(r) for b in rendered if isinstance(b, Table) for r in b.rows}
    extra, missing = sorted(rows - want), sorted(want - rows)
    row = f"a `{status}` migration row whose Since is the target's"
    said = (
        f"lists {extra[0][0]}, which is no {row.removeprefix('a ')}"
        if extra
        else f"leaves out {missing[0][0]}, {row}"
        if missing
        else "differs from its rendering in its header, its order or its closing line"
    )
    since = ", ".join(sorted(map(str, skill.profile.since)))
    return fail(
        f"section {heading.text.split()[0]} {said}; it is the migration table's "
        f"`{status}` rows whose Since is {since or 'the target'}, rendered — "
        "`agent-skill fmt` writes it",
        skill.at(SKILL_MD, heading.line),
        _DRIFT[status],
    )


def subsections(
    lead: Sequence[Block],
) -> tuple[tuple[Block, ...], list[tuple[Heading, tuple[Block, ...]]]]:
    """A section's lead: what precedes its first `###`, then each `###`.

    Each subsection is its heading and the blocks under it.
    """
    before: list[Block] = []
    parts: list[tuple[Heading, tuple[Block, ...]]] = []
    for block in lead:
        if isinstance(block, Heading) and block.level == SUBSECTION_LEVEL:
            parts.append((block, ()))
        elif parts:
            parts[-1] = (parts[-1][0], (*parts[-1][1], block))
        else:
            before.append(block)
    return tuple(before), parts


def _owned(skill: Skill, blocks: Sequence[Block]) -> Iterator[Finding]:
    """Each item of a subsection names one of this standard's rules.

    An item is a paragraph, a list item or a table row, and its owner
    is any rule of this standard it cites. A row of a migration table
    is owned by the rule in its Rule column (decision 9), so an item
    naming that rule names the row's owner. Anything else — an example,
    a quote — is content a chapter owns, and is reported as an item
    naming none.
    """
    for block in blocks:
        if not isinstance(block, (Paragraph, ListBlock, Table)):
            yield fail(
                f"section 2 holds a {type(block).__name__.lower()}, which names no "
                "rule; section 2 indexes the chapters and holds nothing of its own",
                skill.at(SKILL_MD, block.line),
                REALITY_OWNER,
            )
            continue
        for line, item in _stated(block):
            if not any(cited(item, skill.prefix)):
                said = " ".join(item.split())
                yield fail(
                    f"section 2 says {said[:60]!r} and names no rule that owns it; "
                    "section 2 indexes the chapters and holds nothing of its own",
                    skill.at(SKILL_MD, line),
                    REALITY_OWNER,
                )


def _stated(block: Paragraph | ListBlock | Table) -> Iterator[tuple[int, str]]:
    """Each item `block` states, as text, and its line."""
    match block:
        case Paragraph(line=line):
            yield line, block.text
        case ListBlock(items=items):
            for item in items:
                yield item.line, text_of(item.blocks)
        case Table(rows=rows, line=line):
            for k, row in enumerate(rows):
                yield line + 2 + k, " | ".join(row)


def core_section(skill: Skill) -> Section | None:
    """`SKILL.md`'s section 4, if it has one."""
    title = shared.skill_sections(skill)[4]
    return next((s for s in skill.typed.sections if s.title == title), None)


def mapped(skill: Skill) -> tuple[Chapter, ...]:
    """The coded chapters section 6 maps, in the order it maps them.

    A row names its chapter's file, `` `references/errors.md` ``; a file
    no chapter of the skill is, or one with no family code, maps no
    rules.
    """
    by_stem = {c.path.stem: c for c in skill.chapters}
    table = next(_tables(_section(skill.typed.sections, shared.MAP)), None)
    rows = table.rows if table is not None else ()
    stems = (m["stem"] for row in rows if row and (m := _FILE.fullmatch(row[0])))
    return tuple(
        by_stem[stem] for stem in stems if stem in by_stem and vocabulary.code_for(stem)
    )


def chapters_mapped(skill: Skill) -> tuple[Mapped, ...]:
    """Each chapter section 6 maps: its title, and its rules' lines."""
    return tuple(
        (c.typed.title, tuple(Entry(r.id, r.tier, r.title) for r in c.typed.rules))
        for c in mapped(skill)
    )


def _core(skill: Skill) -> Iterator[Finding]:
    """Section 4 is a projection of the chapters (decision 7).

    It lists chapter rules by ID, grouped by chapter in section 6's
    order, each line's tier and title its chapter rule's, so the two
    cannot drift and a line's tier is its rule's by construction. A
    rule of its own — the `CORE` family — is a second statement of a
    chapter rule, and `revise` maps it to that rule. While section 4
    states one, it is not a list to project, so only the rule is
    reported.
    """
    section = core_section(skill)
    if section is None:
        return  # `section` reports a missing or misnamed section 4
    where = skill.at(SKILL_MD, section.line)
    for rule in skill.core:
        yield fail(
            f"{rule.id} is a rule of section 4's own; section 4 lists chapter rules "
            "by ID, and `revise` maps this one to the chapter rule it abbreviated",
            skill.at(SKILL_MD, rule.line),
            CORE_RULE,
        )
    if skill.core:
        return
    held = section.blocks()[1:]
    ids = listed(held)
    chapters = chapters_mapped(skill)
    if held == projection(ids or (), chapters):
        return
    known = {e.id for _, entries in chapters for e in entries}
    unknown = sorted(rid for rid in ids or () if rid not in known)
    said = (
        f"lists {', '.join(map(str, unknown))}, which no chapter section 6 maps holds"
        if unknown
        else "is not one list of chapter rules"
        if ids is None
        else "differs from its chapters' tiers, titles or order"
    )
    yield fail(
        f"section 4 {said}; it is the projection of the chapter rules it lists — "
        "`agent-skill fmt` renders it",
        where,
        CORE_DRIFT,
    )


#: The migration chapter's stem.
MIGRATION_STEM = MIGRATION.removesuffix(".md")


def _migration_chapter(skill: Skill) -> Chapter | None:
    """The skill's migration chapter, if it ships one."""
    return next((c for c in skill.chapters if c.path.stem == MIGRATION_STEM), None)


def _migration_rows(skill: Skill) -> tuple[Chapter, tuple[Migration, ...]] | None:
    """The migration chapter and the rows of its one table.

    None when it holds no table headed as a migration table, or more
    than one: `migration_table` reports which.
    """
    chapter = _migration_chapter(skill)
    if chapter is None:
        return None
    header = migration_header(target(skill))
    tables = [
        b for b in chapter.doc.blocks if isinstance(b, Table) and b.header == header
    ]
    return (chapter, migrations(tables[0])) if len(tables) == 1 else None


def gone_rows(skill: Skill) -> Iterator[tuple[Migration, Location]]:
    """Each `gone` row of the migration table, where it stands.

    What each toolchain verifies against its pinned release: a row
    whose old spelling the release still provides is not gone.
    """
    found = _migration_rows(skill)
    if found is None:
        return
    chapter, rows = found
    for row in rows:
        if row.status == "gone" and row.spelling is not None:
            yield row, chapter.where(row.line)


def _migration(skill: Skill) -> Iterator[Finding]:
    """The migration chapter is one function from old spelling to row.

    One table, `| Old | <target> | Status | Since | Rule |`, keyed
    uniquely by its old spelling, each row giving one of four statuses,
    the release from which it holds and the rule that owns it; and
    after it the command a reader runs, which `fmt` generates from the
    `gone` and `alias` rows (decision 9). Any other table mapping old
    spellings is a second map, and fails with it.
    """
    chapter = _migration_chapter(skill)
    if chapter is None:
        return  # `required_chapter` reports it
    header = migration_header(target(skill))
    tables = [b for b in chapter.doc.blocks if isinstance(b, Table)]
    mine = [t for t in tables if t.header == header]
    others = [
        t for t in tables if t.header != header and {"Old", "Status"} & set(t.header)
    ]
    if len(mine) != 1 or others:
        said = f"{len(mine)} tables" if len(mine) != 1 else "one table"
        also = (
            f", and {len(others)} other table(s) mapping old spellings"
            if others
            else ""
        )
        held = (*others, *mine)
        yield fail(
            f"`{chapter.name}` holds {said} headed `| {' | '.join(header)} |`{also}; "
            "it holds exactly one, and it is the only map of old spellings",
            chapter.where(held[0].line if held else None),
            MIGRATION_TABLE,
        )
    if len(mine) != 1:
        return
    rows = migrations(mine[0])
    yield from _rows_read(skill, chapter, rows)
    spelled: dict[str, Migration] = {}
    for row in rows:
        if row.spelling is None:
            continue
        if (first := spelled.setdefault(row.spelling, row)) is not row:
            yield fail(
                f"`{row.spelling}` is the old spelling of two rows, lines {first.line} "
                f"and {row.line}; a migration table is keyed by it",
                chapter.where(row.line),
                MIGRATION_TWICE,
            )
    found = generated(chapter.doc, header)
    at = next(i for i, b in enumerate(chapter.doc.blocks) if b is mine[0])
    if found is not None and stated(chapter.doc, at) != found[1]:
        yield fail(
            "the command after the migration table is not the one its `gone` and "
            "`alias` rows generate — `agent-skill fmt` writes it",
            chapter.where(mine[0].line),
            MIGRATION_COMMAND,
        )


def _rows_read(
    skill: Skill, chapter: Chapter, rows: Iterable[Migration]
) -> Iterator[Finding]:
    """Each row whose spelling, status, since or rule cannot be read."""
    for row in rows:
        owner = row.owner
        wrong = (
            f"its old spelling `{row.old}` is not one code span"
            if row.spelling is None
            else f"its status `{row.status}` is not one of {', '.join(STATUSES)}"
            if row.status not in STATUSES
            else _since_wrong(skill, row)
            or (
                f"its rule `{row.rule}` is not one rule ID of this standard"
                if owner is None or owner.standard != skill.prefix
                else ""
            )
        )
        if wrong:
            yield fail(
                f"a migration row's {wrong.removeprefix('its ')}",
                chapter.where(row.line),
                MIGRATION_ROW,
            )


def _since_wrong(skill: Skill, row: Migration) -> str:
    """What is wrong with `row`'s Since, or "" when nothing is.

    One form per standard: a release as its series, `3.15`, or, in a
    standard whose profile names an edition, an edition, `2024`. A
    change the target has not reached is no row of its table.
    """
    landed = row.landed
    edition = skill.profile.edition
    series = Version.try_parse(skill.profile.target)
    reached = edition if landed is not None and landed.edition else series
    return (
        f"its Since `{row.since}` is no release"
        f"{' or edition' if edition is not None else ''}"
        if landed is None or (landed.edition and edition is None)
        else f"its Since `{row.since}` is not a release's series, `{landed.series}`"
        if landed != landed.series
        else f"its Since `{row.since}` is after the target's, `{reached}`"
        if reached is not None and landed > reached
        else ""
    )
