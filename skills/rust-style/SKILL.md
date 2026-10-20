---
name: rust-style
description: >-
  The modern Rust engineering standard — a 769-rule library merging the Rust API Guidelines, the
  empirical conventions of ripgrep and the BurntSushi crates, and a functional-first default.
  Covers naming, API design, errors and panics, iterator and combinator style, ownership and
  lifetimes, traits and generics, module and workspace layout, Cargo/features/lints/CI, testing
  and fuzzing, rustdoc, performance, concurrency and async, unsafe and FFI, ripgrep-grade CLI
  architecture, macros, and API symmetry. Use this whenever writing, reviewing, refactoring, scaffolding, or
  debugging ANY Rust — a whole crate, one function, a `Cargo.toml`, an error enum, a trait
  boundary, an async task, an `unsafe` block, a CLI — even if the user never mentions "style",
  "standards", or "quality". Also use when asked to make Rust "idiomatic", "modern", "clean",
  "elegant", "production-grade", or "functional", when auditing a Rust codebase, and when
  choosing between Rust design alternatives.
---

# Rust Style — edition 2024

A single standard formed from three sources: the **Rust API Guidelines** (the public surface,
naming, trait impls), the **empirical conventions of ripgrep and the BurntSushi crates** (crate
architecture, disciplined performance, CLI shape), and a **functional-first default** for function
bodies. Where they disagree, this standard picks a side and says why.

**Target: edition 2024 on the latest stable Rust.** The bar is not "compiles and passes clippy". It
is: a reviewer who maintains `regex`, `ignore`, or `tokio` would merge this without comment.

## How to use this standard

1. **Read section 2** before emitting Rust. It is the edition-2024 reality check, and several of its
   entries silently change behaviour rather than producing a compile error.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID — `RS-FP-04`, `RS-API-12`. The prefix identifies the owning chapter (section 6
maps prefix to file), so cite the ID when justifying a change and the reader can find the full rule
and its rationale. When a rule in a chapter and a rule here appear to conflict, the chapter is the
detailed statement and wins; sections 1 and 3 govern how to break a genuine tie.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against edition 2024 on the latest stable Rust, and any test it ships passes.
`// fragment` — shown in context rather than compiled as a unit, usually because it uses names the
chapter declares around it. `// does-not-compile` — the compile error is the point. A trailing
`— GOOD` or `— BAD` names which side of the rule the block illustrates. A block in another language
carries its marker in that language's comment syntax.

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

## 2. Edition 2024 reality check — read before writing code

Most Rust on the public internet predates these. The entries that **compile either way** are the
dangerous ones, because nothing catches them for you.

### 2.1 What the 2024 edition changed underneath you

| Old habit | Edition 2024 reality |
|---|---|
| `unsafe fn` body is implicitly unsafe | `unsafe_op_in_unsafe_fn` is on; write the inner `unsafe { }` explicitly |
| `#[no_mangle]`, `#[export_name]`, `#[link_section]` | must be `#[unsafe(no_mangle)]` and friends |
| `static mut FOO` then `&FOO` | `static_mut_refs` denies it; use `OnceLock`/`LazyLock`/atomics |
| `impl Trait` return captures only named lifetimes | captures **all** in-scope lifetimes; narrow with `+ use<'a, T>` (1.82) |
| `if let` temporary dropped at end of statement | dropped at end of the `if let`, which changes lock scopes |
| tail-expression temporaries live to end of block | shortened; a temporary can now drop earlier than it used to |
| `gen` usable as an identifier | reserved keyword |

### 2.2 Standard-library features that replaced ecosystem crates

| Reach for this | Not this | Since |
|---|---|---|
| `OnceLock`, `LazyLock` | `lazy_static`, `once_cell` for the common cases | 1.70 / 1.80 |
| `core::error::Error` | `std`-only error traits in no-std crates | 1.81 |
| `#[expect(lint, reason = "…")]` | `#[allow]` that nobody ever removes | 1.81 |
| `[lints]` in `Cargo.toml` | a wall of `#![deny(...)]` in `lib.rs` | 1.74 |
| `thread::scope` | `Arc` + `'static` gymnastics for borrowing threads | 1.63 |
| `async fn` / `impl Trait` in traits | `#[async_trait]` for the non-`dyn` cases | 1.75 |
| let-chains: `if let Some(x) = a && x > 3` | nested `if let` pyramids (edition 2024 only) | 1.88 |
| `let ... else` | `match` with a `_ => return` arm | 1.65 |
| `c"…"` C string literals | manual NUL-terminated byte arrays | 1.77 |
| `CARGO_BUILD_WARNINGS=deny` | `RUSTFLAGS="-Dwarnings"`, which invalidates the build cache | recent |

