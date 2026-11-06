# Build: Manifest, Features, Dependencies, Lints, Toolchain, and CI

Scope: everything Cargo reads and CI runs — package metadata and the MSRV, features, dependencies
and their versions, the `[lints]` table, supply chain and release, the toolchain pin, profiles, and
the CI workflow. Where code goes on disk is the modules chapter's; what the crate's documentation
says is the documentation chapter's; what each lint forbids is the chapter that owns its subject.

The manifest is part of the API. It determines what your users can build, on which compilers, with
which transitive risk. A sloppy `Cargo.toml` produces a crate that is technically correct and
practically unusable.

Rust ships a stable release every six weeks and has no LTS channel, so the rules here assume edition
2024 on the newest stable toolchain.

`assets/Cargo.toml` is a complete, resolvable manifest rather than an excerpt.

## Contents

- **Manifest and metadata**
  - RS-BUILD-01 [M] Use `edition = "2024"` for anything new
  - RS-BUILD-02 [S] Choose an MSRV policy and publish it
  - RS-BUILD-03 [M] Fill in the full publish metadata
  - RS-BUILD-04 [M] Write `description` as one plain sentence
  - RS-BUILD-05 [S] Dual-license `MIT OR Apache-2.0` unless you have a reason not to
  - RS-BUILD-06 [M] Restrict the published tarball with `include`, not `exclude`
  - RS-BUILD-07 [M] Declare shared dependencies and package fields once in the workspace
  - RS-BUILD-08 [S] Rely on target auto-discovery rather than hand-listing targets
  - RS-BUILD-09 [M] Configure `[package.metadata.docs.rs]` and the `docsrs` cfg
  - RS-BUILD-10 [M] Commit `Cargo.lock`, for libraries too
  - RS-BUILD-11 [S] Keep a `CHANGELOG.md` in Keep-a-Changelog form

- **Features**
  - RS-BUILD-12 [M] Keep features additive only
  - RS-BUILD-13 [S] Default to `default = []`
  - RS-BUILD-14 [M] Use `dep:` syntax for optional dependencies
  - RS-BUILD-15 [M] Use the weak dependency syntax `optional-dep?/feature`
  - RS-BUILD-16 [M] Never use features for mutually exclusive choices
  - RS-BUILD-17 [M] Annotate feature-gated public items for docs.rs
  - RS-BUILD-18 [M] Test the feature powerset that matters, not just `--all-features`

- **Dependencies**
  - RS-BUILD-19 [M] Justify every dependency by more than an hour of saved work
  - RS-BUILD-20 [S] Prefer small, widely audited, actively maintained dependencies
  - RS-BUILD-21 [M] Use caret requirements; never pin exact versions in a library
  - RS-BUILD-22 [M] Turn off default features on heavy dependencies

- **Lints and warnings**
  - RS-BUILD-23 [M] Put lints in the manifest's `[lints]` table, not in `lib.rs`
  - RS-BUILD-24 [M] Run `clippy::pedantic` at `warn` and answer each warning
  - RS-BUILD-25 [M] Never blanket-`allow` at crate level to make CI green
  - RS-BUILD-26 [M] Deny warnings through Cargo config, not `RUSTFLAGS`
  - RS-BUILD-27 [M] Enforce `cargo fmt --check` in CI and keep `rustfmt.toml` minimal

- **Supply chain, versioning, release**
  - RS-BUILD-28 [M!] Run `cargo audit` on a schedule as well as on pull requests
  - RS-BUILD-29 [S] Enforce license policy and duplicate limits with `cargo deny`
  - RS-BUILD-30 [S] Run `cargo update` deliberately and review the diff
  - RS-BUILD-31 [M] Verify the MSRV claim with a pinned CI job
  - RS-BUILD-32 [M!] Run `cargo semver-checks` before every release
  - RS-BUILD-33 [M] Follow semver strictly, including the 0.x rule
  - RS-BUILD-34 [M] Dry-run and inspect the package list before publishing
  - RS-BUILD-35 [S] Keep the git tag, changelog entry, and published version in agreement

- **Toolchain, profiles, CI**
  - RS-BUILD-36 [M] Commit a `rust-toolchain.toml`
  - RS-BUILD-37 [M] Test on stable at minimum; add beta and nightly where they earn it
  - RS-BUILD-38 [M] Cover Linux, macOS, and Windows for anything touching the OS
  - RS-BUILD-39 [M] Run the full seven-step CI pipeline
  - RS-BUILD-40 [S] Cache the registry and `target/`, and use `cargo nextest`
  - RS-BUILD-41 [M] Change release profile defaults only with measurements
  - RS-BUILD-42 [S] Keep debug info in profiling builds and strip separately
  - RS-BUILD-43 [S] Raise `opt-level` for dependencies when tests are slow
  - RS-BUILD-44 [M] Keep `target/` and local `.cargo/config.toml` paths out of version control
  - RS-BUILD-45 [S] Prefer `cargo xtask` to shell scripts
  - RS-BUILD-46 [S] Measure build time with `cargo build --timings` before optimizing it

