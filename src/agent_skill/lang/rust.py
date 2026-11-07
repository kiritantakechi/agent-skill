"""A skill's rust examples, as a crate of one module file per block.

And everything else the harness knows about Rust: how a `Decided by
tools` row is checked against the shipped `[workspace.lints]`, and how
the `rust-version` and a library's pin are compared with what runs and
what is released.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import MappingProxyType
lazy import urllib.request
lazy from collections.abc import Iterable, Iterator, Mapping

from agent_skill.doc.chapter import ELIDED
from agent_skill.ids import Op, Pin, Version
from agent_skill.lang import Extraction, Language, Step, Unit, extracted, unquoted
from agent_skill.proc import have, run
from agent_skill.report import Finding, Level, declare, fail, unrun
from agent_skill.text import group
lazy from agent_skill.checks.citations import Row, rows_of
lazy from agent_skill.checks.lints import CARGO, table
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Block, Skill

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

#: An attribute that makes the item under it a test.
_TEST = re.compile(r"^\s*#\[(?:cfg\(test\)|test)\]")


def inside_tests(body: str) -> set[int]:
    """Body-line indices inside a test, by brace depth.

    From a `#[cfg(test)]` or `#[test]` to the brace that closes the item
    it marks: a test module, or a test function outside one.
    """
    inside: set[int] = set()
    depth, active, opened = 0, False, False
    for i, line in enumerate(body.split("\n")):
        code = unquoted(LANGUAGE.uncommented(line), LANGUAGE.quotes)
        if not active and _TEST.match(code):
            active, depth, opened = True, 0, False
        if active:
            inside.add(i)
            depth += code.count("{") - code.count("}")
            opened = opened or "{" in code
            if opened and depth <= 0:
                active = False
    return inside


#: `'` opens a lifetime (`&'a str`) rather than a string, so only `"`
#: delimits one: as a delimiter it swallowed the rest of the line.
#:
#: A mutant deletes no binding or item declaration: removing one stops
#: the build, so it could only be killed, at the cost of a build.
LANGUAGE = Language(
    "rust",
    suffix=".rs",
    tests=inside_tests,
    kept=(
        *("use ", "let ", "pub ", "const ", "static ", "type ", "fn ", "mod "),
        *("struct ", "enum ", "trait ", "impl ", "extern ", "}"),
        *("assert!", "assert_eq!", "assert_ne!", "debug_assert"),
    ),
)

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
            f'[package]\nname = "{self.name}"\nversion = "0.1.0"\n'
            f'edition = "{EDITION}"\n'
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
    #: are unverifiable in `BEVY_STYLE`: the extractor puts a bare
    #: `#![allow(dead_code, unused_imports)]` at the crate's root, and a
    #: lint about the author's attributes cannot be judged on the
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
#:     (E0277). This one has no compliant form (BV-BUILD-12).
#:
#: `type_complexity` and `too_many_arguments` also fire on ordinary Bevy
#: code and are deliberately **not** here: a `type` alias and
#: `#[derive(SystemParam)]` silence them, and both are the better code
#: (BV-ECS-19, BV-SCHED-10).
BEVY_STYLE = RustCrate(
    name="bevy-style-verify",
    library=BEVY,
    #: `missing_docs` because a block documents items selectively;
    #: `allow_attributes*` because the extractor itself puts a bare
    #: `#![allow(dead_code, unused_imports)]` at the crate's root, and a
    #: lint about the author's attributes cannot be judged on the
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
    """The `cargo` toolchain: a crate of one module per block."""

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
    #: A mutant rebuilds the crate before its tests run.
    mutant_timeout: float = 180
    outside: re.Pattern[str] | None = None

    def missing(self) -> list[str]:
        """`cargo` itself, when it is not on PATH."""
        return [f"`{tool}` is not on PATH" for tool in self.needs if not have(tool)]

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write each verified block as a module file of one crate.

        `src/<chapter>/<rule>.rs`, holding the block as written, at
        column zero, with its paths rebased (`rebase`). The block's own
        file is what rustfmt and the compiler judge, so a diff or a
        diagnostic is about the block a reader sees: inside a wrapping
        `pub mod`, rustfmt broke lines four columns early and the
        markdown had to carry the wrap.
        """
        crate = _crate(skill)
        out = out.resolve()
        src = out / "src"
        # A renamed chapter otherwise leaves a module lib.rs never
        # declares: deleting a line in a file nothing compiles can
        # never change a test result, so every statement survives.
        shutil.rmtree(src, ignore_errors=True)
        src.mkdir(parents=True)

        ex = Extraction(out, skill)
        #: each chapter's module, the document it is read from, and the
        #: module of each of its blocks
        chapters: dict[str, tuple[str, list[str]]] = {}
        for b in extracted(skill, LANGUAGE):
            stem = module_name(b.file)
            _, mods = chapters.setdefault(stem, (b.file, []))
            base = str(b.rule).lower().replace("-", "_") if b.rule else "block"
            n = sum(1 for m in mods if m == base or m.startswith(f"{base}_"))
            mod = base if n == 0 else f"{base}_{n}"
            mods.append(mod)
            path = src / stem / f"{mod}.rs"
            path.parent.mkdir(exist_ok=True)
            path.write_text(rebase(b.body, crate, stem, mod))
            ex.units.append(Unit(path, b))

        for stem, (document, mods) in chapters.items():
            head = f"//! Blocks extracted from `{skill.at(document).file}`.\n\n"
            (src / f"{stem}.rs").write_text(
                head + "".join(f"pub mod {m};\n" for m in sorted(mods))
            )
        (src / "lib.rs").write_text(
            f"//! Every `// verified` block in {skill.name}, extracted from the "
            "markdown.\n\n"
            # Once, for the crate: a block is an excerpt, so an item it
            # declares for the reader is not one it must use.
            f"{INJECTED}\n\n" + "".join(f"pub mod {s};\n" for s in sorted(chapters))
        )
        (out / "Cargo.toml").write_text(crate.manifest())
        if crate.clippy:
            (out / "clippy.toml").write_text(crate.clippy_toml())
        return ex

    def restore(self, ex: Extraction) -> dict[Block, str]:
        """Each block's module file, its paths rebased back."""
        crate = _crate(ex.skill)
        return {
            u.block: unrebase(
                u.path.read_text(), crate, u.path.parent.name, u.path.stem
            )
            for u in ex.units
        }

    def steps(self, ex: Extraction) -> Iterator[Step]:
        """Build, lint, test and document the crate."""
        yield self._cargo(ex, "compiles", "build", diagnostics=True)
        # `-D warnings` so the whole shipped table binds. Half of it is
        # `warn`, and clippy exits 0 on a warning — so without this the
        # check could only ever fail on the `deny` half.
        yield self._cargo(
            ex, "clippy", "clippy", "--all-targets", diagnostics=True, then=DENY
        )
        yield self._cargo(ex, "tests", "test")
        yield self._cargo(ex, "intra-doc links", "doc", "--no-deps", diagnostics=True)

    def formatter(self, ex: Extraction) -> Step:
        """`cargo fmt`, over every module file."""
        return self._cargo(ex, "rustfmt", "fmt")

    def tests(self, ex: Extraction, unit: Unit) -> Step:  # noqa: ARG002 — a crate's tests run whole
        """The crate's tests: every unit's are one run."""
        return self._cargo(ex, "tests", "test")

    def _cargo(
        self,
        ex: Extraction,
        name: str,
        command: str,
        *args: str,
        diagnostics: bool = False,
        then: tuple[str, ...] = (),
    ) -> Step:
        """`cargo command` over the extracted crate, in its build cache.

        A step whose tool names lines prints them one to a line
        (`--message-format=short`), as `path:line:col: message`.
        """
        manifest = str(ex.root / "Cargo.toml")
        short = ("--message-format=short",) if diagnostics else ()
        return Step(
            name,
            (
                "cargo",
                command,
                "--quiet",
                *short,
                *args,
                "--manifest-path",
                manifest,
                *then,
            ),
            ex.root,
            _STEP,
            _crate(ex.skill).env,
            diagnostics=diagnostics,
        )

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

    def probe(
        self, skill: Skill, spelling: str, out: Path, since: Version | None = None
    ) -> Step | None:
        """Compile the spelling, or search the pinned source for it.

        An attribute is no item to find, so it is compiled; so is a
        spelling whose row the edition made (`since`), since the edition
        is what rejects it (`_compiled`). Any other is searched for in
        the source of the release: the library's crates as the registry
        holds them at its pin — `bevy-0.20.1` and every `bevy_*-0.20.1`
        — or, for a standard about the language, the standard library's
        source when the toolchain ships it. A path is looked up by its
        last segment: `despawn_recursive` by a public `fn` of that name.
        A method of a type is looked up where the type is implemented:
        `App::observe` in the files holding an `impl` of `App`, so that
        `EntityCommands::observe` does not keep it. A path that opens
        with one of those crates' names is looked up in that crate
        alone, as the compiler resolves it: `bevy_math::primitives`
        moved out of `bevy_math`, and a `mod primitives` elsewhere does
        not keep it there. None for any other spelling, or when no
        source is there to search — a crate the registry does not hold
        included.
        """
        if ATTRIBUTE.fullmatch(spelling):
            return _compiled(f'{spelling}\npub extern "C" fn probe() {{}}\n', out)
        if since is not None and since.edition:
            source = _edition_source(spelling)
            return None if source is None else _compiled(source, out)
        name = spelling.removesuffix("()").removesuffix("!")
        sources = _within(name, _sources(skill))
        if not PATH.fullmatch(name) or not sources:
            return None
        *_, owner, last = ("", *name.split("::"))
        if owner[:1].isupper() and last[:1].islower():
            args = (_implements(owner), _defines(last), *map(str, sources))
            return Step("probe", ("sh", "-c", _METHOD, "probe", *args), out, 120)
        cmd = ("rg", "-n", "-m1", "--no-heading", "-t", "rust", "-e", _defines(last))
        return Step("probe", (*cmd, *map(str, sources)), out, 120)

    def excused(self, skill: Skill) -> Mapping[str, str]:  # noqa: ARG002 — no example is excused
        """Nothing: each example builds under what the skill ships."""
        return dict[str, str]()

    def configured(self, skill: Skill) -> dict[tuple[str, str], str]:
        """Each lint the shipped `[workspace.lints]` sets, at its level.

        A table value, such as clippy's `pedantic` with its priority,
        sets a group; a delta that ships no manifest applies its
        anchor's.
        """
        manifest = skill.asset(CARGO)
        if not manifest.exists():
            return {}
        tools = {section: tool for tool, section in SECTION.items()}
        found: dict[tuple[str, str], str] = {}
        for key, value in table(manifest.read_text(), "workspace.").items():
            section, _, lint = key.partition(".")
            if section in tools and not value.startswith("{"):
                found[tools[section], lint] = value.strip("\"'")
        return found


