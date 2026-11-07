# CLI: Arguments, Streams, Environment, and Signals

Scope: the shape of a command-line binary — what `main` does, how arguments become a validated
configuration, the flag table, `BrokenPipe`, presentation that adapts to a terminal, progress and
the machine-readable mode, signals, configuration files, environment variables and platform
directories. Which stream results and diagnostics go to, colour, logging, how a failure is printed
and which exit code a run chooses are the output chapter's; buffering output is the performance
chapter's; testing the binary end to end is the testing chapter's.

The reference implementation for this chapter is ripgrep. Its structure — a workspace of libraries,
a thin `core` binary, a two-stage argument model (`LowArgs` → `HiArgs`), a trait-per-flag table that
also generates the man page and shell completions, and obsessive attention to stream behaviour — is
what "production-grade Rust CLI" means in practice.

## Contents

- **Architecture**
  - RS-CLI-01 [M] Let `main` do exactly four things
  - RS-CLI-02 [M] Parse into a mechanical `LowArgs`, then transform into a validated `HiArgs`
  - RS-CLI-03 [M] Construct the high-level configuration once, and keep it immutable
  - RS-CLI-04 [M] Resolve configuration in a documented, tested precedence order
  - RS-CLI-05 [S] Provide an escape hatch that disables external configuration
  - RS-CLI-06 [S] Drive parsing, `--help`, the man page, and completions from one flag table
  - RS-CLI-07 [M] Give every flag a unit test over its parsed result
  - RS-CLI-08 [S] Put long-running work behind a trait so the CLI layer stays testable

- **Argument parsing**
  - RS-CLI-09 [S] Use `clap`'s derive API unless you have ripgrep's constraints
  - RS-CLI-10 [M] Follow POSIX/GNU conventions
  - RS-CLI-11 [M] Accept paths as `OsString`/`PathBuf`, never `String`
  - RS-CLI-12 [M] Give every config-settable boolean flag a negation
  - RS-CLI-13 [S] Split brief `-h` from complete `--help`, and end with real examples
  - RS-CLI-14 [S] Support `--version`, with the git hash and target triple
  - RS-CLI-15 [S] Add subcommands only when the tool genuinely does several things
  - RS-CLI-16 [M] On a usage error, print the one problem and a pointer to `--help`

- **Output and streams**
  - RS-CLI-17 [M] Handle `BrokenPipe` by exiting quietly with success
  - RS-CLI-18 [M] Adapt presentation to whether stdout is a terminal — never the data
  - RS-CLI-19 [S] Provide a machine-readable mode and version its schema
  - RS-CLI-20 [S] Say which output format is stable, and do not promise the other
  - RS-CLI-21 [M] Send progress to stderr, suppressed when not a terminal

- **Behaviour, environment, signals**
  - RS-CLI-22 [M] Read stdin when given no files, and treat `-` as stdin
  - RS-CLI-23 [M!] Make destructive operations opt-in, and never prompt when not a terminal
  - RS-CLI-24 [M] On `SIGINT`, restore the terminal and remove temporary files, then re-raise it
  - RS-CLI-25 [S] Respect the platform's directory conventions
  - RS-CLI-26 [M] Namespace and document every environment variable you read
  - RS-CLI-27 [M] Do not phone home, auto-update, or collect telemetry without opt-in
  - RS-CLI-28 [S] Ship a single binary with artifacts and checksums for three platforms

- Decided by tools

---

## Architecture

### RS-CLI-01 [M] Let `main` do exactly four things

`main` does four things: parse the arguments into a configuration, call `run`, report the error, and
return the exit code. Everything else is delegated.

**Why:** `main` is the one function that cannot return a `Result` to anybody, and what it does can
be tested only by running the process, while everything inside `run` is testable. Four steps keep
the error-reporting and exit-code policy in one readable place.

**Check:** read `main`. How many of its lines would an in-process end-to-end test have to duplicate?
That is the untested surface: more than about a dozen lines, or any business logic, is a finding.

