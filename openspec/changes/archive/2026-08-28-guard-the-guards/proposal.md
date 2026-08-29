## Why

This repository holds its rules to a discipline it does not hold its own checks to.

A suppression of a *rule* must justify itself: a `not_decisive` entry carries an anchor quoting the
rule's own Check, and the run fails when that quote goes stale. A `fires` fixture must actually be
matched, and the run fails when it stops being. Both are guarded.

A suppression of a *check* is a set literal:

```python
def test_every_check_has_a_control():
    """A check nothing can break is a check nothing verifies."""
    ...  if c.name not in {"controls", "toolchain", "mutation"}
```

Three checks exempted from the very property the docstring names, with no reason recorded and
nothing to notice if the reason stops holding.

The same shape appears in the coverage lists. `test_unrun` exists to prove that a missing tool
withholds the pass — its own message says *"a NOTE here lets the run report success while nothing
looked"* — and it covers **3 of the 7 checks that depend on an external tool**. The three it misses
(`crossref`, `self-application`, `sensitivity`) all became tool-dependent in the last two changes,
and nothing detected the gap. `pins` is listed as needing `uv` alone, though it now also runs `ruff`,
`ty`, `pytest` and `rg`.

## What Changes

- **A coverage list is derived, not maintained.** `test_unrun` computes which checks depend on a
  tool from the checks themselves; `CROSS_SKILL` in `controls.py` stops being a hand-written set. A
  check that gains a tool dependency is covered the moment it gains it.
- **An exemption carries a reason, and the reason is checked.** The control exemption becomes a
  mapping from check name to why it has no control, the way `not_decisive` maps a rule to why its
  pattern cannot decide. An exemption naming a check that no longer exists is a finding.
- **Two dead members are deleted.** `Span.lines()` has no callers. `Corpus.excluded` is computed and
  never read — and it was already dead before the split that moved it, which is the more useful
  fact: a refactor whose stated goal was separating concerns carried it across without looking at it.
- **`cli.py` stops special-casing one check by name.** `c.run(skills, **({"fast": ...} if c.name ==
  "controls" else {}))` hardcodes which check takes an extra argument; the check declares it instead.
- **The four modules extracted last change get unit tests.** `corpus.origin`'s bisect arithmetic,
  `search.find`'s span computation, `search.matches`, and `dialect.outside_brackets`'s bracket
  scanner are exercised only end-to-end today. The bracket scanner was written from scratch last
  change and is touched by exactly one negative control.

## Capabilities

### New Capabilities

- `harness-integrity`: the discipline the harness applies to itself — that a suppression of a check
  justifies itself the way a suppression of a rule does, and that a list of what must be verified is
  derived from the thing it verifies rather than maintained beside it.

### Modified Capabilities

None. The behaviour of individual checks does not change; what changes is whether the machinery
around them can silently stop being true.

## Impact

| File | What |
|---|---|
| `tests/test_unrun.py` | hand-written 3-entry list → derived from the checks |
| `tests/test_controls.py` | bare exemption set → reasons, checked for staleness |
| `checks/controls.py` | `CROSS_SKILL` derived or declared per check |
| `checks/search.py` | `Span.lines()` deleted |
| `checks/corpus.py` | `Corpus.excluded` deleted |
| `cli.py` | the `if c.name == "controls"` special case |
| `tests/` | new unit tests for `corpus`, `search`, `dialect` |

**Risk** — deriving a coverage list can derive the wrong one, and a test that computes its own
expectations can compute an empty one and pass. Every derivation here needs a floor: the derived set
must be non-empty and must contain the checks known to depend on a tool today.
