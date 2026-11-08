# Modules: Boundaries, Layout, Imports, Order, and Orthogonality

Scope: how code is divided into modules and packages, what each boundary costs, how a package is
laid out on disk, what a module does when it is imported, how imports are written and the shape of
the graph they form, the order of a module and of a class, and the one-mechanism-per-concept
discipline across them. What a module exports is the API chapter; building the distribution is the
build chapter; what a docstring says is the documentation chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Dividing code into modules**
  - PS-MOD-01 [M] Open every module with a docstring that states its one concept
  - PS-MOD-02 [S] Split a module when it has two audiences, not when it is long
  - PS-MOD-03 [M] Count the names a split makes public, not only what it buys
  - PS-MOD-04 [S] Name a module in short lowercase; avoid an underscore in a package name
- **Layout**
  - PS-MOD-05 [M] Put the package under `src/`
  - PS-MOD-06 [M] Give the distribution and the module the same name
- **Imports and the graph**
  - PS-MOD-07 [M] Do no work at import time
  - PS-MOD-08 [S] Defer a costly import with `lazy import` at module scope
  - PS-MOD-09 [M] Keep the dependency graph acyclic and shallow
- **Order within a file**
  - PS-MOD-10 [S] Put a module's public names before its private helpers
  - PS-MOD-11 [S] Order a class body: fields, constructors, public methods, private methods
- **Orthogonality**
  - PS-MOD-12 [M] One concept, one mechanism
  - PS-MOD-13 [S] Keep sibling modules and types structurally parallel
  - PS-MOD-14 [M] Absorb a special case into the general path, or give it its own type
- Decided by tools

---

## Dividing code into modules

### PS-MOD-01 [M] Open every module with a docstring that states its one concept

One sentence at the top: what the module holds, as a role and not as a list of its names. Ruff
`D100` requires a docstring on a public module; this is what the docstring is for.

**Why:** a module is a claim about cohesion, and a claim you cannot state in a sentence is a
boundary in the wrong place. The sentence tells the next contributor where new code goes.

**Check:** for each module, write the sentence. A module whose sentence needs "and" is two modules.

```python
# verified — GOOD
"""Count words. Nothing here reads files or prints."""


def count(text: str) -> int:
    """Return the number of whitespace-separated words in `text`."""
    return len(text.split())


assert count("a b  c") == 3
```

### PS-MOD-02 [S] Split a module when it has two audiences, not when it is long

Length is a symptom; two unrelated groups of callers is the cause.

**Why:** splitting by size produces `utils2.py` and moves the problem. Splitting by audience
produces modules with coherent surfaces, each of which can be understood without the other. A
thousand-line module with one audience is fine; a two-hundred-line module serving two is not.

**Check:** for each module, name its callers. Two disjoint groups is the finding.

### PS-MOD-03 [M] Count the names a split makes public, not only what it buys

A module's siblings can reach only the names it offers. Every name the split makes them need loses
its leading underscore or is imported across the boundary under a private name. A seam that exposes
a handful of names is a seam; one that exposes dozens is the wrong seam, whatever PS-MOD-02 says
about its audiences.

**Why:** the underscore is the only encapsulation a module has (PS-API-05), so a split turns
internals into names other modules may depend on, and the package owes them compatibility from then
on.

**Check:** list the underscore names the split forces other modules to import. Would you have made
each of them public on its own merits?

### PS-MOD-04 [S] Name a module in short lowercase; avoid an underscore in a package name

`retry.py`, not `retry_policy_helpers.py`. `acmewidget`, not `acme_widget`, for the importable
package.

**Why:** a long module name is usually a module doing more than one thing — `retry_policy_helpers`
is three nouns, which is three modules or one badly named one. PEP 8 permits underscores in module
names "if it improves readability" and discourages them in package names outright.

**Check:** `find src -name '[!_]*_*_*.py' -o -name '_*_*_*.py' ! -name '__*'` — a third word in a
module name, not counting a private module's leading underscore or a dunder like `__init__.py`, is a
module worth splitting. Any underscore in a directory under `src/` is the finding.

