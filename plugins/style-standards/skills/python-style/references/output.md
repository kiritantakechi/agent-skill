# Output: Encoding, Interpolation, Logging, and Program Output

Scope: what a string is encoded as, which interpolation form to reach for, template strings
included, how to log, which stream program output and diagnostics go to and how a record reaches a
shared one whole, what a library may not do, how a type renders, how a failure is reported and which
status the run exits with. Docstring content is the documentation chapter; whether a stream may be
shared by threads at all is the concurrency chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Encoding**
  - PS-OUT-01 [M] Pass `encoding=` explicitly to every text open
  - PS-OUT-02 [M] Never assume UTF-8 mode moved only `open`
  - PS-OUT-03 [M] Ask `locale.getencoding()` for the locale's encoding
  - PS-OUT-04 [M!] Choose the error handler deliberately
- **Interpolation**
  - PS-OUT-05 [M] Interpolate with an f-string
  - PS-OUT-06 [M] Never build a query, a path, or markup by interpolation
  - PS-OUT-07 [S] Reach for a template string when the interpolation must be inspected
  - PS-OUT-08 [M] Use `!r` when the value's identity matters to the reader
  - PS-OUT-09 [S] Use `=` in an f-string for a debug line, then delete it
- **Logging**
  - PS-OUT-10 [M] Log with `%`-style arguments, never with an f-string
  - PS-OUT-11 [M] Get a library's logger by `__name__`, and configure nothing in it
  - PS-OUT-12 [S] Log the identifier, not the object
- **Program output**
  - PS-OUT-13 [M] Send program output to stdout and diagnostics to stderr
  - PS-OUT-14 [M] Write each record to a shared text stream in one call, never with `print`
  - PS-OUT-15 [M] Never print, and never end the process, from a library
  - PS-OUT-16 [M] Flush standard output before `main` returns, so a failure to write raises
  - PS-OUT-17 [M] Colour only a terminal, and honour `NO_COLOR` and `CLICOLOR_FORCE`
  - PS-OUT-18 [M] Give a type a `__repr__` that says what it is
  - PS-OUT-19 [S] Give a type a `__str__` only when it has a human form
  - PS-OUT-20 [S] Offer a second rendering through `__format__`'s spec, never a second `__str__`
  - PS-OUT-21 [M] Never let output formatting depend on the locale
- **Failure and exit status**
  - PS-OUT-22 [M] Report an expected failure as one message on stderr, and let a bug keep its traceback
  - PS-OUT-23 [M] Exit non-zero on failure, with a code of its own for each class a caller must tell apart
- Decided by tools

---

## Encoding

### PS-OUT-01 [M] Pass `encoding=` explicitly to every text open

`open(path, encoding="utf-8")`, `Path.read_text(encoding="utf-8")`,
`subprocess.run(..., encoding="utf-8")`.

**Why:** the default is UTF-8 only while UTF-8 mode is on (PS-OUT-02), and `PYTHONUTF8=0` turns it
off, so only an explicit encoding means the same thing on every interpreter and in every locale.

**Check:** run with `-X warn_default_encoding`, which makes the interpreter itself emit an
`EncodingWarning` at every site relying on the default — a better check than a linter, because it
sees the calls a linter cannot resolve. The ruff rule that also finds them is **preview**, and the
shipped configuration runs stable rules only.

```python
# verified — GOOD
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as scratch:
    path = Path(scratch) / "note.txt"
    path.write_text("héllo", encoding="utf-8")
    assert path.read_text(encoding="utf-8") == "héllo"
```

### PS-OUT-02 [M] Never assume UTF-8 mode moved only `open`

UTF-8 mode is on by default in 3.15, and it changes six things at once. Beyond `open`, it sets
`sys.getfilesystemencoding()` to `utf-8`, so argv, environment variables and filenames decode
differently on a non-UTF-8 locale; makes `locale.getpreferredencoding()` return a constant, so any
branch on it takes a different path; and gives `sys.stdin`/`sys.stdout` the **`surrogateescape`**
handler.

**Why:** most people hear "the default encoding is UTF-8 now" and check only their `open` calls,
while the stdout handler turns a pipe's `UnicodeEncodeError` into a silent round-trip. PEP 686 warns
the change "may cause `UnicodeError`, mojibake, or even silent data corruption".

**Check:** `rg -n 'getpreferredencoding|getfilesystemencoding|fsencode|fsdecode' src/` — every hit
is a place the meaning changed. Then run the suite under `-X warn_default_encoding`, and treat every
`EncodingWarning` as a finding.

