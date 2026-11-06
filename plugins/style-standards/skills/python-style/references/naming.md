# Naming: Casing, Words, Formatting, Comments, and Symmetry

Scope: how identifiers are cased and worded, modules and packages included, what `ruff format`
settles and what it leaves to you, comment discipline, and the symmetry questions that apply to
names rather than to types. Semantics of the things being named live elsewhere: what a dataclass
should hold is in the data chapter, what a package accepts and re-exports is in the API chapter, how
a package is laid out and imported is in the modules chapter, and thread-safety of module state is
in the concurrency chapter.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Casing and word choice**
  - PS-NAME-01 [M] Apply PEP 8's casing rules mechanically
  - PS-NAME-02 [M] Capitalise every letter of an acronym in a CapWords name
  - PS-NAME-03 [M] Use two leading underscores only for name mangling
  - PS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - PS-NAME-05 [M] Put units and qualifiers last, sorted by descending significance
  - PS-NAME-06 [M] Name a predicate so it reads as a question
  - PS-NAME-07 [S] Give related names the same shape
  - PS-NAME-08 [M] Name a module in short lowercase; never put an underscore in a package name
- **Formatting and comments**
  - PS-NAME-09 [M] Run `ruff format`; it is not a suggestion
  - PS-NAME-10 [M] Hold lines to 88 columns, and know this departs from PEP 8
  - PS-NAME-11 [M] Let the magic trailing comma decide when a call explodes
  - PS-NAME-12 [M] Say why, not what
  - PS-NAME-13 [S] Write comments as prose
- **Symmetry of names**
  - PS-NAME-14 [M] Name the two halves of a pair symmetrically
  - PS-NAME-15 [M] One concept, one mechanism
  - PS-NAME-16 [M] One term, one meaning, project-wide
  - PS-NAME-17 [S] Keep sibling modules and types structurally parallel
- Decided by tools

---

## Casing and word choice

### PS-NAME-01 [M] Apply PEP 8's casing rules mechanically

`CapWords` for classes and type aliases. `snake_case` for functions, methods, variables, modules and
packages. `SCREAMING_SNAKE_CASE` for module-level constants. `self` and `cls` always, never renamed.
A trailing underscore is the documented escape for a keyword collision — `class_`, not `klass` or
`cls_`.

**Why:** casing carries information, and only if it is uniform. Seeing `foo.Bar` you know `Bar` is a
type without looking it up; seeing `foo.bar()` you know it is not. Mixed conventions destroy that
signal for every reader thereafter.

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
        """Retry `attempts` times, doubling from `backoff_ms`."""
        self.attempts = attempts
        self.backoff_ms = backoff_ms

    def next_delay_ms(self, attempt: int) -> int:
        """Return the wait before retry number `attempt`."""
        return self.backoff_ms << attempt


policy = RetryPolicy(attempts=MAX_RETRIES, backoff_ms=500)
assert policy.next_delay_ms(2) == 2_000
```

### PS-NAME-02 [M] Capitalise every letter of an acronym in a CapWords name

`HTTPClient`, `XMLParser`, `JSONDecodeError`. Never `HttpClient`, `XmlParser`, `JsonDecodeError`. In
a `snake_case` name the acronym is lower case like every other word: `parse_url`, `http_client`.

**Why:** PEP 8 states it — "HTTPServerError is better than HttpServerError" — and the standard
library spells its own that way: `JSONDecodeError`, `HTTPStatus`, `TOMLDecodeError`, `SSLError`. A
project's `JsonError` beside `json.JSONDecodeError` gives one acronym two spellings to remember.

**Check:** `rg -n '\b(Http|Https|Json|Xml|Html|Url|Uri|Sql|Api|Tcp|Udp|Ssl|Tls|Toml|Csv)[A-Z]' src/`
— a common acronym folded into a word ahead of the next one. The list is not exhaustive; add the
project's own acronyms to it.

### PS-NAME-03 [M] Use two leading underscores only for name mangling

`__slot` means "I need name mangling, because a subclass might define the same name". That one
leading underscore marks a non-public name is PS-API-04's rule.

**Why:** the double underscore buys name mangling and nothing else, since `_Class__name` is right
there. Using it for privacy makes the attribute painful to reach in a debugger and in a test without
making it any more private; PEP 8 reserves it for the mangling, not for emphasis.

**Check:** `rg -n 'self\.__[a-z]' src/` — every hit must be a name a subclass could plausibly
collide with.

### PS-NAME-04 [M] Spell names out; abbreviate only as scope tightens

`connection`, not `conn`, at module scope. `conn` is fine inside a four-line function where the
declaration is visible. The universally understood exceptions stay: `i`/`j` for indices, `n` for a
count, `k`/`v` in a dict comprehension, `_` for a value deliberately discarded.

**Why:** a name's cost is paid by every reader who must reconstruct it, and that cost scales with
the distance from the declaration. At module scope the distance is unbounded; inside a short
function it is two lines, and there the shorter name is genuinely easier to read.

**Check:** every module-level name and every parameter of a public function. A name shorter than
four characters is a candidate: one that abbreviates a longer word and is not on the exception list
is the finding, while a word that is short already, such as `key` or `raw`, is spelled out.

### PS-NAME-05 [M] Put units and qualifiers last, sorted by descending significance

`timeout_seconds`, `latency_ms_max`, `payload_size_bytes`. Not `max_latency_ms`, not
`seconds_timeout`. A unit is one of the qualifiers: a value whose type carries its unit (PS-DATA-16)
needs none in its name, and a primitive that keeps one — the `float` of seconds a standard-library
call takes — carries it here, last.

**Why:** big-endian naming makes alphabetical order a *semantic* grouping — `latency_ms_min` and
`latency_ms_max` land adjacent wherever names are sorted, so a missing member of a family shows.

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

# Sorted, the family is contiguous, so a missing member shows.
family = ["PAYLOAD_SIZE_BYTES_MAX", "LATENCY_MS_MIN", "LATENCY_MS_MAX"]
assert sorted(family)[:2] == ["LATENCY_MS_MAX", "LATENCY_MS_MIN"]
```

