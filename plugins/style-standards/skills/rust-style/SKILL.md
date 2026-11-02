---
name: rust-style
description: >-
  The modern Rust 1.99 (edition 2024) engineering standard — a 633-rule library merging the Rust API
  Guidelines, the empirical conventions of ripgrep and the BurntSushi crates, and a functional-first
  default. Covers naming, API design, errors and panics, iterator and combinator style, ownership
  and lifetimes, traits and generics, module and workspace layout, Cargo/features/lints/CI, testing
  and fuzzing, rustdoc, performance, concurrency and async, unsafe and FFI, ripgrep-grade CLI
  architecture, macros, and API symmetry. Use this whenever writing, reviewing, refactoring,
  scaffolding, or debugging ANY Rust — a crate, one function, a `Cargo.toml`, a trait, an async
  task, an `unsafe` block, a CLI — even if the user never mentions "style", "standards", or
  "quality". Also use when asked to make Rust "idiomatic", "modern", "clean", "elegant",
  "production-grade", or "functional", when auditing a Rust codebase, when choosing between Rust
  design alternatives, and when moving code to edition 2024 or a newer toolchain.
---

# Rust Style — 1.99

A single standard formed from three sources: the **Rust API Guidelines** (the public surface,
naming, trait impls), the **empirical conventions of ripgrep and the BurntSushi crates** (crate
architecture, disciplined performance, CLI shape), and a **functional-first default** for function
bodies. Where they disagree, this standard picks a side and says why.

**Target: Rust 1.99 stable, edition 2024.** The bar is not "compiles and passes clippy". It
is: a reviewer who maintains `regex`, `ignore`, or `tokio` would merge this without comment.

## How to use this standard

1. **Read section 2** before emitting Rust code. It is the Rust 1.99 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID — `RS-ERR-03`, `RS-TEST-05`. The prefix identifies the owning chapter (section
6 maps prefix to file), so cite the ID when justifying a change and the reader can find the full
rule and its rationale. When a rule in a chapter and a rule here appear to conflict, the chapter is
the detailed statement and wins; sections 1 and 3 govern how to break a genuine tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered,
`references/migration.md` maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Rust 1.99, edition 2024, and any test it ships passes. `// fragment` — shown in
context rather than run as a unit, usually because it uses names the chapter declares around it. `//
rejected — <tool>: …` — the rejection is the point, and the marker names the tool that rejects it:
`rustc`, `clippy`, `rustdoc`. A trailing `— GOOD` or `— BAD` names which side of the rule the block
illustrates. A block in another language carries its marker in that language's comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Rust code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in library and high-reliability code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**Code is "library or high-reliability" — `[M!]` applies as `[M]` — if any of these hold:** it is
published to a registry or consumed by code you do not control; a panic takes down a process that
someone else owns (a server, a plugin, an embedded target); it is a security boundary (parsers on
untrusted input, cryptography, sandboxes, allocators); or it stores data others cannot reconstruct.
**Otherwise** — scripts, internal binaries, prototypes, examples — `[M!]` rules are recommendations,
and the relaxed form given with each rule is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Rust 1.99 reality check

Most Rust on the public internet predates these. The entries that **compile either way** are the
dangerous ones, because the compiler says nothing about them.

### 2.1 What compiles either way and behaves differently

1. **Integer overflow panics in debug and wraps in release.** Arithmetic on attacker-influenced
   values must be `checked_*`, `saturating_*` or `wrapping_*` explicitly, or debug and release
   disagree about what your program does. `strict_*` panics in both profiles, so it belongs where
   overflow is a bug rather than an input (`RS-ERR-31`).
2. **`as` casts truncate silently at run time.** `len as u32` on a 5 GB buffer is a wrong answer
   with no error. rustc accepts it; clippy's `cast_possible_truncation`, a warning in
   `assets/Cargo.toml`, is what flags it. Use `u32::try_from(len)?` on any conversion that can lose
   data, and `cast_signed` or `cast_unsigned` where a sign change is the point (`RS-PERF-30`).
3. **A dropped `Future` is a cancellation at an arbitrary `.await`.** Anything holding a resource
   across an await must be correct when dropped there; `select!` makes this routine rather than
   exotic (`RS-CONC-33`).

The 2024 edition changed four behaviours without a diagnostic:

