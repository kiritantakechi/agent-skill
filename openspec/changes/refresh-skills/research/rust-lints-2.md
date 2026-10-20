# rust-style lint classification, part 2

Chapters: naming, ownership, performance, review-checklist, structure, testing, traits-generics,
unsafe-ffi (331 rules; review-checklist has no rules).

Toolchain used for verification: rustc 1.99.0, clippy 0.1.99, rustfmt 1.10.0-stable. I checked every
lint name against `clippy-driver -W help`, `rustc -W help`, `rustdoc -W help` and
`cargo clippy --explain`, and probed edge cases with single-file `clippy-driver`/`rustc` runs in the
scratchpad. No cargo builds were run and nothing in the repo was touched.

Notation for **set in assets?**: `default` means the lint is on by default and assets leaves it
alone. `pedantic` means it is enabled through `pedantic = warn`. `yes: X` means it is set
explicitly. `no` means it is off unless someone enables it.

## Per-chapter counts

| Chapter | Rules | LINT | PARTIAL | Pointer (strict) | Trailing `(RS-…)` cross-ref | Why-long |
|---|---|---|---|---|---|---|
| naming | 44 | 3 | 11 | 0 | 1 | 4 |
| ownership | 46 | 6 | 8 | 0 | 1 | 9 |
| performance | 50 | 3 | 13 | 1 | 12 | 1 |
| structure | 57 | 5 | 6 | 0 | 0 | 15 |
| testing | 42 | 1 | 5 | 0 | 7 | 1 |
| traits-generics | 56 | 0 | 7 | 0 | 1 | 6 |
| unsafe-ffi | 36 | 1 | 13 | 0 | 10 | 1 |
| **Total** | **331** | **19** | **63** | **1** | **32** | **37** |

## Cross-cutting findings (affect the lint table itself)

1. **No `clippy.toml` ships, and that silences several lints on public API.** The clippy setting
   `avoid-breaking-exported-api` defaults to `true`, which suppresses the following lints on
   exported items: `wrong_self_convention`, `enum_variant_names`, `upper_case_acronyms`,
   `box_collection`, `redundant_allocation`, `rc_buffer`, `vec_box`, `trivially_copy_pass_by_ref`,
   `large_types_passed_by_value`, `unnecessary_box_returns` and `needless_pass_by_ref_mut`.
   - Verified by probe: `pub enum Error { IoError, … }`, a `pub fn(Box<Vec<u8>>)` and a `pub` field
     of type `Rc<String>` all went unflagged, while the `pub(crate)` equivalents were flagged.
   - Rows marked † below need `avoid-breaking-exported-api = false` in a shipped `clippy.toml`.
     `upper_case_acronyms` also needs `upper-case-acronyms-aggressive = true`.
2. **The `assets/rustfmt.toml` options are unstable.** Stable rustfmt 1.10.0 does not list
   `group_imports` or `imports_granularity` in `--help=config`, so stable `cargo fmt --check`
   ignores both options. They are only enforced by a nightly fmt job (the file's comment admits
   this).
3. **`module_name_repetitions` is now in `clippy::restriction`, so it is off by default.** The
   assets entry `module_name_repetitions = "allow"` therefore does nothing.
4. **Four explicit warns repeat what pedantic already does.** `cast_possible_truncation`,
   `cast_precision_loss`, `cast_sign_loss` and `float_cmp` are all pedantic lints, so their
   explicit `"warn"` entries duplicate `pedantic = warn`. This is harmless and only documentary.
5. **`unsafe_code = "forbid"` cannot be relaxed per module.** `#[expect]` and `#[allow]` cannot
   override `forbid`, so the unsafe-ffi chapter's "confine unsafe to one module" needs `deny` in
   the workspace table. Under `forbid`, `undocumented_unsafe_blocks = "deny"` is moot.
6. **Two lints are nightly-only.** `rustdoc::missing_doc_code_examples` and
   `implicit_provenance_casts` produce "unknown lint … is unstable" on stable (verified).
