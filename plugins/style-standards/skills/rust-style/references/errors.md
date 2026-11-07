# Errors: `Result`, Panics, and Exit Codes

Scope: when a failure is a `Result` and when it is a panic, how a library's error type is shaped and
what it must carry, how errors propagate and accumulate context, the panic rules including
`panic = "abort"`, how a binary reports failure and chooses an exit code, how a resource is released
on every path out (RAII, and a `Drop` that must not fail), and the shape of a function body around a
failure (`match` over a chain, a bounded recursion). A panic at the FFI boundary is RS-UNSAFE-24.
Naming of error types is in the naming chapter (RS-NAME-31); the `# Errors` and `# Panics` rustdoc
sections are in the documentation chapter; the deny rows that mechanically enforce this chapter are
in the build chapter's table.

The dividing line that organizes everything here: **libraries** must hand callers structured,
matchable, non-lossy errors, because the caller knows things the library does not. **Binaries** are
the end of the chain — nobody matches on their errors, so they may collapse everything into a report
and an exit code.

## Contents

- **Fundamentals**
  - RS-ERR-01 [M] Split failures into recoverable, caller-bug, and self-bug
  - RS-ERR-02 [M] Never discard a `Result` silently
  - RS-ERR-03 [M!] No `unwrap`, `expect`, or `panic!` on a recoverable path
  - RS-ERR-04 [M] Make an `expect` message state the invariant, not the symptom
  - RS-ERR-05 [M] Implement `Error` with a correct `source()`
  - RS-ERR-06 [M] Make `Display` describe this layer only
  - RS-ERR-07 [M!] Keep error types `Send + Sync + 'static`
  - RS-ERR-08 [M] Never throw away an error's information
  - RS-ERR-09 [M] Handle or propagate — never both

- **Designing error types**
  - RS-ERR-10 [M] Define one error enum per library, one variant per branchable failure
  - RS-ERR-11 [S] Derive the boilerplate with `thiserror`
  - RS-ERR-12 [M] Carry the context that identifies which operation failed
  - RS-ERR-13 [M] Never expose a catch-all error from a library
  - RS-ERR-14 [S] Offer inspection methods for the properties callers branch on
  - RS-ERR-15 [S] Prefer a struct with a private `kind` to a single-variant enum
  - RS-ERR-16 [S] Implement `Clone` on an error only when it is genuinely free
  - RS-ERR-17 [S] Keep foreign protocol codes as data, not as prose

- **Propagation and context**
  - RS-ERR-18 [M] Propagate with `?`; a re-wrapping `match` means a missing `From`
  - RS-ERR-19 [S] Add context at layer boundaries, not at every frame
  - RS-ERR-20 [M] Do not let `?` widen an error the caller needs to distinguish
  - RS-ERR-21 [S] Choose the lazy combinator when constructing the error costs anything
  - RS-ERR-22 [S] Put retry policy above the error type, not inside it
  - RS-ERR-23 [M] Do not use `Option` as an error channel

- **Panics**
  - RS-ERR-24 [S] Prefer restructuring, then `unreachable!`, then `panic!`
  - RS-ERR-25 [M] Choose `assert!` or `debug_assert!` by what a release build relies on
  - RS-ERR-26 [M!] Make overflow behaviour explicit on untrusted arithmetic and computed sizes
  - RS-ERR-27 [M] Do not choose `panic = "abort"` on a library's behalf

- **Binaries, reporting, exit codes**
  - RS-ERR-28 [S] Use `anyhow` inside binaries and only there
  - RS-ERR-29 [S] Return `ExitCode` and format the error yourself
  - RS-ERR-30 [M] Assign exit codes by convention, and document them
  - RS-ERR-31 [S] Print the cause chain, not a backtrace
  - RS-ERR-32 [M] Report every failure of a run over independent inputs, and finish the run

- **Cleanup**
  - RS-ERR-33 [M] Acquire in the constructor, release in `Drop`
  - RS-ERR-34 [M] Make `Drop` infallible and offer an explicit `finish`

- **The shape of a function**
  - RS-ERR-35 [M] Write a `match`, not an `if`/`else if` chain, on one value
  - RS-ERR-36 [M!] Use an explicit worklist where recursion depth is unbounded

