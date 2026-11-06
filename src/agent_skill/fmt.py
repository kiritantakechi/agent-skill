"""Format a skill the way its checks demand.

Each shared passage is rewritten from its template and every markdown
file printed canonically; then each verified block is rewritten the way
its toolchain's formatter would (`Toolchain.format`).

`cargo fmt --check` decides whether a rust block is formatted, and it
judges the block as the extractor wrote it — indented inside a
`pub mod`, where rustfmt's `chain_width` and `struct_lit_width` bite
earlier than they do at column zero. That made the check report diffs
a reader of the markdown could not have predicted. A formatter runs the
same extraction, formats it, and writes the result back with
`put_back`, so the check is actionable rather than merely correct.
"""

lazy from collections.abc import Iterable

from agent_skill import shared
from agent_skill.doc import canonical
from agent_skill.lang import toolchain_for
from agent_skill.report import Finding, Level, declare, fail, note
lazy from agent_skill.model import Block, Skill

# The branches `fmt` reports through. It is a command rather than a
# check, so no control is owed them.
REPRINTED = declare("fmt", "reprinted", Level.NOTE)
CARGO_FMT = declare("fmt", "cargo_fmt", Level.FAIL)
MODULES = declare("fmt", "modules", Level.FAIL)
UNLOCATABLE = declare("fmt", "unlocatable", Level.FAIL)
REFORMATTED = declare("fmt", "reformatted", Level.NOTE)
RUFF_FORMAT = declare("fmt", "ruff_format", Level.FAIL)


def format_skill(skill: Skill) -> list[Finding]:
    """Rewrite a skill's verified blocks and shared passages.

    Each verified block the way that language's formatter would, and
    each shared passage the way its template says.

    Returns a note per passage or chapter changed, and a failure for
    each thing that could not be rewritten — a formatter that failed, a
    block that was skipped — so the command can say it did not finish.
    The text comes first, shared passages and then every file's
    canonical form: it needs no toolchain to rewrite.
    """
    changed = shared.rewrite(skill) + _reprint(skill)
    toolchain = toolchain_for(skill.profile.toolchain)
    return changed + (toolchain.format(skill) if toolchain else [])


def _reprint(skill: Skill) -> list[Finding]:
    """Print every markdown file in its canonical form.

    An edit lengthens a line and a renaming lengthens a code inside a
    sentence; either way the paragraph is filled for words it no longer
    has. The canonical form is the one fill of the words it has now, and
    it is what `layout` holds every file to. The file is read with its
    newlines untranslated, as `layout` reads it, so a CR inside an
    example is left for a person rather than turned into a line break.
    """
    changed: list[Finding] = []
    for path in skill.markdown:
        text = path.read_text(newline="")
        if (printed := canonical(text)) != text:
            path.write_text(printed)
            changed.append(
                note("re-printed in its canonical form", skill.at(path), REPRINTED)
            )
    return changed


def put_back(
    skill: Skill, chapter: str, fence: str, edits: Iterable[tuple[Block, str]]
) -> list[Finding]:
    """Write each new body over its block in `path`, in the order given.

    Returns a failure per block skipped, then a note for the chapter if
    it changed. A block whose fenced text is not found exactly once is
    skipped rather than guessed at.
    """
    path = skill.path_of(chapter)
    text = path.read_text()
    changed: list[Finding] = []
    hits = 0
    for block, body in edits:
        if block.body == body:
            continue
        old = f"```{fence}\n{block.body}```"
        if text.count(old) != 1:
            changed.append(
                fail("not uniquely locatable; skipped", block.where, UNLOCATABLE)
            )
            continue
        text = text.replace(old, f"```{fence}\n{body}```")
        hits += 1
    if hits:
        path.write_text(text)
        changed.append(
            note(f"{hits} block(s) reformatted", skill.at(chapter), REFORMATTED)
        )
    return changed
