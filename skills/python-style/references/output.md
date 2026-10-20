# Strings and Output: Encoding, Interpolation, Logging, and Program Output

Scope: what a string is encoded as now that 3.15 changed the default, which interpolation form to
reach for including the new template strings, how to log, and the difference between program
output and diagnostics. Docstring content is the documentation chapter; the thread-safety of a
stream is the concurrency chapter.

Two sources are merged here: the **CPython 3.15 documentation** — PEP 686 for the encoding default,
PEP 750 for template strings, and the `logging` module's own guidance — and **Ruff's `G`, `LOG`,
`ISC`, `RUF` and `T20` families**, which decide the mechanical half.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Encoding**
  - PS-OUT-01 [M] Pass `encoding=` explicitly to every text open
  - PS-OUT-02 [M] Know what PEP 686 moved, which is more than `open`
  - PS-OUT-03 [M] Never rely on `locale.getpreferredencoding`
  - PS-OUT-04 [M!] Choose the error handler deliberately
  - PS-OUT-05 [M] Read and write bytes when the data is bytes
- **Interpolation**
  - PS-OUT-06 [M] Interpolate with an f-string
  - PS-OUT-07 [M] Never build a query, a path, or markup by interpolation
  - PS-OUT-08 [S] Reach for a template string when the interpolation must be inspected
  - PS-OUT-09 [M] Use `!r` when the value's identity matters to the reader
  - PS-OUT-10 [S] Use `=` in an f-string for a debug line, then delete it
- **Logging**
  - PS-OUT-11 [M] Log with `%`-style arguments, never with an f-string
  - PS-OUT-12 [M] Get the logger by `__name__`, at module scope
  - PS-OUT-13 [M] Never configure logging in a library
  - PS-OUT-14 [S] Log the identifier, not the object
- **Program output**
  - PS-OUT-15 [M] Send program output to stdout and diagnostics to stderr
  - PS-OUT-16 [M] Give a type a `__repr__` that says what it is
  - PS-OUT-17 [S] Give a type a `__str__` only when it has a human form
  - PS-OUT-18 [M] Never let output formatting depend on the locale
- Decided by tools

---

## Encoding

### PS-OUT-01 [M] Pass `encoding=` explicitly to every text open

`open(path, encoding="utf-8")`, `Path.read_text(encoding="utf-8")`,
`subprocess.run(..., encoding="utf-8")`.

**Why:** the default changed in 3.15, so code relying on the old default now behaves differently,
and code relying on the new one changes again wherever `PYTHONUTF8=0` disables UTF-8 mode. Only an
explicit encoding means the same thing on every interpreter and in every locale.

**Check:** run with `-X warn_default_encoding`, which makes the interpreter itself emit an
`EncodingWarning` at every site relying on the default — a better check than a linter, because it
sees the calls a linter cannot resolve. The ruff rule that also finds them is **preview**, and the
shipped configuration runs stable rules only.

```python
# verified — GOOD
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "note.txt"
    path.write_text("héllo", encoding="utf-8")
    assert path.read_text(encoding="utf-8") == "héllo"
```

### PS-OUT-02 [M] Know what PEP 686 moved, which is more than `open`

UTF-8 mode is on by default in 3.15, and it changes six things at once. Beyond `open`, it sets
`sys.getfilesystemencoding()` to `utf-8`, so argv, environment variables and filenames decode
differently on a non-UTF-8 locale; makes `locale.getpreferredencoding()` return a constant, so any
branch on it takes a different path; and gives `sys.stdin`/`sys.stdout` the **`surrogateescape`**
handler.

**Why:** most people hear "the default encoding is UTF-8 now" and check only their `open` calls,
while the stdout handler turns a pipe's `UnicodeEncodeError` into a silent round-trip. PEP 686 warns
the change "may cause `UnicodeError`, mojibake, or even silent data corruption".

**Check:** `rg -n 'getpreferredencoding|getfilesystemencoding|fsencode|fsdecode' src/` —
every hit is a place the meaning changed.

### PS-OUT-03 [M] Never rely on `locale.getpreferredencoding`

