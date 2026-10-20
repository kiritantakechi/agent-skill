# rust-style vs Rust 1.99 stable: what has to change

Research date: 2026-10-20. Local toolchain: rustc 1.99.0 (b940084d7 2026-09-28), clippy 0.1.99, cargo 1.99.0, rustfmt 1.10.0.
Latest stable is **1.99.1** (2026-10-15). It fixes an x86_64 miscompilation of FFI `bool` return values, and the local machine is still on 1.99.0.
Next stable: 1.100.0, due 2026-11-12.

**Skill revision history** (`git log -- skills/rust-style`): 17fbe51 2026-08-22, 86e6f1a 2026-08-22, cf35968 2026-08-25 and 4afde73 2026-08-29. These dates fall while 1.98 was the current stable, which matches the assets' `rust-version = "1.98"`. However, the §2 tables cite no stabilisation later than 1.88. The only exceptions are two items marked "recent" with no version. So this review covers every release from **1.85 through 1.99.1**, and looks hardest at 1.89–1.99.

**Method.** I read every release note listed below in full. I checked lint names with `cargo clippy --explain` and `rustc -W help` on 1.99.0. I also compiled small probes with `rustc` and `clippy-driver` in the scratchpad. None of them ran in the repo, and I ran no harness or `agent-skill check`. Items I could not confirm are marked **UNCONFIRMED**.

---

## Sources

Release notes:
- [S1] rust-lang/rust RELEASES.md: https://github.com/rust-lang/rust/blob/main/RELEASES.md. It covers 1.85.0 to 1.99.1, with per-version anchors such as `#version-1990-2026-10-01`. A mirror is at https://doc.rust-lang.org/stable/releases.html.
- [S2] Announcing Rust 1.99.0: https://blog.rust-lang.org/2026/10/01/Rust-1.99.0/ — and 1.99.1: https://blog.rust-lang.org/2026/10/15/Rust-1.99.1/
- [S3] Announcing Rust 1.98.0: https://blog.rust-lang.org/2026/08/20/Rust-1.98.0/ — and 1.98.1: https://blog.rust-lang.org/2026/09/03/Rust-1.98.1/
- [S4] Announcing Rust 1.97.0: https://blog.rust-lang.org/2026/07/09/Rust-1.97.0/
- [S5] Announcing Rust 1.96.0: https://blog.rust-lang.org/2026/05/28/Rust-1.96.0/
- [S6] Announcing Rust 1.95.0: https://blog.rust-lang.org/2026/04/16/Rust-1.95.0/
- [S7] 1.94.0 https://blog.rust-lang.org/2026/03/05/Rust-1.94.0/ · 1.93.0 https://blog.rust-lang.org/2026/01/22/Rust-1.93.0/ · 1.92.0 https://blog.rust-lang.org/2025/12/11/Rust-1.92.0/ · 1.91.0 https://blog.rust-lang.org/2025/10/30/Rust-1.91.0/ · 1.90.0 https://blog.rust-lang.org/2025/09/18/Rust-1.90.0/ · 1.89.0 https://blog.rust-lang.org/2025/08/07/Rust-1.89.0/ · 1.88.0 https://blog.rust-lang.org/2025/06/26/Rust-1.88.0/ · 1.87.0 https://blog.rust-lang.org/2025/05/15/Rust-1.87.0/
- [S8] releases.rs: https://releases.rs/docs/1.99.0/ ; 1.100.0 beta: https://releases.rs/docs/1.100.0/

Clippy:
- [S9] Clippy CHANGELOG, Rust 1.85 to 1.99 sections: https://github.com/rust-lang/rust-clippy/blob/master/CHANGELOG.md
- [S10] Clippy stable lint index. It is the 1.99 build and gives each lint's group, level and "Added in": https://rust-lang.github.io/rust-clippy/stable/index.html

Cargo:
- [S11] Cargo changelog, 1.92 to 1.99: https://doc.rust-lang.org/nightly/cargo/CHANGELOG.html#cargo-199-2026-10-01
- [S12] Cargo config `build.warnings` ("MSRV: Respected as of 1.97"): https://doc.rust-lang.org/cargo/reference/config.html#buildwarnings
- [S13] Cargo book, Continuous Integration (uses `actions/checkout@v6`, `cargo hack check --rust-version`, `CARGO_BUILD_WARNINGS: deny`): https://doc.rust-lang.org/cargo/guide/continuous-integration.html

rustc, rustdoc and std:
- [S14] rustc lint listing for `linker_messages`: https://doc.rust-lang.org/rustc/lints/listing/warn-by-default.html#linker-messages
- [S15] rustc allow-by-default listing (`dead_code_pub_in_binary`, `raw_borrows_via_references`, `linker_info`): https://doc.rust-lang.org/rustc/lints/listing/allowed-by-default.html
- [S16] PR #153968, "linker-messages is warn-by-default again", which also makes it ignore `-Dwarnings`: https://github.com/rust-lang/rust/pull/153968
- [S17] `std::sync::atomic::Atomic` docs: `fetch_update` is "Deprecated since 1.99.0: renamed to try_update": https://doc.rust-lang.org/stable/std/sync/atomic/struct.Atomic.html
- [S18] `assert_matches!` docs, 1.96.0: https://doc.rust-lang.org/stable/std/macro.assert_matches.html
- [S19] Unstable book, `-Zon-broken-pipe`. Rust sets SIGPIPE to SIG_IGN before `main`: https://doc.rust-lang.org/nightly/unstable-book/compiler-flags/on-broken-pipe.html
- [S20] rustdoc unstable features. `doc_cfg` is still unstable, and "By default, `#[doc(auto_cfg)]` is enabled at the crate-level": https://doc.rust-lang.org/nightly/rustdoc/unstable-features.html

Rust blog posts:
- [S21] docs.rs builds only the default target from 2026-05-01: https://blog.rust-lang.org/2026/04/04/docsrs-only-default-targets/
- [S22] GitHub Actions leaking secrets when Miri output is cached: https://blog.rust-lang.org/2026/09/21/github-actions-leaking-secrets-when-miri-output-is-cached/
- [S23] Demoting i686 Windows targets with 1.100.0: https://blog.rust-lang.org/2026/10/02/demoting-i686-windows-targets-to-std-only/

