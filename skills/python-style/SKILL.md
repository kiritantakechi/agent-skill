---
name: python-style
description: >-
  The modern Python 3.15 engineering standard — a 262-rule library merging the normative Python
  specifications (PEP 8, PEP 257, PEP 20, and the Python Typing Spec), the empirical conventions of
  the CPython standard library, and Ruff's rule catalogue as its house standard. Covers free
  threading and what the GIL stopped guaranteeing, shared state, iterators, caches and context,
  streams, and the build. Use this whenever writing, reviewing, refactoring, scaffolding, or
  debugging ANY Python — a package, one function, a pyproject.toml, a dataclass, a thread pool, a
  test — even if the user never mentions "style", "standards", or "quality". Also use when asked to
  make Python "idiomatic", "modern", "clean", or "production-grade", when auditing a Python
  codebase, when the current spelling of a standard-library symbol is uncertain, and when moving
  code to the free-threaded build.
---

# Python Style — 3.15

A single standard formed from three sources: the **normative Python specifications** (PEP 8, PEP
257, PEP 20, and the Python Typing Spec, cited from the living specs rather than from the PEPs,
which now redirect to them), the **empirical conventions of the CPython 3.15 standard library**, and
**Ruff's rule catalogue** as the house standard. Where they disagree, this standard picks a side and
says why.

**Target: CPython 3.15, free-threaded.** Nothing below 3.14t is supported and no compatibility shim
is described. Section 2 is the highest-value part of this skill: most of what 3.14 and 3.15 changed
produces silently different behaviour rather than an error, so nothing catches it for you.

## How to use this standard

1. **Read section 2** before emitting Python code. It is the Python 3.15 reality check, and some of
   its entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID — `PS-ERR-03`, `PS-TEST-05`. The prefix identifies the owning chapter (section
6 maps prefix to file), so cite the ID when justifying a change and the reader can find the full
rule and its rationale. When a rule in a chapter and a rule here appear to conflict, the chapter is
the detailed statement and wins; sections 1 and 3 govern how to break a genuine tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered,
`references/migration.md` maps every old ID to its new one.

Every fenced example carries a marker on its first line. `# verified` — the block runs as written on
free-threaded CPython 3.15.0, and any test it ships passes. `# fragment` — shown in context rather
than run as a unit, usually because it uses names the chapter declares around it. `# rejected —
<tool>: …` — the rejection is the point, and the marker names the tool that rejects it: `python`,
`ty`, `ruff`. A trailing `— GOOD` or `— BAD` names which side of the rule the block illustrates. A
block in another language carries its marker in that language's comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Python code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in library and high-reliability code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**Code is "library or high-reliability" — `[M!]` applies as `[M]` — if any of these hold:** it is
published to an index or imported by code you do not control; it runs threads, or is imported by
something that does; it is a security boundary (parsers on untrusted input, cryptography, sandboxes,
authentication); or it stores data others cannot reconstruct. **Otherwise** — scripts, notebooks,
internal one-off tooling — `[M!]` rules are recommendations, and the relaxed form given with each
rule is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Python 3.15 reality check

Most Python on the public internet predates these. The entries that **run either way** are the
dangerous ones, because nothing catches them for you.

### 2.1 The changes that produce a wrong answer rather than an error

| Change | What silently differs |
|---|---|
| `contextlib` decorators on a generator | The context now stays open across the whole generator; it used to close when the generator object was created. Every lock, transaction, `chdir` and `contextvars` token held that way changed duration (PS-CONC-22). |
| PEP 686 UTF-8 mode on by default | Moves six surfaces at once: `open()`, the filesystem encoding, `os.fsencode`, `locale.getpreferredencoding()` (now a constant), and `sys.stdin`/`stdout` — which gain `surrogateescape`, turning what used to raise into silent mojibake (PS-OUT-02). |
| `frozendict` is not a `dict` subclass | It inherits from `object`, so `isinstance(x, dict)` is now False for it. The stdlib was updated; third-party code was not. Test `collections.abc.Mapping` (PS-DATA-13). |
| `functools.singledispatchmethod` | Dispatches on the second argument when wrapping a regular method called as a class attribute, so a different registered implementation can be selected. |
| The GIL is gone in `3.15t` | Every read-modify-write on shared state that "worked" now loses updates. See section 2.2. |

### 2.2 Free threading changes a reason, not a list

Cite the *Thread Safety Guarantees* page, not the FAQ's reason that each bytecode instruction is
atomic: that reason was the GIL, under which the never-atomic `obj.n += 1` shipped for years, and on
`3.15t` eight threads running it lose about three quarters of their updates
(`references/concurrency.md` PS-CONC-05).

### 2.3 Spellings that are now wrong

