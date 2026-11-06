# Migration: Editions, Releases, and What Replaced What

Scope: what changed under existing Rust code — the 2024 edition, the stable releases since, the
crates the standard library has replaced, and the APIs it has deprecated — and when each API the
rules prescribe arrived, for a crate whose MSRV is older.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- RS-MIG-01 [M] Reach for the standard-library feature that replaced a crate
- RS-MIG-02 [M] Do not call an API deprecated through 1.99
- When an API arrived
- RS-MIG-03 [M] Re-read what changed silently on every toolchain bump
- Decided by tools

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
| `assert_matches!` and `debug_assert_matches!`, imported from `std` | the `assert_matches` crate, `assert!(matches!(..))` | 1.96 |
| `async fn` and `impl Trait` in traits | `#[async_trait]` where no `dyn` is needed | 1.75 |
| async closures and `AsyncFn*` bounds | an `F: Fn() -> Fut, Fut: Future` pair | 1.85 |
| trait upcasting, including to `dyn Any` | a hand-written `fn as_any(&self) -> &dyn Any` | 1.86 |
| `Atomic*::update`, `try_update` | a `compare_exchange` loop, `fetch_update` | 1.95 |
| `strict_*` arithmetic | `checked_*().expect(..)` where overflow is a bug | 1.91 |
| `extract_if` on `Vec`, `HashMap`, `BTreeMap` | `retain` plus a second collection | 1.87 / 1.88 / 1.91 |
| `env::home_dir` | `home`, or `dirs::home_dir` for `$HOME` alone | 1.87 |
| `thread::scope` | `Arc` and `'static` to borrow into a thread | 1.63 |
| `thread::available_parallelism` | `num_cpus` for how many threads to start | 1.59 |
| `io::IsTerminal` | `atty`, `is-terminal` | 1.70 |
| `mem::offset_of!`, nested fields included | `memoffset` | 1.77 / 1.82 |
| `const _: () = assert!(…)`, `const { assert!(…) }` | `static_assertions` | 1.57 / 1.79 |
| `hint::black_box` | `criterion::black_box`, `test::black_box` | 1.66 |
| `<[T]>::chunk_by` | itertools `group_by` on a slice | 1.77 |
| `let ... else` | a `match` with a `_ => return` arm | 1.65 |
| `c"…"` literals | a hand-terminated byte array | 1.77 |
| `#[expect(lint, reason = "…")]` | an `#[allow]` nobody removes | 1.81 |
| `[lints]` in `Cargo.toml` | `#![deny(...)]` in `lib.rs` | 1.74 |
| `CARGO_BUILD_WARNINGS=deny` | `RUSTFLAGS="-Dwarnings"`, which invalidates the cache | 1.97 |

**Why:** a dependency the standard library covers is code to audit, update and build for nothing,
and the crate's spelling outlives the reason it existed. The std version is also the one every
reader already knows.

**Check:** each hit is a dependency the standard library now covers, in the workspace table, a
member's manifest, or a member's `foo.workspace = true` line:
`rg -n -g '*.toml' '^(lazy_static|once_cell|cfg-if|itoa|fs[24]|filetime|num_cpus|memoffset)[ .=]'`
`rg -n -g '*.toml' '^(atty|is-terminal|os_pipe|assert_matches|async-trait|static_assertions)[ .=]'`

### RS-MIG-02 [M] Do not call an API deprecated through 1.99

`Atomic*::fetch_update` is deprecated in 1.99: use `update` or `try_update`. The module constants
`std::i32::MAX` and the rest are deprecated too: use the associated `i32::MAX`.

**Why:** a deprecation warns, and `CARGO_BUILD_WARNINGS=deny` turns the warning into a failed build
— so a toolchain bump breaks CI on code that has not changed.

**Check:** the `deprecated` row below, under `CARGO_BUILD_WARNINGS=deny`; before a toolchain bump,
`rg -n '\.fetch_update\(|std::[iu](8|16|32|64|128|size)::(MAX|MIN)\b' src/`.

## When an API arrived

The rules write what 1.99 offers. A crate whose MSRV is older (RS-BUILD-31) checks each API it uses
against this table and RS-MIG-01's "Since" column, which keep the dates the rules no longer carry.

| API | Stable since |
|---|---|
| generic associated types | 1.65 |
| an omitted `version` meaning `0.0.0` and `publish = false` | 1.75 |
| `Arc::unwrap_or_clone`, `Rc::unwrap_or_clone` | 1.76 |
| `File::create_new`; `<[T]>::first_chunk` | 1.77 |
| `#[diagnostic::on_unimplemented]` | 1.78 |
| `CStr::count_bytes` | 1.79 |
| `core::error::Error`; `fs::exists` | 1.81 |
| `use<..>` bounds; `&raw const` and `&raw mut`; `unsafe extern` blocks | 1.82 |
| `BufRead::skip_until` | 1.83 |
| `#[diagnostic::do_not_recommend]`; unsigned `midpoint`; `Waker::noop`; `ptr::fn_addr_eq` | 1.85 |
| `Vec::pop_if` | 1.86 |
| `OsStr::display`; `is_multiple_of` | 1.87 |
| let chains, in edition 2024 | 1.88 |
| `Path::with_added_extension` | 1.91 |
| `fmt::from_fn`; `Vec::into_raw_parts`; `VecDeque::pop_front_if` and `pop_back_if` | 1.93 |
| `array_windows`; `Peekable::next_if_map` | 1.94 |
| `if let` guards; `hint::cold_path` | 1.95 |
| `core::range::Range` | 1.96 |

## What changed silently

### RS-MIG-03 [M] Re-read what changed silently on every toolchain bump

Each of these compiles before and after, and behaves differently:

| Since | What changed |
|---|---|
| 1.99 | Cargo turns incremental compilation off when `CI` is set |
| 1.99 | an exhausted `RangeInclusive` reports different `start()` and `end()`, and slices differently |
| 1.98 | a derived `PartialOrd` beside a derived `Ord` takes the `Ord` path, so the two can no longer disagree |
| 1.97 | v0 symbol mangling is the default, and `linker_messages` warns outside the `warnings` group |
| 1.97 | on Windows, a write after a socket `shutdown` reports `BrokenPipe` |
| 1.96 | `BTreeMap::append` may panic when the key's `Ord` is inconsistent |
| 1.95 | a `#[non_exhaustive]` match reads the discriminant, which changes what a closure captures |
| 1.94 | closure captures around patterns move, and a `Drop` can run at a different point |
| 1.91 | bindings drop in the order they are written, and panic messages carry the thread ID |
| 1.81 | a panic that escapes an `extern "C"` function aborts the process |
| 1.75 | rustc makes the smallest non-generic functions inlinable across crates without `#[inline]` |

**Why:** nothing fails when these change, so the only defence is reading them against the code at
the moment the toolchain moves. A version bump that skips this step ships behaviour nobody chose.

**Check:** a review matter: on a toolchain bump, read each row newer than the old toolchain against
the diff's feature sets, `Ord` impls, drop order and anything that parses panic messages.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `deprecated` | warn | a deprecated API — CI denies warnings, so treat it as already removed |
