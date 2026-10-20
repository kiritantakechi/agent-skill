# Errors and Control Flow: Exceptions, Guards, and the Shape of a Function

Scope: designing an exception hierarchy, raising and catching, what `try` should enclose, exception
groups, and the control-flow shapes that keep a function readable — guards, early return, `match`,
the walrus. What to log when you catch is the output chapter; what a public function
should raise is the API chapter; concurrency-specific control flow is the async and free-threading
chapters.

Two sources are merged here: the **CPython 3.15 documentation**, including PEP 765's new restriction
on `finally` and the exception-group machinery, and **Ruff's `B`, `TRY`, `RET`, `EM` and `BLE`
families**, which decide most of this mechanically. Where a rule can cite a code it does, and the
shipped `assets/ruff.toml` enables it.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Designing the hierarchy**
  - PS-ERR-01 [M] Give the package one base exception, and inherit everything from it
  - PS-ERR-02 [M] Inherit from the closest builtin that is already right
  - PS-ERR-03 [M] Put the data on the exception, not only in the message
  - PS-ERR-04 [S] Name an exception for what happened, not for who noticed
- **Raising**
  - PS-ERR-05 [M] Never raise a bare `Exception`
  - PS-ERR-06 [M] Chain with `raise ... from`, and use `from None` deliberately
  - PS-ERR-07 [M] Never use `assert` to validate input
- **Catching**
  - PS-ERR-08 [M] Never catch what you cannot handle
  - PS-ERR-09 [M] Never swallow an exception silently
  - PS-ERR-10 [M] Enclose in `try` only the line that can raise
  - PS-ERR-11 [M] Use `except*` for a group, and never mix it with `except`
  - PS-ERR-12 [S] Prefer asking forgiveness where the failure is rare
- **`finally` and cleanup**
  - PS-ERR-13 [M] Never `return`, `break` or `continue` inside `finally`
  - PS-ERR-14 [M] Release with a context manager rather than with `finally`
  - PS-ERR-15 [M] Make a cleanup path idempotent
- **The shape of a function**
  - PS-ERR-16 [M] Reject at the top with a guard, then proceed unindented
  - PS-ERR-17 [M] Write the condition as the invariant that holds
  - PS-ERR-18 [S] Use `match` for structure, not as a switch
  - PS-ERR-19 [S] Bind with the walrus only where it removes a line without hiding one
  - PS-ERR-20 [M] Return one type from one function
- Decided by tools

---

## Designing the hierarchy

### PS-ERR-01 [M] Give the package one base exception, and inherit everything from it

`class AcmeError(Exception)`, and every exception the package raises inherits from it.

**Why:** it gives a caller exactly one name to catch for "anything this library raises", and that
catch survives you adding exception types later. Without it, the caller must enumerate your types
and go stale, or catch `Exception` and swallow their own bugs along with yours.

**Check:** every `class .*Error(Exception)` in the package. More than one root is the finding.

```python
# verified — GOOD
class AcmeError(Exception):
    """Base for everything this package raises."""


class ConfigError(AcmeError):
    pass


class TimeoutError_(AcmeError, TimeoutError):
    """Also a builtin `TimeoutError`, so existing handlers keep working."""


assert issubclass(ConfigError, AcmeError)
assert issubclass(TimeoutError_, TimeoutError)
```

### PS-ERR-02 [M] Inherit from the closest builtin that is already right

A bad argument is a `ValueError`. A wrong type is a `TypeError`. A missing key is a `KeyError`. A
timeout is a `TimeoutError`. Inherit from both your base and the builtin, as in PS-ERR-01's example.

**Why:** callers already have handlers for the builtins, and code they did not write already raises
them. With both bases, a caller catching either name gets it, so you add a name without breaking
anyone; a parallel hierarchy forces every caller to learn yours.

**Check:** every custom exception. If a builtin describes the condition, it should be in the bases.

### PS-ERR-03 [M] Put the data on the exception, not only in the message

`raise ConfigError(path=path, key=key)` with attributes, not `raise ConfigError(f"{path}: {key}")`.

**Why:** a handler that must parse the message to react to it is coupled to your prose, so improving
the wording breaks it. Attributes give the handler a stable interface and let the message be written
for a human. The message can still interpolate them.

**Check:** every custom exception with no `__init__` and no attributes. If a handler would need
anything from it beyond "it happened", it needs a field.

### PS-ERR-04 [S] Name an exception for what happened, not for who noticed

`ConfigMissingError`, not `ConfigLoaderError`. `PaymentDeclinedError`, not `StripeError`.

**Why:** the caller is handling a condition, not a component. Naming for the component leaks the
implementation into the exception hierarchy, so replacing the component becomes a breaking change to
the error contract even when the conditions are identical.

**Check:** every exception whose name contains a class name, a module name, or a vendor.

## Raising

### PS-ERR-05 [M] Never raise a bare `Exception`

Nor `BaseException`, nor `RuntimeError` used as a general-purpose complaint.