```rust
// verified
use std::{ffi::OsString, process::ExitCode};

/// What the arguments asked for, parsed once.
#[derive(Debug)]
struct Config {
    inputs: Vec<OsString>,
}

fn run(config: &Config) -> Result<(), Failure> {
    if config.inputs.is_empty() {
        Err(Failure::NoInput)
    } else {
        Ok(())
    }
}

/// The run failed for a reason worth reporting.
#[derive(Debug, Clone, Copy, thiserror::Error)]
pub enum Failure {
    #[error("no input files")]
    NoInput,
}

/// Parse, run, report, exit — and nothing else.
fn main() -> ExitCode {
    let config = Config {
        inputs: std::env::args_os().skip(1).collect(),
    };
    match run(&config) {
        Ok(()) => ExitCode::SUCCESS,
        Err(failure) => {
            eprintln!("{failure}");
            ExitCode::FAILURE
        }
    }
}
```

### RS-CLI-02 [M] Parse into a mechanical `LowArgs`, then transform into a validated `HiArgs`

Parse arguments into a low-level, mechanical representation first (one field per flag, no
interpretation), then transform that into a validated, high-level configuration that the rest of the
program consumes. ripgrep calls these `LowArgs` and `HiArgs`; the separation keeps parsing free of
policy and policy free of parsing.

**Why:** flags interact — `--color=never` plus `--pretty`, `-l` plus `--count`. Resolving those
interactions during parsing scatters policy across the parser; resolving them after gives one
function where every interaction is visible and testable.

**Check:** is there a type that holds raw flag values and another that holds resolved policy? If one
type does both, the interactions are being decided in the parser.

```rust
// verified
use std::path::PathBuf;

/// A two-variant enum, so the call site reads `set_quiet(Quiet::Yes)` (RS-API-23).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Quiet {
    Yes,
    #[default]
    No,
}

/// Mechanical: one field per flag, no interpretation, no policy.
#[derive(Debug, Default)]
pub struct LowArgs {
    colour: Option<String>,
    paths: Vec<PathBuf>,
    quiet: Quiet,
}

impl LowArgs {
    pub fn set_colour(&mut self, value: String) {
        self.colour = Some(value);
    }

    pub fn push_path(&mut self, path: PathBuf) {
        self.paths.push(path);
    }

    pub fn set_quiet(&mut self, quiet: Quiet) {
        self.quiet = quiet;
    }
}

/// Resolved: every interaction between flags has already been decided.
#[derive(Debug)]
pub struct HiArgs {
    colour: bool,
    paths: Vec<PathBuf>,
}

impl HiArgs {
    #[must_use]
    pub fn wants_colour(&self) -> bool {
        self.colour
    }

    #[must_use]
    pub fn paths(&self) -> &[PathBuf] {
        &self.paths
    }
}

impl From<LowArgs> for HiArgs {
    fn from(low: LowArgs) -> Self {
        let colour = matches!(low.colour.as_deref(), Some("always")) && low.quiet == Quiet::No;
        Self {
            colour,
            paths: low.paths,
        }
    }
}
```

### RS-CLI-03 [M] Construct the high-level configuration once, and keep it immutable

The high-level configuration is immutable and constructed once. Downstream code takes `&Config` and
never re-reads the environment, the command line, or the config file.

**Why:** a function that reads the environment is a function whose behaviour cannot be reproduced in
a test, and one that mutates shared configuration makes the program's behaviour depend on call
order. An immutable value passed by reference has neither problem.

**Check:** is there an `env::var` or a configuration-file read outside the construction path? Each
is a hidden input.

```rust
// verified
/// Constructed once, then read-only: nothing downstream re-reads the environment.
#[derive(Debug, Clone)]
pub struct Config {
    threads: usize,
}

impl Config {
    #[must_use]
    pub fn new(threads: usize) -> Self {
        Self { threads }
    }

    #[must_use]
    pub fn threads(&self) -> usize {
        self.threads
    }
}
```

### RS-CLI-04 [M] Resolve configuration in a documented, tested precedence order

Resolve configuration in a documented precedence order: built-in defaults, then config file, then
environment, then command-line flags, with the last occurrence winning. Document it in `--help` and
the man page, and test it.

**Why:** precedence is the thing users get wrong and file bugs about, and every tool that leaves it
undocumented gets the same bug repeatedly. Testing it also pins behaviour that is easy to break
while refactoring the parser.

**Check:** is there a test that sets the same option at all four levels and asserts the winner? And
does `--help` state the order?