- Decided by tools

---

## Manifest and metadata

### RS-BUILD-01 [M] Use `edition = "2024"` for anything new

`edition = "2024"` for anything new. The 2024 edition tightens `unsafe_op_in_unsafe_fn`,
`static_mut_refs`, RPIT lifetime capture, and `if let` temporary scopes — all of which make code
more correct, not merely newer.

**Why:** each of those changes converts a class of silent bug into a diagnostic. `if let` temporary
scopes in particular fixed a real deadlock pattern where a lock guard in the scrutinee outlived the
body. Editions are per-crate, so adopting it costs nothing to dependents.

**Check:** `edition = "2024"` in the manifest; `cargo init` produces it by default.

```toml
# fragment — Cargo.toml
[package]
name = "myproj"
version = "0.1.0"
edition = "2024"
rust-version = "1.99"        # a real, tested MSRV — see RS-BUILD-31
```

### RS-BUILD-02 [S] Choose an MSRV policy and publish it

The policy is one of "latest stable", "stable minus two", or a pinned old version for distribution
packagers, stated where RS-DOC-33 puts it. Bumping the MSRV is at least a minor version bump.

**Why:** downstream users plan around your policy — distribution packagers especially, who may be on
a toolchain two years old. Publishing the policy converts an unpredictable breakage into a scheduled
one.

**Check:** does the README state the policy, and does the changelog record MSRV bumps as such?

### RS-BUILD-03 [M] Fill in the full publish metadata

`description`, `license` (or `license-file`), `repository`, `documentation`, `homepage`, `keywords`,
`categories` and `readme`, every one. A missing field degrades the crates.io and docs.rs pages and
is a five-minute fix.

**Why:** these fields drive search, categorization, and the links users need to evaluate the crate.
A crate with no `repository` cannot be audited before adoption, which for many organizations is
disqualifying.

**Check:** run `cargo publish --dry-run` and read the warnings; it names the missing fields.

```toml
# fragment — Cargo.toml
[package]
name = "globset"
version = "0.4.0"
edition = "2024"
description = "Cross-platform glob matching with a focus on throughput."
license = "MIT OR Apache-2.0"
repository = "https://github.com/OWNER/REPO"
documentation = "https://docs.rs/globset"
homepage = "https://github.com/OWNER/REPO"
keywords = ["glob", "pattern", "match"]
categories = ["text-processing"]
readme = "README.md"
```

### RS-BUILD-04 [M] Write `description` as one plain sentence

`description` is one sentence, no marketing, no crate name repetition, no trailing period-less
fragment. It appears in search results and is often all a user reads.

**Why:** it is displayed next to fifty competitors in a search listing, where the reader spends
about a second per line. Repeating the crate name wastes the part of that second that could have
said what the crate does.

**Check:** read the description without the name. Does it say what the crate does, in one sentence?

### RS-BUILD-05 [S] Dual-license `MIT OR Apache-2.0` unless you have a reason not to

Dual-license `MIT OR Apache-2.0` unless you have a specific reason otherwise; it is what the
ecosystem expects and what corporate reviewers approve without escalation. Ship both license files.

**Why:** this pair is the Rust ecosystem default, so it passes legal review as a known quantity.
Apache-2.0 contributes an explicit patent grant and MIT contributes maximum compatibility; anything
unusual triggers a review cycle that can take weeks.

**Check:** does `license` say `MIT OR Apache-2.0`, and are both files present in the published
tarball?

### RS-BUILD-06 [M] Restrict the published tarball with `include`, not `exclude`

Restrict what gets published with `include = [...]` rather than `exclude`. An allow-list keeps test
fixtures, benchmark corpora, and CI config out of the `.crate` tarball and cannot be defeated by a
new directory.

**Why:** `exclude` is a deny-list, so anything added later is published by default — including a
large fixture directory or, worse, a file with credentials. `include` fails closed.

**Check:** `cargo package --list` and read it. Anything a consumer does not need to build is a
finding.

```toml
# fragment — Cargo.toml
[package]
name = "myproj"
version = "0.1.0"
edition = "2024"
# An allow-list: a directory added tomorrow is excluded by default.
include = ["src/**/*.rs", "Cargo.toml", "README.md", "LICENSE-*"]
```