### 2.3 The three that change behaviour silently

1. **Integer overflow panics in debug and wraps in release.** Arithmetic on attacker-influenced
   values must be `checked_*` / `saturating_*` / `wrapping_*` explicitly, or debug and release
   disagree about what your program does (`RS-PRF-40`).
2. **`as` casts truncate without a diagnostic.** `len as u32` on a 5 GB buffer is a silent wrong
   answer. Use `u32::try_from(len)?` on any conversion that can lose data (`RS-PRF-41`).
3. **A dropped `Future` is a cancellation at an arbitrary `.await`.** Anything holding a resource
   across an await must be correct when dropped there; `select!` makes this routine rather than
   exotic (`RS-CNC-37`).

Also recent: symbol mangling v0 is the default, and `linker_messages` is a default-on warning that
is deliberately **not** part of the `warnings` group — read it rather than silencing it
(`RS-CAR-33`).

## 3. Design principles — subtraction and symmetry

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
   restriction the documentation must state, or an oversight (`RS-API-79` … `RS-API-82`).
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general case, or name it as its own type (`RS-STR-54`,
   `RS-STR-55`).

Readability outranks all five. A combinator chain that requires the reader to track three type
transformations is worse than the `match` it replaced (`RS-FP-58`), and a symmetry nobody can see is
not worth the name it costs.

## 4. Core rules

These 28 `RS-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### Names

- **RS-CORE-01 `[M]`** `UpperCamelCase` types, traits, and variants; `snake_case` functions,
  modules, and locals; `SCREAMING_SNAKE_CASE` constants. Acronyms are ordinary words —
  `HttpClient`, `Uuid`, `OsStr`, never `HTTPClient`. See `references/naming.md` RS-NAM-01.
- **RS-CORE-02 `[M]`** Conversion prefixes carry cost information and are not interchangeable:
  `as_` is a free borrowed view, `to_` allocates or computes, `into_` consumes the receiver. A
  method named `as_*` that allocates is misnamed (`references/naming.md` RS-NAM-13).
- **RS-CORE-03 `[M]`** Getters omit `get_`: `len()`, `name()`, `config()`. `get_` is reserved for
  the fallible `Index`-like lookup returning `Option`/`Result`
  (`references/naming.md` RS-NAM-17).
- **RS-CORE-04 `[S]`** No abbreviations unless the abbreviation is more standard than the word
  (`config`, `regex`, `buf`, `ctx`). `rslt`, `mngr`, `hdlr` are not
  (`references/naming.md` RS-NAM-28).
- **RS-CORE-05 `[M]`** Run `cargo fmt`. Keep `rustfmt.toml` minimal — the default style is a
  coordination win and every override costs new contributors
  (`references/cargo-toolchain.md` RS-CAR-34).

### Public surface

- **RS-CORE-06 `[M]`** Everything is private until proven public. `pub` is a promise of support;
  `pub(crate)` costs nothing (`references/api-design.md` RS-API-01).
- **RS-CORE-07 `[M]`** Be generic in what you accept, concrete in what you return. Take `&[T]` not
  `&Vec<T>`, `&str` not `&String`, `&Path` not `&PathBuf` — the borrowed form accepts strictly more
  callers at no cost. This is the single most common signature defect in Rust
  (`references/api-design.md` RS-API-10, RS-API-12).
- **RS-CORE-08 `[M]`** Every struct field is private, whether or not it carries an invariant, and
  the type exposes methods rather than storage. The one exception is a `#[repr(C)]` type whose
  layout is already the contract (`references/api-design.md` RS-API-24, RS-API-19).