| Stale | Current |
|---|---|
| `from __future__ import annotations` | Nothing. PEP 563 is Superseded; the import now silently degrades `annotationlib` VALUE and FORWARDREF to bare strings |
| `typing.List`, `Optional[X]`, `Union[A, B]` | `list`, `X | None`, `A | B` |
| `T = TypeVar("T")` plus `Generic[T]` | `class Box[T]:` and `def f[T](x: T) -> T:` |
| `Alias: TypeAlias = int | str` | `type Alias = int | str` |
| `TypeGuard` | `TypeIs`, unless the narrowed type is not assignable to the input |
| a hand-rolled `_MISSING = object()` | `sentinel("MISSING")` |
| `types.MappingProxyType` for an immutable mapping | `frozendict` |
| moving an import into a function for startup time | `lazy import x` at module scope |
| `sum(lists, [])` | `[*sub for sub in lists]`, which ruff `RUF017` writes for you |

### 2.4 What the type system gained

| Addition | What it is for |
|---|---|
| `TypeForm[T]` (PEP 747) | A parameter that receives a *type expression* — `int \| None`, `list[int]` — which `type[T]` rejects and `object` erases |
| `TypedDict(closed=True)`, `extra_items=` (PEP 728) | Saying a wire format forbids unknown keys, so a producer's typo is caught rather than silently dropped |
| `@disjoint_base` (PEP 800) | Declaring two bases cannot be combined, so an impossible class is a type error |
| `sentinel()` (PEP 661) | A missing-value marker the type system can name, narrowed by `is`, instead of an `object()` the checker sees as `Any` |
| `frozendict` (PEP 814) | An immutable mapping, in place of `MappingProxyType`, with section 2.1's `isinstance` trap |

Two of these — `extra_items` and `sentinel` in a type expression — are specified but not yet
implemented by every checker. Specified is the bar this standard uses, so it uses them; see
`references/types.md` PS-TYPE-02 for where that boundary is drawn.

## 3. Design principles

Elegance in Python has two axes, and a design needs both. **One obvious way** is PEP 20's claim and
it is a constraint on the *author*: if two spellings of a thing both exist in your codebase, one of
them is a defect, and the cost is paid by every reader who must learn both. **Symmetry** is what
remains after that being *regular*: operations that come in pairs, siblings that take arguments in
the same order, one mechanism per concept, and no branch that exists for a single input.

The two fail differently. Two ways to do one thing makes a codebase larger than it needs to be.
Asymmetry makes it unlearnable — the reader cannot generalise from one function to the next, so
every call site must be read individually. A codebase accretes asymmetry one reasonable-looking
patch at a time, which is why it needs a standing question rather than occasional cleanup.

When two rules appear to conflict and their tiers are equal, break the tie with these five
questions, in order:

1. **What can be deleted?** Fewer parameters, fewer branches, fewer states, fewer dependencies,
   fewer things two threads can both reach.
2. **What can be made unrepresentable?** Push the invariant into the type — a frozen dataclass, a
   `Literal`, an enum, a `NewType` — so the invalid state cannot be constructed rather than being
   rejected at runtime.
3. **What can be made a value instead of an effect?** Prefer a function returning data over one
   mutating state, and an immutable message over a shared object.
4. **What is asymmetric?** If `from_x` exists, does `to_x`? Do sibling functions take their
   arguments in the same order? Does every `__enter__` have its `__exit__`? A missing half is either
   a restriction the docstring must state, or an oversight.
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general case, or give it its own type.

Readability outranks all five. A comprehension that requires the reader to track three
transformations is worse than the loop it replaced, and a symmetry nobody can see is not worth the
name it costs.

## 4. Core rules

