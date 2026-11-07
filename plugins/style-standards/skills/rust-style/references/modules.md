# Modules: Crates, Workspaces, and File Layout

Scope: where code goes on disk. Module boundaries and naming, the `foo.rs` + `foo/` layout,
workspace shape and facade crates, import grouping, and the order of declarations inside a file.
Visibility, the `pub use` surface and what the public surface should *be* are in the API chapter;
the manifest side of a workspace is in the build chapter.

The reference implementation is ripgrep: a workspace of narrow crates (`grep-matcher`, `grep-regex`,
`grep-searcher`, `grep-printer`, `globset`, `ignore`) with a thin facade and a binary that is mostly
wiring. Structure is what keeps a codebase comprehensible past ten thousand lines.

## Contents

- **Modules and files**
  - RS-MOD-01 [M] Give every module a documented concept
  - RS-MOD-02 [S] Prefer a few substantial modules to many tiny ones
  - RS-MOD-03 [S] Split a file on a seam, not on a line count
  - RS-MOD-04 [S] Keep crate names short, lowercase, and pronounceable
  - RS-MOD-05 [S] Keep a type, its impls, and its unit tests in one file
  - RS-MOD-06 [S] Nest public modules at most two levels deep
  - RS-MOD-07 [S] Nest private modules as deeply as is useful
  - RS-MOD-08 [M] Confine platform differences to a `sys` module
  - RS-MOD-09 [S] Isolate generated code in its own module

- **Crate and workspace layout**
  - RS-MOD-10 [M] One crate, one purpose
  - RS-MOD-11 [S] Follow the canonical workspace layout
  - RS-MOD-12 [M] Split the binary from the library
  - RS-MOD-13 [S] Give workspace members a shared prefix matching the facade
  - RS-MOD-14 [S] Keep the facade crate nearly empty
  - RS-MOD-15 [M] Keep member dependencies a shallow DAG
  - RS-MOD-16 [S] Keep `examples/` compiling in CI
  - RS-MOD-17 [M] Write a `build.rs` only for codegen or C compilation
  - RS-MOD-18 [S] Keep the repository root sparse
  - RS-MOD-19 [M] Name the resolver explicitly in a virtual manifest
  - RS-MOD-20 [M] Check each member's features alone: one invocation unifies them
  - RS-MOD-21 [M] Build every member alone in CI, not only `--workspace`
  - RS-MOD-22 [M] Count the encapsulation a split costs, not only what it buys
  - RS-MOD-23 [M] Leave `version` out of an unpublished member's manifest
  - RS-MOD-24 [S] Give the directory and the crate the same name
  - RS-MOD-25 [S] Keep `crates/` flat
  - RS-MOD-26 [M] Point every dependency edge away from the facade

- **Imports and in-file order**
  - RS-MOD-27 [S] Group imports std / external / crate
  - RS-MOD-28 [S] Merge imports from the same crate
  - RS-MOD-29 [S] Import types and traits; call functions through a short path
  - RS-MOD-30 [S] Do not import an item used once when the path is short
  - RS-MOD-31 [S] Resolve collisions by aliasing the module, not the item
  - RS-MOD-32 [S] Order a file: docs, imports, public items, private items, tests
  - RS-MOD-33 [S] Keep `impl` blocks in a predictable order
  - RS-MOD-34 [S] Order struct fields for the reader
  - RS-MOD-35 [S] Keep functions short enough to see whole

- **Orthogonality**
  - RS-MOD-36 [M] One concept, one mechanism
  - RS-MOD-37 [M] Absorb a special case into the general path, or give it its own type
  - RS-MOD-38 [S] Keep sibling modules structurally parallel

- Decided by tools

---

## Modules and files

### RS-MOD-01 [M] Give every module a documented concept

A `//!` block stating what belongs in it — its role, not a restatement of the item list — and a name
that is a singular noun.

**Why:** the module boundary is a claim about cohesion, and if you cannot write one sentence
describing what belongs inside and what does not, the boundary is in the wrong place. The sentence
also tells contributors where new code goes.

