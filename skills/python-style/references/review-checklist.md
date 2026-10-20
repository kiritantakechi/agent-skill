# Review protocol

How to audit existing Python against this standard. Read this before reviewing; read the domain
files as the code demands them.

## Severity model

Report every finding with one of these labels. The label sets the ordering of the review and tells
the author what must change before merge.

| Severity | Meaning | Examples |
|---|---|---|
| **Unsound** | Corrupts memory or data, or crashes the runtime, from code that looks safe | A compound assignment on shared state, check-then-act across a lock boundary, a shared generator, `frame.f_locals` from another thread |
| **Stale** | A spelling the target superseded — fails to build, or worse, builds and means something else | `from __future__ import annotations`, `typing.List`, `Optional[X]`, `TypeGuard` where `TypeIs` fits, `isinstance(x, dict)` against a `frozendict`, a `contextmanager` decorator on a generator, an `open()` without `encoding=`, `singledispatchmethod` dispatch, context inheritance assumed |
| **Incorrect** | Produces wrong results or crashes on reachable input | Off-by-one, a swallowed exception, an unreachable branch |
| **Contract** | Breaks or under-specifies the public surface | An unannotated public function, a mutable default, an implicit re-export, a missing `py.typed` |
| **Design** | Works, but the shape will cost later | Shared mutable state where a message would do, a lock whose invariant cannot be named, one mechanism spelled two ways |
| **Performance** | Measurable, avoidable cost | Per-iteration allocation, a lock on the hot path where a thread-local would serve, an unbuffered write |
| **Style** | Idiom and readability | Naming, import order, docstring shape, anything `ruff format` settles |

Unsound, Stale and Incorrect findings block a merge. Contract findings block a release. Design and
Performance findings need a decision, not necessarily a change. Style findings are batched — do not
spend a review's attention on them while an Unsound or Incorrect finding sits unaddressed.

## Review order

Do not read the diff top to bottom. Read in this order, because a finding at each stage can
invalidate the work of reading the next.

1. **Stale spellings.** Before anything else, because a superseded spelling means the author is
   writing against a language that no longer exists. Run the mechanical pass below.
2. **Shared state.** For every function a thread or executor runs: which names are neither
   parameters nor locals? For each, who else writes it, and what holds them apart? (`PS-CONC`)
3. **Compound operations.** Every `+=`, every check-then-act, every read-then-use on a shared name.
   These are the ones that were merely unlikely under the GIL and are now immediate. (`PS-CONC-02`,
   `PS-CONC-03`)
4. **Iterators.** Any generator, iterator, or `tee` branch reachable from two threads. The generator
   raises; everything else is silent. (`PS-CONC-13` … `PS-CONC-17`)
5. **Things that look safe.** Caches, `cached_property`, `print`, the module-level `random`, and
   every `ContextVar`. Each has a documented caveat that reads like a guarantee. (`PS-CONC-18` …
   `PS-CONC-24`)
6. **Hold times.** Every `contextmanager` used as a decorator, and every lock spanning a call you do
   not control. (`PS-CONC-25`, `PS-CONC-26`)
7. **The public surface.** What is newly public? Is it annotated, is the ownership documented, does
   the package ship `py.typed`?
8. **Function bodies.** Now read the code.
9. **Tests.** Does the change ship the test that would have caught the bug? Does a concurrency test
   assert an invariant, or merely run threads?
10. **The build.** Are the tool versions pinned? Does CI assert the GIL is off rather than hoping?

## Mechanical pass

Run these before reading anything, and report what could not be run rather than implying it passed.

```sh
uv run ruff check                     # the shipped assets/ruff.toml
uv run ruff format --check            # zero stderr proves no formatter conflict
uv run ty check                       # the shipped assets/ty.toml
uv run pytest
python -c "import sys; assert not sys._is_gil_enabled()"
```

Then the greps that no linter carries, because Ruff has no free-threading rule at all:

```sh
grep -rn 'from __future__ import annotations' src/
grep -rnE '^\s*(self\.)?[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?\s*([+*|&^-]|//)=' src/
grep -rn 'f_locals' src/
grep -rn 'itertools.tee' src/
grep -rnB2 '@contextmanager' src/
```

## Output format

One finding per line, severity first, then the location, then what to do:

```
Unsound  worker.py:41   `self.count += 1` is a read-modify-write on state three
                        threads reach. Accumulate locally and merge under the lock
                        that already guards `self.totals` (PS-CONC-04).
```

Group by severity, not by file. Cite the rule ID so the author can read the reason rather than
taking the reviewer's word for it. Where a finding is a judgement rather than a verdict — the greps
above mostly are — say which way you read it and why.

## Refactoring a codebase to this standard

Do it in this order, one mechanical step per commit, so that each commit is reviewable and
revertible:

1. Pin `ruff`, `ty` and `pytest` exactly and ship the two configuration assets. Commit the noise as
   it stands, then fix by ruff linter family, one family per commit.
2. Run CI on the free-threaded interpreter with the GIL assertion, so every later step is tested
   where it will run.
3. Remove the stale spellings. `ruff check --fix --select UP` does most of it, as one commit.
4. Find the shared state, one module per commit: guard it or partition it, each with a test that
   asserts an invariant under contention rather than merely starting threads.
5. Annotate the public surface and ship `py.typed`, then make `ty` a gate.

State up front which of these steps you are doing, and do not mix a behavioural change into any of
them.
