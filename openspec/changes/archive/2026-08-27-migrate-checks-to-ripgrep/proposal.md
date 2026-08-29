## Why

A rule's `**Check:**` is the standard's only mechanical surface, and today those checks are executed
in two incompatible regex dialects chosen by accident: **83 commands are BRE** because they omit
`-E`, **61 are ERE** because they carry it. Which dialect a reader gets depends on which one that
rule's author happened to write, and nothing in the repository states that the two differ.

The engine has already been bitten by exactly this. `selfapply.py`'s module docstring records a
pattern that parsed as a character class of `[:space` plus a literal `]`, matched nothing, and was
reported as ran-and-clean — because **a check that cannot fire is indistinguishable in the report
from a check that fired and found nothing**. Two dialects double the surface for that failure, and
`grep`'s BRE is the half that produces it: `\(`, `\|` and `\{` mean the opposite of what a reader
who knows modern regex expects.

`rg` has one dialect, one binary, and no BRE mode to fall back into.

## What Changes

- **The engine executes patterns with `rg` instead of `grep`.** One dialect, so `Pattern.mode` stops
  carrying a three-way BRE/ERE/fixed distinction and the `-F` retry stops meaning "the other
  grammar".
- **All 144 command-form Checks are rewritten as `rg` commands**, with the 83 BRE patterns
  translated to ERE. **BREAKING** for any reader who copied a Check verbatim: `grep 'A\|B'` becomes
  `rg 'A|B'`, and the old spelling under `rg` matches a literal pipe — silently, exit code 1.
- **Every translation is guarded by an equivalence assertion.** For each pattern, the old spelling
  under `grep` and the new spelling under `rg`, run over the same corpus, must produce identical
  hit-line sets. A translation that changes what a Check finds is a defect, not a migration. The
  assertion is a migration instrument and is deleted when the migration lands.
- **The word `grep` leaves the repository** — roughly 94 lines across the engine, the four profiles,
  `README.md` and the tests. This includes the `NotDecisive` reasons ("the grep finds every
  dataclass; the `frozen=True` argument decides"), which are user-visible report text, not comments.
- **`rg` becomes a declared, pinned tool** of the harness, the way every other tool it depends on is
  declared and pinned, rather than an assumed binary.
- **Multi-line matching (`-U`) is enabled**, and the execution path is rebuilt on `rg`'s own model
  rather than on grep's:
  - **The corpus becomes one file per example block** instead of one concatenated file. Under `-U` a
    concatenated corpus manufactures matches that straddle two unrelated examples — verified: a
    `try:` in one example paired with a `finally:` in the next. Separate files make that
    structurally impossible and let `rg` traverse a tree, which is what it is built to do.
  - **Results are read from `--json`**, not by splitting `-n` text on colons. The event stream
    carries the path, the start line, the byte offset, the matched span, and per-submatch offsets.
  - **A hit becomes a span, not a line number.** Under `-U` one match covers a range, so the model
    the engine carries has to say so.
  - **Every invocation passes `--no-config`.** Verified hazard: a `RIPGREP_CONFIG_PATH` on the
    machine running verification silently changed a result — a personal `-i` turned a
    non-matching pattern into a match. Verification must not depend on whose machine it runs on.

**Non-goal: `--multiline-dotall`.** `-U` alone is conservative and that is why it is safe to enable
here: verified, `^` and `$` keep their line anchoring, and `.` still does not cross a newline. Only
`--multiline-dotall` changes what existing patterns mean, so it stays off and a pattern that wants
to span lines says so with an inline `(?s)`.

## Capabilities

### New Capabilities

- `check-execution`: how a rule's Check is expressed and executed — the dialect it is written in,
  the tool that runs it, the requirement that one dialect serve all four skills, the isolation
  between the units a pattern is matched against, the reproducibility of an invocation, and the
  guarantee that rewriting a pattern preserves what it finds.

### Modified Capabilities

None. `openspec/specs/` is empty, so this change introduces its capability rather than amending one.

## Impact

**Engine and configuration**

| File | `grep` refs | Why it is affected |
|---|---:|---|
| `src/agent_skill/checks/selfapply.py` | 25 | Runs the patterns; its docstring documents the hazard this change removes |
| `src/agent_skill/profiles/python_style.py` | 24 | `NotDecisive` reasons are report text a user reads |
| `src/agent_skill/profiles/{__init__,bevy_style,zig_style}.py` | 12 | Same |
| `src/agent_skill/checks/{crossref,controls}.py` | 7 | Cite Check text and inject grep-shaped defects |
| `src/agent_skill/{model,text}.py` | 3 | Parse and strip around Check bodies |
| `README.md` | 12 | Describes the harness's decisive greps by name |
| `tests/{test_selfapply,test_model}.py` | 11 | Assert on grep behaviour and dialect |

`src/agent_skill/profiles/rust_style.py` is untouched: it has no `grep` reference at all.

**Rule text**

144 command sites across `skills/*/references/*.md`, in all four skills. The two patterns that need
more than a mechanical `grep`→`rg` swap are the 20 using BRE `\|` alternation and the 1 using
`[[:space:]]` — the latter needs no change, because `rg` accepts POSIX classes.

**Risk**

The failure mode is silent by construction. A mistranslated pattern does not error; it matches
nothing and the check reports clean. This is why the equivalence assertion is part of the change
rather than a review step.

Enabling `-U` does not weaken that argument, which is why it belongs here rather than in a later
change. Measured: with `-U` on and `--multiline-dotall` off, every one of the 144 existing
single-line patterns matches exactly what it matched before, because `^`/`$` stay line-anchored and
`.` still stops at a newline. Hit-set equality therefore remains provable across the whole
migration — provided the corpus is split per block first, since that is what `-U` would otherwise
break.
