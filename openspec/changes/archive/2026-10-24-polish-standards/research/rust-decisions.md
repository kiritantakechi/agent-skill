# rust-style: decisions taken for the apply

What `research/rust.md` left open, decided once, so the chapters edited in parallel agree.

## The `demote` plan

Each merged rule's owner first absorbs what `rust.md` says the merged rule adds. Where a group has
several merged rules, each merges into the owner named.

| Merged | Into | | Merged | Into | | Merged | Into |
|---|---|---|---|---|---|---|---|
| FUNC-33 | OWN-26 | | API-15 | OWN-03 | | API-02 | MOD-15 |
| FUNC-32 | OWN-17 | | API-14 | FUNC-18 | | TEST-06 | MOD-16 |
| PERF-13 | OWN-17 | | API-10 | TRAIT-38 | | API-66 | API-22 |
| PERF-36 | ERR-38 | | OWN-33 | CONC-21 | | API-25 | API-23 |
| NAME-30 | API-34 | | CONC-18 | CONC-22 | | NAME-23 | API-67 |
| NAME-36 | TEST-08 | | CONC-38 | CONC-50 | | API-45 | API-69 |
| API-81 | NAME-27 | | CONC-20 | CONC-50 | | API-70 | API-69 |
| API-73 | BUILD-34 | | TEST-37 | UNSAFE-30 | | ERR-14 | API-69 |
| TRAIT-14 | UNSAFE-20 | | UNSAFE-32 | TEST-25 | | API-48 | PERF-31 |
| CONC-29 | UNSAFE-21 | | UNSAFE-33 | TEST-35 | | API-19 | FUNC-47 |
| TRAIT-20 | CONC-35 | | TEST-19 | TEST-41 | | API-33 | FUNC-47 |
| CLI-33 | OWN-42 | | MOD-31 | PERF-40 | | CLI-15 | FUNC-47 |
| FUNC-43 | CONC-13 | | TEST-31 | PERF-40 | | API-39 | API-27 |
| ERR-37 | OWN-36 | | CLI-01 | MOD-24 | | API-28 | API-27 |
| PERF-25 | CLI-21 | | ERR-41 | CLI-02 | | OWN-06 | API-21 |
| CLI-29 | PERF-26 | | CLI-37 | TEST-30 | | MOD-54 | API-29 |
| PERF-09 | FUNC-12 | | MOD-28 | BUILD-08 | | FUNC-42 | API-29 |
| FUNC-19 | PERF-07 | | MOD-29 | BUILD-25 | | NAME-32 | TRAIT-02 |
| PERF-06 | PERF-07 | | DOC-33 | BUILD-19 | | FUNC-54 | TRAIT-08 |
| OWN-14 | PERF-08 | | TEST-36 | BUILD-20 | | TRAIT-06 | TRAIT-54 |
| PERF-10 | OWN-13 | | BUILD-02 | BUILD-33 | | TRAIT-04 | TRAIT-03 |
| PERF-12 | OWN-13 | | BUILD-15 | NAME-07 | | TRAIT-39 | TRAIT-44 |
| ERR-20 | PERF-20 | | ERR-34 | DOC-13 | | TRAIT-49 | TRAIT-19 |
| API-12 | OWN-02 | | DOC-14 | UNSAFE-04 | | API-71 | TRAIT-30 |
| DOC-16 | ERR-23 | | TEST-32 | DOC-08 | | TRAIT-28 | TRAIT-07 |
| TEST-33 | DOC-27 | | DOC-03 | MOD-01 | | FUNC-40 | TRAIT-18 |
| MOD-10 | MOD-48 | | MOD-11 | API-01 | | TRAIT-53 | UNSAFE-18 |
| API-03 | MOD-22 | | UNSAFE-34 | UNSAFE-14 | | FUNC-46 | FUNC-45 |
| FUNC-13 | FUNC-04 | | FUNC-25 | CONC-40 | | MACRO-07 | MACRO-18 |
| BUILD-49 | MACRO-18 | | MACRO-25 | MACRO-05 | | MACRO-26 | MACRO-16 |
| CLI-09 | CLI-07 | | ERR-33 | ERR-01 | | ERR-26 | ERR-28 |
| ERR-15 | API-05 | | NAME-37 | NAME-11 | | NAME-41 | NAME-11 |
| NAME-43 | NAME-26 | | | | | | |

Demoted to a row that already exists: FUNC-01 (`clippy:needless_late_init`), FUNC-10
(`clippy:needless_range_loop`), API-11 (`clippy:ptr_arg`). NAME-01 becomes two new rows in naming's
table, rustc's `non_camel_case_types` and `non_snake_case`, at the level the shipped configuration
gives them; its FFI exception moves to the unsafe chapter's FFI rule.

The macros fork decides the one group `rust.md` leaves open (#87: MACRO-09, MACRO-17 and MACRO-23,
absolute paths and distinctive generated names for both macro kinds) and reports the merge.

The overlaps `rust.md` resolves without a merge (#31, #43, #62, #70, #74, #80, the cross-reference
list) are deduplicated in place: the shared part stays in the owner, and the other rule cites it.
FUNC-58 and FUNC-31 stay two rules: FUNC-31 keeps the `[M]` floor for `map`, and FUNC-58 cites it.

## Decisions

1. **Tiers.** The owner's tier stands, except that API-67 rises to `[M!]` with NAME-23's relaxed
   form. PERF-31 takes API-48's correct account of cross-crate inlining in place of its stale Why.
2. **Core rules (A.2).**
   - UNSAFE-01 states `unsafe_code = "forbid"` unless `unsafe` is the crate's point, and CORE-27
     cites it.
   - CORE-10 asks for an example on non-trivial items, as DOC-08 does, and cites DOC-08.
   - CORE-12's relaxed form matches ERR-03's.
   - CORE-01 cites NAME-02 for acronyms.
   - CORE-15 is retargeted to ERR-01.
3. **New rows (A.3 "no row", B.2).** A row is added to the owning chapter's table only for a lint
   the shipped configuration enables or a default group carries, at the level it ships at, so
   `citations` verifies it. The rule that lint decides in part names the row in its Check. Nursery
   lints and allow-by-default lints the configuration leaves off are not rows.
4. **The `bool`-parameter decision (#64).** API-29 states it: a flag that selects behaviour splits the
   function; a flag that is data is a two-variant enum; three or more flags read together are an
   options struct or a policy closure.
5. **`*_unchecked` (#45).** UNSAFE-04 is right: a `*_unchecked` function is `unsafe`. API-68 says so.
6. **Edition-2024 changes (B.1 #1, #2, #27)** go to SKILL.md §2's silent changes, and #25's crates
   to the MIG-01 table.