| Old habit | Edition 2024 reality |
|---|---|
| `if let` temporary dropped at end of statement | dropped at end of the `if let`, which changes lock scopes |
| tail-expression temporaries live to end of block | shortened; a temporary can now drop earlier than it used to |
| `$e:expr` stops before `_` and `const { … }` | `expr` matches both, so a later `_` arm stops firing; `expr_2021` keeps the old fragment (`RS-MACRO-09`) |
| `boxed_slice.into_iter()` yields `&T` | yields `T`, by value |

Releases change things silently too — CI builds without incremental compilation in 1.99, the
derived `PartialOrd` path in 1.98, drop timing in 1.91 to 1.95. `references/migration.md` RS-MIG-03
lists them by release, to read on every toolchain bump.

### 2.2 What the 2024 edition rejects

| Old habit | Edition 2024 reality |
|---|---|
| `unsafe fn` body is implicitly unsafe | `unsafe_op_in_unsafe_fn` is on; write the inner `unsafe { }` explicitly |
| `#[no_mangle]`, `#[export_name]`, `#[link_section]` | must be `#[unsafe(no_mangle)]` and friends |
| `static mut FOO` then `&FOO` | `static_mut_refs` denies it; use `OnceLock`/`LazyLock`/atomics |
| `impl Trait` return captures only named lifetimes | captures **all** in-scope lifetimes; narrow with `+ use<'a, T>` (1.82) |
| `gen` usable as an identifier | reserved keyword |
| `extern "C" { fn abs(…); }` | must be `unsafe extern "C" { … }`; an item marked `safe fn` is called without `unsafe` |
| `env::set_var` and `env::remove_var` are safe | both are `unsafe`, so `unsafe_code = "forbid"` rejects them; pass tests a lookup (`RS-TEST-16`) |

### 2.3 Standard-library features that replaced ecosystem crates

The ones most often missed: `LazyLock` for `lazy_static`, `cfg_select!` for `cfg-if`,
`assert_matches!` for `assert!(matches!(..))`, `File::lock` for `fs2`, `async fn` in traits for
`#[async_trait]`, and `Atomic*::update` for a `compare_exchange` loop. `references/migration.md`
RS-MIG-01 has every one, with the release it arrived in.

## 3. Design principles

Elegance in Rust has two axes, and a design needs both. **Subtraction** removes what does not earn
its place: a `mut` that a fold would remove, a `String` that a `&str` would remove, a `clone()` that
a borrow would remove, an `Arc<Mutex<_>>` that a channel would remove, a builder that a struct
literal would remove. **Symmetry** is what remains after subtraction being *regular*: operations
that come in pairs, siblings that take their arguments in the same order, one mechanism per concept,
and no branch that exists for a single input.

The two fail differently. Excess makes code longer than it needs to be. Asymmetry makes it
unlearnable — the reader cannot generalize from one function to the next, so every call site must be
read individually. A codebase accretes asymmetry one reasonable-looking patch at a time, which is
why it needs a standing question rather than occasional cleanup.

When two rules appear to conflict and their tiers are equal, break the tie with these five
questions, in order:

1. **What can be deleted?** Fewer types, fewer parameters, fewer lifetimes, fewer allocations, fewer
   dependencies, fewer states.
2. **What can be made unrepresentable?** Push invariants into the type system so invalid states
   cannot be constructed, not merely rejected at runtime.
3. **What can be made a value instead of an effect?** Prefer a pipeline that returns data over a
   loop that mutates data.
4. **What is asymmetric?** If `from_x` exists, does `to_x`? Do sibling functions take their
   arguments in the same order? Do the error variants share one shape? A missing half is either a
   restriction the documentation must state, or an oversight (`RS-API-58` … `RS-API-61`).
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general case, or name it as its own type (`RS-MOD-45`,
   `RS-MOD-46`).

Readability outranks all five. A combinator chain that requires the reader to track three type
transformations is worse than the `match` it replaced (`RS-FUNC-42`), and a symmetry nobody can see
is not worth the name it costs.

## 4. Core rules

