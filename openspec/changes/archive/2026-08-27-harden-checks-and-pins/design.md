## Context

See `proposal.md` — Why. What the audit found, since the decisions below rest on it:

**`selfapply.py` is 423 lines holding five concerns**, and one of them is already shared:

| Lines | Concern | Names |
|---|---|---|
| 52–67 | parsing a Check into patterns | `Pattern`, `dialect_of`, `patterns_of` |
| 70–105 | what a match is, what a corpus unit is | `Span`, `Unit` |
| 108–275 | building the corpus and running a pattern | `Corpus`, `corpus_for`, `searcher_problem` |
| 328–413 | deciding a tier | `selfapply`, `_run` |
| 415–423 | rendering | `_render` |

`crossref.py` imports `corpus_for`, `patterns_of` and `searcher_problem` from it. So the module is
already a shared library that another check depends on, wearing the name of one particular check.

**The Check population**, measured rather than estimated — an earlier figure of "247 convertible" came
from keyword matching and was wrong:

| | count | share |
|---|---:|---:|
| judgement, permanently | 1197 | 74% |
| a span the engine already extracts and runs as tier 2 | 186 | 11% |
| already a command that decides | 133 | 8% |
| names a search but no usable span | 99 | 6% |

**The audit's findings**, measured rather than assumed:

| duplication | verdict |
|---|---|
| `QUOTED` in `dialect.py` and `selfapply.py` | real; one home after the split |
| a bracket scanner in `dialect.py` | **not duplicated** — `patterns_of` never had one. The task list said it did; it was in the migration instrument, which was deleted with it |
| `META` in two profiles, `_SKIP` in three `lang` modules | not duplication — per-profile and per-language by design |

`controls` is **38.7s of a 53.1s `--fast` run**, and the cost is not where the plan assumed:

```
self-application   24.3s  (4 controls, ~6s each)   ← 65% of controls
anatomy             5.5s
assets              4.5s   (the uv build added last change)
copytree            0.8s   total, all 37 controls  ← not the problem
```

A control injects its defect into **one** skill's file and then runs the check over **all four**.
Nothing needs the other three: the assertion is only that the check reports a failure. Scoping each
control's run to the skill it edited is the fix, and it is worth roughly a 4x cut on the dominant
cost. Cross-skill checks — `crossref`, `mirror` — still need the whole set, so the scope comes from
the control rather than being assumed.

`_HELD` does not leak across processes (127 temp directories before a `controls` run and 127 after),
but it does hold one directory per distinct tree for the life of the process, which a `controls` run
makes ~30 of.

## Goals / Non-Goals

**Goals**

- Every Check that *can* decide, does.
- Every pattern that accuses has been shown to catch something.
- Every pin is compared against what runs and against what exists.
- The harness's shared machinery stops living inside one check.

**Non-Goals**

- Converting the 1197 judgement Checks. Their predicates are not searchable and forcing them into
  patterns produces the noise tier 3 exists to flag.
- Changing what any rule *means*. A promoted Check states the same claim in a runnable form.
- Multi-line patterns. `-U` is on from the previous change; authoring rules that exploit it is
  separate work.

## Decisions

### 1. `selfapply.py` splits four ways, along the seam `crossref` already crossed

```
checks/selfapply.py  ──▶  patterns.py   Pattern, dialect_of, patterns_of
                          corpus.py     Unit, Corpus, corpus_for
                          search.py     Span, searcher_problem, the rg invocation
                          selfapply.py  the check: tiering and rendering
```

The split is not by line count, it is by who needs what. `crossref` needs a corpus and a parser and
has no interest in tiering; `dialect` needs the Check-text parser and nothing else, and currently
carries its own copy of `QUOTED`. Its bracket scanner is *not* duplicated — the audit checked, and
`patterns_of` never had one. After the split `QUOTED` has one home and the scanner stays where it is
used.

`Span` travels with the search rather than with the corpus: it describes a match, and the corpus is
what was matched against.

### 2. A newly authored pattern must be shown to fire

This is the change's most important decision and it closes a gap that predates it.

`selfapply` proves **specificity**: tier 1 must be empty, so no deciding pattern may match the
standard's own compliant examples. Nothing proves **sensitivity**. Not one of the 133 existing
command patterns has ever been shown to match a violation. For patterns that were translated from an
older spelling that was itself in use, that is a tolerable gap. For 99 patterns invented from
nothing, with no prior spelling to compare against, it is not — a pattern that matches nothing looks
exactly like a pattern that correctly found nothing wrong.

So each authored pattern ships a fixture containing the defect, and the pattern matching that fixture
is asserted. The fixture is the rule's own `BAD` example where one exists, and a minimal one written
alongside where it does not.

This is deliberately *not* extended to the 133 existing patterns in this change. Doing so would mean
authoring 133 fixtures, which is its own body of work; the requirement here binds what is newly
written, and the older half is named as remaining debt.

### 3. Promotion is per rule, and the default is not to promote

The 186 spans the engine already extracts are reported as tier 2 — "the pattern narrows, a person
decides" — and that classification was never examined; it is what the code assumes about any prose
span.

It turns out to be mostly right. Promoting all 186 and running the suite is a cheap experiment,
because promotion to `rg -nF` preserves the literal and moves only the tier:

```
186 promoted
  52  fire on the standard's own compliant examples   → cannot decide, measured
 134  pass specificity                                → necessary, not sufficient
```

A linguistic classifier reached 32 candidates; adding a scope-qualifier test cut that to 13; reading
those 13 by hand rejected 3 — and the experiment independently rejected the same 3. Judgement and
measurement agreed, which is the evidence that the qualifier reading is the real discriminator.