### RS-BUILD-07 [M] Declare shared dependencies and package fields once in the workspace

In a workspace, declare shared dependencies once in `[workspace.dependencies]` and inherit with
`dep.workspace = true`. Also inherit `version`, `edition`, `license`, `repository`, and
`rust-version` via `[workspace.package]` — one place to bump, no drift. A member may write
`dep = { workspace = true, default-features = false }` only with `rust-version` at 1.99 or later:
Cargo 1.99 honours it on an edition-2024 member, and older Cargo rejects that manifest.

**Why:** duplicated version requirements across members drift, until two members pull different
majors of one crate into one build (RS-BUILD-29). One declaration makes that impossible rather than
a review responsibility.

**Check:** grep member manifests for a version literal on a dependency another member also uses.
Each is a value that should be inherited.

```toml
# fragment — the workspace Cargo.toml
[workspace]
resolver = "3"
members = ["crates/*"]

[workspace.package]
edition = "2024"
rust-version = "1.99"
license = "MIT OR Apache-2.0"
repository = "https://github.com/OWNER/REPO"

[workspace.dependencies]
thiserror = "2"
```

### RS-BUILD-08 [S] Rely on target auto-discovery rather than hand-listing targets

Set `[package] autobins`/`autotests` behaviour by convention rather than by hand-listing targets;
explicit `[[bin]]` sections are for binaries whose name differs from the file, or with distinct
`required-features`.

**Why:** hand-listed targets go stale — a new integration test in `tests/` silently stops running if
the manifest enumerates them. Convention keeps the manifest short and the discovery automatic.

**Check:** are there `[[bin]]` or `[[test]]` sections that only restate the conventional path? They
can be deleted.

### RS-BUILD-09 [M] Configure `[package.metadata.docs.rs]` and the `docsrs` cfg

`[package.metadata.docs.rs]` should enable the features docs.rs should build with
(`all-features = true`, or an explicit list) and `rustdoc-args = ["--cfg", "docsrs"]` so the
`docsrs`-gated `doc_cfg` line takes effect (RS-BUILD-17). Since 2026-05-01 docs.rs builds only
`x86_64-unknown-linux-gnu` unless `targets` lists more, so a crate with platform-gated API sets
`targets` to cover it.

**Why:** docs.rs builds with default features unless told otherwise, so a crate whose interesting
API is feature-gated publishes documentation missing most of itself. The `docsrs` cfg is what makes
the feature badges appear (RS-BUILD-17).

**Check:** open the published docs and look for a feature-gated item and a platform-gated one.
Missing or unbadged means the metadata is absent.

```toml
# fragment — Cargo.toml
[package.metadata.docs.rs]
all-features = true
rustdoc-args = ["--cfg", "docsrs"]
# Only the default target is built unless `targets` lists every one to document:
# targets = ["x86_64-unknown-linux-gnu", "x86_64-pc-windows-msvc"]
```

### RS-BUILD-10 [M] Commit `Cargo.lock`, for libraries too

Commit `Cargo.lock` for binaries and workspaces that produce binaries; commit it for libraries too —
modern guidance is that it makes CI reproducible, and it does not affect downstream consumers.

**Why:** the lockfile is ignored when your crate is used as a dependency, so committing it costs
downstream nothing and buys you a CI that fails on your schedule rather than on a dependency's
release schedule. The old advice against it predates that clarification.

**Check:** is `Cargo.lock` in the repository and not in `.gitignore`?

### RS-BUILD-11 [S] Keep a `CHANGELOG.md` in Keep-a-Changelog form

A section per version and a line per user-visible change. "See git log" is not a changelog.

**Why:** a git log is a record of implementation steps, not of what changed for users, and it cannot
be read in the two minutes someone spends deciding whether to upgrade. The changelog is a different
document with a different audience (RS-DOC-26).

**Check:** can a user determine from the changelog alone whether an upgrade affects them?

## Features

### RS-BUILD-12 [M] Keep features additive only

Features are additive only. Enabling a feature must never remove an item, change a signature, or
alter behaviour, because Cargo unifies features across the whole dependency graph and your user did
not ask for it.

**Why:** feature unification means any crate in the graph can turn on your feature for everyone. If
the feature subtracts, an unrelated dependency's choice silently breaks a consumer who never opted
in — and the failure appears at a distance from its cause.

**Check:** for each feature, does disabling it remove items only? Any `#[cfg(not(feature = …))]`
providing an alternative implementation is a subtractive feature.

### RS-BUILD-13 [S] Default to `default = []`

`default = []` where you can afford it. Every default feature is a dependency you impose on
`--no-default-features` users who never learned it existed. What each feature costs is documented in
the crate root (RS-DOC-02).