**Check:** for each module, write the sentence. If it needs "and", the module is two.

```rust
// verified
//! Compiles a pattern into a matcher. Nothing here reads files or writes output.

/// A compiled pattern.
#[derive(Debug, Clone)]
pub struct Pattern {
    literal: String,
}

impl Pattern {
    #[must_use]
    pub fn new(literal: String) -> Self {
        Self { literal }
    }
}
```

### RS-MOD-02 [S] Prefer a few substantial modules to many tiny ones

**Why:** a 400-line module with a clear theme is easier to navigate than eight 50-line modules whose
relationships you have to reconstruct from the import graph. Module count is a cost paid on every
read.

**Check:** how many modules are under 100 lines? Could any two merge under one honest name?

```rust
// verified
// A few substantial modules, each with a stated concept.
pub mod scanning {
    //! Walks inputs and yields candidate lines. Knows nothing about output.

    #[must_use]
    pub fn candidates(lines: &[String]) -> Vec<&str> {
        lines
            .iter()
            .map(String::as_str)
            .filter(|line| !line.is_empty())
            .collect()
    }
}

pub mod reporting {
    //! Renders results for a human. Knows nothing about how they were found.

    #[must_use]
    pub fn render(items: &[&str]) -> String {
        items.join("\n")
    }
}
```

### RS-MOD-03 [S] Split a file on a seam, not on a line count

Roughly 600–1000 lines *and* an obvious internal boundary.

**Why:** splitting on size alone produces modules named after nothing — `parser2.rs`,
`config_more.rs` — which is worse than the long file, because now the reader has to hold two files
and the relationship between them.

**Check:** when splitting, can you name both halves with a noun? If not, do not split yet.

### RS-MOD-04 [S] Keep crate names short, lowercase, and pronounceable

Two words is the ceiling for a leaf crate; three for a facade (`regex-automata`, `grep-searcher`).

**Why:** the name appears in every dependent's manifest, in every `use`, and in conversation. If it
needs four words to describe the crate, the crate does too much — the name is reporting a design
problem (RS-MOD-10).

**Check:** say the name out loud. If you have to spell it, or if it does not fit in the `Cargo.toml`
line without wrapping, shorten it or split the crate.

### RS-MOD-05 [S] Keep a type, its impls, and its unit tests in one file

**Why:** scattering `impl Display for Foo` three files away from `Foo` makes every change a
scavenger hunt and makes it easy to update one and forget the other. Rust does not require the
split, so the only reason to do it is file size (RS-MOD-03).

**Check:** for each type, is any `impl` block in a different file? If so, why?

```rust
// verified
/// The type and its `impl` live together; nothing about it is spread across files.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Position {
    line: u32,
    column: u32,
}

impl Position {
    #[must_use]
    pub fn advance(self, ch: char) -> Self {
        if ch == '\n' {
            Self {
                line: self.line + 1,
                column: 0,
            }
        } else {
            Self {
                column: self.column + 1,
                ..self
            }
        }
    }
}
```

### RS-MOD-06 [S] Nest public modules at most two levels deep

**Why:** `crate::search::matcher::regex::inner::Config` is a path nobody will type, and every
segment of it is API you cannot reorganize. Flatten with re-exports at the root (RS-API-04).

**Check:** read the crate's own doc examples. How many `::` segments does the longest path have?

### RS-MOD-07 [S] Nest private modules as deeply as is useful

**Why:** internal organization is free — it does not appear in any user's code and can be
reorganized at any time. The two-level limit is about the *public* surface, not about how you
arrange your own files.

**Check:** are you flattening internals for consistency with the public rule? Do not.

### RS-MOD-08 [M] Confine platform differences to a `sys` module

`sys/unix.rs`, `sys/windows.rs`, selected by `#[cfg]` in one place behind a shared interface. Where
one item needs an arm per platform, write `cfg_select!` rather than depending on `cfg-if`.

**Why:** `#[cfg(unix)]` scattered through business logic means no single file can be read without
mentally running the preprocessor, and the Windows path silently rots because nobody reads it. One
boundary means one place to keep in sync.

