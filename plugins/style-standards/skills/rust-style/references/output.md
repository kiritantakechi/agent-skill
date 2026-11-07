# Output: Streams, Logging, Exit Status, and Rendering

Scope: what a Rust program writes and how it ends: results to stdout and diagnostics to stderr, one
record per write, the flush before exit, colour, logging through a facade, how a failure is printed
and which status the run exits with, and how a value renders (`Debug`, `Display`). Parsing
arguments, a closed pipe, progress and the machine-readable mode are the cli chapter's; how a
failure is carried to the place that prints it is the errors chapter's; buffering for speed is the
performance chapter's.

## Contents

- **Where output goes**
  - RS-OUT-01 [M] Send results to stdout and diagnostics to stderr
  - RS-OUT-02 [M] Write each record to a shared stream in one locked call
  - RS-OUT-03 [M] Never print, and never exit, from a library
  - RS-OUT-04 [M] Flush explicitly before exiting, and check the result
  - RS-OUT-05 [M] Respect `NO_COLOR`, `CLICOLOR_FORCE`, and `TERM=dumb`
- **Logging**
  - RS-OUT-06 [M] Use structured logging for diagnostics, never `println!`
  - RS-OUT-07 [M] Log from a library through the facade, and install no logger
- **Failure and exit status**
  - RS-OUT-08 [M] Print a failure as its cause chain in prose, never as `Debug` output or a backtrace
  - RS-OUT-09 [M] Assign exit codes by convention, and document them
- **Rendering a value**
  - RS-OUT-10 [M] Implement `Debug` on every public type
  - RS-OUT-11 [M] Keep `Debug` for programmers and `Display` for users
  - RS-OUT-12 [S] Implement `Display` only when there is one obvious rendering

---

## Where output goes

### RS-OUT-01 [M] Send results to stdout and diagnostics to stderr

Results go to stdout, diagnostics to stderr. This single rule is what makes a tool composable:
`tool | grep`, `tool > file`, and `tool 2> log` all behave as the user expects.

**Why:** the two streams exist precisely so that data and commentary can be routed separately. A
warning on stdout corrupts every pipeline the tool appears in, and the corruption is silent.

**Check:** run `tool > /dev/null` and confirm only diagnostics remain; run `tool 2>/dev/null` and
confirm the data is intact.

```rust
// verified
use std::io::{self, Write};

/// Results to the sink the caller chose, diagnostics to another: composable either way.
///
/// # Errors
/// Propagates any write error.
pub fn emit(
    mut results: impl Write,
    mut diagnostics: impl Write,
    lines: &[String],
) -> io::Result<()> {
    for line in lines {
        if line.is_empty() {
            writeln!(diagnostics, "skipped an empty line")?;
        } else {
            writeln!(results, "{line}")?;
        }
    }
    results.flush()
}
```

### RS-OUT-02 [M] Write each record to a shared stream in one locked call

A record leaves for `stdout` or `stderr` in one `println!` or `writeln!`, and a record of several
lines under one `stdout().lock()` held across them. A line assembled from several `print!` calls
takes the lock each time, so another thread's output can land inside it.

**Why:** the lock is per call, not per line. Two threads that each print `name`, `: ` and `detail`
with three calls interleave their pieces, and the log that results cannot be parsed.

**Check:** `rg -n '\be?print!\(' -g '*.rs'` — a `print!` that does not end its line, on a path
another thread can reach, is the finding.

```rust
// verified — GOOD
use std::io::{self, Write};

/// Both lines of the record leave under one lock.
///
/// # Errors
/// Propagates any write error.
pub fn print_record(name: &str, detail: &str) -> io::Result<()> {
    let mut out = io::stdout().lock();
    writeln!(out, "{name}")?;
    writeln!(out, "  {detail}")
}
```

```rust
// verified — BAD: another thread's output can land between the pieces
pub fn print_record(name: &str, detail: &str) {
    print!("{name}: ");
    println!("{detail}");
}
```

### RS-OUT-03 [M] Never print, and never exit, from a library

A library function returns a `Result` and writes only to a `Write` the caller passed in (RS-OUT-01)
or through the `log` facade (RS-OUT-07). It does not call `std::process::exit`, `println!`,
`print!`, `eprintln!` or `eprint!`; those belong to the binary's `main`.

**Why:** a library cannot know where its caller's output goes or whether the caller can recover.
`process::exit` also runs no destructor, so every buffered writer and guard on the stack is lost.