### PS-OUT-03 [M] Ask `locale.getencoding()` for the locale's encoding

To interoperate with a program that writes in the locale's encoding, ask `locale.getencoding()`,
which reports it whatever the UTF-8 mode. Never `locale.getpreferredencoding()`: it returns
`'utf-8'` under UTF-8 mode regardless of the locale, and its `do_setlocale` has no effect.

**Why:** `getpreferredencoding` is a constant dressed as a query, so code branching on it takes one
branch forever — including code written for a legacy encoding, which silently stops handling it.

**Check:** `rg -n 'getpreferredencoding' src/` — every hit is the finding, and the call it wants is
`locale.getencoding()`.

### PS-OUT-04 [M!] Choose the error handler deliberately

`errors="strict"` is the default and usually right. `surrogateescape` for filesystem paths.
`replace` only where a human reads the result and losing a character is acceptable.

*Relaxed form:* `replace` at a display boundary, without a comment.

**Why:** the handler decides what happens to data you cannot represent, a policy question and not a
technical one: `strict` fails loudly so the caller can retry or report, `surrogateescape`
round-trips undecodable bytes so a path can be reopened, and `replace` destroys them silently.

**Check:** every `errors=` argument needs a comment. Every text `open` on data from outside the
process without one is the finding.

## Interpolation

### PS-OUT-05 [M] Interpolate with an f-string

Not `%`, not `str.format`, not concatenation. The exceptions are logging (PS-OUT-10) and templates
(PS-OUT-07).

**Why:** the f-string puts the expression where the value appears, which is the only form a reader
can check without counting arguments. It is also the fastest, because the interpolation is compiled
rather than parsed at runtime.

**Check:** ruff `UP031` and `UP032` rewrite the two older forms automatically.

### PS-OUT-06 [M] Never build a query, a path, or markup by interpolation

SQL takes parameters. Paths take `pathlib`. HTML takes an escaping template. Shell takes an argument
list.

**Why:** every injection vulnerability in the catalogue is this rule being broken, and an f-string
makes it one keystroke easier than the safe form. The safe forms all exist and are not harder: a
parameterised query is the same length as the interpolated one.

**Check:** ruff `S608` for SQL, `S602`–`S607` for shell.
`rg -n 'f"[^"\n]*(SELECT|INSERT|UPDATE|DELETE) ' src/` for what the linter misses.

### PS-OUT-07 [S] Reach for a template string when the interpolation must be inspected

A PEP 750 template string, `t"SELECT * FROM {table}"`, produces a `Template` whose static parts and
interpolations are separate values, so a library can escape each one correctly. This is `[S]`
because it only helps when something downstream understands templates; writing one and then calling
`str()` on it has bought nothing.

**Why:** an f-string interpolates immediately and hands you a `str`, at which point nothing can tell
which characters came from the literal and which from the value. A template string defers it, so the
consumer sees the structure and can escape, parameterise, or reject.

**Check:** every library that takes a pre-formatted string and must escape part of it. That
signature should take a `Template`.

### PS-OUT-08 [M] Use `!r` when the value's identity matters to the reader

`f"port must be a number, got {raw!r}"` — so an empty string, a string with a trailing space, and
the word `None` are distinguishable from each other.

**Why:** without `!r`, `got ` and `got None` and `got  ` are three different failures that print
nearly identically, and the reader cannot tell which. In an exception message this is the difference
between a five-second diagnosis and a session with a debugger.

**Check:** every exception message and log line interpolating a value that came from outside. No
`!r` is the finding.

### PS-OUT-09 [S] Use `=` in an f-string for a debug line, then delete it

`f"{value=}"` prints `value=42`. It is a debugging tool, not an output format.

**Why:** it is the fastest way to write a temporary trace, and the fact that it embeds the
expression text is exactly what makes it wrong to ship — a rename changes the output. Its presence
in committed code is a debug line someone forgot.

**Check:** `rg -n '=\}' src/` — every hit is either a debug line or a deliberate choice needing a
comment.

## Logging

### PS-OUT-10 [M] Log with `%`-style arguments, never with an f-string

`logger.info("retrying %s after %s", url, exc)`. Not `logger.info(f"retrying {url}")`.

**Why:** the arguments form defers the interpolation until a handler actually emits the record, so a
log call below the configured level costs almost nothing. It also keeps the message template
constant, which lets an aggregator group a million occurrences of one event as one.