---

## Fundamentals

### RS-ERR-01 [M] Split failures into recoverable, caller-bug, and self-bug

A failure a caller could reasonably handle is a `Result`. A failure that indicates a bug in the
caller is a panic. A failure that indicates a bug in you is also a panic — but it must be
unreachable, not merely unlikely. A panic never reports invalid input, a missing file, a network
failure or a parse error: `catch_unwind` is not a `try`/`catch`, and under `panic = "abort"` it
catches nothing.

**Why:** `Result` says "you may recover"; a panic says "the program is already wrong". Getting it
backwards produces either a server that aborts on a malformed request, or a `Result` nobody can act
on because the only correct response is to fix the code.

**Check:** for each `Result`-returning function, name the caller action for at least one error
variant. If the only sane action is "file a bug", it should have been an assertion. For each panic,
name the input that reaches it — if a file, a socket, an argument or an environment variable can
produce it, it is a `Result`.

```rust
// verified
/// An operating condition is a `Result`; a programmer error would be a `debug_assert`.
///
/// # Errors
/// Returns [`Empty`] when the input has no fields.
pub fn first_field(line: &str) -> Result<&str, Empty> {
    line.split(',')
        .next()
        .filter(|field| !field.is_empty())
        .ok_or(Empty)
}

/// The line contained no fields.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[error("line was empty")]
pub struct Empty;
```

### RS-ERR-02 [M] Never discard a `Result` silently

`Result` is `#[must_use]`. If a failure is genuinely ignorable, say so explicitly and record why. A
`Result<(), Infallible>` cannot fail, and `unused_must_use` does not ask for it to be handled.

**Why:** `let _ = f();` and `#[allow(unused_must_use)]` both suppress the compiler's only warning
about an unhandled failure, and they read identically whether the author thought about it or not.
The comment is what distinguishes a decision from an oversight.

**Check:** does a `let _ =` discard a `Result`, or does `unused_must_use` fire? Each needs a comment
naming the reason the failure does not matter.

The same line twice — the comment is the entire difference:

```rust
// fragment — BAD: indistinguishable from an oversight
let _ = writeln!(stderr, "{err}");
```

```rust
// fragment — GOOD: the reason is recorded at the point of the decision
// Best effort: stderr may already be closed, and there is nowhere left to report it.
let _ = writeln!(stderr, "{err}");
```

### RS-ERR-03 [M!] No `unwrap`, `expect`, or `panic!` on a recoverable path

Also `todo!`, `unimplemented!`, fallible indexing (`v[i]`), and slicing (`&s[a..b]`).

*Relaxed form:* `unwrap` and `expect` are allowed in tests (the shipped `clippy.toml`). A binary,
`build.rs` or example member that wants `expect` on a genuine invariant relaxes `expect_used` in its
own `[lints]` table, with the reason — see RS-ERR-04 for the message.

**Why:** each one converts a handleable failure inside your crate into a process abort inside
someone else's server. This is the highest-cost defect in this standard, because the damage lands on
a party who had no say in the decision and cannot work around it.

**Check:** mechanically: `assets/Cargo.toml` denies `unwrap_used`, `expect_used`, `panic`, `todo`,
`unimplemented` and `indexing_slicing`. The command for a codebase that has not adopted them yet:

```bash
# fragment — the grep, until the lints are adopted
rg -n '\.unwrap\(\)|\.expect\(|panic!|todo!|unimplemented!' \
   --glob '!**/tests/**' --glob '!**/benches/**' --glob '!**/examples/**'
```

```rust
// verified
/// The error is handled here because this layer is the one that can act on it.
#[must_use]
pub fn width_or_default(raw: &str) -> u32 {
    raw.parse().unwrap_or(80)
}
```

### RS-ERR-04 [M] Make an `expect` message state the invariant, not the symptom

`.expect("regex was validated at construction")`, not `.expect("failed to compile regex")`.

**Why:** the symptom is already in the panic output — the reader can see which call failed. What
they cannot see is *why you believed it could not fail*, which is the only information that helps
locate the broken assumption. A message that restates the call adds nothing to the backtrace.

