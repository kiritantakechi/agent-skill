# Migration: Editions, Releases, and What Replaced What

Scope: every old spelling the 2024 edition, the releases through 1.99 and the standard library's own
growth left behind — removed, changed, superseded by std or deprecated — keyed by the old spelling,
with the rule that owns it; what changed under existing code with no spelling to find it by; and
when each API the rules prescribe arrived, for a crate whose MSRV is older. Why a spelling is wrong
is its owning rule's to say; this chapter is the table and the command it generates.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- Old spellings
- **Finding the old spellings**
  - RS-MIG-01 [M] Run the command after the table over code no build compiles
  - RS-MIG-02 [M!] Fail the build on a spelling the table marks `alias`
- **What replaced what**
  - RS-MIG-03 [M] Reach for the standard-library feature that replaced a crate
  - RS-MIG-04 [M] Do not call an API deprecated through 1.99
- When an API arrived
- **What changed silently**
  - RS-MIG-05 [M] Re-read what changed silently on every toolchain bump

---

## Old spellings

A row's status says what Rust 1.99, edition 2024, does with its old spelling under the shipped
configuration: `gone` — it rejects it, so the build fails where it stands; `changed` — it accepts
it, and it means something else, so its owning rule's Check finds it; `alias` — it accepts it, and
the standard library provides what it was for, so it is rewritten wherever it stands; `deprecated` —
it accepts it, and it means what it did, with a warning, which `CARGO_BUILD_WARNINGS=deny` makes a
failed build, or for `static mut` a lint that denies a reference to one. A spelling with `…` in it
is a shape: code left out where the `…` stands, which no fixed string finds, so its owning rule's
Check does. Its Since is the release from which it does so — for an `alias`, the one that stabilised
the replacement — or `2024` for a change the edition made; section 2.1 lists the `changed` rows of
1.99 and of edition 2024, and section 2.2 the `gone` ones. The command after the table finds every
`gone` and `alias` row but a shape.