**Why:** defaults are what most users get, so they set the crate's real dependency footprint. An
empty default makes cost opt-in, which is what forces the question of what each addition buys.

**Check:** what does `--no-default-features` leave working? If nothing, the defaults are not really
optional.

### RS-BUILD-14 [M] Use `dep:` syntax for optional dependencies

Optional dependencies use the `dep:` syntax so they do not implicitly create a feature of the same
name: `serde = { version = "1", optional = true }` plus `serde = ["dep:serde", "chrono?/serde"]`.

**Why:** without `dep:`, every optional dependency silently becomes a public feature name you must
support forever, including ones you meant to keep internal. The explicit form lets you control the
feature surface.

**Check:** grep for `optional = true` and confirm the corresponding feature uses `dep:`.

```toml
# fragment — Cargo.toml
[dependencies]
serde = { version = "1", optional = true }

[features]
# `dep:` keeps the optional dependency from becoming a public feature name.
serde = ["dep:serde"]
```

### RS-BUILD-15 [M] Use the weak dependency syntax `optional-dep?/feature`

`optional-dep?/feature` enables a feature on an optional dependency only when that dependency is
already enabled. Without the `?`, you silently turn the optional dependency on.

**Why:** `chrono/serde` without the `?` enables `chrono` itself, so a user who wanted only `serde`
support gets an entire date library. The one character is the difference between conditional and
unconditional.

**Check:** grep feature definitions for `/` without a preceding `?` on an optional dependency.

```toml
# fragment — Cargo.toml
[dependencies]
chrono = { version = "0.4", optional = true }
serde = { version = "1", optional = true }

[features]
# `chrono?/serde` enables chrono's serde support only if chrono is already on.
serde = ["dep:serde", "chrono?/serde"]
```

### RS-BUILD-16 [M] Never use features for mutually exclusive choices

Two crates in the graph will enable both, and your `compile_error!` becomes their unfixable build
failure. Use runtime selection, separate crates, or `cfg` on target.

**Why:** unification guarantees that if two dependents each pick a different option, both get
enabled — and neither dependent can fix it, because neither is wrong. The resulting build failure
has no resolution short of forking.

**Check:** grep for `compile_error!` guarded on feature combinations. Each is a design that cannot
survive unification.

### RS-BUILD-17 [M] Annotate feature-gated public items for docs.rs

Put `#![cfg_attr(docsrs, feature(doc_cfg))]` at the crate root so docs.rs shows the badge on every
feature-gated public item. `doc_cfg` is nightly-only and docs.rs builds on nightly; with it on,
rustdoc derives each badge from the item's own `#[cfg]`, so an explicit
`#[cfg_attr(docsrs, doc(cfg(feature = "x")))]` is needed only to override a derived badge. An item
that appears in docs but does not exist by default is a support ticket.

**Why:** with `all-features` documentation, every gated item appears as though it is always
available. The badge is the only thing that tells the reader they need to enable something.

**Check:** does the crate root carry the `doc_cfg` line, and does
`RUSTDOCFLAGS="--cfg docsrs" cargo +nightly doc --all-features` show a badge on a feature-gated
item? After a release, open the crate on docs.rs and find one there too: its badge names the
feature.

### RS-BUILD-18 [M] Test the feature powerset that matters, not just `--all-features`

At minimum: default, `--no-default-features`, and each feature alone.
`cargo hack --feature-powerset --depth 2` automates this.

**Why:** `--all-features` compiles every `cfg` block but never the combinations where one is absent,
so a missing import behind `#[cfg(not(feature))]` goes undetected. Each feature alone is the
configuration real users pick.

**Check:** does CI build all three configurations? `--all-features` alone hides the
`--no-default-features` breakage.

## Dependencies

### RS-BUILD-19 [M] Justify every dependency by more than an hour of saved work

Every dependency must be justified by something it does that would take meaningfully more than an
hour to write and maintain. A crate for left-padding, for `is_even`, or for three lines of `std` is
a supply-chain liability, a compile-time cost, and a semver risk — for nothing.

**Why:** each dependency adds an author who can compromise your users, a version requirement that
can conflict, and build time for every consumer. Those costs are permanent and shared; the saved
hour is one-off and yours.

**Check:** for each direct dependency, estimate what replacing it would cost. Under an hour, inline
it.

### RS-BUILD-20 [S] Prefer small, widely audited, actively maintained dependencies

Prefer dependencies that are small, widely audited, and maintained by people who ship: `serde`,
`regex`, `rayon`, `tokio`, `clap`, `thiserror`, `anyhow`, `itertools`, `bstr`, `memchr`. Check last
release date, open issue trends, and transitive count before adding anything else.

