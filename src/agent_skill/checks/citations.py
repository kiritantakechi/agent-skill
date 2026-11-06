"""A rule's check must be one the shipped config actually turns on.

`lints` compares the Rust crate's declared table with the shipped
`Cargo.toml`. Rows and citations need a comparison of their own: a
standard cites its checks by tool and code, so a rule can name a lint
the asset disables — or one the tool withdrew — and read as enforced
while nothing enforces it.

What is generic is here: a row names a tool the standard requires, at a
level that fails a run. What a row or a citation means to its tool is
the skill's toolchain's to say (`Toolchain.cite`), because each tool
reads its own configuration.
"""

import re
from collections import Counter
lazy from collections.abc import Iterable, Iterator

from agent_skill.checks import check, per_skill
from agent_skill.doc import text_of
from agent_skill.doc.chapter import CHECK
from agent_skill.lang import needs, toolchain_for, toolchains
from agent_skill.report import Level, declare, fail
lazy from agent_skill.doc.chapter import LintRow, Rule
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from. Each toolchain
# declares those its rows and citations report through.
ROW_TOOL = declare("citations", "row_tool", Level.FAIL)
ROW_LEVEL = declare("citations", "row_level", Level.FAIL)

# The branches only a normalised standard is held to (`_bijection`).
UNROWED = declare("citations", "unrowed", Level.FAIL)
ROWED_TWICE = declare("citations", "rowed_twice", Level.FAIL)
ROW_REASON = declare("citations", "row_reason", Level.FAIL)
ONLY_LINT = declare("citations", "only_lint", Level.FAIL)
ALLOW_REASON = declare("citations", "allow_reason", Level.FAIL)


#: A row of a chapter's `Decided by tools` table, and where it is.
type Row = tuple[Location, LintRow]


def rows_of(skill: Skill) -> list[Row]:
    """Every `Decided by tools` row, chapter by chapter, where it is."""
    return [
        (chapter.where(row.line), row)
        for chapter in skill.chapters
        for row in chapter.typed.tools
    ]


def levels() -> dict[str, frozenset[str]]:
    """The levels a row may state, per tool: those that fail a run.

    A row at a level that lets the run pass is a lint nothing enforces,
    which is a rule with its Why and Check deleted. Each toolchain says
    which tools its rows name, and at which levels each fails.
    """
    return {tool: lv for tc in toolchains() for tool, lv in tc.rows.items()}


def row_shape(rows: Iterable[Row], tools: tuple[str, ...]) -> Iterator[Finding]:
    """Each row whose tool or level enforces nothing.

    Such a row names a tool the standard does not require, or a level at
    which the tool would let the run pass.
    """
    failing = levels()
    for where, row in rows:
        if row.tool not in tools or row.tool not in failing:
            yield fail(
                f"`{row.tool}` is not a tool this standard requires",
                where,
                ROW_TOOL,
            )
        elif row.level not in failing[row.tool]:
            stated = " / ".join(sorted(failing[row.tool]))
            yield fail(
                f"`{row.lint}` at `{row.level}` fails no run; a row is one of {stated}",
                where,
                ROW_LEVEL,
            )


@check(
    "citations",
    "a cited check must be one the shipped config enables",
    needs=needs(lambda tc: tc.cites_with),
)
@per_skill
def citations(skill: Skill) -> Iterator[Finding]:
    """Every lint row and cited code, against the shipped config."""
    yield from row_shape(rows_of(skill), skill.profile.tools)
    if skill.profile.normalized:
        yield from bijection(skill)
        yield from _excused(skill)
    if (toolchain := toolchain_for(skill.profile.toolchain)) is not None:
        yield from toolchain.cite(skill)


def _excused(skill: Skill) -> Iterator[Finding]:
    """Each lint the examples are excused from says why (decision 12).

    A normalised standard's examples are linted with the configuration
    it ships, less an allowlist of rules about a project's shape, which
    a fenced snippet cannot have. An entry with no reason is an
    exemption nobody can weigh.
    """
    toolchain = toolchain_for(skill.profile.toolchain)
    excused = toolchain.excused(skill) if toolchain is not None else {}
    for code, reason in sorted(excused.items()):
        if not reason.strip():
            yield fail(
                f"the examples are excused from `{code}` with no reason; a rule a "
                "snippet cannot satisfy says why it cannot",
                skill.at(),
                ALLOW_REASON,
            )


# ------------------------------------------------------------------
# the lint bijection: what a normalised standard is held to (decision 8)

#: What a row for a lint the configuration does not set one by one says
#: before the reason it is listed at all.
LISTED = "listed because"

#: A lint and the tool that reports it, as a row names the two.
type Lint = tuple[str, str]


def configured(skill: Skill) -> dict[Lint, str]:
    """Each lint `skill`'s configuration sets one by one to fail a run.

    At the level it sets: a lint set to `allow` forbids nothing, so a
    row could only say what the build lets through.
    """
    toolchain = toolchain_for(skill.profile.toolchain)
    if toolchain is None:
        return {}
    failing = levels()
    return {
        lint: level
        for lint, level in toolchain.configured(skill).items()
        if level in failing.get(lint[0], ())
    }