- **RS-CORE-09 `[M]`** Make illegal states unrepresentable. `bool` parameters are enums that have
  not been written yet; two `Option` fields where exactly one is always `Some` is an enum in
  disguise; a `&str` that accepts three values is an enum
  (`references/api-design.md` RS-API-30, RS-API-32, RS-API-33).
- **RS-CORE-10 `[M]`** Every public type implements `Debug`, and every public item is documented
  with a summary line plus an example that compiles. `missing_docs` is a deny, not a warn
  (`references/api-design.md` RS-API-51, `references/documentation.md` RS-DOC-01).
- **RS-CORE-11 `[M!]`** `#[non_exhaustive]` on public enums and structs whose shape may grow, so an
  addition is a minor version rather than a major one. *Relaxed form:* omit it on a genuinely closed
  enum, where it only costs the caller exhaustiveness checking
  (`references/api-design.md` RS-API-71, RS-API-72).

### Errors and panics

- **RS-CORE-12 `[M!]`** No `unwrap()`, `expect()`, `panic!`, `todo!`, `unimplemented!`, or fallible
  indexing on a recoverable path. Each one converts a handleable failure in your crate into a
  process abort in someone else's server. *Relaxed form:* in tests, `build.rs`, and binaries,
  `expect` is permitted where the condition is a genuine invariant, and the message states the
  invariant rather than the symptom (`references/errors.md` RS-ERR-03, RS-ERR-04).
- **RS-CORE-13 `[M]`** Errors are types, not strings. A library defines an enum with one variant per
  failure mode a caller might branch on, implements `Error` with a correct `source()`, and never
  exposes `Box<dyn Error>` or `anyhow::Error` in its public API. `anyhow` belongs in binaries
  (`references/errors.md` RS-ERR-06, RS-ERR-11, RS-ERR-14).
- **RS-CORE-14 `[M]`** Never discard an error's information. `map_err(|_| MyError::Io)` throws away
  the operating system's message; carry the source (`references/errors.md` RS-ERR-09).
- **RS-CORE-15 `[M]`** A panic means a bug, and a reachable one must be documented in a `# Panics`
  section stating the exact condition. An undocumented panic is an undocumented API contract
  (`references/errors.md` RS-ERR-35 and RS-ERR-36, `references/documentation.md` RS-DOC-13).

### Function bodies

- **RS-CORE-16 `[M]`** Everything that can be an expression is one. `if`, `match`, `loop`, and
  blocks produce values; a declared-then-assigned binding is a mutable slot in disguise
  (`references/functional.md` RS-FP-01).
- **RS-CORE-17 `[S]`** A `for` loop that only pushes into a `Vec` declared just above it is a
  `map`/`filter`/`collect`; one that only accumulates a scalar is a `fold`, `sum`, or `count`; one
  that searches and breaks is `find`, `position`, `any`, or `all`. Keep `for` for side effects, for
  `?` over several error types, and for labelled control flow
  (`references/functional.md` RS-FP-04 … RS-FP-07).
- **RS-CORE-18 `[S]`** Each `let mut` is a proof obligation: state why no fold, `collect`, `scan`,
  or shadowing expresses this. Reach for shadowing before mutation
  (`references/functional.md` RS-FP-29, RS-FP-30).
- **RS-CORE-19 `[M]`** Parse, don't validate. Convert untrusted input into a type that cannot be
  invalid at the boundary, and let every downstream function take the parsed type
  (`references/functional.md` RS-FP-53).
- **RS-CORE-20 `[S]`** Separate computing from doing: parse and read at the entry, compute over
  plain data in the middle, write and log at the exit. A function that both derives a value and
  writes it somewhere is two functions (`references/functional.md` RS-FP-51, RS-FP-52).

### Ownership

- **RS-CORE-21 `[M]`** Never `.clone()` to silence the borrow checker. Try, in order: shortening the
  borrow, splitting it by destructuring `self`, giving the data one owner, using an index or handle
  — and only then cloning, with a comment saying why
  (`references/ownership.md` RS-OWN-10, RS-OWN-12).
- **RS-CORE-22 `[M]`** Do not put a lifetime parameter on a struct unless the borrow is essential to
  what the type is. Lifetimes propagate into every user's code; owning the data, or indexing into an
  arena, usually costs less than the ergonomic tax
  (`references/ownership.md` RS-OWN-05, RS-OWN-27).