**Check:** read each message with "…but it did" appended. "Failed to compile regex, but it did" is
nonsense; "regex was validated at construction, but it was not" names the bug.

### RS-ERR-05 [M] Implement `Error` with a correct `source()`

Public error types implement `std::error::Error` — or `core::error::Error` in no-std — and return
the underlying cause from `source()`. The type can be named from outside the crate: it is in every
fallible signature, so it is public API whether it was documented or not.

**Why:** `source()` is how every reporter walks the chain — `anyhow`'s `{:#}`, `eyre`'s handlers,
`tracing`'s error fields. Omitting it truncates the diagnostics of every downstream user, and they
cannot fix it from their side.

**Check:** for each error variant that wraps another error, is that error reachable through
`source()`? With `thiserror`, that means a `#[source]` or `#[from]` attribute on the field — a plain
field is not enough. Then name the type from a test outside the crate.

```rust
// verified
use std::io;

/// `#[source]` builds the chain; the reporter walks it rather than re-printing it.
#[derive(Debug, thiserror::Error)]
#[error("could not open the index")]
pub struct OpenFailed {
    #[source]
    source: io::Error,
}

impl OpenFailed {
    #[must_use]
    pub fn new(source: io::Error) -> Self {
        Self { source }
    }
}
```

### RS-ERR-06 [M] Make `Display` describe this layer only

One lowercase clause, no trailing period, no cause text: `"failed to read config file"`.

**Why:** the reporter concatenates the chain, so a `Display` that embeds its source shows each cause
twice: `failed to read config: No such file: No such file`. Lowercase and no period, because the
string is a fragment that gets composed, not a sentence.

**Check:** does any `Display` impl (or `#[error("…")]` string) interpolate a field that is itself an
error? Print the full chain with `{:#}` and look for repetition.

```rust
// fragment — BAD: duplicates the source in the chain output
#[error("failed to read {path}: {source}")]
Read { path: PathBuf, #[source] source: io::Error },
```

```rust
// fragment — GOOD: this layer only; the reporter appends the cause
#[error("failed to read {path}")]
Read { path: PathBuf, #[source] source: io::Error },
```

### RS-ERR-07 [M!] Keep error types `Send + Sync + 'static`

An error type that holds a `!Send` resource — a raw handle, a single-threaded runtime object — says
so in its rustdoc, since it cannot have them.

*Relaxed form:* leave the bounds out until a caller needs one.

**Why:** without those bounds the error cannot cross a thread, be stored in `anyhow::Error`, or be
returned from a spawned task — and callers discover this deep in a refactor, with no fix except
wrapping your type in theirs.

**Check:** add a compile-time assertion in the test module — it costs one line and catches the
regression the day a `Rc` or a `dyn Trait` field sneaks in.

```rust
// verified
/// A public error type is `Send + Sync + 'static` so callers can box and move it.
#[derive(Debug, thiserror::Error)]
#[error("configuration is invalid")]
pub struct Error;