Edition sources:
- [S24] rustc `edition.rs` on main: https://github.com/rust-lang/rust/blob/main/compiler/rustc_span/src/edition.rs
- [S25] Edition Guide SUMMARY: https://github.com/rust-lang/edition-guide/blob/master/src/SUMMARY.md
- [S26] `A-edition-2027` label: https://github.com/rust-lang/rust/labels/A-edition-2027. Examples: PR #164328 https://github.com/rust-lang/rust/pull/164328, issue #151084 https://github.com/rust-lang/rust/issues/151084, issue #149359 https://github.com/rust-lang/rust/issues/149359
- [S27] Internals thread "We have only two years to prepare the Rust 2027 Edition" (2025-03-03): https://internals.rust-lang.org/t/we-have-only-two-years-to-prepare-the-rust-2027-edition/22494
- [S28] 2026 project goals: https://github.com/rust-lang/rust-project-goals/tree/main/src/2026

Local verification:
- [L] Probes run on rustc/clippy/cargo 1.99.0 in the scratchpad (`rustc -W help`, `cargo clippy --explain`, `clippy-driver`, and a throwaway crate). Each claim tagged [L] was reproduced locally.

---

## Release-by-release relevant changes

Only items that change idiomatic code, lints, deprecations, or behaviour that the skill relies on are listed. The source for each version's notes is [S1] unless another tag is given.

### 1.85 (2025-02-20) — edition 2024 release
- Async closures stabilised, and `AsyncFn`/`AsyncFnMut`/`AsyncFnOnce` added to the prelude in all editions. `#[diagnostic::do_not_recommend]` stabilised.
- Clippy [S9]: `repr_packed_without_abi` and `doc_nested_refdefs` (suspicious). `as_pointer_underscore` and `doc_include_without_cfg` (restriction).

### 1.86 (2025-04-03)
- Trait upcasting stabilised, including `&dyn Sub` → `&dyn Super` and `&dyn Any` when `Any` is a supertrait. Also stabilised: `<[_]>::get_disjoint_mut`, `HashMap::get_disjoint_mut`, `Vec::pop_if`, `OnceLock::wait`, `Once::wait`. `missing_abi` becomes warn-by-default. `double_negations` is uplifted from Clippy.
- Clippy [S9]: `non_std_lazy_statics` (pedantic) flags `lazy_static!` and `once_cell::sync::Lazy`. `unnecessary_semicolon` (pedantic). `format_collect` and `format_push_string` move to pedantic.

### 1.87 (2025-05-15)
- Stabilised: `Vec::extract_if`, `LinkedList::extract_if`, `io::pipe`, `<uN>::cast_signed`, `<iN>::cast_unsigned`, `<uN>::is_multiple_of`, `<[T]>::split_off*`, `OsStr::display`. `std::arch` intrinsics are callable from safe code when the target features are enabled. `use<..>` is allowed in RPITIT. `env::home_dir` is undeprecated.
- Clippy [S9]: `io_other_error` (style). `elidable_lifetime_names`, `unnecessary_debug_formatting` and `manual_midpoint` (pedantic). `comparison_chain` moves to pedantic.

### 1.88 (2025-06-26)
- let-chains (edition 2024), naked functions and `cfg(true)` stabilised. Also `Cell::update`, `HashMap::extract_if`, `HashSet::extract_if`, `<[T]>::as_chunks`, `hint::select_unpredictable`. `#[bench]` is fully destabilised. libtest `--nocapture` is deprecated for `--no-capture`. `invalid_null_arguments` is uplifted.
- Clippy [S9]: `ignore_without_reason` (pedantic), `redundant_test_prefix` (restriction), `char_indices_as_byte_indices` (correctness). `match_on_vec_items` deprecated. Superseded transmute lints removed.

### 1.89 (2025-08-07)
- **`mismatched_lifetime_syntaxes` is warn-by-default in every edition**, superseding `elided_named_lifetimes`. `dangerous_implicit_autorefs` becomes deny.
- Stabilised: `File::lock`, `lock_shared`, `try_lock`, `try_lock_shared`, `unlock`; `Result::flatten`; `NonNull::from_ref`/`from_mut`; explicitly inferred const args (`_`). `missing_fragment_specifier` becomes a hard error. Cross-compiled doctests run (doctest-xcompile).
- Clippy [S9]: `uninlined_format_args` moves back to pedantic. `ip_constant` (pedantic). `infallible_try_from` and `confusing_method_to_numeric_cast` (suspicious).

### 1.90 (2025-09-18)
- **lld is the default linker on `x86_64-unknown-linux-gnu`.** `x86_64-apple-darwin` is demoted to Tier 2. `UnixStream` sets `MSG_NOSIGNAL`. `env::home_dir` falls back when `HOME` is empty. `u{n}::*_sub_signed` stabilised. `unknown_or_malformed_diagnostic_attributes` is split into four lints. Cargo stabilises multi-package publish.
- Clippy [S9]: `manual_is_multiple_of` (complexity, warn), `doc_broken_link` (pedantic).

### 1.91 (2025-10-30)
- **`{integer}::strict_*` arithmetic is stabilised**: it panics on overflow in every profile. Also stabilised: `core::iter::chain`, `BTreeMap::extract_if`, `BTreeSet::extract_if`, `str::floor_char_boundary`/`ceil_char_boundary`, `Path::file_prefix`, `PathBuf::add_extension`, `Duration::from_mins`/`from_hours`, `PanicHookInfo::payload_as_str`, and `carrying_*`/`borrowing_sub`.
- Lints: `dangling_pointers_from_locals` and `integer_to_ptr_transmutes` (warn). `semicolon_in_expressions_from_macros` becomes deny.
- Silent changes:
  - Pattern-binding drop order now follows the written order of the primary bindings.
  - Panic messages print the thread ID.
  - Edition-2024 `if let` scrutinee temporaries from `pin!`, `format_args!` and `write!` are rescoped.
- Platforms: `aarch64-pc-windows-msvc` becomes Tier 1. Cargo stabilises `build.build-dir`.

### 1.92 (2025-12-11)
- Never-type fallback lints become deny. `unused_must_use` stops warning on `Result<(), Uninhabited>`.
- Stabilised: `RwLockWriteGuard::downgrade`, `Box`/`Rc`/`Arc::new_zeroed*`, `btree_map::Entry::insert_entry`.
- Behaviour: `iter::Repeat::last` and `count` now panic instead of looping. Unwind tables are on by default with `panic=abort` on Linux.
- Clippy [S9]: `unchecked_duration_subtraction` renamed to `unchecked_time_subtraction`. `self_only_used_in_recursion` (pedantic).

