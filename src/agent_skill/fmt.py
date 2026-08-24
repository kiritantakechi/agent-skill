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

from .lang.rust import RUST
from .proc import run

#: The line the extractor injects into every block module.
INJECTED = "#![allow(dead_code, unused_imports)]"

_MODULE = re.compile(r"^pub mod (\w+) \{$", re.M)


def _bodies(path: Path) -> list[str]:
    """The dedented body of each `pub mod` in an extracted chapter file."""
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
        out.append("\n".join(body) + "\n")
    return out


def format_skill(skill) -> list[str]:
    """Rewrite each `// verified` rust block as rustfmt would have it.

    Returns one line per chapter changed.
    """
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
            bodies = _bodies(src)
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