- **RS-CORE-23 `[M]`** Interior mutability is a deliberate escape hatch. Every `Cell`, `RefCell`,
  `Mutex`, or `OnceLock` gets a comment saying why the mutation cannot be threaded through
  `&mut self` instead (`references/ownership.md` RS-OWN-30).

### Abstraction

- **RS-CORE-24 `[M]`** Name the capability as a trait before writing the type that provides it, and
  program against the trait. A boundary designed first stays total and symmetric; one extracted
  later is shaped by whichever implementation came first. The cost is indirection and a generic
  parameter at each use site, which is the trade this standard accepts against the Rust API
  Guidelines' advice (`references/traits-generics.md` RS-TRG-01).
- **RS-CORE-25 `[M]`** For a closed set of implementations, an enum beats a trait object: no
  allocation, no vtable, exhaustive matching, and derives for free. Reach for `dyn` when the set is
  genuinely open (`references/traits-generics.md` RS-TRG-22).
- **RS-CORE-26 `[S]`** Prefer composition to supertrait hierarchies. A struct holding a `Matcher`
  and a `Printer` is easier to reason about than a five-level supertrait chain
  (`references/traits-generics.md` RS-TRG-08).

### Unsafe and dependencies

- **RS-CORE-27 `[M]`** `unsafe_code = "forbid"` in `[lints.rust]` unless `unsafe` is the point of
  the crate. Where it is required, confine it to one module behind a safe API, give every block a
  `// SAFETY:` comment stating why the precondition holds *here*, and run Miri in CI
  (`references/unsafe-ffi.md` RS-UNS-02, RS-UNS-03, RS-UNS-30).
- **RS-CORE-28 `[M]`** Every dependency must be justified by something it does that would take
  meaningfully more than an hour to write and maintain. A crate for three lines of `std` is a
  supply-chain liability, a compile-time cost, and a semver risk — for nothing
  (`references/cargo-toolchain.md` RS-CAR-21).

## 5. Review checklist

When reviewing or self-reviewing a Rust diff, walk this list. The full protocol — severity model,
review order, grep commands, output format — is `references/review-checklist.md`.

1. **Soundness.** Every `unsafe` block: does the `// SAFETY:` comment state a real precondition, and
   is it established at that point? Any manual `Send`/`Sync`, `transmute`, or raw pointer?
2. **Panics.** Any `unwrap`, `expect`, `panic!`, `todo!`, fallible indexing, or slicing on a path
   reachable from user input?
3. **Silent numerics.** Any `as` cast that can truncate? Any arithmetic on untrusted values that is
   not `checked_*`/`saturating_*`/`wrapping_*`? Debug and release must agree.
4. **Errors.** Every error handled or propagated, never both? Any `map_err` that discards a source?
   Any `Box<dyn Error>` in a library's public type?
5. **Public surface.** What is newly `pub`? Documented? `# Errors` and `# Panics` present? Does it
   leak a dependency's types? Would `cargo semver-checks` complain?
6. **Signatures.** `&Vec<T>`/`&String`/`&PathBuf` parameters? Owned parameters that only get read?
   Bounds tighter than the body needs? A `'static` that is not earned?
7. **Concurrency.** Lock held across an `.await` or a blocking call? Lock order documented?
   Unbounded channel? Detached task? A defined shutdown path?
8. **Data model.** Are illegal states representable — `bool` parameters, paired `Option`s,
   stringly-typed fields?
9. **Bodies.** Loops that are pipelines, `mut` that folds away, clones a borrow would remove,
   allocation inside a loop, `collect` in the middle of a chain.
10. **Resources.** Every buffered writer flushed and the result checked? `Drop` infallible? A
    `finish()` for cleanup that can fail?
11. **Tests.** Does the change ship with the test that would have caught the bug? Is the error path
    covered by matching the variant rather than its `Display` string?
12. **Symmetry.** Does every new operation have its inverse, or a documented reason it cannot? Do
    sibling functions take their arguments in the same order, and sibling error variants carry the
    same context? Is there a branch that exists for exactly one input (`RS-API-79` … `RS-API-84`,
    `RS-STR-54` … `RS-STR-57`)?
