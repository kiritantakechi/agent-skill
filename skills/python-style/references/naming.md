# Naming, Modules, Imports, Formatting, and Symmetry

Scope: how identifiers are cased and worded, how a module is named and laid out, import grouping
and re-export, what `ruff format` settles and what it leaves to you, comment discipline, and the
symmetry questions that apply to names rather than to types. Semantics of the things being named
live elsewhere: what a dataclass should hold is in the data-modelling chapter, what a public
function should accept is in the API chapter, and thread-safety of module state is in the
free-threading chapter.

Two sources are merged here: **PEP 8**, quoted where it is normative and named where this standard
departs from it, and **Ruff's rule catalogue**, which decides most of this mechanically — the `E`,
`N`, `I` and `D` families between them enforce roughly two thirds of what PEP 8 states in prose.
Where a rule can be a ruff code it cites one, and the shipped `assets/ruff.toml` enables it.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Casing and word choice**
  - PS-NAME-01 [M] Apply PEP 8's casing rules mechanically
  - PS-NAME-02 [M] Capitalise acronyms as ordinary English words
  - PS-NAME-03 [M] One leading underscore for non-public, two only to avoid a subclass collision
  - PS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - PS-NAME-05 [M] Put units and qualifiers last, sorted by descending significance
  - PS-NAME-06 [M] Name a predicate so it reads as a question
  - PS-NAME-07 [M] Never shadow a builtin
  - PS-NAME-08 [S] Give related names the same shape
- **Modules, packages, and imports**
  - PS-NAME-09 [M] Name a module in short lowercase; never put an underscore in a package name
  - PS-NAME-10 [M] Group imports standard library, third party, local, with a blank line between
  - PS-NAME-11 [M] Import absolutely
  - PS-NAME-12 [M] Never use a wildcard import
  - PS-NAME-13 [M] Re-export by redundant alias or by `__all__`, and pick one
  - PS-NAME-14 [M] Do no work at import time
  - PS-NAME-15 [S] Defer a costly import with `lazy import` at module scope
  - PS-NAME-16 [M] Put the package under `src/`
- **Formatting and comments**
  - PS-NAME-17 [M] Run `ruff format`; it is not a suggestion
  - PS-NAME-18 [M] Hold lines to 88 columns, and know this departs from PEP 8
  - PS-NAME-19 [M] Let the magic trailing comma decide when a call explodes
  - PS-NAME-20 [M] Say why, not what
  - PS-NAME-21 [S] Write comments as prose
  - PS-NAME-22 [M] Delete commented-out code rather than shipping it
- **Symmetry of names**
  - PS-NAME-23 [M] Name the two halves of a pair symmetrically
  - PS-NAME-24 [M] One concept, one mechanism
  - PS-NAME-25 [M] One term, one meaning, project-wide
  - PS-NAME-26 [S] Keep sibling modules structurally parallel

---

## Casing and word choice

### PS-NAME-01 [M] Apply PEP 8's casing rules mechanically

`CapWords` for classes and type aliases. `snake_case` for functions, methods, variables, modules and
packages. `SCREAMING_SNAKE_CASE` for module-level constants. `self` and `cls` always, never renamed.

**Why:** casing carries information, and only if it is uniform. Seeing `foo.Bar` you know `Bar` is a
type without looking it up; seeing `foo.bar()` you know it is not. Mixed conventions destroy that
signal for every reader thereafter, which is why PEP 8 spends more words on naming than on anything
else. A trailing underscore is the documented escape for a keyword collision — `class_`, not `klass`
or `cls_`.

**Check:** ruff's `N` family, `N801` through `N818`, decides the casing of classes, functions,
methods, arguments and variables. No `N` rule checks a module constant, so that one is review. A
codebase that cannot enable `N` has names that need fixing, not a rule that needs relaxing.

```python
# verified — GOOD
from typing import Final

MAX_RETRIES: Final = 5


class RetryPolicy:
    """CapWords for the type, snake_case for everything it holds."""

    def __init__(self, attempts: int, backoff_ms: int) -> None:
        self.attempts = attempts
        self.backoff_ms = backoff_ms

    def next_delay_ms(self, attempt: int) -> int:
        return self.backoff_ms << attempt


policy = RetryPolicy(attempts=MAX_RETRIES, backoff_ms=500)
assert policy.next_delay_ms(2) == 2_000
```

