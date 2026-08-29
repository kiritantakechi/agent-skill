## Context

See `proposal.md` — Why. The audit's measurements, since the decisions rest on them:

**Seven checks depend on an external tool. `test_unrun` covers three.**

| check | needs | covered |
|---|---|---|
| `assets` | `zig`, `uv` | ✓ |
| `citations` | `ruff`, `ty` | ✓ |
| `pins` | `uv` — and now `ruff`, `ty`, `pytest`, `rg` | partly |
| `crossref` | `rg` | ✗ |
| `self-application` | `rg` | ✗ |
| `sensitivity` | `rg` | ✗ |
| `search` (shared) | `rg` | n/a |

The three uncovered ones became tool-dependent in `migrate-checks-to-ripgrep` and
`harden-checks-and-pins`. Neither change noticed, because nothing was watching.

**Three hand-maintained lists, none guarded:**

```
tests/test_controls.py:38   {"controls", "toolchain", "mutation"}      no reasons
tests/test_unrun.py:24      [("assets", …), ("citations", …), …]      3 of 7
checks/controls.py:39       CROSS_SKILL = {"crossref", "mirror"}       no completeness guard
```

**Two dead members:** `Span.lines()` has zero callers and was written in the last change.
`Corpus.excluded` is assigned and never read, and `git show HEAD` confirms it was already dead
before the split that carried it into a new module.

## Goals / Non-Goals

**Goals**

- A guarantee about checks covers a new check without anyone remembering to add it.
- An exemption from a guarantee reads like a `not_decisive` entry: named, reasoned, and reported
  when it goes stale.
- The modules extracted last change are tested where their logic actually lives.

**Non-Goals**

- Changing what any check decides. This is about the machinery around the checks.
- Giving `toolchain` and `mutation` negative controls. Whether they should have them is a question
  this change surfaces by demanding a reason; answering it is separate work.
- Auditing the skills' rule text. Nothing here touches a standard.

## Decisions

### 1. Derive the tool-coverage list from the checks, with a floor

`test_unrun` should ask each check what it needs rather than being told. Two candidate derivations:

| approach | catches a new dependency | risk |
|---|---|---|
| grep each check module for `have("x")` / `tool_path("x")` / `searcher_problem()` | yes | brittle to spelling; a helper indirection hides it |
| a declared `needs: tuple[str, ...]` on `Check` | yes, if declared | someone forgets to declare |

Neither is sufficient alone: the first misses an indirection, the second misses a forgetting. The
first task of this change demonstrated the first failure immediately — inspection reports `pins` as
needing `uv`, because `_tool_pins` iterates `for tool in TOOLS: if not have(tool)`. A variable, not a
literal. `pins` in fact needs `ruff`, `ty`, `pytest` and `rg` as well, and measuring it confirmed
that removing `rg` makes `pins` withhold the pass.

**A floor built from that inspection would have been wrong in the same direction as the list it
replaced**, which is why the decision as first written does not hold: it would have frozen the
under-report rather than caught it.

So both, cross-checked: each check **declares** what it needs, and inspection **derives** what it can
see. A tool found by inspection and absent from the declaration is a failure — someone forgot. A
declaration is what the guarantee runs over, so an indirection inspection cannot see is still
covered. Two declarations compared, which is the same shape `pins` already uses for the interpreter
against `assets/ci.yml`, and for the shipped asset against the harness pin.

This is the same reasoning that made the equivalence harness in `migrate-checks-to-ripgrep`
worthless: a test that computes its own expectations can compute an empty one and pass. There, the
lesson arrived after the harness was built and trusted. Here it is a precondition.

### 2. An exemption becomes a mapping, and stale entries fail

`{"controls", "toolchain", "mutation"}` becomes `{check: reason}`, and a name that no longer resolves
to a check is a failure — exactly what `not_decisive` already does for rules and `fires` does for
fixtures. Writing the reasons is where the value is: `controls` is genuinely self-referential, and
whether `toolchain` and `mutation` are exempt because they are slow or because nobody got to them is
a question nobody can currently answer from the code.

