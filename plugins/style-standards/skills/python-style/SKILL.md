---
name: python-style
description: >-
  Use when writing, reviewing, refactoring, scaffolding or debugging any Python, moving it to the
  free-threaded build, or checking whether a standard-library spelling is still current, even when
  no one asks for "style", "idiomatic" or "modern" code. Applies to a package, a module, a script, a
  test suite, a dataclass, a thread pool, `pyproject.toml`, `ruff.toml`, `ty.toml` and a CI
  workflow. Targets Python 3.15.
---

# Python Style — 3.15

A single standard formed from three sources: the **normative Python specifications** (PEP 8, PEP
257, PEP 20, and the Python Typing Spec, cited from the living specs rather than from the PEPs,
which now redirect to them), the **empirical conventions of the CPython 3.15 standard library**, and
**Ruff's rule catalogue** as the house standard. Where they disagree, this standard picks a side and
says why.

**Target: CPython 3.15, free-threaded.** Nothing below 3.15 is supported and no compatibility shim
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

Rules are cited by ID: `PS-`, then the family of the chapter that owns the rule, then its number.
Section 6 maps each family to its chapter, so cite the ID when justifying a change and the reader
can find the full rule and its rationale. When two rules appear to conflict, sections 1 and 3 govern
how to break the tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered, the migration
chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `# verified` — the block runs as written on
free-threaded CPython 3.15.2, and any test it ships passes. `# fragment` — shown in context rather
than run as a unit, usually because it uses names the chapter declares around it.
`# rejected — <tool>: …` — the rejection is the point, and the marker names the tool that rejects
it: `python`, `ty`, `ruff`. A trailing `— GOOD` or `— BAD` names which side of the rule the block
illustrates. A block in another language carries its marker in that language's comment syntax.

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

### 2.1 Compiles, and behaves differently

| Old | Python 3.15 | Rule |
|---|---|---|
| `contextlib.contextmanager` | a decorator built from one, on a generator function, holds until the generator is exhausted | PS-CONC-21 |
| `functools.singledispatchmethod` | called through its class, dispatches on the argument after the instance | PS-TYPE-17 |
| `isinstance(x, dict)` | `False` for a `frozendict`; `isinstance(x, collections.abc.Mapping)` | PS-DATA-13 |
| `locale.getpreferredencoding` | `'utf-8'` under UTF-8 mode, whatever the locale; `locale.getencoding()` | PS-OUT-03 |
| `open(path)` | UTF-8 whatever the locale, while UTF-8 mode is on | PS-OUT-02 |
| `sys.getfilesystemencoding` | `'utf-8'` under UTF-8 mode, so argv, environment variables and filenames decode as UTF-8 whatever the locale | PS-OUT-02 |
| `sys.stdout` | writes with the `surrogateescape` error handler under UTF-8 mode, as `sys.stdin` reads, where an unencodable character raised | PS-OUT-02 |

A `changed` row of an earlier release is in the migration table, `PS-MIG` in section 6, with its
Since; its owning rule's Check finds it.

### 2.2 No longer compiles

