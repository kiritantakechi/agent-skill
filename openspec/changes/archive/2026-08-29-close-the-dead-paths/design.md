## Context

See `proposal.md` — Why. Three points of current state the approach turns on:

1. **`crossref` reaches its verdict by four independent branches** over the same input: citations into
   another standard, override-table rows, the anchor-pattern sweep, and the apparatus check. Its one
   control injects a defect that trips two of them. That is why a dead branch went unnoticed.
2. **`_render` already prints the live hit count.** A tier-2 note reads
   `BV-ECS-12 -E /Vec<Entity>/ — 4 hit(s) — <title>  (measured: … hit 4 compliant examples)`. The
   number appears twice: once measured now, once frozen in a string.
3. **`fires` is `dict[str, str]`** — one fixture per rule — which is why `sensitivity` could only ever
   ask `any`. The data shape, not the predicate, is what limits it.

Measured before choosing an approach: with `_anchor_patterns` de-indented, the current tree produces
**0** anchor findings. Restoring the branch does not surface a backlog, so this change is not also a
`bevy-style` content change.

## Goals / Non-Goals

**Goals**

- Every branch of every check is reachable, and has a control that fails when it stops being.
- Where a search can fail to answer, no consumer reads that as a clean result.
- What the standard prints is what the pinned tool accepts.

**Non-Goals**

- **Making a wheel install fully functional.** The pin is not shipped as package data. A distribution
  install degrades to *cannot confirm which version ran*, which is the honest answer; making it
  *confirm* would mean shipping build configuration into the runtime package. Decided by the user.
- **A general unreachable-code check.** Ruff has no such rule at the selected set, and adding a
  bespoke one for a defect that the control discipline should catch is fixing the symptom at the
  wrong altitude. The control is the fix.
- **Re-auditing the 133 pre-existing command patterns for fixtures.** Tightening `sensitivity` applies
  to rules that already declare a fixture; extending coverage to every accusing pattern in the library
  remains recorded debt.

## Decisions

### Decision 0 — a control is accepted only after it fails on the reverted code

Every control this change writes or rewrites is run twice: against the fixed code, where it must
pass, and against the code with the branch it names disabled, where it must fail. The second run is
the entire point — the existing `crossref` control passes the first and would have passed the second,
which is how it certified an unreachable loop.

*Alternative considered:* read the control and satisfy oneself that it reaches the branch. Rejected on
evidence: that is what was done, and the loop was unreachable for the reading's whole lifetime. A
control's correctness is a claim about execution, so it is settled by executing.

### Decision 1 — the replacement `crossref` control injects into an example, not into `SKILL.md`

The anchor branch fires when an anchor standard's decisive pattern hits the delta's examples **and**
the delta's `SKILL.md` never names that rule. The current control gets there by renaming `RS-API-26`
to `RS-API-99` in an override row — which also makes `RS-API-99` an uncited id, tripping the citation
branch, which is the branch that actually reported.

So the injection moves to the examples: add to a `bevy-style` example a construct some `rust-style`
`[M]` rule's command pattern catches, where that rule is not named anywhere in `bevy-style/SKILL.md`.
`SKILL.md` is untouched, so no citation or override branch can report, and the control fails if and
only if the anchor sweep stops running.

*Alternative considered:* delete a rule id from the prose in `SKILL.md` that explains why a rule is
*not* on the override table. Also isolates the branch, and is a smaller edit. Rejected as second
choice because it tests the `named` set rather than the sweep — a control that stops at "the id went
missing" would still pass if the pattern execution beneath it were removed.

### Decision 2 — `dialect` owns the raw newline; extraction stays permissive

`patterns_of` could reject a pattern containing a newline at extraction. It will not.

`dialect` is defined as *"a pattern carrying syntax from a grammar it will not be read in"*, and a raw
newline is exactly that: `rg` rejects it under the invocation the standard prints and accepts it under
the invocation the harness adds. Reporting it there gives the reader a rule id, a pattern, and a
sentence about why the printed command fails — and `dialect` already carries a negative control, so
the new case inherits the discipline rather than needing its own apparatus.

Rejecting at extraction would fail earlier and say less: the pattern would simply vanish from the
corpus sweep, and the message would name a stage of the harness rather than the rule that is wrong.

*Consequence:* the two wrapped Checks (`PS-FMT-07`, `PS-MIG-05`) must be unwrapped in the same change,
or `dialect` fails on the tree it ships with.

### Decision 3 — `fires` becomes rule id → several fixtures, matched as a bipartite cover

`fires: dict[str, tuple[str, ...]]`. For each rule that declares fixtures:

- **every command pattern** in its Check matches at least one fixture — otherwise that pattern has
  never been shown to catch anything;
- **every fixture** is matched by at least one pattern — otherwise it is an orphan, the same defect
  shape as an exemption naming a rule that no longer exists.

