# Modules, Crates, Workspaces, File Layout

Scope: where code goes on disk and how visibility is escalated. Module boundaries and naming, the
`foo.rs` + `foo/` layout, `pub`/`pub(crate)`/`pub use` discipline, workspace shape and facade
crates, import grouping, and the order of declarations inside a file. What the public surface should
*be* is in the API chapter; the manifest side of a workspace is in the Cargo chapter.

The reference implementation is ripgrep: a workspace of narrow crates (`grep-matcher`, `grep-regex`,
`grep-searcher`, `grep-printer`, `globset`, `ignore`) with a thin facade and a binary that is mostly
wiring. Structure is what keeps a codebase comprehensible past ten thousand lines.

## Contents

- **Modules and files**
  - RS-MOD-01 [M] Give every module a documented concept
  - RS-MOD-02 [M] Never create `utils`, `helpers`, `common`, or `misc`
  - RS-MOD-03 [S] Prefer a few substantial modules to many tiny ones
  - RS-MOD-04 [S] Split a file on a seam, not on a line count
  - RS-MOD-05 [S] Keep a type, its impls, and its unit tests in one file
  - RS-MOD-06 [S] Nest public modules at most two levels deep
  - RS-MOD-07 [S] Nest private modules as deeply as is useful
  - RS-MOD-08 [M] Confine platform differences to a `sys` module
  - RS-MOD-09 [S] Isolate generated code in its own module

- **Visibility**
  - RS-MOD-10 [M] Cross a parent-child edge with `pub(super)`, not `pub(crate)`
  - RS-MOD-11 [M] Reserve `pub(crate)` for a genuine non-parent-child edge
  - RS-MOD-12 [M] Assemble the public surface in the crate root and nowhere else
  - RS-MOD-13 [M] Never make an item `pub` to satisfy a test
  - RS-MOD-14 [S] Re-export with `pub use`; use `pub mod` only for real API paths
  - RS-MOD-15 [M] Do not glob re-export from a library root
  - RS-MOD-16 [S] Provide a `prelude` only for trait-heavy ecosystem crates
  - RS-MOD-17 [M] Namespace `#[doc(hidden)] pub` macro support items
  - RS-MOD-18 [M] Remember that enum variants inherit the enum's visibility

- **Crate and workspace layout**
  - RS-MOD-19 [M] One crate, one purpose
  - RS-MOD-20 [S] Follow the canonical workspace layout
  - RS-MOD-21 [M] Split the binary from the library
  - RS-MOD-22 [S] Give workspace members a shared prefix matching the facade
  - RS-MOD-23 [S] Keep the facade crate nearly empty
  - RS-MOD-24 [M] Keep member dependencies a shallow DAG
  - RS-MOD-25 [S] Keep `examples/` compiling in CI
  - RS-MOD-26 [M] Treat `build.rs` as a last resort
  - RS-MOD-27 [S] Keep the repository root sparse
  - RS-MOD-28 [M] Name the resolver explicitly in a virtual manifest
  - RS-MOD-29 [M] Expect features to unify across everything built in one invocation
  - RS-MOD-30 [M] Build every member alone in CI, not only `--workspace`
  - RS-MOD-31 [M] Count the encapsulation a split costs, not only what it buys
  - RS-MOD-32 [M] Leave `version` out of an unpublished member's manifest
  - RS-MOD-33 [S] Give the directory and the crate the same name
  - RS-MOD-34 [S] Keep `crates/` flat
  - RS-MOD-35 [M] Point every dependency edge away from the facade

- **Imports and in-file order**
  - RS-MOD-36 [S] Group imports std / external / crate
  - RS-MOD-37 [S] Merge imports from the same crate
  - RS-MOD-38 [S] Import types and traits; call functions through a short path
  - RS-MOD-39 [S] Do not import an item used once when the path is short
  - RS-MOD-40 [S] Resolve collisions by aliasing the module, not the item
  - RS-MOD-41 [S] Order a file: docs, imports, public items, private items, tests
  - RS-MOD-42 [S] Keep `impl` blocks in a predictable order
  - RS-MOD-43 [S] Order struct fields for the reader
  - RS-MOD-44 [S] Keep functions short enough to see whole