const _: fn() = || {
    fn assert_send_sync_static<T: Send + Sync + 'static>() {}
    assert_send_sync_static::<Error>();
};
```

### RS-ERR-08 [M] Never throw away an error's information

`map_err(|_| MyError::Io)` discards the `io::Error` and the operating system's message with it.

**Why:** the discarded message is usually the entire diagnostic. "Io error" tells the user nothing;
"Permission denied (os error 13)" tells them exactly what to do. Once the information is dropped at
one layer, no amount of reporting machinery downstream can recover it.

**Check:** `rg -n -F 'map_err(|_|' -g '*.rs'` lists every erased error; each that is not a
deliberate, commented decision is the finding, and so is an `.ok()` on a `Result` whose error is not
itself logged.

```rust
// fragment — BAD
.map_err(|_| Error::Io)?
```

```rust
// fragment — GOOD: the From impl carries the source, and `?` applies it
.map_err(Error::Io)?
```

### RS-ERR-09 [M] Handle or propagate — never both

Either recover from the error here (log it, fall back, continue) or return it and let the caller
decide.

**Why:** log-and-return produces the same failure in the log twice — once from you and once from
whoever finally handles it — and leaves nobody clearly responsible for it. Duplicate diagnostics are
worse than none, because they make the log's line count meaningless as a signal.

**Check:** does a block log an error and also return it, with `return Err` or a `?` on the same
value? The legitimate exception is a boundary that is genuinely the last handler and re-raises for
control flow — say so in a comment.

## Designing error types

### RS-ERR-10 [M] Define one error enum per library, one variant per branchable failure

Not one variant per call site, and not one variant total. Not one error type per module either: one
crate-level `Error` with well-chosen variants beats fifteen types that need `From` impls between
them. Split only when a sub-API is genuinely independent — the way `grep-matcher` and
`grep-searcher` are separate crates, not separate modules.

**Why:** the variant set is the caller's vocabulary for recovery: too few and "file missing"
(retryable) is not "file corrupt" (not); too many and the enum is a log of your call graph. N types
also need N² conversions, each a place `source()` can be dropped.

**Check:** for each variant, name a caller who would branch on it and what they would do. A variant
nobody branches on either merges into a neighbour or becomes a field on one. Count the `From` impls
between your own error types: more than a couple is the signal.

### RS-ERR-11 [S] Derive the boilerplate with `thiserror`

It generates `Display`, `Error`, `source()`, and `From` from attributes, and adds nothing at
runtime.

**Why:** hand-written error impls are twenty lines of mechanical code per type, and the mechanical
part is where `source()` gets forgotten (RS-ERR-05). The proc macro costs compile time, a trade
worth making for an error type (RS-MACRO-17).

**Check:** a hand-written error impl is fine, but it must have `source()`, and the `Display` must
satisfy RS-ERR-06.

### RS-ERR-12 [M] Carry the context that identifies which operation failed

The path, the key, the byte offset, the line number, the URL — whatever distinguishes this
invocation from the other forty. Print a path or an `OsStr` with `.display()`, never `{:?}`
(RS-CLI-11).

**Why:** "file not found" forces the user to guess which of their files. The information is free at
the point of failure and unrecoverable afterwards, because the stack that knew the path has already
unwound.

**Check:** read each error message as a user with a thousand inputs. Can they tell which one broke?
If not, the variant needs a field.

### RS-ERR-13 [M] Never expose a catch-all error from a library

Not `Box<dyn Error>`, not `anyhow::Error`, and not an `Other(String)` variant (nor `Msg(String)`,
nor `Custom(String)`): not as the error type, not as a variant payload, not behind a type alias. In
a binary, where nobody matches, `anyhow::Error` is correct (RS-ERR-28).

**Why:** it erases the variant set, so callers cannot match, recover selectively, or test for a
specific failure. An `Other(String)` is `Box<dyn Error>` with extra steps: every failure nobody
wanted to model lands in it, and the taxonomy stops growing.

**Check:** does `Box<dyn Error` or `anyhow::` appear in a type a downstream crate can name?
`cargo public-api` lists what is reachable when you are unsure. Does a variant carry a `String` that
is a message rather than data (a key, a name, a token)? If a failure genuinely has no structure,
that is a signal it has not been analyzed yet.

```rust
// verified
/// The error set is explicit, so a caller can match it exhaustively.
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[non_exhaustive]
pub enum ParseError {
    #[error("unexpected end of input")]
    UnexpectedEnd,
    #[error("unexpected byte at offset {offset}")]
    UnexpectedByte { offset: usize },
}
```

### RS-ERR-14 [S] Offer inspection methods for the properties callers branch on

`fn is_not_found(&self) -> bool`, `fn kind(&self) -> ErrorKind`, `fn is_retryable(&self) -> bool`.

**Why:** this is what `io::Error` does, and it is why `io::Error` survived a decade of additions
without a breaking change: callers depend on the *question*, not on the variant that answers it, so
the variant set stays free to evolve.

**Check:** what do callers actually ask of this error? If the answer is "whether it is worth
retrying", ship that method rather than making everyone re-derive it from six variants.

### RS-ERR-15 [S] Prefer a struct with a private `kind` to a single-variant enum

`pub struct Error { kind: ErrorKind, … }` with `pub fn kind(&self) -> ErrorKind`.

**Why:** it is the most evolvable shape available: variants can be added, fields can be added, and
the internal representation can change entirely, all without a breaking change — because callers
never named the layout. `io::Error` and `std::num::ParseIntError` are both built this way.

**Check:** a one-variant `pub enum` gains nothing over a struct and locks the shape in. If the
variant set is genuinely one, use a struct.

```rust
// verified
use std::num::{NonZeroU32, ParseIntError};