Both directions, because each catches what the other cannot. The first is the requirement the user
asked for. The second is what keeps the first honest: without it, narrowing a pattern until it stops
matching can be "fixed" by adding a fixture that nothing checks the relevance of.

*Alternatives considered:*

| Shape | Why not |
|---|---|
| `dict[str, dict[str, str]]` keyed by pattern text | Explicit, and mirrors `NotDecisive.anchor` — but a pattern is a long escaped string, and duplicating it into the profile means two spellings that must agree. The anchor discipline exists because an anchor is a *short quoted fragment*; a full pattern is not. |
| `tuple[str, ...]` positional against `patterns_of` order | Order is an artefact of how the Check happens to be written. Reordering two alternations in a Check would silently reassign every fixture. |
| One fixture that all patterns must match | Impossible in general: `ZS-MIG-13`'s four patterns cover four disjoint dead-API families, and no single snippet exhibits all four. |

*Measured cost, taken before the shape was chosen:* ten rules declare fixtures, covering **13** command
patterns, of which **3** are unproven under the every-pattern rule — all three in `ZS-MIG-13`, which is
the only declared rule carrying more than one pattern. The other nine convert mechanically.

| | |
|---|---|
| `pipeToFileSystem\|PipeOptions\|std\.rand\.\|CrossTarget\|StackIterator` | unproven |
| `captureStackTrace\|dumpStackTraceFromBase\|walkStackWindows` | unproven |
| `wtf8Decode\b\|utf8Decode\b\|std\.debug\.runtime_safety` | unproven |

Each is a disjoint family of dead 0.13→0.16 APIs, which is why one fixture was never going to cover
them and why `any` hid it.

### Decision 4 — an unreadable pin declaration reuses the unfindable-pin path

`pinned_version` catches `OSError` and returns `None`, which `version_mismatch` already turns into
*"`{tool}` decides whether checks fire but `pyproject.toml` pins no version for it"* — reworded to
distinguish *no pin in the file* from *no file*. Both callers already handle a complaint: `pins`
yields it as `FAIL`, `searcher_problem` as `UNRUN`. Neither needs to change.

The level therefore depends on who asked, which is correct: a repository verifying its own pins has a
failure; a run that merely cannot confirm which `rg` executed has withheld a pass. Encoding one level
at the source would have been wrong for one of them.

### Decision 5 — the frozen hit counts are deleted, not derived

`_render` already prints `— {len(hits)} hit(s) —` for the same pattern, in the same line, two fields
before the reason. Deriving the count into the reason would print it twice; keeping it frozen prints a
current number and a stale one side by side and invites the reader to believe the stale one.

So the reasons lose the number and keep what only a person could have written — what the pattern finds
and what decides. `patterns.py` already states the rule these violated: *"a number in a comment is a
claim nothing checks."*

### Decision 6 — the test resolves a check's module from the function, not from its source text

`inspect.getsourcefile(check.fn)`. Matching on `@check("name"` asked the source how it happens to be
formatted, and three of six subjects are formatted the other way. A miss becomes an assertion failure
rather than a `continue`, per the derived-subject requirement: a subject that cannot be located is a
failure of the guarantee, not an omission from it.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| ~~Tightening `sensitivity` surfaces more unproven patterns than expected, and the change grows without bound~~ | **Retired.** The sweep was run before the shape was chosen: 13 command patterns under declared fixtures, 3 unproven, all in `ZS-MIG-13`. Task 4.1 re-runs it as a gate rather than as a discovery. |
| The rewritten `crossref` control depends on a `rust-style` rule not being named in `bevy-style/SKILL.md` — a fact that a later edit could quietly change | The control fails loudly if that stops holding: `edit()` raises `FixtureGone` when its anchor text is absent, and the `named`-set condition is asserted at injection time rather than assumed. |
| `dialect` gaining a case means every existing `rg` pattern is re-inspected, and a false positive blocks the build | The new case is a literal newline in the extracted pattern — decidable, with no ambiguity and no regex heuristic. Measured: exactly two patterns in the library carry one. |
| Restoring `_anchor_patterns` makes `crossref` slower — it runs an anchor standard's full decisive set over the delta's corpus | Measured at 0 findings today, and the corpus is shared through `corpus_for`, so no new corpus is built. Timing is re-measured against the 22.3s `--fast` baseline in task 6.3. |

## Migration Plan

Order matters in two places:

1. **`PS-FMT-07` / `PS-MIG-05` are unwrapped before `dialect` gains the newline case**, or the tree
   fails its own new check mid-change.
2. **`crossref` is de-indented before its control is rewritten**, so the new control can be verified
   against working code first and reverted code second (Decision 0).

Everything else is independent. No rollback plan: each item is a self-contained edit, and the suite is
the gate.

## Open Questions

None. The four choices that could have gone either way — batching, `sensitivity`'s strictness, the
wheel-install semantics, and where the newline case belongs — were put to the user and decided before
this document was written.