- **Orthogonality**
  - RS-MOD-45 [M] One concept, one mechanism
  - RS-MOD-46 [M] Absorb a special case into the general path, or give it its own type
  - RS-MOD-47 [S] Keep sibling modules structurally parallel

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

### RS-MOD-02 [M] Never create `utils`, `helpers`, `common`, or `misc`

Also `shared`, `types`, `lib`, and `core` as a grab-bag.

**Why:** these are not names — they are admissions that the boundary has not been found, so nobody
can predict which function landed in one. They also grow monotonically, because nothing is ever
obviously *not* a utility (RS-NAME-05).

**Check:** grep the module tree for these names. For each function inside, name the type or concept
it actually serves.

```rust
// verified
// Named for the concept it serves, never `utils`.
pub mod escaping {
    //! Escapes text for terminal output.

    #[must_use]
    pub fn escape(input: &str) -> String {
        input.replace('\x1b', "^[")
    }
}
```

### RS-MOD-03 [S] Prefer a few substantial modules to many tiny ones

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

### RS-MOD-04 [S] Split a file on a seam, not on a line count

Roughly 600–1000 lines *and* an obvious internal boundary.

**Why:** splitting on size alone produces modules named after nothing — `parser2.rs`,
`config_more.rs` — which is worse than the long file, because now the reader has to hold two files
and the relationship between them.

**Check:** when splitting, can you name both halves with a noun? If not, do not split yet.

### RS-MOD-05 [S] Keep a type, its impls, and its unit tests in one file

**Why:** scattering `impl Display for Foo` three files away from `Foo` makes every change a
scavenger hunt and makes it easy to update one and forget the other. Rust does not require the
split, so the only reason to do it is file size (RS-MOD-04).

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
segment of it is API you cannot reorganize. Flatten with re-exports at the root (RS-MOD-12).

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

## Visibility

### RS-MOD-10 [M] Cross a parent-child edge with `pub(super)`, not `pub(crate)`

Visibility escalates one step at a time: private, `pub(super)`, `pub(crate)`, `pub` (RS-API-01). An
item a child module shares with its parent, or a parent shares with one child, is `pub(super)`. The
two spellings coincide for a module directly under the crate root, where `super` *is* the root; the
distinction starts one level further down, and so does this rule.

**Why:** `pub(crate)` on a parent-child edge says any module may depend on the item, which is almost
never what the code means. A reader who sees `pub(super)` knows the coupling stops one level up, and
a reviewer who sees it spreading knows the seam is wrong before the coupling is load-bearing.

**Check:** for each `pub(crate)` item, list the modules that name it. If they all sit under one
parent, it is a `pub(super)`.

```rust
// verified
/// `parse` reaches `syntax` and stops: `pub(crate)` here would offer it to the whole crate.
mod syntax {
    mod lexer {
        pub(super) fn parse(input: &str) -> usize {
            input.split_whitespace().count()
        }
    }

    pub(super) fn token_count(input: &str) -> usize {
        lexer::parse(input)
    }
}
```

### RS-MOD-11 [M] Reserve `pub(crate)` for a genuine non-parent-child edge

Two modules with no ancestor relationship, or an item three or more levels away.

**Why:** at that distance `pub(super)` cannot express the edge, so `pub(crate)` is the honest
spelling rather than a shortcut. Keeping it to that case means a `pub(crate)` in a diff is a claim
worth reading — this item is crate infrastructure — instead of the default everything drifts to.

**Check:** does the item have at least two consumers that share no parent below the crate root? If
not, narrow it.