### 1.93 (2026-01-22)
- Stabilised: `std::fmt::from_fn`/`FromFn`, `<[T]>::as_array`, `Vec::into_raw_parts`, `String::into_raw_parts`, `VecDeque::pop_front_if`/`pop_back_if`, `char::MAX_LEN_UTF8`, `unchecked_shl`/`unchecked_shr`/`unchecked_neg`, and `[MaybeUninit<T>]` slice helpers.
- Lints: `const_item_interior_mutations` and `function_casts_as_integer` (warn). `deref_nullptr` becomes deny.
- Rustdoc: `#![doc(document_private_items)]` removed. `rustdoc::invalid_doc_attributes` is deny. `#[test]` in meaningless positions is now an error.
- The std `Copy` specialisation is removed, so some APIs now call `Clone::clone`.
- Clippy [S9]: `needless_if` renamed `needless_ifs`, `empty_enum` renamed `empty_enums`. `doc_paragraphs_missing_punctuation` (restriction).

### 1.94 (2026-03-05)
- Stabilised: `<[T]>::array_windows`, `element_offset`, `LazyLock`/`LazyCell::get`/`get_mut`/`force_mut`, `Peekable::next_if_map`, `TryFrom<char> for usize`.
- `unused_visibilities` (warn).
- **Closure capture semantics around patterns changed**: "can cause `Drop` to run at a different point in time".
- Std macros are now imported through the prelude, so glob-imported same-name macros become ambiguous.
- Cargo: config `include` stabilised; TOML 1.1 parsed; `CARGO_BIN_EXE_<name>` available at runtime [S11].
- Clippy [S9]: `collapsible_else_if` moves style → pedantic. `manual_ilog2`, `decimal_bitwise_operands`, `ptr_offset_by_literal` and `same_length_and_capacity` (pedantic).

### 1.95 (2026-04-16) [S6]
- **`if let` guards on match arms** stabilised.
- **`cfg_select!`** stabilised; the blog post says it serves "the same purpose as the popular `cfg-if` crate".
- Stabilised: `core::hint::cold_path`, `Atomic*::update`/`try_update`, `Vec::push_mut`/`insert_mut`, `MaybeUninit<[T; N]>: From<[MaybeUninit<T>; N]>`, `bool: TryFrom<{integer}>`, `core::range` module with `RangeInclusive`, `Layout::repeat*`, and `<*mut T>::as_mut_unchecked`.
- `irrefutable_let_patterns` no longer fires on let chains.
- Matching a `#[non_exhaustive]` single-variant enum now reads the discriminant, which can change closure captures.
- `Eq::assert_receiver_is_total_eq` deprecated. JSON target specs destabilised.
- Clippy [S9]: `duration_suboptimal_units` and `unnecessary_trailing_comma` (pedantic). `manual_checked_ops` and `manual_take` (complexity). `disallowed_fields` (style).

### 1.96 (2026-05-28) [S5]
- **`assert_matches!` and `debug_assert_matches!` stabilised.** They are *not* in the prelude and must be imported; I confirmed `use std::assert_matches;` works [L].
- New `Copy` range types: `core::range::{Range, RangeFrom, RangeToInclusive, ...}`. The blog advises "consider making use of `impl RangeBounds` in public API"; range syntax will switch to these types "in a future edition".
- `From<T>` implemented for `LazyLock` and `LazyCell`.
- `uninhabited_static` becomes deny.
- `BTreeMap::append` may now panic for incorrect `Ord` impls.
- Cargo fixes CVE-2026-5222 and CVE-2026-5223.
- Clippy [S9]: `manual_pop_if`, `manual_option_zip` and `manual_noop_waker` (complexity).

### 1.97 (2026-07-09) [S4]
- **v0 symbol mangling is the default.**
- **`linker_messages` is warn-by-default and deliberately unaffected by the `warnings` group or `-Dwarnings`** [S4][S16].
- **Cargo stabilises `build.warnings` / `CARGO_BUILD_WARNINGS`** [S11][S12]. Cargo also stabilises `resolver.lockfile-path` and adds `-m` for `--manifest-path`.
- Lints: `dead_code_pub_in_binary` (allow-by-default, new). `Result<T, Uninhabited>` is treated as `T` for `must_use`.
- Stabilised: `isolate_highest_one`/`isolate_lowest_one`/`highest_one`/`lowest_one`/`bit_width`.
- Deprecations: `std::char` constants and functions.
- `pin!` no longer deref-coerces.
- On Windows, a write after `shutdown` now returns `BrokenPipe` instead of `Other`.
- Clippy [S9]: `nonminimal_bool` (from complexity) and `overly_complex_bool_expr` (from correctness) move to pedantic. `manual_assert_eq` (pedantic). `manual_clear` and `useless_borrows_in_formatting` (perf). `inline_modules` and `inline_trait_bounds` (restriction).
- 1.97.1 fixes an LLVM miscompilation.

### 1.98 (2026-08-20) [S3]
- **`<int>::format_into` with `core::fmt::NumBuffer`.** The blog says it "could serve as a standard replacement for [`itoa`] and others like it".
- Stabilised: `bool::ok_or`/`ok_or_else`, `str::substr_range`, `[T]::subslice_range`, `str::strip_circumfix`/`[T]::strip_circumfix`, `{fN}::algebraic_*`, `String::from_utf16le`/`be*`, `NonZero::from_str_radix`, `Atomic<T>::from_mut*`, `std::range::legacy`. `{core,std}::derive` is accepted, with an MSRV of 1.96. The `ManuallyDrop<Box<_>>` guarantee is documented.
- Lints: `invalid_runtime_symbol_definitions` (deny), `suspicious_runtime_symbol_definitions` (warn), `c_void_returns` (warn). `UNSAFE_CODE` now fires on all unsafe attributes.
- Silent changes:
  - **The `derive(PartialOrd)` fast path when `Ord` is also derived "can break crates … where a type's PartialOrd and Ord impls were inconsistent".**
  - `repr(transparent)` is stricter: `repr(C)`, private-field and `#[non_exhaustive]` fields are no longer "trivial".
  - Temporaries in `assert_eq!`/`assert_ne!` are rescoped.
  - Windows thread-local destructors now use FLS.
  - `File::lock` returns "unsupported" on Solaris.
  - More `ambiguous_glob_imports` cases become hard errors.
- Clippy [S9]: `from_iter_instead_of_collect` deprecated. `empty_enums` moves pedantic → nursery. New lints:
  - pedantic: `with_capacity_zero`, `unused_async_trait_impl`, `assert_is_empty` [S10];
  - style: `chunks_exact_to_as_chunks`;
  - complexity: `manual_isolate_lowest_one`, `unnecessary_unwrap_unchecked`;
  - suspicious: `by_ref_peekable_peek`, `for_unbounded_range`.
