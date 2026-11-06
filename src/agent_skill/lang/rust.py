"""A skill's rust examples, as a crate.

And everything else the harness knows about Rust: how a `Decided by
tools` row is checked against the shipped `[workspace.lints]`, how the
`rust-version` and a library's pin are compared with what runs and what
is released, and how `fmt` rewrites a block the way rustfmt would.
"""

import json
import re
import tempfile
from dataclasses import dataclass, field
from functools import cache
from itertools import groupby
from pathlib import Path
from types import MappingProxyType
lazy import urllib.request
lazy from collections.abc import Iterable, Iterator, Mapping

from agent_skill.ids import Op, Pin, Version
from agent_skill.lang import Extraction, Language, Unit, inconclusive, timed_out
from agent_skill.proc import Ran, have, run
from agent_skill.report import Finding, Level, declare, fail, unrun
from agent_skill.text import group
lazy from agent_skill.checks.citations import Row, rows_of
lazy from agent_skill.checks.lints import CARGO, table
lazy from agent_skill.checks.pins import _sort_key
lazy from agent_skill.fmt import (
    CARGO_FMT,
    MODULES,
    put_back,
)
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Skill

# The branches of `toolchain` and of `mutation` Rust's steps report
# through. A crate is built whole, so each finding lies in the skill.
STEP_TIMEOUT = declare("toolchain", "rust_timeout", Level.FAIL)
STEP = declare("toolchain", "rust_step", Level.FAIL)
BASE_TIMEOUT = declare("mutation", "rust_base_timeout", Level.FAIL)
BASE = declare("mutation", "rust_base", Level.FAIL)
HUNG = declare("mutation", "rust_inconclusive", Level.NOTE)
SURVIVOR = declare("mutation", "rust_survivor", Level.FAIL)

# The branches of `citations` Rust's lint rows report through.
TOOL_ABSENT = declare("citations", "rust_tool_absent", Level.UNRUN)
NO_CARGO_TOML = declare("citations", "no_cargo_toml", Level.FAIL)
CATALOGUE_UNREAD = declare("citations", "rust_catalogue_unread", Level.UNRUN)
UNKNOWN_LINT = declare("citations", "rust_unknown_lint", Level.FAIL)
LINT_LEVEL = declare("citations", "rust_level", Level.FAIL)

# The branches of `pins` the Rust pin and a library's report through.
RUSTC_SILENT = declare("pins", "rustc_silent", Level.UNRUN)
RUSTC_DIFFERS = declare("pins", "rustc_differs", Level.FAIL)
STABLE_SILENT = declare("pins", "stable_silent", Level.UNRUN)
RUST_STALE = declare("pins", "rust_stale", Level.FAIL)
CRATES_SILENT = declare("pins", "crates_silent", Level.UNRUN)
LIBRARY_UNORDERED = declare("pins", "library_unordered", Level.UNRUN)
LIBRARY_STALE = declare("pins", "library_stale", Level.FAIL)

#: The `[lints]` table each Rust row's tool is configured under.
SECTION = {"rustc": "rust", "clippy": "clippy", "rustdoc": "rustdoc"}

#: The levels at which a Rust lint fails a run, under `-D warnings`.
LINT_LEVELS = frozenset({"warn", "deny", "forbid"})

#: `'` opens a lifetime (`&'a str`) rather than a string, so only `"`
#: delimits one: as a delimiter it swallowed the rest of the line.
LANGUAGE = Language("rust", suffix=".rs")

#: Shared, gitignored, and safe to delete: cargo rebuilds it.
CACHE = Path(__file__).resolve().parents[3] / ".cache" / "target"


#: The Rust release a crate is compiled under unless it says otherwise.
RUST_RELEASE = Pin.parse("rust==1.99")


