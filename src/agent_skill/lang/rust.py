"""rust-style's examples, as a crate."""

from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import groupby
from pathlib import Path

from ..proc import run
from ..report import Finding, fail
from . import Extraction, Unit

CRATE = "rust-style-verify"

#: The shipped table (`assets/Cargo.toml`) minus the two entries a fragment
#: cannot satisfy: `missing_docs` (blocks document items selectively) and
#: `unsafe_code = "forbid"` (the unsafe-ffi chapter exists). Everything else is
#: enforced verbatim, and checks/lints.py compares the two so they cannot drift —
#: `undocumented_unsafe_blocks` was dropped here with nothing saying so, which
#: left RS-CAR-29 unverified.
LINTS: dict[str, dict[str, str]] = {
    "rust": {
        "missing_debug_implementations": '"deny"',
        "unreachable_pub": '"warn"',
        "unused_qualifications": '"warn"',
        "elided_lifetimes_in_paths": '"warn"',
        "explicit_outlives_requirements": '"warn"',
    },
    "clippy": {
        "pedantic": '{ level = "warn", priority = -1 }',
        "unwrap_used": '"deny"',
        "expect_used": '"deny"',
        "panic": '"deny"',
        "todo": '"deny"',
        "unimplemented": '"deny"',
        "indexing_slicing": '"deny"',
        "dbg_macro": '"deny"',
        "undocumented_unsafe_blocks": '"deny"',
        "mem_forget": '"deny"',
        "cast_possible_truncation": '"warn"',
        "cast_precision_loss": '"warn"',
        "cast_sign_loss": '"warn"',
        "float_cmp": '"warn"',
        "module_name_repetitions": '"allow"',
    },
}

#: The entries the verified crate legitimately cannot carry.
UNVERIFIABLE = {"rust.missing_docs", "rust.unsafe_code"}


def _manifest() -> str:
    lints = "\n".join(
        f"[lints.{section}]\n" + "\n".join(f"{k} = {v}" for k, v in table.items())
        for section, table in LINTS.items()
    )
    return (
        f'[package]\nname = "{CRATE}"\nversion = "0.1.0"\nedition = "2024"\n'
        'rust-version = "1.98"\n\n[dependencies]\nthiserror = "2"\n\n[workspace]\n\n' + lints + "\n"
    )


class Rust:
    name = "rust"
    tool = "cargo"

    def extract(self, skill, out: Path) -> Extraction:
        src = out / "src"
        src.mkdir(parents=True, exist_ok=True)
        # A renamed chapter otherwise leaves a module lib.rs never declares,
        # which the mutation pass still globs: deleting a line in a file nothing
        # compiles can never change a test result, so every statement survives.
        for stale in src.glob("*.rs"):
            stale.unlink()

        ex = Extraction(out)
        chapters: list[str] = []
        for chapter, blocks in groupby(skill.blocks("rust"), key=lambda b: b.file):
            mods: list[tuple[str, str]] = []
            for b in blocks:
                if not b.marker.verified or b.rule == "?":
                    continue
                base = b.rule.lower().replace("-", "_")
                n = sum(1 for m, _ in mods if m == base or m.startswith(base + "_"))
                mods.append((base if n == 0 else f"{base}_{n}", b.body))
                ex.units.append(Unit(src, chapter, b.line, b.rule))
            if not mods:
                continue
            stem = Path(chapter).stem.replace("-", "_")
            chapters.append(stem)
            (src / f"{stem}.rs").write_text(_module(stem, chapter, mods))

        lib = [f"//! Every `// verified` block in {skill.name}, extracted from the markdown."]
        lib += [f"pub mod {s};" for s in sorted(chapters)]
        (src / "lib.rs").write_text("\n".join(lib) + "\n")
        (out / "Cargo.toml").write_text(_manifest())
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        manifest = str(ex.root / "Cargo.toml")
        steps = [
            ("compiles", ["cargo", "build", "--quiet", "--manifest-path", manifest]),
            # `-D warnings` so the whole shipped table binds. Half of it is
            # `warn`, and clippy exits 0 on a warning — so without this the check
            # could only ever fail on the `deny` half.
            (
                "clippy",
                [
                    "cargo",
                    "clippy",
                    "--quiet",
                    "--all-targets",
                    "--manifest-path",
                    manifest,
                    "--",
                    "-D",
                    "warnings",
                ],
            ),
            ("tests", ["cargo", "test", "--quiet", "--manifest-path", manifest]),
            ("rustfmt", ["cargo", "fmt", "--manifest-path", manifest, "--", "--check"]),
        ]
        for label, cmd in steps:
            r = run(cmd, cwd=ex.root, timeout=600)
            if not r.ok:
                first = next(
                    (ln for ln in (r.err or r.out).split("\n") if ln.startswith(("error", "Diff"))),
                    (r.err or r.out).strip()[:120],
                )
                yield fail(f"{label}: {first[:150]}", "rust")

        env_doc = ["cargo", "doc", "--quiet", "--no-deps", "--manifest-path", manifest]
        r = run(env_doc, cwd=ex.root, timeout=600)
        if not r.ok:
            yield fail(f"intra-doc links: {r.err.strip().splitlines()[:1]}", "rust")

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """A shipped test must be able to fail.

        A block once carried a test that passed whether or not the function did
        anything: the assertion only checked that a buffer stayed empty, and
        gutting the function kept it empty.
        """
        src = ex.root / "src"
        base = run(["cargo", "test", "-q"], cwd=ex.root, timeout=600)
        if not base.ok:
            yield fail("the unmutated crate does not pass; nothing to mutate", "rust")
            return

        for path, lineno, stmt in _targets(src):
            original = path.read_text()
            lines = original.split("\n")
            path.write_text("\n".join(lines[:lineno] + lines[lineno + 1 :]))
            try:
                # Deleting a loop increment turns a test into a hang; a mutant
                # that never finishes is one the tests killed.
                r = run(["cargo", "test", "-q"], cwd=ex.root, timeout=120)
                if r.ok:
                    yield fail(
                        f"`{stmt[:56]}` can be deleted and every test still passes",
                        f"{path.name}:{lineno + 1}",
                    )
            finally:
                path.write_text(original)


