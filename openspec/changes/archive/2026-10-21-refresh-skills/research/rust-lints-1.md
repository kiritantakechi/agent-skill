# rust-style lint classification, part 1

Scope: `skills/rust-style/references/{api-design,cargo-toolchain,cli-apps,concurrency-async,documentation,errors,functional,macros}.md`
(410 rules) and `SKILL.md` §4 (RS-CORE-01..28). Baseline is `skills/rust-style/assets/Cargo.toml`, with
`assets/ci.yml` and `assets/rustfmt.toml` also checked. No `clippy.toml` is shipped.

Toolchain: rustc 1.99.0 / clippy 0.1.99 (b940084d7, 2026-09-28). I confirmed every cited clippy lint with
`cargo clippy --explain <name>`: all 86 resolve, and a bogus name returns `unknown lint` as a control.
Default levels and groups come from `clippy-driver -W help`. rustc lints come from `rustc -W help` and
rustdoc lints from `rustdoc -W help`.

"Set in assets?" values:
- **deny (explicit)** or **warn (explicit)**: the lint is listed by name in `assets/Cargo.toml`.
- **via pedantic**: the lint is a pedantic member, enabled at warn by `pedantic = { level = "warn", priority = -1 }`.
- **default**: the lint is not listed, and its built-in level (warn or deny) applies.
- **no**: the lint is allow-by-default and not listed, so it is off.

## Counts

| Chapter | Rules | LINT | PARTIAL | Pointers | Why-long |
|---|---:|---:|---:|---:|---:|
| api-design | 84 | 2 | 15 | 1 | 33 |
| cargo-toolchain | 54 | 6 | 5 | 0 | 2 |
| cli-apps | 40 | 0 | 1 | 1 | 0 |
| concurrency-async | 52 | 1 | 8 | 0 | 1 |
| documentation | 40 | 2 | 7 | 0 | 0 |
| errors | 50 | 2 | 9 | 1 | 15 |
| functional | 64 | 7 | 17 | 0 | 15 |
| macros | 26 | 0 | 3 | 0 | 2 |
| SKILL.md §4 (core) | 28 | 1 | 13 | 0 | n/a (no Why paragraphs) |
| **Total** | **438** | **21** | **78** | **3** | **68** |

## Lint classification

Group abbreviations: `restr` = clippy::restriction, `ped` = clippy::pedantic, `nurs` = clippy::nursery.
Every lint name without a `rustc` or `rustdoc` prefix is a clippy lint.

### SKILL.md §4 core rules

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-CORE-01 | LINT | `non_camel_case_types`, `non_snake_case`, `non_upper_case_globals`; `upper_case_acronyms` | rustc nonstandard_style, warn; style, warn | default | `HTTPClient` is only caught with `upper-case-acronyms-aggressive = true` in clippy.toml, and no clippy.toml is shipped. The row should say to set it. |
| RS-CORE-02 | PARTIAL | `wrong_self_convention` | style, warn | default | Checks the receiver kind for `as_`, `to_` and `into_`. It cannot see whether the method allocates. |
| RS-CORE-05 | PARTIAL | rustfmt (`cargo fmt --check`) | tool | rustfmt.toml + ci.yml fmt job | "Keep rustfmt.toml minimal" is a policy, not something a tool checks. Same as RS-CAR-34. |
| RS-CORE-06 | PARTIAL | `unreachable_pub` (rustc) | allow | warn (explicit) | Only flags `pub` items that are not reachable. |
| RS-CORE-07 | PARTIAL | `ptr_arg`, `borrowed_box` | style warn; complexity warn | default | "Generic in what you accept" is not linted. |
| RS-CORE-09 | PARTIAL | `fn_params_excessive_bools`, `struct_excessive_bools` | ped, allow | via pedantic | Fires only above 3 bools. The Option-pair and stringly-typed cases are not linted. |
| RS-CORE-10 | PARTIAL | `missing_debug_implementations`, `missing_docs` (rustc) | allow | deny (explicit) | "An example that compiles" is not linted. |
| RS-CORE-11 | PARTIAL | `exhaustive_enums`, `exhaustive_structs` | restr, allow | no | The lint fires unconditionally. The rule only applies where the shape may grow, and has a relaxed form. |
| RS-CORE-12 | PARTIAL | `unwrap_used`, `expect_used`, `panic`, `todo`, `unimplemented`, `indexing_slicing` | restr, allow | deny (explicit) | Otherwise the same as RS-CAR-28. It also folds in RS-ERR-04 ("the message states the invariant"), which no lint can check. |
| RS-CORE-14 | PARTIAL | `map_err_ignore` | restr, allow | no | |
| RS-CORE-15 | PARTIAL | `missing_panics_doc` | ped, allow | via pedantic | |
| RS-CORE-16 | PARTIAL | `needless_late_init` | style, warn | default | |
| RS-CORE-17 | PARTIAL | `manual_find`, `needless_for_each` | complexity warn; ped allow | default; via pedantic | No lint covers push→collect or accumulate→fold. |
| RS-CORE-27 | PARTIAL | `unsafe_code` (rustc); `undocumented_unsafe_blocks` | allow; restr allow | forbid; deny (explicit) | Confining unsafe to one module and running Miri are not lints. |