#: A name a probe can look up: a path of identifiers.
PATH = re.compile(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*")

#: A spelling a probe compiles rather than looks up: an outer attribute.
ATTRIBUTE = re.compile(r"#\[[^\[\]]+\]")

#: The edition the examples are written in, and the one before it.
EDITION = "2024"
PREVIOUS_EDITION = "2021"


#: An identifier: a name an edition can reserve, as 2024 did `gen`.
IDENT = re.compile(r"[A-Za-z_]\w*")


def _edition_source(spelling: str) -> str | None:
    """`spelling` as a crate root an edition can reject, or None.

    An item with its body left out, `extern "C" { … }`, with the body
    empty; a name, as a function's. Any other spelling — a call, a
    path — has no source the harness can write for it.
    """
    if spelling.endswith(f"{{ {ELIDED} }}"):
        return spelling.replace(ELIDED, "") + "\n"
    if IDENT.fullmatch(spelling):
        return f"pub fn {spelling}() {{}}\n"
    return None


def _compiled(source: str, out: Path) -> Step:
    """A step that exits 0 while the target edition accepts `source`.

    The crate root is compiled under the edition before the target's,
    then under the target's: 1 when only the older edition accepts it,
    which is what `gone` claims, and 2 when neither does — the probe
    itself is wrong, and the driver says so rather than reading a
    broken probe as a verified row.
    """
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"probe_{len(list(out.glob('probe_*.rs'))):03d}.rs"
    path.write_text(source)
    rustc = "rustc --crate-type lib --emit metadata --out-dir . --edition"
    script = (
        f'{rustc} {PREVIOUS_EDITION} "$1" 2>/dev/null || exit 2; '
        f'exec {rustc} {EDITION} "$1"'
    )
    return Step("probe", ("sh", "-c", script, "probe", path.name), out, 120)


def _defines(name: str) -> str:
    """A line defining `name` where a reader of the crate can reach it.

    A public item, an exported macro, or a method of a trait or impl —
    in code, not in a comment: a doc example's `/// pub struct Parent`
    defines nothing the crate exports, and read as a definition it kept
    a removed name alive. So nothing before the item may be a `/`.
    """
    item = r"(?:fn|struct|enum|trait|type|const|static|mod|union)"
    qualifiers = r"(?:(?:const|async|unsafe|extern)\s+)*"
    return (
        rf"^[^/]*\bpub(?:\([^)]*\))?\s+{qualifiers}{item}\s+{name}\b"
        rf"|^[^/]*\bmacro_rules!\s*{name}\b"
        rf"|^\s+{qualifiers}fn\s+{name}\b"
    )


def _implements(owner: str) -> str:
    """A line opening an `impl` of `owner`, its own or a trait's."""
    return rf"^[^/]*\bimpl\b[^{{;]*\b{owner}\b"


#: Searches the files that implement a type for its method: `$1` the
#: `impl` line, `$2` the method's definition, then the directories.
#: Exits as `rg` does — 1 when no file implements the type, or none
#: of them defines the method.
_METHOD = (
    'impl=$1; def=$2; shift 2; files=$(rg -l -t rust -e "$impl" -- "$@") || exit $?; '
    'exec rg -n -m1 --no-heading -e "$def" -- $files'
)


def _within(name: str, sources: list[Path]) -> list[Path]:
    """Where `name` can be defined: its crate, if it names one.

    A crate's directory is `<crate>-<version>`; a path whose first
    segment is a crate of the library (`bevy_math::curve`), but not the
    facade, which re-exports them all, resolves in that crate only, and
    in nothing when the registry does not hold it.
    """
    first = name.split("::", 1)[0]
    if "::" not in name or not first.startswith(("bevy_",)):
        return sources
    return [p for p in sources if p.name.rpartition("-")[0] == first]


def _sources(skill: Skill) -> list[Path]:
    """The source of the release `skill` is pinned to, as found here.

    A library's crates in Cargo's registry at its pin; the standard
    library's when the language itself is the subject and the toolchain
    ships its source.
    """
    library = _crate(skill).library
    if library is None:
        std = _sysroot() / "lib" / "rustlib" / "src" / "rust" / "library"
        return [std] if std.is_dir() else []
    home = Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo")
    name, version = library.pin.tool, library.pin.version
    found = (home / "registry" / "src").glob(f"*/{name}*-{version}")
    return sorted(
        p
        for p in found
        if p.name == f"{name}-{version}" or p.name.startswith(f"{name}_")
    )


@cache
def _sysroot() -> Path:
    """Where the toolchain here keeps its files; "." if it says not."""
    ran = run(["rustc", "--print", "sysroot"], timeout=60)
    return Path(ran.out.strip()) if ran.ok and ran.out.strip() else Path()


#: How long one cargo step may take: Bevy builds from cold in minutes.
_STEP = 900

#: What clippy is given after `--`: every warning a failure.
DENY = ("--", "-D", "warnings")


def _crate(skill: Skill) -> RustCrate:
    """The crate `skill`'s examples are compiled as."""
    crate = skill.profile.crate
    if crate is None:
        msg = f"{skill.name} compiles rust examples and its profile names no crate"
        raise ValueError(msg)
    return crate


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
    `unsafe`, and `pub mod unsafe;` does not parse. `SKILL.md` ->
    `skill`, since a module's name is snake case.
    """
    stem = Path(chapter).stem.replace("-", "_").lower()
    return f"{stem}_" if stem in KEYWORDS else stem


def _rebasings(crate: RustCrate, stem: str, mod: str) -> tuple[tuple[str, str], ...]:
    """Each path a block spells, and what it becomes in its module.

    `mycrate::` is the placeholder a reader replaces with their own
    crate; it points at this one, so the doctest runs. `crate::` in a
    block means the reader's own crate root, and a module file is not
    that root, so it is rebased here rather than making the published
    example spell a path it does not mean. `$crate::` names the same
    root from inside a macro, so it moves with it.
    """
    here = f"{stem}::{mod}::"
    return (("mycrate::", f"{crate.ident}::{here}"), ("crate::", f"crate::{here}"))


def rebase(body: str, crate: RustCrate, stem: str, mod: str) -> str:
    """`body` with its paths pointed into module `stem::mod`."""
    for spelled, rebased in _rebasings(crate, stem, mod):
        body = body.replace(spelled, rebased)
    return body


def unrebase(text: str, crate: RustCrate, stem: str, mod: str) -> str:
    """`rebase` undone: the block's paths as the skill spells them.

    Writing the rebased form back would store the harness's own path in
    the skill — the leak the old apparatus had, arriving by the other
    door — so `restore` inverts it, in the reverse order.
    """
    for spelled, rebased in reversed(_rebasings(crate, stem, mod)):
        text = text.replace(rebased, spelled)
    return text


#: The line the extractor puts at the top of the crate.
INJECTED = "#![allow(dead_code, unused_imports)]"


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
    in_groups = False
    for line in text.split("\n"):
        if line.startswith("Lint groups"):
            in_groups = True
        elif line.startswith("Lint checks"):
            in_groups = False
        if not in_groups:
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
    want = pinned.series
    if not running:
        yield unrun(
            "could not ask `rustc` its version, "
            f"so the Rust pin {pinned} was not compared",
            where,
            RUSTC_SILENT,
        )
    elif _series(running) != want:
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
    elif (there := _series(newest)) is not None and there > want:
        yield fail(
            f"the Rust pin is {pinned} and {newest} is stable — move "
            "`rust` in `lang/rust.py` and the assets, re-read the "
            "release notes, and re-run the suite",
            where,
            RUST_STALE,
        )


def _series(answer: str) -> Version | None:
    """The major.minor a version `rustc` or the channel gave belongs to.

    A Rust pin holds the minor, so a patch or a `-nightly` after it is
    the same series. None for an answer that names no version.
    """
    found = Version.search(answer)
    return found.series if found is not None else None


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
    here, there = Version.released(pinned), Version.released(newest)
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