**Check:** ruff `G004` for the f-string, `G001`–`G003` for the other eager forms.

```python
# verified — GOOD
import logging

logger = logging.getLogger(__name__)


def fetch(url: str) -> None:
    # The template stays constant, so an aggregator can group these;
    # and the interpolation does not happen at all if INFO is off.
    logger.info("fetching %s", url)


fetch("https://example.invalid")
```

### PS-OUT-11 [M] Get a library's logger by `__name__`, and configure nothing in it

`logger = logging.getLogger(__name__)` at module scope. Not the root logger, and not a hand-written
string. Getting a logger is all a library does: no `basicConfig`, no handlers, no level setting, no
`dictConfig`. Adding a `NullHandler` is the one permitted exception, and only to silence the
no-handler warning.

**Why:** `__name__` makes the logging hierarchy mirror the package hierarchy, so an operator can
raise the level for one subpackage, and the root logger cannot be configured per component.
Configuration is the application's decision: a library that makes it wins whichever import is last.

**Check:** ruff `LOG015` for the root-logger calls. `rg -n 'getLogger\("' src/` for hand-written
names, and `rg -n 'basicConfig|dictConfig|setLevel|addHandler' src/` — every hit outside the
application entry point is the finding.

### PS-OUT-12 [S] Log the identifier, not the object

`logger.info("user %s", user.id)`, not `logger.info("user %s", user)`.

**Why:** logging an object calls its `__str__` at emit time, which may be expensive, may raise, and
may include data that should not be in a log. It also makes the line unstable: adding a field to the
type changes every log line that mentions it.

**Check:** every logging argument that is not a primitive. Each is a `__str__` call at emit time.

## Program output

### PS-OUT-13 [M] Send program output to stdout and diagnostics to stderr

The result goes to stdout, written with `sys.stdout.write`. Progress, warnings and errors go to
stderr, through `logging`. `print` is for neither: `T201` reads every one as a forgotten debug line.

**Why:** this is what makes a program composable: `prog | wc -l` must count results, not progress
messages. Mixing them means the pipeline consumer receives your diagnostics as data, and redirecting
stdout hides the errors you most needed to see.

**Check:** `rg -n 'sys\.stdout\.write' src/` — is each write part of the result? If not, it belongs
in `logging`.

### PS-OUT-14 [M] Write each record to a shared text stream in one call, never with `print`

`open()` in text mode returns a `TextIOWrapper`, and so do `sys.stdout` and `sys.stderr`, which
every thread that prints already shares. `print` is not one call to it: it writes each argument,
each separator and then `end` separately, so another thread's output lands inside the line. Send a
record as one `write` of the whole line, or through `logging`, whose handlers lock around each emit.

**Why:** the `io` docs call `TextIOWrapper` "not thread-safe" and promise nothing finer. On `3.15t`
eight threads printing 20,000 lines each garbled thousands of the 160,000, while the same lines sent
as single `write` calls arrived whole; under the GIL, `print` garbled a handful.

**Check:** `rg -n '\bprint\(|\.write\(' src/` inside any thread target. A `print` is the finding,
and so is a `write` that sends part of a record.

### PS-OUT-15 [M] Never print, and never end the process, from a library

A library returns a value or raises, and records what it saw through `logging` (PS-OUT-11). The
calls that write to the process's streams or end it, `print`, `sys.exit`, `raise SystemExit`, `quit`
and `os._exit`, belong to the entry point, which is the one place that knows what the process should
say and how it should end.

**Why:** a library cannot know whether its caller is a script, a server or a test run. A `sys.exit`
in one ends all three, and a `print` puts the library's words on a stream the application may be
using for data.

**Check:** `rg -n '\b(sys\.exit|quit|exit|os\._exit)\(|raise SystemExit' src/` — every hit outside
the entry point is the finding. `print` is the `T201` row.

```python
# verified — GOOD: the library raises; the caller decides
class PortError(Exception):
    """A port could not be read."""


def port(raw: str) -> int:
    """Return the port in `raw`, or raise `PortError`."""
    try:
        return int(raw)
    except ValueError as error:
        message = f"port must be a number, got {raw!r}"
        raise PortError(message) from error


assert port("8080") == 8080
```

```python
# verified — BAD: the library ends the caller's process
import sys


def port(raw: str) -> int:
    if not raw.isdigit():
        sys.exit(f"port must be a number, got {raw!r}")
    return int(raw)
```

