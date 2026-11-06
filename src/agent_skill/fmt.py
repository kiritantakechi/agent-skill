"""Format a skill the way its checks demand.

Each shared passage is rewritten from its template and every markdown
file printed canonically; then every verified block is rewritten as its
toolchain's formatter would: `restore ∘ format ∘ extract`, the same
composition for every toolchain, so each gets write-back with no code
of its own. Zig had none, and `zig fmt --check` named a block a reader
then had to fix by hand.

The formatter judges the file the extractor wrote, so what `toolchain`
calls unformatted is exactly what this rewrites: the check is
actionable rather than merely correct.
"""

import tempfile
from pathlib import Path
lazy from collections.abc import Mapping

from agent_skill import shared
from agent_skill.doc import Doc, Fence, Item, ListBlock, Quote, walk
from agent_skill.doc.chapter import Section, SkillMd, migration_header
from agent_skill.doc.normal import listed, normal, projection, with_command
from agent_skill.lang import execute, judged, toolchain_for
from agent_skill.model import Block, Skill
from agent_skill.report import Finding, Level, declare, fail, note
lazy from agent_skill import doc
lazy from agent_skill.checks.skeleton import MIGRATION_STEM, chapters_mapped, target

# The branches `fmt` reports through. It is a command rather than a
# check, so no control is owed them.
REPRINTED = declare("fmt", "reprinted", Level.NOTE)
FORMATTER = declare("fmt", "formatter", Level.FAIL)
FORMATTER_TIMEOUT = declare("fmt", "formatter_timeout", Level.FAIL)
UNLOCATABLE = declare("fmt", "unlocatable", Level.FAIL)
REFORMATTED = declare("fmt", "reformatted", Level.NOTE)
CORE_UNRENDERED = declare("fmt", "core_unrendered", Level.FAIL)


def format_skill(skill: Skill) -> list[Finding]:
    """Rewrite a skill's shared passages, markdown and verified blocks.

    Returns a note per passage or file changed, and a failure for each
    thing that could not be rewritten — a formatter that failed, a block
    that was skipped — so the command can say it did not finish. The
    text comes first, shared passages and then every file's canonical
    form: it needs no toolchain to rewrite.
    """
    changed = shared.rewrite(skill) + _reprint(skill)
    # Read again: the text just written moved the blocks' lines.
    return changed + _examples(Skill(skill.root, skill.profile))


def _reprint(skill: Skill) -> list[Finding]:
    """Print every markdown file in its canonical form.

    An edit lengthens a line and a renaming lengthens a code inside a
    sentence; either way the paragraph is filled for words it no longer
    has. The canonical form is the one fill of the words it has now, and
    it is what `layout` holds every file to. The file is read with its
    newlines untranslated, as `layout` reads it, so a CR inside an
    example is left for a person rather than turned into a line break.

    A normalised standard is printed in its normal form as well: every
    citation bare, every rule's elements in order. Only a normalised
    one, while `Profile.normalized` is the gate: the other standards
    still cite a core rule's chapter by path, which `anatomy` reads
    until section 4 is a projection, and are normalised a standard at a
    time rather than by a formatter.
    """
    changed: list[Finding] = []
    chapters = {c.path for c in skill.chapters}
    for path in skill.markdown:
        text = path.read_text(newline="")
        tree = Doc.parse(text)
        if skill.profile.normalized:
            tree = normal(tree, chapter=path in chapters)
        if skill.profile.normalized and path == skill.skill_md:
            tree, unrendered = _projected(skill, tree)
            changed += unrendered
        if skill.profile.normalized and path.stem == MIGRATION_STEM:
            tree = with_command(tree, migration_header(target(skill)))
        if (printed := str(tree)) != text:
            path.write_text(printed)
            changed.append(
                note("re-printed in its canonical form", skill.at(path), REPRINTED)
            )
    return changed