- **1.98.1** fixes a vtable miscompilation [S1][S3].

### 1.99 (2026-10-01) [S2]
- **C-variadic function definitions** with `VaList` stabilised. `#[my_macro] mod foo;` is allowed.
- Stabilised:
  - `Vec::into_parts`/`from_parts`, `Box::into_non_null`/`from_non_null`;
  - **`std::fs::set_times` and `set_times_nofollow`**;
  - `String::from_utf8_lossy_owned`, `FromUtf8Error::into_utf8_lossy`;
  - `VecDeque::retain_back`;
  - `mem::size_of_val_raw`, `mem::align_of_val_raw`, `Layout::for_value_raw`;
  - `IntoIterator for Box<[T; N]>`.
- `core::fmt::NumBuffer` is re-exported as `std::fmt::NumBuffer`.
- Lints and errors:
  - `raw_borrows_via_references` (allow-by-default, new).
  - `unreachable_cfg_select_predicates` joins the `unused` group.
  - `unconditional_panic` covers `chunks(0)` and `windows(0)`.
  - `no_mangle_generic_items` becomes a hard error.
  - The non-local `semicolon_in_expressions_from_non_local_macros` lint is added.
  - Rustdoc: new `unused_footnote_definition` lint, and doctest code blocks now error on attributes that apply to nothing.
- Deprecations:
  - **The legacy integral modules (`std::i32::MAX` etc.) are fully deprecated.**
  - **`Atomic*::fetch_update` is deprecated in favour of `try_update`** [S17]. This is not in RELEASES.md, but I verified that rustc 1.99.0 warns [L].
- Semantics:
  - `UnsafeCell` contents may be accessed without going through `get`.
  - The Reference withdraws its recommendation to match a union and another value in one pattern (UB risk).
  - **Docs recommend against round-tripping `Box::leak` back to a `Box`**; use `Box::into_raw` or `into_non_null` instead [S2].
- Silent changes:
  - Exhausted `RangeInclusive` values report different `start()`/`end()` and index differently.
  - **Cargo disables incremental compilation in CI** (detected through `CI`).
  - **On edition-2024 members, Cargo now honours `default-features = false` on an inherited workspace dependency.** Before 1.99 it was ignored with a warning (RFC 3945) [S11].
- Cargo also adds a new built-in `debug` profile, which prepares `dev` to stop being debug-oriented, and warns on hyphenated lint names in `[lints]` [S11].
- Clippy [S9]:
  - pedantic: `assert_is_empty`, `manual_bit_width`;
  - suspicious: `block_scrutinee` (edition 2021 and older only), `mismatched_bit_width_type`;
  - complexity: `nonnull_unchecked_on_box_ptr`;
  - restriction: `definition_in_module_root`, `rest_pattern_accessible_field`, `unnecessary_rest_pattern`.
- **1.99.1** (2026-10-15) fixes the x86_64 FFI `bool` return miscompilation, the missing `wcslen` on UEFI and embedded targets, and the rust-lld rpath on macOS [S1][S2].

### Forward-looking (not stable yet)
- The 1.100 beta, due 2026-11-12, lists "stabilize never type" and "alloc: stabilise Allocator" [S8]. **UNCONFIRMED** that either survives to stable.
- i686 Windows host tools are demoted in 1.100 [S23].

---

## Rule impacts

Priority key:
- **R (required):** the skill is wrong or stale on 1.99.
- **S (should):** a newly stable feature or lint the rule ought to prefer or cite.
- **O (optional):** a polish item, or a gap rather than an error.

