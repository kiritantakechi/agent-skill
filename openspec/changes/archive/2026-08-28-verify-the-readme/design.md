## Context

See `proposal.md` — Why. Two measurements the decisions rest on:

```
README check table   16 rows          registry   18 checks    ← found by hand, since corrected
controls' claimed scope  "every other check"     actual  15 of 18
```

The three uncovered are `toolchain`, `mutation` and `controls` itself. `guard-the-guards` made those
exemptions explicit and gave each a reason in `WITHOUT_A_CONTROL`; the README was not part of that
change and still describes the world as it was before.

This repository already solved this problem once. `controls` exists because *"Every check carries a
negative control"* was a claim in a file, verified by hand once and never again — the fix was to make
the claim executable. The same file now carries the same kind of claim about `controls`, and the fix
that worked was never turned on the file itself.

## Goals / Non-Goals

**Goals**

- The documented list of checks and the registry cannot disagree.
- A universal claim about checks quantifies over the registry rather than over what someone typed.
- The `controls` row states its real scope, derived rather than written.

**Non-Goals**

- Verifying that a note is *true*. Whether `dialect` was added for the reason it gives is a
  reviewer's judgement; a check that pretended to decide it would be a check that cannot.
- Checking prose style, wording, or column order. Those drift without a defect, and a check that
  fires on them teaches people to ignore it.
- Extending this to the skills' own documentation. `anatomy` already holds those to their contents
  tables.

## Decisions

### 1. The check reads the table, not the prose around it

A README is mostly prose, and a check that reads prose is a check that fails on rewording. The claim
worth verifying lives in a table with one row per check, so the check parses exactly that: the
backticked name in the first column of each row, and whether the third column is non-empty.

Everything else in the file is out of scope by construction. This is what keeps the check from
becoming the kind nobody trusts — it fires only when the set of documented checks or the presence of
a reason changes, which is exactly when a claim has changed.

### 2. The `controls` row's scope is derived, not corrected

The row could simply be edited to say "15 of 18". It would be true today and false the next time a
check is added, which is the failure being fixed rather than an instance of it.

So the row states the rule and the check supplies the count: what `controls` covers is *every check
except those `WITHOUT_A_CONTROL` names*, and the check asserts that the README's phrasing matches
that set. The exemption mapping is already the single source for which checks are excluded — this
makes the README a second reader of it rather than a second copy.

### 3. The universal claim becomes an assertion about rows

*"Every one was added because a real defect shipped past the checks that existed at the time"* is
verifiable in exactly one respect: every row has a note. Whether the note is honest is not machine-
decidable, and Decision 1's scope excludes it.

That is a narrower guarantee than the sentence promises, and the narrowing is deliberate rather than
hidden: the check proves the sentence is *possible*, and a reviewer proves it is true. Recorded here
so that nobody later reads the passing check as evidence of more than it establishes.

### 4. Where the check lives

A new check rather than an extension of `anatomy` or `conventions`. Both of those are scoped to a
skill and run once per skill; this one is about the repository and must run once. `scope="all"` is
the shape, which `controls`, `crossref` and `mirror` already use.

It needs no external tool, so it declares no `needs` and stays outside the `UNRUN` machinery
`guard-the-guards` built. It does need a negative control, and will have one — there is no reason
here that would justify an entry in `WITHOUT_A_CONTROL`.

### 5. What the check found that reading the file had not

It fired twice on its first run. One was the row for `controls`, already known. The other was
itself: `documented` was registered and undocumented, so the first thing the check did was refuse to
let the file's promise be broken by the check that enforces it.

Two things surfaced that reading the README could not have shown.

**The check was structurally uncontrollable as first written.** It resolved `README.md` from its own
file location, so `controls` — which copies the tree, injects a defect and re-runs the check over the
copy — was reading the untouched original every time. A control could not have reached it. That is
how a check ends up in `WITHOUT_A_CONTROL` for a reason that sounds like "it is different" and is
really "nobody could make it fail". Resolving the README from the tree under test fixed it, and the
copy now carries one.

**Fixing that exposed two copies of the same setup.** `controls` built its throwaway tree in its own
loop and the tests built theirs in a `scratch` fixture, and only the first learned about the README.
The same control then fired under `agent-skill check` and not under `pytest` — a control that fires
in one runner and not the other is a control nobody can trust in either. One `throwaway_tree`
function now serves both.

| | before | after |
|---|---:|---:|
| checks | 18 | **19** |
| README rows | 16, then 18 by hand | 19, asserted |
| tests | 157 | **160** |
| tree-copy definitions | 2 | **1** |
| `--fast` | 22.3s | 22.5–22.9s |
| `controls` | 12.3s | 12.9s |

## Risks / Trade-offs

- **A check over documentation fires on formatting** → Decision 1 scopes it to the table's first and
  third columns. Wording, order and style are explicitly outside it.
- **The narrowed guarantee is read as the full one** → Decision 3 records the gap in the design and
  the check's own message says what it did and did not establish.
- **The README and the registry are kept in sync by editing the README** → that is the intent; the
  cost of adding a check is now one row of documentation, which is the price the file already claims
  to charge.
- **`controls` gains a dependency on `WITHOUT_A_CONTROL`, which lives in a test** → the mapping may
  need to move beside the registry so both the test and the check read one copy. If it moves, the
  test that guards it moves with it rather than being left pointing at the old location.