| Old | Rust 1.99 | Status | Since | Rule |
|---|---|---|---|---|
| `#[no_mangle]` | `#[unsafe(no_mangle)]`; `#[export_name]` and `#[link_section]` likewise | gone | 2024 | RS-BUILD-01 |
| `env::remove_var` | an `unsafe fn`, so a call outside `unsafe` is rejected, and `unsafe_code = "forbid"` rejects one inside; pass the code under test a lookup | gone | 2024 | RS-TEST-16 |
| `env::set_var` | an `unsafe fn`, so a call outside `unsafe` is rejected, and `unsafe_code = "forbid"` rejects one inside; pass the code under test a lookup | gone | 2024 | RS-TEST-16 |
| `extern "C" { … }` | rejected; `unsafe extern "C" { … }`, where an item marked `safe fn` is called without `unsafe` | gone | 2024 | RS-UNSAFE-23 |
| `gen` | `r#gen` where the name must stay; `gen` is a reserved keyword, so rejected as a name | gone | 2024 | RS-BUILD-01 |
| `lazy_static!` | `std::sync::LazyLock` | alias | 1.80 | RS-CONC-27 |
| `once_cell::sync::Lazy` | `std::sync::LazyLock` | alias | 1.80 | RS-CONC-27 |
| `once_cell::sync::OnceCell` | `std::sync::OnceLock` | alias | 1.70 | RS-CONC-27 |
| `cfg_if::cfg_if` | `cfg_select!` | alias | 1.95 | RS-MOD-08 |
| `itoa::Buffer` | `<int>::format_into(&mut NumBuffer)` | alias | 1.98 | RS-MIG-03 |
| `fs2::FileExt` | `File::lock`, `try_lock`, `lock_shared` | alias | 1.89 | RS-MIG-03 |
| `fs4::fs_std::FileExt` | `File::lock`, `try_lock`, `lock_shared` | alias | 1.89 | RS-MIG-03 |
| `fd_lock::RwLock` | `File::lock`, `lock_shared` | alias | 1.89 | RS-MIG-03 |
| `filetime::set_file_times` | `fs::set_times`, `File::set_times` | alias | 1.99 | RS-MIG-03 |
| `os_pipe::pipe` | `io::pipe` | alias | 1.87 | RS-MIG-03 |
| `static_assertions::const_assert` | `const _: () = assert!(…)`, or `const { assert!(…) }` | alias | 1.57 | RS-MIG-03 |
| `assert_matches::assert_matches` | `assert_matches!`, imported from `std` | alias | 1.96 | RS-TEST-13 |
| `home::home_dir` | `std::env::home_dir` | alias | 1.87 | RS-CLI-25 |
| `dirs::home_dir` | `std::env::home_dir` | alias | 1.87 | RS-CLI-25 |
| `num_cpus::get` | `std::thread::available_parallelism` | alias | 1.59 | RS-CONC-14 |
| `atty::is` | `std::io::IsTerminal` | alias | 1.70 | RS-CLI-18 |
| `is_terminal::IsTerminal` | `std::io::IsTerminal` | alias | 1.70 | RS-CLI-18 |
| `memoffset::offset_of` | `std::mem::offset_of!`, nested fields included | alias | 1.82 | RS-UNSAFE-14 |
| `criterion::black_box` | `std::hint::black_box` | alias | 1.66 | RS-PERF-29 |
| `test::black_box` | `std::hint::black_box` | alias | 1.66 | RS-PERF-29 |
| `$e:expr` | matches `_` and `const { … }` as well, so a later `_` arm stops firing; `expr_2021` keeps the old fragment | changed | 2024 | RS-MACRO-09 |
| `-> impl Trait` | captures every lifetime in scope, so a caller can fail to borrow; narrow it with `+ use<'a, T>` | changed | 2024 | RS-OWN-21 |
| `Box<[T]>::into_iter` | yields `T`, by value, where it yielded `&T` | changed | 2024 | RS-BUILD-01 |
| `if let` | a temporary in the scrutinee drops before the `else` block, which shortens a lock guard's life | changed | 2024 | RS-BUILD-01 |
| `RangeInclusive` | once exhausted, reports a different `start()` and `end()`, and slices differently | changed | 1.99 | RS-MIG-05 |
| `#[derive(PartialOrd, Ord)]` | the derived `partial_cmp` takes the `Ord` path, so the two can no longer disagree | changed | 1.98 | RS-MIG-05 |
| `TcpStream::shutdown` | on Windows, a write after it reports `BrokenPipe` | changed | 1.97 | RS-MIG-05 |
| `BTreeMap::append` | may panic when the key's `Ord` is inconsistent | changed | 1.96 | RS-MIG-05 |
| `#[non_exhaustive]` | a `match` on such a type reads the discriminant, which changes what a closure captures | changed | 1.95 | RS-MIG-05 |
| `panic!` | its message carries the thread ID | changed | 1.91 | RS-MIG-05 |
| `extern "C" fn` | a panic that escapes one aborts the process | changed | 1.81 | RS-MIG-05 |
| `Atomic*::fetch_update` | `try_update`, which it now aliases | deprecated | 1.99 | RS-CONC-25 |
| `std::<int>::MAX` | `<int>::MAX`; `MIN` and the other module constants likewise | deprecated | 1.99 | RS-MIG-04 |
| `static mut` | builds, and a reference to one is denied (`static_mut_refs`); `OnceLock`, `LazyLock` or an atomic | deprecated | 2024 | RS-CONC-27 |
| `unsafe fn` | builds, and its body is no longer one `unsafe` block: `unsafe_op_in_unsafe_fn` warns on each operation, which CI denies | deprecated | 2024 | RS-UNSAFE-06 |