/// What a caller can branch on; a new kind is a minor version.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum SettingErrorKind {
    NotANumber,
    Zero,
}

/// The layout is private, so a field can be added without a breaking change.
#[derive(Debug, thiserror::Error)]
#[error("invalid value for setting {name}")]
pub struct SettingError {
    kind: SettingErrorKind,
    name: String,
    #[source]
    source: Option<ParseIntError>,
}

impl SettingError {
    #[must_use]
    pub fn kind(&self) -> SettingErrorKind {
        self.kind
    }
}

/// # Errors
/// Returns a [`SettingError`] whose kind says why `raw` was rejected.
pub fn parse_setting(name: &str, raw: &str) -> Result<NonZeroU32, SettingError> {
    let fail = |kind, source| SettingError {
        kind,
        name: name.to_owned(),
        source,
    };
    let value: u32 = raw
        .parse()
        .map_err(|e| fail(SettingErrorKind::NotANumber, Some(e)))?;
    NonZeroU32::new(value).ok_or_else(|| fail(SettingErrorKind::Zero, None))
}
```

### RS-ERR-16 [S] Implement `Clone` on an error only when it is genuinely free

Do not force `Clone` by dropping the `io::Error` source.

**Why:** `io::Error` is not `Clone`, so deriving `Clone` on an error that wraps one requires
replacing it with a `String` or an `ErrorKind` — trading permanent information loss (RS-ERR-08) for
a convenience the caller can get another way.

**Check:** if callers need to clone the error, ask what they do with the copy. Usually they want to
report it twice, which `Arc<Error>` or a formatted string at the report site solves without changing
the type.

### RS-ERR-17 [S] Keep foreign protocol codes as data, not as prose

`StatusCode(u16)`, `Errno(i32)`, the vendor's own error number.

**Why:** translating to prose at the point of capture is lossy and premature: the caller may want to
branch on `429` specifically, and the reporter may want to render it differently for a machine
consumer than for a terminal. Translation is the reporter's job.

**Check:** does any variant store a message where the protocol supplied a code? Store both if the
protocol supplies both.

## Propagation and context

### RS-ERR-18 [M] Propagate with `?`; a re-wrapping `match` means a missing `From`

**Why:** `?` applies `From` automatically, so a `match` that exists only to map one error type onto
another is boilerplate the compiler would have written. It is also a place a `source()` gets lost by
hand.

**Check:** does a `match` or `if let Err` exist only to return a converted error? Each is a missing
`#[from]`.

```rust
// fragment — BAD
let text = match fs::read_to_string(path) {
    Ok(t) => t,
    Err(e) => return Err(Error::Io(e)),
};
```

```rust
// fragment — GOOD: with #[from] on the variant
let text = fs::read_to_string(path)?;
```

### RS-ERR-19 [S] Add context at layer boundaries, not at every frame

**Why:** three layers of "failed to X: failed to Y: failed to Z" is informative; ten is noise that
buries the root cause under your own call stack. Context earns its place when it names something the
next layer down could not know — usually a resource identifier, not an operation name.

**Check:** print a real failure's full chain. Can you read the root cause without scrolling? Do any
two links say substantially the same thing?

### RS-ERR-20 [M] Do not let `?` widen an error the caller needs to distinguish

**Why:** `?` composes conversions silently, which is its virtue and its hazard: an inner function
returning a precise `ParseError` can be widened to a catch-all variant by a single `?` in a wrapper,
and the caller's ability to branch disappears without a compile error anywhere.

**Check:** for each public function, does its error type distinguish everything its documentation
promises to distinguish? Test it by matching the variant, not by reading the code (RS-TEST-13).