### cargo-toolchain.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-CAR-26 | LINT | `lint_groups_priority` | correctness, **deny** | default (deny) | The clippy explain text lists a known problem: it "does not check lints inherited using `lints.workspace = true`". The rule says "Cargo rejects the manifest", but the error it quotes is clippy's message. |
| RS-CAR-27 | LINT | `clippy::pedantic` (group) | allow | warn, priority -1 (explicit) | The row reason should say: allow members one at a time with a reason, never the whole group. |
| RS-CAR-28 | LINT | `unwrap_used`, `expect_used`, `panic`, `todo`, `unimplemented`, `indexing_slicing` | restr, allow | deny (explicit, all 6) | The row must keep the relaxed form (`expect_used` relaxed in tests and binaries). Cargo `[lints]` has no per-target override, so the actual mechanism is clippy.toml `allow-expect-in-tests` / `allow-unwrap-in-tests`, which is not shipped. |
| RS-CAR-29 | LINT | `undocumented_unsafe_blocks` | restr, allow | deny (explicit) | |
| RS-CAR-30 | LINT | `allow_attributes`, `allow_attributes_without_reason` | restr, allow | warn (explicit, both) | |
| RS-CAR-33 | LINT | `linker_messages` (rustc) | warn | default | Row: leave at the default; allow only per platform, with a comment. |
| RS-CAR-04 | PARTIAL | `cargo_common_metadata` | cargo, allow | no | The lint does not require `documentation` or `homepage`, which the rule lists. |
| RS-CAR-13 | PARTIAL (weak) | `negative_feature_names` | cargo, allow | no | Only flags `no-`/`not-` names. It cannot see `cfg(not(feature))` alternatives. |
| RS-CAR-34 | PARTIAL | rustfmt `cargo fmt --check` | tool | rustfmt.toml + ci.yml | The minimal-config policy and the nightly-only caveat go beyond what the tool checks. |
| RS-CAR-36 | PARTIAL | `multiple_crate_versions` | cargo, allow | no | Covers only the duplicate-versions part. License policy and bans need cargo-deny. |
| RS-CAR-38 | PARTIAL | `incompatible_msrv` | suspicious, warn | default (reads `rust-version`) | Only checks std APIs. The pinned CI job and the minimal-versions run are still needed. |

### errors.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-ERR-03 | LINT | the six lints from RS-CAR-28 | restr, allow | deny (explicit) | Duplicates RS-CAR-28. Its inline *Relaxed form* goes into the row. |
| RS-ERR-05 | LINT | `unwrap_used` | restr, allow | deny (explicit) | Exempting tests needs clippy.toml `allow-unwrap-in-tests = true` (not shipped). The doc-example clause belongs to RS-TST-34. |
| RS-ERR-02 | PARTIAL | `unused_must_use` (rustc); `let_underscore_must_use`; `unused_result_ok` | warn; restr allow ×2 | default; no; no | No lint can check "comment the reason". The lint-native equivalent is `#[expect(…, reason)]`. |
| RS-ERR-09 | PARTIAL | `map_err_ignore` | restr, allow | no | Discarding with `.ok()` is not covered. |
| RS-ERR-15 | PARTIAL | `exhaustive_enums` | restr, allow | no | The lint fires unconditionally. The rule has a growth test and a relaxed form. |
| RS-ERR-21 | PARTIAL | `result_large_err`, `large_enum_variant` | perf, warn | default | The default threshold is 128 B, against the rule's 3 words / one cache line. The rule also asks for a size assertion. |
| RS-ERR-25 | PARTIAL | `question_mark` | style, warn | default | A converting `match` that signals a missing `#[from]` is not linted. |
| RS-ERR-29 | PARTIAL (near-LINT) | `or_fun_call`; reverse direction: `unnecessary_lazy_evaluations` | nurs allow; style warn | no; default | Becomes LINT once `or_fun_call` is enabled. I could not confirm it fires on a call nested in a struct literal, which is the rule's own example. |
| RS-ERR-34 | PARTIAL | `manual_let_else` | ped, allow | via pedantic | Misses the Check's own pattern, an `if let` that wraps the rest of the function. |
| RS-ERR-36 | PARTIAL | `missing_panics_doc` | ped, allow | via pedantic | Only sees unwrap, expect, panic and assert, not indexing or division. It cannot judge "the exact condition". |
| RS-ERR-41 | PARTIAL | `arithmetic_side_effects` | restr, allow | no | The lint is all-or-nothing. The rule only covers untrusted operands. |