```rust
// verified
/// Defaults, then file, then environment, then flags — resolved in one place.
#[derive(Debug, Clone, Copy, Default)]
pub struct Resolved {
    threads: usize,
}

impl Resolved {
    #[must_use]
    pub fn thread_count(self) -> usize {
        self.threads
    }
}

#[must_use]
pub fn resolve(file: Option<usize>, env: Option<usize>, flag: Option<usize>) -> Resolved {
    Resolved {
        threads: flag.or(env).or(file).unwrap_or(1),
    }
}
```

### RS-CLI-05 [S] Provide an escape hatch that disables external configuration

One flag — ripgrep's `--no-config` — turns off every configuration file and environment default, so
a user can reproduce a clean run and a script is not affected by a developer's personal settings.

**Why:** a config file that silently changes behaviour makes bug reports unreproducible — the
maintainer cannot see the reporter's file. It also breaks scripts when a user later adds a personal
default.

**Check:** is there a single flag that makes the run depend only on the command line? If not, no bug
report can be trusted.

### RS-CLI-06 [S] Drive parsing, `--help`, the man page, and completions from one flag table

Keep the flag definitions in one table, with each flag as a value implementing a common trait: name,
short name, category, doc text, and an `update` method that writes into the low-level args. One
table drives parsing, `--help`, the man page, and shell completions — so they cannot drift apart.
Generate the completions and the man page from it at build time or through a hidden subcommand;
never edit them by hand.

**Why:** these four artifacts describe the same thing, and maintaining them separately guarantees
the man page is a release behind. Deriving them from one definition makes drift structurally
impossible rather than a review responsibility.

**Check:** add a flag. If more than one file has to change, the definitions are not unified. A
checked-in completion script with no regeneration command is hand-edited, and the finding.

### RS-CLI-07 [M] Give every flag a unit test over its parsed result

Every flag gets a unit test that parses a representative argument list and asserts on the resulting
low-level args. With a hundred flags this is the only way the matrix stays correct.

**Why:** flags are cheap to add and each one is a branch nobody exercises again. A per-flag test is
fast, mechanical, and catches the class of bug where a refactor silently drops a flag's effect.

**Check:** compare the flag count to the parser test count. A large gap is the list of untested
flags.

### RS-CLI-08 [S] Put long-running work behind a trait so the CLI layer stays testable

Long-running work belongs behind a trait or a callback so the CLI layer can be tested without doing
it. A CLI whose only test is "run the binary" has no fast tests.

**Why:** end-to-end tests are necessary (RS-TEST-29) but too slow to run per keystroke. A seam
between "decide what to do" and "do it" gives you fast tests for the decisions, which is where most
of the bugs are.

**Check:** can the argument-handling and policy layers be tested without touching the filesystem or
the network? If not, the seam is missing.

## Argument parsing

### RS-CLI-09 [S] Use `clap`'s derive API unless you have ripgrep's constraints

Use `clap` with the derive API for most tools: it is the ecosystem default, users recognize its
conventions, and the derive form keeps the definitions next to the types. Reach for a hand-written
parser only when you have ripgrep's constraints — a hundred flags, hard compile-time budgets, or
argument semantics that a general parser cannot express — and be honest that the trade is real work.

**Why:** `clap` gets the conventions, the error messages, and the help formatting right, and users
have seen them before. Hand-rolling is justified when the constraints are real, but it is a
permanent maintenance cost, not a weekend.

**Check:** if the parser is hand-written, name the constraint that forced it. "It seemed lighter" is
not one.

### RS-CLI-10 [M] Follow POSIX/GNU conventions

`-v` short, `--verbose` long, `--` terminating flags, `-abc` bundling for boolean shorts, and
`--flag=value` as well as `--flag value`. Users have muscle memory; do not surprise it.

**Why:** a CLI is used from muscle memory and inside scripts written by people who never read the
help. Deviating costs every user a small, permanent tax and breaks the composition patterns they
already know.

**Check:** test `--`, bundling, and both `=` and space forms. A tool that rejects `--flag=value` is
violating this.

### RS-CLI-11 [M] Accept paths as `OsString`/`PathBuf`, never `String`

