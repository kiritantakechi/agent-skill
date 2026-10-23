# rust-style: duplicate rules and newer APIs (Rust 1.99, edition 2024)

Read: `SKILL.md` (28 core rules), all 709 chapter rules, the review protocol, `migration.md` and
the `assets/` lint config. Release notes 1.85–1.99.0 from the local `releases.md`; 1.99.1
(2026-10-15) from doc.rust-lang.org. Probes ran on rustc and clippy 1.99.0 with the shipped lint set
(pedantic at warn, the shipped restriction denies, `clippy.toml`), in
`/private/tmp/claude-501/-Users-kiritan-Projects-agent-skill/e256aaa1-d796-4f52-9d69-ba70cd3c0dce/scratchpad/research-rust/`:
`probe/src/modern.rs` holds the replacements (clippy clean, 3 tests pass), `asis/src/as_written.rs`
the examples as written.

## A. Duplicates

### A.1 Duplicate rules, most valuable first

"Tier conflict" means the two rules give the same instruction at different tiers; the owner's tier
wins unless the row says otherwise.

| # | Rules | Owner | Absorb from the other |
|---|---|---|---|
| 1 | OWN-26 / FUNC-33 (justify interior mutability), CORE-23 | OWN-26 | nothing; FUNC-33 goes |
| 2 | OWN-17 / FUNC-32 / PERF-13 (`Box<[T]>`, `Box<str>`, `Arc<[T]>` for finished data) | OWN-17 | FUNC-32: the type invites a push into final data. PERF-13: the footprint at a million values, and its `Box<[Box<str>]>` example |
| 3 | ERR-38 `[M!]` / PERF-36 `[M]` (explicit overflow), tier conflict | ERR-38 | PERF-36's "computed sizes" scope and its grep over lengths, offsets and parsed numbers. Retarget SKILL §2.3 and the review checklist |
| 4 | API-34 `[M]` / NAME-30 `[M!]` (unit in the type), with NAME-10, API-27; tier conflict | API-34; "failing that, in the name" goes to NAME-10 | NAME-30's relaxed form ("never omit both") and its `retry()` fragments |
| 5 | TEST-08 `[M]` / NAME-36 `[S]` (test names as sentences), tier conflict | TEST-08 | nothing; NAME-36 goes |
| 6 | NAME-27 / API-81 (one term, one meaning) | NAME-27 | API-81's `id`/`key`/`handle`, `path`/`file` examples, its "group nouns by referent" Check and its verified example. API-81 mis-cites NAME-42 |
| 7 | BUILD-34 `[M!]` / API-73 `[M]` (`cargo semver-checks`), tier conflict | BUILD-34 | "changed variant shapes" |
| 8 | UNSAFE-20 / TRAIT-14 (`unsafe trait` when unsafe code relies on it) | UNSAFE-20 | TRAIT-14's counter-case (wrong answers only → safe, documented contract) and its Check |
| 9 | UNSAFE-21 / CONC-29 (manual `Send`/`Sync` is a proof obligation) | UNSAFE-21 | "if a type is not `Send`, the compiler is telling you something true". Fix UNSAFE-21's example (defects) |
| 10 | CONC-35 / TRAIT-20 (decide the `Send` story for async traits) | CONC-35 | TRAIT-20's `Pin<Box<dyn Future + Send>>` option and "say which in the rustdoc" |
| 11 | OWN-42 / CLI-33 (install process-wide state once, in `main`) | OWN-42 | nothing; CLI-33 goes |
| 12 | CONC-13 / FUNC-43 (clone before a spawned closure) | CONC-13 | FUNC-43's verified example |
| 13 | OWN-36 / ERR-37 (infallible `Drop`, explicit `finish`) | OWN-36 | ERR-37's Why (a panic while unwinding aborts) and its Check |
| 14 | CLI-21 / PERF-25 (lock stdout once). PERF-25's example has no `BufWriter`, so it still flushes per line | CLI-21; PERF-24 keeps the general case | PERF-25's "a million lock acquisitions" |
| 15 | PERF-26 / CLI-29 (flush and check before exit) | PERF-26 | CLI-29's example |
| 16 | FUNC-12 / PERF-09 (no intermediate collect) | FUNC-12 | the cache-pressure Why |
| 17 | PERF-07 / FUNC-19 / PERF-06 (pre-size when `size_hint` cannot) | PERF-07 | PERF-06's `String`/`HashMap::with_capacity` list. The FUNC-19 and PERF-06 examples pre-size the one case `collect` already sizes exactly |
| 18 | PERF-08 / OWN-14 (hoist the buffer a loop refills), with PERF-11 | PERF-08 | OWN-14's `clear()` + `read_line`/`read_until` pattern and the ripgrep rationale |
| 19 | OWN-13 / PERF-10 / PERF-12 (do not allocate to compare or slice) | OWN-13 | PERF-10's list (`trim`, `strip_prefix`, `split_once`, `find`) and PERF-12's "where is the owned value stored" Check |
| 20 | PERF-20 / ERR-20 / PERF-19 (enum and error size) | PERF-20; PERF-19 keeps struct size only | `large_enum_variant` and `result_large_err` are default lints (B.2) |
| 21 | OWN-02 / API-12 (take by value when you keep it), with API-13 | OWN-02 | API-12's converse (the `needless_pass_by_value` row) and API-13's `impl Into<String>` |
| 22 | OWN-03 / API-15 (return borrows for views) | OWN-03 | API-15's `Cow` reference to OWN-15 |
| 23 | FUNC-18 `[M]` / API-14 `[S]` (keep iterators lazy), with FUNC-55; tier conflict | FUNC-18 | API-14's Check: does the caller immediately `.iter()` or index the first element? |
| 24 | TRAIT-38 / API-10 (genericise only where used) | TRAIT-38 | API-10's three costs |
| 25 | CONC-21 / OWN-33 (three questions before `Arc<Mutex<_>>`) | CONC-21 | nothing; OWN-33 goes |
| 26 | CONC-22 / CONC-18 (hold locks briefly), with CONC-33. CONC-22's statement ends in an orphaned colon | CONC-22 | CONC-18's example and its second-lock deadlock Why |
| 27 | CONC-50 / CONC-38 / CONC-20 (no fire-and-forget) | CONC-50; CONC-12 stays | CONC-20's "detached threads die at exit with no flush", CONC-38's "detach only with a comment" |
| 28 | TEST-37 / UNSAFE-30 / CONC-44 / CONC-45 (Miri, loom, TSan) | UNSAFE-30 (Miri), CONC-44 (loom), CONC-45 (TSan only) | nothing; TEST-37 goes |
| 29 | TEST-25 / UNSAFE-32 (fuzz untrusted parsing) | TEST-25 | "a crash is release-blocking" |
| 30 | TEST-35 / UNSAFE-33 (`compile_fail` doc tests for pin misuse), with UNSAFE-19 | TEST-35 | UNSAFE-33's soundness argument, into UNSAFE-19 |
| 31 | TEST-23 / UNSAFE-10 / PERF-38 (the naive version as oracle), with TEST-22 | TEST-23 | UNSAFE-10 and PERF-38 keep their `[M!]` application as one line |
| 32 | TEST-41 / TEST-19 (delete tests that test nothing) | TEST-41 | TEST-19 becomes its example |
| 33 | PERF-40 / MOD-31 / TEST-31 (benchmarks in `benches/`, built in CI) | PERF-40 | — |
| 34 | MOD-24 / CLI-01 (split the binary from the library) | MOD-24 | CLI-01's `grep-searcher` and "benchmarkable" rationale |
| 35 | CLI-02 / ERR-41 (`main` does four things) | CLI-02, whose list names five | ERR-41's "untested surface" Check. ERR-42 keeps `ExitCode` |
| 36 | TEST-30 / CLI-37 (binary end-to-end, with exit code) | TEST-30 | CLI-37's cases: pipe, not-a-terminal, non-UTF-8 filename |
| 37 | BUILD-08 / MOD-28 (workspace dependencies) | BUILD-08 | "two members pulling different majors" |
| 38 | BUILD-25 / MOD-29 (workspace lints) | BUILD-25 | — |
| 39 | BUILD-10 + BUILD-19 / DOC-33 (docs.rs metadata, `docsrs` cfg) | BUILD-10, BUILD-19 | DOC-33's "find a feature-gated item on docs.rs" Check, into BUILD-19. BUILD-03, DOC-36 and DOC-38 all put the MSRV in the README: merge under DOC-38 |
| 40 | BUILD-20 / TEST-36 (feature matrix) | BUILD-20 | — |
| 41 | BUILD-02 / BUILD-33 (MSRV verified by a pinned job) | BUILD-33 | BUILD-02's "Cargo enforces it against your users" |
| 42 | NAME-07 `[M]` / BUILD-15 `[S]` (features name capabilities), tier conflict | NAME-07 | BUILD-15's Why: swapping the dependency becomes breaking |
| 43 | DOC-04 / BUILD-14 (document each feature and its cost) | DOC-04; BUILD-14 keeps `default = []` | — |
| 44 | DOC-13 / ERR-34 (`# Panics`) | DOC-13 | ERR-34's slicing and `Duration` sources and its `#[track_caller]` reference |
| 45 | UNSAFE-04 / DOC-14 (`# Safety`) | UNSAFE-04 | Conflict: UNSAFE-04 says every `*_unchecked` is `unsafe`; API-68 says "`unsafe` or `*_unchecked`" |
| 46 | ERR-23 / DOC-16 (document the error type once) | ERR-23 | nothing; DOC-16 goes |
| 47 | DOC-08 / TEST-32 (examples are passing doc tests) | DOC-08 | — |
| 48 | DOC-27 / TEST-33 (`?` over `unwrap()` in doc tests) | DOC-27 | TEST-33's hidden `# fn main() -> Result<…>` |
| 49 | MOD-01 / DOC-03 / NAME-06 / MOD-02 (a module is a documented concept; no `utils`) | MOD-01 (boundary), MOD-02 (ban) | DOC-03's "not a restatement of the item list". NAME-06 keeps only "a singular noun" |
| 50 | MOD-48 / MOD-10 (file order) | MOD-48 | — |
| 51 | API-01 / MOD-11 (private until proven public), with MOD-12–14. MOD-11's Check contradicts MOD-12 | API-01; MOD-12–14 keep the ladder | MOD-11's ladder line becomes MOD-12's intro |
| 52 | MOD-22 / API-03 (one crate, one purpose) | MOD-22 | API-03's "no conjunction" Check and its `grep-*` example |
| 53 | MOD-15 / API-02 (the surface is assembled in the root), with MOD-17, MOD-06. API-02's example never uses `pub use` | MOD-15 | API-02's "move the file without a breaking change" |
| 54 | MOD-16 / TEST-06 (never `pub` for a test) | MOD-16 | nothing; TEST-06 goes |
| 55 | API-22 / API-66 (close every path to an invalid instance) | API-22 | API-66's "`From<Options>` that skips validation" Check |
| 56 | API-23 / API-25 (tuple-struct fields private too) | API-23 | the `struct X(pub` grep and the `.0` rationale |
| 57 | API-67 `[S]` / NAME-23 `[M!]` (inherent `from_*` only for several sources), with API-55/56; tier conflict | API-67, promoted to `[M!]` | NAME-23's "would leak a type parameter" exception, its "thin forwarder" Check and the `collect`/`TryInto`/`?` Why |
| 58 | API-45 / API-69 / API-70 / ERR-14 (decide exhaustiveness) | API-69, with API-70 as its relaxed form and API-45 merged in | ERR-14's `Endianness` example |
| 59 | PERF-31 `[M]` / API-48 `[S]` (`#[inline]` across crates). PERF-31's Why is false since 1.75; tier conflict | PERF-31 | API-48's correct account |
| 60 | FUNC-47 / API-19 / API-33 / CLI-15 (parse, don't validate), with CORE-19 | FUNC-47 | API-19's "same validation twice" grep, API-33's "how deep does the `&str` travel", CLI-15's "the error names the flag" |
| 61 | API-27 / API-39 / API-28 (newtype a unit, domain or validity condition) | API-27, with API-28 as its Check | API-39's doc-comment grep ("must", ranges) |
| 62 | API-37 / API-32 (a finite set is an enum) | API-37 | API-32 keeps the non-enum cases (`String` errors, string-keyed config) |
| 63 | API-21 / OWN-06 (no `&mut` to invariant-bearing state), with API-24 | API-21 | OWN-06's "two accessors in an invalid order" Check |
| 64 | API-29 / MOD-54 / FUNC-42 (a `bool` parameter) | API-29, with an explicit decision: a flag that selects behaviour splits the function; a flag that is data is an enum; three or more read together are an options struct or a policy closure | — |
| 65 | TRAIT-02 / NAME-32 (a trait is a capability) | TRAIT-02 | NAME-32's verb or agent-noun form, and "`IntoIterator`, not `Iterable`" |
| 66 | TRAIT-08 / FUNC-54 (composition over supertrait chains), with CORE-26 | TRAIT-08 | nothing; FUNC-54 goes |
| 67 | TRAIT-54 / TRAIT-06 (every impl is total) | TRAIT-54 | TRAIT-06's `Storage`/`MutableStorage` example, which is the better one |
| 68 | TRAIT-03 / TRAIT-04 (small required set) | TRAIT-03 | "more than three required methods means a redesign" |
| 69 | TRAIT-44 `[M]` / TRAIT-39 `[S]` (associated type vs parameter) | TRAIT-44 | TRAIT-39's `Iterator::Item` example |
| 70 | TRAIT-17 / TRAIT-15 (named parameter when a caller may turbofish) | TRAIT-17; TRAIT-15 drops that clause | — |
| 71 | TRAIT-19 / TRAIT-49, with TRAIT-43 (associated constants break dyn) | TRAIT-19 | both remedies |
| 72 | TRAIT-30 / API-71 / TRAIT-32 (seal an enumeration) | TRAIT-30, TRAIT-32 its converse | API-71's "a defaulted method on an unsealed trait is technically breaking" |
| 73 | TRAIT-07 / TRAIT-28 (sealed extension traits) | TRAIT-07 | — |
| 74 | TRAIT-50 / FUNC-50 (typestate) | TRAIT-50 | FUNC-50 keeps "return the new state as a value" |
| 75 | TRAIT-18 / FUNC-40 (return `impl Fn`) | TRAIT-18 | — |
| 76 | UNSAFE-18 / TRAIT-53 (`PhantomData<fn() -> T>`) | UNSAFE-18 | — |
| 77 | UNSAFE-14 / UNSAFE-28 / UNSAFE-34 (`repr` and a const layout assert) | UNSAFE-14; UNSAFE-28 keeps its FFI specifics | take numbers from the C side, `c_void_returns`, 1.99.1 |
| 78 | FUNC-45 `[M]` / FUNC-46 `[S]` (pure core, effects at the edges) | FUNC-45 | FUNC-46's entry/middle/exit wording and its "deepest I/O call" Check |
| 79 | FUNC-04 / FUNC-13 (named aggregate over `fold`) | FUNC-04 | FUNC-13's `max_by_key` vs `max_by` |
| 80 | FUNC-20 / FUNC-14 (collect into the target) | FUNC-20 | FUNC-14 keeps "fold only for non-collection accumulators" |
| 81 | FUNC-58 `[S]` / FUNC-31 `[M]` (no stage mutates a capture), with FUNC-16, CONC-42 | FUNC-58, keeping FUNC-31's `[M]` floor for `map` | — |
| 82 | FUNC-22 / FUNC-09 (end) / FUNC-10 (adapters over indices) | FUNC-22; FUNC-10 becomes a row (A.3) | — |
| 83 | CONC-40 / FUNC-25 (`iter` → `par_iter`) | CONC-40 | — |
| 84 | CONC-30 / OWN-27 (`lazy_static`/`once_cell`), and the MIG-01 row | CONC-30; OWN-27 keeps its primitive table | — |
| 85 | MACRO-18 / MACRO-07 / BUILD-49 (proc-macro cost) | MACRO-18, with MACRO-07 merged in | — |
| 86 | MACRO-05 / MACRO-25 (expand to a function call) | MACRO-05 | — |
| 87 | MACRO-09 + MACRO-17 / MACRO-23 (absolute paths; distinctive names) | one rule for both macro kinds | — |
| 88 | MACRO-16 / MACRO-26 (`trybuild`; expansion tests) | one rule | — |
| 89 | CLI-07 / CLI-09 (one flag table) | CLI-07 | — |
| 90 | ERR-01 / ERR-33 (a panic means a bug) | ERR-01; retarget CORE-15 | — |
| 91 | ERR-28 / ERR-26 (lazy arguments) | ERR-28 | a row for `.context(format!…)` |
| 92 | API-05 / ERR-15 (error coupling) | API-05 | ERR-15's `#[from]` Check |
| 93 | NAME-11 / NAME-37 / NAME-41 (generic-parameter names) | one rule with a stated order | — |
| 94 | NAME-26 / NAME-43 (word order) | one rule | — |

**Cross-reference, not merge:** ERR-30 ~ ERR-45; ERR-43 ~ CLI-19; ERR-42 ~ ERR-41/44;
BUILD-12 ~ DOC-30; BUILD-35 ~ API-72; API-18 ~ DOC-18; TRAIT-13 ~ DOC-17; TEST-04 ~ MOD-05/48;
TEST-13 ~ TEST-16; CONC-02 ⊃ CONC-03; CONC-07 ~ CONC-32; CONC-36 ⊃ CONC-37; DOC-02 ~ DOC-07;
DOC-20 ~ DOC-22; ERR-12 ~ CLI-13; NAME-42 ~ API-76.

### A.2 Core rules that differ from their chapter rule

- **RS-CORE-27**: `unsafe_code = "forbid"` unless `unsafe` is the point. No cited rule (UNSAFE-02,
  -03, -30) says so; only BUILD-25's TOML and `assets/Cargo.toml` do. A chapter rule must own it.
- **RS-CORE-10**: "an example that compiles" on every public item. DOC-08 asks only for
  non-trivial items, and CORE-10 cites DOC-01 for it.
- **RS-CORE-12**: its relaxed form allows only `expect` in tests, `build.rs` and binaries. ERR-03
  allows `unwrap` and `expect` in tests, and binaries and `build.rs` relax `expect_used` in their own
  `[lints]`.
- **RS-CORE-01**: includes the acronym rule (NAME-02) but cites only NAME-01.

### A.3 Rules a "Decided by tools" table already decides

**A row in the rule's own chapter:**

- **NAME-01** (casing): the `non_upper_case_globals` row. rustc's default `non_camel_case_types` and
  `non_snake_case` have no rows, and the rule's Check says the compiler catches every case. Add the
  two rows and keep only the FFI exception.
- **FUNC-01** (expressions over statements): its only BAD/GOOD pair is `needless_late_init`. The
  rest is `clippy::useless_let_if_seq`, which is nursery and not shipped.

**A row in another chapter's table:**

- **FUNC-10**: the performance table's `needless_range_loop`. Nothing is left.
- **API-11**: the ownership table's `ptr_arg`. `&Box<T>` is `clippy::borrowed_box`, a default.
- **ERR-03**: the build table's `unwrap_used`, `expect_used`, `panic`, `todo`, `unimplemented` and
  `indexing_slicing`. The Why and the relaxed form remain.
- **API-12**, its converse half: `needless_pass_by_value`.

UNSAFE-03 (`undocumented_unsafe_blocks`) and DOC-31 (`broken_intra_doc_links`) check presence only.
The rules carry the quality requirement, so neither is a duplicate.

**A shipped or default lint decides it, with no row** ("fired" means a probe triggered it):

| Rule | Lint |
|---|---|
| NAME-02 | `clippy::upper_case_acronyms` with `upper-case-acronyms-aggressive` (shipped `clippy.toml`). Fired on `HTTPClient` |
| NAME-09 | `clippy::enum_variant_names`, with `avoid-breaking-exported-api = false` (shipped). Fired |
| OWN-39 | rustc `let_underscore_lock`, deny by default. It rejects the rule's BAD fragment, whose marker should be `// rejected — rustc: let_underscore_lock` |
| UNSAFE-06 | rustc `unsafe_op_in_unsafe_fn`, warn in edition 2024 |
| DOC-01 | `missing_docs = "deny"` |
| API-50 | `missing_debug_implementations = "deny"` |
| MOD-14 | `unreachable_pub` |
| MOD-44 | `clippy::wildcard_imports` (pedantic), which exempts test `use super::*` and preludes. Fired |
| DOC-26 | `clippy::doc_markdown` (pedantic). Fired |
| TEST-04, "at the bottom" | `clippy::items_after_test_module`. Fired |
| MOD-42 / MOD-43 | rustfmt `group_imports`, `imports_granularity` |
| OWN-40, `mem::forget` | `clippy::mem_forget = "deny"` |
| DOC-12/13/14, UNSAFE-04, presence only | `missing_errors_doc`, `missing_panics_doc` (pedantic), `missing_safety_doc` |

## B. Newer APIs, syntax and edition changes

### B.1 Updates, most valuable first

| # | Where | Old | New (release) | Probe |
|---|---|---|---|---|
| 1 | SKILL §2.1, UNSAFE-23, UNSAFE-25 (no `extern` block shown) | `extern "C" { fn abs(…); }` | `unsafe extern "C" { pub safe fn abs(…); }`, required in edition 2024 | A plain block fails: `extern blocks must be unsafe` (`edition_extern.rs`) |
| 2 | SKILL §2.1 silent changes; MACRO-10 recommends `expr` | an `$e:expr` arm before a `_` arm | in edition 2024 `expr` also matches `_` and `const {}`; `expr_2021` keeps the old meaning | `mac.rs`: `which!(_)` picks a different arm on 2021 and 2024 |
| 3 | FUNC-44's Why ("`fn(&str) -> bool` is … comparable") | `a == b` on fn pointers | `unpredictable_function_pointer_comparisons` warns; `ptr::fn_addr_eq` states intent | fires in `asis`; denied under `CARGO_BUILD_WARNINGS=deny` |
| 4 | OWN-39 | BAD fragment marked `fragment` | `rejected — rustc: let_underscore_lock` | `error: non-binding let on a synchronization lock` |
| 5 | UNSAFE-12/16/17, `static mut` advice | `&mut *x as *mut T`, `&STATIC as *const T`, a reference to a packed field | `&raw const` / `&raw mut`; `raw_borrows_via_references` (allow) | `raw_borrow.rs` |
| 6 | UNSAFE-14/28/34 | asserts on size and align only | also `assert!(offset_of!(Point, y) == 8)`; size and align miss a swap of same-typed fields | `modern.rs` |
| 7 | TEST-17, FUNC-49 | tests that set environment variables | `env::set_var`/`remove_var` are `unsafe` in 2024 and `unsafe_code = "forbid"` bans them: inject a lookup, as CLI-36 does | `ed24.rs`: E0133 |
| 8 | API-52; TRAIT-36/37 `.collect::<Vec<_>>().join(", ")` | a method returning `String` | `fmt::from_fn`, a zero-allocation `impl Display` | `Bytes(3).verbose().to_string() == "3 bytes"` |
| 9 | FUNC-09 | `windows(2)` then `w[0]`, `w[1]`, which `indexing_slicing = "deny"` rejects | `array_windows`, destructured as `[a, b]` | `deltas(&[1,4,9]) == [3,5]` |
| 10 | TRAIT-18, PERF-07 examples | `value % 2 == 0` | `value.is_multiple_of(2)`; `manual_is_multiple_of` is a default lint | fires for a by-value `u32` |
| 11 | MOD-38 | `publish = false` with `version = "0.0.0"` | omit `version`: it means `0.0.0` and `publish = false` | `pkgnover/` |
| 12 | CLI-32 `staging_path` | `file_name()…to_os_string()` + `push(".tmp")` + `with_file_name` | `target.with_added_extension("tmp")`; `File::create_new` opens it exclusively | tests pass |
| 13 | TRAIT-01 example | `String::new()` + `read_to_string(&mut text)` | `io::read_to_string(source)?` | test passes |
| 14 | UNSAFE-15 example | `bytes.get(..4)?.try_into().ok()?` | `bytes.first_chunk::<4>().copied().map(u32::from_le_bytes)` | test passes |
| 15 | PERF-27 example (count lines) | `read_until` into a discarded `Vec` | `while source.skip_until(b'\n')? > 0` | `skip.rs` |
| 16 | ERR-36 `midpoint` | `low + (high - low) / 2` | `low.midpoint(high)`; `manual_midpoint` (pedantic) | test at `u32::MAX` |
| 17 | PERF-34, CONC-30 examples | `static OnceLock<Vec<char>>` for constant data; `LazyLock<Vec<&str>>` of literals | a `const` array (FUNC-29); `LazyLock` only for a computed value | clippy clean |
| 18 | CLI-21, PERF-25 examples | `let stdout = io::stdout(); stdout.lock()` | `io::stdout().lock()` is `StdoutLock<'static>` | compiles |
| 19 | OWN-34 (Check greps for `try_unwrap` then clone) | `Arc::try_unwrap` + match + clone | `Arc::unwrap_or_clone`; `make_mut` stays for in-place mutation | test passes |
| 20 | FUNC-17 (`peekable`) | `if let Some(c) = it.peek() … it.next()` | `Peekable::next_if` / `next_if_map` | `leading_digits("123abc") == 123` |
| 21 | FUNC-23 ("`chunk_by`, `dedup_by`, `tuple_windows` have no std equivalent") | itertools on slices | `<[T]>::chunk_by`, `array_windows`, `Vec::dedup_by`; itertools only for non-slice iterators | `runs(&[1,1,2,3,3,3]) == [2,1,3]` |
| 22 | PERF-04 ("make the rare case correct") | — | `#[cold]` / `std::hint::cold_path()` | compiles |
| 23 | UNSAFE-25 example | `CStr::from_ptr(p).to_bytes().len()` | `.count_bytes()` | compiles |
| 24 | DOC-19 example; API-06 prose | `impl Iterator<Item = usize> + '_` | edition 2024 captures every in-scope lifetime; `+ '_` is redundant | compiles without it |
| 25 | MIG-01, missing rows | `atty`/`is-terminal`, `num_cpus`, `memoffset`, `static_assertions` (UNSAFE-34 still suggests it), `criterion::black_box`, itertools `group_by` on slices | `io::IsTerminal`, `thread::available_parallelism`, `mem::offset_of!`, `const { assert!(..) }`, `hint::black_box`, `slice::chunk_by` | — |
| 26 | CONC-16 (crossbeam "for throughput") | crossbeam for throughput | std `mpsc` is crossbeam's implementation; crossbeam only for `select` and multiple consumers | release notes |
| 27 | SKILL §2.1 silent edition changes | — | `Box<[T]>::into_iter()` yields `T` in 2024 | `ed24.rs` |
| 28 | PERF-30 (`exists()` then `metadata()`) | `Path::exists()` swallows errors | `fs::exists` returns `io::Result<bool>` | `uoc.rs` |
| 29 | testing, concurrency (poll a future in a unit test) | a runtime as a test dependency | `Waker::noop()` + `pin!` + `poll` | `noop.rs` |
| 30 | MACRO-13; DOC-34 | — | 1.99 lints trailing semicolons from non-local macros too; method suggestions prefer exact `#[doc(alias)]` matches | release notes |

### B.2 Lints that decide or strengthen a rule and are never named

| Lint | Group | Rule |
|---|---|---|
| `large_enum_variant`, `result_large_err` | default | ERR-20, PERF-19, PERF-20 |
| `box_collection` | default | OWN-32 |
| `redundant_allocation`, `rc_buffer` | — | OWN-32 |
| `multiple_unsafe_ops_per_block` | restriction | UNSAFE-05 |
| `clone_on_ref_ptr` | restriction | OWN-11 |
| `needless_collect` | nursery | FUNC-21 |
| `or_fun_call` | nursery | ERR-28 |
| `unnecessary_lazy_evaluations` | default (the converse) | ERR-28 |
| `dead_code_pub_in_binary` | rustc, allow | MOD-14 for binaries: `unreachable_pub` misses root `pub` items in a bin |

## Defects

- **TRAIT-11's Why is wrong**: `#[must_use]` on a trait covers only `impl Trait` and `dyn Trait`
  values, not every implementor.
- **TRAIT-17's GOOD example** returns a caller-chosen `C: FromIterator<u32>`, which TRAIT-40 and
  API-09's Check reject.
- **UNSAFE-21's example** adds `unsafe impl Send` to a type that is already `Send`, and its SAFETY
  comment names a "raw handle above" that does not exist.
- **CONC-05's example** spawns a thread per item (CONC-15) and clones an `Arc` inside
  `thread::scope` (CONC-11).
- **CONC-38's example** has a no-op `.filter(|_| true)`.
- **CONC-22's statement** ends in an orphaned colon.
- **CLI-02** says four things and lists five; its `fn main(args: &[String])` is not an entry point.
- **BUILD-38's** `channel = "stable"` pins nothing, contradicting "identical to CI".
- **FUNC-19, PERF-06 and PERF-07 examples** pre-size where `collect` is already exact, or with an
  invented count.
- **Wrong citations**: DOC-18 cites API-30; API-81 cites NAME-42 for NAME-27.
- **UNSAFE-28's 1.99.1 note** is correct; the local rustc is 1.99.0, which still has the FFI `bool`
  miscompilation.

## Applied

All of A and B, by the plan and decisions in `rust-decisions.md`, with these changes and
exceptions:

- **FUNC-01 stays a rule.** Its Check also covers `let mut x = default` overwritten later, which
  no shipped lint decides; `useless_let_if_seq` is nursery.
- **Demoted beyond the plan**, because the shipped lint now decides all of each: DOC-01
  (`missing_docs`), MOD-14 (`unreachable_pub`), MOD-44 (`wildcard_imports`).
- **#87:** MACRO-23 merged into MACRO-09; MACRO-17 keeps the generated-names half.
- **API-27 rose to `[M]`**, so that absorbing API-28 did not demote "never leave two same-typed
  parameters adjacent".
- **#1:** UNSAFE-23's `safe fn` example is `getpid`, not `abs`: C's `abs(INT_MIN)` is undefined, so
  `abs` cannot be declared `safe`.
- **Skipped:** #8 in TRAIT-36/37 (a `from_fn` renderer roughly triples examples that teach
  bounds); #29 in testing (no example polls a future; CONC-34's Check names `Waker::noop`);
  `clone_on_ref_ptr`, `rc_buffer`, `multiple_unsafe_ops_per_block` and
  `dead_code_pub_in_binary` rows (the shipped configuration leaves them off); MOD-42/43 (there is
  no rustfmt row kind); a `.context(format!…)` row (no shipped lint decides it).
- **The arrival dates** the annotations carried are `migration.md`'s "When an API arrived" table,
  for a crate whose MSRV is below 1.99; the silent ones are rows of RS-MIG-03.