### PS-NAME-06 [M] Name a predicate so it reads as a question

`is_valid`, `has_children`, `can_retry`, `should_flush`, `contains`, `startswith`. A function
returning `bool` whose name is a noun is a function whose call site reads as an assignment.

**Why:** `if flush(buffer):` gives the reader no way to know whether it flushed and reported success
or merely asked a question, and the two are opposite. The prefix removes the ambiguity at every call
site for the cost of three characters at one declaration.

**Check:** every function annotated `-> bool`. A name that is not a question is the finding.

### PS-NAME-07 [S] Give related names the same shape

If one is `read_timeout_seconds`, its sibling is `write_timeout_seconds`, not `write_timeout` or
`timeout_write`.

**Why:** a reader who has learned one name should be able to guess the others. Where they can, the
API teaches itself; where they cannot, every name must be looked up individually. This is the naming
half of PS-NAME-14.

**Check:** read each class body and each module's public surface as a list. A name that breaks the
pattern its neighbours establish is the finding.

### PS-NAME-08 [M] Name a module in short lowercase; never put an underscore in a package name

`retry.py`, not `retry_policy_helpers.py`. `acmewidget`, not `acme_widget`, for the importable
package.

**Why:** a long module name is usually a module doing more than one thing — `retry_policy_helpers`
is three nouns, which is three modules or one badly named one. PEP 8 permits underscores in module
names "if it improves readability" and discourages them in package names outright.

**Check:** `find src -name '[!_]*_*_*.py' -o -name '_*_*_*.py' ! -name '__*'` — a third word in a
module name, not counting a private module's leading underscore or a dunder like `__init__.py`, is a
module worth splitting. Any underscore in a directory under `src/` is the finding.

## Formatting and comments

### PS-NAME-09 [M] Run `ruff format`; it is not a suggestion

In CI, as a gate, with `--check`. Never as a matter of individual discipline.

**Why:** formatting arguments have no right answer, so the only way to stop having them is to remove
the choice. A formatter that runs sometimes is worse than none, because the diff noise it produces
lands on whoever touches the file next rather than on whoever skipped it.

**Check:** `ruff format --check` in CI. Its stderr also names an enabled lint rule that conflicts
with the formatter — but only for some of the documented conflicts, so the rule set must be checked
against that list directly rather than inferred from a quiet run.

### PS-NAME-10 [M] Hold lines to 88 columns, and know this departs from PEP 8

88 for code. 72 for the text inside a docstring or comment, which is PEP 8's number and which the
formatter does not enforce for you. PEP 8 says 79 for code, and CPython itself uses 79.

**Why:** 88 is the default of Ruff, the house standard, and deviating from a formatter's own default
is the unmotivated divergence this standard exists to argue against. PEP 8's 99-column escape hatch
for an agreeing team explicitly does not lift the 72-column limit on docstrings and comments.

**Check:** ruff `E501` at 88 and `W505` at 72, the documentation chapter's row for prose. The
formatter makes only a best-effort attempt at 88, so `E501` stays enabled as the backstop rather
than being ignored as redundant.