**Why:** a widely used crate has had its bugs found by other people and will be patched when a CVE
lands. An unmaintained one becomes your problem at the worst possible moment, and vendoring it later
is more work than avoiding it now.

**Check:** for each dependency, when was the last release and how many transitive crates does it
pull in?

### RS-BUILD-21 [M] Use caret requirements; never pin exact versions in a library

Use caret requirements (`"1.2"`, meaning `^1.2`) and let Cargo resolve. Do not pin exact versions
(`"=1.2.3"`) in a library — it makes your crate uncombinable with anyone else's constraint.

**Why:** an exact pin means any other crate requiring a different patch version cannot coexist with
yours, which is an unresolvable conflict for the user. Reproducibility belongs in the lockfile
(RS-BUILD-10), not in the requirement.

**Check:** grep for `=` version requirements in a library manifest.

### RS-BUILD-22 [M] Turn off default features on heavy dependencies

Enable only what you use:
`tokio = { version = "1", default-features = false, features = ["rt", "macros"] }`. This is often
the single largest build-time win available. In a workspace, turn them off in
`[workspace.dependencies]`; turning them off on one member's inherited dependency needs
`rust-version` 1.99 (RS-BUILD-07).

**Why:** default features are chosen for the dependency's typical user, not for you, and they
frequently pull in most of the crate. Because features unify, your choice also affects everyone
downstream.

**Check:** `cargo tree` and look for large subtrees. Each is a candidate for
`default-features = false`.

```toml
# fragment — Cargo.toml
[dependencies]
# Default features off, then exactly what is used — usually the largest build win.
tokio = { version = "1", default-features = false, features = ["rt", "macros"] }
```

## Lints and warnings

### RS-BUILD-23 [M] Put lints in the manifest's `[lints]` table, not in `lib.rs`

Lints belong in the manifest's `[lints]` table, inherited from `[workspace.lints]`, not in a wall of
`#![deny(...)]` attributes in `lib.rs`. The manifest is where a reviewer looks for policy, and it
applies to every target automatically. `[lints] workspace = true` is all-or-nothing, so a lint only
some members want stays out of the workspace table, as `print_stdout` does in `assets/Cargo.toml` —
the table this standard ships, to copy whole. Name `elided_lifetimes_in_paths` and
`explicit_outlives_requirements` individually rather than enabling `rust_2018_idioms`: its other
three members cover what edition 2024 already rejects or has made unnecessary.

**Why:** crate-level attributes apply only to that crate root, so tests, benches, and examples
silently miss them. The manifest table covers every target and is inheritable across a workspace.

**Check:** grep for `#![deny(` and `#![warn(` in source; each belongs in the manifest. Every member
has `[lints] workspace = true` or a deliberate block of its own — a member with neither starts with
none of the standard.

### RS-BUILD-24 [M] Run `clippy::pedantic` at `warn` and answer each warning

`clippy::pedantic` at `warn` is the right default. Treat each resulting warning as a question to
answer, and allow individual lints with a comment giving the reason — never allow the group. The
group grows with the toolchain, so each toolchain bump brings new warnings to answer.

**Why:** pedantic contains genuinely valuable lints mixed with ones that will not suit your crate,
so the group is worth enabling and the exceptions are worth recording. Allowing the whole group
discards the valuable ones to avoid arguing with a handful.

**Check:** grep for `pedantic = "allow"`. Each individual allow in the manifest carries a comment
giving its reason — no lint reads a manifest comment, so this one is review.

### RS-BUILD-25 [M] Never blanket-`allow` at crate level to make CI green

A crate that allows `clippy::too_many_arguments` globally has decided never to notice a
nine-argument function again.

**Why:** a crate-level allow silences the lint for code that does not exist yet, which is where it
would have been most useful. It converts a temporary annoyance into a permanent blind spot.

**Check:** for each crate-level allow, could it be scoped to the handful of items that need it?

### RS-BUILD-26 [M] Deny warnings through Cargo config, not `RUSTFLAGS`

Deny warnings in CI through Cargo's own configuration rather than `RUSTFLAGS`:
`CARGO_BUILD_WARNINGS=deny` (or `[build] warnings = "deny"` in `.cargo/config.toml`) controls this
without invalidating the build cache, so developers can flip it locally without a full rebuild. It
also fails `cargo doc` on a rustdoc warning. A Cargo older than the target ignores the setting, so
an MSRV job on an older toolchain does not deny warnings.

**Why:** `RUSTFLAGS` is part of the fingerprint Cargo uses to decide what to rebuild, so setting it
invalidates the entire cache. The dedicated setting does not, which makes "build with warnings
denied" a cheap local check rather than a CI-only step.