| Old | Python 3.15 | Rule |
|---|---|---|
| `__cached__` | `__spec__.cached`; a module's `__cached__` is no longer set or read | PS-MIG-03 |
| `ctypes.SetPointerType` | nothing; it was undocumented | PS-MIG-03 |
| `glob.glob0` | `glob.glob()` with `root_dir=` | PS-MIG-03 |
| `glob.glob1` | `glob.glob()` with `root_dir=` | PS-MIG-03 |
| `http.server.CGIHTTPRequestHandler` | nothing | PS-MIG-03 |
| `python -m http.server --cgi` | nothing | PS-MIG-03 |
| `importlib.abc.Loader.load_module` | `exec_module()`; the import system no longer calls it | PS-MIG-03 |
| `pathlib.PurePath.is_reserved` | `os.path.isreserved()` | PS-MIG-03 |
| `platform.java_ver` | nothing | PS-MIG-03 |
| `sre_compile` | `re` | PS-MIG-03 |
| `sre_constants` | `re` | PS-MIG-03 |
| `sre_parse` | `re` | PS-MIG-03 |
| `types.CodeType.co_lnotab` | `co_lines()` | PS-MIG-03 |
| `typing.no_type_check_decorator` | nothing | PS-TYPE-11 |
| `wave.Wave_read.getmark` | nothing | PS-MIG-03 |
| `wave.Wave_read.getmarkers` | nothing | PS-MIG-03 |
| `wave.Wave_write.getmark` | nothing | PS-MIG-03 |
| `wave.Wave_write.getmarkers` | nothing | PS-MIG-03 |
| `wave.Wave_write.setmark` | nothing | PS-MIG-03 |
| `zipimport.zipimporter.load_module` | `exec_module()` | PS-MIG-03 |
| `PyImport_ImportModuleNoBlock` | `PyImport_ImportModule` | PS-MIG-03 |
| `PySys_ResetWarnOptions` | nothing | PS-MIG-03 |
| `PyUnicode_AsDecodedObject` | `PyCodec_Decode` | PS-MIG-03 |
| `PyUnicode_AsDecodedUnicode` | `PyCodec_Decode` | PS-MIG-03 |
| `PyUnicode_AsEncodedObject` | `PyCodec_Encode` | PS-MIG-03 |
| `PyUnicode_AsEncodedUnicode` | `PyCodec_Encode` | PS-MIG-03 |
| `PyWeakref_GET_OBJECT` | `PyWeakref_GetRef` | PS-MIG-03 |
| `PyWeakref_GetObject` | `PyWeakref_GetRef` | PS-MIG-03 |
| `Py_GetExecPrefix` | `PyConfig_Get()` | PS-MIG-03 |
| `Py_GetPath` | `PyConfig_Get()` | PS-MIG-03 |
| `Py_GetPrefix` | `PyConfig_Get()` | PS-MIG-03 |
| `Py_GetProgramFullPath` | `PyConfig_Get()` | PS-MIG-03 |
| `Py_GetProgramName` | `PyConfig_Get()` | PS-MIG-03 |
| `Py_GetPythonHome` | `PyConfig_Get()` | PS-MIG-03 |
| `ast.<Node>(…)` | raises `TypeError` for a field missing or a keyword no field has; give each of the node's `_fields`, and only those | PS-MIG-04 |
| `datetime.strptime(…, "%d/%m")` | raises `ValueError` for a day with no year; give the format a year directive | PS-MIG-04 |
| `importlib.resources.files(package=…)` | raises `TypeError`; pass the package positionally | PS-MIG-04 |
| `sysconfig.is_python_build(check_home=…)` | raises `TypeError`; call it with no argument | PS-MIG-04 |
| `threading.RLock(…)` | raises `TypeError` given any argument; `threading.RLock()`, which never used them | PS-MIG-04 |
| `typing.NamedTuple(…, x=…)` | raises `TypeError` for a field given as a keyword; `class P(NamedTuple)` | PS-MIG-04 |
| `typing.TypedDict("…")` | raises `TypeError` given a name and no fields; `class TD(TypedDict)` | PS-MIG-04 |

A `gone` row of an earlier release is in the migration table, `PS-MIG` in section 6, with its Since;
the `rg` command after that table finds every `gone` and `alias` spelling the code writes out but a
shape, whatever its release, and the type checker every `gone` member the code reaches through a
value.

### 2.3 What Python 3.15 gained

- `frozendict` (PEP 814), an immutable mapping, in place of `types.MappingProxyType`, which was only
  a view (PS-DATA-13).
- `sentinel()` (PEP 661), a missing-value marker the type system can name, in place of `object()`
  (PS-TYPE-20).
- `TypeForm[T]` (PEP 747), for a parameter that receives a type expression, which `type[T]` rejects
  (PS-TYPE-18).
- `TypedDict(closed=True)` and `extra_items=` (PEP 728), for a wire format that forbids or
  constrains unknown keys; specified, which is the bar this standard uses (PS-TYPE-19, PS-TYPE-02).
