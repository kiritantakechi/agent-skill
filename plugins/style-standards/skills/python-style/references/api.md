# API and Modules: The Public Surface, Re-export, and Package Shape

Scope: deciding what a package exposes and how — signatures, defaults, the boundary between public
and private, `py.typed`, and the module layout that makes the boundary visible. How to spell a type
is the types chapter; what a value should be shaped like is the data chapter; naming is the naming
chapter.

Two sources are merged here: the **Python Typing Spec's distributing chapter**, which is normative
about re-export and `py.typed` and is enforced by every type checker, and the **empirical
conventions of the CPython standard library**, whose module surfaces are the reference for what a
Python API looks like. Ruff's `ANN`, `FBT`, `ARG` and `INP` families decide the mechanical half.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **The boundary**
  - PS-API-01 [M] Declare the public surface explicitly, and keep it small
  - PS-API-02 [M] Re-export through `__all__`, never by a bare import
  - PS-API-03 [M] Ship `py.typed` in every typed package
  - PS-API-04 [M] Underscore-prefix everything that is not public
  - PS-API-05 [M] Never import from another package's private name
- **Signatures**
  - PS-API-06 [M] Annotate every parameter and every return of a public function
  - PS-API-07 [M] Make a parameter keyword-only when the call site would not read
  - PS-API-08 [M] Take an abstract type; return a concrete one
  - PS-API-09 [S] Take a value, not a flag that selects between two behaviours
  - PS-API-10 [M] Give every parameter a name the caller would choose
- **Defaults and effects**
  - PS-API-11 [M] Make a function either return a value or perform an effect
  - PS-API-12 [M] Document what the function does not do
  - PS-API-13 [M] Say who owns what the function returns
- **Modules**
  - PS-API-14 [M] Give every package an `__init__.py` that is a table of contents
  - PS-API-15 [S] Split a module when it has two audiences, not when it is long
  - PS-API-16 [M] Keep the dependency graph acyclic and shallow
- **Evolution**
  - PS-API-17 [M] Deprecate with `warnings.deprecated`, and enable the check
  - PS-API-18 [M] Add a keyword-only parameter rather than changing an existing one
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

### PS-API-03 [M] Ship `py.typed` in every typed package

An empty file inside the package directory, plus `Typing :: Typed` in the classifiers. The marker
applies recursively, and `uv_build` includes it automatically because it lives inside the package.

**Why:** PEP 561 makes the marker the switch: without it, a downstream type checker ignores your
annotations entirely and treats every import from you as untyped. The annotations are there and do
nothing.

**Check:** install the wheel into a clean environment and type-check a file that imports from it. A
missing-stubs error is the finding.

### PS-API-04 [M] Underscore-prefix everything that is not public

`_helpers.py`, `_Cache`, `_parse`. The underscore is the signal, and `__all__` is the contract.

**Why:** the two work together — `__all__` says what is public, the underscore says what is not, and
having both means a reader can tell from a name alone without consulting the list. PEP 8 asks for
the underscore even when `__all__` is set, for exactly that reason.

**Check:** every module-level name absent from `__all__` and lacking an underscore is ambiguous.

### PS-API-05 [M] Never import from another package's private name

Not `from other._internal import thing`, however convenient.

**Why:** the underscore is the author telling you there is no compatibility promise, so the import
breaks on their patch release and the breakage is your problem. If you need it, ask them to make it
public; if you cannot wait, vendor it and own the copy.

**Check:** ruff `SLF001` for private member access. `rg -n 'from [a-z_.]+\._' src/` for the import
form.

## Signatures

### PS-API-06 [M] Annotate every parameter and every return of a public function

Including `-> None`.

**Why:** a missing annotation is a hole the checker cannot see through — it infers `Any`, which then
propagates to every caller and erases their types too. Without `-> None` the return is unannotated,
so assigning the result of a function that returns nothing type-checks.

**Check:** ruff's `ANN` family — `ANN001` for parameters, `ANN201` for returns. `ty` does not
require annotations at all, which is exactly why Ruff carries this half.

### PS-API-07 [M] Make a parameter keyword-only when the call site would not read

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

### PS-API-08 [M] Take an abstract type; return a concrete one

`Iterable[str]` or `Sequence[str]` in, `list[str]` out. Not `list[str]` in and `Iterable[str]` out.
A mutable parameter type is the exception, where mutating the argument is the point.

**Why:** a parameter constrains your callers and a return makes them a promise, so the two want
opposite generality. Accepting `Iterable` lets a caller pass a generator; returning it denies them
the indexing and the `.append` you actually gave, and they will cast it back.

**Check:** every public signature. A concrete container in a parameter, unless the function mutates
the argument, or an abstract one in a return, is the finding.

### PS-API-09 [S] Take a value, not a flag that selects between two behaviours

`sort(key=...)` rather than `sort(reverse_and_dedupe=True)`. A flag that genuinely toggles one line
— `strict=True` — is fine, which is why this is `[S]`.

