"""Format a skill's rust examples the way the toolchain check demands.

`cargo fmt --check` decides whether a block is formatted, and it judges the
block as the extractor wrote it — indented inside a `pub mod`, where rustfmt's
`chain_width` and `struct_lit_width` bite earlier than they do at column zero.
That made the check report diffs a reader of the markdown could not have
predicted. This runs the same extraction, formats it, and writes the result
back, so the check is actionable rather than merely correct.
"""

from __future__ import annotations

import re
import tempfile
from itertools import groupby
from pathlib import Path

from .lang.rust import RUST, Crate
from .proc import run

#: The line the extractor injects into every block module.
INJECTED = "#![allow(dead_code, unused_imports)]"

_MODULE = re.compile(r"^pub mod (\w+) \{$", re.M)


def _bodies(path: Path, crate: Crate) -> list[str]:
    """The dedented body of each `pub mod`, with the extractor's rebasing undone.

    `lang.rust._module` rewrites `crate::` and `mycrate::` to point inside the
    wrapper module, so the block compiles where it is put. Writing that back
    would store the harness's own path in the skill — the leak the extractor's
    comment warns about, arriving by the other door — so it is inverted here.
    Round-tripping a block through `fmt` has to be the identity on everything
    except whitespace.
    """
    text = path.read_text()
    starts = [m for m in _MODULE.finditer(text)]
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


#: Toolchain name -> the function that rewrites that language's blocks. A
#: formatter is a fact about a language, so the dispatch is by toolchain rather
#: than by whether the profile happens to carry a `Crate` — that gate returned
#: early for every non-Rust skill before the branch was even reached.
FORMATTERS: dict[str, object] = {}


def format_skill(skill) -> list[str]:
    """Rewrite each verified block the way that language's formatter would.

    Returns one line per chapter changed.
    """
    formatter = FORMATTERS.get(skill.profile.toolchain or "")
    return formatter(skill) if formatter else []


def _format_rust(skill) -> list[str]:
    """Rewrite each `// verified` rust block as rustfmt would have it."""
    if skill.profile.crate is None:
        return []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = RUST.extract(skill, Path(work) / "out")
        if not extraction:
            return []
        r = run(["cargo", "fmt"], cwd=extraction.root, timeout=300, env=extraction.crate.env)
        if not r.ok:
            return [f"cargo fmt failed: {(r.err or r.out).strip()[:160]}"]

        changed: list[str] = []
        for chapter, blocks in groupby(skill.blocks("rust"), key=lambda b: b.file):
            wanted = [b for b in blocks if b.marker.verified and b.rule != "?"]
            src = extraction.root / "src" / f"{Path(chapter).stem.replace('-', '_')}.rs"
            if not wanted or not src.exists():
                continue
            bodies = _bodies(src, extraction.crate)
            if len(bodies) != len(wanted):
                changed.append(f"{chapter}: {len(wanted)} blocks, {len(bodies)} modules; skipped")
                continue
            path = skill.root / "references" / chapter
            text = path.read_text()
            # Last first, so an earlier replacement cannot move a later block.
            hits = 0
            for block, body in reversed(list(zip(wanted, bodies, strict=True))):
                if block.body == body:
                    continue
                old = f"```rust\n{block.body}```"
                if text.count(old) != 1:
                    changed.append(f"{chapter}:{block.line} is not uniquely locatable; skipped")
                    continue
                text = text.replace(old, f"```rust\n{body}```")
                hits += 1
            if hits:
                path.write_text(text)
                changed.append(f"{chapter}: {hits} block(s) reformatted")
        return changed


def _format_python(skill) -> list[str]:
    """Rewrite each `# verified` python block as `ruff format` would have it.

    Simpler than the Rust path because each block is already its own file: there
    is no crate to reassemble, so a block that fails to format is reported alone
    rather than taking its chapter's siblings with it.
    """
    from .lang.python import PYTHON_TOOLCHAIN

    config = skill.root / "assets" / "ruff.toml"
    if not config.exists():
        return []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        extraction = PYTHON_TOOLCHAIN.extract(skill, Path(work) / "out")
        if not extraction:
            return []
        r = run(
            ["ruff", "format", "--no-cache", "--config", str(config), str(extraction.root)],
            timeout=300,
        )
        if not r.ok:
            return [f"ruff format failed: {(r.err or r.out).strip()[:160]}"]

        changed: list[str] = []
        by_chapter: dict[str, list] = {}
        for unit in extraction.units:
            by_chapter.setdefault(unit.chapter, []).append(unit)
        for chapter, units in by_chapter.items():
            path = skill.root / "references" / chapter
            text = path.read_text()
            hits = 0
            # Last first, so an earlier replacement cannot move a later block.
            for unit in sorted(units, key=lambda u: u.line, reverse=True):
                body = unit.path.read_text()
                same = (b for b in skill.blocks("python") if b.file == chapter)
                block = next((b for b in same if b.line == unit.line), None)
                if block is None or block.body == body:
                    continue
                old_fence = f"```python\n{block.body}```"
                if text.count(old_fence) != 1:
                    changed.append(f"{chapter}:{unit.line} is not uniquely locatable; skipped")
                    continue
                text = text.replace(old_fence, f"```python\n{body}```")
                hits += 1
            if hits:
                path.write_text(text)
                changed.append(f"{chapter}: {hits} block(s) reformatted")
        return changed


FORMATTERS["rust"] = _format_rust
FORMATTERS["python"] = _format_python