7. **Factual slips found in rule text:**
   - RS-NAM-01's **Why:** calls `non_camel_case_types` and `non_snake_case` "clippy's". They are
     rustc lints (the `nonstandard_style` group).
   - RS-OWN-06's **Why:** says hidden-lifetime paths are something "edition 2024 lints against".
     That is wrong: `elided_lifetimes_in_paths` is allow-by-default in every edition. The lint that
     warns by default is `mismatched_lifetime_syntaxes`, and it does so in all editions (verified:
     it fires on `fn iter(&self) -> It`).
   - RS-UNS-24 (and the RS-UNS-11 UB list) say that unwinding out of `extern "C"` "is undefined
     behaviour". Since Rust 1.81, a panic escaping a Rust-defined `extern "C" fn` aborts instead.
     A foreign unwind entering Rust through a `"C"` ABI is still UB. The `catch_unwind` advice still
     holds (it turns an abort into an error code), but the wording should be re-checked.
   - The output-format example in review-checklist.md cites `RS-PRF-11`, which is a pointer rule.
     It should cite `RS-OWN-17`.

## Lint classification

Columns: ID | class | lint(s) | default level / group | set in assets? | note (for PARTIAL, the part
the lint cannot see).

### naming.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-NAM-01 | LINT | `non_camel_case_types`, `non_snake_case`, `non_upper_case_globals` | rustc warn | default | Row reason: allow only on FFI declarations mirroring a C symbol. |
| RS-NAM-02 | LINT† | `clippy::upper_case_acronyms` | style warn, but only fully capitalised names by default | default (needs clippy.toml) | Probe flagged `HTTP` but not `HTTPClient`. Needs `upper-case-acronyms-aggressive = true` plus finding 1. |
| RS-NAM-40 | LINT | `non_upper_case_globals` | rustc warn | default | Probe: fires on `const rows: usize` generic params. |
| RS-NAM-08 | PARTIAL | `clippy::redundant_feature_names` | cargo group, allow | no | Covers `use-`/`with-` (and `-support`). Not `enable-`. |
| RS-NAM-09 | PARTIAL† | `clippy::enum_variant_names` | style warn | default | Probe: silent on `pub enum`. Synonyms of the enum name are not caught. |
| RS-NAM-12 | PARTIAL | `clippy::module_inception` | style warn | default | Only the exact case `foo/foo.rs`. A prefix such as `grep/grep_searcher.rs` is not caught. |
| RS-NAM-13 | PARTIAL† | `clippy::wrong_self_convention` | style warn | default | Enforces that `as_*` takes `&self`/`&mut self`. Does not check "free, no allocation". |
| RS-NAM-15 | PARTIAL† | `clippy::wrong_self_convention` | style warn | default | Enforces that `into_*` takes `self` and that a non-Copy `to_*` does not. Does not check "every self-by-value conversion is `into_`". |
| RS-NAM-18 | PARTIAL | `clippy::misnamed_getters` | suspicious warn | default | Catches a getter returning the wrong field. The `_mut` suffix and setter policy are not covered. |
| RS-NAM-19 | PARTIAL | `clippy::fallible_impl_from` | nursery allow | no | Catches a `From` impl that panics, which should be `TryFrom`. The `try_` naming is not covered. |
| RS-NAM-20 | PARTIAL | `clippy::iter_not_returning_iterator`, `into_iter_without_iter`, `iter_without_into_iter` | pedantic allow | pedantic | The "other iterator methods name what they yield" part is not covered. |
| RS-NAM-23 | PARTIAL | `clippy::should_implement_trait` | style warn | default | Only std-trait method names (`from_str`, `from_iter`, …), not arbitrary inherent `from_*`. |
| RS-NAM-29 | PARTIAL | `clippy::many_single_char_names` | pedantic allow | pedantic | Counts single-char bindings in scope. The "lives longer than ~10 lines" limit is not covered. |
| RS-NAM-36 | PARTIAL | `clippy::redundant_test_prefix` | restriction allow | no | Covers the `test_` prefix only. Behaviour-sentence naming is not covered. |