## What implementing this found that reading the diff had not

**The control's passing was measurable, and the measurement is the deliverable.** The review could
say the `crossref` control "passes for the wrong reason". Running it said how: 1 failure before the
de-indent, 2 after, and the surviving one was the citation branch. The replacement produces exactly
1, from the anchor sweep, and **0 with the loop re-indented under the `return`** — which is the
number the old control could never have produced. Decision 0 is worth more than the fix it guards.

**Unwrapping a Check was not possible as stated.** `PS-MIG-05` on one line is ~185 columns against
`layout`'s limit of 100. "Put the command on one line" had no solution; the rule became four
commands split on API family, each separately runnable and each family kept whole. Nothing in the
diff shows this — it needs two checks' constraints held at once. `PS-FMT-07` did fit, once its prose
moved to its own line.

**The two directions of the cover are entangled under a 1:1 cover.** Narrowing a pattern so it stops
matching its fixture reports *both* — the pattern covers nothing, and the fixture is now an orphan.
Isolating the orphan direction meant pointing one pattern at a fixture another already covers, so
every pattern still matches something and only the orphan is left to report. The review named the
second direction; it could not have shown that a naive control tests both at once and therefore
neither.

**A comment block was filed against the wrong field.** The paragraph explaining `not_decisive` —
*"Measured, not judged: each of these was promoted to accuse and hit the standard's own compliant
examples"* — sat above `fires` in both `bevy_style` and `rust_style`. In a diff it reads as a
docstring for the field it precedes. It only showed up because editing the reasons meant reading
what claimed to describe them.

**The frozen counts were 52, not ~40 — and the requirement they failed was already there.** The main
`check-authoring` spec has said *"the rule records that, naming what decides"* since it was written.
All 52 had been failing it, and the measurement in the string was what made them look like they said
something. Removing the number did not create the gap; it exposed one that had been paid for in
advance.

**`_sort_key` had a second caller that depended on its totality.** `max(newer, key=_sort_key)` was
not in the review's finding, and returning `None` broke it — quietly, in the sense that `ty` caught
it and a test would not have. `newer` became a `dict` of version to order so the best is chosen
without a key function that is allowed to answer `None`.

**`PS-FMT-07`'s dead alternative, confirmed.** Before the unwrap the pattern could match `SELECT`
and never `DELETE`, even under the harness's own `--multiline`. After it, both. The rule had been
half a rule since it was written.

**One task's verification clause was wrong and was corrected in place.** Task 2.4 asked that a reason
consisting only of `\|` fail. The spec scenario is about *truncation* — reading the whole cell — not
about a minimum reason. Judging `\|` as absent would be `documented` deciding whether a reason is
good, which its own failure message explicitly says is a reviewer's call. The task now asks what the
spec asks.

## What the verification measured

Run serially with nothing else on the machine, in the order the constraint requires.

| | Result | Time |
|---|---|---|
| `agent-skill check` | ALL CHECKS PASSED, 19 checks, `toolchain` and `mutation` included | 4070.9s |
| `pytest` | 208 passed | 4925.4s |
| `agent-skill check --fast` ×2 | ALL CHECKS PASSED | 25.4s, 25.7s |
| `pytest -m "not toolchain"` | 206 passed | 69.9s |

**`--fast` moved 22.3s → 25.4s, +3.2s (14%).** Two things were added to that path and both were
expected to cost: the `crossref` anchor sweep now executes, running an anchor standard's decisive
patterns over the delta's corpus — 185 `rust-style` command patterns over `bevy-style`'s examples —
and `sensitivity` grew from 13 `matches` calls to a full pattern × fixture grid. Neither builds a
corpus of its own; both go through `corpus_for`. The budget for restoring a check that had never run
is 3.2 seconds, which is the whole point of it having been cheap to skip.

**The test suite is 208 tests, up from 160.** The 48 new ones are unit tests over the branches this
change touched, and they run in about 10 seconds together — `test_crossref`, `test_pins`,
`test_documented`, `test_sensitivity`, `test_proc`.

**The suite's wall clock moved 35:30 → 1:22:05, and none of it is this change.** Measured by
splitting the run rather than reasoned about: the 206 tests without the `toolchain` mark take
**69.9 seconds together**, all 48 new ones included. The remaining ~81 minutes is two tests —
`test_toolchain_check_is_clean[toolchain]` and `[mutation]` — which compile and run every Rust and
Zig example. Nothing in this change touches an example's code, so what those two compile is
identical to what they compiled before it.

The same work in the standalone `agent-skill check` took 68 minutes, thirteen minutes less, on the
same machine minutes apart. That locates the variance in the toolchain builds — a cold cache against
a warm one — rather than in anything the suite asserts. Worth stating plainly because the first
reading of *35:30 → 1:22:05* is that this change cost an hour, and the measurement says it cost
seventy seconds.