def _projected(skill: Skill, tree: Doc) -> tuple[Doc, list[Finding]]:
    """`SKILL.md` with section 4 rendered from the rules it lists.

    Each listed rule's line is its chapter's ID, tier and title, grouped
    by chapter in section 6's order (decision 7). A section 4 that
    holds what the rendering would drop — a rule of its own, prose, a
    rule no chapter in section 6 holds — is left as it is and reported:
    which rule it meant is a person's to say, through `revise`.
    """
    md = SkillMd.read(tree)
    title = shared.skill_sections(skill)[4]
    at = next((i for i, s in enumerate(md.sections) if s.title == title), None)
    if at is None:
        return tree, []
    section = md.sections[at]
    chapters = chapters_mapped(skill)
    ids = listed(section.blocks()[1:])
    known = {e.id for _, entries in chapters for e in entries}
    if ids is None or any(rid not in known for rid in ids):
        return tree, [
            fail(
                "section 4 holds what its projection would drop — a rule of its own, "
                "prose, or a rule no chapter section 6 maps holds; not rendered",
                skill.at(skill.skill_md, section.line),
                CORE_UNRENDERED,
            )
        ]
    rendered = Section(section.title, projection(ids, chapters), (), section.line)
    sections = (*md.sections[:at], rendered, *md.sections[at + 1 :])
    return SkillMd(md.frontmatter, md.title, md.preamble, sections).doc(), []


def _examples(skill: Skill) -> list[Finding]:
    """Each verified block, as its toolchain's formatter prints it."""
    tc = toolchain_for(skill.profile.toolchain)
    if tc is None:
        return []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        ex = tc.extract(skill, Path(work) / "out")
        if not ex:
            return []
        step = tc.formatter(ex)
        failed = judged(
            step, execute(step), ex, failed=FORMATTER, timeout=FORMATTER_TIMEOUT
        )
        if failed:
            return failed
        restored = tc.restore(ex)
    return put_back(skill, {b: body for b, body in restored.items() if body != b.body})


def put_back(skill: Skill, bodies: Mapping[Block, str]) -> list[Finding]:
    """Write each new body into its block's fence, last block first.

    A block is found in the file's tree by its fence's line, as the
    skill was read, so two blocks with one body are told apart. One
    whose fence is not on that line, or no longer holds its body in its
    language, is skipped rather than guessed at. The file is printed
    from its tree, as `fmt` has just printed it.

    Returns a failure per block skipped, then a note per file changed.
    """
    changed: list[Finding] = []
    by_file: dict[str, list[Block]] = {}
    for block in bodies:
        by_file.setdefault(block.file, []).append(block)
    for document, blocks in by_file.items():
        path = skill.path_of(document)
        tree = Doc.parse(path.read_text())
        fences = {f.line: f for f in walk(tree.blocks) if isinstance(f, Fence)}
        swaps: dict[int, str] = {}
        for block in sorted(blocks, key=lambda b: b.line, reverse=True):
            fence = fences.get(block.line - 1)
            if fence is None or (fence.info, fence.body) != (block.lang, block.body):
                changed.append(
                    fail("not where it was read; skipped", block.where, UNLOCATABLE)
                )
                continue
            swaps[fence.line] = bodies[block].removesuffix("\n") + "\n"
        if swaps:
            new = (_swapped(b, swaps) for b in tree.blocks)
            path.write_text(str(Doc(tree.frontmatter, tuple(new))))
            changed.append(
                note(
                    f"{len(swaps)} block(s) reformatted",
                    skill.at(document),
                    REFORMATTED,
                )
            )
    return changed


def _swapped(block: doc.Block, bodies: Mapping[int, str]) -> doc.Block:
    """`block`, each fence it is or holds given its line's new body."""
    match block:
        case Fence(info, _, line, closed) if line in bodies:
            return Fence(info, bodies[line], line, closed)
        case ListBlock(items, start, loose, line):
            held = tuple(
                Item(tuple(_swapped(b, bodies) for b in i.blocks), i.line)
                for i in items
            )
            return ListBlock(held, start, loose, line)
        case Quote(inner, alert, line, lazy):
            return Quote(tuple(_swapped(b, bodies) for b in inner), alert, line, lazy)
        case _:
            return block
