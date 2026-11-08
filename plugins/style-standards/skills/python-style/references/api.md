# API: The Public Surface, Signatures, and Evolution

Scope: deciding what a package exposes and how — the boundary between public and private, re-export
and `py.typed`, signatures, defaults and effects, the pairs and siblings a surface keeps alike, and
changing the surface without breaking it. How to spell a type is the types chapter; what a value
should be shaped like is the data chapter; naming is the naming chapter; how a package is laid out
and imported is the modules chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **The boundary**
  - PS-API-01 [M] Declare the public surface explicitly, and keep it small
  - PS-API-02 [M] Re-export through `__all__`, never by a bare import
  - PS-API-03 [M] Give every package an `__init__.py` that is a table of contents
  - PS-API-04 [M] Ship `py.typed` in every typed package
  - PS-API-05 [M] Underscore-prefix everything that is not public
  - PS-API-06 [M] Never import from another package's private name
- **Signatures**
  - PS-API-07 [M] Annotate every parameter and every return of a public function
  - PS-API-08 [M] Make a parameter keyword-only when the call site would not read
  - PS-API-09 [M] Take an abstract type; return a concrete one
  - PS-API-10 [M] Take a value, not a flag that selects between two behaviours
  - PS-API-11 [M] Give every parameter a name the caller would choose
- **Defaults and effects**
  - PS-API-12 [M] Make a function either return a value or perform an effect
  - PS-API-13 [M] Document what the function does not do
  - PS-API-14 [M] Say who owns what the function returns
- **Evolution**
  - PS-API-15 [M] Deprecate with `warnings.deprecated`, and enable the check
  - PS-API-16 [M] Add a keyword-only parameter rather than changing an existing one
- **Symmetry**
  - PS-API-17 [M] Give every operation its inverse, or document why there is none
  - PS-API-18 [M] Keep argument order identical across sibling functions
  - PS-API-19 [M] Give sibling exceptions a uniform shape
- Decided by tools

---

## The boundary

### PS-API-01 [M] Declare the public surface explicitly, and keep it small

`__all__` in every module a caller imports from, listing exactly what they may use.

**Why:** without it the public surface is "everything without a leading underscore", which includes
every name you happened to import — so `from acme import json` works, and now you cannot stop
importing `json`. Declaring it makes the surface a decision rather than an accident.

**Check:** every module under the package root. No `__all__` is the finding. Ruff `F822` catches an
`__all__` naming something that does not exist.

### PS-API-02 [M] Re-export through `__all__`, never by a bare import

`from acme._core import Widget` in `__init__.py`, with `"Widget"` in the `__all__` that PS-API-01
already requires. The typing spec's other form, the redundant alias `Widget as Widget`, then only
repeats the `__all__`, so do not mix the two.

**Why:** the typing spec makes a name that a `py.typed` package merely imports private, so a checker
that follows it rejects downstream code importing a bare re-export — pyright does, and `ty` does for
a stub. The package's own tests import it fine, so only a downstream user finds out.

**Check:** ruff `F401` flags an import in `__init__.py` that neither `__all__` nor a redundant alias
re-exports.

### PS-API-03 [M] Give every package an `__init__.py` that is a table of contents

Re-exports, `__all__` and a docstring, and nothing else. That it does no work is PS-MOD-07, which
holds for every module.

**Why:** the `__init__` is what every importer of the package runs, so anything in it is a cost paid
by everyone, including those who wanted one submodule. Kept declarative, it reads as the package's
index.

**Check:** every `__init__.py`. Anything other than imports, `__all__` and a docstring is the
finding.

### PS-API-04 [M] Ship `py.typed` in every typed package

An empty file inside the package directory, and `Typing :: Typed` among the classifiers
(PS-BUILD-06). The marker applies recursively, and `uv_build` includes it because it lives inside
the package — which the built wheel confirms, not the source tree.

**Why:** PEP 561 makes the marker the switch: without it, a downstream type checker ignores your
annotations entirely and treats every import from you as untyped. The annotations are there and do
nothing.

**Check:** install the wheel into a clean environment and type-check a file that imports from it. A
missing-stubs error is the finding.

### PS-API-05 [M] Underscore-prefix everything that is not public

`_helpers.py`, `_Cache`, `_parse`. The underscore is the signal, and `__all__` is the contract.

**Why:** the two work together — `__all__` says what is public, the underscore says what is not, and
having both means a reader can tell from a name alone without consulting the list. PEP 8 asks for
the underscore even when `__all__` is set, for exactly that reason.

**Check:** every module-level name absent from `__all__` and lacking an underscore is ambiguous.

### PS-API-06 [M] Never import from another package's private name

Not `from other._internal import thing`, however convenient.

**Why:** the underscore is the author telling you there is no compatibility promise, so the import
breaks on their patch release and the breakage is your problem. If you need it, ask them to make it
public; if you cannot wait, vendor it and own the copy.

**Check:** ruff `SLF001` for private member access. `rg -n 'from [a-z_.]+\._' src/` for the import
form.

## Signatures