```sh
rg -n -F -w \
  -e '#[no_mangle]' \
  -e 'env::remove_var' \
  -e 'env::set_var' \
  -e 'gen' \
  -e 'lazy_static!' \
  -e 'once_cell::sync::Lazy' \
  -e 'once_cell::sync::OnceCell' \
  -e 'cfg_if::cfg_if' \
  -e 'itoa::Buffer' \
  -e 'fs2::FileExt' \
  -e 'fs4::fs_std::FileExt' \
  -e 'fd_lock::RwLock' \
  -e 'filetime::set_file_times' \
  -e 'os_pipe::pipe' \
  -e 'static_assertions::const_assert' \
  -e 'assert_matches::assert_matches' \
  -e 'home::home_dir' \
  -e 'dirs::home_dir' \
  -e 'num_cpus::get' \
  -e 'atty::is' \
  -e 'is_terminal::IsTerminal' \
  -e 'memoffset::offset_of' \
  -e 'criterion::black_box' \
  -e 'test::black_box' \
  .
```

## Finding the old spellings

### RS-MIG-01 [M] Run the command after the table over code no build compiles

A `gone` spelling survives a passing build wherever rustc never compiled it: a `cfg` branch for a
target or a feature the build does not select, a test module nobody ran, a crate outside the default
members. Run the command after the table over the whole tree, not only over what the build compiled,
and before reading a diff.

**Why:** rustc rejects a removed name only in the configuration it compiles, so the rest waits for
the first build that selects it, often on another platform and long after the migration.

**Check:** a hit of the command on a `gone` row in a tree whose build passes is code no build
compiled; rewrite it to the row's 1.99 column, or delete it if nothing builds it.

### RS-MIG-02 [M!] Fail the build on a spelling the table marks `alias`

Add a CI step that runs the command after the table and fails on a hit, and treat the hits of the
day it is added as its first commit. An `alias` compiles with no warning, so nothing else stops the
next one from arriving.

*Relaxed form:* no CI gate; the same command runs by hand before each release, and an `alias` in a
file you are already editing is fixed in that diff.

**Why:** an `alias` never fails a build, so on a long-lived codebase they accumulate until an
edition or toolchain bump deletes them all at once and the diff is too large to review. A gate turns
that migration into a cost of each change.

**Check:** the CI workflow runs the command after the table and fails on a hit — its exit status
checked, not swallowed by `|| true`. Run it once by hand when adding it: a hit means the gate is
being added to a tree that already fails it.

## What replaced what

### RS-MIG-03 [M] Reach for the standard-library feature that replaced a crate

Every `alias` row is a crate, or a crate's API, that the standard library replaced; the rows with no
topical rule are this rule's. A dependency on one is the finding, wherever the manifest declares it.
A crate that is still the right tool for part of its use — `async-trait` where a trait object needs
`async fn` — is no row: RS-CONC-31 decides it.

**Why:** a dependency the standard library covers is code to audit, update and build for nothing,
and the crate's spelling outlives the reason it existed. The std version is also the one every
reader already knows.

**Check:** each hit is a dependency the standard library now covers, in the workspace table, a
member's manifest, or a member's `foo.workspace = true` line:
`rg -n -g '*.toml' '^(lazy_static|once_cell|cfg-if|itoa|fs[24]|filetime|num_cpus|memoffset)[ .=]'`
`rg -n -g '*.toml' '^(atty|is-terminal|os_pipe|assert_matches|static_assertions|fd-lock)[ .=]'`

### RS-MIG-04 [M] Do not call an API deprecated through 1.99

Every `deprecated` row the rule column gives to RS-MIG-04: `Atomic*::fetch_update` is renamed
`try_update`, and the module constants `std::i32::MAX` and the rest give way to the associated
`i32::MAX`.

**Why:** a deprecation warns, and `CARGO_BUILD_WARNINGS=deny` turns the warning into a failed build
— so a toolchain bump breaks CI on code that has not changed.

**Check:** rustc's `deprecated` lint, under `CARGO_BUILD_WARNINGS=deny`; before a toolchain bump,
`rg -n '\.fetch_update\(|std::[iu](8|16|32|64|128|size)::(MAX|MIN)\b' src/`.