These 28 `RS-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### Names

- **RS-CORE-01 `[M]`** `UpperCamelCase` types, traits, and variants; `snake_case` functions,
  modules, and locals; `SCREAMING_SNAKE_CASE` constants — rustc's default lints enforce all three.
  Acronyms are ordinary words — `HttpClient`, `Uuid`, `OsStr`, never `HTTPClient`
  (`references/naming.md` RS-NAME-01).
- **RS-CORE-02 `[M]`** Conversion prefixes carry cost information and are not interchangeable:
  `as_` is a free borrowed view, `to_` allocates or computes, `into_` consumes the receiver. A
  method named `as_*` that allocates is misnamed (`references/naming.md` RS-NAME-12).
- **RS-CORE-03 `[M]`** Getters omit `get_`: `len()`, `name()`, `config()`. `get_` is reserved for
  the fallible `Index`-like lookup returning `Option`/`Result`
  (`references/naming.md` RS-NAME-16).
- **RS-CORE-04 `[S]`** No abbreviations unless the abbreviation is more standard than the word
  (`config`, `regex`, `buf`, `ctx`). `rslt`, `mngr`, `hdlr` are not
  (`references/naming.md` RS-NAME-26).
- **RS-CORE-05 `[M]`** Run `cargo fmt`. Keep `rustfmt.toml` minimal — the default style is a
  coordination win and every override costs new contributors
  (`references/build.md` RS-BUILD-27).

### Public surface

- **RS-CORE-06 `[M]`** Everything is private until proven public. `pub` is a promise of support;
  `pub(crate)` costs nothing (`references/api.md` RS-API-01).
- **RS-CORE-07 `[M]`** Be generic in what you accept, concrete in what you return. Take `&[T]` not
  `&Vec<T>`, `&str` not `&String`, `&Path` not `&PathBuf` — the borrowed form accepts strictly more
  callers at no cost, and clippy's `ptr_arg` flags the owned forms. This is the single most common
  signature defect in Rust (`references/api.md` RS-API-07).
- **RS-CORE-08 `[M]`** Every struct field is private, whether or not it carries an invariant, and
  the type exposes methods rather than storage. The one exception is a `#[repr(C)]` type whose
  layout is already the contract (`references/api.md` RS-API-15, RS-API-16).
- **RS-CORE-09 `[M]`** Make illegal states unrepresentable. `bool` parameters are enums that have
  not been written yet; two `Option` fields where exactly one is always `Some` is an enum in
  disguise; a `&str` that accepts three values is an enum
  (`references/api.md` RS-API-19, RS-API-21, RS-API-22).
- **RS-CORE-10 `[M]`** Every public type implements `Debug`, and every public item has a summary
  line, with an example that compiles on every non-trivial one. `missing_docs` is a deny, not a warn
  (`references/api.md` RS-API-36, `references/documentation.md` RS-DOC-06).
- **RS-CORE-11 `[M!]`** `#[non_exhaustive]` on a public enum whose variant set may grow, and on a
  struct whose fields are public, so an addition is a minor version rather than a major one. A
  genuinely closed enum stays exhaustive. *Relaxed form:* internal crates within one workspace may
  omit it (`references/api.md` RS-API-54).

### Errors and panics

- **RS-CORE-12 `[M!]`** No `unwrap()`, `expect()`, `panic!`, `todo!`, `unimplemented!`, or fallible
  indexing on a recoverable path. Each one converts a handleable failure in your crate into a
  process abort in someone else's server. *Relaxed form:* `unwrap` and `expect` are allowed in
  tests; a binary, `build.rs` or example that wants `expect` on a genuine invariant relaxes
  `expect_used` in its own `[lints]`, and the message states the invariant rather than the symptom
  (`references/errors.md` RS-ERR-03, RS-ERR-04).
- **RS-CORE-13 `[M]`** Errors are types, not strings. A library defines an enum with one variant per
  failure mode a caller might branch on, implements `Error` with a correct `source()`, and never
  exposes `Box<dyn Error>` or `anyhow::Error` in its public API. `anyhow` belongs in binaries
  (`references/errors.md` RS-ERR-05, RS-ERR-10, RS-ERR-13).
- **RS-CORE-14 `[M]`** Never discard an error's information. `map_err(|_| MyError::Io)` throws away
  the operating system's message; carry the source (`references/errors.md` RS-ERR-08).
- **RS-CORE-15 `[M]`** A panic means a bug, and a reachable one must be documented in a `# Panics`
  section stating the exact condition. An undocumented panic is an undocumented API contract
  (`references/errors.md` RS-ERR-01, `references/documentation.md` RS-DOC-11).

### Function bodies

- **RS-CORE-16 `[M]`** Everything that can be an expression is one. `if`, `match`, `loop`, and
  blocks produce values; a declared-then-assigned binding is a mutable slot in disguise
  (`references/functional.md` RS-FUNC-01).
- **RS-CORE-17 `[S]`** A `for` loop that only pushes into a `Vec` declared just above it is a
  `map`/`filter`/`collect`; one that only accumulates a scalar is a `fold`, `sum`, or `count`; one
  that searches and breaks is `find`, `position`, `any`, or `all`. Keep `for` for side effects, for
  `?` over several error types, and for labelled control flow
  (`references/functional.md` RS-FUNC-03 … RS-FUNC-06).