**Check:** `rg -c 'cfg\(unix|cfg\(windows|cfg\(target_os' src/`. Anything outside `sys/` needs a
reason.

### RS-MOD-09 [S] Isolate generated code in its own module

`include!`d from a dedicated module, never hand-edited, with a comment saying so at the top.

**Why:** a generated file that someone has edited by hand is a landmine — the next regeneration
silently discards the fix. The comment and the isolation are what prevent it.

**Check:** does every generated file's module say what generates it and how to regenerate?

## Crate and workspace layout

### RS-MOD-10 [M] One crate, one purpose

Split into a workspace when a piece is independently useful, has a different dependency footprint,
or must be versioned separately.

**Why:** a crate split for tidiness adds compilation units and version coordination for nothing; a
crate that should have been split forces every consumer to take dependencies they do not use.
ripgrep's `grep-matcher`, `grep-regex`, `grep-searcher` and `grep-printer` are each usable alone.

**Check:** describe the crate in one sentence. A conjunction is a candidate split; which of the
three criteria applies to it?

### RS-MOD-11 [S] Follow the canonical workspace layout

**Why:** it is what the ecosystem expects, so contributors know where to look before reading
anything. Deviating has a cost paid by every newcomer.

**Check:** can someone find the binary's entry point and the primary library in under ten seconds?

```text
# fragment — the top level of the workspace
project/
├── Cargo.toml            # [workspace] with shared deps and lints
├── crates/
│   ├── core/             # the binary's own logic (ripgrep calls this `core`)
│   ├── foo-matcher/      # narrow libraries
│   └── foo/              # thin facade re-exporting the pieces
├── tests/
├── benches/
└── examples/
```

### RS-MOD-12 [M] Split the binary from the library

`src/lib.rs` holds everything testable; `src/main.rs` is argument parsing, wiring, and reporting.
That split is why ripgrep's search engine is `grep-searcher`, a crate others build on, rather than a
module in `main.rs`.

**Why:** a binary-only crate cannot be integration-tested, benchmarked, or reused, and its logic can
only be exercised by running the process. The split costs one file.

**Check:** how many lines are in `main.rs`? More than a few dozen means logic is trapped there.

```rust
// verified
/// The library holds the logic; a binary would only wire this up.
#[derive(Debug, Clone, Copy, Default)]
pub struct Stats {
    matched: u64,
    scanned: u64,
}

impl Stats {
    #[must_use]
    pub fn matched(self) -> u64 {
        self.matched
    }

    #[must_use]
    pub fn scanned(self) -> u64 {
        self.scanned
    }
}

#[must_use]
pub fn scan(lines: &[String], needle: &str) -> Stats {
    let matched = lines.iter().filter(|line| line.contains(needle)).count();
    Stats {
        matched: matched as u64,
        scanned: lines.len() as u64,
    }
}
```

### RS-MOD-13 [S] Give workspace members a shared prefix matching the facade

`grep-matcher`, `grep-regex`, `grep-searcher`, facade `grep`.

**Why:** the `Cargo.toml` then reads as a table of contents, and a user who knows one crate can
guess the others. Unrelated names in one workspace force everyone to learn the mapping.

**Check:** does the member list sort into a readable group?

### RS-MOD-14 [S] Keep the facade crate nearly empty

`pub use` of the pieces, crate-level documentation, and the feature flags that turn optional members
on and off.

**Why:** logic in the facade cannot be used by someone who depends on one piece directly, and it
makes the facade a fourth thing to version. Its job is curation.

**Check:** how many lines of non-`pub use` code are in the facade?

### RS-MOD-15 [M] Keep member dependencies a shallow DAG

**Why:** if two members depend on each other's internals, they are one crate wearing two names — and
Cargo will not let you make it a cycle, so the workaround is always worse than merging. Depth also
serializes the build.

**Check:** draw the member graph. Any pair that would like to be mutual is a merge.

### RS-MOD-16 [S] Keep `examples/` compiling in CI