### RS-ERR-21 [S] Choose the lazy combinator when constructing the error costs anything

`ok_or_else` over `ok_or`, `unwrap_or_else` over `unwrap_or`, `map_or_else` over `map_or` — and,
with `anyhow`, `.with_context(|| format!("reading {}", path.display()))` over
`.context(format!(…))`.

**Why:** the eager form evaluates its argument on the success path too.
`ok_or(Error::NotFound { path: path.to_owned() })` allocates the `PathBuf` every single time the
lookup succeeds.

**Check:** is the argument of an `ok_or(`, `unwrap_or(` or `map_or(`, or of a `.context(format!`,
something that allocates, formats, or calls a function? Each is the finding — a `Copy` constant is
fine. The converse — a closure around a constant — is clippy's `unnecessary_lazy_evaluations`.

```rust
// verified
/// `ok_or_else` builds the error only on the failing path.
///
/// # Errors
/// Returns [`NotFound`] when no entry matches.
pub fn lookup(entries: &[(String, u32)], key: &str) -> Result<u32, NotFound> {
    entries
        .iter()
        .find(|(name, _)| name == key)
        .map(|&(_, value)| value)
        .ok_or_else(|| NotFound {
            key: key.to_owned(),
        })
}

/// No entry matched the requested key.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("no entry named {key}")]
pub struct NotFound {
    key: String,
}
```

### RS-ERR-22 [S] Put retry policy above the error type, not inside it

Expose `fn is_retryable(&self) -> bool`; let the caller own the backoff and the budget.

**Why:** the library does not know whether it is inside a batch job that can wait ten minutes or a
request handler with a 200 ms budget. Baked-in retries also compose catastrophically: three layers
each retrying three times is twenty-seven attempts.

**Check:** does any library function sleep, loop, or take a retry count? That policy belongs to the
caller.

### RS-ERR-23 [M] Do not use `Option` as an error channel

`None` cannot carry a reason.

**Why:** a function that can fail for more than one cause and returns `Option` forces the caller to
guess, and forces you to log the reason instead of returning it (violating RS-ERR-09). `Option`
means *absent* — a key that is not in the map, a field that was not set — not *failed*.

**Check:** for each `Option`-returning function, is there exactly one reason it can be `None`, and
is that reason obvious from the name? `HashMap::get` passes; `parse_config` does not.

```rust
// verified
/// `Option` for ordinary absence; `Result` is reserved for something going wrong.
#[derive(Debug, Default)]
pub struct Headers {
    entries: Vec<(String, String)>,
}

impl Headers {
    #[must_use]
    pub fn get(&self, name: &str) -> Option<&str> {
        self.entries
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case(name))
            .map(|(_, value)| value.as_str())
    }
}
```

## Panics

### RS-ERR-24 [S] Prefer restructuring, then `unreachable!`, then `panic!`

**Why:** a branch that "cannot happen" is usually a type that is too wide, and making it
unrepresentable removes the branch entirely (RS-API-21). Where the branch must exist,
`unreachable!("…")` says *why* you believe it, the information RS-ERR-04 asks for.

**Check:** for each `unreachable!`, can the enum, the newtype, or the signature be narrowed so the
arm disappears?

### RS-ERR-25 [M] Choose `assert!` or `debug_assert!` by what a release build relies on

`assert!`/`assert_eq!` run in release; `debug_assert!`, `debug_assert_eq!`, and
`debug_assert_matches!` (imported with `use std::debug_assert_matches;`) do not.

**Why:** `debug_assert!` compiles to nothing in release, so anything a release build depends on must
not live there. Conversely, an expensive O(n) invariant check inside `assert!` is a release-mode
performance bug. The distinction is a decision, not a spelling preference.

**Check:** for each `debug_assert!`, would a release build be unsound or wrong if the condition were
false? If yes, promote it. For each `assert!`, is it O(1)? If not, demote it or hoist it out of the
hot path.

```rust
// verified
/// A `debug_assert` states an internal invariant without costing anything in release.
#[must_use]
pub fn split_point(low: u32, high: u32) -> u32 {
    debug_assert!(low < high, "a search step needs a non-empty range");
    low.midpoint(high)
}
```