It returns `'utf-8'` under UTF-8 mode regardless of the locale, and `do_setlocale` has no effect.
If you need to know the platform's encoding for interoperating with another program, ask for that
specifically rather than for "the preferred" one.

**Why:** it is now a constant dressed as a query, so any code branching on it takes one branch
forever — including code written to handle a legacy encoding, which now silently stops handling it.

**Check:** `rg -n 'getpreferredencoding' src/` — every hit is the finding.

### PS-OUT-04 [M!] Choose the error handler deliberately

`errors="strict"` is the default and usually right. `surrogateescape` for filesystem paths.
`replace` only where a human reads the result and losing a character is acceptable.

*Relaxed form:* application code at a display boundary may use `replace` without a comment; library
code may not.

**Why:** the handler decides what happens to data you cannot represent, a policy question and not
a technical one: `strict` fails loudly so the caller can retry or report, `surrogateescape`
round-trips undecodable bytes so a path can be reopened, and `replace` destroys them silently.

**Check:** every `errors=` argument needs a comment. Every text `open` on data from outside the
process without one is the finding.

### PS-OUT-05 [M] Read and write bytes when the data is bytes

`Path.read_bytes()`, `open(path, "rb")`. Not a text mode with a made-up encoding.

**Why:** decoding binary data as text and re-encoding it does not round-trip, so a "text" read of a
file that is not text is a lossy transformation you did not intend. Any hashing, signing, or
byte-level comparison must be on the bytes.

**Check:** every `open` and `read_text` whose file may not be text. Every `hashlib` call whose input
came from a text read is the finding.

## Interpolation

### PS-OUT-06 [M] Interpolate with an f-string

Not `%`, not `str.format`, not concatenation. The exceptions are logging (PS-OUT-11) and templates
(PS-OUT-08).

**Why:** the f-string puts the expression where the value appears, which is the only form a reader
can check without counting arguments. It is also the fastest, because the interpolation is compiled
rather than parsed at runtime.

**Check:** ruff `UP031` and `UP032` rewrite the two older forms automatically.

### PS-OUT-07 [M] Never build a query, a path, or markup by interpolation

SQL takes parameters. Paths take `pathlib`. HTML takes an escaping template. Shell takes an argument
list.

**Why:** every injection vulnerability in the catalogue is this rule being broken, and an f-string
makes it one keystroke easier than the safe form. The safe forms all exist and are not harder: a
parameterised query is the same length as the interpolated one.

**Check:** ruff `S608` for SQL, `S602`–`S607` for shell.
`rg -n 'f"[^"\n]*(SELECT|INSERT|UPDATE|DELETE) ' src/` for what the linter misses.

### PS-OUT-08 [S] Reach for a template string when the interpolation must be inspected

New in 3.14 (PEP 750). `t"SELECT * FROM {table}"` produces a `Template` whose static parts and
interpolations are separate values, so a library can escape each one correctly. This is `[S]`
because it only helps when something downstream understands templates; writing one and then calling
`str()` on it has bought nothing.

**Why:** an f-string interpolates immediately and hands you a `str`, at which point nothing can
tell which characters came from the literal and which from the value. A template string defers it,
so the consumer sees the structure and can escape, parameterise, or reject.

**Check:** every library that takes a pre-formatted string and must escape part of it. That
signature should take a `Template`.

### PS-OUT-09 [M] Use `!r` when the value's identity matters to the reader

`f"port must be a number, got {raw!r}"` — so an empty string, a string with a trailing space, and
the word `None` are distinguishable from each other.

**Why:** without `!r`, `got ` and `got None` and `got  ` are three different failures that print
nearly identically, and the reader cannot tell which. In an exception message this is the difference
between a five-second diagnosis and a session with a debugger.

**Check:** every exception message and log line interpolating a value that came from outside. No
`!r` is the finding.

### PS-OUT-10 [S] Use `=` in an f-string for a debug line, then delete it

`f"{value=}"` prints `value=42`. It is a debugging tool, not an output format.

**Why:** it is the fastest way to write a temporary trace, and the fact that it embeds the
expression text is exactly what makes it wrong to ship — a rename changes the output. Its
presence in committed code is a debug line someone forgot.

