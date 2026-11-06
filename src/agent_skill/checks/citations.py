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

lazy from collections.abc import Iterable, Iterator

from agent_skill.checks import check, per_skill
from agent_skill.lang import needs, toolchain_for, toolchains
from agent_skill.report import Level, declare, fail
lazy from agent_skill.doc.chapter import LintRow
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from. Each toolchain
# declares those its rows and citations report through.
ROW_TOOL = declare("citations", "row_tool", Level.FAIL)
ROW_LEVEL = declare("citations", "row_level", Level.FAIL)


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
    if (toolchain := toolchain_for(skill.profile.toolchain)) is not None:
        yield from toolchain.cite(skill)