### concurrency-async.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-CNC-34 | LINT | `unused_async` | ped, allow | via pedantic | |
| RS-CNC-12 | PARTIAL | `unused_must_use` (rustc); `let_underscore_must_use` | warn; restr allow | default; no | Dropping a `JoinHandle` without joining it is not linted. |
| RS-CNC-22 | PARTIAL | `await_holding_lock` (+ `significant_drop_tightening`) | suspicious warn; nurs allow | default; no | The blocking-call half and "compute outside, mutate inside" are not linted. |
| RS-CNC-26 | PARTIAL | `unwrap_used` | restr, allow | deny (explicit) | Catches `.lock().unwrap()`. The poisoning policy itself is the rule. |
| RS-CNC-29 | PARTIAL | `undocumented_unsafe_blocks` (it also covers `unsafe impl`); `non_send_fields_in_send_ty` | restr allow; nurs allow | deny; no | `unsafe_code = "forbid"` in assets rejects manual impls outright. |
| RS-CNC-30 | PARTIAL | `static_mut_refs` (rustc); `non_std_lazy_statics` | warn (deny under edition 2024); ped allow | edition default; via pedantic | The `Mutex<Option<T>>` half is not linted. |
| RS-CNC-31 | PARTIAL | `unused_must_use` (rustc); `let_underscore_future` | warn; suspicious warn | default | Futures collected into a `Vec` and never joined are not linted. |
| RS-CNC-36 | PARTIAL | `async_fn_in_trait` (rustc) | warn | default | The lint forces the Send question on public traits. Making the decision and documenting it is the rule. |
| RS-CNC-39 | PARTIAL (weak) | `let_underscore_future` | suspicious, warn | default | Catches `let _ = spawn(..)`, since a `JoinHandle` is a Future. A bare `spawn(..);` is not linted. |

### cli-apps.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-CLI-28 | PARTIAL | `dbg_macro`; `print_stdout`, `print_stderr` | restr, allow | deny; commented out (library members only) | The logging framework and `-v` / `RUST_LOG` control are not lintable. |

### documentation.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-DOC-01 | LINT | `missing_docs` (rustc) | allow | deny (explicit) | |
| RS-DOC-32 | LINT | `rustdoc::broken_intra_doc_links` | rustdoc, warn | Not in Cargo.toml. Already denied by `assets/ci.yml` (`RUSTDOCFLAGS: -D warnings` + `cargo doc --no-deps --all-features`). | Could also go in `[workspace.lints.rustdoc]`. |
| RS-DOC-03 | PARTIAL | `missing_docs` (rustc) | allow | deny | Checks presence on public modules only. The content requirement (state the role, not the item list) is not linted. |
| RS-DOC-08 | PARTIAL | `missing_docs`; `rustdoc::missing_doc_code_examples` | allow; allow (unstable) | deny; no | Only an unstable lint covers the example half. |
| RS-DOC-10 | PARTIAL | `too_long_first_doc_paragraph` | nurs, allow | no | Length heuristic. |
| RS-DOC-12 | PARTIAL | `missing_errors_doc` | ped, allow | via pedantic | Checks presence only. |
| RS-DOC-13 | PARTIAL | `missing_panics_doc` | ped, allow | via pedantic | Same limits as RS-ERR-36. |
| RS-DOC-14 | PARTIAL | `missing_safety_doc` | style, warn | default | Checks presence on `pub unsafe fn` only. |
| RS-DOC-26 | PARTIAL | `doc_markdown` | ped, allow | via pedantic | Catches `_`, `::` and CamelCase. Misses literals and one-word identifiers (`match`, `Box`), which are the Why's own examples. |