### RS-ERR-26 [M!] Make overflow behaviour explicit on untrusted arithmetic and computed sizes

Integer overflow panics in debug and wraps in release, by default. On untrusted values and on sizes
computed from the input — lengths, offsets, parsed numbers — choose the behaviour: `checked_*`,
`saturating_*`, `wrapping_*`, or `strict_*`, which panics in both profiles where overflow is a bug
rather than an input. A value with a proven internal bound, such as a counter over a fixed array,
asserts that bound instead.

*Relaxed form:* the default behaviour, with a `debug_assert!` of each bound the arithmetic assumes.

**Why:** that is a correctness fork: debug and release are two different programs on the same input.
On attacker-influenced values the release behaviour is a silent wrong answer that frequently becomes
a bounds bug two lines later.

**Check:** for each arithmetic on lengths, offsets, and parsed numbers, can either operand originate
outside the process, or grow with the input? If yes, it must be one of the four, chosen
deliberately, not whichever compiles.

```rust
// verified
/// On untrusted sizes the behaviour must not depend on the build profile.
#[must_use]
pub fn total_len(parts: &[usize]) -> Option<usize> {
    parts
        .iter()
        .try_fold(0_usize, |acc, &part| acc.checked_add(part))
}
```

### RS-ERR-27 [M] Do not choose `panic = "abort"` on a library's behalf

It is the application's decision, set in its own profile.

**Why:** it removes `catch_unwind` from the whole dependency graph, silently breaking test
harnesses, FFI wrappers (RS-UNSAFE-24), and worker pools that isolate task failures. In a library's
`Cargo.toml` it is ignored anyway: only the workspace root sets profiles.

**Check:** `rg -n 'panic = "abort"' -g '*.toml'` finds the setting; each hit outside the top-level
binary's profile is the finding.

## Binaries, reporting, exit codes

### RS-ERR-28 [S] Use `anyhow` inside binaries and only there

Or `eyre`, if you want custom report handlers.

**Why:** the binary is the end of the chain — nobody matches on its errors — so the flexibility of a
dynamic error costs nothing and the `.context()` ergonomics are worth a great deal. The same type is
a defect in a library for exactly the reason it is right here (RS-ERR-13).

**Check:** is `anyhow` in the library crate's `[dependencies]`? It should be in the binary's.

### RS-ERR-29 [S] Return `ExitCode` and format the error yourself

Rather than `fn main() -> Result<…>`, which prints the `Debug` representation.

**Why:** `Debug` output is developer-facing and leaks the error's internal structure into a
user-facing channel: `Error: Read { path: "/etc/x", source: Os { code: 2, kind: NotFound, … } }`.
Formatting it yourself gives you the cause chain in prose, and control over the exit code.

**Check:** does the program's failure output look like something you would show a user?

### RS-ERR-30 [M] Assign exit codes by convention, and document them

`0` success, `1` a handled failure, `2` a usage error. Search-style tools follow grep: `0` match
found, `1` no match, `2` error.

**Why:** scripts branch on the exit code and cannot branch on prose. Choosing them casually — or
returning `1` for a usage error — breaks `set -e` pipelines in ways that are very hard to debug from
the other side.

**Check:** are the codes documented in `--help` and the man page, and covered by an end-to-end test
(RS-TEST-28)?

```rust
// verified
use std::process::ExitCode;

/// Distinct exit codes let a script tell the failure modes apart.
#[must_use]
pub fn code_for(outcome: Result<u32, Failure>) -> ExitCode {
    match outcome {
        Ok(_) => ExitCode::SUCCESS,
        Err(Failure::Usage) => ExitCode::from(2),
        Err(Failure::NotFound) => ExitCode::from(1),
    }
}

/// Why the run did not succeed.
#[derive(Debug, Clone, Copy, thiserror::Error)]
pub enum Failure {
    #[error("bad usage")]
    Usage,
    #[error("nothing matched")]
    NotFound,
}
```

### RS-ERR-31 [S] Print the cause chain, not a backtrace

