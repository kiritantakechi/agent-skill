"""A skill's rust examples, as a crate."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from ..proc import run
from ..report import Finding, fail
from . import Extraction, Unit

#: Shared, gitignored, and safe to delete: cargo rebuilds it.
CACHE = Path(__file__).resolve().parents[3] / ".cache" / "target"


@dataclass(frozen=True, slots=True)
class Crate:
    """The crate one skill's `// verified` blocks are compiled as.

    Per **skill**, not per language. `bevy-style`'s examples need Bevy on the
    dependency line and a lint table two entries looser than `rust-style`'s, and
    a single shared manifest would have left one of the two skills unverifiable —
    which is indistinguishable from verified.
    """

    name: str
    #: the table the extracted crate is compiled under; `checks/lints.py`
    #: compares it against the one the skill ships in `assets/Cargo.toml`
    lints: dict[str, dict[str, str]]
    #: shipped entries the extracted crate legitimately cannot carry
    unverifiable: frozenset[str] = frozenset()
    dependencies: tuple[str, ...] = ()
    rust_version: str = "1.98"

    @property
    def ident(self) -> str:
        return self.name.replace("-", "_")

    @property
    def env(self) -> dict[str, str]:
        """A build directory that outlives the extraction.

        Extraction goes to a fresh temporary directory every run, so without
        this every check rebuilds the dependency tree from scratch — 47
        seconds for Bevy, five times over (build, clippy, test, doc, and
        again for the mutation pass). Keyed by crate name so two skills
        with different dependency sets do not evict each other.
        """
        return {"CARGO_TARGET_DIR": str(CACHE / self.name)}

    def manifest(self) -> str:
        lints = "\n".join(
            f"[lints.{section}]\n" + "\n".join(f"{k} = {v}" for k, v in table.items())
            for section, table in self.lints.items()
        )
        deps = "\n".join(self.dependencies)
        return (
            f'[package]\nname = "{self.name}"\nversion = "0.1.0"\nedition = "2024"\n'
            f'rust-version = "{self.rust_version}"\n\n[dependencies]\n{deps}\n'
            "\n[workspace]\n\n" + lints + "\n"
        )


#: The table `rust-style` ships (`assets/Cargo.toml`) minus the two entries a
#: fragment cannot satisfy: `missing_docs` (blocks document items selectively)
#: and `unsafe_code = "forbid"` (the unsafe-ffi chapter exists). Everything else
#: is enforced verbatim, and checks/lints.py compares the two so they cannot
#: drift — `undocumented_unsafe_blocks` was once dropped here with nothing saying
#: so, which left RS-CAR-29 unverified.
RUST_STYLE = Crate(
    name="rust-style-verify",
    dependencies=('thiserror = "2"',),
    unverifiable=frozenset({"rust.missing_docs", "rust.unsafe_code"}),
    lints={
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
    },
)


#: `bevy-style`'s crate. Two entries are looser than `rust-style`'s, and both
#: were measured rather than assumed:
#:
#:   * `elided_lifetimes_in_paths` fires on **every** system parameter — fourteen
#:     hits in one five-system plugin. Writing `Query<'_, '_, …>` and `Res<'_, T>`
#:     does satisfy it and does stay a valid system, so this is a noise
#:     judgement, not an impossibility (BV-CAR-11).
#:   * `needless_pass_by_value` fires on every `Res<T>`, and its suggestion does
#:     not compile: `&Res<'_, T>` is not a `SystemParam` (E0277). This one has no
#:     compliant form (BV-CAR-12).
#:
#: `type_complexity` and `too_many_arguments` also fire on ordinary Bevy code and
#: are deliberately **not** here: a `type` alias and `#[derive(SystemParam)]`
#: silence them, and both are the better code (BV-ECS-21, BV-SCH-10).
#:
#: The features are the `*_api` collections: every type a game names, without
#: `bevy_render`, winit or wgpu. A standard talks about the API surface, and the
#: backends cost minutes of build time to compile examples that never run.
BEVY_STYLE = Crate(
    name="bevy-style-verify",
    dependencies=(
        'bevy = { version = "=0.19.1", default-features = false, features = ['
        '"std", "2d_api", "3d_api", "ui_api"] }',
    ),
    #: `missing_docs` because a block documents items selectively;
    #: `allow_attributes*` because the extractor itself injects a bare
    #: `#![allow(dead_code, unused_imports)]` into every block module, and a
    #: lint about the author's attributes cannot be judged on the harness's.
    unverifiable=frozenset(
        {"rust.missing_docs", "clippy.allow_attributes", "clippy.allow_attributes_without_reason"}
    ),
    lints={
        "rust": {
            "unsafe_code": '"forbid"',
            "missing_debug_implementations": '"deny"',
            "unreachable_pub": '"warn"',
            "unused_qualifications": '"warn"',
            "explicit_outlives_requirements": '"warn"',
            "elided_lifetimes_in_paths": '"allow"',
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
            "mem_forget": '"deny"',
            "cast_possible_truncation": '"warn"',
            "cast_precision_loss": '"warn"',
            "cast_sign_loss": '"warn"',
            "float_cmp": '"warn"',
            "module_name_repetitions": '"allow"',
            "needless_pass_by_value": '"allow"',
        },
    },
)


class Rust:
    name = "rust"
    tool = "cargo"

    def extract(self, skill, out: Path) -> Extraction:
        crate = skill.profile.crate
        src = out / "src"
        src.mkdir(parents=True, exist_ok=True)
        # A renamed chapter otherwise leaves a module lib.rs never declares,
        # which the mutation pass still globs: deleting a line in a file nothing
        # compiles can never change a test result, so every statement survives.
        for stale in src.glob("*.rs"):
            stale.unlink()

        ex = Extraction(out, crate=crate)
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
            (src / f"{stem}.rs").write_text(_module(crate, stem, chapter, mods))

        lib = [f"//! Every `// verified` block in {skill.name}, extracted from the markdown."]
        lib += [f"pub mod {s};" for s in sorted(chapters)]
        (src / "lib.rs").write_text("\n".join(lib) + "\n")
        (out / "Cargo.toml").write_text(crate.manifest())
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        manifest = str(ex.root / "Cargo.toml")
        env = ex.crate.env
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
            r = run(cmd, cwd=ex.root, timeout=900, env=env)
            if not r.ok:
                first = next(
                    (ln for ln in (r.err or r.out).split("\n") if ln.startswith(("error", "Diff"))),
                    (r.err or r.out).strip()[:120],
                )
                remedy = " — `agent-skill fmt` rewrites the blocks" if label == "rustfmt" else ""
                yield fail(f"{label}: {first[:150]}{remedy}", "rust")

        env_doc = ["cargo", "doc", "--quiet", "--no-deps", "--manifest-path", manifest]
        r = run(env_doc, cwd=ex.root, timeout=900, env=env)
        if not r.ok:
            yield fail(f"intra-doc links: {r.err.strip().splitlines()[:1]}", "rust")

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """A shipped test must be able to fail.

        A block once carried a test that passed whether or not the function did
        anything: the assertion only checked that a buffer stayed empty, and
        gutting the function kept it empty.
        """
        src = ex.root / "src"
        env = ex.crate.env
        base = run(["cargo", "test", "-q"], cwd=ex.root, timeout=900, env=env)
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
                r = run(["cargo", "test", "-q"], cwd=ex.root, timeout=180, env=env)
                if r.ok:
                    yield fail(
                        f"`{stmt[:56]}` can be deleted and every test still passes",
                        f"{path.name}:{lineno + 1}",
                    )
            finally:
                path.write_text(original)


def _module(crate: Crate, stem: str, chapter: str, mods: list[tuple[str, str]]) -> str:
    out = [f"//! Blocks extracted from `references/{chapter}`.", ""]
    for mod, body in mods:
        # `mycrate::` is the placeholder a reader replaces with their own crate.
        # Point it at this crate so the doctest runs; the skill keeps the
        # placeholder, which is why the old apparatus leaked its own crate name.
        body = body.replace("mycrate::", f"{crate.ident}::{stem}::{mod}::")
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