**Check:** both `CARGO_BUILD_WARNINGS=deny` and `[build] warnings = "deny"` fail the build with
``error: warnings are denied by `build.warnings` configuration``. Grep CI config for
`RUSTFLAGS="-Dwarnings"` and `RUSTDOCFLAGS="-D warnings"`, and replace both.

### RS-BUILD-27 [M] Enforce `cargo fmt --check` in CI and keep `rustfmt.toml` minimal

Enforce formatting in CI with `cargo fmt --check`, and keep `rustfmt.toml` minimal — the default
style is a coordination win, and every override costs new contributors. The overrides worth having
are `group_imports = "StdExternalCrate"` and `imports_granularity = "Crate"`. Both are nightly-only,
so a crate that sets them formats with `cargo +nightly fmt` locally and checks with
`cargo +nightly fmt --check` in CI; a crate on stable rustfmt alone sets neither.

**Why:** formatting arguments consume review attention that should go to behaviour, and only a
mechanical check ends them. Each override reintroduces the argument in a smaller form, so it needs a
concrete benefit — import grouping is one, because it reduces diff noise.

**Check:** both options are nightly-only. Stable rustfmt reports
`can't set imports_granularity = Crate, unstable features are only available in nightly channel` and
continues with the default, so code it formatted fails a nightly format job. Do the local command
and the CI job use one toolchain?

## Supply chain, versioning, release

### RS-BUILD-28 [M!] Run `cargo audit` on a schedule as well as on pull requests

Run `cargo audit` (or `cargo deny check advisories`) in CI on a schedule as well as on pull
requests, so a new advisory against an unchanged dependency is noticed.

*Relaxed form:* for a tool with no network or untrusted input, a monthly manual run is acceptable.
Anything that parses data you did not create wants the schedule.

**Why:** advisories are published against versions you already depend on, so a PR-only check never
fires for a crate nobody touched. The scheduled run is what converts "we would have caught it on the
next change" into "we caught it".

**Check:** is there a scheduled workflow, not just a PR trigger?

### RS-BUILD-29 [S] Enforce license policy and duplicate limits with `cargo deny`

Use `cargo deny` to enforce license policy, banned crates, and duplicate-version limits. Multiple
major versions of the same crate in one graph is a compile-time and binary-size tax worth measuring.

**Why:** license compliance and duplicate bloat both degrade silently as the graph grows, and
neither is visible in a normal build. A configured check turns both into a reviewable diff.

**Check:** does `cargo deny check` pass, and does the config actually list the allowed licenses
rather than allowing everything?

### RS-BUILD-30 [S] Run `cargo update` deliberately and review the diff

An update is a change of its own, with its lockfile diff read, never a side effect of an unrelated
one.

**Why:** a lockfile change bundled into a feature PR gets no review, and it is exactly where a
compromised release would enter. Isolating it makes the diff readable and the bisection clean if
something breaks.

**Check:** do lockfile updates appear in their own commits?

### RS-BUILD-31 [M] Verify the MSRV claim with a pinned CI job

Set `rust-version` to a real, tested MSRV, and verify it with a dedicated CI job pinned to that
toolchain. Test minimal versions (`cargo +nightly update -Z minimal-versions`) at least occasionally
— under-specified lower bounds are a common latent breakage. Running
`cargo hack check --rust-version --workspace --all-targets --ignore-private` takes the toolchain
from each package's `rust-version`, so the job cannot drift from the manifest. A hand-written job
runs `cargo +<msrv>`: a committed `rust-toolchain.toml` (RS-BUILD-36) outranks the default an action
installs, so plain `cargo` there builds on the pinned release, not the MSRV.

**Why:** Cargo enforces `rust-version` against your users and resolves versions by it, so an
untested value is a hard failure for someone. Normal CI runs the latest toolchain and the newest
permitted dependencies, so neither the MSRV nor the lower bounds are exercised otherwise.

**Check:** is there a job pinned to `rust-version`, and has minimal-versions ever been run?

### RS-BUILD-32 [M!] Run `cargo semver-checks` before every release

Trust it over intuition about what is breaking. It catches removed impls, narrowed bounds, changed
variant shapes, and newly private items that human review misses (RS-API-54).

*Relaxed form:* an unpublished internal crate with one consumer can rely on that consumer's build.
The moment there are two, the tool is cheaper than the coordination.

**Why:** semver breakage in Rust is subtle — adding a trait impl, tightening a bound, or making an
enum non-exhaustive can all break dependents in ways that are invisible in a diff. The tool checks
the actual API surface rather than the intent.

**Check:** is the check part of the release process rather than something run when someone
remembers?

### RS-BUILD-33 [M] Follow semver strictly, including the 0.x rule

