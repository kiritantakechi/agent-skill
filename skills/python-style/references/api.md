# API and Modules: The Public Surface, Re-export, and Package Shape

Scope: deciding what a package exposes and how — signatures, defaults, the boundary between public
and private, `py.typed`, and the module layout that makes the boundary visible. How to spell a type
is the types chapter; what a value should be shaped like is the data chapter; naming is
the naming chapter.

Two sources are merged here: the **Python Typing Spec's distributing chapter**, which is normative
about re-export and `py.typed` and is enforced by every type checker, and the **empirical
conventions of the CPython standard library**, whose module surfaces are the reference for what a
Python API looks like. Ruff's `ANN`, `FBT`, `ARG` and `INP` families decide the mechanical half.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **The boundary**
  - PS-API-01 [M] Declare the public surface explicitly, and keep it small
  - PS-API-02 [M] Re-export by redundant alias or `__all__`, consistently
  - PS-API-03 [M] Ship `py.typed` in every typed package
  - PS-API-04 [M] Underscore-prefix everything that is not public
  - PS-API-05 [M] Never import from another package's private name
- **Signatures**
  - PS-API-06 [M] Annotate every parameter and every return of a public function
  - PS-API-07 [M] Make a parameter keyword-only when the call site would not read
  - PS-API-09 [M] Take the narrowest type that works; return the most specific
  - PS-API-10 [S] Take a value, not a flag that selects between two behaviours
  - PS-API-11 [M] Give every parameter a name the caller would choose
- **Defaults and effects**
  - PS-API-13 [M] Make a function either return a value or perform an effect
  - PS-API-14 [M] Document what the function does not do
  - PS-API-15 [M] Say who owns what the function returns
- **Modules**
  - PS-API-16 [M] Give every package an `__init__.py` that is a table of contents
  - PS-API-17 [M] Never let a submodule import its parent package
  - PS-API-18 [S] Split a module when it has two audiences, not when it is long
  - PS-API-19 [M] Keep the dependency graph acyclic and shallow
- **Evolution**
  - PS-API-20 [M] Deprecate with `warnings.deprecated`, and enable the check
  - PS-API-21 [M] Add a keyword-only parameter rather than changing an existing one
  - PS-API-22 [M] Give every public change a note in the changelog
- Decided by tools

---

## The boundary

### PS-API-01 [M] Declare the public surface explicitly, and keep it small

`__all__` in every module a caller imports from, listing exactly what they may use.

**Why:** without it the public surface is "everything without a leading underscore", which includes
every name you happened to import — so `from acme import json` works, and now you cannot stop
importing `json`. Declaring it makes the surface a decision rather than an accident, and it makes
adding to it deliberate.

**Check:** every module under the package root. No `__all__` is the finding. Ruff `F822` catches an
`__all__` naming something that does not exist.

### PS-API-02 [M] Re-export by redundant alias or `__all__`, consistently

`from ._core import Widget as Widget`, or `__all__ = ["Widget"]`. Pick one per project.

**Why:** this is normative, not stylistic: the typing spec says imported symbols are **private by
default**, so a bare `from ._core import Widget` in `__init__.py` is not part of your public
interface as far as any type checker is concerned — and downstream code importing it gets an error
while your own tests pass. The two forms above are the documented ways to say otherwise. Mixing them
means a reader must check both places to learn whether a name is public.

**Check:** type-check a file that imports each documented name from the package root. A
"not explicitly exported" error is the finding.

### PS-API-03 [M] Ship `py.typed` in every typed package

An empty file inside the package directory, plus `Typing :: Typed` in the classifiers.

**Why:** PEP 561 makes the marker the switch: without it, a downstream type checker ignores your
annotations entirely and treats every import from you as untyped. The annotations are there and do
nothing. The marker applies recursively, and `uv_build` includes it
automatically because it lives inside the package.

**Check:** install the wheel into a clean environment and type-check a file that imports from it. A
missing-stubs error is the finding.

### PS-API-04 [M] Underscore-prefix everything that is not public

`_helpers.py`, `_Cache`, `_parse`. The underscore is the signal, and `__all__` is the contract.

