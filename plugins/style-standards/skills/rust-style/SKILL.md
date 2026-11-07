---
name: rust-style
description: >-
  Use when writing, reviewing, refactoring, scaffolding or debugging any Rust, auditing a Rust
  codebase, choosing between design alternatives, or moving code to edition 2024 or a newer
  toolchain, even when no one asks for "style", "idiomatic" or "production-grade" code. Applies to a
  crate, a function, a trait, an async task, an `unsafe` block, a CLI, `Cargo.toml`, `clippy.toml`,
  `rustfmt.toml` and a CI workflow. Targets Rust 1.99.
---

# Rust Style — 1.99

A single standard formed from three sources: the **Rust API Guidelines** (the public surface,
naming, trait impls), the **empirical conventions of ripgrep and the BurntSushi crates** (crate
architecture, disciplined performance, CLI shape), and a **functional-first default** for function
bodies. Where they disagree, this standard picks a side and says why.

**Target: Rust 1.99 stable, edition 2024.** The bar is not "compiles and passes clippy". It is: a
reviewer who maintains `regex`, `ignore`, or `tokio` would merge this without comment.

## How to use this standard

1. **Read section 2** before emitting Rust code. It is the Rust 1.99 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID: `RS-`, then the family of the chapter that owns the rule, then its number.
Section 6 maps each family to its chapter, so cite the ID when justifying a change and the reader
can find the full rule and its rationale. When two rules appear to conflict, sections 1 and 3 govern
how to break the tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered, the migration
chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Rust 1.99, edition 2024, and any test it ships passes. `// fragment` — shown in
context rather than run as a unit, usually because it uses names the chapter declares around it.
`// rejected — <tool>: …` — the rejection is the point, and the marker names the tool that rejects
it: `rustc`, `clippy`, `rustdoc`. A trailing `— GOOD` or `— BAD` names which side of the rule the
block illustrates. A block in another language carries its marker in that language's comment syntax.

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

### 2.1 Compiles, and behaves differently

| Old | Rust 1.99 | Rule |
|---|---|---|
| `$e:expr` | matches `_` and `const { … }` as well, so a later `_` arm stops firing; `expr_2021` keeps the old fragment | RS-MACRO-09 |
| `-> impl Trait` | captures every lifetime in scope, so a caller can fail to borrow; narrow it with `+ use<'a, T>` | RS-OWN-21 |
| `Box<[T]>::into_iter` | yields `T`, by value, where it yielded `&T` | RS-BUILD-01 |
| `if let` | a temporary in the scrutinee drops before the `else` block, which shortens a lock guard's life | RS-BUILD-01 |
| `RangeInclusive` | once exhausted, reports a different `start()` and `end()`, and slices differently | RS-MIG-03 |

A `changed` row of an earlier release is in the migration table, `RS-MIG` in section 6, with its
Since; its owning rule's Check finds it.

### 2.2 No longer compiles

| Old | Rust 1.99 | Rule |
|---|---|---|
| `#[no_mangle]` | `#[unsafe(no_mangle)]`; `#[export_name]` and `#[link_section]` likewise | RS-BUILD-01 |
| `env::remove_var` | an `unsafe fn`, so a call outside `unsafe` is rejected, and `unsafe_code = "forbid"` rejects one inside; pass the code under test a lookup | RS-TEST-16 |
| `env::set_var` | an `unsafe fn`, so a call outside `unsafe` is rejected, and `unsafe_code = "forbid"` rejects one inside; pass the code under test a lookup | RS-TEST-16 |
| `extern "C" { … }` | rejected; `unsafe extern "C" { … }`, where an item marked `safe fn` is called without `unsafe` | RS-UNSAFE-23 |
| `gen` | a reserved keyword, so rejected as a name; `r#gen` where the name must stay | RS-BUILD-01 |

A `gone` row of an earlier release is in the migration table, `RS-MIG` in section 6, with its Since;
the `rg` command after that table finds every `gone` and `alias` spelling the code writes out but a
shape, whatever its release, and the type checker every `gone` member the code reaches through a
value.

### 2.3 What Rust 1.99 gained

- `LazyLock` and `OnceLock`, in place of `lazy_static` and `once_cell` (RS-CONC-27).
- `cfg_select!`, in place of `cfg-if` (RS-MOD-08).
- `assert_matches!`, in place of `assert!(matches!(..))` and the `assert_matches` crate
  (RS-TEST-13).
- `File::lock`, `try_lock` and `lock_shared`, in place of `fs2` and its forks; `fs::set_times`, in
  place of `filetime` (RS-MIG-01).
- `async fn` in traits, in place of `#[async_trait]` wherever no trait object is needed
  (RS-CONC-31).