0.y.z treats `y` as the major. Do not ship a breaking change as a patch because "nobody uses it
yet". RS-API-54 lists which changes break.

**Why:** Cargo's resolver implements these rules exactly, so a breaking patch release breaks every
existing build that resolves to it, without any action by the user. "Nobody uses it" is not
observable from your side.

**Check:** does the version bump match the nature of the change, as `cargo semver-checks` classifies
it?

### RS-BUILD-34 [M] Dry-run and inspect the package list before publishing

`cargo publish --dry-run` and inspect `cargo package --list` before a real publish. Publishing is
irreversible; yanking does not remove anything.

**Why:** a yanked version stays downloadable and stays in every existing lockfile, so a leaked file
or a missing module cannot be withdrawn — only superseded by another version, with the mistake still
available.

**Check:** does the release process include both commands before the publish step?

### RS-BUILD-35 [S] Keep the git tag, changelog entry, and published version in agreement

Tag releases in git, and make the tag, the `CHANGELOG.md` entry, and the published version agree.
`cargo release` or `release-plz` automates this consistently.

**Why:** these three are the only way anyone maps a published artifact back to source, and manual
processes desynchronize them within a few releases. A mismatch makes it impossible to audit what was
actually shipped.

**Check:** for the last three releases, do the tag, changelog heading, and crates.io version match?

## Toolchain, profiles, CI

### RS-BUILD-36 [M] Commit a `rust-toolchain.toml`

It pins an exact release as `channel`, with `components = ["rustfmt", "clippy"]` and any required
`targets`, so every contributor's first build is identical to CI's. `assets/rust-toolchain.toml` is
the file.

**Why:** without it, contributors use whatever toolchain they have, so lint and format results
differ from CI and the first PR is a round trip about warnings nobody can reproduce. `"stable"` pins
nothing: it moves every six weeks. `rustup` honours the file automatically.

**Check:** does the file exist, name an exact release, and list the components CI uses?

```toml
# fragment — rust-toolchain.toml
[toolchain]
channel = "1.99.1"
components = ["rustfmt", "clippy"]
targets = ["x86_64-unknown-linux-musl"]
```

### RS-BUILD-37 [M] Test on stable at minimum; add beta and nightly where they earn it

Test on stable at minimum; add beta to catch upcoming regressions and nightly only for the jobs that
need it (Miri, `-Z` flags, fuzzing). Such a job runs `cargo +beta` or `cargo +nightly`: a committed
`rust-toolchain.toml` (RS-BUILD-36) outranks the toolchain an action installs, so plain `cargo`
there tests the pinned release again.

**Why:** beta gives six weeks of warning before a regression reaches your users, which is enough to
file and fix. Nightly is unstable enough that gating the whole pipeline on it produces failures
unrelated to your code.

**Check:** is nightly required for anything other than the tools that genuinely need it, and does
every beta or nightly job name its toolchain with `+`?

### RS-BUILD-38 [M] Cover Linux, macOS, and Windows for anything touching the OS

CI matrix covers Linux, macOS, and Windows for anything touching paths, processes, terminals, or
filesystem metadata. Path handling that was never run on Windows is path handling that is broken on
Windows.

**Why:** path separators, case sensitivity, permissions, and line endings all differ, and none of
the differences produce a compile error. The bug is found by a user on the platform you did not
test.

**Check:** does the matrix include all three for any crate touching the filesystem?

### RS-BUILD-39 [M] Run the full seven-step CI pipeline

The CI pipeline is: `fmt --check`, `clippy --all-targets --all-features` with warnings denied,
`test --all-features`, `test --no-default-features`, `doc --no-deps` with rustdoc warnings denied,
then audit and semver checks on release branches.

**Why:** each step catches a class the others cannot — formatting, lints, the two feature
configurations, documentation links, advisories, and API breakage. Dropping one leaves that class
entirely unchecked.

**Check:** compare the pipeline against the seven. `--all-targets` matters: without it, tests and
benches are not linted.

### RS-BUILD-40 [S] Cache the registry and `target/`, and use `cargo nextest`

Cache the Cargo registry and `target/` directory in CI (for example with `Swatinem/rust-cache`), and
use `cargo nextest` for faster, clearer test output on large suites. A job that runs Miri, or that
writes a `target/` cache pull requests can read, holds no secrets in its environment: a tool may
save the environment into `target/`, as Miri did, and the cache hands it to the next pull request.
Cargo turns incremental compilation off when `CI` is set, so CI needs no `CARGO_INCREMENTAL=0`.

**Why:** CI time is the length of the feedback loop, and a cold dependency build dominates it.
`nextest` runs each test in its own process, which both parallelizes better and isolates failures.