| ID | File | Pri | Change | Source |
|---|---|---|---|---|
| §2.2 last row | SKILL.md:99 | R | `CARGO_BUILD_WARNINGS=deny` is marked "recent"; change it to **1.97**. | [S4][S12] |
| §2.3 "Also recent" | SKILL.md:112 | R | Version the two items: v0 mangling default is **1.97**, and `linker_messages` warn-by-default is **1.97**. Optionally add the silent changes listed under §2 below. | [S4][S16] |
| RS-CAR-32 | cargo-toolchain.md:575 | R | Say it has been stable since 1.97, and that Cargo older than 1.97 ignores it (MSRV jobs below 1.97 do not deny). It **also covers `cargo doc`**: rustdoc warnings fail with `CARGO_BUILD_WARNINGS=deny` [L], so `RUSTDOCFLAGS: -D warnings` in `assets/ci.yml` is redundant and re-fingerprints doc builds. The real error text uses backticks: ``warnings are denied by `build.warnings` configuration`` [L]. | [S12][L] |
| RS-CAR-33 | cargo-toolchain.md:589 | S | Add "(1.97)". Mention that `linker_info` (allow-by-default) carries the informational linker output. The existing claim that `linker_messages` is outside the `warnings` group is confirmed. | [S4][S15][S16] |
| RS-CAR-26 | cargo-toolchain.md:503 | R | The mechanism is wrong. Cargo does **not** reject the manifest, and `cargo build` succeeds [L]. The error comes from `clippy::lint_groups_priority` (correctness, deny) under `cargo clippy`, with the message ``lint group `pedantic` has the same priority (0) as a lint``. | [S10][L] |
| RS-CAR-25 (example) and asset | cargo-toolchain.md:491, assets/Cargo.toml:68 | R | `module_name_repetitions = "allow"` has done nothing since Clippy 1.84 moved the lint to **restriction** (allow-by-default), so it is no longer a pedantic exception. Delete it. The same line is in `src/agent_skill/lang/rust.py` lines 111 and 175 and `skills/bevy-style/assets/Cargo.toml:83`, and `checks/lints.py` requires those to match. | [S9 §1.84][S10] |
| RS-CAR-27 | cargo-toolchain.md:516 | S | Pedantic membership has changed. **Moved in:** `collapsible_else_if` (1.94), `nonminimal_bool` and `overly_complex_bool_expr` (1.97), `uninlined_format_args` (back in pedantic since 1.89/1.90). **New pedantic lints, 1.89–1.99:** `ip_constant`, `doc_broken_link`, `self_only_used_in_recursion`, `manual_ilog2`, `decimal_bitwise_operands`, `ptr_offset_by_literal`, `same_length_and_capacity`, `duration_suboptimal_units`, `unnecessary_trailing_comma`, `manual_assert_eq`, `assert_is_empty`, `manual_bit_width`, `unused_async_trait_impl`, `with_capacity_zero`. Each toolchain bump adds questions to answer. **UNCONFIRMED** whether any of these fire on the `// verified` blocks: the harness was not run. | [S9][S10] |
| RS-CAR-08 | cargo-toolchain.md:200 | R | Since 1.99, edition-2024 members can write `dep = { workspace = true, default-features = false }`, and it takes effect. Before 1.99 it was ignored with a warning, so the same manifest resolves **different features on 1.98 and 1.99**. Either require `rust-version >= 1.99` when a member relies on it, or forbid the override. | [S11] |
| RS-CAR-24 | cargo-toolchain.md:440 | S | Cross-reference the 1.99 member-level `default-features` override as the workspace form of this rule, with the MSRV caveat above. | [S11] |
| RS-CAR-10 / RS-DOC-34 | cargo-toolchain.md:240, documentation.md:688 | R | Since 2026-05-01, docs.rs builds **only the default target** (`x86_64-unknown-linux-gnu`) unless `targets` is set. A crate with `cfg(windows)` or `cfg(target_os)` API must list `targets = [...]` or its docs omit that API. | [S21] |
| RS-CAR-19 | cargo-toolchain.md:378 | S | `doc(cfg(...))` still needs `#![cfg_attr(docsrs, feature(doc_cfg))]` at the crate root; it is nightly-only, and the skill never shows this line. With `doc_cfg` enabled, `doc(auto_cfg)` is on crate-wide by default, so per-item `cfg_attr(docsrs, doc(cfg(...)))` annotations are now mostly redundant. **UNCONFIRMED**: whether docs.rs's current nightly matches the nightly rustdoc book. | [S20] |
| RS-CAR-38 + ci.yml `msrv` | cargo-toolchain.md:657, assets/ci.yml:46 | S | The Cargo book now shows `cargo hack check --rust-version --workspace --all-targets --ignore-private`, which reads `rust-version` and so avoids hand-syncing `dtolnay/rust-toolchain@1.98` with the manifest. If any example adopts a 1.99 API, bump to 1.99; the toolchain then resolves to 1.99.1, **UNCONFIRMED** that dtolnay picks the latest patch. | [S13] |
| RS-CAR-46/47 + ci.yml | cargo-toolchain.md:764-786 | S | (a) Cargo 1.99 disables incremental in CI by default, so no `CARGO_INCREMENTAL=0` is needed. (b) The 2026-09-21 security advisory: a job that runs Miri, or any job that writes a `target/` cache readable by PRs, must not have secrets in its environment. The commented `miri` job and RS-UNS-30 should say so. (c) The Cargo book's examples use `actions/checkout@v6`; the asset uses `@v4`. **UNCONFIRMED** that v4 is deprecated. | [S11][S22][S13] |
| RS-CAR-48/49/50 | cargo-toolchain.md:787-830 | O | 1.99 adds a built-in `debug` profile in preparation for "transitioning the dev profile away from debugging". Mention it as the profile to request for debugger sessions once `dev` changes. | [S11] |
| RS-CAR-02 + assets | assets/Cargo.toml:10, cargo-toolchain.md:101 and 220, ci.yml:46, `src/agent_skill/lang/rust.py:36` | S | `rust-version = "1.98"` throughout. Any example that adopts a 1.99 API (`fs::set_times`, `Vec::into_parts`, `std::fmt::NumBuffer`, `String::from_utf8_lossy_owned`) triggers `clippy::incompatible_msrv` (suspicious, warn) under 1.98 [L], which fails `-D warnings`. Bump all five places to 1.99 together, or keep 1.98 and use `core::fmt::NumBuffer` (1.98) and no 1.99 APIs. | [S10][L] |
| RS-ERR-41, RS-PRF-40, §2.3 #1, §5 item 3 | errors.md:851, performance.md:921, SKILL.md:103 and 281 | S | Add **`strict_*` (1.91)** as the fourth deliberate choice. It panics on overflow in both profiles, so debug and release agree when overflow is a bug rather than an input. | [S1 §1.91] |
| RS-PRF-41, §2.3 #2 | performance.md:943, SKILL.md:106 | S | For same-width sign reinterpretation, which is not lossy and so is not a `try_from` case, prefer **`cast_signed()`/`cast_unsigned()` (1.87)** over `as`. | [S1 §1.87] |
| RS-TST-14 | testing.md:407 | R | The example uses `assert!(matches!(...))`. Use **`assert_matches!` (1.96)**: it prints the `Debug` of the actual value. It needs `use std::assert_matches;` because it is not in the prelude [L]. PR #164328 (`A-edition-2027`) proposes adding it to the next-edition prelude. The Check line ("Each should be a `matches!`") should name `assert_matches!`. | [S5][S18][S26][L] |
| RS-ERR-38 | errors.md | O | Add `debug_assert_matches!` (1.96) to the list of assertions that disappear in `--release`. | [S18] |
| RS-TST-12 | testing.md:309 | O | The Check line ("grep for `assert!(` containing `==`") is now mechanised by `clippy::manual_assert_eq` (pedantic, 1.97) and `assert_is_empty` (pedantic), both on under the shipped table. | [S9][S10] |
| RS-TST-40, RS-CNC-48 | testing.md:906, concurrency-async.md:1001 | R | The rules say "behind `#[ignore]`", but `clippy::ignore_without_reason` (pedantic, 1.88) is enabled by the shipped `pedantic = warn` and rejects a bare `#[ignore]` under `-D warnings`. Write `#[ignore = "slow: stress test; run with --ignored"]`. | [S9 §1.88][S10] |
| RS-TST-08 | testing.md:208 | O | "Do not prefix with `test_`" can be enforced with `clippy::redundant_test_prefix` (restriction, 1.88). | [S9][S10] |
| RS-TST-31 | testing.md:798 | O | `CARGO_BIN_EXE_<name>` is available at run time since Cargo 1.94, which helps a hand-rolled e2e harness. | [S11] |
| RS-CNC-27/28 | concurrency-async.md:621-666 | S | For read-modify-write that is not a single `fetch_*`, use **`update`/`try_update` (1.95)** rather than a hand `compare_exchange` loop. **`fetch_update` is deprecated in 1.99** and warns [L], which fails CI under `CARGO_BUILD_WARNINGS=deny`. | [S6][S17][L] |
| RS-CNC-30, RS-OWN-31 | concurrency-async.md:679, ownership.md:552 | O | The "grep for `lazy_static!`/`once_cell::`" Check is mechanised by `clippy::non_std_lazy_statics` (pedantic, 1.86). `LazyLock::get` and `force_mut` exist since 1.94. | [S9][S10][S1] |
| RS-CNC-26 | concurrency-async.md:611 | O | No change needed. Note that std's non-poisoning locks are still unstable, and that switching the default is an Edition 2027 candidate (#149359). | [S26] |
| RS-CNC-36, RS-FP-42/43 | concurrency-async.md:785, functional.md:741-760 | S | For async callbacks, use **async closures and `AsyncFn`/`AsyncFnMut`/`AsyncFnOnce` bounds (1.85)** instead of `F: Fn() -> Fut, Fut: Future`. Apply the same loosest-bound logic (`AsyncFnOnce` before `AsyncFnMut` before `AsyncFn`). | [S1 §1.85] |
| RS-FP-10 | functional.md:212 | S | Extend let-chains to **`if let` guards on match arms (1.95)**. 1.95 also stopped `irrefutable_let_patterns` from firing on let chains. | [S6] |
| RS-FP-34 | functional.md:638 | S | Add `extract_if` (Vec 1.87, HashMap/HashSet 1.88, BTreeMap/BTreeSet 1.91) for "remove and keep the removed". Also add `Vec::pop_if` (1.86), `VecDeque::pop_front_if`/`pop_back_if` (1.93) and `VecDeque::retain_back` (1.99). `clippy::manual_pop_if` (1.96) enforces part of this. | [S1][S9] |
| RS-OWN-06 | ownership.md:165-174 | R | It says hiding the lifetime (`Iter<T>`) is something "edition 2024 lints against". That is wrong. `fn iter(&self) -> Iter<u32>` is caught by **`mismatched_lifetime_syntaxes` (warn-by-default since 1.89, in every edition)** [L], and `elided_lifetimes_in_paths` is allow-by-default in every edition, enabled only by the asset. | [S1 §1.89][L] |
| RS-OWN-23, RS-UNS-26 | ownership.md:443, unsafe-ffi.md:648 | S | 1.99 docs: do not "unleak" (turn a leaked reference back into a `Box`). For memory that will be reclaimed, use `Box::into_raw`/`into_non_null` (1.99) with `from_raw`/`from_non_null`. Also cite `Vec::into_raw_parts` (1.93) and `Vec::into_parts`/`from_parts` (1.99) for the FFI ownership round-trip. | [S2][S1] |
| RS-UNS-13 example | unsafe-ffi.md:322-347 | S | Replace `transmute::<[MaybeUninit<u8>; 8], [u8; 8]>` with `MaybeUninit::<[u8; 8]>::from(buf).assume_init()`, using the 1.95 `From` impl. This removes a transmute in line with RS-UNS-15. It compiles clean under pedantic on 1.99 [L]. | [S1 §1.95][L] |
| RS-UNS-15/17 | unsafe-ffi.md | O | Cite `integer_to_ptr_transmutes` and `dangling_pointers_from_locals` (warn, 1.91), and `raw_borrows_via_references` (allow, 1.99), which suggests `&raw const`. | [S1][S15] |
| RS-UNS-11 | unsafe-ffi.md | S | Add to the UB list: matching a union together with another value in one pattern can read the union before the rest is checked (Reference changed in 1.99). Also add that `UnsafeCell` contents may now be accessed without `get` (1.99 guarantee). | [S1 §1.99] |
| RS-UNS-14/28/34 | unsafe-ffi.md:350, 700, 790 | O | `repr(transparent)` is stricter since 1.98: `repr(C)`, private-field and `#[non_exhaustive]` ZST fields no longer count as "trivial". | [S1 §1.98] |
| RS-UNS-24/25/28 | unsafe-ffi.md | S | C-variadic **definitions** are stable (1.99, `core::ffi::VaList`). Other changes: `c_void_returns` (warn, 1.98); `invalid_runtime_symbol_definitions` (deny, 1.98) for defining `memcpy`-like symbols; `no_mangle_generic_items` is a hard error (1.99). FFI crates on x86_64 need **≥ 1.99.1** because of the `bool`-return miscompilation. | [S1][S2] |
| RS-API-55 | api-design.md:1280 | S | Strengthen the Why. Since 1.98, derived `PartialOrd` with derived `Ord` takes a fast path that changes results when a field's `PartialOrd` and `Ord` disagree. Since 1.96, `BTreeMap::append` can **panic** on an inconsistent `Ord`. | [S1 §1.96, §1.98] |
| RS-API-63 example | api-design.md:1451 (example ~1484) | O | `(d != 0).then_some(Self{..}).ok_or(E)` can become `(d != 0).ok_or(E).map(\|()\| Self{..})` with `bool::ok_or` (1.98). | [S3] |
| RS-API (ranges, gap) | api-design.md | O | 1.96 guidance: public APIs that take ranges should accept `impl RangeBounds<_>`, and stored ranges can use the new `Copy` `core::range::Range`. `a..b` syntax changes type in a future edition. | [S5] |
| RS-PRF-12 | performance.md:290 | S | For integers, use `NumBuffer` + `format_into` (1.98) instead of `write!` into the reused `String`. It skips the `fmt` machinery and replaces `itoa`. The path is `core::fmt::NumBuffer` on 1.98 and `std::fmt::NumBuffer` from 1.99. A rewrite of the example compiles clean on 1.99 [L]. | [S3][S1 §1.99][L] |
| RS-PRF-24 | performance.md:597-616 | O | Add `<[T]>::as_array` (1.93) and `array_windows` (1.94) next to `as_chunks`. The Check "a `chunks_exact` with a literal width is an `as_chunks`" is now `clippy::chunks_exact_to_as_chunks` (style, warn-by-default). | [S1][S9] |
| RS-PRF-34/35 | performance.md | O | `core::hint::cold_path` (1.95) is the std way to mark an unlikely branch, measured like `#[inline(always)]`. | [S1 §1.95] |
| RS-CLI-22 | cli-apps.md:644 | R | This is factually inverted, and it is still wrong on 1.99. Rust *does* set SIGPIPE to `SIG_IGN` before `main` (since 2014), which is why the write returns `ErrorKind::BrokenPipe` instead of the process dying; it is C programs that die by default. `-Zon-broken-pipe` is still unstable. Also, since 1.97, Windows reports `BrokenPipe` for a write after `shutdown`. | [S19][S1 §1.97] |
| RS-CLI-36 | cli-apps.md:1052 | O | `std::env::home_dir` was undeprecated in 1.87 and fixed for an empty `HOME` in 1.90, so the `home` crate is unnecessary for `$HOME` alone. `directories` or `etcetera` are still right for config and cache dirs. | [S1 §1.87, §1.90] |
| RS-CLI-13 / path printing | cli-apps.md, errors.md:575 | O | `OsStr::display` (1.87). `clippy::unnecessary_debug_formatting` (pedantic, 1.87) flags `{:?}` on paths and `OsStr`. | [S1][S10] |
| RS-STR-10 | structure.md:254 | S | Inside `sys/`, use `cfg_select!` (1.95) instead of `cfg-if` for arm-wise platform selection. | [S6] |
| RS-STR-06 | structure.md:217 | O | Enforceable with `clippy::mod_module_files` (restriction; an old lint). | [S10] |
| RS-STR glob-import rule | structure.md:888 | O | This is reinforced by two changes: std macros arrive through the prelude (1.94), so globs collide with `matches`-like names, and more `ambiguous_glob_imports` cases became hard errors (1.98). | [S1] |
| RS-MAC-* | macros.md | O | `semicolon_in_expressions_from_macros` is deny (1.91), with a non-local variant added in 1.99. `missing_fragment_specifier` is a hard error (1.89). Attribute macros are allowed on `mod foo;` (1.99). The `macros.md` examples were checked and none end in `;` in expression position. | [S1] |
| RS-TRG-12 | traits-generics.md:346 | O | Add `#[diagnostic::do_not_recommend]` (1.85). The diagnostic lint was split into four in 1.90. | [S1] |
| RS-DOC-* | documentation.md | O | New rustdoc lint `unused_footnote_definition` (1.99). `rustdoc::invalid_doc_attributes` is deny (1.93). `#![doc(document_private_items)]` was removed (1.93). Doctest blocks now error on attributes that apply to nothing (1.99). Clippy adds `doc_broken_link` (pedantic, 1.90) and `doc_paragraphs_missing_punctuation` (restriction, 1.93). | [S1][S9] |
| RS-ERR-02 | errors.md | O | Since 1.92/1.97, `unused_must_use` treats `Result<T, Uninhabited>` as `T`, so `Result<(), Infallible>` no longer needs handling. | [S1] |