def owed(skill: Skill) -> tuple[dict[Lint, str], frozenset[Lint]]:
    """The lints owed a row here, and those whose row is the anchor's.

    Every lint the configuration sets one by one is owed exactly one
    row. A delta's configuration repeats its anchor's where it does not
    depart, and a lint it sets as its anchor does is the anchor's to
    row, so each lint has one owner: the delta owes a row only for an
    entry its anchor sets otherwise or not at all, as it ships only the
    assets it departs in.
    """
    mine = configured(skill)
    anchor = skill.profile.anchor
    if not anchor:
        return mine, frozenset()
    # The anchor's files, read as this standard's toolchain reads its
    # own: a delta builds with its anchor's language, so its toolchain
    # is the one that reads the anchor's configuration.
    theirs = configured(Skill(skill.root.parent / anchor, skill.profile))
    shared = frozenset(k for k, level in mine.items() if theirs.get(k) == level)
    return {k: v for k, v in mine.items() if k not in shared}, shared


def bijection(skill: Skill) -> Iterator[Finding]:
    """Each configured lint has one row, and each row a reason.

    A lint the configuration sets one by one has exactly one row, in
    the chapter that owns its subject — which chapter that is, is a
    reader's to judge; one row is the harness's. A row for a lint the
    configuration does not set one by one — on by default, or through a
    group — says why it is listed, since a reader learns what the build
    forbids from the configuration, and a row adds only its reason. A
    compiler's error is set by no configuration, and its row is proved
    by its probe. A rule whose Check is a lint and nothing more is that
    lint's row.
    """
    due, anchors = owed(skill)
    rows = rows_of(skill)
    seen = Counter((row.tool, row.lint) for _, row in rows)
    for tool, lint in sorted(set(due) - set(seen)):
        yield fail(
            f"the configuration sets `{tool}:{lint}` to `{due[tool, lint]}` and no "
            "chapter lists it; a reader learns what the build forbids from the rows",
            skill.at(),
            UNROWED,
        )
    toolchain = toolchain_for(skill.profile.toolchain)
    compilers = toolchain.compilers if toolchain is not None else frozenset()
    every = configured(skill)
    listed: Counter[Lint] = Counter()
    for where, row in rows:
        lint = (row.tool, row.lint)
        listed[lint] += 1
        if listed[lint] == 2:  # noqa: PLR2004 — the second row is the one too many
            yield fail(
                f"`{row.tool}:{row.lint}` has {seen[lint]} rows; a lint has one, in "
                "the chapter that owns its subject",
                where,
                ROWED_TWICE,
            )
        elif lint in anchors:
            yield fail(
                f"`{row.tool}:{row.lint}` is set here as `{skill.profile.anchor}` sets "
                "it, so its row is the anchor's; one lint, one row",
                where,
                ROWED_TWICE,
            )
        if lint not in every and row.tool not in compilers and not _reasoned(row):
            yield fail(
                f"`{row.tool}:{row.lint}` is not set one by one, and its row does not "
                f"say why it is listed (`{LISTED} …`)",
                where,
                ROW_REASON,
            )
    for chapter in skill.chapters:
        for rule in chapter.typed.rules:
            if only_lint(rule):
                yield fail(
                    f"{rule.id}'s Check is a lint and nothing more; the rule is that "
                    "lint's row, and `revise` demotes it",
                    chapter.where(rule.line),
                    ONLY_LINT,
                )


def _reasoned(row: LintRow) -> bool:
    """Does `row` say why it is listed, after what it forbids?"""
    said, listed, reason = row.forbids.lower().partition(LISTED)
    return bool(said.strip() and listed and reason.strip(" :—-"))


#: What a Check that is only a lint says beside its lint: the words
#: that join a tool's name to a code.
_JOINING = frozenset({"and", "or", "the", "its", "by", "lint", "lints", "decides"})

#: A lint as a Check names one in a code span: `UP006`, `unwrap_used`.
_LINT = re.compile(r"[\w:-]+")

#: A lint code written outside a code span: `TRY002`.
_CODE = re.compile(r"[A-Z]+\d+")


def only_lint(rule: Rule) -> bool:
    """Is the rule's Check a lint and nothing more?

    Its words, its label and code spans aside, are tools' names, codes
    and the words that join them: `**Check:** ruff `UP040`.` Such a
    rule is that lint's row (decision 8).
    """
    tools = {tool for tc in toolchains() for tool in tc.rows}
    said = text_of(rule.check).removeprefix(CHECK)
    spans = re.findall(r"`([^`]+)`", said)
    rest = re.findall(r"[A-Za-z][\w-]*", re.sub(r"`[^`]+`", " ", said))
    return bool(spans) and (
        all(_LINT.fullmatch(s) for s in spans)
        and all(w in tools or w in _JOINING or _CODE.fullmatch(w) for w in rest)
    )


def unrowed(skill: Skill) -> tuple[int, int]:
    """How many lints owed a row have none, of how many are owed."""
    due, _ = owed(skill)
    rows = {(row.tool, row.lint) for _, row in rows_of(skill)}
    return len(set(due) - rows), len(due)