```rust
// verified
/// The consumers live under `front` and `back`, so `pub(super)` on `Interner` would reach neither.
mod util {
    pub(crate) mod intern {
        #[derive(Debug, Default)]
        pub(crate) struct Interner {
            names: Vec<String>,
        }

        impl Interner {
            pub(crate) fn intern(&mut self, name: &str) -> usize {
                self.names.push(name.to_owned());
                self.names.len() - 1
            }
        }
    }
}

mod front {
    mod render {
        use crate::util::intern::Interner;

        pub(super) fn label(interner: &mut Interner, name: &str) -> usize {
            interner.intern(name)
        }
    }
}

mod back {
    mod store {
        use crate::util::intern::Interner;

        pub(super) fn key(interner: &mut Interner, name: &str) -> usize {
            interner.intern(name)
        }
    }
}
```

### RS-MOD-12 [M] Assemble the public surface in the crate root and nowhere else

`lib.rs` holds the `pub use` statements that decide the API; no other file makes that decision. The
single exception is `prelude.rs`, which may only re-export names `lib.rs` has already made public
(RS-MOD-16) — and `pub mod prelude;` still appears in `lib.rs`.

**Why:** the surface is then one file long and reviewable as a unit, and an addition is a visible
edit to the file that owns it. Users write `grep::Searcher`, not the path to the file, so the file
can move without a breaking change.

**Check:** `rg -n 'pub use' -g '*.rs' src/ | rg -v '^src/(lib|prelude)\.rs'`. Each surviving hit
must be a module assembling its own internals, never widening the crate's surface.

```rust
// verified
/// Every name on the surface is decided here, in one readable block.
mod pattern {
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
}

mod report {
    #[derive(Debug, Clone, Copy, Default)]
    pub struct Summary {
        matched: u64,
    }

    impl Summary {
        #[must_use]
        pub fn matched(self) -> u64 {
            self.matched
        }
    }
}

pub use pattern::Pattern;
pub use report::Summary;
```

### RS-MOD-13 [M] Never make an item `pub` to satisfy a test

**Why:** tests inside the crate can see private items already, so a test that cannot is an
integration test testing the wrong layer. Widening the API for a test makes the test's needs
permanent public contract.

**Check:** grep for `pub` items with a comment mentioning tests, or `pub(crate)` items used only
from `#[cfg(test)]`.

```rust
// verified
/// Private by default; the public surface is declared deliberately and stays small.
#[derive(Debug, Default)]
pub struct Index {
    entries: Vec<Entry>,
}

#[derive(Debug)]
struct Entry {
    offset: usize,
}

impl Index {
    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}
```

### RS-MOD-14 [S] Re-export with `pub use`; use `pub mod` only for real API paths

**Why:** `pub mod` makes the module path part of the API, which is right for `error`, `prelude`, or
a submodule holding many related types — and wrong for a module that exists because the file was
getting long.

**Check:** for each `pub mod`, would you be willing to keep that path working for a major version?

```rust
// verified
/// Re-export so the caller writes one path, not the internal one.
mod inner {
    #[derive(Debug, Clone, Default)]
    pub struct Counter {
        hits: u64,
    }

    impl Counter {
        pub fn record(&mut self) {
            self.hits += 1;
        }

        #[must_use]
        pub fn hits(&self) -> u64 {
            self.hits
        }
    }
}

pub use inner::Counter;
```

### RS-MOD-15 [M] Do not glob re-export from a library root

`pub use inner::*;`

**Why:** it makes the public surface implicit, so adding an internal item can accidentally publish
it — a semver commitment made by a typo. It also makes `cargo public-api` diffs unreadable.
Enumerate the re-exports.

**Check:** grep `pub use .*::\*`.

```rust
// verified
/// The facade re-exports the surface; the internal split stays private.
mod matcher {
    #[derive(Debug, Clone, Copy)]
    pub struct Matcher;
}

mod printer {
    #[derive(Debug, Clone, Copy)]
    pub struct Printer;
}

pub use matcher::Matcher;
pub use printer::Printer;
```

### RS-MOD-16 [S] Provide a `prelude` only for trait-heavy ecosystem crates

