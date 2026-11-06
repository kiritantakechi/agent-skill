"""A skill's rust examples, as a crate."""

import re
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
lazy from collections.abc import Iterable, Iterator

from agent_skill.lang import Extraction, Language, Unit, inconclusive, timed_out
from agent_skill.proc import Ran, have, run
from agent_skill.report import Finding, Level, declare, fail
lazy from agent_skill.model import Skill

# The branches of `toolchain` and of `mutation` Rust's steps report
# through. A crate is built whole, so each finding lies in the skill.
STEP_TIMEOUT = declare("toolchain", "rust_timeout", Level.FAIL)
STEP = declare("toolchain", "rust_step", Level.FAIL)
BASE_TIMEOUT = declare("mutation", "rust_base_timeout", Level.FAIL)
BASE = declare("mutation", "rust_base", Level.FAIL)
HUNG = declare("mutation", "rust_inconclusive", Level.NOTE)
SURVIVOR = declare("mutation", "rust_survivor", Level.FAIL)

#: `'` opens a lifetime (`&'a str`) rather than a string, so only `"`
#: delimits one: as a delimiter it swallowed the rest of the line.
LANGUAGE = Language("rust", suffix=".rs")

#: Shared, gitignored, and safe to delete: cargo rebuilds it.
CACHE = Path(__file__).resolve().parents[3] / ".cache" / "target"


@dataclass(frozen=True, slots=True)
class Crate:
    """The crate one skill's `// verified` blocks are compiled as.

    Per **skill**, not per language. `bevy-style`'s examples need Bevy
    on the dependency line and a lint table two entries looser than
    `rust-style`'s, and a single shared manifest would have left one of
    the two skills unverifiable — which is indistinguishable from
    verified.
    """

    name: str
    #: the table the extracted crate is compiled under;
    #: `checks/lints.py` compares it against the one the skill ships in
    #: `assets/Cargo.toml`
    lints: dict[str, dict[str, str]]
    #: shipped entries the extracted crate legitimately cannot carry
    unverifiable: frozenset[str] = frozenset()
    dependencies: tuple[str, ...] = ()
    #: `clippy.toml` beside the manifest; `checks/lints.py` compares it
    #: with the one the skill ships, the same way it compares the lint
    #: table
    clippy: dict[str, object] = field(default_factory=dict)
    #: The Rust release the examples are verified against, at the
    #: precision `rust-version` takes. `pins` compares it with
    #: `rustc -V` and with the newest stable release, at that same
    #: precision: a patch release is not a new target, a minor release
    #: is.
    rust_version: str = "1.99"

    @property
    def ident(self) -> str:
        """The crate's name as a Rust path spells it."""
        return self.name.replace("-", "_")

    @property
    def env(self) -> dict[str, str]:
        """A build directory that outlives the extraction.

        Extraction goes to a fresh temporary directory every run, so
        without this every check rebuilds the dependency tree from
        scratch — 47 seconds for Bevy, five times over (build, clippy,
        test, doc, and again for the mutation pass). Keyed by crate name
        so two skills with different dependency sets do not evict each
        other.
        """
        return {"CARGO_TARGET_DIR": str(CACHE / self.name)}

    def clippy_toml(self) -> str:
        """The `clippy.toml` written beside the manifest."""

        def value(v: object) -> str:
            return (
                str(v).lower()
                if isinstance(v, bool)
                else f'"{v}"'
                if isinstance(v, str)
                else str(v)
            )

        return "".join(f"{k} = {value(v)}\n" for k, v in self.clippy.items())

    def manifest(self) -> str:
        """The `Cargo.toml` the extracted crate is built from."""
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