### functional.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-FP-02 | LINT | `needless_return` | style, warn | default | |
| RS-FP-09 | LINT | `match_like_matches_macro` | style, warn | default | |
| RS-FP-20 | LINT | `map_clone`, `filter_map_identity`, `flat_map_identity` | style/complexity, warn | default | The Check already lists exactly these. |
| RS-FP-24 | LINT | `needless_collect` | nurs, allow | no (enable at warn) | Covers the direct form and the indirect one (`let v = …collect(); v.len()`). |
| RS-FP-32 | LINT | `needless_late_init` | style, warn | default | |
| RS-FP-36 | LINT | `manual_inspect` | complexity, warn | default | |
| RS-FP-41 | LINT | `redundant_closure`, `redundant_closure_for_method_calls` | style warn; ped allow | default; via pedantic | |
| RS-FP-01 | PARTIAL | `needless_late_init` | style, warn | default | `let mut x = default;` followed by an overwrite is not linted. |
| RS-FP-03 | PARTIAL | `comparison_chain` | ped, allow | via pedantic | Only `<`/`>`/`==` chains on two operands. |
| RS-FP-06 | PARTIAL | `manual_find` | complexity, warn | default | Only loops shaped as an early `return`. |
| RS-FP-07 | PARTIAL | `needless_for_each` | ped, allow | via pedantic | |
| RS-FP-08 | PARTIAL | `manual_let_else` | ped, allow | via pedantic | Duplicates RS-ERR-34. |
| RS-FP-10 | PARTIAL | `collapsible_if` (+ `collapsible_match`) | style, warn | default | Unverified: the explain text does not show let-chain collapsing. The "split long chains" counterweight is not linted. |
| RS-FP-11 | PARTIAL | `manual_filter_map`, `map_flatten` | complexity, warn | default | `zip`, `windows` and `chunks` are not linted. |
| RS-FP-12 | PARTIAL | `needless_range_loop` | style, warn | default | The Check itself says it catches only "the common shape". Patterns like `v[i+1]` are missed. |
| RS-FP-14 | PARTIAL | `needless_collect` | nurs, allow | no | Only catches `.into_iter()` after a collect, not `.iter()`. |
| RS-FP-15 | PARTIAL | `unnecessary_fold` | style, warn | default | `max_by` with a projection → `max_by_key` is not linted. |
| RS-FP-17 | PARTIAL | `manual_try_fold` | perf, warn | default | A mutable `Result` updated in a loop is not linted. |
| RS-FP-25 | PARTIAL | `needless_range_loop`, `range_zip_with_len` | style/complexity, warn | default | `len() - 1` arithmetic is not linted. |
| RS-FP-31 | PARTIAL | `shadow_unrelated` | restr, allow | no | The scope-size half is not linted. |
| RS-FP-33 | PARTIAL | `missing_const_for_fn` | nurs, allow | no | `static` → `const` is not linted. |
| RS-FP-34 | PARTIAL | `manual_retain` | perf, warn | default | `remove(i)` inside a loop is not linted. |
| RS-FP-48 | PARTIAL | `fn_params_excessive_bools` | ped, allow | via pedantic | Fires above 3 bools. The policy-closure remedy is design advice. |
| RS-FP-57 | PARTIAL | `manual_map` (+ `manual_unwrap_or`; `option_if_let_else` nurs) | style/complexity warn | default | |

### macros.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-MAC-04 | PARTIAL | `missing_docs`, `missing_debug_implementations` (rustc) | allow | deny (explicit) | Error-message quality is not linted. |
| RS-MAC-09 | PARTIAL | `crate_in_macro_def` | suspicious, warn | default | Only covers `crate::` → `$crate`. Rooting paths at `::std` is not linted. |
| RS-MAC-21 | PARTIAL | `unwrap_used`, `expect_used`, `panic` | restr, allow | deny (explicit) | The spanned `syn::Error` design is the rule. |