### PS-NAME-02 [M] Capitalise acronyms as ordinary English words

`HttpClient`, `XmlParser`, `JsonDecoder`, `parse_url`, `IoError`. Never `HTTPClient`, `XMLParser`,
`JSONDecoder`.

**Why:** an all-capitals acronym has no word boundary against what follows, so `HTTPSError` reads as
`HTTPS Error` or `HTTP SError` with equal justification, and `parseHTTPURL` has none at all.
Treating the acronym as a word makes the boundary mechanical. The standard library is
inconsistent here for historical reasons — `HTTPServer` alongside `JsonDecodeError` — so this is
a rule the language itself does not settle for you.

**Check:** `rg -n '\b[A-Z]{2,}[A-Z][a-z]' src/` — two or more capitals followed by a capital and
a lowercase letter is an acronym that has not been folded.

### PS-NAME-03 [M] One leading underscore for non-public, two only to avoid a subclass collision

`_helper` means "not part of the interface". `__slot` means "and I need name mangling because a
subclass might define the same name".

**Why:** PEP 8 is explicit that the double underscore is for the mangling, not for emphasis — "if
your class is intended to be subclassed, and you have attributes that you do not want subclasses to
use". Using it for privacy makes the attribute painful to reach in a debugger and in a test without
making it any more private, since `_Class__name` is right there.

**Check:** `rg -n 'self\.__[a-z]' src/` — every hit must be a name a subclass could plausibly
collide with. `SLF001` catches the other side: reaching into someone else's underscore.

### PS-NAME-04 [M] Spell names out; abbreviate only as scope tightens

`connection`, not `conn`, at module scope. `conn` is fine inside a four-line function where the
declaration is visible.

**Why:** a name's cost is paid by every reader who must reconstruct it, and that cost scales with
the distance from the declaration. At module scope the distance is unbounded. Inside a short
function it is two lines, and there the shorter name is genuinely easier to read. The universally
understood exceptions stay: `i`/`j` for indices, `n` for a count, `k`/`v` in a dict
comprehension, `_` for a value deliberately discarded.

**Check:** every module-level name and every parameter of a public function. A name shorter than
four characters that is not on the exception list is the finding.

### PS-NAME-05 [M] Put units and qualifiers last, sorted by descending significance

`timeout_seconds`, `latency_ms_max`, `payload_size_bytes`. Not `max_latency_ms`, not
`seconds_timeout`.

**Why:** big-endian naming makes alphabetical order a *semantic* grouping — `latency_ms_min` and
`latency_ms_max` land adjacent in autocomplete, in a sorted listing, and in a class body, so a
missing member of a family is visible. The unit in the name is also the cheapest defence against
the whole size/count/index confusion: `size_bytes` and `count` cannot be silently swapped, `n`
and `size` can.

**Check:** any constant, field, or keyword argument that *begins* with `max`, `min`, `num`, `total`,
or `default`. The word must be qualifying a noun to be a hit — `total_before` and `total_after` name
a total at two times, and there `total` is the noun.

```python
# verified — GOOD
from typing import Final

LATENCY_MS_MIN: Final = 1
LATENCY_MS_MAX: Final = 5_000
CONNECTION_COUNT_MAX: Final = 512
PAYLOAD_SIZE_BYTES_MAX: Final = 1 << 20

# Sorted, the family is contiguous and a missing member would be visible.
assert sorted(("LATENCY_MS_MIN", "LATENCY_MS_MAX"))[0] == "LATENCY_MS_MAX"
```

### PS-NAME-06 [M] Name a predicate so it reads as a question

`is_valid`, `has_children`, `can_retry`, `should_flush`, `contains`, `startswith`. A function
returning `bool` whose name is a noun is a function whose call site reads as an assignment.

**Why:** `if flush(buffer):` gives the reader no way to know whether it flushed and reported success
or merely asked a question, and the two are opposite. The prefix removes the ambiguity at every call
site for the cost of three characters at one declaration.

**Check:** every function annotated `-> bool`. A name that is not a question is the finding.

### PS-NAME-07 [M] Never shadow a builtin

Not `id`, `type`, `list`, `dict`, `input`, `filter`, `format`, `hash`, `next`, `object`, `bytes`.
Where the shadowing name is genuinely right, take the trailing underscore: `id_`, `type_`.