Accept file paths as `OsString`/`PathBuf`, never as `String`. Not all filenames are valid UTF-8 on
either Unix or Windows, and rejecting them is a bug that surfaces only in the users' most annoying
directories. Print them with `Path::display` or `OsStr::display`, never `{:?}`, which
`clippy::unnecessary_debug_formatting` (pedantic) flags.

**Why:** on Unix a filename is bytes and on Windows it is UTF-16; neither is guaranteed to be UTF-8.
Forcing `String` makes the tool fail on exactly the files the user most needs a tool for, and the
failure looks like the tool is broken rather than opinionated.

**Check:** is any path-shaped argument typed `String`? Test with a non-UTF-8 filename (RS-TEST-29).

```rust
// verified
use std::{ffi::OsString, path::PathBuf};

/// Paths arrive as `OsString`, so a non-UTF-8 filename is not rejected at the door.
#[must_use]
pub fn to_paths(raw: Vec<OsString>) -> Vec<PathBuf> {
    raw.into_iter().map(PathBuf::from).collect()
}
```

### RS-CLI-12 [M] Give every config-settable boolean flag a negation

Provide a negation for every boolean flag that a config file can enable (`--color` / `--no-color`,
`--hidden` / `--no-hidden`), so a user can override their own configuration on the command line
(RS-NAME-27).

**Why:** precedence (RS-CLI-04) is only useful if the higher-precedence level can express both
values. Without a negation, a config-file `true` is unreachable from the command line, which makes
the config file a trap.

**Check:** for each boolean readable from config, is there a `--no-` form? Each missing one is a
setting the user cannot turn off. The pair is a *flag* pair on the command line; inside the program
it lands as a two-variant enum, never as a `bool` parameter (RS-API-23).

```rust
// verified
/// `--colour` and `--no-colour` both exist, so the command line can always win.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Colour {
    On,
    Off,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Flags {
    colour: Option<Colour>,
}

impl Flags {
    /// `--colour`.
    #[must_use]
    pub fn with_colour(mut self) -> Self {
        self.colour = Some(Colour::On);
        self
    }

    /// `--no-colour`.
    #[must_use]
    pub fn with_no_colour(mut self) -> Self {
        self.colour = Some(Colour::Off);
        self
    }

    /// The command line wins where it spoke; the config file is the fallback.
    #[must_use]
    pub fn resolve_colour(self, from_config: Colour) -> Colour {
        self.colour.unwrap_or(from_config)
    }
}
```

### RS-CLI-13 [S] Split brief `-h` from complete `--help`, and end with real examples

Make `--help` genuinely useful: a one-line summary, usage, flags grouped by category, and two or
three real examples at the end. Keep the short `-h` output brief and the long `--help` complete;
that split is what makes both usable.

**Why:** the two forms serve different moments — "I forgot the flag name" and "I am learning this
tool". One combined output fails both, and examples are the part users actually copy.

**Check:** is `-h` short enough to fit on a screen, and does `--help` end with runnable examples?

```rust
// verified
/// The short and long help are different documents, not the same one truncated.
#[must_use]
pub fn short_help() -> &'static str {
    "usage: mytool [OPTIONS] [PATH]...\n  -h, --help     brief help\n      --help     full help"
}

#[must_use]
pub fn long_help() -> String {
    let mut out = String::from(short_help());
    out.push_str("\n\nExamples:\n  mytool src/\n  mytool --json src/ | jq .\n");
    out
}
```

### RS-CLI-14 [S] Support `--version`, with the git hash and target triple

Support `--version` with the crate version, and consider adding the git hash and target triple for
bug reports.

**Why:** the first question on every bug report is "which build?", and a version number alone does
not distinguish a release from a local build of the same tag. The hash costs a build script and
removes a round trip.

**Check:** does `--version` identify the build uniquely enough to reproduce it?

### RS-CLI-15 [S] Add subcommands only when the tool genuinely does several things

Subcommands only when the tool genuinely does several things. A tool with one job and eleven flags
is easier to use than one with three subcommands sharing eight flags each.

**Why:** subcommands add a level of nesting to every invocation and every help page, and shared
flags across them are a source of inconsistency. They pay off when the verbs are genuinely
different, and cost otherwise.

**Check:** do the subcommands share most of their flags? If so, they are one command with a mode
flag.