- **RS-CORE-18 `[S]`** Each `let mut` is a proof obligation: state why no fold, `collect`, `scan`,
  or shadowing expresses this. Reach for shadowing before mutation
  (`references/functional.md` RS-FUNC-22, RS-FUNC-23).
- **RS-CORE-19 `[M]`** Parse, don't validate. Convert untrusted input into a type that cannot be
  invalid at the boundary, and let every downstream function take the parsed type
  (`references/functional.md` RS-FUNC-37).
- **RS-CORE-20 `[M]`** Separate computing from doing: parse and read at the entry, compute over
  plain data in the middle, write and log at the exit. A function that both derives a value and
  writes it somewhere is two functions (`references/functional.md` RS-FUNC-36).

### Ownership

- **RS-CORE-21 `[M]`** Never `.clone()` to silence the borrow checker. Try, in order: shortening the
  borrow, splitting it by destructuring `self`, giving the data one owner, using an index or handle
  — and only then cloning, with a comment saying why
  (`references/ownership.md` RS-OWN-06, RS-OWN-08).
- **RS-CORE-22 `[M]`** Do not put a lifetime parameter on a struct unless the borrow is essential to
  what the type is. Lifetimes propagate into every user's code; owning the data, or indexing into an
  arena, usually costs less than the ergonomic tax
  (`references/ownership.md` RS-OWN-04, RS-OWN-21).
- **RS-CORE-23 `[M]`** Interior mutability is a deliberate escape hatch. Every `Cell`, `RefCell`,
  `Mutex`, or `OnceLock` gets a comment saying why the mutation cannot be threaded through
  `&mut self` instead (`references/ownership.md` RS-OWN-24).

### Abstraction

- **RS-CORE-24 `[M]`** Name the capability as a trait before writing the type that provides it, and
  program against the trait. A boundary designed first stays total and symmetric; one extracted
  later is shaped by whichever implementation came first. The cost is indirection and a generic
  parameter at each use site, which is the trade this standard accepts against the Rust API
  Guidelines' advice (`references/traits.md` RS-TRAIT-01).
- **RS-CORE-25 `[M]`** For a closed set of implementations, an enum beats a trait object: no
  allocation, no vtable, exhaustive matching, and derives for free. Reach for `dyn` when the set is
  genuinely open (`references/traits.md` RS-TRAIT-18).
- **RS-CORE-26 `[S]`** Prefer composition to supertrait hierarchies. A struct holding a `Matcher`
  and a `Printer` is easier to reason about than a five-level supertrait chain
  (`references/traits.md` RS-TRAIT-06).

### Unsafe and dependencies

- **RS-CORE-27 `[M]`** `unsafe_code = "forbid"` in `[lints.rust]` unless `unsafe` is the point of
  the crate. Where it is required, confine it to one module behind a safe API, give every block a
  `// SAFETY:` comment stating why the precondition holds *here*, and run Miri in CI
  (`references/unsafe.md` RS-UNSAFE-01, RS-UNSAFE-02, RS-UNSAFE-03, RS-UNSAFE-30).
- **RS-CORE-28 `[M]`** Every dependency must be justified by something it does that would take
  meaningfully more than an hour to write and maintain. A crate for three lines of `std` is a
  supply-chain liability, a compile-time cost, and a semver risk — for nothing
  (`references/build.md` RS-BUILD-19).

## 5. Review checklist

When reviewing or self-reviewing a Rust diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **Soundness.** Does every `// SAFETY:` comment state a real precondition that holds at that
   point? Any manual `Send`/`Sync`, `transmute`, or raw pointer?
2. **Panics and error handling.** Any `unwrap`, `expect`, `panic!`, fallible indexing, unchecked
   arithmetic or truncating `as` on a path reachable from input? Every error handled or propagated,
   never both?
3. **Public API.** What is newly `pub`? Documented, with `# Errors` and `# Panics`? Does it leak a
   dependency's types? Would `cargo semver-checks` complain?
4. **Concurrency.** A lock held across an `.await` or a blocking call? Lock order documented? An
   unbounded channel, a detached task, no shutdown path?
5. **Data model.** Are illegal states representable — `bool` parameters, paired `Option`s,
   stringly-typed fields?
6. **Function bodies.** Loops that are pipelines, `mut` that folds away, clones a borrow would
   remove, allocation inside a loop?
7. **Tests.** Does the change ship the test that would have caught the bug, matching the error
   variant rather than its `Display` string?