## When an API arrived

The rules write what 1.99 offers. A crate whose MSRV is older (RS-BUILD-30) checks each API it uses
against this table, which keeps the dates the rules no longer carry.

| API | Stable since |
|---|---|
| `const _: () = assert!(…)` | 1.57 |
| `thread::available_parallelism` | 1.59 |
| `thread::scope` | 1.63 |
| `let ... else`; generic associated types | 1.65 |
| `hint::black_box` | 1.66 |
| `OnceLock`; `io::IsTerminal` | 1.70 |
| `[lints]` in `Cargo.toml` | 1.74 |
| `async fn` and `impl Trait` in traits; an omitted `version` meaning `0.0.0` and `publish = false` | 1.75 |
| `Arc::unwrap_or_clone`, `Rc::unwrap_or_clone` | 1.76 |
| `File::create_new`; `<[T]>::first_chunk`; `<[T]>::chunk_by`; `mem::offset_of!`; `c"…"` literals | 1.77 |
| `#[diagnostic::on_unimplemented]` | 1.78 |
| `CStr::count_bytes`; `const { … }` blocks | 1.79 |
| `LazyLock` | 1.80 |
| `core::error::Error`; `fs::exists`; `#[expect(lint, reason = "…")]` | 1.81 |
| `use<..>` bounds; `&raw const` and `&raw mut`; `unsafe extern` blocks; `offset_of!` on nested fields | 1.82 |
| `BufRead::skip_until` | 1.83 |
| `#[diagnostic::do_not_recommend]`; unsigned `midpoint`; `Waker::noop`; `ptr::fn_addr_eq`; async closures and `AsyncFn*` bounds | 1.85 |
| `Vec::pop_if`; trait upcasting, including to `dyn Any` | 1.86 |
| `OsStr::display`; `is_multiple_of`; `io::pipe`; `env::home_dir` undeprecated; `extract_if` on `Vec` | 1.87 |
| let chains, in edition 2024; `extract_if` on `HashMap` | 1.88 |
| `File::lock`, `try_lock`, `lock_shared` | 1.89 |
| `Path::with_added_extension`; `strict_*` arithmetic; `extract_if` on `BTreeMap` | 1.91 |
| `fmt::from_fn`; `Vec::into_raw_parts`; `VecDeque::pop_front_if` and `pop_back_if` | 1.93 |
| `array_windows`; `Peekable::next_if_map` | 1.94 |
| `if let` guards; `hint::cold_path`; `cfg_select!`; `Atomic*::update` and `try_update` | 1.95 |
| `core::range::Range`; `assert_matches!` and `debug_assert_matches!` | 1.96 |
| `CARGO_BUILD_WARNINGS=deny` | 1.97 |
| `<int>::format_into(&mut NumBuffer)` | 1.98 |
| `fs::set_times`, `File::set_times` | 1.99 |

## What changed silently

### RS-MIG-05 [M] Re-read what changed silently on every toolchain bump

Every `changed` row the rule column gives to RS-MIG-05 compiles before and after, and behaves
differently; so do these, which no spelling keys:

| Since | What changed |
|---|---|
| 1.99 | Cargo turns incremental compilation off when `CI` is set |
| 1.97 | v0 symbol mangling is the default, and `linker_messages` warns outside the `warnings` group |
| 1.94 | closure captures around patterns move, and a `Drop` can run at a different point |
| 1.91 | bindings drop in the order they are written |
| 1.75 | rustc makes the smallest non-generic functions inlinable across crates without `#[inline]` |

**Why:** nothing fails when these change, so the only defence is reading them against the code at
the moment the toolchain moves. A version bump that skips this step ships behaviour nobody chose.

**Check:** a review matter: on a toolchain bump, read each row newer than the old toolchain against
the diff's feature sets, `Ord` impls, drop order and anything that parses panic messages.