**Why:** a flag parameter means the function has two bodies sharing a name, so every reader must
hold both and every test must cover both. Splitting them gives each an honest name; passing a value
instead makes the variation the caller's to express.

**Check:** every `bool` parameter whose body is `if flag: ... else: ...` at the top level.

### PS-API-10 [M] Give every parameter a name the caller would choose

`path`, not `p`. `timeout_seconds`, not `t`.

**Why:** with keyword arguments the parameter name is part of the public API — renaming it is a
breaking change — and it is the only documentation visible at the call site. A one-letter name in a
public signature is a name the caller must look up every time.

**Check:** every public signature. Ruff `ARG` catches the unused ones, which are a related defect.

## Defaults and effects

### PS-API-11 [M] Make a function either return a value or perform an effect

Not both, wherever the two can be had apart: a function that writes a file and returns the parsed
contents is two functions. Where they cannot — taking from a queue, popping a list, issuing a unique
id — the effect and its result are one step, PS-CONC-03 owns it, and the one call is named for the
effect: `get`, `pop`, `issue`.

**Why:** the mixed form cannot be tested without the effect, cannot be called for one half, and
gives the caller no way to know the effect happened from the value they received. Splitting makes
each half testable and lets the caller compose them.

**Check:** every function with a return value and an effect that PS-CONC-03 does not make one step.
`command-query separation` is the name for the split.

### PS-API-12 [M] Document what the function does not do

"Does not validate the path exists." "Does not retry." "Does not close the stream."

**Why:** a caller's bugs come from what they assumed you did. The docstring naturally describes what
happens; the omissions are invisible and are exactly where the assumption forms. One sentence
removes a class of misuse.

**Check:** every public function whose name suggests more than it does — anything with `load`,
`save`, `ensure`, `sync` in it.

### PS-API-13 [M] Say who owns what the function returns

Whether it is a view or a copy, and whether it must be closed: say it in the docstring. A container
the caller should not edit is returned immutable instead, which is PS-DATA-11's rule.

**Why:** returning a live view without saying so makes the caller's mutation your bug, and returning
something that must be closed without saying so guarantees a leak. Both are invisible from the
signature.

**Check:** every public return of a container or a resource. No ownership sentence is the finding.

## Modules

### PS-API-14 [M] Give every package an `__init__.py` that is a table of contents

Re-exports, `__all__` and a docstring, and nothing else. That it does no work is PS-NAME-10, which
holds for every module.

**Why:** the `__init__` is what every importer of the package runs, so anything in it is a cost paid
by everyone, including those who wanted one submodule. Kept declarative, it reads as the package's
index.

**Check:** every `__init__.py`. Anything other than imports, `__all__` and a docstring is the
finding.

### PS-API-15 [S] Split a module when it has two audiences, not when it is long

Length is a symptom; two unrelated groups of callers is the cause.

**Why:** splitting by size produces `utils2.py` and moves the problem. Splitting by audience
produces modules with coherent surfaces, each of which can be understood without the other. A
thousand-line module with one audience is fine; a two-hundred-line module serving two is not.

**Check:** for each module, name its callers. Two disjoint groups is the finding.

### PS-API-16 [M] Keep the dependency graph acyclic and shallow

No import cycles, and no chain of internal imports deeper than a few levels. The commonest cycle is
a submodule importing its own package: `acme/reader.py` doing `from acme import thing` runs
`acme/__init__.py`, which imports `acme.reader`.

**Why:** a cycle makes import order load-bearing: it works, or raises a partially initialised module
error, depending on which module was imported first. Depth is the subtler cost: understanding one
module requires understanding a chain, and every change ripples along it.

**Check:** `rg -n 'from <package> import|import <package>$' src/<package>/` for a submodule
importing its parent. Then draw the internal import graph: a cycle is the finding, and a chain
longer than three or four is a design question.

## Evolution

### PS-API-17 [M] Deprecate with `warnings.deprecated`, and enable the check

`@warnings.deprecated("Use X instead; removed in 2.0")` on the function, class or overload. It lives
in `warnings`, not `typing`. Not every checker reports it unless enabled explicitly; `ty` does so by
default.

**Why:** PEP 702's decorator is both a runtime `DeprecationWarning` and a static signal, so callers
find out at type-check time rather than at runtime — which is when they can still act.

**Check:** every deprecation. A docstring note without the decorator is invisible to tooling.

### PS-API-18 [M] Add a keyword-only parameter rather than changing an existing one

New behaviour arrives as `*, new_thing: X | None = None`, defaulting to the old behaviour.

**Why:** it is the only change that cannot break a caller: nobody passes it, so nobody notices, and
those who want it opt in. Changing a parameter's type, order, or default changes the meaning of code
you cannot see. PS-API-07's keyword-only discipline is what makes this possible later.

**Check:** every signature change in review. Anything but an added keyword-only parameter is a
breaking change and needs a version bump.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `FBT001` | error | a `bool` positional parameter — make it keyword-only, or an enum |
| ruff | `FBT002` | error | a `bool` default on a positional parameter |
| ruff | `FBT003` | error | a bare `True` or `False` passed positionally |