**Check:** how long is a no-op CI run? Several minutes means the cache is missing or ineffective.

### RS-BUILD-41 [M] Change release profile defaults only with measurements

`[profile.release]` defaults are reasonable; change them with measurements. `lto = "thin"` is
usually a good trade, `codegen-units = 1` buys a few percent for much slower builds, and
`panic = "abort"` is an application decision (RS-ERR-29).

**Why:** each of these trades build time or behaviour for runtime, and the sizes of both sides are
project-specific. `panic = "abort"` in particular changes semantics — `catch_unwind` stops working —
so it is never a library's call.

**Check:** for each non-default profile setting, is there a measurement?

```toml
# fragment — Cargo.toml
[profile.release]
lto = "thin"                    # usually a good trade
debug = "line-tables-only"      # keep profiles usable; strip separately
# codegen-units = 1             # a few percent, much slower builds
# panic = "abort"               # an application decision, never a library's
```

### RS-BUILD-42 [S] Keep debug info in profiling builds and strip separately

Keep `debug = true` (or `debug = "line-tables-only"`) in release builds you intend to profile, and
strip separately. Profiling a stripped binary wastes more time than the build costs.

**Why:** without symbols a profile shows addresses, so the expensive step is reconstructing what
they mean. `line-tables-only` gives usable stacks at a fraction of the size of full debug info.

**Check:** does the profiling build carry symbols, and is stripping a separate release step?

### RS-BUILD-43 [S] Raise `opt-level` for dependencies when tests are slow

Use `[profile.dev.package."*"] opt-level = 3` when tests are slow because of dependencies
(compression, crypto, image decoding) while keeping your own crate at `opt-level = 0` for fast
iteration.

**Why:** dependencies are rebuilt rarely and are often the runtime bottleneck in debug tests, so
optimizing them costs little and buys a lot. Your own crate stays unoptimized, which is what keeps
the edit-compile loop fast.

**Check:** if the test suite is slow in debug, is the time in your code or a dependency?

```toml
# fragment — Cargo.toml, fast dependencies and fast-to-compile own code
[profile.dev.package."*"]
opt-level = 3
```

### RS-BUILD-44 [M] Keep `target/` and local `.cargo/config.toml` paths out of version control

Do not check `target/` into version control, and do not commit `.cargo/config.toml` settings that
hard-code a local path or a private registry into a public repository.

**Why:** `target/` is enormous and machine-specific, and a committed local path breaks every other
contributor's build. A private registry URL in a public repo is also an information leak.

**Check:** is `target/` in `.gitignore`, and does any committed `.cargo/config.toml` contain an
absolute path?

### RS-BUILD-45 [S] Prefer `cargo xtask` to shell scripts

Prefer `cargo` subcommands over shell scripts for repeatable tasks (`cargo xtask` pattern) so
contributors on all platforms run the same thing.

**Why:** shell scripts do not run on Windows without a shim, and they are unchecked — a typo in a
path is found at runtime. An xtask is a Rust binary in the workspace, so it is compiled,
cross-platform, and can reuse project code.

**Check:** are there `.sh` scripts that contributors must run? Each is a Windows contributor
blocked.

### RS-BUILD-46 [S] Measure build time with `cargo build --timings` before optimizing it

Measure build time before optimizing it: `cargo build --timings` identifies the crate that costs 40%
of the build, which is usually one heavy default feature away from being cheap (RS-BUILD-22).

**Why:** build time is usually dominated by one or two dependencies rather than spread evenly, so
the fix is targeted rather than architectural. Guessing leads to splitting your own crate, which
rarely helps.

**Check:** has `--timings` been run? The report names the crate and shows what blocks pipelining.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `lint_groups_priority` | deny | a lint group at the same priority as a lint in it — give groups `priority = -1` |
| clippy | `unwrap_used` | deny | `unwrap()` outside tests |
| clippy | `expect_used` | deny | `expect()` outside tests |
| clippy | `panic` | deny | `panic!` in library code |
| clippy | `todo` | deny | `todo!` |
| clippy | `unimplemented` | deny | `unimplemented!` |
| clippy | `indexing_slicing` | deny | indexing or slicing that can panic — `get` instead |
| clippy | `undocumented_unsafe_blocks` | deny | an `unsafe` block without a `// SAFETY:` comment |
| clippy | `allow_attributes` | warn | `#[allow]` — `#[expect(…, reason = "…")]` warns once it is no longer needed |
| clippy | `allow_attributes_without_reason` | warn | a lint attribute without `reason = "…"` |
| rustc | `linker_messages` | warn | linker output, which sits outside `warnings` — read it, and allow it only per platform |