### ownership.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-OWN-02 | LINT | `clippy::ptr_arg` + `clippy::needless_pass_by_value` | style warn; pedantic allow | default; pedantic | The Check is exactly these two. Also duplicates RS-API-12. |
| RS-OWN-06 | LINT | `elided_lifetimes_in_paths` + `mismatched_lifetime_syntaxes` + `clippy::elidable_lifetime_names` | rustc allow; rustc warn; pedantic allow | yes: warn; default; pedantic | Probe: all three fire. Fix the Why (finding 7). |
| RS-OWN-07 | LINT | `clippy::needless_lifetimes` + `clippy::elidable_lifetime_names` (+ `extra_unused_lifetimes`) | complexity warn; pedantic allow; complexity warn | default; pedantic | Probe: `impl<'a> Q<'a>` is flagged. |
| RS-OWN-14 | LINT | `clippy::clone_on_ref_ptr` | restriction allow | no, so enable warn | Suggests `Arc::clone(&x)`, which is exactly the rule. |
| RS-OWN-15 | LINT | `clippy::str_to_string` | restriction allow | no, so enable warn | Flags only `to_string`, so `String::from` stays allowed, as the rule says. |
| RS-OWN-36 | LINT† | `clippy::box_collection`, `clippy::redundant_allocation`, `clippy::rc_buffer` | perf warn; perf warn; restriction allow | default; default; no, so enable warn | Probe: all are silent on `pub` signatures and fields (finding 1). |
| RS-OWN-01 | PARTIAL | `needless_pass_by_value`, `trivially_copy_pass_by_ref`, `large_types_passed_by_value` (pedantic); `needless_pass_by_ref_mut` (nursery) | allow | pedantic; nursery no | They catch over-strong signatures. The read/change/own contract is a judgement. |
| RS-OWN-16 | PARTIAL | `clippy::cmp_owned`, `manual_ignore_case_cmp`, `unnecessary_to_owned` | perf warn | default | Covers the compare and borrow-only cases. Not `format!` inside conditions. |
| RS-OWN-31 | PARTIAL | `clippy::non_std_lazy_statics` | pedantic allow | pedantic | Covers `lazy_static!`/`once_cell` → `LazyLock`. Not `RefCell<Copy>` → `Cell`. |
| RS-OWN-32 | PARTIAL | `clippy::await_holding_refcell_ref` | suspicious warn | default | Only borrows held across `.await`. |
| RS-OWN-33 | PARTIAL | `clippy::arc_with_non_send_sync` | suspicious warn | default | Only `Arc<!Send/!Sync>`. Not "Arc that never crosses a thread". |
| RS-OWN-35 | PARTIAL | `clippy::boxed_local`, `unnecessary_box_returns` | perf warn; pedantic allow | default; pedantic | Catches needless boxes. The three legitimate reasons are a judgement. |
| RS-OWN-43 | PARTIAL (near-LINT) | `let_underscore_lock` + `let_underscore_drop` | rustc deny; rustc allow | default; no | Probe: `let_underscore_lock` catches `let _ = m.lock()` and `r.read()`. RefCell and `Span::enter` guards need `let_underscore_drop`, which flags every Drop type (noisy). |
| RS-OWN-44 | PARTIAL | `clippy::mem_forget` | restriction allow | yes: deny | Only `mem::forget` on Drop types. Not `ManuallyDrop` or "confine to the owning module". |