#: The table `rust-style` ships (`assets/Cargo.toml`) minus the two
#: entries a fragment cannot satisfy: `missing_docs` (blocks document
#: items selectively) and `unsafe_code = "forbid"` (the unsafe-ffi
#: chapter exists). Everything else is enforced verbatim, and
#: checks/lints.py compares the two so they cannot drift —
#: `undocumented_unsafe_blocks` was once dropped here with nothing
#: saying so, which left `undocumented_unsafe_blocks` unverified.
RUST_STYLE = Crate(
    name="rust-style-verify",
    dependencies=('thiserror = "2"',),
    clippy={
        "avoid-breaking-exported-api": False,
        "allow-unwrap-in-tests": True,
        "allow-expect-in-tests": True,
        "upper-case-acronyms-aggressive": True,
    },
    #: `allow_attributes*` join the two above for the same reason they
    #: are unverifiable in `BEVY_STYLE`: the extractor injects a bare
    #: `#![allow(dead_code, unused_imports)]` into every block module,
    #: and a lint about the author's attributes cannot be judged on the
    #: harness's.
    unverifiable=frozenset(
        {
            "rust.missing_docs",
            "rust.unsafe_code",
            "clippy.allow_attributes",
            "clippy.allow_attributes_without_reason",
        }
    ),
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
            "redundant_test_prefix": '"warn"',
            "mod_module_files": '"warn"',
        },
        "rustdoc": {
            "broken_intra_doc_links": '"deny"',
        },
    },
)


#: `bevy-style`'s crate. Two entries are looser than `rust-style`'s, and
#: both were measured rather than assumed:
#:
#:   * `elided_lifetimes_in_paths` fires on **every** system parameter —
#:     fourteen hits in one five-system plugin. Writing
#:     `Query<'_, '_, …>` and `Res<'_, T>` does satisfy it and does stay
#:     a valid system, so this is a noise judgement, not an
#:     impossibility (BV-BUILD-12).
#:   * `needless_pass_by_value` fires on every `Res<T>`, and its
#:     suggestion does not compile: `&Res<'_, T>` is not a `SystemParam`
#:     (E0277). This one has no compliant form (BV-BUILD-13).
#:
#: `type_complexity` and `too_many_arguments` also fire on ordinary Bevy
#: code and are deliberately **not** here: a `type` alias and
#: `#[derive(SystemParam)]` silence them, and both are the better code
#: (BV-ECS-19, BV-SCHED-09).
#:
#: The features are the `*_api` collections plus `scene`: every type a
#: game names, without `bevy_render`, winit or wgpu. A standard talks
#: about the API surface, and the backends cost minutes of build time to
#: compile examples that never run. `scene` is there for one example —
#: `bsn!` is the newest surface in Bevy and the only one whose grammar
#: is not Rust, so it is the one that most needs a compiler behind it.
#: `bevy_ui_widgets` is there because 0.20's text input is a widget: the
#: `ui` collection a game uses includes it, `ui_api` does not.
BEVY_STYLE = Crate(
    name="bevy-style-verify",
    dependencies=(
        (
            'bevy = { version = "=0.20.1", default-features = false, features = ['
            '"std", "2d_api", "3d_api", "ui_api", "scene", "bevy_ui_widgets"] }'
        ),
    ),
    #: `missing_docs` because a block documents items selectively;
    #: `allow_attributes*` because the extractor itself injects a bare
    #: `#![allow(dead_code, unused_imports)]` into every block module,
    #: and a lint about the author's attributes cannot be judged on the
    #: harness's.
    unverifiable=frozenset(
        {
            "rust.missing_docs",
            "clippy.allow_attributes",
            "clippy.allow_attributes_without_reason",
        }
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
            "undocumented_unsafe_blocks": '"deny"',
            "mem_forget": '"deny"',
            "cast_possible_truncation": '"warn"',
            "cast_precision_loss": '"warn"',
            "cast_sign_loss": '"warn"',
            "float_cmp": '"warn"',
            "needless_pass_by_value": '"allow"',
        },
    },
)