Checked and still accurate on 1.99:
- `rust_2018_idioms` still has the five members RS-CAR-25 names [L].
- `group_imports` and `imports_granularity` are still nightly-only in rustfmt 1.10.0 [L], so RS-CAR-34 and `rustfmt.toml` hold.
- No skill example uses `std::i32::MAX`-style paths, `fetch_update`, or `std::char::*`, which were checked by grep.
- The `value % 2 == 0` examples (performance.md:207, traits-generics.md:498) do **not** trigger `manual_is_multiple_of` [L].
- `async fn` in `dyn` traits is still unstable, so §2.2's `#[async_trait]` row stands.

---

## §2 changes

### 2.1 What the 2024 edition changed
- Nothing to remove; every row is still true on 1.99.
- Optional refinements:
  - The `if let` row: 1.91 extended edition-2024 `if let` rescoping to temporaries from `pin!`, `format_args!` and `write!` [S1 §1.91].
  - The `impl Trait` capture row: `use<..>` works in trait RPITIT since 1.87 [S1 §1.87].

### 2.2 Standard-library features that replaced ecosystem crates
Fix the existing row: `CARGO_BUILD_WARNINGS=deny` "recent" → **1.97** [S4].

Add rows. The crate replacements come first, ordered by how often the crate is reached for:

| Reach for this | Not this | Since | Source |
|---|---|---|---|
| `cfg_select!` | `cfg-if` | 1.95 | [S6] |
| `<int>::format_into(&mut NumBuffer)` | `itoa` | 1.98 (`std::fmt` path 1.99) | [S3][S1] |
| `File::lock` / `try_lock` / `lock_shared` | `fs2`, `fs4`, `fd-lock` for whole-file advisory locks | 1.89 (unsupported on Solaris since 1.98) | [S1] |
| `std::fs::set_times` / `set_times_nofollow` (and `File::set_times`) | `filetime` | 1.99 | [S2] |
| `std::io::pipe` | `os_pipe` | 1.87 | [S1] |
| `assert_matches!` / `debug_assert_matches!` (import from `std`) | the `assert_matches` crate; `assert!(matches!(..))` | 1.96 | [S5][S18] |
| trait upcasting, including to `dyn Any` | hand-written `fn as_any(&self) -> &dyn Any` | 1.86 | [S1] |
| async closures and `AsyncFn*` bounds | `F: Fn() -> Fut, Fut: Future` pairs | 1.85 | [S1] |
| `if let` guards in `match` | `match` + nested `if let` | 1.95 | [S6] |
| `Atomic*::update` / `try_update` | hand `compare_exchange` loops; `fetch_update` (deprecated 1.99) | 1.95 | [S6][S17] |
| `strict_*` arithmetic | `checked_*().expect(..)` when overflow is a bug | 1.91 | [S1] |
| `extract_if` on `Vec`/`HashMap`/`BTreeMap` | `drain_filter` shims, or retain plus a second `Vec` | 1.87 / 1.88 / 1.91 | [S1] |
| `std::env::home_dir` | `home` / `dirs::home_dir` for `$HOME` alone | 1.87 (undeprecated) | [S1] |

Lower-value candidates, to include only if the table should stay idiom-oriented:
- `fmt::from_fn` (1.93) instead of one-off `Display` wrapper structs;
- `get_disjoint_mut` (1.86);
- `hint::cold_path` (1.95);
- `core::range::Range` as a `Copy` range (1.96).

### 2.3 Silent behaviour changes
Keep the three entries; they are language semantics, not version changes. Strengthen #1 with `strict_*` (1.91) and #2 with `cast_signed`/`cast_unsigned` (1.87).

Extend the "Also recent" paragraph with version tags. These all compile either way and change behaviour:
1. **Cargo 1.99: `default-features = false` on an inherited workspace dependency now takes effect** in edition-2024 members; before 1.99 it was ignored with a warning. A 1.98 MSRV job and a 1.99 stable job build different feature sets from the same manifest [S11].
2. **1.98: derived `PartialOrd` alongside derived `Ord` takes an `Ord` fast path.** Results change when a field type's two impls disagree. Since 1.96, `BTreeMap::append` may panic on an inconsistent `Ord` [S1].
3. **Drop timing:**
   - 1.94 changed closure captures around patterns, which "can cause `Drop` to run at a different point in time".
   - 1.91 made binding drop order follow written order.
   - 1.95 made `#[non_exhaustive]` matches read the discriminant, which changes captures.
   These belong beside the §2.1 drop-scope rows [S1].