### PS-NAME-11 [M] Let the magic trailing comma decide when a call explodes

A trailing comma in a collection or call means "one element per line, always". No trailing comma
means "fit it on one line if it fits".

**Why:** this turns a formatting decision into a semantic one the author makes deliberately and the
formatter then executes. It is also the single lever that keeps a growing argument list from
producing a one-line diff that touches every argument.

**Check:** `ruff format --check` (PS-NAME-09). With `skip-magic-trailing-comma = false`, ruff's
default and the shipped `[format]` setting, the formatter enforces this itself; flake8-commas, the
lint that looks like it, is on ruff's formatter-conflict list and stays disabled.

```python
# verified — GOOD
short = [1, 2, 3]

# The trailing comma is the instruction: one per line, though they fit.
tall = [
    1,
    2,
    3,
]
assert short == tall
```

### PS-NAME-12 [M] Say why, not what

Code says what it does. A comment exists to record the reasoning — why this algorithm, why this
default — the alternative rejected, and the constraint that is not visible locally.

**Why:** a comment restating the code is a second copy that will drift, invisibly. A comment
recording *why* cannot be derived from the code at all: without it the next person re-derives the
reason, usually by reverting the decision and rediscovering it.

**Check:** every non-obvious constant, every hand-rolled algorithm and every `# noqa` carries its
reason. For every other comment, ask whether the line below it would have told you the same thing: a
comment that restates is the finding. `ERA001` catches the commented-out-code case.

### PS-NAME-13 [S] Write comments as prose

A space after the `#`, a capital letter, a full stop. An end-of-line comment may be a bare phrase.

**Why:** comments are the part of the file a reader reads at reading speed rather than at parsing
speed, and the typography is what makes that possible. `ruff format` does not touch comment text, so
this is one of the few things left to discipline.

**Check:** a review matter, and deliberately so. The two pycodestyle rules that would decide the
marker and the space are both **preview**, and the shipped configuration runs stable rules only —
citing them would claim an enforcement this standard's own configuration does not provide.

## Symmetry of names

### PS-NAME-14 [M] Name the two halves of a pair symmetrically

`open`/`close`, `acquire`/`release`, `encode`/`decode`, `push`/`pop`, `to_json`/`from_json`. Never
`open`/`shutdown`, never `encode`/`parse`. Whether the inverse must exist is PS-DATA-18's rule; this
one is how it is spelled.

**Why:** an asymmetric pair forces the reader to remember two words where one would have implied the
other, and a reader who finds `serialise` and no `deserialise` cannot tell a missing inverse from
one spelled unguessably.

**Check:** list every public verb that has an inverse. A pair whose names are not each other's
mirror is the finding.

### PS-NAME-15 [M] One concept, one mechanism

If configuration comes from a dataclass, it does not also come from a dict. If errors are
exceptions, they are not also sentinel return values.

**Why:** two mechanisms for one concept doubles the surface every caller must handle and every test
must cover, and the second one is invariably less complete than the first. It usually arrives as a
convenience added for one call site and then spreads.

**Check:** for each concept in the module — configuration, errors, identity, time — name the
mechanism. Two mechanisms for one concept is the finding.

### PS-NAME-16 [M] One term, one meaning, project-wide

If a row from the database is an `Account`, it is not a `User` in the next module and a `Customer`
in the one after.

**Why:** synonyms make search useless and start every conversation about the code with a translation
step. The cost compounds: a reader who has learned that `Account` and `User` are the same thing must
then decide, for each new name, whether it is a third synonym or a genuinely different concept.

**Check:** keep a glossary. A name that is not in it is either new — add it — or a synonym, which is
the finding.

### PS-NAME-17 [S] Keep sibling modules and types structurally parallel

If `readers/json.py` exposes `load`, `loads` and a `JSONError`, then `readers/toml.py` exposes
`load`, `loads` and a `TOMLError`. If `Request` is a frozen slotted dataclass with
`to_dict`/`from_dict`, so is `Response`.

**Why:** parallel siblings let a reader learn one and use all of them, and they make a missing piece
visible as a hole in the pattern rather than as an absence nobody notices. It also makes the
siblings substitutable, which is what lets a caller pick one at runtime.

**Check:** list the public names of each sibling module or type side by side. A name present in one
column and absent from another is either a deliberate difference — say why — or the finding.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `A001` | error | a variable named after a builtin — take a trailing underscore, `id_` — listed because its fix is PS-NAME-01's trailing underscore |
| ruff | `ERA001` | error | commented-out code — version control keeps it — listed because PS-NAME-12's comments say why, and code commented out says nothing |