### performance.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-PRF-19 | LINT | `clippy::map_entry` | perf warn | default | The Check's `get_mut` variant is not covered (minor). |
| RS-PRF-23 | LINT | `clippy::needless_range_loop` (+ `indexing_slicing`) | style warn; restriction | default; yes: deny | Duplicates RS-FP-12. |
| RS-PRF-35 | LINT | `clippy::inline_always` | pedantic allow | pedantic | The suppression `#[expect(…, reason = "<benchmark>")]` carries the "measurement" requirement. |
| RS-PRF-06 | PARTIAL | `clippy::vec_init_then_push` | perf warn | default | Only `new()` plus immediate pushes. Not "a loop with a known bound". |
| RS-PRF-09 | PARTIAL | `clippy::needless_collect` | nursery allow | no | Nursery lint with false positives. Duplicates RS-FP-14. |
| RS-PRF-12 | PARTIAL | `clippy::format_push_string`, `format_collect` | pedantic allow | pedantic | A plain `format!` in a loop is not covered. |
| RS-PRF-13 | PARTIAL | `clippy::cmp_owned`, `unnecessary_to_owned` | perf warn | default | Duplicates RS-OWN-16. |
| RS-PRF-21 | PARTIAL | `clippy::large_enum_variant`, `result_large_err` | perf warn | default | Cache-line sizing of structs is not covered. |
| RS-PRF-22 | PARTIAL | `clippy::large_enum_variant`, `result_large_err` | perf warn | default | The `const` size assertion is not covered. |
| RS-PRF-24 | PARTIAL | `clippy::chunks_exact_to_as_chunks` | style warn | default | Covers only the Check's last sentence. |
| RS-PRF-25 | PARTIAL | `clippy::stable_sort_primitive`, `unnecessary_sort_by` | pedantic allow; complexity warn | pedantic; default | Key cost, `sort_by_cached_key` and `select_nth` are not covered. |
| RS-PRF-29 | PARTIAL (minor) | `unused_must_use` | rustc warn | default | Only an ignored `flush()` result. A missing flush is not covered. |
| RS-PRF-30 | PARTIAL | `clippy::unbuffered_bytes` | perf warn | default | Only `.bytes()` on an unbuffered reader. |
| RS-PRF-38 | PARTIAL | `clippy::regex_creation_in_loops` | perf warn | default | Only `Regex::new`. |
| RS-PRF-40 | PARTIAL | `clippy::arithmetic_side_effects` | restriction allow | no | Flags all arithmetic, which is broader than "untrusted paths". Duplicates RS-ERR-41. |
| RS-PRF-41 | PARTIAL | `cast_possible_truncation`, `cast_sign_loss`, `cast_possible_wrap`, `as_conversions` | pedantic / restriction | yes: warn ×2; pedantic; no | The choice of integer width is not covered. |

### structure.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-STR-06 | LINT | `clippy::mod_module_files` | restriction allow | no, so enable warn | Must run with `--all-targets` so `tests/**/mod.rs` is seen. Never enable the opposite lint, `self_named_module_files`. |
| RS-STR-16 | LINT (borderline) | `unreachable_pub` | rustc allow | yes: warn | The lint accepts items reachable through a `pub mod`. The "re-exported at root" half lives in STR-17/STR-19. |
| RS-STR-44 | LINT | rustfmt `group_imports = "StdExternalCrate"` | rustfmt, unstable | assets/rustfmt.toml | Nightly fmt only (finding 2). |
| RS-STR-45 | LINT | rustfmt `imports_granularity = "Crate"` | rustfmt, unstable | assets/rustfmt.toml | Nightly fmt only. |
| RS-STR-46 | LINT | `clippy::wildcard_imports` (+ `enum_glob_use`) | pedantic allow | pedantic | It has built-in exemptions for `use super::*` in test modules and for `prelude` modules, which are the rule's exceptions. |
| RS-STR-01 | PARTIAL | `missing_docs`; `clippy::missing_docs_in_private_items` | rustc allow; restriction | yes: deny; no | `missing_docs` covers public modules only. The concept and noun-name parts are not covered. |
| RS-STR-09 | PARTIAL | `clippy::items_after_test_module` | style warn | default | Neither `use super::*` nor "no `tests/unit/`" is covered. Duplicates RS-TST-04. |
| RS-STR-13 | PARTIAL | `unreachable_pub` | rustc allow | yes: warn | The `pub(super)` vs `pub(crate)` ladder is not covered. |
| RS-STR-51 | PARTIAL | `clippy::multiple_inherent_impl` | restriction allow | no | Covers only the Check's question. The ordering is not covered. |
| RS-STR-53 | PARTIAL | `clippy::too_many_lines` (+ `excessive_nesting`) | pedantic allow; complexity warn | pedantic; inert | `excessive_nesting` does nothing without a clippy.toml threshold. |
| RS-STR-56 | PARTIAL | `clippy::fn_params_excessive_bools` | pedantic allow | pedantic | Only more than 3 bool mode flags. |