- `Atomic*::update` and `try_update`, in place of a `compare_exchange` loop and `fetch_update`
  (RS-CONC-25).

## 3. Design principles

Elegance in Rust has two axes, and a design needs both. **Subtraction** removes what does not earn
its place: a `mut` that a fold would remove, a `String` that a `&str` would remove, a `clone()` that
a borrow would remove, an `Arc<Mutex<_>>` that a channel would remove, a builder that a `Default`
options struct would remove. **Symmetry** is what remains after subtraction being *regular*:
operations that come in pairs, siblings that take their arguments in the same order, one mechanism
per concept, and no branch that exists for a single input.

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
   restriction the documentation must state, or an oversight (RS-API-55 … RS-API-58).
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general case, or name it as its own type (RS-MOD-36, RS-MOD-37).

Readability outranks all five. A combinator chain that requires the reader to track three type
transformations is worse than the `match` it replaced (RS-FUNC-41), and a symmetry nobody can see is
not worth the name it costs.

## 4. Core rules

- **Naming: Casing, Conversions, Word Order, and Generics**
  - RS-NAME-01 [M] Capitalize acronyms as ordinary English words
  - RS-NAME-11 [M] `as_` is a free borrowed view
  - RS-NAME-15 [M] Getters omit `get_`
  - RS-NAME-25 [M] Spell names out; abbreviate only where the abbreviation is the standard word
- **API: The Public Surface, Signatures, Invariants, and Evolution**
  - RS-API-01 [M] Keep everything private until proven public
  - RS-API-15 [M] Be generic in what you accept, concrete in what you return
  - RS-API-20 [M] Keep every field of a published struct private, including the ones with no invariant
  - RS-API-21 [M] Give the caller the question it is asking, not the field it would have read
  - RS-API-23 [M] Replace a `bool` parameter: split the function, or name the flag
  - RS-API-25 [M] Do not build stringly-typed APIs
  - RS-API-35 [M] Implement `Debug` on every public type
  - RS-API-51 [M] Decide `#[non_exhaustive]` for every published enum and struct
- **Errors: `Result`, Panics, and Exit Codes**
  - RS-ERR-01 [M] Split failures into recoverable, caller-bug, and self-bug
  - RS-ERR-03 [M!] No `unwrap`, `expect`, or `panic!` on a recoverable path
  - RS-ERR-04 [M] Make an `expect` message state the invariant, not the symptom
  - RS-ERR-05 [M] Implement `Error` with a correct `source()`
  - RS-ERR-08 [M] Never throw away an error's information
  - RS-ERR-10 [M] Define one error enum per library, one variant per branchable failure
  - RS-ERR-13 [M] Never expose a catch-all error from a library
  - RS-ERR-15 [S] Prefer a struct with a private `kind` to a single-variant enum
- **Functional: Expressions, Iterators, Immutability, and Purity**
  - RS-FUNC-01 [M] Make everything that can be an expression one
  - RS-FUNC-02 [S] A `for` loop that only pushes is a `collect`
  - RS-FUNC-03 [S] A `for` loop that only accumulates a scalar is a fold
  - RS-FUNC-04 [S] A `for` loop that searches and breaks is `find`, `any`, or `position`
  - RS-FUNC-05 [S] Keep `for` for the three things it is actually better at
  - RS-FUNC-21 [S] Treat every `let mut` as a proof obligation
  - RS-FUNC-22 [S] Prefer shadowing to mutation for stepwise refinement
  - RS-FUNC-35 [M] Separate computing from doing, and push the doing to the edges
  - RS-FUNC-36 [M] Parse, don't validate
- **Ownership: Borrowing, Lifetimes, and Resources**
  - RS-OWN-04 [M] Do not put a lifetime on a struct unless the borrow is the point
  - RS-OWN-06 [M] Split borrows by destructuring instead of fighting them
  - RS-OWN-08 [M] Never clone to silence the borrow checker
  - RS-OWN-23 [M] Justify every use of interior mutability in a comment
- **Traits: Generics, Dispatch, and Type-Level Design**
  - RS-TRAIT-05 [S] Prefer composition to supertrait hierarchies
- **Build: Manifest, Features, Dependencies, Lints, Toolchain, and CI**
  - RS-BUILD-18 [M] Justify every dependency by more than an hour of saved work
  - RS-BUILD-26 [M] Enforce `cargo fmt --check` in CI and keep `rustfmt.toml` minimal
- **Documentation: Rustdoc, Sections, Examples, and the README**
  - RS-DOC-06 [M] Give every non-trivial public item an example that runs as a test
  - RS-DOC-10 [M] Give every panicking function a `# Panics` section