### PS-OUT-16 [M] Flush standard output before `main` returns, so a failure to write raises

`sys.stdout` is buffered when it is not a terminal. Call `sys.stdout.flush()` as the last act of the
entry point, inside the code that can report a failure, rather than leaving the flush to the
interpreter's shutdown.

**Why:** a flush that fails at shutdown, on a full disk or a closed pipe, is only reported as
`Exception ignored on flushing sys.stdout`, and the process exits `120`. Flushed in `main`, it is an
`OSError` the entry point can report and turn into the status it chose.

**Check:** does the entry point flush `sys.stdout` after its last write? Run it with `> /dev/full`:
the status should be the one the program chose for a failure, not `120`.

```python
# verified — GOOD
import sys


def main(lines: list[str]) -> int:
    for line in lines:
        sys.stdout.write(f"{line}\n")
    # Failing here, the write is an OSError we can handle.
    sys.stdout.flush()
    return 0


assert main([]) == 0
```

### PS-OUT-17 [M] Colour only a terminal, and honour `NO_COLOR` and `CLICOLOR_FORCE`

Write escape sequences only when `--color=auto|always|never` says so, with `auto` the default. Under
`auto`, a non-empty `CLICOLOR_FORCE` turns colour on, a non-empty `NO_COLOR` or `TERM=dumb` turns it
off, and otherwise the stream's `isatty()` decides. One function makes that decision, and every
escape sequence is written behind it.

**Why:** these are the conventions users configure once and expect every tool to honour. Escape
codes written unconditionally end up as visible garbage in a file, a pipe and a CI log.

**Check:** `rg -n '\\x1b\[|\\033\[' src/` — every hit outside the one function that decides colour
is the finding, and so is a program that writes any and never reads `NO_COLOR`.

```python
# verified — GOOD
from typing import Literal, Protocol
lazy from collections.abc import Mapping


class Stream(Protocol):
    """What the decision asks of an output stream."""

    def isatty(self) -> bool:
        """Whether the stream is a terminal."""
        ...


def use_colour(
    choice: Literal["auto", "always", "never"],
    stream: Stream,
    environ: Mapping[str, str],
) -> bool:
    """Whether to write escape sequences to `stream`."""
    if choice != "auto":
        return choice == "always"
    if environ.get("CLICOLOR_FORCE", "") != "":
        return True
    if environ.get("NO_COLOR", "") != "" or environ.get("TERM") == "dumb":
        return False
    return stream.isatty()


class Pipe:
    """A stream that is not a terminal."""

    def isatty(self) -> bool:
        """Whether the stream is a terminal."""
        return False


assert not use_colour("auto", Pipe(), {})
assert not use_colour("auto", Pipe(), {"NO_COLOR": "1"})
assert use_colour("auto", Pipe(), {"CLICOLOR_FORCE": "1"})
assert not use_colour("never", Pipe(), {"CLICOLOR_FORCE": "1"})
```

### PS-OUT-18 [M] Give a type a `__repr__` that says what it is

Ideally one that could be evaluated back: `Point(x=1, y=2)`.

**Why:** the default `<acme.Point object at 0x7f...>` tells you nothing at the moment you most need
it — in a traceback, a debugger, or a failed assertion diff. The `dataclass` decorator writes a good
one for free, which is one more reason to reach for it.

**Check:** every class that is not a dataclass and has no `__repr__`. `RUF` does not catch this; it
is a review matter.

### PS-OUT-19 [S] Give a type a `__str__` only when it has a human form

If `str(x)` and `repr(x)` would say the same thing, define only `__repr__`.

**Why:** `str` falls back to `repr`, so defining both when they agree is duplication that will
drift. Define `__str__` when there is a genuinely different, human-facing rendering — a currency
amount, a duration — and let `repr` stay the precise one.

**Check:** every class defining both. If the two bodies are the same shape, delete `__str__`.

### PS-OUT-20 [S] Offer a second rendering through `__format__`'s spec, never a second `__str__`

`str(x)` takes no options, so a type with two reasonable renderings, short and verbose or absolute
and relative, implements `__format__` and lets the spec choose, `f"{span:long}"`, or gives the
second a method of its own. The bare form stays the common one.

**Why:** a type that picks one rendering for `__str__` leaves every caller who wants the other to
reimplement it, and a flag read from somewhere else makes the same value print two ways.

**Check:** are there two ways a reader would reasonably want this value printed? The second should
be a spec or a method, not a module-level helper that every caller has to know about.