**Check:** `rg -n 'process::exit|\be?print(ln)?!' -g '*.rs'` — each hit in library code, which is
neither `main.rs`, nor `src/bin/`, nor a test or an example, is the finding.

```rust
// verified — GOOD: the library reports to the sink it was given and returns
use std::io::{self, Write};

/// # Errors
/// Propagates any write error.
pub fn report(mut out: impl Write, matched: usize) -> io::Result<()> {
    writeln!(out, "{matched} matched")
}
```

```rust
// verified — BAD: the library decides what is said and how the process ends
#[must_use]
pub fn parse_port(raw: &str) -> u16 {
    raw.parse().unwrap_or_else(|_| {
        eprintln!("port must be a number, got {raw}");
        std::process::exit(2)
    })
}
```

### RS-OUT-04 [M] Flush explicitly before exiting, and check the result

`BufWriter` flushes on drop but swallows the error (RS-ERR-30).

**Why:** buffering means the last write is still in memory when `main` returns, and `Drop` cannot
report a failure. A full disk or a closed pipe silently truncates the output — the failure
introduced by the optimization in RS-PERF-19.

**Check:** is there an explicit `flush()` whose `Result` is handled before exit?

```rust
// verified
use std::io::{self, Write};

/// The flush is explicit and its result is propagated, not dropped by `Drop`.
///
/// # Errors
/// Returns the flush error if the final block cannot be written.
pub fn finish(mut sink: impl Write) -> io::Result<()> {
    sink.flush()
}
```

### RS-OUT-05 [M] Respect `NO_COLOR`, `CLICOLOR_FORCE`, and `TERM=dumb`

Provide `--color=auto|always|never` with `auto` as the default, and use `anstream`/`termcolor`
rather than emitting escape codes by hand — Windows console handling is not something to
reimplement.

**Why:** these are the cross-tool conventions users configure once and expect everything to honour.
Hand-written escape sequences also break on Windows consoles and in CI logs, where the codes end up
as visible garbage.

**Check:** run with `NO_COLOR=1` and with output piped. Neither should contain escape sequences.

```rust
// verified
/// `NO_COLOR` and `TERM=dumb` win over the default, and `--color` wins over both.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ColourChoice {
    Auto,
    Always,
    Never,
}

/// The three variables resolved into one answer. `CLICOLOR_FORCE` wins over `NO_COLOR`: it is the
/// explicit override, and it is what lets a CI job force colour into a captured log.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EnvColour {
    /// `NO_COLOR` is present, or `TERM` is `dumb`.
    Suppressed,
    /// `CLICOLOR_FORCE` is present: colour even when the stream is redirected.
    Forced,
    /// Nothing in the environment has an opinion.
    Permitted,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stream {
    Terminal,
    Redirected,
}

#[must_use]
pub fn should_use_colour(choice: ColourChoice, env: EnvColour, stream: Stream) -> bool {
    match choice {
        ColourChoice::Always => true,
        ColourChoice::Never => false,
        ColourChoice::Auto => match env {
            EnvColour::Suppressed => false,
            EnvColour::Forced => true,
            EnvColour::Permitted => stream == Stream::Terminal,
        },
    }
}
```

## Logging

### RS-OUT-06 [M] Use structured logging for diagnostics, never `println!`

Use structured logging (`tracing` or `log` plus `env_logger`) for diagnostics, controlled by
`-v`/`-vv` or `RUST_LOG`. Never `println!` for debugging in shipped code, and deny
`clippy::dbg_macro` (RS-BUILD-22).

**Why:** logging gives levels, targets, and runtime filtering; `println!` gives none of those and
cannot be turned off by the user. Debug prints that ship are also the most common way secrets end up
in logs.

**Check:** does shipped code report a diagnostic with `println!` or `eprintln!`? Each is the
finding. A `dbg!` is the `dbg_macro` row.

### RS-OUT-07 [M] Log from a library through the facade, and install no logger

A library emits its records with the `log` or `tracing` macros, whose target defaults to the module
path, so the application can filter it by crate. It never installs a logger or subscriber
(`env_logger::init`, `log::set_logger`, `tracing::subscriber::set_global_default`). The binary
installs one, once, at the top of `main` (RS-OWN-36).

**Why:** a process has one global logger. A library that installs it either panics when the
application does the same, or wins the race and fixes a format and destination the application
cannot change.

