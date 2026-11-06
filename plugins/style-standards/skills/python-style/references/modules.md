# Modules: Layout, Imports, and the Import Graph

Scope: how a package is laid out on disk, what a module does when it is imported, how imports are
written, and the shape of the graph they form. What a module exports is the API chapter; what a
module is called is the naming chapter; building the distribution is the build chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Layout**
  - PS-MOD-01 [M] Put the package under `src/`
  - PS-MOD-02 [M] Give every package an `__init__.py` that is a table of contents
  - PS-MOD-03 [S] Split a module when it has two audiences, not when it is long
- **Imports**
  - PS-MOD-04 [M] Do no work at import time
  - PS-MOD-05 [S] Defer a costly import with `lazy import` at module scope
  - PS-MOD-06 [M] Keep the dependency graph acyclic and shallow
- Decided by tools

---

## Layout

### PS-MOD-01 [M] Put the package under `src/`

`src/acmewidget/__init__.py`, with `tests/` a sibling of `src/` rather than inside it.

**Why:** without `src/`, the current directory is on `sys.path`, so your tests import the working
copy rather than the installed package — which means the packaging is never exercised until someone
else installs it.

**Check:** a `pyproject.toml` whose package directory is a sibling of it rather than under `src/`.
Ruff `INP001` catches the related defect of a package directory with no `__init__.py`.

### PS-MOD-02 [M] Give every package an `__init__.py` that is a table of contents

Re-exports, `__all__` and a docstring, and nothing else. That it does no work is PS-MOD-04, which
holds for every module.

**Why:** the `__init__` is what every importer of the package runs, so anything in it is a cost paid
by everyone, including those who wanted one submodule. Kept declarative, it reads as the package's
index.

**Check:** every `__init__.py`. Anything other than imports, `__all__` and a docstring is the
finding.

### PS-MOD-03 [S] Split a module when it has two audiences, not when it is long

Length is a symptom; two unrelated groups of callers is the cause.

**Why:** splitting by size produces `utils2.py` and moves the problem. Splitting by audience
produces modules with coherent surfaces, each of which can be understood without the other. A
thousand-line module with one audience is fine; a two-hundred-line module serving two is not.

**Check:** for each module, name its callers. Two disjoint groups is the finding.

## Imports

### PS-MOD-04 [M] Do no work at import time

No registry population, no monkey-patching, no configuration reads, no network, no logging setup.
Importing a module defines names; it does not do things.

**Why:** import-time effects make the order of imports load-bearing in a way nothing declares. Under
PEP 810's lazy imports the module body runs at first *use*, so a registry that populated itself on
import populates itself at an unpredictable moment or not at all.

**Check:** read every module body for a statement that is not a definition, a constant, or an
import. Each is a candidate; a call is the finding.

### PS-MOD-05 [S] Defer a costly import with `lazy import` at module scope

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

### PS-MOD-06 [M] Keep the dependency graph acyclic and shallow

No import cycles, and no chain of internal imports deeper than a few levels. The commonest cycle is
a submodule importing its own package: `acme/reader.py` doing `from acme import thing` runs
`acme/__init__.py`, which imports `acme.reader`.

**Why:** a cycle makes import order load-bearing: it works, or raises a partially initialised module
error, depending on which module was imported first. Depth is the subtler cost: understanding one
module requires understanding a chain, and every change ripples along it.

**Check:** `rg -n 'from <package> import|import <package>$' src/<package>/` for a submodule
importing its parent. Then draw the internal import graph: a cycle is the finding, and a chain
longer than three or four is a design question.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `I001` | error | imports out of the standard library, third party, local grouping, or unsorted within a group — listed because it settles PEP 8's import grouping, which no rule here restates |
| ruff | `F403` | error | `from x import *` — listed because a wildcard import makes a module's names another module's `__all__` |
| ruff | `TID252` | error | a relative import, a sibling's too — listed because `ban-relative-imports = "all"` goes past ruff's default and past PEP 8, which permits explicit relative imports |
| ty | `possibly-missing-import` | warn | an import of a name its module may not define |