The safe default therefore stands, now backed by a number rather than caution: leave the Check as
prose and record *why*. A wrong promotion produces a false failure on correct code, which is worse
than a missed promotion — it teaches the reader that the standard's failures are not to be trusted.

**Specificity is not sufficient and the 134 are not promotable on its strength.** That is what the
positive control is for, and what bounds this change: promoting a pattern to accuse means writing a
fixture that proves it fires, and only patterns that accuse need one.

### 4. Order: `python-style` last, `rust-style` first

`rust-style` has 98 spans and 58 patterns to author against 9 existing commands, so it is where the
judgement is hardest and where a bad rule of thumb would do the most damage. Doing it first means the
rule of thumb is formed under the hardest conditions rather than tuned on easy cases and then
applied there.

`python-style` has 3 candidates in total; it is a validation pass, not a work item — and the clearest
evidence that the gap was command discipline rather than subject matter.

### 5. `pins` compares in two directions, and the second one needs the network

The pin is compared against **what runs** (`version_mismatch`, already written for `rg` in the
previous change — reused, not reimplemented) and against **what exists** (the newest release on the
index, as the interpreter check already does with `uv python list`).

The second direction has a real cost that is being accepted rather than solved: a release upstream
turns the build red until someone moves the pin. That is the intended behaviour — it is why the
interpreter check was written that way, and Decision 0 of the previous design says moving a pin is a
reviewed event. But it means the build's colour now depends on a third party's release schedule.

When the index cannot be reached, the result is `UNRUN`, never "up to date". A check that could not
look must not report success — the same rule that had to be applied to two paths in `assets`.

### 6. The archival ordering hazard, now resolved

`check-execution` is amended here and introduced by `migrate-checks-to-ripgrep`. Archiving in the
wrong order would have left a `MODIFIED` delta with nothing to modify, and validation would not have
caught it: deltas are checked against the change set rather than only against `openspec/specs/`.

`migrate-checks-to-ripgrep` has since been archived, so `check-execution` is a main spec and the
`MODIFIED` delta here has its target. Recorded because the hazard was real and the check that would
have caught it does not exist.

### 7. What the promotion actually yielded, and what it says

| | before | after |
|---|---:|---:|
| Checks shipping a command that accuses | 133 | **138** |
| prose spans reported as candidates | 186 | 181 |
| Checks naming a search but no pattern | 99 | 99 (untouched) |
| `not_decisive` entries | 31 | **78** |
| positive-control fixtures | 0 | **10** |
| `--fast` wall-clock | 53.1s | **22.6s** |
| `controls` wall-clock | 38.7s | **14.9s** |
| checks in the suite | 16 | **18** |

Tier counts are **identical** to the baseline — 0 / 142 / 31, unchanged per skill. That is a stronger
result than "every difference was intended", and the reason is worth stating: all five promoted rules
had zero hits on the compliant corpus, which is precisely what passing specificity meant. A rule with
no hits produces no finding, so it was never among the 142 tier-2 findings to begin with.

**Five promotions out of 186.** Not the yield the proposal implied, and the number is the finding:
52 spans were measured unable to accuse, and of the 134 that passed specificity, reading each one's
own sentence found a qualifier the pattern cannot see in all but five — `$HOME` only in "string
concatenation", `#[should_panic]` only "with no `expected`", `validate_*` only "returning
`Result<(), _>`".

The promotion of `ZS-MIG-13` is the clearest evidence the gate works. Its authored pattern listed
`utf8Decode` among the dead APIs and immediately accused a compliant example using
`std.unicode.utf8Decode2` — a **live** function whose name the pattern matched as a prefix. A word
boundary fixed it. Nothing but running the pattern against real examples would have found that.

**The 99 Checks that name no pattern are untouched.** Authoring 99 patterns and 99 fixtures against
the 14 defect examples this repository has is a body of work this change measured and did not take
on. The measurement is the deliverable: a later change starts from 52-cannot / 134-unproven / 99-
unwritten rather than repeating the experiment.

## Risks / Trade-offs

- **A promoted Check does not actually decide** → per-rule judgement, `not_decisive` as the default
  when unsure, and `selfapply`'s tier-1 rule as the backstop. Unlike the `rg` migration there is no
  equality baseline here: these Checks have no prior executable spelling to compare against.
- **An authored pattern is written to match its own fixture and nothing else** → the fixture is the
  rule's existing `BAD` example where one exists, so it is not written by the same hand in the same
  minute as the pattern.
- **The build goes red because ruff released** → intended, and stated in the proposal as breaking.
  The alternative is a pin that drifts silently, which this repository has already paid for once.
- **The refactor and the 285 rule edits land together** → they are independent, and the refactor goes
  first so the rule work happens against the structure it will live in rather than being rewritten by
  it.
- **285 judgements is a large body of work with no mechanical check on the judgement itself** →
  accepted; the alternative measured earlier is that three quarters of the mechanical surface stays
  unavailable.

## Migration Plan

1. **Audit and split** the harness. No rule text changes; the full suite must pass unchanged.
2. **Extend `pins`** to every tool, both directions, with the `UNRUN` path for an unreachable index.
3. **Author the positive-control mechanism** and prove it fails when a pattern stops matching its
   fixture, before any pattern depends on it.
4. **Per skill, hardest first**: judge each span, promote or record, author the missing patterns with
   their fixtures. `rust-style`, `zig-style`, `bevy-style`, `python-style`.
5. **Re-verify** the full suite and record the promotion rate — how many of the 186 decided, and how
   many of the 99 could be written at all.

**Rollback**: steps 1–3 are independently revertible. Step 4 is revertible per skill, since each
skill's rule text is disjoint from the others'.