These 26 `PS-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### Names and shape

- **PS-CORE-01 `[M]`** Apply PEP 8's casing mechanically, and let `ruff format` settle everything it
  can. Formatting is a command, not a matter of individual discipline.
  (`references/naming.md` PS-NAME-01, PS-NAME-13).
- **PS-CORE-02 `[M]`** Put units and qualifiers last — `latency_ms_max`, not `max_latency_ms` — so
  alphabetical order becomes a semantic grouping and a missing member of a family is visible.
  (`references/naming.md` PS-NAME-05).
- **PS-CORE-03 `[M]`** Reject at the top with a guard, then proceed unindented. The body should
  describe only the case that survived. (`references/errors.md` PS-ERR-16).
- **PS-CORE-04 `[M]`** Say why, not what. Code records what it does; a comment exists for the
  reasoning, the alternative rejected, and the constraint that is not visible locally.
  (`references/naming.md` PS-NAME-16).

### Types

- **PS-CORE-05 `[M]`** Run `ty` at the pinned version with the shipped configuration. An annotation
  nothing checks is a comment with syntax. (`references/types.md` PS-TYPE-01).
- **PS-CORE-06 `[M]`** Never write `from __future__ import annotations`. PEP 563 is Superseded, and
  the import silently degrades `annotationlib` to bare strings. (`references/types.md` PS-TYPE-04).
- **PS-CORE-07 `[M]`** Write `X | None`, `list[int]`, `class Box[T]`, `type Alias = ...`. The
  `typing` aliases, `Optional`, and module-level `TypeVar` are all superseded spellings.
  (`references/types.md` PS-TYPE-07, PS-TYPE-08, PS-TYPE-09).
- **PS-CORE-08 `[M]`** Use `object` for "anything" and `Any` only with a comment naming what cannot
  be expressed. They look alike and are opposites. (`references/types.md` PS-TYPE-13).
- **PS-CORE-09 `[M]`** Narrow with `TypeIs`, not `TypeGuard`: `TypeGuard` leaves the `else` branch
  un-narrowed, which is not what anyone expects. (`references/types.md` PS-TYPE-14).

### Data

- **PS-CORE-10 `[M]`** Model a record as `@dataclass(frozen=True, slots=True)` by default, and reach
  for a mutable one only when you can say what it buys.
  (`references/data.md` PS-DATA-01, PS-DATA-02).
- **PS-CORE-11 `[M]`** Never give a mutable or computed default. The default is evaluated once and
  shared by every caller — and, under free threading, by every thread.
  (`references/data.md` PS-DATA-08, PS-DATA-09).
- **PS-CORE-12 `[M!]`** Make the invalid state unrepresentable before validating against it. A type
  is a check performed everywhere for free; validation is one that can be forgotten at any call
  site. *Relaxed form:* application code at a boundary may validate a primitive, provided it does so
  exactly once. (`references/data.md` PS-DATA-15).

### Errors

- **PS-CORE-13 `[M]`** Never swallow an exception and never catch what you cannot handle. Converting
  a loud failure into a quiet wrong answer is the most expensive thing in this standard.
  (`references/errors.md` PS-ERR-08, PS-ERR-09).
- **PS-CORE-14 `[M]`** Never `return`, `break` or `continue` inside `finally` — it discards the
  in-flight exception silently. PEP 765 makes it a `SyntaxWarning`.
  (`references/errors.md` PS-ERR-13).
- **PS-CORE-15 `[M]`** Never use `assert` to validate input: `python -O` removes it, so the
  validation disappears in exactly the deployment that needed it.
  (`references/errors.md` PS-ERR-07).
- **PS-CORE-16 `[M]`** Catch an `ExceptionGroup` with `except*`. A plain `except ValueError` never
  matches one, so the handler you wrote is silently never entered.
  (`references/errors.md` PS-ERR-11).

### Concurrency

- **PS-CORE-17 `[M]`** No compound assignment on state two threads can reach. `counter += 1` is a
  read, a computation and a write. (`references/concurrency.md` PS-CONC-02).
- **PS-CORE-18 `[M]`** No check-then-act on shared state. Both halves being individually atomic does
  not make the pair one step. (`references/concurrency.md` PS-CONC-03).
- **PS-CORE-19 `[M]`** Never share one iterator or generator across threads. A generator raises;
  any other iterator may silently duplicate or drop elements.
  (`references/concurrency.md` PS-CONC-12).
- **PS-CORE-20 `[M]`** A cache is coherent, not single-flight — `lru_cache` and `cached_property`
  both run the body more than once under contention.
  (`references/concurrency.md` PS-CONC-15, PS-CONC-16).
- **PS-CORE-21 `[M]`** Never share a `TextIOWrapper` across threads, `print` and the standard
  streams included. (`references/concurrency.md` PS-CONC-20).
- **PS-CORE-22 `[M]`** Start every task inside a `TaskGroup`, give every wait a timeout, and never
  swallow `CancelledError`. (`references/async.md` PS-ASYNC-03, PS-ASYNC-05, PS-ASYNC-08).

### Boundaries

- **PS-CORE-23 `[M]`** Annotate every parameter and return of a public function, and re-export
  explicitly — the typing spec makes imported symbols private by default, so a bare import in
  `__init__.py` is not public. (`references/api.md` PS-API-02, PS-API-06).
- **PS-CORE-24 `[M]`** Pass `encoding=` explicitly to every text open. 3.15 moved the default, and
  it moved six surfaces rather than one. (`references/output.md` PS-OUT-01, PS-OUT-02).
- **PS-CORE-25 `[M]`** Log with `%`-style arguments, never an f-string, and never configure logging
  in a library. (`references/output.md` PS-OUT-11, PS-OUT-13).

### Knowing which interpreter you are on

- **PS-CORE-26 `[M]`** Ask `sys.abi_info.free_threaded` how the interpreter was built and
  `sys._is_gil_enabled()` what it is doing right now. One dependency can turn the second answer
  around at import time, and neither a `cp3XXt` wheel tag nor the `abi3t` stable ABI declares that
  it will not.
  (`references/concurrency.md` PS-CONC-01, `references/build.md` PS-BUILD-19).

## 5. Review checklist

When reviewing or self-reviewing a Python diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **Stale spellings.** Any `from __future__ import annotations`, `typing.List`, `Optional[X]`,
   `TypeVar` where PEP 695 syntax fits, or `TypeGuard` where `TypeIs` does?
2. **Shared state.** Every name a thread target touches that is not a parameter or a local: who else
   writes it, and what holds them apart?
3. **Compound operations.** Every `+=`, every check-then-act, every "read it then use it".
4. **Iterators.** Any iterator, generator, or `tee` branch reachable from two threads?
5. **Things that look safe.** Any `lru_cache` or `cached_property` whose body does I/O, any `open()`
   without an explicit `encoding=`, any `ContextVar` read where it was never set?
6. **Hold times.** Any `contextmanager` used as a decorator on a generator function, or a lock held
   across a call you do not control?
7. **The public surface.** What is newly public — annotated, its ownership documented, `py.typed`
   shipped?
8. **Function bodies.** A loop that is a comprehension, a `try` wider than the statement that
   raises, a mutable default?
9. **Tests.** Does the change ship the test that would have caught the bug, and does a concurrency
   test assert an invariant rather than merely run threads?
10. **The build.** Are the tools pinned exactly, and does CI assert the GIL is actually off?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 26
`PS-CORE-*` rules live in section 4 above; the other 236 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `PS-NAME` (21) | Casing and word choice, module and package names, import grouping, what `ruff format` settles, comment discipline, and the symmetry of names |
| `references/types.md` | `PS-TYPE` (20) | The mandated checker, lazy annotations and `annotationlib`, modern spellings, narrowing and precision, and what 3.15 adds |
| `references/data.md` | `PS-DATA` (18) | Choosing between dataclass, enum, protocol and TypedDict, fields and defaults, immutability, validity, and the symmetry of a data type |
| `references/errors.md` | `PS-ERR` (20) | Designing an exception hierarchy, raising and catching, `except*`, `finally` after PEP 765, and the control-flow shapes that keep a function readable |
| `references/concurrency.md` | `PS-CONC` (23) | What the GIL guaranteed and no longer does, sharing objects between threads, iterators and generators, caches and context, streams and hold times |
| `references/async.md` | `PS-ASYNC` (18) | Entering and leaving a loop, owning tasks with `TaskGroup`, cancellation and timeouts, not blocking the loop, and the thread boundary |
| `references/output.md` | `PS-OUT` (18) | Encoding after PEP 686, interpolation and template strings, logging discipline, and the difference between program output and diagnostics |
| `references/performance.md` | `PS-PERF` (17) | Measuring with the 3.15 profiling package, complexity before constants, allocation, and what the free-threaded build costs |
| `references/api.md` | `PS-API` (18) | Declaring the public surface, re-export and `py.typed`, signature and default discipline, module shape, and evolving without breaking |
| `references/documentation.md` | `PS-DOC` (12) | Docstring shape and content, choosing a convention and what that choice disables, doctests, and the documents outside the code |
| `references/testing.md` | `PS-TEST` (21) | pytest 9 configuration and its discovery trap, what a test should assert, parametrisation and subtests, fixtures, and testing concurrency |
| `references/build.md` | `PS-BUILD` (21) | Metadata against the living specs, dependency groups and pinning, locking, Trusted Publishing, and what the free-threaded build demands of a dependency tree |
| `references/migration.md` | `PS-MIG` (9) | The four tiers of obsolescence, what 3.14 and 3.15 removed and changed, what to write today for 3.16, and pytest's own ladder |
| `references/review-checklist.md` | — | The audit protocol: eight-level severity model, review order, the mechanical pass, and the output format |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/ruff.toml` | The lint configuration: `py315` with stable rules only, the fifteen formatter-conflicting rules disabled, `convention = "google"` so `D417` survives, and the `flake8-type-checking` exemptions that keep PEP 649 annotations resolvable at runtime |
| `assets/ty.toml` | The type-checker configuration: every ignore-by-default rule named one at a time rather than promoted wholesale — enabled, or left off with the reason — the strict analysis options, and `concise` output |
| `assets/pyproject.toml` | Project metadata: PEP 639 SPDX license, PEP 735 dependency groups with every tool pinned exactly, PEP 753 URL labels, and pytest 9's native `[tool.pytest]` table |
| `assets/ci.yml` | The workflow: pinned `uv`, the free-threaded interpreter installed as its own build, lint and type gates, and the assertion that the GIL is genuinely off at runtime |