```python
# verified — GOOD
from typing import override


class Span:
    """A length of time in whole seconds."""

    def __init__(self, seconds: int) -> None:
        """Hold `seconds`."""
        self.seconds = seconds

    @override
    def __format__(self, spec: str) -> str:
        """Render short by default and long when asked."""
        minutes, seconds = divmod(self.seconds, 60)
        if spec == "long":
            return f"{minutes} minutes {seconds} seconds"
        if spec in {"", "short"}:
            return f"{minutes}m{seconds:02d}s"
        message = f"unknown format spec {spec!r} for Span"
        raise ValueError(message)


assert f"{Span(125)}" == "2m05s"
assert f"{Span(125):long}" == "2 minutes 5 seconds"
```

### PS-OUT-21 [M] Never let output formatting depend on the locale

No `locale.format_string`, no `%c`/`%x` date codes, no thousands separators from the environment.

**Why:** output that changes with the environment cannot be tested, parsed, or diffed, and the
failure only appears on a machine configured differently from yours. Format explicitly:
`f"{value:,.2f}"` chooses the separator rather than inheriting one.

**Check:** `rg -n 'locale\.(setlocale|format_string|currency|str|localeconv)\(' src/` and
`rg -n 'strftime\(.*%[cxX]|:n\}' src/` — every hit is environment-dependent output.
`locale.getencoding()` is not, and PS-OUT-03 asks for it.

## Failure and exit status

### PS-OUT-22 [M] Report an expected failure as one message on stderr, and let a bug keep its traceback

The entry point catches the package's base exception (PS-ERR-01), writes one line to stderr that
names the problem and then each `__cause__` beneath it, and returns a non-zero status. An exception
that is not the package's own is a bug, and its traceback is what the programmer needs, so it
propagates.

**Why:** a traceback is a message to the programmer and a sentence is a message to the user. A tool
that prints a traceback because someone mistyped a port is unusable, and one that reduces a bug to a
sentence has thrown away the only record of where it happened.

**Check:** run the program with a bad argument and with a missing file. Is the output one line, and
does it name each cause? Does an unexpected exception still show its traceback?

```python
# verified — GOOD: an expected failure is one line on stderr
import sys


class AppError(Exception):
    """The base of every failure this package reports."""


def port(raw: str) -> int:
    """Return the port in `raw`, or raise `AppError`."""
    try:
        return int(raw)
    except ValueError as error:
        message = f"port must be a number, got {raw!r}"
        raise AppError(message) from error


def message(error: BaseException) -> str:
    """The error and each cause beneath it, on one line."""
    parts: list[str] = []
    current: BaseException | None = error
    while current is not None:
        parts.append(str(current))
        current = current.__cause__
    return ": ".join(parts)


def main(argv: list[str]) -> int:
    try:
        port(argv[0])
    except AppError as error:
        sys.stderr.write(f"error: {message(error)}\n")
        return 2
    return 0


assert main(["8080"]) == 0
```

### PS-OUT-23 [M] Exit non-zero on failure, with a code of its own for each class a caller must tell apart

`0` for success, `1` for a failure of the run, `2` for a usage error, which is the code `argparse`
already uses, and a distinct code for any other class a script must branch on. `main` returns the
status and the module's guard hands it to `sys.exit`. Document the codes in `--help`.

**Why:** scripts branch on the exit code and cannot branch on prose. An uncaught exception exits `1`
too, so a program that returns `1` for everything makes its own failures look like bugs.

**Check:** does `main` return a status, and is each code documented and covered by a test that runs
the program? A `sys.exit(1)` for a usage error is the finding.

```python
# verified — GOOD
import enum


class Status(enum.IntEnum):
    """What a run returns to the shell."""

    OK = 0
    FAILED = 1
    USAGE = 2


def status(error: Exception | None) -> Status:
    """The status a run that ended with `error` returns."""
    if error is None:
        return Status.OK
    if isinstance(error, ValueError):
        return Status.USAGE
    return Status.FAILED


assert status(None) == 0
assert status(ValueError("bad port")) == 2
assert status(OSError("disk full")) == 1
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `TRY400` | error | `logger.error` in a handler — `logger.exception` keeps the traceback — listed because a handler's log line is where a traceback is lost |
| ruff | `T201` | error | `print`, a debug line — results go to `sys.stdout.write`, diagnostics to `logging` — listed because PS-OUT-13 leaves `print` no channel |