### testing.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-TST-17 | LINT | `clippy::should_panic_without_expect` | pedantic allow | pedantic | The "prefer a returned Err" clause fits in the row's reason. |
| RS-TST-04 | PARTIAL | `clippy::items_after_test_module`, `tests_outside_test_module` | style warn; restriction | default; no | Duplicates RS-STR-09. |
| RS-TST-07 | PARTIAL | `clippy::mod_module_files` | restriction allow | no | The `#[path]` remedy and "every `tests/*.rs` has a `#[test]`" are not covered. |
| RS-TST-08 | PARTIAL | `clippy::redundant_test_prefix` | restriction allow | no | Numbering and sentence names are not covered. Duplicates RS-NAM-36. |
| RS-TST-12 | PARTIAL | `clippy::manual_assert_eq`, `assert_is_empty`, `bool_assert_comparison` | pedantic; pedantic; style warn | pedantic; default | Compound `&&` "shape" asserts are not covered. |
| RS-TST-33 | PARTIAL (nightly) | `rustdoc::missing_doc_code_examples` | rustdoc allow, unstable | no | Gives "unknown lint" on stable. |

### traits-generics.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-TRG-06 | PARTIAL | `clippy::panic`, `todo`, `unimplemented` | restriction | yes: deny | Not `Err(Unsupported)` or no-op defaults. |
| RS-TRG-20 | PARTIAL | `async_fn_in_trait`; `clippy::future_not_send` | rustc warn; nursery | default; no | Probe: fires on a public trait. Documenting the decision is not covered. |
| RS-TRG-24 | PARTIAL (weak) | `clippy::type_complexity` | complexity warn | default | Only a score threshold, not nesting depth. |
| RS-TRG-35 | PARTIAL | `clippy::multiple_bound_locations` | style warn | default | Inline vs `where` by length is not covered. |
| RS-TRG-37 | PARTIAL | `clippy::implied_bounds_in_impls`; `trait_duplication_in_bounds`, `type_repetition_in_bounds` | complexity warn; nursery | default; no | Only redundant bounds, not unnecessary distinct ones. |
| RS-TRG-42 | PARTIAL | `clippy::type_complexity` | complexity warn | default | The crate `Result<T>` alias is not covered. |
| RS-TRG-55 | PARTIAL | `clippy::panic`, `todo`, `unimplemented` | restriction | yes: deny | Same as TRG-06, which it overlaps. |

### unsafe-ffi.md

| ID | Class | Lint | Default level | Set in assets? | Note |
|---|---|---|---|---|---|
| RS-UNS-06 | LINT | `unsafe_op_in_unsafe_fn` | rustc: allow ≤2021, warn in 2024 | default (edition 2024) | |
| RS-UNS-03 | PARTIAL | `clippy::undocumented_unsafe_blocks` | restriction | yes: deny | Checks presence only, not "why it holds here". Overlaps RS-CAR-29. |
| RS-UNS-04 | PARTIAL | `clippy::missing_safety_doc` | style warn | default | Checks presence on public items only. Checkability and `*_unchecked` are not covered. |
| RS-UNS-05 | PARTIAL (near-LINT) | `clippy::multiple_unsafe_ops_per_block` | restriction allow | no | Counts unsafe ops. Safe statements inside the block are not covered. |
| RS-UNS-07 | PARTIAL | `clippy::not_unsafe_ptr_arg_deref` | correctness deny | default | Only the raw-pointer-argument subset. |
| RS-UNS-12 | PARTIAL (narrow) | `clippy::mut_from_ref` | correctness deny | default | Only `&T -> &mut T` signatures. |
| RS-UNS-13 | PARTIAL | `invalid_value`, `deprecated`; `clippy::uninit_assumed_init`, `uninit_vec` | rustc warn; correctness deny | default | The "every byte written" proof is not covered. |
| RS-UNS-14 | PARTIAL | `improper_ctypes`, `improper_ctypes_definitions` | rustc warn | default | Only FFI signatures. Byte-mapped types and the size assertion are not covered. |
| RS-UNS-15 | PARTIAL | `unnecessary_transmutes` (rustc); `useless_transmute`, `transmutes_expressible_as_ptr_casts`, `missing_transmute_annotations`, `unsound_collection_transmute`; `transmute_undefined_repr` | warn/deny by default; last one nursery | default; last no | "Last resort" ordering is not covered. |
| RS-UNS-16 | PARTIAL (near-LINT) | `clippy::cast_ptr_alignment` | pedantic allow | pedantic | Only `as`/`.cast()` pointer casts. Misalignment via `from_raw_parts` or transmute is not covered. |
| RS-UNS-17 | PARTIAL (nightly) | `implicit_provenance_casts`; `clippy::manual_dangling_ptr` | rustc allow, unstable; style warn | no; default | The provenance lint is unknown on stable. |
| RS-UNS-21 | PARTIAL | `clippy::undocumented_unsafe_blocks` (also covers `unsafe impl`); `non_send_fields_in_send_ty` | restriction; nursery | yes: deny; no | Checks presence only. Overlaps RS-CNC-29. |
| RS-UNS-27 | PARTIAL | `clippy::manual_c_str_literals` | complexity warn | default | Only the `c"…"` sentence. |
| RS-UNS-28 | PARTIAL | `improper_ctypes` | rustc warn | default | The layout assertion is not covered. |