**Why:** it forces the caller to catch `Exception`, which catches everything including their own
bugs, or to match on the message. Both are worse than the type you did not bother to define. The
cost of defining one is a single line.

**Check:** ruff `TRY002` for the raise and `TRY004` for using the wrong builtin for a type error.

### PS-ERR-06 [M] Chain with `raise ... from`, and use `from None` deliberately

`raise ConfigError(...) from exc` when translating. `from None` only when the original would
mislead: when it is an implementation detail the caller cannot act on, never when it carries the
actual reason.

**Why:** without `from`, Python still shows the original under "During handling of the above
exception, another exception occurred", which reads as a bug in your handler rather than as a
deliberate translation. `from exc` says "this caused that"; `from None` suppresses the original.

**Check:** ruff `B904` — a `raise` inside an `except` without `from` is the finding.

```python
# verified — GOOD
class ConfigError(Exception):
    pass


def port_from(raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        msg = f"port must be a number, got {raw!r}"
        # `from exc` keeps the cause; the caller sees both and knows which is which.
        raise ConfigError(msg) from exc


try:
    port_from("http")
except ConfigError as exc:
    assert isinstance(exc.__cause__, ValueError)
```

### PS-ERR-07 [M] Never use `assert` to validate input

`assert` states something the code believes; `raise` reports something the caller did.

**Why:** `python -O` removes every `assert` statement, so validation written as an assertion
silently disappears in exactly the deployment where you most wanted it. And a failed assertion
blames *this* code for the caller's mistake, which misdirects whoever reads the traceback.

**Check:** ruff `S101` outside tests. Inside a test the assertion is the point, which is why the
shipped configuration ignores `S101` under `tests/`.

## Catching

### PS-ERR-08 [M] Never catch what you cannot handle

Catching to log and re-raise is handling. Catching to continue as if nothing happened is not.

**Why:** a handler that cannot repair the situation and does not re-raise converts a loud failure
into a quiet wrong answer, at the layer least able to judge whether that was acceptable. The caller
who has the context decides; your job is to let the failure reach them.

**Check:** every `except`. Name what the handler does about it. "Logs it" without a re-raise is the
finding unless this is the top-level boundary that owns the process.

### PS-ERR-09 [M] Never swallow an exception silently

`except X: pass` needs a comment saying why the failure is genuinely uninteresting.

**Why:** the empty handler is indistinguishable from an unfinished one, so every future reader must
re-derive whether it was deliberate. Where it *is* deliberate — a best-effort cleanup, a cache write
that may fail — one line of comment records the reasoning that cannot be recovered from the code.

**Check:** ruff `S110` (`try`/`except`/`pass`) and `SIM105`, which suggests `contextlib.suppress`
where that is what you meant. `suppress` is also more honest: it names the intent in the syntax.

```python
# verified — GOOD
import contextlib
from pathlib import Path

cache = Path("cache.bin")

# `suppress` says in the syntax what `except ... : pass` says only in a comment:
# the cache is best-effort and its absence is not an error.
with contextlib.suppress(FileNotFoundError):
    cache.unlink()

assert not cache.exists()
```

### PS-ERR-10 [M] Enclose in `try` only the line that can raise

Not the whole function body. Not the setup and the work together.

**Why:** a wide `try` catches the exception you were expecting from a line you were not thinking
about, so the handler runs on a situation it was not written for. The narrow form also documents
which call is the risky one, which the wide form hides.

**Check:** every `try` with more than about three statements. Each additional line is another source
the handler now silently claims to cover.

### PS-ERR-11 [M] Use `except*` for a group, and never mix it with `except`

A `TaskGroup` or a `Barrier` raises `ExceptionGroup`; catch it with `except*`.

**Why:** a plain `except ValueError` does not match an `ExceptionGroup` containing a `ValueError`,
so that handler is silently never entered. `except*` matches into the group, handles the matching
part, and re-raises the rest. Python forbids mixing the forms: the semantics would be ambiguous.

**Check:** every `try` around a `TaskGroup`, a `Barrier`, or anything that may raise a group. A
plain `except` there is the finding.

```python
# verified — GOOD
def failing() -> None:
    raise ExceptionGroup("two problems", [ValueError("a"), KeyError("b")])


caught: list[str] = []
try:
    failing()
except* ValueError as group:
    caught.append(f"value:{len(group.exceptions)}")
except* KeyError as group:
    caught.append(f"key:{len(group.exceptions)}")

assert caught == ["value:1", "key:1"]
```

### PS-ERR-12 [S] Prefer asking forgiveness where the failure is rare

`try: return d[k] / except KeyError:` beats `if k in d: return d[k]` when the key is usually there.
Where the failure is *common*, the exception machinery costs more than the check, so check first.

**Why:** the check-then-act form is two lookups instead of one, and under free threading it is
also PS-CONC-03's race: the key can vanish between the test and the use. The `try` form is atomic
with respect to that.

**Check:** every `if x in y:` immediately followed by an access to `y[x]`. `SIM401` catches the
subset that `dict.get` replaces outright.

## `finally` and cleanup