8. **Symmetry.** Does every new operation have its inverse, siblings the same argument order, and
   sibling error variants the same context?
9. **Manifest and lints.** New dependencies justified? Features additive and `dep:`-scoped? Lints
   still enforced, and the MSRV still true?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 28
`RS-CORE-*` rules live in section 4 above; the other 605 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `RS-NAME` (35) | Casing, conversion prefixes (`as_`/`to_`/`into_`), getters, predicates, iterator names, word order, generic parameters and lifetimes |
| `references/api.md` | `RS-API` (62) | Public surface shape, parameters and returns, encapsulation, type safety and newtypes, `#[must_use]`/`#[non_exhaustive]`, the std trait impl set, constructors and builders, semver evolution |
| `references/errors.md` | `RS-ERR` (37) | Error enum design, `thiserror` vs `anyhow`, `source()` chains, context, `?` discipline, panics, explicit overflow, exit codes, `BrokenPipe` |
| `references/functional.md` | `RS-FUNC` (47) | Expression orientation, the iterator adapter set, immutability and shadowing, closures and bounds, purity, parse-don't-validate, when to stop |
| `references/ownership.md` | `RS-OWN` (39) | Borrow-vs-own signatures, clone discipline, `Cow`, lifetimes and elision, arenas and indices, smart pointers, interior mutability, `Drop` and RAII |
| `references/traits.md` | `RS-TRAIT` (47) | Trait design and contracts, static vs dynamic dispatch, dyn compatibility, coherence and blanket impls, sealing, bounds, associated types, GATs, const generics, typestate |
| `references/modules.md` | `RS-MOD` (47) | Module boundaries, `foo.rs` + `foo/`, visibility escalation, the library/binary split, workspace layout and facades, imports and in-file declaration order |
| `references/build.md` | `RS-BUILD` (46) | Manifest and metadata, docs.rs, additive features, dependency discipline, the `[lints]` table, supply chain and semver, toolchain, profiles, CI |
| `references/testing.md` | `RS-TEST` (34) | Unit/integration/doc test split, table-driven tests, property and differential testing, fuzzing, snapshots, CLI end-to-end, flakes |
| `references/documentation.md` | `RS-DOC` (34) | Crate and module docs, the section order, `# Errors`/`# Panics`/`# Safety`, prose style, intra-doc links, README |
| `references/performance.md` | `RS-PERF` (39) | Measure-first discipline, allocation and buffer reuse, collection choice and layout, buffered I/O and syscalls, monomorphization and `#[inline]`, integer widths and casts, SIMD, benchmarking |
| `references/concurrency.md` | `RS-CONC` (47) | Choosing a model, scoped threads and channels, shared state and lock discipline, async fundamentals and cancellation safety, `rayon`, `loom` and determinism |
| `references/unsafe.md` | `RS-UNSAFE` (33) | `// SAFETY:` discipline, the UB list, layout and `repr`, `PhantomData` and variance, `unsafe trait`, C interop and `catch_unwind`, Miri and sanitizers |
| `references/cli.md` | `RS-CLI` (33) | The `LowArgs`→`HiArgs` two-stage model, the flag table, streams and colour, `BrokenPipe`, signals, config precedence |
| `references/migration.md` | `RS-MIG` (3) | The crates std replaced, the APIs deprecated through 1.99, when each API the rules prescribe arrived, what changed silently by release, and the rename table |
| `references/macros.md` | `RS-MACRO` (22) | When not to write a macro, `macro_rules!` hygiene and fragment specifiers, proc-macro crate split, spans and diagnostics, `trybuild` |
| `references/review-checklist.md` | — | The audit protocol: the shared seven-level severity model, review order, mechanical greps, output format, and the order in which to refactor an existing codebase |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/Cargo.toml` | Workspace manifest with the canonical `[workspace.lints]` block (correct `priority = -1` on groups), profiles, and shared dependencies |
| `assets/clippy.toml` | clippy's own settings: lints on public items no longer muted by `avoid-breaking-exported-api`, `unwrap` and `expect` allowed inside tests, and acronyms capitalised as words everywhere |
| `assets/rustfmt.toml` | The two overrides worth having, with the stability caveat |
| `assets/ci.yml` | GitHub Actions enforcing this standard: clippy with `CARGO_BUILD_WARNINGS=deny`, the feature matrix, three platforms, MSRV, rustdoc, audit, `cargo semver-checks` |
| `assets/rust-toolchain.toml` | The pinned stable toolchain every contributor and CI job builds with |