### Considered and rejected (do not cite)

These lints look related but are broader than the rule, or contradict it.

| Rule | Lint | Why rejected |
|---|---|---|
| NAM-29 | `min_ident_chars` (restriction) | Bans every short identifier the rule allows. |
| NAM-38 | `single_char_lifetime_names` (restriction) | Bans the lone `'a` the rule allows. |
| NAM-35 | `error_impl_error` (restriction); `module_name_repetitions` | The first contradicts the `io::Error` spelling. The second flags `parse::ParseError`. |
| STR-06 | `self_named_module_files` | The opposite policy. |
| STR-13/14/15 | `redundant_pub_crate` (nursery) | Pushes `pub(crate)` → `pub`, fighting `unreachable_pub`. |
| STR-17 | `pub_use` (restriction) | Bans `pub use` outright. |
| STR-20 | `wildcard_imports` | Probe: does **not** fire on `pub use inner::*`, so STR-20 has no lint. |
| STR-50 | `arbitrary_source_item_ordering` | Enforces a different order (by kind, then alphabetical). |
| TST-13 | `missing_assert_message` | Demands a message on every assert. |
| TRG-17 | `impl_trait_in_params` | Bans all argument-position `impl Trait`, contradicting TRG-15. |
| TRG-35 | `inline_trait_bounds` | Forces `where` for all bounds. |
| PRF-34 | `missing_inline_in_public_items` | The opposite of the rule. |
| OWN-12 | `redundant_clone` (nursery) | Finds dead clones, not borrow-silencing ones. |
| STR-36 | cargo's "virtual workspace defaulting to resolver" warning | A Cargo diagnostic, not a rustc/clippy/rustfmt lint, so out of scope. |

## Pointers

### Strict (`(see RS-…)`)

| ID | Target | Shape |
|---|---|---|
| RS-PRF-11 | RS-OWN-17 | The heading carries `(see RS-OWN-17)`. The body opens "Owned by `references/ownership.md` RS-OWN-17", then 2 sentences. It has no **Why:** or **Check:**. |

Outside these chapters: RS-ERR-39 → RS-UNS-24, and RS-API-73 → RS-TRG-30.

### Statement ends in a bare `(RS-…)` cross-reference (dup = restates the target)