**Why:** an example that no longer builds is worse than no example, because users copy it before
discovering that. `cargo test` does not necessarily build them — `cargo build --examples` does.

**Check:** is `cargo build --examples` in CI (RS-BUILD-38)?

### RS-MOD-17 [M] Write a `build.rs` only for codegen or C compilation

**Why:** it slows every build, runs arbitrary code on every user's machine, breaks cross-compilation
in subtle ways, and is harder to audit than ordinary source. It is right for genuine codegen and C
compilation and wrong for convenience.

**Check:** what does the build script do that a committed generated file or a `const fn` could not?

### RS-MOD-18 [S] Keep the repository root sparse

`README.md`, `LICENSE-APACHE`, `LICENSE-MIT`, `CHANGELOG.md`, `Cargo.toml`, `rust-toolchain.toml`,
`.github/`, and the directories above.

**Why:** the root is the first thing anyone sees, and every extra file there is a small tax on
orientation. Everything else has a home inside one of those directories.

**Check:** `ls` the root. Can you justify each entry in one clause?

### RS-MOD-19 [M] Name the resolver explicitly in a virtual manifest

A root with no `[package]` has no edition to infer the resolver from, so Cargo falls back to
`resolver = "1"`, the pre-2021 algorithm, however new the members are. It says so only in a warning:
`virtual workspace defaulting to resolver = "1" despite one or more workspace members being on edition 2024`.

**Why:** the versions are not interchangeable: `"2"` stops features unifying across build-, dev-,
and inactive target-specific dependencies, and `"3"` passes over a dependency release that raises
its `rust-version` past yours rather than picking it (RS-BUILD-30).

**Check:** does the workspace root name a resolver? A build that prints that warning is not
configured, it is defaulted.

### RS-MOD-20 [M] Check each member's features alone: one invocation unifies them

Two members built together each see the union of their features on every shared dependency.
Per-package unification (`resolver.feature-unification`) is nightly-only, so the working remedies
are separate invocations or `cargo hack`.

**Why:** the member that asked for less is built with the larger dependency anyway, so adding a
feature in one member silently changes another member's binary.

**Check:** for a dependency two members configure differently, compare `cargo tree -e features`
alone against `--workspace`. Any difference is a member being built in a way nobody declared.

### RS-MOD-21 [M] Build every member alone in CI, not only `--workspace`

**Why:** unification hides a missing feature declaration: a member that forgot `serde/derive` still
compiles when a sibling asks for it, so `--workspace` is green while the published crate fails for
the first user who depends on it alone (RS-BUILD-38).

**Check:** does CI build members individually — `cargo hack --each-feature`, or one `-p` per member
— or only `--workspace`?

### RS-MOD-22 [M] Count the encapsulation a split costs, not only what it buys

Everything the new crate's siblings reach for must become `pub`. A seam that turns a handful of
items public is a seam; a seam that turns dozens public is the wrong seam, whatever RS-MOD-10's
three criteria say about it.

**Why:** a crate boundary is the one boundary `pub(crate)` cannot cross, so a split converts
internal items into public API — visible to every consumer, and bound by semver from then on.

**Check:** list the items the split forces from `pub(crate)` to `pub`. Would you have made each one
public on its own merits?

### RS-MOD-23 [M] Leave `version` out of an unpublished member's manifest

Cargo reads a missing `version` as `0.0.0` and `publish = false`, so the one absence says both.
Members that *are* published carry real versions and the full metadata (RS-BUILD-03).

**Why:** `publish = false` is what stops `cargo publish` from shipping an internal crate by
accident, and no version states that the number carries no promise — an internal member versioned
`0.3.1` invites readers to reason about compatibility that nobody maintains.

**Check:** for each member, is it published? If not, does its manifest omit `version`? A `version`
line on an internal member is the finding.

### RS-MOD-24 [S] Give the directory and the crate the same name

**Why:** the manifest's `path`, the directory listing, and the dependency name then agree, so one
grep finds every mention and a rename is one operation. When they differ, every reader maintains the
mapping by hand.

