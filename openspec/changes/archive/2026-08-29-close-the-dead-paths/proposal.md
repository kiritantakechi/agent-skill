## Why

An extra-high-effort review of the working tree found thirteen defects. Three are live. Ten are the
shape this repository exists to prevent: **a guard that cannot fail looks exactly like a guard that
passes.**

The centrepiece is `crossref`. Removing a `with tempfile.TemporaryDirectory(...)` wrapper left the
whole anchor-pattern loop indented under the `return` that had guarded it:

```python
corpus = corpus_for(skill, lang)
if not corpus.blocks:
    return
    for prefix in sorted(anchors):   # ← unreachable
```

So the mechanism that runs one standard's decisive patterns over another's examples — the thing the
README's `crossref` row names first — has not executed once. `ast.parse` confirms the function's last
statement is that `if`, whose body is `[Return, For]`.

**And its negative control still passes.** The control named *"an anchor rule that fires on the
delta's examples and is not accounted for"* edits `bevy-style/SKILL.md` to renumber `RS-API-26`, which
also trips the unrelated override-table branch in the outer `crossref` function. Measured on a copied
tree: 0 findings as shipped, 1 finding when the loop is de-indented —
`RS-API-26 -E /struct [A-Za-z_]*\(pub / hits 60 line(s)`. `controls` is the mechanism that proves
every check can fail, and it reported green over a mechanism that could not fire, because the control
never touched it.

Two more findings are the same failure at one remove:

- `test_a_declaration_is_not_missing_a_tool` locates a check's module by the literal `@check("<name>"`
  and skips on a miss. Three of the six checks that declare `needs` spell the decorator across two
  lines, so `crossref`, `pins` and `sensitivity` are all silently uncovered — **including `pins`,
  which the test's own docstring names as the case it was written for.**
- `pins._sort_key` returns `(0, 0, 0, 0, 0)` for a version it cannot parse, so an index answer of
  `1.2.3.post1` compares as older than the pin and the staleness check quietly passes. This is the
  bug `version_mismatch` was already fixed for — *"An unfindable pin is itself the complaint"* —
  reintroduced one function away.

The three live defects:

| | Defect | Evidence |
|---|---|---|
| **1** | `crossref`'s anchor-pattern loop is unreachable | above |
| **2** | `pinned_version` crashes under a wheel install | `uv build --wheel` ships no `pyproject.toml`; installing into a clean 3.14 venv and calling `pinned_version('rg')` raises `FileNotFoundError`. `[project.scripts]` declares the entry point, so installed use is intended. |
| **3** | Two shipped Checks are unrunnable as printed | `PS-FMT-07` and `PS-MIG-05` wrap their `rg` command across a markdown line, so `QUOTED` captures a literal newline. Run as a reader would: `rg: the literal "\n" is not allowed in a regex`, rc=2. The harness passes `--multiline` unconditionally, so the pattern compiles here and the `DELETE` alternative silently never matches. |

Defect 3 is `dialect`'s subject exactly — *a pattern carrying syntax from a grammar it will not be
read in* — and `dialect` looks only for `\|`.

## What Changes

**The dead path is closed, and the control that missed it is made to reach it.**

- `_anchor_patterns` is de-indented and runs. Its `controls` entry is rewritten to inject a defect the
  anchor-pattern branch alone can report, so it fails when that branch stops firing rather than
  passing through a sibling branch.
- Its `if not lines: continue` stops reading `find`'s `None` — pattern rejected, timed out, tool
  absent — as zero hits. `selfapply` already distinguishes them; this call site did not.

**Two guards start guarding.**

- The tool cross-check resolves a check's module from the registered function rather than from
  decorator text, and a subject it cannot locate is a failure rather than a `continue`.
- `_sort_key` stops answering for input it did not understand. An unparseable version withholds the
  pass instead of reporting agreement.

**A pattern must be runnable as printed.** `dialect` takes ownership of the newline case: an `rg`
pattern containing a raw newline is reported, because the command the standard shows a reader is
rejected by the tool the standard pins. `PS-FMT-07` and `PS-MIG-05` are unwrapped.

**`sensitivity` starts meaning what it is called.** Its module is titled *"Every authored pattern,
shown to catch the defect it was written for"* and its code asserts `any`. `ZS-MIG-13` ships four
command patterns and its fixture matches one; the other three are counted as covered and could be
narrowed to match nothing without this check noticing. `fires` becomes rule id → one fixture per
pattern, and every command pattern must be shown to fire. **This will surface further unproven
patterns, and that is the point.**