### api-design.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-API-12 | LINT | `ptr_arg`, `borrowed_box` | style warn; complexity warn | default | |
| RS-API-51 | LINT | `missing_debug_implementations` (rustc) | allow | deny (explicit) | |
| RS-API-01 | PARTIAL | `unreachable_pub` (rustc) | allow | warn (explicit) | |
| RS-API-13 | PARTIAL | `needless_pass_by_value` | ped, allow | via pedantic | Taking `&T` and then cloning it is not linted. |
| RS-API-14 | PARTIAL | `needless_pass_by_value` | ped, allow | via pedantic | Taking `&str` and then calling `to_owned()` is not linted. |
| RS-API-30 | PARTIAL | `fn_params_excessive_bools` | ped, allow | via pedantic | Fires above 3 bools. The rule targets every `bool` parameter. |
| RS-API-38 | PARTIAL | `struct_excessive_bools` | ped, allow | via pedantic | Integer constants and string tags are not linted. |
| RS-API-41 | PARTIAL | `missing_debug_implementations`; `missing_copy_implementations` (rustc); `derive_partial_eq_without_eq` | allow; allow; nurs | deny; no; no | Do not enable `missing_copy_implementations`: it conflicts with RS-API-54. |
| RS-API-46 | PARTIAL | `exhaustive_enums` | restr, allow | no | |
| RS-API-47 | PARTIAL | `must_use_candidate`, `return_self_not_must_use` | ped, allow | via pedantic | Guard and future types need the attribute on the type itself, which no lint asks for. |
| RS-API-52 | PARTIAL | `missing_fields_in_debug` | ped, allow | via pedantic | A `Display` that formats with `{:?}` is not linted. |
| RS-API-55 | PARTIAL | `derived_hash_with_manual_eq`, `derive_ord_xor_partial_ord`, `non_canonical_partial_ord_impl` | correctness deny ×2; suspicious warn | default | Consistency between hand-written impls, and the property tests, are not linted. |
| RS-API-56 | PARTIAL (weak) | `should_implement_trait` | style, warn | default | Flags an inherent `from_str`, not an inherent `parse`. |
| RS-API-57 | PARTIAL | `fallible_impl_from`; `cast_possible_truncation` | nurs allow; ped allow | no; warn (explicit) | |
| RS-API-58 | PARTIAL | `iter_without_into_iter`, `into_iter_without_iter` | ped, allow | via pedantic | `FromIterator` and `Extend` are not linted. |
| RS-API-70 | PARTIAL | `missing_safety_doc` | style, warn | default | The naming and `unsafe` choice are not linted. |
| RS-API-71 | PARTIAL | `exhaustive_enums`, `exhaustive_structs` | restr, allow | no | The lint fires unconditionally. The rule only applies where the shape may grow, and has a relaxed form. |

## Pointers

Each of these has a heading ending in `(see RS-…)`. The body is "Owned by …" plus a two-sentence restatement,
with no **Why:** or **Check:**.

| ID | Target |
|---|---|
| RS-ERR-39 | RS-UNS-24 |
| RS-CLI-31 | RS-ERR-49 |
| RS-API-73 | RS-TRG-30 |

None of the core rules uses the `(see RS-…)` form. All 28 end in a chapter citation by design, so I did
not count them as pointers. Many chapter statements end in a bare `(RS-…)` citation; those are not
pointers either.

## Why-long (Why paragraph > 3 lines)

An asterisk (*) marks a Why that contains an inline *Relaxed form*. Moving that clause out would shorten the paragraph.

| ID | Lines | | ID | Lines | | ID | Lines |
|---|---:|---|---|---:|---|---|---:|
| RS-API-03 | 4 | | RS-API-52 | 4 | | RS-ERR-15* | 5 |
| RS-API-07 | 4 | | RS-API-54 | 4 | | RS-ERR-16 | 4 |
| RS-API-08 | 4 | | RS-API-56 | 4 | | RS-ERR-37 | 4 |
| RS-API-09 | 6 | | RS-API-59 | 4 | | RS-ERR-41* | 4 |
| RS-API-11 | 4 | | RS-API-70 | 4 | | RS-ERR-42 | 4 |
| RS-API-14 | 4 | | RS-API-71* | 4 | | RS-ERR-45 | 4 |
| RS-API-15 | 4 | | RS-API-75 | 4 | | RS-ERR-50 | 4 |
| RS-API-16 | 4 | | RS-API-78 | 4 | | RS-FP-04 | 4 |
| RS-API-17 | 4 | | RS-API-79 | 4 | | RS-FP-16 | 4 |
| RS-API-19 | 5 | | RS-API-80 | 4 | | RS-FP-19 | 4 |
| RS-API-20 | 4 | | RS-API-81 | 4 | | RS-FP-21 | 4 |
| RS-API-21 | 4 | | RS-CAR-34 | 4 | | RS-FP-22 | 4 |
| RS-API-24 | 7 | | RS-CAR-41 | 4 | | RS-FP-26 | 4 |
| RS-API-25 | 5 | | RS-CNC-39 | 4 | | RS-FP-28 | 4 |
| RS-API-26 | 4 | | RS-ERR-01 | 4 | | RS-FP-38 | 5 |
| RS-API-27 | 5 | | RS-ERR-03* | 5 | | RS-FP-44 | 4 |
| RS-API-32 | 4 | | RS-ERR-06 | 4 | | RS-FP-49 | 4 |
| RS-API-38 | 5 | | RS-ERR-07 | 4 | | RS-FP-53 | 4 |
| RS-API-39 | 6 | | RS-ERR-08* | 5 | | RS-FP-59* | 5 |
| RS-API-40 | 5 | | RS-ERR-11 | 4 | | RS-FP-62 | 4 |
| RS-API-45 | 4 | | RS-ERR-12 | 4 | | RS-FP-63 | 4 |
| RS-API-49 | 4 | | RS-ERR-14* | 5 | | RS-FP-64 | 4 |
| | | | | | | RS-MAC-16 | 4 |
| | | | | | | RS-MAC-17 | 4 |