**Why:** shadowing is legal and local, which is what makes it dangerous — the code works until
someone adds a line that needs the builtin, and the error names a type mismatch rather than the
shadow. `id` and `type` are the common cases because they are also the words a domain model wants.

**Check:** ruff `A001`, `A002`, `A003` decide this — builtin shadowed by a variable, an argument,
and an attribute respectively.

### PS-NAME-08 [S] Give related names the same shape

If one is `read_timeout_seconds`, its sibling is `write_timeout_seconds`, not `write_timeout` or
`timeout_write`.

**Why:** a reader who has learned one name should be able to guess the others. Where they can, the
API teaches itself; where they cannot, every name must be looked up individually. This is the naming
half of PS-NAME-23.

**Check:** read each class body and each module's public surface as a list. A name that breaks the
pattern its neighbours establish is the finding.

## Modules, packages, and imports

### PS-NAME-09 [M] Name a module in short lowercase; never put an underscore in a package name

`retry.py`, not `retry_policy_helpers.py`. `acmewidget`, not `acme_widget`, for the importable
package.

**Why:** PEP 8 permits underscores in module names "if it improves readability" and discourages them
in package names outright. The deeper reason is that a long module name is usually a module doing
more than one thing — `retry_policy_helpers` is three nouns, which is three modules or one badly
named one.

**Check:** `find src -name '*_*_*.py'` — two or more underscores in a module name is a module worth
splitting. Any underscore in a directory under `src/` is the finding.

### PS-NAME-10 [M] Group imports standard library, third party, local, with a blank line between

Within each group, sorted. `import x` before `from x import y`.

**Why:** PEP 8 mandates the grouping and the blank lines. It does **not** mandate alphabetical order
within a group — that is isort's convention, which ruff `I001` implements and which this standard
adopts because a mechanically decidable order removes an argument that has no right answer.

**Check:** ruff `I001`. The alphabetisation is a tool convention rather than PEP 8; the grouping is
PEP 8.

```python
# verified — GOOD
import json
import sys
from pathlib import Path

# A third-party group would sit here, blank-line separated.
from typing import Final

ENCODING: Final = "utf-8"


def load(path: Path) -> dict[str, object]:
    # The encoding is explicit: 3.15 changed the default, so relying on it means
    # relying on a thing that moved.
    parsed = json.loads(path.read_text(encoding=ENCODING))
    # `json.loads` returns `Any`. Returning it straight from an annotated
    # function launders an unchecked value into a checked one, which a strict
    # type checker rejects and which is the whole reason it is strict.
    if not isinstance(parsed, dict):
        msg = f"{path}: expected an object at the top level"
        raise TypeError(msg)
    return {str(k): v for k, v in parsed.items()}


assert sys.version_info >= (3, 15)
```

### PS-NAME-11 [M] Import absolutely

`from acmewidget.retry import RetryPolicy`, not `from .retry import RetryPolicy`.

**Why:** PEP 8 recommends absolute imports because they are "usually more readable and tend to be
better behaved". The concrete misbehaviour is that a relative import makes a module's meaning depend
on where it sits, so moving a file changes what it imports without changing a character of it. PEP 8
does permit explicit relative imports for complex layouts; the standard library requires absolute.

**Check:** ruff `TID252` bans relative imports beyond a configurable depth. `rg -n '^from \.'
src/` finds the rest.

### PS-NAME-12 [M] Never use a wildcard import

`from x import *` at any scope.

**Why:** it makes the set of names in scope depend on a file you are not reading, so a rename in the
imported module silently shadows or un-shadows a name here. It also defeats every tool: neither the
type checker nor the reader can resolve a name to its origin. The one carve-out PEP 8 allows —
republishing an internal interface — is better served by PS-NAME-13's explicit re-export.

**Check:** ruff `F403` for the import and `F405` for each name that may be coming from it.

### PS-NAME-13 [M] Re-export by redundant alias or by `__all__`, and pick one

`from ._core import Widget as Widget`, or `__all__ = ["Widget"]`. Not a bare
`from ._core import Widget` in an `__init__.py`.

**Why:** this is not a style preference — the typing specification makes imported symbols **private
by default**, so a bare import in `__init__.py` is not part of your public interface as far as a
type checker is concerned, and downstream code importing it gets an error. The two spellings
above are the documented ways to say otherwise. Pick one per project: mixing them means the
reader must check both places to know whether a name is public.