- `@disjoint_base` (PEP 800), declaring that two bases cannot be combined (PS-TYPE-15).
- `lazy import` (PEP 810), in place of an import moved into a function for startup time (PS-MOD-08).
- Unpacking in a comprehension (PEP 798), `[*sub for sub in lists]`, in place of `sum(lists, [])`
  (PS-PERF-06).
- `threading.serialize_iterator`, `concurrent_tee` and `synchronized_iterator`, for an iterator
  threads share (PS-CONC-12, PS-CONC-13, PS-CONC-14).
- The `profiling` package (PEP 799): `profiling.tracing` and `profiling.sampling` (PS-PERF-02).
- `TaskGroup.cancel()`, which ends a group without an exception (PS-ASYNC-04).
- `sys.abi_info.free_threaded`, which says how the interpreter was built (PS-CONC-01).

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

- **Naming: Casing, Words, Formatting, and Symmetry**
  - PS-NAME-01 [M] Apply PEP 8's casing rules mechanically
  - PS-NAME-05 [M] Put units and qualifiers last, sorted by descending significance
- **Types: Annotations, Generics, Narrowing, and the Checker**
  - PS-TYPE-01 [M] Run `ty` at the pinned version, with the shipped configuration
  - PS-TYPE-04 [M] Never write `from __future__ import annotations`
  - PS-TYPE-07 [M] Write unions with `|`, and put `None` last
  - PS-TYPE-08 [M] Declare type parameters with PEP 695 syntax
  - PS-TYPE-09 [M] Declare an alias with the `type` statement
  - PS-TYPE-12 [M] Use `object` for "anything", and `Any` only with a reason
  - PS-TYPE-13 [M] Narrow with `TypeIs`, not `TypeGuard`
- **Data: Dataclasses, Enums, Protocols, and Immutability**
  - PS-DATA-01 [M] Model a record as a frozen dataclass by default
  - PS-DATA-02 [M] Add `slots=True` unless something needs the instance dict
  - PS-DATA-08 [M] Never give a mutable default
  - PS-DATA-09 [M] Never compute a default at import time
  - PS-DATA-15 [M] Make the invalid state unrepresentable before validating against it
- **Errors and Control Flow: Exceptions, Guards, and the Shape of a Function**
  - PS-ERR-07 [M] Never use `assert` to validate input
  - PS-ERR-08 [M] Never catch what you cannot handle
  - PS-ERR-09 [M] Never swallow an exception silently
  - PS-ERR-11 [M] Use `except*` for a group, and never mix it with `except`
  - PS-ERR-13 [M] Never `return`, `break` or `continue` inside `finally`
  - PS-ERR-16 [M] Reject at the top with a guard, then proceed unindented
- **Concurrency: Threads Without the GIL, Shared State, Iterators, Caches, and Context**
  - PS-CONC-01 [M] Probe the build with `sys.abi_info` and the runtime with `sys._is_gil_enabled`
  - PS-CONC-02 [M] Never treat a compound assignment as one step
  - PS-CONC-03 [M] Never treat check-then-act as one step
  - PS-CONC-12 [M] Serialise a shared iterator with `threading.serialize_iterator`
  - PS-CONC-15 [M] Never rely on `lru_cache` or `cached_property` to run a body once
  - PS-CONC-19 [M] Write each record to a shared text stream in one call, never with `print`
- **Async: Tasks, Cancellation, Lifecycle, and the Thread Boundary**
  - PS-ASYNC-03 [M] Start every task inside a `TaskGroup`
  - PS-ASYNC-05 [M] Never swallow `CancelledError`
  - PS-ASYNC-08 [M] Give every wait a timeout, with `asyncio.timeout`
- **Output: Encoding, Interpolation, Logging, and Program Output**
  - PS-OUT-01 [M] Pass `encoding=` explicitly to every text open
  - PS-OUT-02 [M] Never assume UTF-8 mode moved only `open`
  - PS-OUT-11 [M] Log with `%`-style arguments, never with an f-string
  - PS-OUT-13 [M] Never configure logging in a library