@dataclass(frozen=True, slots=True)
class Library:
    """The crate a standard is about, pinned exactly, with its features.

    No default features: a standard talks about the API surface, and the
    backends cost minutes of build time to compile examples that never
    run.
    """

    #: As Cargo pins exactly, `bevy=0.20.1`: a caret requirement lets
    #: the resolver pick a release the examples were never compiled
    #: against.
    pin: Pin
    features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse a pin Cargo would not read as one release."""
        if self.pin.op is not Op.CARGO:
            msg = f"a library is pinned as Cargo pins one release: {self.pin}"
            raise ValueError(msg)

    def dependency(self) -> str:
        """Its line under `[dependencies]`."""
        features = ", ".join(f'"{f}"' for f in self.features)
        return (
            f'{self.pin.tool} = {{ version = "{self.pin.op.value}{self.pin.version}", '
            f"default-features = false, features = [{features}] }}"
        )


@dataclass(frozen=True, slots=True)
class RustCrate:
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
    rust: Pin = RUST_RELEASE
    #: the crate the examples are written against, for a standard whose
    #: subject is a library rather than the language
    library: Library | None = None

    @property
    def pin(self) -> Pin:
        """The language release the crate is compiled under."""
        return self.rust

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
        library = (self.library.dependency(),) if self.library else ()
        deps = "\n".join((*self.dependencies, *library))
        return (
            f'[package]\nname = "{self.name}"\nversion = "0.1.0"\nedition = "2024"\n'
            f'rust-version = "{self.rust.version}"\n\n[dependencies]\n{deps}\n'
            "\n[workspace]\n\n" + lints + "\n"
        )


#: The table `rust-style` ships (`assets/Cargo.toml`) minus the two
#: entries a fragment cannot satisfy: `missing_docs` (blocks document
#: items selectively) and `unsafe_code = "forbid"` (the unsafe-ffi
#: chapter exists). Everything else is enforced verbatim, and
#: checks/lints.py compares the two so they cannot drift —
#: `undocumented_unsafe_blocks` was once dropped here with nothing
#: saying so, which left `undocumented_unsafe_blocks` unverified.
RUST_STYLE = RustCrate(
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


#: Bevy, as `bevy-style`'s examples use it. The features are the
#: `*_api` collections plus `scene`: every type a game names, without
#: `bevy_render`, winit or wgpu. A standard talks about the API surface,
#: and the backends cost minutes of build time to compile examples that
#: never run. `scene` is there for one example —
#: `bsn!` is the newest surface in Bevy and the only one whose grammar
#: is not Rust, so it is the one that most needs a compiler behind it.
#: `bevy_ui_widgets` is there because 0.20's text input is a widget: the
#: `ui` collection a game uses includes it, `ui_api` does not.
BEVY = Library(
    Pin.parse("bevy=0.20.1"),
    features=("std", "2d_api", "3d_api", "ui_api", "scene", "bevy_ui_widgets"),
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
BEVY_STYLE = RustCrate(
    name="bevy-style-verify",
    library=BEVY,
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
    language: Language = LANGUAGE
    needs: tuple[str, ...] = ("cargo",)
    #: Each row's tool, and the levels at which it fails a run.
    rows: Mapping[str, frozenset[str]] = MappingProxyType(
        dict.fromkeys(SECTION, LINT_LEVELS)
    )
    compilers: frozenset[str] = frozenset[str]()
    cites_with: tuple[str, ...] = ("clippy-driver", "rustdoc")
    pins_with: tuple[str, ...] = ("rustc",)
    asset_suffixes: tuple[str, ...] = ()
    assets_with: tuple[str, ...] = ()

    def missing(self) -> list[str]:
        """`cargo` itself, when it is not on PATH."""
        return [f"`{tool}` is not on PATH" for tool in self.needs if not have(tool)]

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

    def cite(self, skill: Skill) -> Iterator[Finding]:
        """The Rust rows, against the shipped `[workspace.lints]`."""
        # Asked before looking for rows: a check that declares a tool
        # and returns early without it reports clean while it could not
        # have looked.
        for tool in self.cites_with:
            if not have(tool):
                yield unrun(
                    f"`{tool}` is not available, so no Rust lint row was compared",
                    skill.at(),
                    TOOL_ABSENT,
                )
                return
        rows = [(where, row) for where, row in rows_of(skill) if row.tool in SECTION]
        manifest = skill.root / CARGO
        if not rows:
            return
        if not manifest.exists():
            yield fail(
                f"Rust lint rows, and no `{CARGO}` to enforce them",
                skill.at(),
                NO_CARGO_TOML,
            )
            return
        catalogue = rust_catalogue()
        if catalogue is None:
            yield unrun(
                "`clippy-driver` or `rustdoc` did not list its lints",
                skill.at(),
                CATALOGUE_UNREAD,
            )
            return

        shipped = table(manifest.read_text(), "workspace.")
        yield from rust_rows(rows, shipped, catalogue)

    def pins(self, skill: Skill) -> Iterator[Finding]:
        """The `rust-version`, and the library's pin when it has one."""
        crate = skill.profile.crate
        if crate is None:
            return
        where = skill.at()
        yield from rust_pin(crate.rust.version, _rustc(), _stable(), where)
        if crate.library is not None:
            pin = crate.library.pin
            yield from library_pin(pin, _crates_io(pin.tool), where)

    def asset(self, path: Path, where: Location) -> Iterator[Finding]:  # noqa: ARG002 — no asset is Rust's to read
        """Nothing: `assets` reads a manifest as TOML, as any other."""
        return iter(())

    def format(self, skill: Skill) -> list[Finding]:
        """Rewrite each `// verified` rust block as rustfmt would."""
        # `RUST.extract` builds from this crate, so this is
        # `extraction.crate`, with the type that field does not carry.
        crate = skill.profile.crate
        if crate is None:
            return []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
            extraction = self.extract(skill, Path(work) / "out")
            if not extraction:
                return []
            r = run(["cargo", "fmt"], cwd=extraction.root, timeout=300, env=crate.env)
            if not r.ok:
                said = (r.err or r.out).strip()[:160]
                return [fail(f"cargo fmt failed: {said}", skill.at(), CARGO_FMT)]

            changed: list[Finding] = []
            fence = LANGUAGE.fence
            for chapter, blocks in groupby(skill.blocks(fence), key=lambda b: b.file):
                wanted = [b for b in blocks if b.marker.verified and b.rule != "?"]
                src = extraction.root / "src" / f"{module_name(chapter)}.rs"
                if not wanted or not src.exists():
                    continue
                bodies = module_bodies(src, crate)
                if len(bodies) != len(wanted):
                    changed.append(
                        fail(
                            f"{len(wanted)} blocks, {len(bodies)} modules; skipped",
                            skill.at(chapter),
                            MODULES,
                        )
                    )
                    continue
                # Last first, so an earlier replacement cannot move a
                # later block.
                edits = reversed(list(zip(wanted, bodies, strict=True)))
                changed += put_back(skill, chapter, fence, edits)
            return changed


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