### PS-API-07 [M] Annotate every parameter and every return of a public function

Including `-> None`.

**Why:** a missing annotation is a hole the checker cannot see through — it infers `Any`, which then
propagates to every caller and erases their types too. Without `-> None` the return is unannotated,
so assigning the result of a function that returns nothing type-checks.

**Check:** ruff's `ANN` family — `ANN001` for parameters, `ANN201` for returns. `ty` does not
require annotations at all, which is exactly why Ruff carries this half.

### PS-API-08 [M] Make a parameter keyword-only when the call site would not read

`def connect(host: str, *, timeout_seconds: float = 5.0, retries: int = 3)`. A dataclass field is a
parameter of its constructor, and `_: KW_ONLY` is its `*`. A pair whose order is obvious, such as a
coordinate, reads better positionally and may stay so.

**Why:** `connect("db", 5.0, 3)` gives the reader no way to know what the numbers mean, and
transposing them type-checks. Keyword-only also lets you add, reorder, default or deprecate those
parameters later without breaking anyone, because nobody can be passing them positionally.

**Check:** every function and dataclass with more than two parameters, and every pair of adjacent
parameters or fields sharing a type.

```python
# verified — GOOD
from dataclasses import KW_ONLY, dataclass


def connect(host: str, *, timeout_seconds: float = 5.0, retries: int = 3) -> str:
    """Connect to `host`; everything after `*` must be named."""
    return f"{host}/{timeout_seconds}/{retries}"


@dataclass(frozen=True, slots=True)
class Rect:
    """Fields are constructor parameters; `KW_ONLY` is their `*`."""

    _: KW_ONLY
    width_px: int
    height_px: int


assert connect("db", retries=1) == "db/5.0/1"
assert Rect(width_px=3, height_px=4).width_px == 3
```

### PS-API-09 [M] Take an abstract type; return a concrete one

`Iterable[str]` or `Sequence[str]` in, `list[str]` out. Not `list[str]` in and `Iterable[str]` out.
A mutable parameter type is the exception, where mutating the argument is the point.

**Why:** a parameter constrains your callers and a return makes them a promise, so the two want
opposite generality. Accepting `Iterable` lets a caller pass a generator; returning it denies them
the indexing and the `.append` you actually gave, and they will cast it back.

**Check:** every public signature. A concrete container in a parameter, unless the function mutates
the argument, or an abstract one in a return, is the finding.

### PS-API-10 [M] Take a value, not a flag that selects between two behaviours

`sort(key=...)` rather than `sort(reverse_and_dedupe=True)`. A flag that selects between two
behaviours is two functions sharing a name; one that only toggles a line, such as `strict=True`,
selects nothing and stays, passed by keyword.

**Why:** a flag parameter means the function has two bodies sharing a name, so every reader must
hold both and every test must cover both. Splitting them gives each an honest name; passing a value
instead makes the variation the caller's to express.

**Check:** every `bool` parameter whose body is `if flag: ... else: ...` at the top level.

### PS-API-11 [M] Give every parameter a name the caller would choose

`path`, not `p`. `timeout_seconds`, not `t`.

**Why:** with keyword arguments the parameter name is part of the public API — renaming it is a
breaking change — and it is the only documentation visible at the call site. A one-letter name in a
public signature is a name the caller must look up every time.

**Check:** every public signature. Ruff `ARG` catches the unused ones, which are a related defect.

## Defaults and effects

### PS-API-12 [M] Make a function either return a value or perform an effect

Not both, wherever the two can be had apart: a function that writes a file and returns the parsed
contents is two functions. Where they cannot — taking from a queue, popping a list, issuing a unique
id — the effect and its result are one step, PS-CONC-03 owns it, and the one call is named for the
effect: `get`, `pop`, `issue`.

**Why:** the mixed form cannot be tested without the effect, cannot be called for one half, and
gives the caller no way to know the effect happened from the value they received. Splitting makes
each half testable and lets the caller compose them.

**Check:** every function with a return value and an effect that PS-CONC-03 does not make one step.
`command-query separation` is the name for the split.

### PS-API-13 [M] Document what the function does not do

"Does not validate the path exists." "Does not retry." "Does not close the stream."

**Why:** a caller's bugs come from what they assumed you did. The docstring naturally describes what
happens; the omissions are invisible and are exactly where the assumption forms. One sentence
removes a class of misuse.

**Check:** every public function whose name suggests more than it does — anything with `load`,
`save`, `ensure`, `sync` in it.

### PS-API-14 [M] Say who owns what the function returns

Whether it is a view or a copy, and whether it must be closed: say it in the docstring. A container
the caller should not edit is returned immutable instead, which is PS-DATA-10's rule.

**Why:** returning a live view without saying so makes the caller's mutation your bug, and returning
something that must be closed without saying so guarantees a leak. Both are invisible from the
signature.

**Check:** every public return of a container or a resource. No ownership sentence is the finding.

## Evolution

### PS-API-15 [M] Deprecate with `warnings.deprecated`, and enable the check