- **API: The Public Surface, Signatures, and Evolution**
  - PS-API-02 [M] Re-export through `__all__`, never by a bare import
  - PS-API-07 [M] Annotate every parameter and every return of a public function
- **Documentation: Docstrings, Comments in Public Places, and What Ships**
  - PS-DOC-13 [M] Say why, not what
- **Build: Metadata, Dependencies, Locking, Publishing, and the Free-Threaded Wheel**
  - PS-BUILD-19 [M] Run `ruff format`; it is not a suggestion
  - PS-BUILD-21 [M] A free-threaded wheel tag is not a declaration of thread safety

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
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. All
251 rules live here; section 4 lists by ID those that bind on their own.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `PS-NAME` (13) | Casing and word choice, what `ruff format` settles, and the symmetry of names |
| `references/types.md` | `PS-TYPE` (20) | The mandated checker, lazy annotations and `annotationlib`, modern spellings, narrowing and precision, and what 3.15 adds |
| `references/data.md` | `PS-DATA` (17) | Choosing between dataclass, enum, protocol and TypedDict, fields and defaults, immutability, validity, and the symmetry of a data type |
| `references/errors.md` | `PS-ERR` (21) | Designing an exception hierarchy, raising and catching, `except*`, `finally` after PEP 765, and the control-flow shapes that keep a function readable |
| `references/concurrency.md` | `PS-CONC` (22) | What the GIL guaranteed and no longer does, sharing objects between threads, iterators and generators, caches and context, streams and hold times |
| `references/async.md` | `PS-ASYNC` (18) | Entering and leaving a loop, owning tasks with `TaskGroup`, cancellation and timeouts, not blocking the loop, and the thread boundary |
| `references/output.md` | `PS-OUT` (18) | Encoding and UTF-8 mode, interpolation and template strings, logging discipline, and the difference between program output and diagnostics |
| `references/performance.md` | `PS-PERF` (17) | Measuring with the 3.15 profiling package, complexity before constants, allocation, and what the free-threaded build costs |
| `references/api.md` | `PS-API` (19) | Declaring the public surface, re-export and `py.typed`, signature and default discipline, the pairs and siblings a surface keeps alike, and evolving without breaking |
| `references/modules.md` | `PS-MOD` (14) | What a module boundary costs, module and package names, layout under `src/`, what a module does when imported, `lazy import`, the import graph, and the order of a module and a class |
| `references/documentation.md` | `PS-DOC` (14) | Docstring shape and content, choosing a convention and what that choice disables, doctests, the comments that explain the code, and the documents outside it |
| `references/testing.md` | `PS-TEST` (27) | pytest 9 configuration and its discovery trap, what a test should assert, parametrisation and subtests, fixtures, and testing concurrency |
| `references/build.md` | `PS-BUILD` (23) | Metadata against the living specs, dependency groups and pinning, locking, Trusted Publishing, and what the free-threaded build demands of a dependency tree |
| `references/migration.md` | `PS-MIG` (8) | Every old spelling 3.14 and 3.15 removed, changed, aliased or deprecated, with its status and owning rule; the command the table generates; what to write now for 3.16; and pytest's own ladder |
| `references/review-checklist.md` | — | The audit protocol: the shared seven-level severity model, review order, the mechanical pass, and the output format |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/ruff.toml` | The lint configuration: `py315` with stable rules only, every rule on ruff's formatter-conflict list disabled, `convention = "google"` so `D417` survives, and the `flake8-type-checking` exemptions that keep PEP 649 annotations resolvable at runtime |
| `assets/ty.toml` | The type-checker configuration: every ignore-by-default rule named one at a time rather than promoted wholesale — enabled, or left off with the reason — the strict analysis options, and `concise` output |
| `assets/pyproject.toml` | Project metadata: PEP 639 SPDX license, PEP 735 dependency groups with every tool pinned exactly, PEP 753 URL labels, and pytest 9's native `[tool.pytest]` table |
| `assets/ci.yml` | The workflow: pinned `uv`, the free-threaded interpreter installed as its own build, lint and type gates, and the assertion that the GIL is genuinely off at runtime |