**Why:** the two work together — `__all__` says what is public, the underscore says what is not,
and having both means a reader can tell from a name alone without consulting the list. PEP 8 asks
for the underscore even when `__all__` is set, for exactly that reason.

**Check:** every module-level name absent from `__all__` and lacking an underscore is ambiguous.

### PS-API-05 [M] Never import from another package's private name

Not `from other._internal import thing`, however convenient.

**Why:** the underscore is the author telling you there is no compatibility promise, so the import
breaks on their patch release and the breakage is your problem. If you need it, ask them to make it
public; if you cannot wait, vendor it and own the copy.

**Check:** ruff `SLF001` for private member access. `rg -n 'from [a-z_.]+\._' src/` for the
import form.

## Signatures

### PS-API-06 [M] Annotate every parameter and every return of a public function

Including `-> None`.

**Why:** the annotation is the contract, and a missing one is a hole the checker cannot see
through — it infers `Any`, which then propagates to every caller and erases their types too. `->
None` matters as much as the others: without it the function's return is unannotated, so
assigning its result type-checks.

**Check:** ruff's `ANN` family — `ANN001` for parameters, `ANN201` for returns. `ty` does not
require annotations at all, which is exactly why Ruff carries this half.

### PS-API-07 [M] Make a parameter keyword-only when the call site would not read

`def connect(host: str, *, timeout_seconds: float = 5.0, retries: int = 3)`.

**Why:** `connect("db", 5.0, 3)` gives the reader no way to know what the numbers mean, and
transposing them type-checks. Keyword-only makes the call site self-documenting and — the reason
that matters more — lets you add, reorder, or deprecate those parameters later without breaking
anyone, because nobody can be passing them positionally.

**Check:** every function with more than two parameters, and every pair of adjacent parameters
sharing a type.

```python
# verified — GOOD
def connect(host: str, *, timeout_seconds: float = 5.0, retries: int = 3) -> str:
    """Everything after `*` must be named, so the call site reads as prose."""
    return f"{host}/{timeout_seconds}/{retries}"


assert connect("db", retries=1) == "db/5.0/1"
```

### PS-API-09 [M] Take the narrowest type that works; return the most specific

`Iterable[str]` in, `list[str]` out. Not `list[str]` in and `Iterable[str]` out.

**Why:** the parameter constrains your callers and the return constrains you, so they pull opposite
ways. Accepting `Iterable` lets a caller pass a generator; returning `Iterable` denies them the
indexing you actually gave. This is PS-TYPE-14 stated as an API rule rather than a typing one,
because it is a design decision before it is an annotation.

**Check:** every public signature. A concrete container in, or an abstract one out, is the finding.

### PS-API-10 [S] Take a value, not a flag that selects between two behaviours

`sort(key=...)` rather than `sort(reverse_and_dedupe=True)`.

**Why:** a flag parameter means the function has two bodies sharing a name, so every reader must
hold both and every test must cover both. Splitting them gives each an honest name; passing a
value instead makes the variation the caller's to express. This is `[S]` because a flag that
genuinely toggles one line — `strict=True` — is fine.

**Check:** every `bool` parameter whose body is `if flag: ... else: ...` at the top level.

### PS-API-11 [M] Give every parameter a name the caller would choose

`path`, not `p`. `timeout_seconds`, not `t`.

**Why:** with keyword arguments the parameter name is part of the public API — renaming it is a
breaking change — and it is the only documentation visible at the call site. A one-letter name in a
public signature is a name the caller must look up every time.

**Check:** every public signature. Ruff `ARG` catches the unused ones, which are a related defect.

## Defaults and effects

### PS-API-13 [M] Make a function either return a value or perform an effect

Not both. A function that writes a file and returns the parsed contents is two functions.

**Why:** the mixed form cannot be tested without the effect, cannot be called for one half, and
gives the caller no way to know the effect happened from the value they received. Splitting makes
each half testable and lets the caller compose them.

**Check:** every function with a return value and an effect. `command-query separation` is the name
for the split.

### PS-API-14 [M] Document what the function does not do

"Does not validate the path exists." "Does not retry." "Does not close the stream."

**Why:** a caller's bugs come from what they assumed you did. The docstring naturally describes
what happens; the omissions are invisible and are exactly where the assumption forms. One
sentence removes a class of misuse.