def _module(stem: str, chapter: str, mods: list[tuple[str, str]]) -> str:
    out = [f"//! Blocks extracted from `references/{chapter}`.", ""]
    for mod, body in mods:
        # `mycrate::` is the placeholder a reader replaces with their own crate.
        # Point it at this crate so the doctest runs; the skill keeps the
        # placeholder, which is why the old apparatus leaked its own crate name.
        body = body.replace("mycrate::", f"{CRATE.replace('-', '_')}::{stem}::{mod}::")
        # `crate::` in a block means the reader's own crate root. Wrapping the
        # block in a module moves that root, so rebase it here rather than making
        # the published example spell a path it does not mean. `$crate::` is
        # macro syntax and must survive untouched.
        body = (
            body.replace("$crate::", "\x00")
            .replace("crate::", f"crate::{stem}::{mod}::")
            .replace("\x00", "$crate::")
        )
        out.append(f"pub mod {mod} {{")
        out.append("    #![allow(dead_code, unused_imports)]")
        out += [("    " + ln) if ln.strip() else "" for ln in body.rstrip("\n").split("\n")]
        out += ["}", ""]
    return "\n".join(out).rstrip("\n") + "\n"


#: A statement worth deleting: not a declaration, brace, attribute, or doc.
#: Excluding `let mut ` but not `let ` was arbitrary — deleting either breaks
#: compilation, so both are mutants that cost a full `cargo test` and can only
#: ever be killed. The zig side draws the same line at `const`/`var`.
_SKIP = ("use ", "//", "#", "let ", "pub ", "}")


def _targets(src: Path):
    for path in sorted(src.glob("*.rs")):
        text = path.read_text()
        for m in re.finditer(r"^pub mod (\w+) \{$", text, re.M):
            start = m.start()
            nxt = text.find("\npub mod ", start + 1)
            seg = text[start : nxt if nxt != -1 else len(text)]
            if "#[cfg(test)]" not in seg:
                continue
            body_start = text[:start].count("\n")
            for j, line in enumerate(seg[: seg.index("#[cfg(test)]")].split("\n")):
                s = line.strip()
                if (
                    s.endswith(";")
                    and not s.startswith(_SKIP)
                    and "struct" not in s
                    and "enum" not in s
                ):
                    yield path, body_start + j, s


RUST = Rust()