| ID | Target | Dup? |
|---|---|---|
| RS-NAM-38 | RS-OWN-06 | No (last sentence only) |
| RS-OWN-02 | RS-API-12 | **Dup.** The statement is just examples plus the ref. |
| RS-PRF-07 | RS-FP-22 | Partial overlap |
| RS-PRF-09 | RS-FP-14 | **Dup** |
| RS-PRF-13 | RS-OWN-16 | **Dup** (subset) |
| RS-PRF-14 | RS-OWN-20 | **Dup** (also RS-FP-37) |
| RS-PRF-16 | RS-OWN-27 | Overlap |
| RS-PRF-21 | RS-ERR-21 | Overlap |
| RS-PRF-23 | RS-FP-12 | **Dup** |
| RS-PRF-29 | RS-OWN-40 | Related |
| RS-PRF-34 | RS-API-49 | **Dup** |
| RS-PRF-37 | RS-TRG-16 | **Dup**-ish |
| RS-PRF-40 | RS-ERR-41 | **Dup** |
| RS-PRF-44 | RS-STR-33 | Overlap |
| RS-TST-06 | RS-STR-18 | **Dup** |
| RS-TST-08 | RS-NAM-36 | **Dup** |
| RS-TST-25 | RS-TST-22 | Related |
| RS-TST-32 | RS-PRF-44 | **Dup** (the CI half of PRF-44) |
| RS-TST-33 | RS-DOC-08 | Overlap |
| RS-TST-37 | RS-CAR-20 | Overlap, slightly in tension (three configs vs "the powerset that matters") |
| RS-TST-38 | RS-UNS-30, RS-CNC-45 | **Dup** |
| RS-TRG-55 | RS-TRG-01, RS-TRG-06 | Overlaps TRG-06 |
| RS-UNS-03 | RS-CAR-29 | Overlap (UNS-03 adds content quality) |
| RS-UNS-04 | RS-DOC-14 | **Dup** (+ `*_unchecked`) |
| RS-UNS-10 | RS-TST-24 | Related |
| RS-UNS-18 | RS-TRG-54 | **Dup of RS-OWN-25** (the same four PhantomData cases) |
| RS-UNS-19 | RS-TST-36 | Related |
| RS-UNS-20 | RS-TRG-14 | **Dup** |
| RS-UNS-21 | RS-CNC-29 | **Dup** |
| RS-UNS-24 | RS-ERR-39 | UNS-24 is the owner; ERR-39 is the pointer |
| RS-UNS-32 | RS-TST-26 | **Dup**-ish |
| RS-UNS-33 | RS-TST-36 | **Dup** |

### Mirrored pairs that reference each other in **Why:** rather than the statement

These came from a scan for mutual references.

- **Same title, or nearly:**
  - RS-OWN-22 ↔ RS-TRG-39 (`'static` unless spawn/erase/store)
  - RS-STR-09 → RS-TST-04 (tests module at the bottom; one-directional)
  - RS-OWN-25 → RS-UNS-18 (PhantomData)
  - RS-OWN-30 ↔ RS-FP-38 (justify interior mutability)
  - RS-OWN-46 ↔ RS-CLI-34 (process-wide resources)
  - RS-PRF-28 ↔ RS-CLI-21 (lock stdout)
  - RS-STR-24 ↔ RS-API-03 (one crate, one purpose)
  - RS-STR-01 ↔ RS-DOC-03 (module `//!`)
  - RS-TST-31 ↔ RS-CLI-38 (CLI end-to-end)
  - RS-OWN-40 ↔ RS-ERR-40 (infallible Drop)
- **Overlapping:**
  - RS-STR-02 ↔ RS-NAM-06, RS-STR-26 ↔ RS-CLI-01, RS-TRG-02 ↔ RS-NAM-32, RS-TRG-08 ↔ RS-FP-60,
    RS-TRG-51 ↔ RS-FP-56, RS-TRG-38 ↔ RS-API-11, RS-TRG-20 ↔ RS-CNC-36, RS-NAM-31 ↔ RS-CLI-14,
    RS-STR-06 ↔ RS-TST-07
- No dangling references were found in these chapters.

## Why-long (more than 3 wrapped lines)

All lines are at most 100 columns, so source lines equal wrapped lines.

| ID | Lines |
|---|---|
| RS-NAM-06 | 5 |
| RS-NAM-23 | 5 |
| RS-NAM-30 | 4 |
| RS-NAM-31 | 4 |
| RS-OWN-03 | 4 |
| RS-OWN-05 | 4 |
| RS-OWN-10 | 4 |
| RS-OWN-12 | 4 |
| RS-OWN-22 | 4 |
| RS-OWN-28 | 4 |
| RS-OWN-30 | 5 |
| RS-OWN-32 | 4 |
| RS-OWN-40 | 4 |
| RS-PRF-24 | 6 |
| RS-STR-01 | 4 |
| RS-STR-02 | 4 |
| RS-STR-06 | 5 |
| RS-STR-14 | 7 |
| RS-STR-16 | 5 |
| RS-STR-17 | 4 |
| RS-STR-24 | 4 |
| RS-STR-36 | 7 |
| RS-STR-37 | 5 |
| RS-STR-38 | 5 |
| RS-STR-39 | 5 |
| RS-STR-40 | 4 |
| RS-STR-43 | 5 |
| RS-STR-53 | 4 |
| RS-STR-55 | 4 |
| RS-TST-07 | 5 |
| RS-TRG-01 | 5 |
| RS-TRG-14 | 4 |
| RS-TRG-16 | 4 |
| RS-TRG-19 | 4 |
| RS-TRG-20 | 5 |
| RS-TRG-22 | 4 |
| RS-UNS-01 | 4 |

