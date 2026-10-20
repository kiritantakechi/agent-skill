# Migration: Editions, Releases, and What Replaced What

Scope: what changed under existing Rust code — the 2024 edition, the stable releases since, the
crates the standard library has replaced, and the APIs it has deprecated — and the rule IDs this
standard used before its current revision.

## Contents

- RS-MIG-01 [M] Reach for the standard-library feature that replaced a crate
- RS-MIG-02 [M] Do not call an API deprecated through 1.99
- RS-MIG-03 [M] Re-read what changed silently on every toolchain bump

---

## What replaced what

### RS-MIG-01 [M] Reach for the standard-library feature that replaced a crate

| Reach for this | Not this | Since |
|---|---|---|
| `OnceLock`, `LazyLock` | `lazy_static`, `once_cell` for the common cases | 1.70 / 1.80 |
| `cfg_select!` | `cfg-if` | 1.95 |
| `<int>::format_into(&mut NumBuffer)` | `itoa` | 1.98 |
| `File::lock`, `try_lock`, `lock_shared` | `fs2`, `fs4`, `fd-lock` for a whole-file advisory lock | 1.89 |
| `fs::set_times`, `File::set_times` | `filetime` | 1.99 |
| `io::pipe` | `os_pipe` | 1.87 |
| `assert_matches!`, imported from `std` | the `assert_matches` crate, `assert!(matches!(..))` | 1.96 |
| `async fn` and `impl Trait` in traits | `#[async_trait]` where no `dyn` is needed | 1.75 |
| async closures and `AsyncFn*` bounds | an `F: Fn() -> Fut, Fut: Future` pair | 1.85 |
| trait upcasting, including to `dyn Any` | a hand-written `fn as_any(&self) -> &dyn Any` | 1.86 |
| `Atomic*::update`, `try_update` | a `compare_exchange` loop, `fetch_update` | 1.95 |
| `strict_*` arithmetic | `checked_*().expect(..)` where overflow is a bug | 1.91 |
| `extract_if` on `Vec`, `HashMap`, `BTreeMap` | `retain` plus a second collection | 1.87 / 1.88 / 1.91 |
| `env::home_dir` | `home`, or `dirs::home_dir` for `$HOME` alone | 1.87 |
| `thread::scope` | `Arc` and `'static` to borrow into a thread | 1.63 |
| `let ... else` | a `match` with a `_ => return` arm | 1.65 |
| `c"…"` literals | a hand-terminated byte array | 1.77 |
| `#[expect(lint, reason = "…")]` | an `#[allow]` nobody removes | 1.81 |
| `[lints]` in `Cargo.toml` | `#![deny(...)]` in `lib.rs` | 1.74 |
| `CARGO_BUILD_WARNINGS=deny` | `RUSTFLAGS="-Dwarnings"`, which invalidates the cache | 1.97 |

**Why:** a dependency the standard library covers is code to audit, update and build for nothing,
and the crate's spelling outlives the reason it existed. The std version is also the one every
reader already knows.

**Check:** each hit is a dependency the standard library now covers.
`rg -n '^(lazy_static|cfg-if|itoa|fs2|fs4|filetime) *=' Cargo.toml` and
`rg -n '^(os_pipe|assert_matches|async-trait) *=' Cargo.toml`

### RS-MIG-02 [M] Do not call an API deprecated through 1.99

`Atomic*::fetch_update` is deprecated in 1.99: use `update` or `try_update`. The module constants
`std::i32::MAX` and the rest are deprecated too: use the associated `i32::MAX`.

**Why:** a deprecation warns, and `CARGO_BUILD_WARNINGS=deny` turns the warning into a failed
build — so a toolchain bump breaks CI on code that has not changed.

**Check:** `rg -n '\.fetch_update\(|std::[iu](8|16|32|64|128|size)::(MAX|MIN)\b' src/`

## What changed silently

### RS-MIG-03 [M] Re-read what changed silently on every toolchain bump

Each of these compiles before and after, and behaves differently:

| Since | What changed |
|---|---|
| 1.99 | Cargo turns incremental compilation off when `CI` is set |
| 1.99 | an exhausted `RangeInclusive` reports different `start()` and `end()`, and slices differently |
| 1.98 | a derived `PartialOrd` beside a derived `Ord` takes the `Ord` path, so the two can no longer disagree |
| 1.97 | v0 symbol mangling is the default, and `linker_messages` warns outside the `warnings` group |
| 1.96 | `BTreeMap::append` may panic when the key's `Ord` is inconsistent |
| 1.95 | a `#[non_exhaustive]` match reads the discriminant, which changes what a closure captures |
| 1.94 | closure captures around patterns move, and a `Drop` can run at a different point |
| 1.91 | bindings drop in the order they are written, and panic messages carry the thread ID |

**Why:** nothing fails when these change, so the only defence is reading them against the code at
the moment the toolchain moves. A version bump that skips this step ships behaviour nobody chose.

**Check:** a review matter: on a toolchain bump, read each row newer than the old toolchain against
the diff's feature sets, `Ord` impls, drop order and anything that parses panic messages.

## Rule IDs before the Rust 1.99 revision

Before the revision the families ran `RS-API-01`–`RS-API-84`, `RS-CAR-01`–`RS-CAR-54`,
`RS-CLI-01`–`RS-CLI-40`, `RS-CNC-01`–`RS-CNC-52`, `RS-DOC-01`–`RS-DOC-40`, `RS-ERR-01`–`RS-ERR-50`,
`RS-FP-01`–`RS-FP-64`, `RS-MAC-01`–`RS-MAC-26`, `RS-NAM-01`–`RS-NAM-44`, `RS-OWN-01`–`RS-OWN-46`,
`RS-PRF-01`–`RS-PRF-50`, `RS-STR-01`–`RS-STR-57`, `RS-TST-01`–`RS-TST-42`, `RS-TRG-01`–`RS-TRG-56`
and `RS-UNS-01`–`RS-UNS-36`. The table lists every ID in those ranges that changed, and what it is
now; an ID it does not list is unchanged.