def _crate(ex: Extraction) -> RustCrate:
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


def _module(
    crate: RustCrate, stem: str, chapter: str, mods: list[tuple[str, str]]
) -> str:
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


#: The line the extractor injects into every block module.
INJECTED = "#![allow(dead_code, unused_imports)]"

_MODULE = re.compile(r"^pub mod (\w+) \{$", re.MULTILINE)


def module_bodies(path: Path, crate: RustCrate) -> list[str]:
    """Each `pub mod`'s dedented body, the extractor's rebasing undone.

    `_module` rewrites `crate::` and `mycrate::` to point inside the
    wrapper module, so the block compiles where it is put. Writing that
    back would store the harness's own path in the skill — the leak the
    extractor's comment warns about, arriving by the other door — so it
    is inverted here. Round-tripping a block through `fmt` has to be the
    identity on everything except whitespace.
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


def rust_rows(
    rows: Iterable[Row],
    shipped: dict[str, str],
    catalogue: dict[str, tuple[str, set[str]]],
) -> Iterator[Finding]:
    """Each Rust row not enforced as the row states.

    The shipped `[workspace.lints]` is what enforces them. `shipped` is
    the asset's table as `lints.table` reads it (`clippy.unwrap_used` ->
    `"deny"`). `catalogue` maps every lint the pinned toolchain knows,
    spelled as a `[lints]` key under its tool's section, to its default
    level and its groups. A lint's level is its own entry, else the
    entry of a group it belongs to, else its default — the order Cargo
    applies them in, given the groups' `priority = -1`.
    """
    for where, row in rows:
        section = SECTION.get(row.tool)
        if section is None:
            continue
        key = f"{section}.{row.lint}"
        if key not in catalogue:
            yield fail(
                f"`{row.lint}` is not a {row.tool} lint the pinned toolchain knows",
                where,
                UNKNOWN_LINT,
            )
            continue
        default, groups = catalogue[key]
        level = _level(shipped.get(key, "")) or next(
            (
                _level(shipped[f"{section}.{g}"])
                for g in sorted(groups)
                if f"{section}.{g}" in shipped
            ),
            default,
        )
        if level != row.level:
            yield fail(
                f"`{row.lint}` is `{row.level}` in the row and `{level}` as shipped",
                where,
                LINT_LEVEL,
            )


def _level(value: str) -> str:
    return group(re.search(r'"(allow|warn|deny|forbid)"', value))


def rust_catalogue() -> dict[str, tuple[str, set[str]]] | None:
    """Every lint the Rust toolchain knows, keyed as a `[lints]` entry.

    As `clippy-driver` and `rustdoc` list them; None when either cannot.
    """
    out: dict[str, tuple[str, set[str]]] = {}
    members: dict[str, set[str]] = {}
    for tool in RUST.cites_with:
        if not have(tool):
            return None
        answered = run([tool, "-W", "help"], timeout=60)
        if not answered.ok:
            return None
        _read_help(answered.out, out, members)
    for key, groups in members.items():
        if key in out:
            out[key] = (out[key][0], out[key][1] | groups)
    return out


def _read_help(
    text: str,
    out: dict[str, tuple[str, set[str]]],
    members: dict[str, set[str]],
) -> None:
    """Fold one tool's `-W help` listing into `out` and `members`."""
    section = "lints"
    for line in text.split("\n"):
        if line.startswith("Lint groups"):
            section = "groups"
        elif line.startswith("Lint checks"):
            section = "lints"
        if section == "lints":
            if m := re.match(r"^\s+(\S+)\s+(allow|warn|deny|forbid)\s", line):
                out[_key(m.group(1))] = (m.group(2), set())
        elif m := re.match(r"^\s+(\S+)\s+(\S.*)$", line):
            group, names = _key(m.group(1)), m.group(2)
            for name in names.split(", "):
                members.setdefault(_key(name.strip()), set()).add(
                    group.split(".", 1)[1]
                )