class Rust:
    """The `cargo` toolchain: every verified block, in one crate."""

    name = "rust"
    tool = "cargo"
    language = LANGUAGE

    def missing(self) -> list[str]:
        """`cargo` itself, when it is not on PATH."""
        return [] if have(self.tool) else [f"`{self.tool}` is not on PATH"]

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write the verified blocks as a crate of chapter modules."""
        crate = skill.profile.crate
        if crate is None:
            msg = f"{skill.name} compiles rust examples and its profile names no crate"
            raise ValueError(msg)
        src = out / "src"
        src.mkdir(parents=True, exist_ok=True)
        # A renamed chapter otherwise leaves a module lib.rs never
        # declares, which the mutation pass still globs: deleting a line
        # in a file nothing compiles can never change a test result, so
        # every statement survives.
        for stale in src.glob("*.rs"):
            stale.unlink()

        ex = Extraction(out, crate=crate, skill=skill.name)
        chapters: list[str] = []
        for chapter, blocks in groupby(skill.blocks("rust"), key=lambda b: b.file):
            mods: list[tuple[str, str]] = []
            for b in blocks:
                if not b.marker.verified or b.rule == "?":
                    continue
                base = b.rule.lower().replace("-", "_")
                n = sum(1 for m, _ in mods if m == base or m.startswith(base + "_"))
                mods.append((base if n == 0 else f"{base}_{n}", b.body))
                ex.units.append(Unit(src, chapter, b.line, b.rule, skill.name))
            if not mods:
                continue
            stem = module_name(chapter)
            chapters.append(stem)
            (src / f"{stem}.rs").write_text(_module(crate, stem, chapter, mods))

        lib = [
            (
                f"//! Every `// verified` block in {skill.name}, "
                "extracted from the markdown."
            )
        ]
        lib += [f"pub mod {s};" for s in sorted(chapters)]
        (src / "lib.rs").write_text("\n".join(lib) + "\n")
        (out / "Cargo.toml").write_text(crate.manifest())
        if crate.clippy:
            (out / "clippy.toml").write_text(crate.clippy_toml())
        return ex

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        """Build, lint, test, format-check and document the crate."""
        manifest = str(ex.root / "Cargo.toml")
        env = _crate(ex).env
        steps = [
            ("compiles", ["cargo", "build", "--quiet", "--manifest-path", manifest]),
            # `-D warnings` so the whole shipped table binds. Half of it
            # is `warn`, and clippy exits 0 on a warning — so without
            # this the check could only ever fail on the `deny` half.
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
            (
                "intra-doc links",
                ["cargo", "doc", "--quiet", "--no-deps", "--manifest-path", manifest],
            ),
        ]
        for label, cmd in steps:
            r = run(cmd, cwd=ex.root, timeout=_STEP, env=env)
            if r.timed_out:
                yield timed_out(label, _STEP, ex.where, STEP_TIMEOUT)
            elif not r.ok:
                remedy = (
                    " — `agent-skill fmt` rewrites the blocks"
                    if label == "rustfmt"
                    else ""
                )
                yield fail(f"{label}: {_first_error(r)[:150]}{remedy}", ex.where, STEP)

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """A shipped test must be able to fail.

        A block once carried a test that passed whether or not the
        function did anything: the assertion only checked that a buffer
        stayed empty, and gutting the function kept it empty.
        """
        src = ex.root / "src"
        env = _crate(ex).env
        base = run(["cargo", "test", "-q"], cwd=ex.root, timeout=_STEP, env=env)
        if base.timed_out:
            yield timed_out(
                "the unmutated crate's tests", _STEP, ex.where, BASE_TIMEOUT
            )
            return
        if not base.ok:
            yield fail(
                "the unmutated crate does not pass; nothing to mutate", ex.where, BASE
            )
            return

        for path, lineno, stmt in _targets(src):
            original = path.read_text()
            lines = original.split("\n")
            # The crate's module file, not the markdown: tracing a line
            # of it back to its block needs the block each module holds.
            spot = f"{path.name}:{lineno + 1}"
            path.write_text("\n".join(lines[:lineno] + lines[lineno + 1 :]))
            try:
                r = run(["cargo", "test", "-q"], cwd=ex.root, timeout=180, env=env)
                if r.timed_out:
                    yield inconclusive(stmt, ex.where, HUNG, extracted=spot)
                elif r.ok:
                    # Survivors are rare, so a second opinion is nearly
                    # free — and it is what stands between a transient
                    # and a reported defect that the example does not
                    # actually have.
                    again = run(
                        ["cargo", "test", "-q"], cwd=ex.root, timeout=300, env=env
                    )
                    if again.timed_out:
                        yield inconclusive(stmt, ex.where, HUNG, extracted=spot)
                    elif again.ok:
                        yield fail(
                            f"{spot}: `{stmt[:56]}` can be deleted and every test "
                            "still passes",
                            ex.where,
                            SURVIVOR,
                        )
            finally:
                path.write_text(original)


#: How long one cargo step may take: Bevy builds from cold in minutes.
_STEP = 900


def _first_error(r: Ran) -> str:
    """The line of `r`'s output that says what went wrong.

    The first `error` or `Diff` line, else the start of the output, and
    the exit status when there was no output at all.
    """
    said = (r.err or r.out).strip()
    lines = said.split("\n")
    first = next((ln for ln in lines if ln.startswith(("error", "Diff"))), said[:120])
    return first or f"exited {r.rc} and said nothing"


def _crate(ex: Extraction) -> Crate:
    """The crate `Rust.extract` recorded on `ex`."""
    if ex.crate is None:
        msg = "a rust extraction carries the crate it was extracted as"
        raise ValueError(msg)
    return ex.crate


#: Words a chapter may be named that Rust will not take as a module
#: name.
KEYWORDS = frozenset(
    [
        "as",
        "async",
        "await",
        "break",
        "const",
        "continue",
        "crate",
        "dyn",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "gen",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
    ]
)


def module_name(chapter: str) -> str:
    """The module a chapter's blocks are compiled as.

    `unsafe.md` -> `unsafe_`: the shared vocabulary names a chapter
    `unsafe`, and `pub mod unsafe;` does not parse.
    """
    stem = Path(chapter).stem.replace("-", "_")
    return f"{stem}_" if stem in KEYWORDS else stem


def _module(crate: Crate, stem: str, chapter: str, mods: list[tuple[str, str]]) -> str:
    out = [f"//! Blocks extracted from `references/{chapter}`.", ""]
    for mod, body in mods:
        # `mycrate::` is the placeholder a reader replaces with their
        # own crate. Point it at this crate so the doctest runs; the
        # skill keeps the placeholder, which is why the old apparatus
        # leaked its own crate name.
        code = body.replace("mycrate::", f"{crate.ident}::{stem}::{mod}::")
        # `crate::` in a block means the reader's own crate root.
        # Wrapping the block in a module moves that root, so rebase it
        # here rather than making the published example spell a path it
        # does not mean. `$crate::` names the same root from inside a
        # macro, so it moves with it — the replace covers both
        # spellings, and `fmt` undoes both the same way.
        code = code.replace("crate::", f"crate::{stem}::{mod}::")
        out.append(f"pub mod {mod} {{")
        out.append("    #![allow(dead_code, unused_imports)]")
        out += [
            ("    " + ln) if ln.strip() else "" for ln in code.rstrip("\n").split("\n")
        ]
        out += ["}", ""]
    return "\n".join(out).rstrip("\n") + "\n"


#: A statement worth deleting: not a declaration, brace, attribute, or
#: doc. Excluding `let mut ` but not `let ` was arbitrary — deleting
#: either breaks compilation, so both are mutants that cost a full
#: `cargo test` and can only ever be killed. The zig side draws the same
#: line at `const`/`var`.
_SKIP = ("use ", "//", "#", "let ", "pub ", "}")


def _targets(src: Path) -> Iterator[tuple[Path, int, str]]:
    """Each statement outside a test worth deleting, and where it is."""
    for path in sorted(src.glob("*.rs")):
        text = path.read_text()
        for m in re.finditer(r"^pub mod (\w+) \{$", text, re.MULTILINE):
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