### RS-CLI-16 [M] On a usage error, print the one problem and a pointer to `--help`

Name the flag or value that was wrong, point at `--help`, and exit with the usage code RS-OUT-09
assigns — never the entire help text on a typo.

**Why:** dumping the full help scrolls the actual error off the screen, which is the one thing the
user needed, and leaves them to find which of forty flags they mistyped.

**Check:** run the tool with a bad flag. The output should be one line naming the flag, plus a
pointer, and the exit code should be RS-OUT-09's usage code.

```rust
// verified
use std::process::ExitCode;

/// Usage errors get exit code 2, distinct from an operation that ran and failed.
#[must_use]
pub fn usage_error(flag: &str) -> ExitCode {
    eprintln!("unrecognised flag `{flag}`; run with --help for the list");
    ExitCode::from(2)
}
```

## Output and streams

### RS-CLI-17 [M] Handle `BrokenPipe` by exiting quietly with success

Every `tool | head` will otherwise print an error, and this is the most common polish defect in Rust
CLIs. Match on `io::ErrorKind::BrokenPipe` (Windows also reports it for a write after a socket
`shutdown`); the flag that restores C's behaviour, `-Zon-broken-pipe=kill`, is nightly-only.

**Why:** `head` closing the pipe is normal termination, not a failure — the user got what they asked
for. Rust sets `SIGPIPE` to `SIG_IGN` before `main`, so where a C program is killed silently by the
signal, a Rust write returns `BrokenPipe` and `println!` panics on it.

**Check:** run `tool | head -1`. Any error output or non-zero exit is a violation.

### RS-CLI-18 [M] Adapt presentation to whether stdout is a terminal — never the data

Detect whether stdout is a terminal and adapt: colour, progress bars, and column alignment when
interactive; plain, stable, line-oriented output when piped. Never change the *data*, only the
presentation.

**Why:** the distinction is what keeps the tool both pleasant and scriptable. Changing the data —
dropping columns, truncating, reordering — when piped breaks scripts in a way that is very hard to
diagnose, because it works when the user tests it by eye.

**Check:** diff `tool` against `tool | cat` with colour stripped. Any difference in the data, as
opposed to styling, is a violation.

```rust
// verified
/// The presentation adapts; the data does not.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Style {
    Plain,
    Coloured,
}

#[must_use]
pub fn render(row: &str, style: Style) -> String {
    match style {
        Style::Plain => row.to_owned(),
        Style::Coloured => format!("\x1b[1m{row}\x1b[0m"),
    }
}
```

### RS-CLI-19 [S] Provide a machine-readable mode and version its schema

Provide a machine-readable output mode (`--json`, or NDJSON for streaming) for anything a script
might consume, and treat its schema as a versioned API.

**Why:** without one, users parse the human output with regexes, and then every cosmetic improvement
you make is a breaking change for them. A declared machine format lets both audiences be served
without freezing the display.

**Check:** is there a documented, stable output format? If users parse the pretty output, the answer
is no.

### RS-CLI-20 [S] Say which output format is stable, and do not promise the other

Keep human-readable output stable enough to grep but do not promise it. Say in the docs which format
is stable (the JSON one) so users script against the right thing.

**Why:** an explicit statement is what makes a later change to the human format legitimate rather
than a broken promise. Silence is read as a guarantee.

**Check:** does the documentation say, in words, which format is covered by semver?

### RS-CLI-21 [M] Send progress to stderr, suppressed when not a terminal

Progress and status go to stderr, are suppressed when not a terminal, and are suppressible with
`--quiet`. A progress bar in a log file is a megabyte of carriage returns.

**Why:** progress is commentary, not data, so it belongs on stderr — and it is meaningless without a
terminal to redraw. Writing it unconditionally makes CI logs unreadable and inflates them
enormously.

**Check:** redirect stderr to a file. It should contain no carriage-return animation.