### PS-ERR-13 [M] Never `return`, `break` or `continue` inside `finally`

New in 3.14: PEP 765 makes it a `SyntaxWarning` at compile time. The PEP leaves open whether it
ever becomes an error.

**Why:** a `return` in `finally` **discards the in-flight exception**, silently. The function
returns normally and the failure that was propagating simply disappears, with no traceback and no
log. PEP 765 exists because the pattern is essentially always a mistake.

**Check:** ruff `B012`, which the shipped configuration enables, flags a `return`, `break` or
`continue` in a `finally`. The interpreter warns too, so a build that turns warnings into errors
catches it as well.

### PS-ERR-14 [M] Release with a context manager rather than with `finally`

`with lock:`, `with open(...) as f:`, `with contextlib.closing(x):`. Not `try/finally`. Note
PS-CONC-25: on 3.15 a `contextmanager`-derived *decorator* on a generator holds until the generator
is exhausted, so prefer the `with` form where the hold time matters.

**Why:** the context manager puts the acquisition and the release in one place where they cannot
drift apart, and it makes the pair impossible to forget at a new call site. Hand-written
`try/finally` repeats the release at every use and is where PS-ERR-13's defect appears.

**Check:** `rg -n 'finally:' src/` — each hit that only releases a resource should be a `with`.

### PS-ERR-15 [M] Make a cleanup path idempotent

Closing twice, unlinking a missing file, releasing an unheld lock: none may raise.

**Why:** cleanup runs on the exception path, which is the path least tested and most likely to run
twice — once from your handler and once from an enclosing one. A cleanup that raises there replaces
the original exception with its own, and the original is what you needed to see.

**Check:** every `close`, `unlink`, `release` and `__exit__`. Call it twice in a test.

## The shape of a function

### PS-ERR-16 [M] Reject at the top with a guard, then proceed unindented

`if not valid: raise ...` first, then the body at one level of indentation.

**Why:** the alternative nests the real work inside the success branch, so the reader tracks an
open condition through the whole function. Guards leave the body describing only the case that
matters, and adding a rejection is one line at the top rather than another level of nesting.

**Check:** ruff `RET505`–`RET508` for the `else`-after-`return` shapes, and `PLR0911` for a function
that has grown too many exits to follow.

```python
# verified — GOOD
def parse_port(raw: str) -> int:
    if not raw:
        msg = "port is required"
        raise ValueError(msg)
    if not raw.isdigit():
        msg = f"port must be a number, got {raw!r}"
        raise ValueError(msg)
    # Every rejection is behind us; the rest reads as the success case.
    return int(raw)


assert parse_port("8080") == 8080
```

### PS-ERR-17 [M] Write the condition as the invariant that holds

`if index < length:` for the branch that proceeds. An early-return guard is the exception, because
stating the rejection is its whole point.

**Why:** a positively-stated condition can be read once; a negated one must be read and then
inverted, and the inversion is where off-by-one errors hide. `if not (a or b)` costs the reader two
transformations. The guard form is exempt because there the rejection *is* the subject.

**Check:** every `if not` whose body is more than a `raise` or a `return`. `SIM103`, `SIM108` and
`SIM110` catch the mechanical subset.

### PS-ERR-18 [S] Use `match` for structure, not as a switch

`match` earns its place when it destructures — a shape, a sequence, a class with fields. Matching a
single value against constants is an `if`/`elif` chain wearing a costume. The enum case is the
exception worth naming: `match` over an enum with `assert_never` is the idiom PS-TYPE-16 requires.

**Why:** `match` reads well when the patterns show the shape of the data and badly when they are a
list of equalities, because the reader is primed by the syntax to look for structure that is not
there.

**Check:** every `match` whose every case is a bare literal and which has no capture pattern.

### PS-ERR-19 [S] Bind with the walrus only where it removes a line without hiding one

`if (found := lookup(k)) is not None:` yes. A walrus inside a comprehension condition that is also
used in the output, usually not.

**Why:** the walrus is at its best where the binding and the test are genuinely one thought, and
at its worst where it buries a side effect inside an expression the reader scans rather than
parses. The test is whether removing it would need one extra line or three.

**Check:** every `:=`. If the bound name is used more than twice, or the expression spans more than
one line, the plain assignment reads better.

### PS-ERR-20 [M] Return one type from one function

Not `str | None` where `None` means failure, and not a value on success with a `bool` on failure.
`X | None` is legitimate where `None` is a *value* the domain has, such as an optional field, and
illegitimate where it means "it went wrong".

**Why:** every extra shape in the return type propagates to every caller, each of whom must
handle it or ignore it — and ignoring it is the default. Failures belong in exceptions, which
callers cannot ignore by accident.

**Check:** every function returning `X | None`. Ask whether `None` is a value or a failure; if it
is a failure, it is an exception.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `EM101` | error | a string literal passed straight to an exception — assign it to `msg` first |
| ruff | `EM102` | error | an f-string passed straight to an exception |
| ruff | `E722` | error | a bare `except:`, which also catches `KeyboardInterrupt` and `SystemExit` |