**Check:** does `ls crates/` read as the member list in the root manifest?

### RS-MOD-25 [S] Keep `crates/` flat

**Why:** Cargo's crate namespace has no hierarchy — a dependency is named `foo-matcher`, never
`foo::matcher` — so directory nesting encodes a structure the build system cannot represent, and it
decays into arguments about where a new crate belongs. Flat keeps `ls crates/` the whole picture.

**Check:** is there a directory under `crates/` that holds directories rather than a crate?

### RS-MOD-26 [M] Point every dependency edge away from the facade

Members do not depend on the crate that re-exports them. `dev-dependencies` are the documented
exception: a cycle through them compiles, and it is the supported way for a member's tests to drive
the assembled facade.

**Why:** Cargo rejects the cycle outright — `error: cyclic package dependency` — so the edge cannot
exist, and reaching for the facade from inside a member is a sign the shared item belongs in a lower
member instead (RS-MOD-14, RS-MOD-15).

**Check:** does a member manifest name the facade outside `[dev-dependencies]`? Each is a layering
error.

## Imports and in-file order

### RS-MOD-27 [S] Group imports std / external / crate

Three blocks separated by blank lines — what `group_imports = "StdExternalCrate"` produces.

**Why:** the grouping tells a reader at a glance how much of the file's vocabulary is foreign, and
where a name came from. Setting it in `rustfmt.toml` makes it enforced rather than remembered
(RS-BUILD-26).

**Check:** is the option set, and does CI run `cargo fmt --check`?

```rust
// verified
//! Imports are grouped std / external / crate and each group is sorted.
use std::{collections::BTreeMap, path::PathBuf};

#[derive(Debug, Default)]
pub struct Manifest {
    paths: BTreeMap<String, PathBuf>,
}
```

### RS-MOD-28 [S] Merge imports from the same crate

`use std::{fs, io::{self, Read, Write}, path::Path};` — `imports_granularity = "Crate"`.

**Why:** fewer lines and exactly one place to look per crate, instead of a screen of `use std::`
lines to scan.

**Check:** the rustfmt option handles it; the check is that the option is set.

### RS-MOD-29 [S] Import types and traits; call functions through a short path

`use std::fs; fs::read_to_string(p)`.

**Why:** the module name is context — `fs::read_to_string` says where the effect happens, while a
bare `read_to_string` could be anything. Types and traits are different: they appear in signatures,
where the path would be noise.

**Check:** is a free function imported by name? Would the call site read better with one segment of
path?

### RS-MOD-30 [S] Do not import an item used once when the path is short

`std::process::exit(2)` at one call site beats an import at the top.

**Why:** the import is a line at the top of the file that the reader must connect to a single use
two hundred lines down. The inline path is self-contained.

**Check:** for each import, how many uses does it have? One plus a short path means inline it.

### RS-MOD-31 [S] Resolve collisions by aliasing the module, not the item

`use std::fmt;` then `fmt::Result`, rather than `use std::fmt::Result as FmtResult;`.

**Why:** the aliased item creates a second name for one thing, which every reader must learn. The
module-qualified form uses names that already exist and reads the same as the documentation.

**Check:** is each `as` in an import a module alias? Otherwise the qualified form would have worked.

### RS-MOD-32 [S] Order a file: docs, imports, public items, private items, tests

**Why:** readers scan top-down looking for the public surface, and the compiler does not care.
Private helpers first make a reader and a reviewer read the implementation before the interface.
Tests go last (RS-TEST-04).

**Check:** in each file, is the first non-import item public?

### RS-MOD-33 [S] Keep `impl` blocks in a predictable order

Inherent constructors, inherent methods, then trait impls grouped by trait, std traits before your
own.

**Why:** a type with nine `impl` blocks in arbitrary order forces a search for every question.
Multiple inherent `impl` blocks for one type need a reason — a `cfg`, or different bounds.

**Check:** does the type have more than one inherent `impl` block, and why?

### RS-MOD-34 [S] Order struct fields for the reader

Identifying field first, configuration next, caches and scratch last.