**Check:** every public function whose name suggests more than it does — anything with `load`,
`save`, `ensure`, `sync` in it.

### PS-API-15 [M] Say who owns what the function returns

Whether the caller may mutate it, whether it is a view or a copy, whether it must be closed.

**Why:** returning a live internal container silently makes the caller's mutation your bug — see
PS-DATA-16 — and returning something that must be closed without saying so guarantees a leak. Both
are invisible from the signature. Say it, or return something immutable so the question does not
arise.

**Check:** every public return of a container or a resource. No ownership sentence is the finding.

## Modules

### PS-API-16 [M] Give every package an `__init__.py` that is a table of contents

Re-exports and `__all__`, and nothing else. No logic, no state, no work.

**Why:** the `__init__` is what every importer of the package runs, so anything in it is a cost
paid by everyone including those who wanted one submodule. Keeping it declarative makes it
readable as the package's index — and per PS-NAME-14 keeps it safe under lazy imports.

**Check:** every `__init__.py`. Anything other than imports, `__all__` and a docstring is the
finding.

### PS-API-17 [M] Never let a submodule import its parent package

`acme/reader.py` must not `from acme import thing`.

**Why:** it is a cycle: importing `acme.reader` runs `acme/__init__.py`, which imports
`acme.reader`. Python sometimes tolerates it and sometimes raises a partially-initialised-module
error depending on which module was imported first — so it works until the import order changes.

**Check:** `rg -n 'from <package> import|import <package>$' src/<package>/` — any self-reference
is the finding.

### PS-API-18 [S] Split a module when it has two audiences, not when it is long

Length is a symptom; two unrelated groups of callers is the cause.

**Why:** splitting by size produces `utils2.py` and moves the problem. Splitting by audience
produces modules with coherent surfaces, each of which can be understood without the other. A
thousand-line module with one audience is fine; a two-hundred-line module serving two is not.

**Check:** for each module, name its callers. Two disjoint groups is the finding.

### PS-API-19 [M] Keep the dependency graph acyclic and shallow

No import cycles, and no chain of internal imports deeper than a few levels.

**Why:** a cycle makes import order load-bearing and makes the modules impossible to test or reuse
separately. Depth is the subtler cost: it means understanding any one module requires understanding
a chain, and it makes every change ripple. Both are properties of the design, visible only when you
look at the graph.

**Check:** draw the internal import graph. A cycle is the finding; a chain longer than three or four
is a design question.

## Evolution

### PS-API-20 [M] Deprecate with `warnings.deprecated`, and enable the check

`@warnings.deprecated("Use X instead; removed in 2.0")` on the function, class or overload.

**Why:** PEP 702's decorator is both a runtime `DeprecationWarning` and a static signal, so callers
find out at type-check time rather than at runtime — which is when they can still act. Note it lives
in `warnings`, not `typing`. The catch worth knowing: not every checker reports it unless enabled
explicitly; `ty` does so by default, which is one of the reasons this standard mandates `ty`.

**Check:** every deprecation. A docstring note without the decorator is invisible to tooling.

### PS-API-21 [M] Add a keyword-only parameter rather than changing an existing one

New behaviour arrives as `*, new_thing: X | None = None`, defaulting to the old behaviour.

**Why:** it is the only change that cannot break a caller: nobody passes it, so nobody notices, and
those who want it opt in. Changing a parameter's type, order, or default changes the meaning of code
you cannot see. PS-API-07's keyword-only discipline is what makes this possible later.

**Check:** every signature change in review. Anything but an added keyword-only parameter is a
breaking change and needs a version bump.

### PS-API-22 [M] Give every public change a note in the changelog

Added, changed, deprecated, removed, fixed — with the version.

**Why:** the changelog is the only place a caller can learn what moved without diffing releases, and
writing it is what forces the question "is this a breaking change?" at the moment it can still be
answered differently. A change nobody wrote down is a change nobody upgraded through.

**Check:** every merge touching a name in `__all__`. No changelog entry is the finding.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `FBT001` | error | a `bool` positional parameter — make it keyword-only, or an enum |
| ruff | `FBT002` | error | a `bool` default on a positional parameter |
| ruff | `FBT003` | error | a bare `True` or `False` passed positionally |