Other shape notes:

- Many ownership, structure and traits-generics rules have no statement paragraph. The heading is
  the statement, and the body is **Why:** + **Check:** (for example RS-OWN-03, RS-STR-03, RS-TRG-03).
- Every performance rule's statement repeats its heading as its first sentence.

## review-checklist.md: shape

The file is titled "Review protocol" and is 140 lines long. It is not a rule file: it has **no IDs
of its own** and no `### RS-` headings. SKILL.md's chapter table lists it with prefix "—".

Its sections, in order:

1. **Severity model.** A 6-row table (Unsound / Incorrect / Contract / Design / Performance / Style)
   with meaning and examples, followed by a blocking policy: Unsound and Incorrect block; Contract
   blocks a release; Design and Performance need a decision; Style is batched.
2. **Review order.** Nine numbered stages: soundness → panics → public API → concurrency → data
   model → bodies → tests → symmetry → manifest. Each stage ends with a parenthetical that
   references rules in one of three ways:
   - by family prefix: `(RS-UNS)`, `(RS-CNC)`;
   - by family plus one ID: `(RS-ERR, RS-PRF-40)`;
   - by ID range: `(RS-API-28 … RS-API-37)`, `(RS-API-79 … RS-API-84, RS-STR-54 … RS-STR-57)`.

   It never cites individual rules per item.
3. **Mechanical pass.** A bash block with 8 commands (fmt, clippy, test ×2, doc, semver-checks,
   miri, audit) and 8 "fast greps". Five or six of the greps duplicate lints the assets already
   enable:

   | Grep | Lint that already covers it |
   |---|---|
   | `.unwrap()` / `.expect(` | `unwrap_used` / `expect_used` (deny) |
   | `unsafe {` without SAFETY | `undocumented_unsafe_blocks` |
   | `as u32` etc. | `cast_possible_truncation` |
   | `&Vec` | `ptr_arg` |
   | `dbg!` | `dbg_macro` (`print_stdout` is commented out in assets) |
   | lock across `.await` | `await_holding_lock` (suspicious warn) |

4. **Output format.** A markdown table template (Severity | Rule | Location | Finding | Fix) with 3
   example rows citing RS-ERR-03, RS-API-30 and RS-PRF-11. RS-PRF-11 is the pointer rule; it should
   be RS-OWN-17. A "Discussion" section follows.
5. **Rules for the review itself.** Six bold-led bullets: cite the rule ID, give the fix, no
   praise-only reviews, no padding, separate wrong from preference, say what you did not check.
6. **Refactoring a codebase to this standard.** Six ordered, one-commit-per-step steps.

All cited IDs resolve.

**Second checklist in SKILL.md.** SKILL.md §5 "Review checklist" is a separate list with 14
question-form items: Soundness, Panics, Silent numerics, Errors, Public surface, Signatures,
Concurrency, Data model, Bodies, Resources, Tests, Symmetry, Manifest, Why. Only item 12 cites IDs
(ranges). It points to review-checklist.md for "the full protocol". The two lists diverge:

- SKILL.md has 14 items; the file has 9 stages.
- SKILL.md's Silent numerics, Errors, Signatures, Resources and Why have no counterpart stage in the
  file.

For a cross-skill standard shape, the reusable parts are:

- a severity table;
- an ordered review pass whose items cite rule IDs or ranges;
- a mechanical pass, which is mostly redundant with the lint table once that exists;
- an output-format template;
- review etiquette;
- the refactor order.