**Check:**
`rg -n 'env_logger::|set_logger|set_boxed_logger|set_global_default|tracing_subscriber' -g '*.rs'` —
each hit in library code, which is not `main.rs` or `src/bin/`, is the finding.

```rust
// verified — GOOD: the library emits, and the binary decides where records go
/// Counts the lines in `text`.
#[must_use]
pub fn count_lines(text: &str) -> usize {
    let count = text.lines().count();
    log::debug!("counted {count} lines");
    count
}
```

## Failure and exit status

### RS-OUT-08 [M] Print a failure as its cause chain in prose, never as `Debug` output or a backtrace

Return `ExitCode` from `main` and format the error yourself, rather than `fn main() -> Result<…>`,
which prints the `Debug` representation. Print the error and then each `source()` beneath it, one
line each. Let `RUST_BACKTRACE=1` add the rest.

**Why:** `Debug` output is developer-facing and leaks the error's structure into a user-facing
channel: `Error: Read { path: "/etc/x", source: Os { code: 2, kind: NotFound, … } }`. A backtrace on
every failure trains users to ignore the output; `RUST_BACKTRACE=1` costs them nothing to opt in.

**Check:** does the program's failure output look like something you would show a user? Does a
routine failure — a missing file, a bad flag — produce more than a few lines?

### RS-OUT-09 [M] Assign exit codes by convention, and document them

`0` success, `1` a handled failure, `2` a usage error. Search-style tools follow grep: `0` match
found, `1` no match, `2` error.

**Why:** scripts branch on the exit code and cannot branch on prose. Choosing them casually — or
returning `1` for a usage error — breaks `set -e` pipelines in ways that are very hard to debug from
the other side.

**Check:** are the codes documented in `--help` and the man page, and covered by an end-to-end test
(RS-TEST-29)?

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

## Rendering a value

### RS-OUT-10 [M] Implement `Debug` on every public type

No exceptions for "internal" types that appear in a public struct.

**Why:** a missing `Debug` poisons `#[derive(Debug)]` for every type containing it, makes
`assert_eq!` unusable in users' tests, and makes the value invisible in a debugger and in `tracing`
fields. The blast radius is far larger than the one type.

**Check:** rustc `missing_debug_implementations`, denied by the shipped configuration, fails the
build on a public type without one. Manual impls are fine; absence is not.

### RS-OUT-11 [M] Keep `Debug` for programmers and `Display` for users

**Why:** `Debug` output may change at any time and favours completeness; `Display` is part of the
contract and favours clarity. A `Display` that delegates to `Debug` publishes internal structure,
the defect in RS-OUT-08.

**Check:** does any `Display` impl call `{:?}`? Does any `Debug` impl omit a field to look tidier?

### RS-OUT-12 [S] Implement `Display` only when there is one obvious rendering

**Why:** `Display` takes no options, so if there are two reasonable renderings — short and verbose,
coloured and plain, absolute and relative — the trait forces you to pick one and users must
reimplement the other. Explicit methods can take arguments.

**Check:** are there two ways a user would reasonably want to print this? Then ship two methods,
each returning an `impl fmt::Display` built with `fmt::from_fn`, and skip the trait.

```rust
// verified
use std::fmt;

/// `Display` is for users; `Debug` is for developers. They are not the same text.
#[derive(Debug, Clone, Copy)]
pub struct Bytes(u64);

impl fmt::Display for Bytes {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let Self(raw) = *self;
        if raw < 1024 {
            write!(f, "{raw} B")
        } else {
            write!(f, "{} KiB", raw / 1024)
        }
    }
}
```

```rust
// verified
use std::fmt;

/// Two renderings, so two methods and no `Display`; neither allocates.
#[derive(Debug, Clone, Copy)]
pub struct Elapsed(u64);

impl Elapsed {
    #[must_use]
    pub fn short(self) -> impl fmt::Display {
        fmt::from_fn(move |f| write!(f, "{}s", self.0))
    }

    #[must_use]
    pub fn verbose(self) -> impl fmt::Display {
        fmt::from_fn(move |f| write!(f, "{} seconds", self.0))
    }
}

#[cfg(test)]
mod tests {
    use super::Elapsed;

    #[test]
    fn renders_both_forms() {
        assert_eq!(Elapsed(3).short().to_string(), "3s");
        assert_eq!(Elapsed(3).verbose().to_string(), "3 seconds");
    }
}
```