**Check:** for a package shipping `py.typed`, run the type checker over a file that imports each
documented name from the package root. A `does not explicitly export` error is the finding.

### PS-NAME-14 [M] Do no work at import time

No registry population, no monkey-patching, no configuration reads, no network, no logging setup.
Importing a module defines names; it does not do things.

**Why:** import-time effects make the order of imports load-bearing, which makes it fragile in a way
nothing declares. PEP 810 sharpens this from untidy to broken: under lazy imports the module body
runs at first *use*, so a registry that populated itself on import populates itself at an
unpredictable moment or not at all. The PEP says it outright — "users should be wary of modules that
rely on import time side effects" — and names the registry pattern as the common case.

**Check:** read every module body for a statement that is not a definition, a constant, or an
import. Each is a candidate; a call is the finding.

### PS-NAME-15 [S] Defer a costly import with `lazy import` at module scope

`lazy import pandas`. Not an import moved inside a function.

**Why:** the function-local import was the only tool available and it has real costs: it hides the
dependency from every reader of the import block, and it re-resolves the import on each call. PEP
810 supersedes it — "users who are moving imports into functions to improve startup time should
instead consider keeping them where they are but adding the `lazy` keyword". `lazy` is
module-scope only; inside a function, a class body, or a `try` it is a `SyntaxError`, which is
the language enforcing this rule for you.

**Check:** `rg -nB2 '^[ \t]+import |^[ \t]+from .* import ' src/`, then read each hit for what
encloses it — indentation alone cannot tell a function body from an `if` block. An import under
`if TYPE_CHECKING:` is the documented way to keep a name out of the runtime and is not a hit. One
inside a function is the finding unless it exists to break a cycle, which needs a comment saying so.
Ruff `TID255` flags the opposite mistake: a `lazy` import that module load resolves at once anyway.

### PS-NAME-16 [M] Put the package under `src/`

`src/acmewidget/__init__.py`, with `tests/` a sibling of `src/` rather than inside it.

**Why:** without `src/`, the current directory is on `sys.path`, so your tests import the working
copy rather than the installed package — which means the packaging is never exercised until someone
else installs it. The PyPA guidance is that the layout "helps prevent accidental usage of the
in-development copy" and "helps enforce that an editable installation is only able to import files
that were meant to be importable". `uv init` produces it for libraries and applications alike.

**Check:** a `pyproject.toml` whose package directory is a sibling of it rather than under `src/`.
Ruff `INP001` catches the related defect of a package directory with no `__init__.py`.

## Formatting and comments

### PS-NAME-17 [M] Run `ruff format`; it is not a suggestion

In CI, as a gate, with `--check`. Never as a matter of individual discipline.

**Why:** formatting arguments have no right answer, so the only way to stop having them is to remove
the choice. A formatter that runs sometimes is worse than none, because the diff noise it produces
lands on whoever touches the file next rather than on whoever skipped it.

**Check:** `ruff format --check` in CI. Zero stderr from it is also ruff's own proof that no enabled
lint rule conflicts with the formatter — though only two of the fifteen documented conflicts
actually warn, so the rule set must be checked against that list directly rather than inferred from
a quiet run.

### PS-NAME-18 [M] Hold lines to 88 columns, and know this departs from PEP 8

88 for code. 72 for the text inside a docstring or comment, which is PEP 8's number and which the
formatter does not enforce for you.

**Why:** PEP 8 says 79, with 99 permitted only "for code maintained exclusively or primarily by a
team that can reach agreement on this issue" — and that escape hatch explicitly does not lift the
72-column limit on docstrings and comments. This standard takes 88 because the house standard is
Ruff and 88 is its default, and deviating from a formatter's own default is the sort of unmotivated
divergence this standard exists to argue against. The disagreement is real and is stated here rather
than hidden. CPython itself uses 79.

**Check:** ruff `E501` at the configured length. The formatter makes only a best-effort attempt, so
`E501` stays enabled as the backstop rather than being ignored as redundant.

### PS-NAME-19 [M] Let the magic trailing comma decide when a call explodes

A trailing comma in a collection or call means "one element per line, always". No trailing comma
means "fit it on one line if it fits".