| Before | Now |
|---|---|
| `RS-API-08` | `RS-DOC-02` |
| `RS-API-09` | `RS-API-08` |
| `RS-API-10` | `RS-API-09` |
| `RS-API-11` | `RS-API-10` |
| `RS-API-12` | `RS-API-11` |
| `RS-API-13` | `RS-API-12` |
| `RS-API-14` | `RS-API-13` |
| `RS-API-15` | `RS-API-14` |
| `RS-API-16` | `RS-API-15` |
| `RS-API-17` | `RS-API-16` |
| `RS-API-18` | `RS-API-17` |
| `RS-API-19` | `RS-API-18` |
| `RS-API-20` | `RS-API-19` |
| `RS-API-21` | `RS-API-20` |
| `RS-API-22` | `RS-API-21` |
| `RS-API-23` | `RS-API-22` |
| `RS-API-24` | `RS-API-23` |
| `RS-API-25` | `RS-API-24` |
| `RS-API-26` | `RS-API-25` |
| `RS-API-27` | `RS-API-26` |
| `RS-API-28` | `RS-API-27` |
| `RS-API-29` | `RS-API-28` |
| `RS-API-30` | `RS-API-29` |
| `RS-API-31` | `RS-API-30` |
| `RS-API-32` | `RS-API-31` |
| `RS-API-33` | `RS-API-32` |
| `RS-API-34` | `RS-API-33` |
| `RS-API-35` | `RS-API-34` |
| `RS-API-36` | `RS-API-35` |
| `RS-API-37` | `RS-API-36` |
| `RS-API-38` | `RS-API-37` |
| `RS-API-39` | `RS-API-38` |
| `RS-API-40` | `RS-API-39` |
| `RS-API-41` | `RS-API-40` |
| `RS-API-42` | `RS-API-41` |
| `RS-API-43` | `RS-API-42` |
| `RS-API-44` | `RS-API-43` |
| `RS-API-45` | `RS-API-44` |
| `RS-API-46` | `RS-API-45` |
| `RS-API-47` | `RS-API-46` |
| `RS-API-48` | `RS-API-47` |
| `RS-API-49` | `RS-API-48` |
| `RS-API-50` | `RS-API-49` |
| `RS-API-51` | `RS-API-50` |
| `RS-API-52` | `RS-API-51` |
| `RS-API-53` | `RS-API-52` |
| `RS-API-54` | `RS-API-53` |
| `RS-API-55` | `RS-API-54` |
| `RS-API-56` | `RS-API-55` |
| `RS-API-57` | `RS-API-56` |
| `RS-API-58` | `RS-API-57` |
| `RS-API-59` | `RS-API-58` |
| `RS-API-60` | `RS-API-59` |
| `RS-API-61` | `RS-ERR-05` |
| `RS-API-62` | `RS-API-60` |
| `RS-API-63` | `RS-API-61` |
| `RS-API-64` | `RS-API-62` |
| `RS-API-65` | `RS-API-63` |
| `RS-API-66` | `RS-API-64` |
| `RS-API-67` | `RS-API-65` |
| `RS-API-68` | `RS-API-66` |
| `RS-API-69` | `RS-API-67` |
| `RS-API-70` | `RS-API-68` |
| `RS-API-71` | `RS-API-69` |
| `RS-API-72` | `RS-API-70` |
| `RS-API-73` | `RS-TRAIT-30` |
| `RS-API-74` | `RS-API-71` |
| `RS-API-75` | `RS-API-72` |
| `RS-API-76` | `RS-API-73` |
| `RS-API-77` | `RS-API-74` |
| `RS-API-78` | `RS-API-75` |
| `RS-API-79` | `RS-API-76` |
| `RS-API-80` | `RS-API-77` |
| `RS-API-81` | `RS-API-78` |
| `RS-API-82` | `RS-API-79` |
| `RS-API-83` | `RS-API-80` |
| `RS-API-84` | `RS-API-81` |
| `RS-CAR-01` | `RS-BUILD-01` |
| `RS-CAR-02` | `RS-BUILD-02` |
| `RS-CAR-03` | `RS-BUILD-03` |
| `RS-CAR-04` | `RS-BUILD-04` |
| `RS-CAR-05` | `RS-BUILD-05` |
| `RS-CAR-06` | `RS-BUILD-06` |
| `RS-CAR-07` | `RS-BUILD-07` |
| `RS-CAR-08` | `RS-BUILD-08` |
| `RS-CAR-09` | `RS-BUILD-09` |
| `RS-CAR-10` | `RS-BUILD-10` |
| `RS-CAR-11` | `RS-BUILD-11` |
| `RS-CAR-12` | `RS-BUILD-12` |
| `RS-CAR-13` | `RS-BUILD-13` |
| `RS-CAR-14` | `RS-BUILD-14` |
| `RS-CAR-15` | `RS-BUILD-15` |
| `RS-CAR-16` | `RS-BUILD-16` |
| `RS-CAR-17` | `RS-BUILD-17` |
| `RS-CAR-18` | `RS-BUILD-18` |
| `RS-CAR-19` | `RS-BUILD-19` |
| `RS-CAR-20` | `RS-BUILD-20` |
| `RS-CAR-21` | `RS-BUILD-21` |
| `RS-CAR-22` | `RS-BUILD-22` |
| `RS-CAR-23` | `RS-BUILD-23` |
| `RS-CAR-24` | `RS-BUILD-24` |
| `RS-CAR-25` | `RS-BUILD-25` |
| `RS-CAR-26` | lint `clippy:lint_groups_priority` |
| `RS-CAR-27` | `RS-BUILD-26` |
| `RS-CAR-28` | lint `clippy:unwrap_used` |
| `RS-CAR-29` | lint `clippy:undocumented_unsafe_blocks` |
| `RS-CAR-30` | lint `clippy:allow_attributes` |
| `RS-CAR-31` | `RS-BUILD-27` |
| `RS-CAR-32` | `RS-BUILD-28` |
| `RS-CAR-33` | lint `rustc:linker_messages` |
| `RS-CAR-34` | `RS-BUILD-29` |
| `RS-CAR-35` | `RS-BUILD-30` |
| `RS-CAR-36` | `RS-BUILD-31` |
| `RS-CAR-37` | `RS-BUILD-32` |
| `RS-CAR-38` | `RS-BUILD-33` |
| `RS-CAR-39` | `RS-BUILD-34` |
| `RS-CAR-40` | `RS-BUILD-35` |
| `RS-CAR-41` | `RS-BUILD-36` |
| `RS-CAR-42` | `RS-BUILD-37` |
| `RS-CAR-43` | `RS-BUILD-38` |
| `RS-CAR-44` | `RS-BUILD-39` |
| `RS-CAR-45` | `RS-BUILD-40` |
| `RS-CAR-46` | `RS-BUILD-41` |
| `RS-CAR-47` | `RS-BUILD-42` |
| `RS-CAR-48` | `RS-BUILD-43` |
| `RS-CAR-49` | `RS-BUILD-44` |
| `RS-CAR-50` | `RS-BUILD-45` |
| `RS-CAR-51` | `RS-BUILD-46` |
| `RS-CAR-52` | `RS-BUILD-47` |
| `RS-CAR-53` | `RS-BUILD-48` |
| `RS-CAR-54` | `RS-BUILD-49` |
| `RS-CLI-31` | `RS-ERR-45` |
| `RS-CLI-32` | `RS-CLI-31` |
| `RS-CLI-33` | `RS-CLI-32` |
| `RS-CLI-34` | `RS-CLI-33` |
| `RS-CLI-35` | `RS-CLI-34` |
| `RS-CLI-36` | `RS-CLI-35` |
| `RS-CLI-37` | `RS-CLI-36` |
| `RS-CLI-38` | `RS-CLI-37` |
| `RS-CLI-39` | `RS-CLI-38` |
| `RS-CLI-40` | `RS-CLI-39` |
| `RS-CNC-01` | `RS-CONC-01` |
| `RS-CNC-02` | `RS-CONC-02` |
| `RS-CNC-03` | `RS-CONC-03` |
| `RS-CNC-04` | `RS-CONC-04` |
| `RS-CNC-05` | `RS-CONC-05` |
| `RS-CNC-06` | `RS-CONC-06` |
| `RS-CNC-07` | `RS-CONC-07` |
| `RS-CNC-08` | `RS-CONC-08` |
| `RS-CNC-09` | `RS-CONC-09` |
| `RS-CNC-10` | `RS-CONC-10` |
| `RS-CNC-11` | `RS-CONC-11` |
| `RS-CNC-12` | `RS-CONC-12` |
| `RS-CNC-13` | `RS-CONC-13` |
| `RS-CNC-14` | `RS-CONC-14` |
| `RS-CNC-15` | `RS-CONC-15` |
| `RS-CNC-16` | `RS-CONC-16` |
| `RS-CNC-17` | `RS-CONC-17` |
| `RS-CNC-18` | `RS-CONC-18` |
| `RS-CNC-19` | `RS-CONC-19` |
| `RS-CNC-20` | `RS-CONC-20` |
| `RS-CNC-21` | `RS-CONC-21` |
| `RS-CNC-22` | `RS-CONC-22` |
| `RS-CNC-23` | `RS-CONC-23` |
| `RS-CNC-24` | `RS-CONC-24` |
| `RS-CNC-25` | `RS-CONC-25` |
| `RS-CNC-26` | `RS-CONC-26` |
| `RS-CNC-27` | `RS-CONC-27` |
| `RS-CNC-28` | `RS-CONC-28` |
| `RS-CNC-29` | `RS-CONC-29` |
| `RS-CNC-30` | `RS-CONC-30` |
| `RS-CNC-31` | `RS-CONC-31` |
| `RS-CNC-32` | `RS-CONC-32` |
| `RS-CNC-33` | `RS-CONC-33` |
| `RS-CNC-34` | lint `clippy:unused_async` |
| `RS-CNC-35` | `RS-CONC-34` |
| `RS-CNC-36` | `RS-CONC-35` |
| `RS-CNC-37` | `RS-CONC-36` |
| `RS-CNC-38` | `RS-CONC-37` |
| `RS-CNC-39` | `RS-CONC-38` |
| `RS-CNC-40` | `RS-CONC-39` |
| `RS-CNC-41` | `RS-CONC-40` |
| `RS-CNC-42` | `RS-CONC-41` |
| `RS-CNC-43` | `RS-CONC-42` |
| `RS-CNC-44` | `RS-CONC-43` |
| `RS-CNC-45` | `RS-CONC-44` |
| `RS-CNC-46` | `RS-CONC-45` |
| `RS-CNC-47` | `RS-CONC-46` |
| `RS-CNC-48` | `RS-CONC-47` |
| `RS-CNC-49` | `RS-CONC-48` |
| `RS-CNC-50` | `RS-CONC-49` |
| `RS-CNC-51` | `RS-CONC-50` |
| `RS-CNC-52` | `RS-CONC-51` |
| `RS-DOC-32` | lint `rustdoc:broken_intra_doc_links` |
| `RS-DOC-33` | `RS-DOC-32` |
| `RS-DOC-34` | `RS-DOC-33` |
| `RS-DOC-35` | `RS-DOC-34` |
| `RS-DOC-36` | `RS-DOC-35` |
| `RS-DOC-37` | `RS-DOC-36` |
| `RS-DOC-38` | `RS-DOC-37` |
| `RS-DOC-39` | `RS-DOC-38` |
| `RS-DOC-40` | `RS-DOC-39` |
| `RS-ERR-05` | lint `clippy:unwrap_used` |
| `RS-ERR-06` | `RS-ERR-05` |
| `RS-ERR-07` | `RS-ERR-06` |
| `RS-ERR-08` | `RS-ERR-07` |
| `RS-ERR-09` | `RS-ERR-08` |
| `RS-ERR-10` | `RS-ERR-09` |
| `RS-ERR-11` | `RS-ERR-10` |
| `RS-ERR-12` | `RS-ERR-11` |
| `RS-ERR-13` | `RS-ERR-12` |
| `RS-ERR-14` | `RS-ERR-13` |
| `RS-ERR-15` | `RS-ERR-14` |
| `RS-ERR-16` | `RS-ERR-15` |
| `RS-ERR-17` | `RS-ERR-16` |
| `RS-ERR-18` | `RS-ERR-17` |
| `RS-ERR-19` | `RS-ERR-18` |
| `RS-ERR-20` | `RS-ERR-19` |
| `RS-ERR-21` | `RS-ERR-20` |
| `RS-ERR-22` | `RS-ERR-21` |
| `RS-ERR-23` | `RS-ERR-22` |
| `RS-ERR-24` | `RS-ERR-23` |
| `RS-ERR-25` | `RS-ERR-24` |
| `RS-ERR-26` | `RS-ERR-25` |
| `RS-ERR-27` | `RS-ERR-26` |
| `RS-ERR-28` | `RS-ERR-27` |
| `RS-ERR-29` | `RS-ERR-28` |
| `RS-ERR-30` | `RS-ERR-29` |
| `RS-ERR-31` | `RS-ERR-30` |
| `RS-ERR-32` | `RS-ERR-31` |
| `RS-ERR-33` | `RS-ERR-32` |
| `RS-ERR-34` | `RS-FUNC-07` |
| `RS-ERR-35` | `RS-ERR-33` |
| `RS-ERR-36` | `RS-ERR-34` |
| `RS-ERR-37` | `RS-ERR-35` |
| `RS-ERR-38` | `RS-ERR-36` |
| `RS-ERR-39` | `RS-UNSAFE-24` |
| `RS-ERR-40` | `RS-ERR-37` |
| `RS-ERR-41` | `RS-ERR-38` |
| `RS-ERR-42` | `RS-ERR-39` |
| `RS-ERR-43` | `RS-ERR-40` |
| `RS-ERR-44` | `RS-ERR-41` |
| `RS-ERR-45` | `RS-ERR-42` |
| `RS-ERR-46` | `RS-CLI-20` |
| `RS-ERR-47` | `RS-ERR-43` |
| `RS-ERR-48` | `RS-ERR-44` |
| `RS-ERR-49` | `RS-ERR-45` |
| `RS-ERR-50` | `RS-CLI-22` |
| `RS-FP-01` | `RS-FUNC-01` |
| `RS-FP-02` | lint `clippy:needless_return` |
| `RS-FP-03` | `RS-FUNC-02` |
| `RS-FP-04` | `RS-FUNC-03` |
| `RS-FP-05` | `RS-FUNC-04` |
| `RS-FP-06` | `RS-FUNC-05` |
| `RS-FP-07` | `RS-FUNC-06` |
| `RS-FP-08` | `RS-FUNC-07` |
| `RS-FP-09` | lint `clippy:match_like_matches_macro` |
| `RS-FP-10` | `RS-FUNC-08` |
| `RS-FP-11` | `RS-FUNC-09` |
| `RS-FP-12` | `RS-FUNC-10` |
| `RS-FP-13` | `RS-FUNC-11` |
| `RS-FP-14` | `RS-FUNC-12` |
| `RS-FP-15` | `RS-FUNC-13` |
| `RS-FP-16` | `RS-FUNC-14` |
| `RS-FP-17` | `RS-FUNC-15` |
| `RS-FP-18` | `RS-FUNC-16` |
| `RS-FP-19` | `RS-FUNC-17` |
| `RS-FP-20` | lint `clippy:map_clone` |
| `RS-FP-21` | `RS-FUNC-18` |
| `RS-FP-22` | `RS-FUNC-19` |
| `RS-FP-23` | `RS-FUNC-20` |
| `RS-FP-24` | `RS-FUNC-21` |
| `RS-FP-25` | `RS-FUNC-22` |
| `RS-FP-26` | `RS-FUNC-23` |
| `RS-FP-27` | `RS-FUNC-24` |
| `RS-FP-28` | `RS-FUNC-25` |
| `RS-FP-29` | `RS-FUNC-26` |
| `RS-FP-30` | `RS-FUNC-27` |
| `RS-FP-31` | `RS-FUNC-28` |
| `RS-FP-32` | lint `clippy:needless_late_init` |
| `RS-FP-33` | `RS-FUNC-29` |
| `RS-FP-34` | `RS-FUNC-30` |
| `RS-FP-35` | `RS-FUNC-31` |
| `RS-FP-36` | lint `clippy:manual_inspect` |
| `RS-FP-37` | `RS-FUNC-32` |
| `RS-FP-38` | `RS-FUNC-33` |
| `RS-FP-39` | `RS-FUNC-34` |
| `RS-FP-40` | `RS-FUNC-35` |
| `RS-FP-41` | lint `clippy:redundant_closure` |
| `RS-FP-42` | `RS-FUNC-36` |
| `RS-FP-43` | `RS-FUNC-37` |
| `RS-FP-44` | `RS-FUNC-38` |
| `RS-FP-45` | `RS-FUNC-39` |
| `RS-FP-46` | `RS-FUNC-40` |
| `RS-FP-47` | `RS-FUNC-41` |
| `RS-FP-48` | `RS-FUNC-42` |
| `RS-FP-49` | `RS-FUNC-43` |
| `RS-FP-50` | `RS-FUNC-44` |
| `RS-FP-51` | `RS-FUNC-45` |
| `RS-FP-52` | `RS-FUNC-46` |
| `RS-FP-53` | `RS-FUNC-47` |
| `RS-FP-54` | `RS-FUNC-48` |
| `RS-FP-55` | `RS-FUNC-49` |
| `RS-FP-56` | `RS-FUNC-50` |
| `RS-FP-57` | `RS-FUNC-51` |
| `RS-FP-58` | `RS-FUNC-52` |
| `RS-FP-59` | `RS-FUNC-53` |
| `RS-FP-60` | `RS-FUNC-54` |
| `RS-FP-61` | `RS-FUNC-55` |
| `RS-FP-62` | `RS-FUNC-56` |
| `RS-FP-63` | `RS-FUNC-57` |
| `RS-FP-64` | `RS-FUNC-58` |
| `RS-MAC-01` | `RS-MACRO-01` |
| `RS-MAC-02` | `RS-MACRO-02` |
| `RS-MAC-03` | `RS-MACRO-03` |
| `RS-MAC-04` | `RS-MACRO-04` |
| `RS-MAC-05` | `RS-MACRO-05` |
| `RS-MAC-06` | `RS-MACRO-06` |
| `RS-MAC-07` | `RS-MACRO-07` |
| `RS-MAC-08` | `RS-MACRO-08` |
| `RS-MAC-09` | `RS-MACRO-09` |
| `RS-MAC-10` | `RS-MACRO-10` |
| `RS-MAC-11` | `RS-MACRO-11` |
| `RS-MAC-12` | `RS-MACRO-12` |
| `RS-MAC-13` | `RS-MACRO-13` |
| `RS-MAC-14` | `RS-MACRO-14` |
| `RS-MAC-15` | `RS-MACRO-15` |
| `RS-MAC-16` | `RS-MACRO-16` |
| `RS-MAC-17` | `RS-MACRO-17` |
| `RS-MAC-18` | `RS-MACRO-18` |
| `RS-MAC-19` | `RS-MACRO-19` |
| `RS-MAC-20` | `RS-MACRO-20` |
| `RS-MAC-21` | `RS-MACRO-21` |
| `RS-MAC-22` | `RS-MACRO-22` |
| `RS-MAC-23` | `RS-MACRO-23` |
| `RS-MAC-24` | `RS-MACRO-24` |
| `RS-MAC-25` | `RS-MACRO-25` |
| `RS-MAC-26` | `RS-MACRO-26` |
| `RS-NAM-01` | `RS-NAME-01` |
| `RS-NAM-02` | `RS-NAME-02` |
| `RS-NAM-03` | `RS-NAME-03` |
| `RS-NAM-04` | `RS-NAME-04` |
| `RS-NAM-05` | `RS-NAME-05` |
| `RS-NAM-06` | `RS-NAME-06` |
| `RS-NAM-07` | `RS-NAME-07` |
| `RS-NAM-08` | `RS-NAME-08` |
| `RS-NAM-09` | `RS-NAME-09` |
| `RS-NAM-10` | `RS-NAME-10` |
| `RS-NAM-11` | `RS-NAME-11` |
| `RS-NAM-12` | `RS-NAME-12` |
| `RS-NAM-13` | `RS-NAME-13` |
| `RS-NAM-14` | `RS-NAME-14` |
| `RS-NAM-15` | `RS-NAME-15` |
| `RS-NAM-16` | `RS-NAME-16` |
| `RS-NAM-17` | `RS-NAME-17` |
| `RS-NAM-18` | `RS-NAME-18` |
| `RS-NAM-19` | `RS-NAME-19` |
| `RS-NAM-20` | `RS-NAME-20` |
| `RS-NAM-21` | `RS-NAME-21` |
| `RS-NAM-22` | `RS-NAME-22` |
| `RS-NAM-23` | `RS-NAME-23` |
| `RS-NAM-24` | `RS-NAME-24` |
| `RS-NAM-25` | `RS-NAME-25` |
| `RS-NAM-26` | `RS-NAME-26` |
| `RS-NAM-27` | `RS-NAME-27` |
| `RS-NAM-28` | `RS-NAME-28` |
| `RS-NAM-29` | `RS-NAME-29` |
| `RS-NAM-30` | `RS-NAME-30` |
| `RS-NAM-31` | `RS-NAME-31` |
| `RS-NAM-32` | `RS-NAME-32` |
| `RS-NAM-33` | `RS-NAME-33` |
| `RS-NAM-34` | `RS-NAME-34` |
| `RS-NAM-35` | `RS-NAME-35` |
| `RS-NAM-36` | `RS-NAME-36` |
| `RS-NAM-37` | `RS-NAME-37` |
| `RS-NAM-38` | `RS-NAME-38` |
| `RS-NAM-39` | `RS-NAME-39` |
| `RS-NAM-40` | lint `rustc:non_upper_case_globals` |
| `RS-NAM-41` | `RS-NAME-40` |
| `RS-NAM-42` | `RS-NAME-41` |
| `RS-NAM-43` | `RS-NAME-42` |
| `RS-NAM-44` | `RS-NAME-43` |
| `RS-OWN-02` | lint `clippy:ptr_arg` |
| `RS-OWN-03` | `RS-OWN-02` |
| `RS-OWN-04` | `RS-OWN-03` |
| `RS-OWN-05` | `RS-OWN-04` |
| `RS-OWN-06` | lint `rustc:elided_lifetimes_in_paths` |
| `RS-OWN-07` | lint `clippy:needless_lifetimes` |
| `RS-OWN-08` | `RS-OWN-05` |
| `RS-OWN-09` | `RS-OWN-06` |
| `RS-OWN-10` | `RS-OWN-07` |
| `RS-OWN-11` | `RS-OWN-08` |
| `RS-OWN-12` | `RS-OWN-09` |
| `RS-OWN-13` | `RS-OWN-10` |
| `RS-OWN-14` | `RS-OWN-11` |
| `RS-OWN-15` | `RS-OWN-12` |
| `RS-OWN-16` | `RS-OWN-13` |
| `RS-OWN-17` | `RS-OWN-14` |
| `RS-OWN-18` | `RS-OWN-15` |
| `RS-OWN-19` | `RS-OWN-16` |
| `RS-OWN-20` | `RS-OWN-17` |
| `RS-OWN-21` | `RS-OWN-18` |
| `RS-OWN-22` | `RS-OWN-19` |
| `RS-OWN-23` | `RS-OWN-20` |
| `RS-OWN-24` | `RS-OWN-21` |
| `RS-OWN-25` | `RS-UNSAFE-18` |
| `RS-OWN-26` | `RS-OWN-22` |
| `RS-OWN-27` | `RS-OWN-23` |
| `RS-OWN-28` | `RS-OWN-24` |
| `RS-OWN-29` | `RS-OWN-25` |
| `RS-OWN-30` | `RS-OWN-26` |
| `RS-OWN-31` | `RS-OWN-27` |
| `RS-OWN-32` | `RS-OWN-28` |
| `RS-OWN-33` | `RS-OWN-29` |
| `RS-OWN-34` | `RS-OWN-30` |
| `RS-OWN-35` | `RS-OWN-31` |
| `RS-OWN-36` | `RS-OWN-32` |
| `RS-OWN-37` | `RS-OWN-33` |
| `RS-OWN-38` | `RS-OWN-34` |
| `RS-OWN-39` | `RS-OWN-35` |
| `RS-OWN-40` | `RS-OWN-36` |
| `RS-OWN-41` | `RS-OWN-37` |
| `RS-OWN-42` | `RS-OWN-38` |
| `RS-OWN-43` | `RS-OWN-39` |
| `RS-OWN-44` | `RS-OWN-40` |
| `RS-OWN-45` | `RS-OWN-41` |
| `RS-OWN-46` | `RS-OWN-42` |
| `RS-PRF-01` | `RS-PERF-01` |
| `RS-PRF-02` | `RS-PERF-02` |
| `RS-PRF-03` | `RS-PERF-03` |
| `RS-PRF-04` | `RS-PERF-04` |
| `RS-PRF-05` | `RS-PERF-05` |
| `RS-PRF-06` | `RS-PERF-06` |
| `RS-PRF-07` | `RS-PERF-07` |
| `RS-PRF-08` | `RS-PERF-08` |
| `RS-PRF-09` | `RS-PERF-09` |
| `RS-PRF-10` | `RS-PERF-10` |
| `RS-PRF-11` | `RS-OWN-14` |
| `RS-PRF-12` | `RS-PERF-11` |
| `RS-PRF-13` | `RS-PERF-12` |
| `RS-PRF-14` | `RS-PERF-13` |
| `RS-PRF-15` | `RS-PERF-14` |
| `RS-PRF-16` | `RS-PERF-15` |
| `RS-PRF-17` | `RS-PERF-16` |
| `RS-PRF-18` | `RS-PERF-17` |
| `RS-PRF-19` | lint `clippy:map_entry` |
| `RS-PRF-20` | `RS-PERF-18` |
| `RS-PRF-21` | `RS-PERF-19` |
| `RS-PRF-22` | `RS-PERF-20` |
| `RS-PRF-23` | lint `clippy:needless_range_loop` |
| `RS-PRF-24` | `RS-PERF-21` |
| `RS-PRF-25` | `RS-PERF-22` |
| `RS-PRF-26` | `RS-PERF-23` |
| `RS-PRF-27` | `RS-PERF-24` |
| `RS-PRF-28` | `RS-PERF-25` |
| `RS-PRF-29` | `RS-PERF-26` |
| `RS-PRF-30` | `RS-PERF-27` |
| `RS-PRF-31` | `RS-PERF-28` |
| `RS-PRF-32` | `RS-PERF-29` |
| `RS-PRF-33` | `RS-PERF-30` |
| `RS-PRF-34` | `RS-PERF-31` |
| `RS-PRF-35` | lint `clippy:inline_always` |
| `RS-PRF-36` | `RS-PERF-32` |
| `RS-PRF-37` | `RS-PERF-33` |
| `RS-PRF-38` | `RS-PERF-34` |
| `RS-PRF-39` | `RS-PERF-35` |
| `RS-PRF-40` | `RS-PERF-36` |
| `RS-PRF-41` | `RS-PERF-37` |
| `RS-PRF-42` | `RS-PERF-38` |
| `RS-PRF-43` | `RS-PERF-39` |
| `RS-PRF-44` | `RS-PERF-40` |
| `RS-PRF-45` | `RS-PERF-41` |
| `RS-PRF-46` | `RS-PERF-42` |
| `RS-PRF-47` | `RS-PERF-43` |
| `RS-PRF-48` | `RS-PERF-44` |
| `RS-PRF-49` | `RS-PERF-45` |
| `RS-PRF-50` | `RS-PERF-46` |
| `RS-STR-01` | `RS-MOD-01` |
| `RS-STR-02` | `RS-MOD-02` |
| `RS-STR-03` | `RS-MOD-03` |
| `RS-STR-04` | `RS-MOD-04` |
| `RS-STR-05` | `RS-MOD-05` |
| `RS-STR-06` | lint `clippy:mod_module_files` |
| `RS-STR-07` | `RS-MOD-06` |
| `RS-STR-08` | `RS-MOD-07` |
| `RS-STR-09` | `RS-TEST-04` |
| `RS-STR-10` | `RS-MOD-08` |
| `RS-STR-11` | `RS-MOD-09` |
| `RS-STR-12` | `RS-MOD-10` |
| `RS-STR-13` | `RS-MOD-11` |
| `RS-STR-14` | `RS-MOD-12` |
| `RS-STR-15` | `RS-MOD-13` |
| `RS-STR-16` | `RS-MOD-14` |
| `RS-STR-17` | `RS-MOD-15` |
| `RS-STR-18` | `RS-MOD-16` |
| `RS-STR-19` | `RS-MOD-17` |
| `RS-STR-20` | `RS-MOD-18` |
| `RS-STR-21` | `RS-MOD-19` |
| `RS-STR-22` | `RS-MOD-20` |
| `RS-STR-23` | `RS-MOD-21` |
| `RS-STR-24` | `RS-MOD-22` |
| `RS-STR-25` | `RS-MOD-23` |
| `RS-STR-26` | `RS-MOD-24` |
| `RS-STR-27` | `RS-MOD-25` |
| `RS-STR-28` | `RS-MOD-26` |
| `RS-STR-29` | `RS-MOD-27` |
| `RS-STR-30` | `RS-MOD-28` |
| `RS-STR-31` | `RS-MOD-29` |
| `RS-STR-32` | `RS-MOD-30` |
| `RS-STR-33` | `RS-MOD-31` |
| `RS-STR-34` | `RS-MOD-32` |
| `RS-STR-35` | `RS-MOD-33` |
| `RS-STR-36` | `RS-MOD-34` |
| `RS-STR-37` | `RS-MOD-35` |
| `RS-STR-38` | `RS-MOD-36` |
| `RS-STR-39` | `RS-MOD-37` |
| `RS-STR-40` | `RS-MOD-38` |
| `RS-STR-41` | `RS-MOD-39` |
| `RS-STR-42` | `RS-MOD-40` |
| `RS-STR-43` | `RS-MOD-41` |
| `RS-STR-44` | `RS-MOD-42` |
| `RS-STR-45` | `RS-MOD-43` |
| `RS-STR-46` | `RS-MOD-44` |
| `RS-STR-47` | `RS-MOD-45` |
| `RS-STR-48` | `RS-MOD-46` |
| `RS-STR-49` | `RS-MOD-47` |
| `RS-STR-50` | `RS-MOD-48` |
| `RS-STR-51` | `RS-MOD-49` |
| `RS-STR-52` | `RS-MOD-50` |
| `RS-STR-53` | `RS-MOD-51` |
| `RS-STR-54` | `RS-MOD-52` |
| `RS-STR-55` | `RS-MOD-53` |
| `RS-STR-56` | `RS-MOD-54` |
| `RS-STR-57` | `RS-MOD-55` |
| `RS-TST-01` | `RS-TEST-01` |
| `RS-TST-02` | `RS-TEST-02` |
| `RS-TST-03` | `RS-TEST-03` |
| `RS-TST-04` | `RS-TEST-04` |
| `RS-TST-05` | `RS-TEST-05` |
| `RS-TST-06` | `RS-TEST-06` |
| `RS-TST-07` | `RS-TEST-07` |
| `RS-TST-08` | `RS-TEST-08` |
| `RS-TST-09` | `RS-TEST-09` |
| `RS-TST-10` | `RS-TEST-10` |
| `RS-TST-11` | `RS-TEST-11` |
| `RS-TST-12` | `RS-TEST-12` |
| `RS-TST-13` | `RS-TEST-13` |
| `RS-TST-14` | `RS-TEST-14` |
| `RS-TST-15` | `RS-TEST-15` |
| `RS-TST-16` | `RS-TEST-16` |
| `RS-TST-17` | lint `clippy:should_panic_without_expect` |
| `RS-TST-18` | `RS-TEST-17` |
| `RS-TST-19` | `RS-TEST-18` |
| `RS-TST-20` | `RS-TEST-19` |
| `RS-TST-21` | `RS-TEST-20` |
| `RS-TST-22` | `RS-TEST-21` |
| `RS-TST-23` | `RS-TEST-22` |
| `RS-TST-24` | `RS-TEST-23` |
| `RS-TST-25` | `RS-TEST-24` |
| `RS-TST-26` | `RS-TEST-25` |
| `RS-TST-27` | `RS-TEST-26` |
| `RS-TST-28` | `RS-TEST-27` |
| `RS-TST-29` | `RS-TEST-28` |
| `RS-TST-30` | `RS-TEST-29` |
| `RS-TST-31` | `RS-TEST-30` |
| `RS-TST-32` | `RS-TEST-31` |
| `RS-TST-33` | `RS-TEST-32` |
| `RS-TST-34` | `RS-TEST-33` |
| `RS-TST-35` | `RS-TEST-34` |
| `RS-TST-36` | `RS-TEST-35` |
| `RS-TST-37` | `RS-TEST-36` |
| `RS-TST-38` | `RS-TEST-37` |
| `RS-TST-39` | `RS-TEST-38` |
| `RS-TST-40` | `RS-TEST-39` |
| `RS-TST-41` | `RS-TEST-40` |
| `RS-TST-42` | `RS-TEST-41` |
| `RS-TRG-01` | `RS-TRAIT-01` |
| `RS-TRG-02` | `RS-TRAIT-02` |
| `RS-TRG-03` | `RS-TRAIT-03` |
| `RS-TRG-04` | `RS-TRAIT-04` |
| `RS-TRG-05` | `RS-TRAIT-05` |
| `RS-TRG-06` | `RS-TRAIT-06` |
| `RS-TRG-07` | `RS-TRAIT-07` |
| `RS-TRG-08` | `RS-TRAIT-08` |
| `RS-TRG-09` | `RS-TRAIT-09` |
| `RS-TRG-10` | `RS-TRAIT-10` |
| `RS-TRG-11` | `RS-TRAIT-11` |
| `RS-TRG-12` | `RS-TRAIT-12` |
| `RS-TRG-13` | `RS-TRAIT-13` |
| `RS-TRG-14` | `RS-TRAIT-14` |
| `RS-TRG-15` | `RS-TRAIT-15` |
| `RS-TRG-16` | `RS-TRAIT-16` |
| `RS-TRG-17` | `RS-TRAIT-17` |
| `RS-TRG-18` | `RS-TRAIT-18` |
| `RS-TRG-19` | `RS-TRAIT-19` |
| `RS-TRG-20` | `RS-TRAIT-20` |
| `RS-TRG-21` | `RS-TRAIT-21` |
| `RS-TRG-22` | `RS-TRAIT-22` |
| `RS-TRG-23` | `RS-TRAIT-23` |
| `RS-TRG-24` | `RS-TRAIT-24` |
| `RS-TRG-25` | `RS-TRAIT-25` |
| `RS-TRG-26` | `RS-TRAIT-26` |
| `RS-TRG-27` | `RS-TRAIT-27` |
| `RS-TRG-28` | `RS-TRAIT-28` |
| `RS-TRG-29` | `RS-TRAIT-29` |
| `RS-TRG-30` | `RS-TRAIT-30` |
| `RS-TRG-31` | `RS-TRAIT-31` |
| `RS-TRG-32` | `RS-TRAIT-32` |
| `RS-TRG-33` | `RS-TRAIT-33` |
| `RS-TRG-34` | `RS-TRAIT-34` |
| `RS-TRG-35` | `RS-TRAIT-35` |
| `RS-TRG-36` | `RS-TRAIT-36` |
| `RS-TRG-37` | `RS-TRAIT-37` |
| `RS-TRG-38` | `RS-TRAIT-38` |
| `RS-TRG-39` | `RS-OWN-19` |
| `RS-TRG-40` | `RS-TRAIT-39` |
| `RS-TRG-41` | `RS-TRAIT-40` |
| `RS-TRG-42` | `RS-TRAIT-41` |
| `RS-TRG-43` | `RS-TRAIT-42` |
| `RS-TRG-44` | `RS-TRAIT-43` |
| `RS-TRG-45` | `RS-TRAIT-44` |
| `RS-TRG-46` | `RS-TRAIT-45` |
| `RS-TRG-47` | `RS-TRAIT-46` |
| `RS-TRG-48` | `RS-TRAIT-47` |
| `RS-TRG-49` | `RS-TRAIT-48` |
| `RS-TRG-50` | `RS-TRAIT-49` |
| `RS-TRG-51` | `RS-TRAIT-50` |
| `RS-TRG-52` | `RS-TRAIT-51` |
| `RS-TRG-53` | `RS-TRAIT-52` |
| `RS-TRG-54` | `RS-TRAIT-53` |
| `RS-TRG-55` | `RS-TRAIT-54` |
| `RS-TRG-56` | `RS-TRAIT-55` |
| `RS-UNS-01` | `RS-UNSAFE-01` |
| `RS-UNS-02` | `RS-UNSAFE-02` |
| `RS-UNS-03` | `RS-UNSAFE-03` |
| `RS-UNS-04` | `RS-UNSAFE-04` |
| `RS-UNS-05` | `RS-UNSAFE-05` |
| `RS-UNS-06` | `RS-UNSAFE-06` |
| `RS-UNS-07` | `RS-UNSAFE-07` |
| `RS-UNS-08` | `RS-UNSAFE-08` |
| `RS-UNS-09` | `RS-UNSAFE-09` |
| `RS-UNS-10` | `RS-UNSAFE-10` |
| `RS-UNS-11` | `RS-UNSAFE-11` |
| `RS-UNS-12` | `RS-UNSAFE-12` |
| `RS-UNS-13` | `RS-UNSAFE-13` |
| `RS-UNS-14` | `RS-UNSAFE-14` |
| `RS-UNS-15` | `RS-UNSAFE-15` |
| `RS-UNS-16` | `RS-UNSAFE-16` |
| `RS-UNS-17` | `RS-UNSAFE-17` |
| `RS-UNS-18` | `RS-UNSAFE-18` |
| `RS-UNS-19` | `RS-UNSAFE-19` |
| `RS-UNS-20` | `RS-UNSAFE-20` |
| `RS-UNS-21` | `RS-UNSAFE-21` |
| `RS-UNS-22` | `RS-UNSAFE-22` |
| `RS-UNS-23` | `RS-UNSAFE-23` |
| `RS-UNS-24` | `RS-UNSAFE-24` |
| `RS-UNS-25` | `RS-UNSAFE-25` |
| `RS-UNS-26` | `RS-UNSAFE-26` |
| `RS-UNS-27` | `RS-UNSAFE-27` |
| `RS-UNS-28` | `RS-UNSAFE-28` |
| `RS-UNS-29` | `RS-UNSAFE-29` |
| `RS-UNS-30` | `RS-UNSAFE-30` |
| `RS-UNS-31` | `RS-UNSAFE-31` |
| `RS-UNS-32` | `RS-UNSAFE-32` |
| `RS-UNS-33` | `RS-UNSAFE-33` |
| `RS-UNS-34` | `RS-UNSAFE-34` |
| `RS-UNS-35` | `RS-UNSAFE-35` |
| `RS-UNS-36` | `RS-UNSAFE-36` |