4. **1.97:** v0 mangling is the default; backtrace and profiler text changes, and old tools fail to demangle. `linker_messages` warns and is not in `warnings` [S4]. This is already in the paragraph and needs a version.
5. **1.99: Cargo turns off incremental compilation when `CI` is set** [S11].
6. **1.99: an exhausted `RangeInclusive`** reports different `start()`/`end()` and slices differently [S1].
7. **Not silent, but CI-breaking under the skill's own `CARGO_BUILD_WARNINGS=deny`:** 1.99 deprecated `fetch_update` and the legacy `std::i32::MAX`-style constants, which now warn [S1][S17][L].
8. Lower priority:
   - `iter::Repeat::last`/`count` now panic (1.92).
   - Panic messages include the thread ID (1.91), which affects log scrapers.
   - lld is the default linker on x86_64 Linux (1.90) [S1].

---

## Asset lint table changes (`assets/Cargo.toml` `[workspace.lints]`)

All 7 rustc and 18 clippy names in the table exist on 1.99. None was renamed or removed, and none is deprecated [L: `rustc -W help`, `cargo clippy --explain`, S10]. The table uses underscore names, which matters because Cargo 1.99 warns on hyphenated lint names [S11].

| Change | Entry | Why | Source |
|---|---|---|---|
| **Remove** | `module_name_repetitions = "allow"` | The lint has been in `restriction` since Clippy 1.84. It is allow-by-default and not part of pedantic, so this allow is dead config, and its comment ("individually justified allows only — never allow the whole group") misdescribes it. Remove it in lockstep from `src/agent_skill/lang/rust.py` lines 111 and 175 (`checks/lints.py` compares the two), `cargo-toolchain.md:491` and `skills/bevy-style/assets/Cargo.toml:83`. | [S9 §1.84][S10] |
| **Add (rust)** | `dead_code_pub_in_binary = "warn"` | Stable allow-by-default lint from 1.97. It reports unused `pub` items in executable crates and only applies to binaries [S15], so it is safe workspace-wide. It complements `unreachable_pub`. | [S1 §1.97][S15][L] |
| Consider (clippy) | `redundant_test_prefix = "warn"` | Restriction lint from 1.88. It mechanises RS-TST-08's "no `test_` prefix". | [S9][S10] |
| Consider (clippy) | `mod_module_files = "warn"` | Restriction lint that mechanises RS-STR-06 (no `foo/mod.rs`). It is old, not new in this window. | [S10] |
| Consider (rust, unsafe crates only) | `raw_borrows_via_references = "warn"` | Allow-by-default lint from 1.99. It flags `&x as *const _` and suggests `&raw const`. | [S1 §1.99][S15][L] |
| Note | `cast_possible_truncation`, `cast_precision_loss`, `cast_sign_loss`, `float_cmp` = "warn" | All four are pedantic, so they duplicate the group at the same level. Keep them only if the intent is that they survive someone allowing pedantic, and say so in the comment. | [S10] |
| Note | `pedantic` group | Pedantic now includes `ignore_without_reason`, which forces `#[ignore = "…"]` (affects RS-TST-40 and RS-CNC-48), and `manual_assert_eq`/`assert_is_empty`, which enforce RS-TST-12. `nonminimal_bool`, `overly_complex_bool_expr` and `collapsible_else_if` moved in. `overly_complex_bool_expr` *dropped* from correctness (deny) to pedantic (warn). | [S9][S10] |
| Do not add | `linker_messages` | Already warn-by-default since 1.97, and outside `warnings`. | [S4] |
| MSRV fields | `rust-version = "1.98"` (asset and RS-CAR-08/01 examples), `dtolnay/rust-toolchain@1.98` (ci.yml), `rust_version = "1.98"` (harness) | To target 1.99, bump all of them together. Use 1.99.1 as the toolchain: 1.99.0 has the x86_64 FFI `bool` miscompilation. With MSRV 1.98, `clippy::incompatible_msrv` rejects any 1.99 API in examples [L]. | [S1][S2][L] |
| ci.yml env | `RUSTDOCFLAGS: -D warnings` | Redundant on 1.97+. `CARGO_BUILD_WARNINGS=deny` already fails `cargo doc` on rustdoc warnings [L], and RUSTDOCFLAGS changes the doc fingerprint, which is the cost RS-CAR-32 cites for RUSTFLAGS. | [S12][L] |

Aside, outside rust-style: `skills/bevy-style/assets/rust-toolchain.toml` pins **1.98.0**. 1.98.1 fixed a vtable miscompilation [S1], so the pin should be at least 1.98.1, or 1.99.1.

---

## Edition status

**No Rust 2027 edition is stabilised, and none is close to being stabilised. It is not even present as an unstable edition on nightly.**

- Stable rustc 1.99 accepts `--edition <2015|2018|2021|2024|future>`, and `--edition 2027` is rejected as an invalid value [L].
- rustc `main` defines only `Edition2015`, `Edition2018`, `Edition2021`, `Edition2024` and the unstable placeholder `EditionFuture`, with `LATEST_STABLE_EDITION = Edition2024`. There is no `Edition2027` variant [S24].
- The Edition Guide has no Rust 2027 section; its SUMMARY ends at Rust 2024 (repo last pushed 2026-08-25) [S25].
- On 1.99 there is no `rust-2027-compatibility` lint group, only `rust-2024-compatibility` [L].
- Signs of early planning only:
  - An `A-edition-2027` label exists on rust-lang/rust. Labelled items include PR #164328 (open, 2026-10-14, "Add `assert_matches` and `debug_assert_matches` to the next prelude") and issue #151084 ("Remove edition-dependent behavior on `panic`"). Issue #149359 ("Edition 2027: Consider replacing `std::sync::Mutex` … with `nonpoison` versions") is also open [S26].
  - The 1.96 blog says range syntax will move to the `core::range` types "in a future edition" [S5].
  - Cargo 1.99 says hyphenated lint names "will not work in a future edition" [S11].
  - rustfmt 1.10.0 lists `style_edition … 2027 (unstable)` [L].
  - An internals thread from 2025-03 argued for preparing a 2027 edition [S27].
  - I found no 2026 project goal that commits to shipping one; grepping the 2026 goals found only passing mentions [S28].
- No official announcement, call for proposals, or date exists. **UNCONFIRMED:** any 2027 ship date.

**Implication for the skill:** "edition 2024 on the latest stable Rust" remains the right target. Three rules may want a one-line "next edition" note, because the change is tracked:
- RS-TST-14: `assert_matches!` may enter the prelude;
- RS-CNC-26: locks may become non-poisoning by default;
- range-taking APIs: `a..b` will change type.

The 1.100 beta, stable 2026-11-12, lists never-type and `Allocator` stabilisation [S8]. If they ship (**UNCONFIRMED**), the next refresh should revisit `Infallible` usage and allocator-generic APIs.