**Why:** this turns a formatting decision into a semantic one the author makes deliberately and the
formatter then executes. It is also the single lever that keeps a growing argument list from
producing a one-line diff that touches every argument. PEP 8's own rule is narrower — a trailing
comma is mandatory only for a one-element tuple, and forbidden on the same line as the closing
bracket.

**Check:** the formatter enforces this itself, so there is no lint rule to enable — and the one that
looks like it, flake8-commas, is on ruff's documented formatter-conflict list and must stay
disabled. Verify by adding a trailing comma to a collection that fits on one line and confirming
`ruff format` keeps it exploded.

```python
# verified — GOOD
short = [1, 2, 3]

# The trailing comma is the instruction: keep one per line, even though they fit.
tall = [
    1,
    2,
    3,
]
assert short == tall
```

### PS-NAME-20 [M] Say why, not what

Code says what it does. A comment exists to record the reasoning, the alternative rejected, and the
constraint that is not visible locally.

**Why:** a comment restating the code is a second copy that will drift from the first, and the drift
is invisible because nothing checks it. A comment recording *why* cannot be derived from the code at
all, which is exactly why it is worth writing — and why deleting it loses something.

**Check:** read every comment and ask whether the line below it would have told you the same
thing. A comment that restates is the finding; `ERA001` catches the commented-out-code case.

### PS-NAME-21 [S] Write comments as prose

A space after the `#`, a capital letter, a full stop. An end-of-line comment may be a bare phrase.

**Why:** comments are the part of the file a reader reads at reading speed rather than at parsing
speed, and the typography is what makes that possible. `ruff format` does not touch comment text, so
this is one of the few things left to discipline.

**Check:** a review matter, and deliberately so. The two pycodestyle rules that would decide the
marker and the space are both **preview**, and the shipped configuration runs stable rules only —
citing them would claim an enforcement this standard's own configuration does not provide.

### PS-NAME-22 [M] Delete commented-out code rather than shipping it

Version control has it. The comment does not say when it was disabled, by whom, or whether it still
works.

**Why:** commented-out code is indistinguishable from code that was never finished, so every reader
must decide whether to restore it and none of them has the information to. The claim that it is
"there for reference" is answered by `git log`.

**Check:** ruff `ERA001`.

## Symmetry of names

### PS-NAME-23 [M] Name the two halves of a pair symmetrically

`open`/`close`, `acquire`/`release`, `encode`/`decode`, `push`/`pop`, `to_json`/`from_json`. Never
`open`/`shutdown`, never `encode`/`parse`.

**Why:** an asymmetric pair forces the reader to remember two words where one would have implied the
other, and it hides the missing half of an incomplete API: if `serialise` exists and nothing is
called `deserialise`, either the inverse is missing or it is spelled unguessably. Both are findings.

**Check:** list every public verb in the module. For each, name its inverse and check the
spelling is its mirror. A verb with no inverse is either genuinely one-directional — say so in
the docstring — or an oversight.

### PS-NAME-24 [M] One concept, one mechanism

If configuration comes from a dataclass, it does not also come from a dict. If errors are
exceptions, they are not also sentinel return values.

**Why:** two mechanisms for one concept doubles the surface every caller must handle and every test
must cover, and the second one is invariably less complete than the first. It usually arrives as a
convenience added for one call site and then spreads.

**Check:** for each concept in the module — configuration, errors, identity, time — name the
mechanism. Two mechanisms for one concept is the finding.

### PS-NAME-25 [M] One term, one meaning, project-wide

If a row from the database is an `Account`, it is not a `User` in the next module and a
`Customer` in the one after.

**Why:** synonyms make search useless and make every conversation about the code start with a
translation step. The cost compounds: a reader who has learned that `Account` and `User` are the
same thing must then decide, for each new name, whether it is a third synonym or a genuinely
different concept.

**Check:** keep a glossary. A name that is not in it is either new — add it — or a synonym, which is
the finding.

### PS-NAME-26 [S] Keep sibling modules structurally parallel

If `readers/json.py` exposes `load`, `loads` and a `JsonError`, then `readers/toml.py` exposes
`load`, `loads` and a `TomlError`.

**Why:** parallel siblings let a reader learn one and use all of them, and they make a missing piece
visible as a hole in the pattern rather than as an absence nobody notices. It also makes the modules
substitutable, which is what lets a caller pick one at runtime.

**Check:** list the public names of each sibling module side by side. A name present in one column
and absent from another is either a deliberate difference — say why — or the finding.