## Layout

### PS-MOD-05 [M] Put the package under `src/`

`src/acmewidget/__init__.py`, with `tests/` a sibling of `src/` rather than inside it.

**Why:** without `src/`, the current directory is on `sys.path`, so your tests import the working
copy rather than the installed package — which means the packaging is never exercised until someone
else installs it.

**Check:** a `pyproject.toml` whose package directory is a sibling of it rather than under `src/`.
Ruff `INP001` catches the related defect of a package directory with no `__init__.py`.

### PS-MOD-06 [M] Give the distribution and the module the same name

`name = "acmewidget"` and `src/acmewidget/`. Not `acme-widget` wrapping a directory called
`acmewidget`.

**Why:** a backend finds your package by normalising the distribution name — `acme-widget` becomes
`acme_widget` — and looking for that directory under `src/`. Name them differently and the build
fails outright until a `module-name` override papers over it; matched, the layout is inferred.

**Check:** `rg -n '^name' pyproject.toml` against the directory under `src/`. Any difference is the
finding.

## Imports and the graph

### PS-MOD-07 [M] Do no work at import time

No registry population, no monkey-patching, no configuration reads, no network, no logging setup.
Importing a module defines names; it does not do things.

**Why:** import-time effects make the order of imports load-bearing in a way nothing declares. Under
PEP 810's lazy imports the module body runs at first *use*, so a registry that populated itself on
import populates itself at an unpredictable moment or not at all.

**Check:** read every module body for a statement that is not a definition, a constant, or an
import. Each is a candidate; a call is the finding.

### PS-MOD-08 [S] Defer a costly import with `lazy import` at module scope

`lazy import pandas`. Not an import moved inside a function. `lazy` is module-scope only; inside a
function, a class body, or a `try` it is a `SyntaxError`.

**Why:** a function-local import hides the dependency from every reader of the import block, and it
re-resolves the import on each call. PEP 810 tells anyone moving imports into functions for startup
time to "instead consider keeping them where they are but adding the `lazy` keyword".

**Check:** `rg -nB2 '^[ \t]+import |^[ \t]+from .* import ' src/`, then read each hit for what
encloses it — indentation alone cannot tell a function body from an `if` block. An import under
`if TYPE_CHECKING:` is the documented way to keep a name out of the runtime and is not a hit. One
inside a function is the finding unless it exists to break a cycle, which needs a comment saying so.
Ruff `TID255` flags the opposite mistake: a `lazy` import that module load resolves at once anyway.

### PS-MOD-09 [M] Keep the dependency graph acyclic and shallow

No import cycles, and no chain of internal imports deeper than a few levels. The commonest cycle is
a submodule importing its own package: `acme/reader.py` doing `from acme import thing` runs
`acme/__init__.py`, which imports `acme.reader`.

**Why:** a cycle makes import order load-bearing: it works, or raises a partially initialised module
error, depending on which module was imported first. Depth is the subtler cost: understanding one
module requires understanding a chain, and every change ripples along it.

**Check:** `rg -n 'from <package> import|import <package>$' src/<package>/` for a submodule
importing its parent. Then draw the internal import graph: a cycle is the finding, and a chain
longer than three or four is a design question.

## Order within a file

### PS-MOD-10 [S] Put a module's public names before its private helpers

Docstring, imports, `__all__`, the public functions and classes, then the private helpers they call.
A function body looks its names up when it runs, so a helper may follow the function that calls it.

**Why:** readers scan top-down for the public surface, and a private helper first makes them read
the implementation before the interface. The order costs nothing, because Python does not care.

**Check:** in each module, is the first definition after the imports and `__all__` public? A private
helper above the public function that calls it is the finding, unless the helper is needed as the
module loads (a decorator, a default value, a base class).