**Check:** `rg -n '=\}' src/` — every hit is either a debug line or a deliberate choice needing a
comment.

## Logging

### PS-OUT-11 [M] Log with `%`-style arguments, never with an f-string

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
    # The template stays constant, so an aggregator can group these; and the
    # interpolation does not happen at all if INFO is not enabled.
    logger.info("fetching %s", url)


fetch("https://example.invalid")
```

### PS-OUT-12 [M] Get the logger by `__name__`, at module scope

`logger = logging.getLogger(__name__)`. Not the root logger, and not a hand-written string.

**Why:** `__name__` makes the logging hierarchy mirror the package hierarchy, so an operator can
raise the level for one subpackage without knowing your naming scheme. `logging.info(...)` at
module level uses the root logger, which cannot be configured per component.

**Check:** ruff `LOG015` for the root-logger calls. `rg -n 'getLogger\("' src/` for hand-written
names.

### PS-OUT-13 [M] Never configure logging in a library

No `basicConfig`, no handlers, no level setting, no `dictConfig`. Getting a logger is all a library
does. Adding a `NullHandler` is the one permitted exception, and only to silence the no-handler
warning.

**Why:** configuration is the application's decision, and a library that makes it wins whichever
import happens last — so behaviour depends on import order. The library's obligation is to emit
records; where they go is not its business.

**Check:** `rg -n 'basicConfig|dictConfig|setLevel|addHandler' src/` — every hit outside the
application entry point is the finding.

### PS-OUT-14 [S] Log the identifier, not the object

`logger.info("user %s", user.id)`, not `logger.info("user %s", user)`.

**Why:** logging an object calls its `__str__` at emit time, which may be expensive, may raise, and
may include data that should not be in a log. It also makes the line unstable: adding a field to the
type changes every log line that mentions it.

**Check:** every logging argument that is not a primitive. Each is a `__str__` call at emit time.

## Program output

### PS-OUT-15 [M] Send program output to stdout and diagnostics to stderr

The result goes to stdout. Progress, warnings and errors go to stderr.

**Why:** this is what makes a program composable: `prog | wc -l` must count results, not progress
messages. Mixing them means the pipeline consumer receives your diagnostics as data, and redirecting
stdout hides the errors you most needed to see.

**Check:** every `print` — is what it emits part of the result? If not, it belongs on stderr or in
`logging`.

### PS-OUT-16 [M] Give a type a `__repr__` that says what it is

Ideally one that could be evaluated back: `Point(x=1, y=2)`.

**Why:** the default `<acme.Point object at 0x7f...>` tells you nothing at the moment you most need
it — in a traceback, a debugger, or a failed assertion diff. The `dataclass` decorator writes a good
one for free, which is one more reason to reach for it.

**Check:** every class that is not a dataclass and has no `__repr__`. `RUF` does not catch this; it
is a review matter.

### PS-OUT-17 [S] Give a type a `__str__` only when it has a human form

If `str(x)` and `repr(x)` would say the same thing, define only `__repr__`.

**Why:** `str` falls back to `repr`, so defining both when they agree is duplication that will
drift. Define `__str__` when there is a genuinely different, human-facing rendering — a currency
amount, a duration — and let `repr` stay the precise one.

**Check:** every class defining both. If the two bodies are the same shape, delete `__str__`.

### PS-OUT-18 [M] Never let output formatting depend on the locale

No `locale.format_string`, no `%c`/`%x` date codes, no thousands separators from the environment.

**Why:** output that changes with the environment cannot be tested, parsed, or diffed, and the
failure only appears on a machine configured differently from yours. Format explicitly:
`f"{value:,.2f}"` chooses the separator rather than inheriting one.

**Check:** `rg -n 'locale\.|strftime\(.*%[cxX]' src/` — every hit is environment-dependent
output.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `TRY400` | error | `logger.error` in a handler — `logger.exception` keeps the traceback |
| ruff | `TRY401` | error | the exception interpolated into a message `logger.exception` already carries |
| ruff | `T201` | error | `print` for diagnostics — use `logging` |
| ruff | `T203` | error | `pprint` for diagnostics |