The reasons are not invented here. Where the reason is not knowable from the code, the entry says so,
which is more honest than a plausible-sounding sentence and leaves the question visible.

### 3. `CROSS_SKILL` moves onto the check

A control's run is scoped to the skill it injected into, except for checks that read one skill
against another. That exception is currently a set of two names in `controls.py`, and a new
cross-skill check would be silently under-tested: scoped to one skill, still passing if it happens to
fire anyway.

The check knows whether it is cross-skill; `Check` already carries `scope`. Reading the distinction
from the check removes the list rather than guarding it, which is strictly better than a guarded list.

### 4. Delete rather than justify the two dead members

`Span.lines()` and `Corpus.excluded` are deleted. `Corpus.excluded` is the one worth recording: the
split that moved it was justified in its own design as separating concerns by who needs what, and it
carried across a field nobody needs at all. A restructuring that relocates without examining has
changed where the code is and not what it is — which is why the requirement is written as *removed,
not carried*.

### 5. Unit tests go where the arithmetic is, not where the check is

The four modules are exercised end-to-end by `test_checks.py` and by negative controls, which proves
the pipeline and not the pieces. The pieces with real logic:

- `corpus.origin` — `bisect` into a starts array, then two offset subtractions. Off-by-one country.
- `search.find` — computes a span's end by counting newlines in the matched text, with a branch for
  text that does not end in one.
- `search.matches` — the True / False / **None** contract, where `None` means the search could not
  answer and must not be read as "no".
- `dialect.outside_brackets` — a hand-written bracket scanner with POSIX class handling, written
  from scratch last change, touched by exactly one negative control.

The last is the most exposed: it decides whether a `\|` is an operator or a literal, and getting it
wrong in the permissive direction means the `dialect` check stops reporting the defect it exists for.

### 6. What the cross-check found, and what it cost

| | before | after |
|---|---:|---:|
| checks the `UNRUN` guarantee covers | 3 | **6** |
| tool removals asserted | 5 | **12** |
| hand-maintained lists | 3 | **0** |
| unit tests over the extracted modules | 0 | **31** |
| total tests | 120 | **157** |
| `--fast` | 22.6s | 22.3s |
| `controls` | 14.9s | **12.3s** |

**The declaration found four things inspection could not.** `pins` declares `uv`, `ruff`, `ty`,
`pytest` and `rg`; reading its source finds only `uv`, because `_tool_pins` asks `have(tool)` in a
loop. Measuring confirmed the declaration rather than the inspection: removing `rg` makes `pins`
withhold the pass.

**Inspection found nothing the declaration had missed** — today. That is not evidence it is
redundant; it is the state the cross-check exists to preserve. It fires the first time someone adds
a `have("x")` without saying so, which was verified by removing `ty` from `citations`' declaration
and watching it fail.

`CROSS_SKILL` was removed rather than guarded: `scope == "all"` already separates the checks that
read one skill against another from those that do not, exactly. Deleting a list beats guarding one,
and the deletion took `controls` from 14.9s to 12.3s.

**Every new test was shown to fail when its subject breaks.** Four subjects, broken one at a time:
`origin`'s bisect offset (3 failures), `find`'s span end (1), `matches` reading unanswerable as
`False` (2), `outside_brackets` no longer skipping bracket expressions (3). Passing is not the same
as testing, and the difference is the only thing this change is about.

## Risks / Trade-offs

- **A derived list derives the wrong set** → the floor in Decision 1; the derivation may grow but
  never shrink below the seven known today.
- **The reasons written in Decision 2 are guesses dressed as facts** → where the reason is not
  knowable from the code, the entry says that rather than inventing one.
- **Removing `CROSS_SKILL` changes control scoping** → every control must still fire afterwards,
  which `controls` already asserts; a scoping mistake fails loudly rather than silently.
- **Unit tests written against the current behaviour freeze bugs as expectations** → the four
  subjects have properties that can be stated independently of the implementation: a span of one
  line, an origin that round-trips, `None` distinct from `False`, a `\|` inside a bracket expression
  that is not an operator.