**Why:** a prelude is worth it when using the crate genuinely requires five traits in scope, as with
`rayon` or `diesel`. For a crate with three public types it is ceremony that adds an import users
must learn about.

**Check:** how many traits must be in scope for the primary use case? Fewer than three means no
prelude.

### RS-MOD-17 [M] Namespace `#[doc(hidden)] pub` macro support items

`__private`, `__internal`.

**Why:** they are public for semver purposes even though rustdoc hides them, so a user *can* depend
on them and their removal *is* breaking. The namespace is what signals "not for you" and keeps them
out of autocomplete's way.

**Check:** grep `#[doc(hidden)]` on `pub` items. Are they under a namespaced module?

### RS-MOD-18 [M] Remember that enum variants inherit the enum's visibility

**Why:** you cannot make one variant private. If some variants are internal, that is two types — a
public one and a private one — not one enum with a convention. People discover this late, after the
enum is public.

**Check:** does any public enum have a variant documented as "internal, do not match"? That is a
design error, not a documentation problem.

## Crate and workspace layout

### RS-MOD-19 [M] One crate, one purpose

Split into a workspace when a piece is independently useful, has a different dependency footprint,
or must be versioned separately.

**Why:** a crate split for tidiness adds compilation units and version coordination for nothing; a
crate that should have been split forces every consumer to take dependencies they do not use.
ripgrep's `grep-matcher`, `grep-regex`, `grep-searcher` and `grep-printer` are each usable alone.

**Check:** describe the crate in one sentence. A conjunction is a candidate split; which of the
three criteria applies to it?

### RS-MOD-20 [S] Follow the canonical workspace layout

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

### RS-MOD-21 [M] Split the binary from the library

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

### RS-MOD-22 [S] Give workspace members a shared prefix matching the facade

`grep-matcher`, `grep-regex`, `grep-searcher`, facade `grep`.

**Why:** the `Cargo.toml` then reads as a table of contents, and a user who knows one crate can
guess the others. Unrelated names in one workspace force everyone to learn the mapping.

**Check:** does the member list sort into a readable group?

### RS-MOD-23 [S] Keep the facade crate nearly empty

`pub use` of the pieces, crate-level documentation, and the feature flags that turn optional members
on and off.

**Why:** logic in the facade cannot be used by someone who depends on one piece directly, and it
makes the facade a fourth thing to version. Its job is curation.

**Check:** how many lines of non-`pub use` code are in the facade?

### RS-MOD-24 [M] Keep member dependencies a shallow DAG

**Why:** if two members depend on each other's internals, they are one crate wearing two names — and
Cargo will not let you make it a cycle, so the workaround is always worse than merging. Depth also
serializes the build.

**Check:** draw the member graph. Any pair that would like to be mutual is a merge.

### RS-MOD-25 [S] Keep `examples/` compiling in CI

**Why:** an example that no longer builds is worse than no example, because users copy it before
discovering that. `cargo test` does not necessarily build them — `cargo build --examples` does.

**Check:** is `cargo build --examples` in CI (RS-BUILD-39)?

### RS-MOD-26 [M] Treat `build.rs` as a last resort

**Why:** it slows every build, runs arbitrary code on every user's machine, breaks cross-compilation
in subtle ways, and is harder to audit than ordinary source. It is right for genuine codegen and C
compilation and wrong for convenience.

**Check:** what does the build script do that a committed generated file or a `const fn` could not?

### RS-MOD-27 [S] Keep the repository root sparse

`README.md`, `LICENSE-APACHE`, `LICENSE-MIT`, `CHANGELOG.md`, `Cargo.toml`, `rust-toolchain.toml`,
`.github/`, and the directories above.

**Why:** the root is the first thing anyone sees, and every extra file there is a small tax on
orientation. Everything else has a home inside one of those directories.

**Check:** `ls` the root. Can you justify each entry in one clause?

### RS-MOD-28 [M] Name the resolver explicitly in a virtual manifest