**Why:** the compiler reorders for layout anyway unless `repr(C)` is set, so field order is purely a
communication decision — use it to tell the reader what the type is about (RS-UNSAFE-14).

**Check:** does the first field identify the value, or is it whatever was added first?

### RS-MOD-35 [S] Keep functions short enough to see whole

When one is not, the fix is almost always extracting a pure helper and leaving a thin caller
(RS-FUNC-35).

**Why:** there is no line limit worth enforcing, but four levels of indentation or eight local
mutable bindings means the reader is simulating the function rather than reading it.

**Check:** what is the maximum indentation depth in the function, and how many `let mut` are live at
once?

## Orthogonality

### RS-MOD-36 [M] One concept, one mechanism

A crate configures itself one way, reports progress one way, and spawns work one way. Two mechanisms
for one concept means every future feature must choose, and every reader must learn both.

**Why:** mechanisms multiply combinations. Two config paths and two logging paths is four states a
maintainer must hold, and the second mechanism is almost always introduced because the first was
inconvenient once — a local fix with a global cost.

**Check:** name the mechanism for each cross-cutting concern: configuration, errors, logging,
concurrency, I/O. More than one per concern needs a migration plan, not an exception.

```rust
// verified
/// One mechanism for configuration: every knob arrives through this one type.
#[derive(Debug, Clone, Default)]
pub struct Config {
    threads: Option<usize>,
    colour: bool,
}

impl Config {
    #[must_use]
    pub fn thread_count(&self) -> usize {
        self.threads.unwrap_or(1)
    }

    #[must_use]
    pub fn wants_colour(&self) -> bool {
        self.colour
    }
}
```

### RS-MOD-37 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is not a feature; it is an unfinished generalization. Either the
general path handles it — usually by widening a parameter or adding a variant — or the case is
different enough to deserve its own type and its own function.

**Why:** special-case branches compound. Each is locally cheap and globally expensive, because every
later change must be tested against every branch, and nothing marks which combinations are
reachable.

**Check:** for each `if` whose condition names a specific input — a particular filename, an empty
collection treated unlike others, a magic value — ask what the general case would have to be for the
branch to disappear. That is usually the correct design.

```rust
// verified
/// The general path absorbs the empty case instead of branching on it.
#[must_use]
pub fn join(parts: &[String], separator: &str) -> String {
    parts.join(separator)
}
```

### RS-MOD-38 [S] Keep sibling modules structurally parallel

Modules at the same level of the tree have the same internal shape: if `parser` has `mod error` and
a `Config`, then `renderer` does too, or the difference is explained.

**Why:** parallel structure is what lets a reader who has learned one module navigate the next
without reading it. The cost of the convention is near zero; the cost of its absence is paid on
every visit by every contributor.

**Check:** list the item kinds in each sibling module side by side. A column present in three of
four siblings is either missing from the fourth or should be removed from the others.

```rust
// verified
/// Sibling modules share a shape: each owns an `Error` and a single entry point.
pub mod parser {
    /// The input was not valid.
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub struct Error;

    /// # Errors
    /// Returns [`Error`] when `input` is empty.
    pub fn run(input: &str) -> Result<usize, Error> {
        if input.is_empty() {
            Err(Error)
        } else {
            Ok(input.len())
        }
    }
}

pub mod renderer {
    /// The value could not be rendered.
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub struct Error;

    /// # Errors
    /// Returns [`Error`] when `width` is zero.
    pub fn run(width: usize) -> Result<String, Error> {
        if width == 0 {
            Err(Error)
        } else {
            Ok(" ".repeat(width))
        }
    }
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `mod_module_files` | warn | `foo/mod.rs` — `foo.rs` beside `foo/` |
| rustc | `unreachable_pub` | warn | a `pub` item the crate root does not re-export |
| rustc | `unused_qualifications` | warn | a path qualified further than its imports need |
| clippy | `wildcard_imports` | warn | a glob import outside a test module and a prelude — listed because an explicit import list is what RS-MOD-29's short paths read from, the rule a revision demoted to it |