```rust
// verified
use std::io::{self, IsTerminal, Write};

/// Diagnostics bound to one stream, which remembers whether that stream is a terminal.
#[derive(Debug)]
pub struct Diagnostics<W> {
    sink: W,
    is_terminal: bool,
}

impl Diagnostics<io::Stderr> {
    /// Progress and status belong on stderr, so that is what this builds.
    #[must_use]
    pub fn stderr() -> Self {
        Self::new(io::stderr())
    }
}

impl<W: Write> Diagnostics<W> {
    /// Asks the stream once, at construction.
    #[must_use]
    pub fn new(sink: W) -> Self
    where
        W: IsTerminal,
    {
        let is_terminal = sink.is_terminal();
        Self { sink, is_terminal }
    }

    /// A sink to treat as a terminal, for a stream already known to be one.
    #[must_use]
    pub fn terminal(sink: W) -> Self {
        Self {
            sink,
            is_terminal: true,
        }
    }

    /// A sink to treat as redirected: a pipe, a file, a CI log.
    #[must_use]
    pub fn redirected(sink: W) -> Self {
        Self {
            sink,
            is_terminal: false,
        }
    }

    /// Writes progress, and nothing at all when the sink is not a terminal.
    ///
    /// # Errors
    /// Propagates any write error.
    pub fn report(&mut self, done: u64) -> io::Result<()> {
        if self.is_terminal {
            write!(self.sink, "\r{done} processed")?;
        }
        Ok(())
    }

    /// Gives the sink back.
    #[must_use]
    pub fn into_inner(self) -> W {
        self.sink
    }
}

/// Everything else a CLI sends to the same stream goes through here, in order.
impl<W: Write> Write for Diagnostics<W> {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.sink.write(buf)
    }

    fn flush(&mut self) -> io::Result<()> {
        self.sink.flush()
    }
}

#[cfg(test)]
mod tests {
    use std::io;

    use super::Diagnostics;

    #[test]
    fn writes_nothing_when_redirected() -> io::Result<()> {
        let mut diagnostics = Diagnostics::redirected(Vec::new());
        diagnostics.report(3)?;
        assert_eq!(diagnostics.into_inner(), b"");
        Ok(())
    }

    #[test]
    fn writes_progress_to_a_terminal() -> io::Result<()> {
        let mut diagnostics = Diagnostics::terminal(Vec::new());
        diagnostics.report(3)?;
        assert_eq!(diagnostics.into_inner(), b"\r3 processed");
        Ok(())
    }
}
```

## Behaviour, environment, signals

### RS-CLI-22 [M] Read stdin when given no files, and treat `-` as stdin

Read from stdin when no file arguments are given, and treat `-` as stdin explicitly. This is the
Unix convention that makes a tool a filter.

**Why:** it is what makes the tool composable with everything else without special-casing. Users try
it before reading any documentation, and a tool that hangs or errors instead is remembered for it.

**Check:** `echo x | tool` and `tool -` should both work.

```rust
// verified
use std::path::{Path, PathBuf};

/// No file arguments means stdin, and `-` means stdin explicitly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Source {
    Stdin,
    File(PathBuf),
}

#[must_use]
pub fn sources(args: &[PathBuf]) -> Vec<Source> {
    if args.is_empty() {
        return vec![Source::Stdin];
    }
    args.iter()
        .map(|path| {
            if path == Path::new("-") {
                Source::Stdin
            } else {
                Source::File(path.clone())
            }
        })
        .collect()
}
```

### RS-CLI-23 [M!] Make destructive operations opt-in, and never prompt when not a terminal

An operation that deletes or overwrites paths the tool chose itself — from a glob, a traversal or a
default — is opt-in: a dry run by default, or at minimum a `--force`/`-i` prompt when interactive.
Paths the user passed one by one are the user's choice already. Never prompt when not a terminal —
fail instead.

*Relaxed form:* destructive by default, without the dry run; failing rather than prompting when not
a terminal still holds, since it is what makes the tool safe in a pipeline.

**Why:** the cost of an unwanted destructive run is unbounded and unrecoverable, while the cost of a
dry run is one extra invocation. Prompting without a terminal is worse than either: the tool blocks
forever in a pipeline, or consumes a line of piped data as the answer.

**Check:** run the destructive path with stdin closed. It must fail, not hang and not proceed.