`@warnings.deprecated("Use X instead; removed in 2.0")` on the function, class or overload. It lives
in `warnings`, not `typing`. Not every checker reports it unless enabled explicitly; `ty` does so by
default.

**Why:** PEP 702's decorator is both a runtime `DeprecationWarning` and a static signal, so callers
find out at type-check time rather than at runtime — which is when they can still act.

**Check:** every deprecation. A docstring note without the decorator is invisible to tooling.

### PS-API-16 [M] Add a keyword-only parameter rather than changing an existing one

New behaviour arrives as `*, new_thing: X | None = None`, defaulting to the old behaviour.

**Why:** it is the only change that cannot break a caller: nobody passes it, so nobody notices, and
those who want it opt in. Changing a parameter's type, order, or default changes the meaning of code
you cannot see. PS-API-08's keyword-only discipline is what makes this possible later.

**Check:** every signature change in review. Anything but an added keyword-only parameter is a
breaking change and needs a version bump.

## Symmetry

### PS-API-17 [M] Give every operation its inverse, or document why there is none

If `to_json` exists, `from_json` exists. If `__str__` is meant to round-trip, something parses it.
The same holds for every verb a type pairs, `encode` with `decode` and `push` with `pop`; how the
two are spelled is PS-NAME-12. A half that is missing on purpose is stated in the docstring.

**Why:** a one-way conversion produces a value you can never recover, and the gap stays invisible
until someone needs the inverse, by which point the format has already shipped. Writing the pair
together also tests the format: a round-trip assertion is the cheapest schema check there is.

**Check:** every `to_*`, `__str__` and paired verb on a data type. A missing inverse is either
deliberate — say so in the docstring — or the finding.

```python
# verified — GOOD
from dataclasses import dataclass
from typing import Self
lazy from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class Point:
    """A point on the integer grid."""

    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        """Return the point as a mapping of its fields."""
        # Not `asdict`: it returns `dict[str, Any]`, and laundering
        # `Any` into an annotated return is what PS-TYPE-12 stops.
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, raw: Mapping[str, int]) -> Self:
        """Return the point `to_dict` gave `raw`."""
        return cls(x=raw["x"], y=raw["y"])


original = Point(1, 2)
assert Point.from_dict(original.to_dict()) == original
assert Point.from_dict(frozendict(x=1, y=2)) == original  # any mapping, not only a dict
```

### PS-API-18 [M] Keep argument order identical across sibling functions

If `copy_len(source, target)` takes the source first, then `move_len` and `link_len` in the same
module do too. Fix the order once per package and do not vary it. A keyword-only parameter
(PS-API-08) cannot be transposed, so the rule binds the positional ones.

**Why:** siblings are called from the same code, and the reader generalises from the first one they
learn. When the types match, an inconsistent order still type-checks, so the failure is a silently
swapped argument at a call site that looks right.

**Check:** list every function in a module with two or more positional parameters of related type
and compare their orders. Any disagreement is the finding, and the outlier is what changes.

```python
# verified — GOOD
def copy_len(source: bytes, target: bytearray) -> int:
    """Append `source` to `target`; return how many bytes."""
    target.extend(source)
    return len(source)


def move_len(source: bytearray, target: bytearray) -> int:
    """Move `source` onto the end of `target`, in `copy_len`'s order."""
    moved = len(source)
    target.extend(source)
    source.clear()
    return moved


sink = bytearray()
assert copy_len(b"ab", sink) == 2
assert move_len(bytearray(b"c"), sink) == 1
assert sink == b"abc"
```

### PS-API-19 [M] Give sibling exceptions a uniform shape

The subclasses of one base carry comparable context: if `ReadError` records the path, `WriteError`
does too. Put the shared field on the base (PS-ERR-01) and let a subclass add to it, never omit it.

**Why:** the caller writes one `except StoreError` and reports from the instance. When some
subclasses carry the path and some do not, the reporting code grows a special case for each
deficient one, and the one that is missing a field is found when it is raised in production.

**Check:** tabulate the subclasses of each package base against the attributes they set. An
attribute set by most and absent from one is either a missing field or a subclass that belongs under
another base.

```python
# verified — GOOD
class StoreError(Exception):
    """Base of the store's failures; every subclass carries `path`."""

    def __init__(self, path: str) -> None:
        """Record the `path` the failure concerns."""
        super().__init__(path)
        self.path = path


class ReadError(StoreError):
    """The file could not be read."""


class WriteError(StoreError):
    """The file could not be written."""


def describe(error: StoreError) -> str:
    """Render any failure of the store the same way."""
    return f"{type(error).__name__}: {error.path}"


assert describe(ReadError("a.db")) == "ReadError: a.db"
assert describe(WriteError("b.db")) == "WriteError: b.db"
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `FBT001` | error | a `bool` positional parameter — make it keyword-only, or an enum — listed because it decides how PS-API-10's permitted flag is passed: by keyword |
| ty | `invalid-legacy-positional-parameter` | warn | a `__`-prefixed parameter the legacy positional-only convention cannot make positional-only |