```python
# verified — GOOD
"""Summarise text. The public name comes first; its helper follows."""

__all__ = ["summarise"]


def summarise(text: str) -> str:
    """Return the first sentence of `text`, trimmed."""
    return _first_sentence(text).strip()


def _first_sentence(text: str) -> str:
    return text.split(".", 1)[0]


assert summarise("One. Two.") == "One"
```

### PS-MOD-11 [S] Order a class body: fields, constructors, public methods, private methods

Class-level attributes and fields first, then `__init__` and the alternative constructors, then the
other special methods and the public methods, and the private methods last.

**Why:** the fields are the data and everything below derives from them, so a reader who rebuilds
the invariants reads top-down and never scrolls back. A fixed order is also where a reviewer looks.

**Check:** read each class body for the first `def`. A field below a method, a constructor below an
ordinary method, or a public method below a private one is out of order.

```python
# verified — GOOD
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class Counter:
    """Fields, constructors, public methods, then private ones."""

    total: int = 0

    @classmethod
    def starting_at(cls, total: int) -> Self:
        """Return a counter that begins at `total`."""
        return cls(total)

    def add(self, amount: int) -> Self:
        """Return the counter advanced by a non-negative `amount`."""
        return type(self)(self.total + self._checked(amount))

    def _checked(self, amount: int) -> int:
        if amount < 0:
            raise ValueError(amount)
        return amount


assert Counter.starting_at(2).add(3).total == 5
```

## Orthogonality

### PS-MOD-12 [M] One concept, one mechanism

If configuration comes from a dataclass, it does not also come from a dict. If errors are
exceptions, they are not also sentinel return values.

**Why:** two mechanisms for one concept doubles the surface every caller must handle and every test
must cover, and the second one is invariably less complete than the first. It usually arrives as a
convenience added for one call site and then spreads.

**Check:** for each concept in the module — configuration, errors, identity, time — name the
mechanism. Two mechanisms for one concept is the finding.

### PS-MOD-13 [S] Keep sibling modules and types structurally parallel

If `readers/json.py` exposes `load`, `loads` and a `JSONError`, then `readers/toml.py` exposes
`load`, `loads` and a `TOMLError`. If `Request` is a frozen slotted dataclass with
`to_dict`/`from_dict`, so is `Response`.

**Why:** parallel siblings let a reader learn one and use all of them, and they make a missing piece
visible as a hole in the pattern rather than as an absence nobody notices. It also makes the
siblings substitutable, which is what lets a caller pick one at runtime.

**Check:** list the public names of each sibling module or type side by side. A name present in one
column and absent from another is either a deliberate difference — say why — or the finding.

### PS-MOD-14 [M] Absorb a special case into the general path, or give it its own type

A branch that exists for one input is not a feature; it is an unfinished generalisation. Either the
general path handles it, usually by widening a parameter or adding a variant, or the case differs
enough to deserve its own type and its own function.

**Why:** special-case branches compound. Each is locally cheap and globally expensive, because every
later change must be tested against every branch and nothing marks which combinations are reachable.

**Check:** for each `if` whose condition names a specific input (a particular filename, an empty
list treated unlike others, a magic value), ask what the general case would have to be for the
branch to disappear. That is usually the correct design.

```python
# verified — GOOD
def join(parts: list[str], separator: str) -> str:
    """The general path absorbs the empty list; no branch names it."""
    return separator.join(parts)


assert join([], ",") == ""
assert join(["a", "b"], ",") == "a,b"
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `I001` | error | imports out of the standard library, third party, local grouping, or unsorted within a group — listed because it settles PEP 8's import grouping, which no rule here restates |
| ruff | `F403` | error | `from x import *` — listed because a wildcard import makes a module's names another module's `__all__` |
| ruff | `TID252` | error | a relative import, a sibling's too — listed because `ban-relative-imports = "all"` goes past ruff's default and past PEP 8, which permits explicit relative imports |
| ty | `possibly-missing-import` | warn | an import of a name its module may not define |
