"""Format a skill's rust examples the way the toolchain check demands.

`cargo fmt --check` decides whether a block is formatted, and it judges
the block as the extractor wrote it — indented inside a `pub mod`, where
rustfmt's `chain_width` and `struct_lit_width` bite earlier than they do
at column zero. That made the check report diffs a reader of the
markdown could not have predicted. This runs the same extraction,
formats it, and writes the result back, so the check is actionable
rather than merely correct.
"""

import re
import tempfile
from itertools import groupby
from pathlib import Path
lazy from collections.abc import Callable, Iterable, Iterator

from agent_skill import shared
from agent_skill.doc import canonical
from agent_skill.lang.rust import RUST, Crate, module_name
from agent_skill.proc import run
from agent_skill.report import Finding, fail, note
lazy from agent_skill.lang import Unit
lazy from agent_skill.lang.python import PYTHON_TOOLCHAIN
lazy from agent_skill.model import Block, Skill

#: The line the extractor injects into every block module.
INJECTED = "#![allow(dead_code, unused_imports)]"

_MODULE = re.compile(r"^pub mod (\w+) \{$", re.MULTILINE)


def _bodies(path: Path, crate: Crate) -> list[str]:
    """Each `pub mod`'s dedented body, the extractor's rebasing undone.

    `lang.rust._module` rewrites `crate::` and `mycrate::` to point
    inside the wrapper module, so the block compiles where it is put.
    Writing that back would store the harness's own path in the skill —
    the leak the extractor's comment warns about, arriving by the other
    door — so it is inverted here. Round-tripping a block through `fmt`
    has to be the identity on everything except whitespace.
    """
    text = path.read_text()
    starts = list(_MODULE.finditer(text))
    out: list[str] = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        lines = text[m.end() : end].split("\n")[1:]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1] == "}":
            lines.pop()
        body = [ln.removeprefix("    ") for ln in lines if ln.strip() != INJECTED]
        while body and not body[0].strip():
            body.pop(0)
        rebased = f"{path.stem}::{m.group(1)}::"
        out.append(
            ("\n".join(body) + "\n")
            .replace(f"{crate.ident}::{rebased}", "mycrate::")
            .replace(f"crate::{rebased}", "crate::")
        )
    return out


#: Toolchain name -> the function that rewrites that language's blocks.
#: A formatter is a fact about a language, so the dispatch is by
#: toolchain rather than by whether the profile happens to carry a
#: `Crate` — that gate returned early for every non-Rust skill before
#: the branch was even reached.
FORMATTERS: dict[str, Callable[[Skill], list[Finding]]] = {}


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
    formatter = FORMATTERS.get(skill.profile.toolchain)
    return changed + (formatter(skill) if formatter else [])


def _reprint(skill: Skill) -> list[Finding]:
    """Print every markdown file in its canonical form.

    An edit lengthens a line and a renaming lengthens a code inside a
    sentence; either way the paragraph is filled for words it no longer
    has. The canonical form is the one fill of the words it has now, and
    it is what `layout` holds every file to.
    """
    changed: list[Finding] = []
    for path in skill.markdown:
        text = path.read_text()
        if (printed := canonical(text)) != text:
            path.write_text(printed)
            changed.append(note("re-printed in its canonical form", path.name))
    return changed


def _format_rust(skill: Skill) -> list[Finding]:
    """Rewrite each `// verified` rust block as rustfmt would."""
    # `RUST.extract` builds from this crate, so this is
    # `extraction.crate`, with the type that field does not carry.
    crate = skill.profile.crate
    if crate is None:
        return []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = RUST.extract(skill, Path(work) / "out")
        if not extraction:
            return []
        r = run(["cargo", "fmt"], cwd=extraction.root, timeout=300, env=crate.env)
        if not r.ok:
            return [fail(f"cargo fmt failed: {(r.err or r.out).strip()[:160]}")]

        changed: list[Finding] = []
        for chapter, blocks in groupby(skill.blocks("rust"), key=lambda b: b.file):
            wanted = [b for b in blocks if b.marker.verified and b.rule != "?"]
            src = extraction.root / "src" / f"{module_name(chapter)}.rs"
            if not wanted or not src.exists():
                continue
            bodies = _bodies(src, crate)
            if len(bodies) != len(wanted):
                changed.append(
                    fail(
                        f"{len(wanted)} blocks, {len(bodies)} modules; skipped", chapter
                    )
                )
                continue
            path = skill.path_of(chapter)
            # Last first, so an earlier replacement cannot move a later
            # block.
            edits = reversed(list(zip(wanted, bodies, strict=True)))
            changed += _put_back(path, chapter, "rust", edits)
        return changed


def _put_back(
    path: Path, chapter: str, fence: str, edits: Iterable[tuple[Block, str]]
) -> list[Finding]:
    """Write each new body over its block in `path`, in the order given.

    Returns a failure per block skipped, then a note for the chapter if
    it changed. A block whose fenced text is not found exactly once is
    skipped rather than guessed at.
    """
    text = path.read_text()
    changed: list[Finding] = []
    hits = 0
    for block, body in edits:
        if block.body == body:
            continue
        old = f"```{fence}\n{block.body}```"
        if text.count(old) != 1:
            changed.append(
                fail("not uniquely locatable; skipped", f"{chapter}:{block.line}")
            )
            continue
        text = text.replace(old, f"```{fence}\n{body}```")
        hits += 1
    if hits:
        path.write_text(text)
        changed.append(note(f"{hits} block(s) reformatted", chapter))
    return changed


def _format_python(skill: Skill) -> list[Finding]:
    """Rewrite each `# verified` python block as `ruff format` would.

    Simpler than the Rust path because each block is already its own
    file: there is no crate to reassemble, so a block that fails to
    format is reported alone rather than taking its chapter's siblings
    with it.
    """
    config = skill.root / "assets" / "ruff.toml"
    if not config.exists():
        return []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = PYTHON_TOOLCHAIN.extract(skill, Path(work) / "out")
        if not extraction:
            return []
        r = run(
            [
                "ruff",
                "format",
                "--no-cache",
                "--config",
                str(config),
                str(extraction.root),
            ],
            timeout=300,
        )
        if not r.ok:
            return [fail(f"ruff format failed: {(r.err or r.out).strip()[:160]}")]

        changed: list[Finding] = []
        by_chapter: dict[str, list[Unit]] = {}
        for unit in extraction.units:
            by_chapter.setdefault(unit.chapter, []).append(unit)
        for chapter, units in by_chapter.items():
            path = skill.path_of(chapter)
            # Last first, so an earlier replacement cannot move a later
            # block.
            ordered = sorted(units, key=lambda u: u.line, reverse=True)
            edits = _python_edits(skill, chapter, ordered)
            changed += _put_back(path, chapter, "python", edits)
        return changed


def _python_edits(
    skill: Skill, chapter: str, units: Iterable[Unit]
) -> Iterator[tuple[Block, str]]:
    """Each unit's formatted body, with the block it was cut from."""
    for unit in units:
        body = unit.path.read_text()
        same = (b for b in skill.blocks("python") if b.file == chapter)
        block = next((b for b in same if b.line == unit.line), None)
        if block is not None:
            yield block, body


FORMATTERS["rust"] = _format_rust
FORMATTERS["python"] = _format_python