13. **Manifest.** New dependencies justified? Features additive and `dep:`-scoped? Lints still
    enforced? MSRV still true?
14. **Why.** Does every non-obvious decision have a comment recording the reasoning and the
    alternative rejected?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The
28 `RS-CORE-*` rules live in section 4 above; the other 741 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `RS-NAM` (44) | Casing, conversion prefixes (`as_`/`to_`/`into_`), getters, predicates, iterator names, word order, generic parameters and lifetimes |
| `references/api-design.md` | `RS-API` (84) | Public surface shape, parameters and returns, encapsulation, type safety and newtypes, `#[must_use]`/`#[non_exhaustive]`, the std trait impl set, constructors and builders, semver evolution |
| `references/errors.md` | `RS-ERR` (50) | Error enum design, `thiserror` vs `anyhow`, `source()` chains, context, `?` discipline, panics, exit codes, `BrokenPipe` |
| `references/functional.md` | `RS-FP` (64) | Expression orientation, the iterator adapter set, immutability and shadowing, closures and bounds, purity, parse-don't-validate, when to stop |
| `references/ownership.md` | `RS-OWN` (46) | Borrow-vs-own signatures, clone discipline, `Cow`, lifetimes and elision, arenas and indices, smart pointers, interior mutability, `Drop` and RAII |
| `references/traits-generics.md` | `RS-TRG` (56) | Trait design and contracts, static vs dynamic dispatch, dyn compatibility, coherence and blanket impls, sealing, bounds, associated types, GATs, const generics, typestate |
| `references/structure.md` | `RS-STR` (57) | Module boundaries, `foo.rs` + `foo/`, visibility escalation, workspace layout and facades, imports and in-file declaration order |
| `references/cargo-toolchain.md` | `RS-CAR` (54) | Manifest and metadata, additive features, dependency discipline, the `[lints]` table, supply chain and semver, toolchain, profiles, CI |
| `references/testing.md` | `RS-TST` (42) | Unit/integration/doc test split, table-driven tests, property and differential testing, fuzzing, snapshots, CLI end-to-end, Miri and `loom`, flakes |
| `references/documentation.md` | `RS-DOC` (40) | Crate and module docs, the section order, `# Errors`/`# Panics`/`# Safety`, prose style, intra-doc links, docs.rs metadata, README |
| `references/performance.md` | `RS-PRF` (50) | Measure-first discipline, allocation and buffer reuse, collection choice and layout, buffered I/O and syscalls, monomorphization and `#[inline]`, overflow and casts, benchmarking |
| `references/concurrency-async.md` | `RS-CNC` (52) | Choosing a model, scoped threads and channels, shared state and lock discipline, async fundamentals and cancellation safety, `rayon`, `loom` and determinism |
| `references/unsafe-ffi.md` | `RS-UNS` (36) | `// SAFETY:` discipline, the UB list, layout and `repr`, `PhantomData` and variance, `unsafe trait`, C interop and `catch_unwind`, Miri and fuzzing |
| `references/cli-apps.md` | `RS-CLI` (40) | Library/binary split, the `LowArgs`→`HiArgs` two-stage model, the flag table, streams and colour, `BrokenPipe`, signals, config precedence |
| `references/macros.md` | `RS-MAC` (26) | When not to write a macro, `macro_rules!` hygiene and fragment specifiers, proc-macro crate split, spans and diagnostics, `trybuild` |
| `references/review-checklist.md` | — | The audit protocol: six-level severity model, review order, mechanical greps, output format, and the order in which to refactor an existing codebase |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe.

| File | Contents |
|---|---|
| `assets/Cargo.toml` | Workspace manifest with the canonical `[workspace.lints]` block (correct `priority = -1` on groups), profiles, and shared dependencies |
| `assets/clippy.toml` | clippy's own settings: lints on public items no longer muted by `avoid-breaking-exported-api`, `unwrap` and `expect` allowed inside tests, and acronyms capitalised as words everywhere |
| `assets/rustfmt.toml` | The two overrides worth having, with the stability caveat |
| `assets/ci.yml` | GitHub Actions enforcing this standard: clippy with `CARGO_BUILD_WARNINGS=deny`, the feature matrix, three platforms, MSRV, rustdoc, audit, `cargo semver-checks` |