A root with no `[package]` has no edition to infer the resolver from, so Cargo falls back to
`resolver = "1"`, the pre-2021 algorithm, however new the members are. It says so only in a warning:
`virtual workspace defaulting to resolver = "1" despite one or more workspace members being on edition 2024`.

**Why:** the versions are not interchangeable: `"2"` stops features unifying across build-, dev-,
and inactive target-specific dependencies, and `"3"` passes over a dependency release that raises
its `rust-version` past yours rather than picking it (RS-BUILD-31).

**Check:** does the workspace root name a resolver? A build that prints that warning is not
configured, it is defaulted.

### RS-MOD-29 [M] Expect features to unify across everything built in one invocation

Two members built together each see the union of their features on every shared dependency.
Per-package unification (`resolver.feature-unification`) is nightly-only, so the working remedies
are separate invocations or `cargo hack`.

**Why:** the member that asked for less is compiled against the larger dependency anyway, so adding
a feature in one member silently changes another member's binary.

**Check:** for a dependency two members configure differently, compare `cargo tree -e features`
alone against `--workspace`. Any difference is a member being built in a way nobody declared.

### RS-MOD-30 [M] Build every member alone in CI, not only `--workspace`

**Why:** unification hides a missing feature declaration: a member that forgot `serde/derive` still
compiles when a sibling asks for it, so `--workspace` is green while the published crate fails for
the first user who depends on it alone (RS-BUILD-39).

**Check:** does CI build members individually — `cargo hack --each-feature`, or one `-p` per member
— or only `--workspace`?

### RS-MOD-31 [M] Count the encapsulation a split costs, not only what it buys

Everything the new crate's siblings reach for must become `pub`. A seam that turns a handful of
items public is a seam; a seam that turns dozens public is the wrong seam, whatever RS-MOD-19's
three criteria say about it.

**Why:** a crate boundary is the one boundary `pub(crate)` cannot cross, so a split converts
internal items into public API — visible to every consumer, and bound by semver from then on.

**Check:** list the items the split forces from `pub(crate)` to `pub`. Would you have made each one
public on its own merits?

### RS-MOD-32 [M] Leave `version` out of an unpublished member's manifest

Cargo reads a missing `version` as `0.0.0` and `publish = false`, so the one absence says both.
Members that *are* published carry real versions and the full metadata (RS-BUILD-03).

**Why:** `publish = false` is what stops `cargo publish` from shipping an internal crate by
accident, and no version states that the number carries no promise — an internal member versioned
`0.3.1` invites readers to reason about compatibility that nobody maintains.

**Check:** for each member, is it published? If not, does its manifest omit `version`? A `version`
line on an internal member is the finding.

### RS-MOD-33 [S] Give the directory and the crate the same name

**Why:** the manifest's `path`, the directory listing, and the dependency name then agree, so one
grep finds every mention and a rename is one operation. When they differ, every reader maintains the
mapping by hand.

**Check:** does `ls crates/` read as the member list in the root manifest?

### RS-MOD-34 [S] Keep `crates/` flat

**Why:** Cargo's crate namespace has no hierarchy — a dependency is named `foo-matcher`, never
`foo::matcher` — so directory nesting encodes a structure the build system cannot represent, and it
decays into arguments about where a new crate belongs. Flat keeps `ls crates/` the whole picture.

**Check:** is there a directory under `crates/` that holds directories rather than a crate?

### RS-MOD-35 [M] Point every dependency edge away from the facade

Members do not depend on the crate that re-exports them. `dev-dependencies` are the documented
exception: a cycle through them compiles, and it is the supported way for a member's tests to drive
the assembled facade.

**Why:** Cargo rejects the cycle outright — `error: cyclic package dependency` — so the edge cannot
exist, and reaching for the facade from inside a member is a sign the shared item belongs in a lower
member instead (RS-MOD-23, RS-MOD-24).

**Check:** grep the member manifests for the facade's name. Outside `[dev-dependencies]`, each hit
is a layering error.

## Imports and in-file order