def _key(name: str) -> str:
    """A lint's name, spelled as a `[lints]` key.

    `clippy::unwrap-used` -> `clippy.unwrap_used`; `unsafe-code` ->
    `rust.unsafe_code`.
    """
    tool, _, lint = name.rpartition("::")
    return f"{tool or SECTION['rustc']}.{lint.replace('-', '_')}"


#: Where the Rust project publishes what the current stable release is.
STABLE = "https://static.rust-lang.org/dist/channel-rust-stable.toml"


def rust_pin(
    pinned: Version, running: str, newest: str, where: Location
) -> Iterator[Finding]:
    """What is wrong with a `rust-version` pin, if anything.

    Compared at the pin's own precision. `running` is what `rustc -V`
    reports and `newest` what the stable channel names; either is ""
    when it could not be asked.
    """
    want = (pinned.release[0], pinned.release[1])
    if not running:
        yield unrun(
            "could not ask `rustc` its version, "
            f"so the Rust pin {pinned} was not compared",
            where,
            RUSTC_SILENT,
        )
    elif _minor(running) != want:
        yield fail(
            f"the examples are pinned to Rust {pinned} and `rustc` here is {running}",
            where,
            RUSTC_DIFFERS,
        )
    if not newest:
        yield unrun(
            "the stable channel did not answer, "
            "so the Rust pin was not compared with it",
            where,
            STABLE_SILENT,
        )
    elif (there := _minor(newest)) is not None and there > want:
        yield fail(
            f"the Rust pin is {pinned} and {newest} is stable — move "
            "`rust` in `lang/rust.py` and the assets, re-read the "
            "release notes, and re-run the suite",
            where,
            RUST_STALE,
        )


def _minor(version: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d+)\.(\d+)", version)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _rustc() -> str:
    if not have("rustc"):
        return ""
    answered = run(["rustc", "-V"], timeout=30)
    return group(re.match(r"^rustc (\S+)", answered.out)) if answered.ok else ""


@cache
def _stable() -> str:
    """What the stable channel names, asked once a run.

    `pins` reads every skill even when a control broke one of them, so
    two Rust skills and four pin controls would otherwise ask the
    network the same question ten times.
    """
    try:
        with urllib.request.urlopen(STABLE, timeout=30) as response:
            text = response.read().decode()
    except OSError:
        return ""
    return group(re.search(r'^\[pkg\.rust\]\nversion = "(\S+)', text, re.MULTILINE))


def library_pin(pin: Pin, newest: str, where: Location) -> Iterator[Finding]:
    """What is wrong with the pin on the library the examples use.

    Exact by construction (`Library` refuses any other), so what is left
    to ask is whether a newer release is out.
    """
    name, pinned = pin.tool, str(pin.version)
    if not newest:
        yield unrun(
            f"crates.io did not answer, so the `{name}` pin {pinned} was not compared",
            where,
            CRATES_SILENT,
        )
        return
    here, there = _sort_key(pinned), _sort_key(newest)
    if here is None or there is None:
        yield unrun(
            f"`{name}` was not compared: {pinned} or {newest} is not a "
            "version this orders",
            where,
            LIBRARY_UNORDERED,
        )
    elif there > here:
        yield fail(
            f"`{name}` is pinned to {pinned} and {newest} is released — move "
            "the pin in `lang/rust.py` and the assets, read the migration "
            "guide, and re-run the suite",
            where,
            LIBRARY_STALE,
        )


@cache
def _crates_io(name: str) -> str:
    """The newest release of crate `name`, asked once a run."""
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"https://crates.io/api/v1/crates/{name}",
                headers={"User-Agent": "agent-skill pins check"},
            ),
            timeout=30,
        ) as response:
            newest = json.load(response)["crate"]["max_stable_version"]
    except OSError, KeyError, ValueError:
        return ""
    # An answer that is not a version string is no answer, the same as
    # one that never arrived.
    return newest if isinstance(newest, str) else ""


RUST = Rust()