Per chapter: api-design 33, errors 15, functional 15, cargo-toolchain 2, macros 2, concurrency-async 1,
cli-apps 0, documentation 0. RS-CAR-25 has a 2-line Why, followed by a separate 4-line paragraph about
`rust_2018_idioms`. I did not count that paragraph as part of the Why.

## Side findings (not asked for, but they affect the lint table)

1. **Wrong cross-reference and conflicting example.** `cargo-toolchain.md:499` is in the RS-CAR-25
   example. It sets `print_stdout = "deny"` in `[workspace.lints.clippy]` with the comment
   "library members only — see RS-CAR-26". RS-CAR-26 is about `priority = -1`, so the reference points
   to the wrong rule. The example also contradicts `assets/Cargo.toml`, which keeps `print_stdout` out
   of the workspace table because `[lints] workspace = true` is all-or-nothing.
2. **No clippy.toml is shipped, but three rows need one.** RS-CAR-28 and RS-ERR-03/05
   (`allow-expect-in-tests`, `allow-unwrap-in-tests`) and RS-CORE-01
   (`upper-case-acronyms-aggressive`) all depend on clippy.toml settings. RS-CAR-28's "`[lints]`
   override on that target" does not exist, because Cargo `[lints]` is per-package.
3. **Lints that conflict with rules.** Do not cite or enable these:
   - `missing_copy_implementations` conflicts with RS-API-54.
   - `partial_pub_fields` accepts all-public structs, which RS-API-24 forbids.
   - `shadow_reuse` and `shadow_same` conflict with RS-FP-30.
   - `missing_inline_in_public_items` conflicts with RS-API-49.
   - `new_without_default` (on by default) pulls mildly against RS-API-45.
   - `wildcard_imports` exempts `pub use` globs, so it does not help RS-API-02.
4. **Redundant explicit entries in assets.** `cast_possible_truncation`, `cast_precision_loss`,
   `cast_sign_loss` and `float_cmp` are pedantic members already at warn through the group. The
   explicit lines only matter if pedantic is ever turned off.
5. **Examples that do not show their rule.** The example in RS-FP-20 shows `position` and the one in
   RS-FP-41 shows `unzip`; neither illustrates its rule.
6. **Duplicates.** Merging these would also shrink the lint table:
   - RS-ERR-03 = RS-CAR-28 (≈ RS-CORE-12)
   - RS-ERR-34 = RS-FP-08
   - RS-ERR-36 ≈ RS-DOC-13
   - RS-ERR-46 = RS-CLI-20
   - RS-ERR-50 = RS-CLI-22
   - RS-ERR-44 ≈ RS-CLI-02
   - RS-ERR-24 ≈ RS-DOC-16
   - RS-ERR-06 ≈ RS-API-61
   - RS-CNC-13 ≈ RS-FP-49
   - RS-API-08 ≈ RS-DOC-02
   - RS-CAR-10 ≈ RS-DOC-34
7. **Tool-enforced but not by a lint.** Under edition 2024, Cargo itself removes the implicit
   features that RS-CAR-16 (`dep:`) guards against. It stays NONE here because that is Cargo
   behaviour, not a lint.