### RS-MOD-36 [S] Group imports std / external / crate

Three blocks separated by blank lines — what `group_imports = "StdExternalCrate"` produces.

**Why:** the grouping tells a reader at a glance how much of the file's vocabulary is foreign, and
where a name came from. Setting it in `rustfmt.toml` makes it enforced rather than remembered
(RS-BUILD-27).

**Check:** is the option set, and does CI run `cargo fmt --check`?

```rust
// verified
//! Imports are grouped std / external / crate and each group is sorted.
use std::collections::BTreeMap;
use std::path::PathBuf;

#[derive(Debug, Default)]
pub struct Manifest {
    paths: BTreeMap<String, PathBuf>,
}
```

### RS-MOD-37 [S] Merge imports from the same crate

`use std::{fs, io::{self, Read, Write}, path::Path};` — `imports_granularity = "Crate"`.

**Why:** fewer lines and exactly one place to look per crate, instead of a screen of `use std::`
lines to scan.

**Check:** the rustfmt option handles it; the check is that the option is set.

### RS-MOD-38 [S] Import types and traits; call functions through a short path

`use std::fs; fs::read_to_string(p)`.

**Why:** the module name is context — `fs::read_to_string` says where the effect happens, while a
bare `read_to_string` could be anything. Types and traits are different: they appear in signatures,
where the path would be noise.

**Check:** grep for imported free functions. Would the call site read better with one segment of
path?

### RS-MOD-39 [S] Do not import an item used once when the path is short

`std::process::exit(2)` at one call site beats an import at the top.

**Why:** the import is a line at the top of the file that the reader must connect to a single use
two hundred lines down. The inline path is self-contained.

**Check:** for each import, how many uses does it have? One plus a short path means inline it.

### RS-MOD-40 [S] Resolve collisions by aliasing the module, not the item

`use std::fmt;` then `fmt::Result`, rather than `use std::fmt::Result as FmtResult;`.

**Why:** the aliased item creates a second name for one thing, which every reader must learn. The
module-qualified form uses names that already exist and reads the same as the documentation.

**Check:** grep `as ` in imports. Each is either a module alias or a case where the qualified form
would have worked.

### RS-MOD-41 [S] Order a file: docs, imports, public items, private items, tests

**Why:** readers scan top-down looking for the public surface, and the compiler does not care.
Private helpers first make a reader and a reviewer read the implementation before the interface.
Tests go last (RS-TEST-04).

**Check:** in each file, is the first non-import item public?

### RS-MOD-42 [S] Keep `impl` blocks in a predictable order

Inherent constructors, inherent methods, then trait impls grouped by trait, std traits before your
own.

**Why:** a type with nine `impl` blocks in arbitrary order forces a search for every question.
Multiple inherent `impl` blocks for one type need a reason — a `cfg`, or different bounds.

**Check:** does the type have more than one inherent `impl` block, and why?

### RS-MOD-43 [S] Order struct fields for the reader

Identifying field first, configuration next, caches and scratch last.

**Why:** the compiler reorders for layout anyway unless `repr(C)` is set, so field order is purely a
communication decision — use it to tell the reader what the type is about (RS-UNSAFE-14).

**Check:** does the first field identify the value, or is it whatever was added first?

### RS-MOD-44 [S] Keep functions short enough to see whole

When one is not, the fix is almost always extracting a pure helper and leaving a thin caller
(RS-FUNC-36).

**Why:** there is no line limit worth enforcing, but four levels of indentation or eight local
mutable bindings means the reader is simulating the function rather than reading it.

**Check:** what is the maximum indentation depth in the function, and how many `let mut` are live at
once?

## Orthogonality

### RS-MOD-45 [M] One concept, one mechanism

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
#[non_exhaustive]
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

### RS-MOD-46 [M] Absorb a special case into the general path, or give it its own type

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

### RS-MOD-47 [S] Keep sibling modules structurally parallel

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
| clippy | `wildcard_imports` | warn | a glob import outside a test module and a prelude |