```rust
// verified
/// Destructive work is opt-in, and a non-terminal run refuses rather than prompting.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Proceed,
    DryRun,
    RefuseNotATerminal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Force {
    Yes,
    No,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Terminal {
    Attached,
    Detached,
}

#[must_use]
pub fn decide(force: Force, terminal: Terminal) -> Decision {
    match (force, terminal) {
        (Force::Yes, _) => Decision::Proceed,
        (Force::No, Terminal::Attached) => Decision::DryRun,
        (Force::No, Terminal::Detached) => Decision::RefuseNotATerminal,
    }
}
```

### RS-CLI-24 [M] On `SIGINT`, restore the terminal and remove temporary files, then re-raise it

A tool that changes terminal modes (raw mode, the alternate screen, a hidden cursor) or creates
temporary files handles `SIGINT`/`Ctrl-C`: it restores the terminal, removes the files, then
restores the default disposition and raises `SIGINT` again —
`signal_hook::low_level::emulate_default_handler` does both. A tool with neither installs no
handler: Rust installs none for `SIGINT`, so the process already dies by the signal and the shell
reports `130`. A tool that leaves the terminal without an echo is remembered for it.

**Why:** Ctrl-C is the normal way users stop a long operation, so it is a supported code path. Dying
by the signal keeps the status `WIFSIGNALED`; `exit(130)` reports a normal exit that a calling
shell's loop carries on past, where a death by `SIGINT` would have stopped it.

**Check:** interrupt the tool mid-run. The terminal should echo afterwards, temp files should be
gone, and `$?` should be `130`. A handler that ends in `exit(130)` rather than re-raising is the
finding.

### RS-CLI-25 [S] Respect the platform's directory conventions

Use `directories` or `etcetera` — `$XDG_CONFIG_HOME`, `~/Library/Application Support`, `%APPDATA%` —
rather than hard-coding `~/.toolrc`. For `$HOME` alone, `std::env::home_dir` needs no crate.

**Why:** users expect config, cache, and data to land where their platform puts them, so backups and
sync tools handle them correctly. A hard-coded dotfile also breaks on Windows entirely.

**Check:** does a path start from a hard-coded `~/.` or a `$HOME` string? Each is a hard-coded path.

### RS-CLI-26 [M] Namespace and document every environment variable you read

Namespace environment variables with the tool's name (`RIPGREP_CONFIG_PATH`, `MYTOOL_LOG`), document
every one in `--help`, and never read an undocumented variable.

**Why:** an undocumented variable is an invisible input that makes behaviour unreproducible — the
user cannot know why the tool acts differently on their machine. Namespacing prevents collisions
with other tools' names.

**Check:** for each `env::var`, is the name prefixed, and does it appear in the help output?

```rust
// verified
/// Namespaced, and read in one place so the set is enumerable.
#[derive(Debug, Clone, Default)]
pub struct Environment {
    config_path: Option<String>,
    log_filter: Option<String>,
}

impl Environment {
    #[must_use]
    pub fn config_path(&self) -> Option<&str> {
        self.config_path.as_deref()
    }

    #[must_use]
    pub fn log_filter(&self) -> Option<&str> {
        self.log_filter.as_deref()
    }
}

#[must_use]
pub fn read(lookup: impl Fn(&str) -> Option<String>) -> Environment {
    Environment {
        config_path: lookup("MYTOOL_CONFIG_PATH"),
        log_filter: lookup("MYTOOL_LOG"),
    }
}
```

### RS-CLI-27 [M] Do not phone home, auto-update, or collect telemetry without opt-in

Do not phone home, auto-update, or collect telemetry without an explicit, documented opt-in. A CLI
that makes a network call the user did not ask for will be removed from their machine.

**Why:** command-line tools run in build systems, air-gapped environments, and on other people's
servers. An unexpected network call is a security finding in all three, regardless of intent.

**Check:** run the tool with the network blocked. Any behaviour change means there is a call you did
not declare.

### RS-CLI-28 [S] Ship a single binary with artifacts and checksums for three platforms

Ship the tool as a static-ish single binary where possible, with release artifacts for the three
major platforms and a checksum. Distribution friction is the main reason good tools go unused.

**Why:** "download one file" is the lowest-friction install there is, and it is what makes a tool
usable in a Dockerfile or a CI job. The checksum is what makes that download verifiable.

**Check:** does a release contain prebuilt artifacts for Linux, macOS, and Windows, plus checksums?

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `dbg_macro` | deny | `dbg!` left in shipped code |