Let `RUST_BACKTRACE=1` add the rest.

**Why:** a backtrace on every failure trains users to ignore the output, and it exposes internal
structure that is not part of your contract. The environment variable is a convention users already
know, so opting in costs them nothing.

**Check:** does a routine failure — a missing file, a bad flag — produce more than a few lines?

### RS-ERR-32 [M] Report every failure of a run over independent inputs, and finish the run

A run over inputs that do not depend on each other — the files of a traversal, the entries of a
configuration, the fields of a form — attempts each one and reports each failure, on stderr in a
binary; a validator returns `Vec<Error>`, or a `Report` type holding them, rather than the first.
The run still exits non-zero when anything failed.

**Why:** aborting a ten-thousand-file traversal because one file is unreadable throws away the work,
and stopping at a configuration's first error turns a two-minute fix into ten edit-run cycles.
ripgrep reports and carries on, which is why it is usable on a filesystem with unreadable parts.

**Check:** does an unreadable input, a broken symlink, or a non-UTF-8 filename stop the whole run?
Does a validator stop at its first error when the user plausibly has several? Is the exit code still
non-zero when something failed?

```rust
// verified
use std::process::ExitCode;

/// Every input is attempted; the failures are reported and the exit code records them.
#[must_use]
pub fn run_all(inputs: &[Result<u32, String>]) -> ExitCode {
    let mut failed = false;
    for input in inputs {
        match input {
            Ok(_value) => {}
            Err(message) => {
                eprintln!("{message}");
                failed = true;
            }
        }
    }
    if failed {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}
```

## Cleanup

### RS-ERR-33 [M] Acquire in the constructor, release in `Drop`

**Why:** RAII makes the release unforgettable, including on early return and on panic. Exposing
`open`/`close` pairs means every caller must get every path right, and the one they miss is the
error path they never tested.

**Check:** does the API have a `close`, `release`, `unlock`, or `end` that a caller must remember to
call? That is a guard type.

### RS-ERR-34 [M] Make `Drop` infallible and offer an explicit `finish`

Offer `fn finish(self) -> Result<T, Error>` for the path that can fail, and let `Drop` be the
best-effort fallback for the path that forgot.

**Why:** `Drop` cannot return a `Result`, so a failing flush or commit is silently swallowed —
`BufWriter` loses the last block and nobody finds out. A `Drop` that panics while another panic
unwinds aborts the process, with no cleanup anywhere.

**Check:** does any `Drop` impl perform I/O, commit, or flush? Is there a fallible alternative the
caller can use? Does any `Drop` call `unwrap`, `expect`, `assert`, or anything else that can panic?

```rust
// verified
use std::io::{self, Write};

/// `Drop` on a buffered writer swallows the error, so flush explicitly and check it.
///
/// # Errors
/// Returns the first write or flush error encountered.
pub fn write_all(mut sink: impl Write, lines: &[String]) -> io::Result<()> {
    for line in lines {
        writeln!(sink, "{line}")?;
    }
    sink.flush()
}
```

## The shape of a function

### RS-ERR-35 [M] Write a `match`, not an `if`/`else if` chain, on one value

**Why:** `match` gives exhaustiveness checking, so adding an enum variant produces a compile error
instead of silently falling through to the `else`. It also reads as a table rather than as a
sequence of tests, which is what it actually is.

**Check:** do two or more `else if` arms test the same subject? If the subject is an enum, this is a
missing exhaustiveness check, not a style preference.

### RS-ERR-36 [M!] Use an explicit worklist where recursion depth is unbounded

A recursion whose depth a constant bounds — an expression AST from your own builder, a directory
walk with a depth cap — asserts that constant at entry and stays recursive.

*Relaxed form:* recursion whose depth the input decides, accepting the stack overflow it risks.

**Why:** Rust has no guaranteed tail-call elimination, so recursion over attacker-controlled depth
is a stack overflow — which aborts immediately and cannot be caught. A `Vec` used as a worklist is
still functional in spirit, is bounded by the heap, and can be depth-limited with one comparison.

**Check:** for each recursive function, what bounds the depth? If the answer is "the input", it
needs a worklist or an asserted cap.