- **Unsafe: Soundness, Undefined Behaviour, Layout, and FFI**
  - RS-UNSAFE-01 [M] Forbid `unsafe` unless it is the crate's point, and justify each use
  - RS-UNSAFE-02 [M] Confine `unsafe` to the smallest module behind a safe API
  - RS-UNSAFE-03 [M] Give every `unsafe` block a `// SAFETY:` comment that says why it holds *here*
  - RS-UNSAFE-30 [M] Run the suite under Miri before every release of a crate with `unsafe`
- **Data**
  - RS-DATA-01 [M] Model a finite set of states as an enum that lists all of them
  - RS-DATA-04 [S] Prefer indices to references for graph-shaped data
  - RS-DATA-05 [M] Make a bad value unrepresentable, else rejected at construction, else checked
- **Types**
  - RS-TYPE-01 [M] Name the capability as a trait before writing the type that provides it
  - RS-TYPE-02 [M] Model a closed set of implementations as an enum, not a trait object

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
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. All
593 rules live here; section 4 lists by ID those that bind on their own.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `RS-NAME` (34) | Casing, conversion prefixes (`as_`/`to_`/`into_`), getters, predicates, iterator names, word order, generic parameters and lifetimes |
| `references/api.md` | `RS-API` (59) | Public surface shape and visibility, parameters and returns, encapsulation, type safety, `#[must_use]`/`#[non_exhaustive]`, the std trait impl set, constructors and builders, semver evolution |
| `references/errors.md` | `RS-ERR` (36) | Error enum design, `thiserror` vs `anyhow`, `source()` chains, context, `?` discipline, panics, exit codes |
| `references/functional.md` | `RS-FUNC` (45) | Expression orientation, the iterator adapter set, immutability and shadowing, closures and bounds, purity, parse-don't-validate, when to stop |
| `references/ownership.md` | `RS-OWN` (36) | Borrow-vs-own signatures, clone discipline, `Cow`, lifetimes and elision, arenas, smart pointers, interior mutability, `Drop` and RAII |
| `references/traits.md` | `RS-TRAIT` (42) | Trait design and contracts, static vs dynamic dispatch, dyn compatibility, coherence and blanket impls, sealing, bounds, associated types, GATs, const generics, typestate |
| `references/modules.md` | `RS-MOD` (38) | Module boundaries and crate names, `foo.rs` + `foo/`, the library/binary split, workspace layout and facades, imports and in-file declaration order |
| `references/build.md` | `RS-BUILD` (46) | Manifest and metadata, docs.rs, additive features, dependency discipline, the `[lints]` table, supply chain and semver, toolchain, profiles, CI |
| `references/testing.md` | `RS-TEST` (35) | Unit/integration/doc test split, table-driven tests, property and differential testing, fuzzing, snapshots, CLI end-to-end, flakes |
| `references/documentation.md` | `RS-DOC` (35) | Crate and module docs, the section order, `# Errors`/`# Panics`/`# Safety`, prose style, the changelog, intra-doc links, README |
| `references/performance.md` | `RS-PERF` (38) | Measure-first discipline, allocation and buffer reuse, collection choice and layout, buffered I/O and syscalls, monomorphization and `#[inline]`, SIMD, benchmarking |
| `references/concurrency.md` | `RS-CONC` (46) | Choosing a model, scoped threads and channels, shared state and lock discipline, async fundamentals and cancellation safety, `rayon`, `loom` and determinism |
| `references/unsafe.md` | `RS-UNSAFE` (33) | `// SAFETY:` discipline, the UB list, layout and `repr`, `PhantomData` and variance, `unsafe trait`, C interop and `catch_unwind`, Miri and sanitizers |
| `references/cli.md` | `RS-CLI` (31) | The `LowArgs`→`HiArgs` two-stage model, the flag table, streams and colour, `BrokenPipe`, signals, config precedence |
| `references/data.md` | `RS-DATA` (10) | Enums and sum types, records over tuples, indices over references, unrepresentable and rejected values, views over containers, equality and hashing, integer widths and explicit overflow |
| `references/types.md` | `RS-TYPE` (4) | The capability named as a trait before the type that provides it, a closed set kept an enum, a trait's contract written down, and how far a parameter is generic |
| `references/migration.md` | `RS-MIG` (3) | Every old spelling the 2024 edition and the releases through 1.99 left behind, with its status and owning rule; the command the table generates; when each API arrived; and what changed silently by release |
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
| `assets/rustfmt.toml` | The two import overrides worth having; both are nightly-only, so it is formatted with `cargo +nightly fmt` |
| `assets/ci.yml` | GitHub Actions enforcing this standard: clippy with `CARGO_BUILD_WARNINGS=deny`, each member under each feature alone, three platforms, MSRV, beta, rustdoc, audit, `cargo semver-checks`, read-only token permissions |
| `assets/rust-toolchain.toml` | The pinned stable toolchain every contributor and CI job builds with |