**The positive control is prepared like the corpus.** `find` searches the comment-stripped copy for a
pattern without `//` in it; `matches` writes the fixture verbatim. Nothing is wrong today — measured
across all four profiles — but the two halves are unaligned, so a fixture can certify a pattern the
production path could never fire.

**A pin that cannot be read is a complaint, not a crash.** `pinned_version` reuses the path
`version_mismatch` already has for an unfindable pin.

**Smaller, all in the same family:**

- The `controls` row's reason column is parsed as `[^|]*`, which stops at the `\|` a GFM table needs
  for a literal pipe. Measured: `dialect`'s reason reads back as `` ` \ `` — two characters that
  satisfy "every row carries a reason".
- ~40 new `not_decisive` reasons hard-code *"hit 6 compliant examples"*. `patterns.py` states this
  repository's rule against exactly that: *"a number in a comment is a claim nothing checks."* These
  are worse than a comment — `selfapply` renders them into the report.
- `exempt`'s declared type still says `int` after the migration to `Span`; the lambdas are untyped, so
  `ty` cannot see the disagreement.
- Two identical `return None, pattern.mode` branches in `find`, whose docstring argues they are
  different cases.
- `Corpus.build` recomputes a running total `starts` already carries.

## Capabilities

### Modified Capabilities

- `harness-integrity`: gains the requirement that **a negative control exercises the mechanism it
  names**. The capability already says machinery nothing reaches is removed and that a list of
  subjects is derived rather than maintained; neither catches a control that passes through a
  different branch of the check it is aimed at. Also extends the derived-subject requirement to say
  that a derivation which cannot locate a subject fails rather than skipping it, and the
  documented-claim requirement to say a claim's presence is decided over the whole field.
- `check-authoring`: **a Check is runnable as printed** — the command the standard shows a reader must
  be accepted by the pinned tool as the reader would invoke it, not only under flags the harness adds.
  The positive-control requirement is tightened from *the pattern* to *every command pattern of the
  rule*. The narrowing-Check requirement gains: a recorded reason states what decides, not a
  measurement nothing re-measures.
- `check-execution`: the *cannot-match-is-a-failure* requirement is extended to hold **at every call
  site**, not wherever it was remembered. The pinned-tool requirement gains: a pin that cannot be read
  and a version that cannot be parsed are each the complaint, never silent agreement. The
  positive-control fixture is prepared under the same rules as the corpus it stands in for.

## Impact

| File | What |
|---|---|
| `src/agent_skill/checks/crossref.py` | de-indent; `find`'s `None` distinguished from `[]` |
| `src/agent_skill/checks/controls.py` | a control that reaches the anchor-pattern branch and no other |
| `src/agent_skill/checks/dialect.py` | raw newline joins `\|` as reported syntax |
| `src/agent_skill/checks/sensitivity.py` | `any` → every command pattern |
| `src/agent_skill/checks/search.py` | fixture stripped like the corpus; the duplicate branch |
| `src/agent_skill/checks/pins.py` | `_sort_key` stops answering for what it did not parse |
| `src/agent_skill/checks/documented.py` | reason parsed over the whole cell |
| `src/agent_skill/checks/corpus.py` | the running total |
| `src/agent_skill/proc.py` | an unreadable pin is a complaint |
| `src/agent_skill/profiles/*.py` | `fires` per pattern; `exempt`'s type; the hard-coded counts |
| `skills/python-style/references/` | `PS-FMT-07`, `PS-MIG-05` unwrapped |
| `tests/test_unrun.py` | module resolved from the function; a miss fails |

**Risk — tightening `sensitivity` is open-ended.** Requiring every command pattern to fire is the one
change here whose cost is not known in advance: `ZS-MIG-13` alone needs three fixtures, and the sweep
may find more. If the count is large, the fallback is not to weaken the requirement but to record the
unproven patterns explicitly, so the gap is visible rather than absorbed by an `any`.

**Risk — a control that reaches only one branch is harder to write.** The current `crossref` control
passes for the wrong reason precisely because `crossref` has several branches over the same input.
The replacement must be checked against the fixed code *and* against the code with the fix reverted:
it has to fail on the second.
