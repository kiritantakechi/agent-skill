## Why

Two gaps, both of the same shape: something the repository claims is checked, and nothing checking it.

**Most Checks do not run.** Of 1615 `**Check:**` sections, **133 (8%)** ship a command that can accuse.
A further **186** name a backticked span the engine already extracts and runs — but as a tier-2 note,
because a prose span is assumed to narrow rather than decide. Another **99** say "grep the view layer
for constructions of domain types" and name nothing runnable at all. The remaining 1197 are genuine
judgement and always will be.

`python-style` ships 81 commands; `rust-style` ships 9 across 737 rules, and that asymmetry looked
like a spelling difference. **It is mostly not.** Measured by promoting all 186 spans to commands —
matching unchanged, only the tier moves — **52 of them fire on the standard's own compliant
examples**. Their predicates carry a qualifier the pattern cannot see: `$HOME` is only a defect in
"string concatenation", `assert!(` only when "containing `==`". The remaining 134 pass that test,
but passing it is weak: a pattern matching nothing anywhere passes it perfectly.

So the surface is smaller than the raw counts suggest, and the reason is genuinely that most of
these predicates need context. The work is to find the ones that do not, and to prove it.

**A pin nobody verifies is a claim, not a control.** `pins` checks the interpreter and nothing else.
This was found the expensive way: the standard stated it was validated against `ruff==0.16.4` while
the harness was running `0.16.3`, and every check passed. `rg` gained a runtime version assertion in
the previous change; `ruff`, `ty` and `pytest` still have none.

## What Changes

- **Every prose Check that can decide becomes a command.** All 285 candidates across four skills are
  judged individually: a span that decides is written as an `rg` command and promoted to tier 1; a
  span that only narrows keeps its prose form and gains a `not_decisive` entry recording *why*, so
  the classification stops being implicit.
- **The 99 Checks that name no pattern get one authored.** These are not translations — there is no
  existing spelling to preserve — so each ships with a **positive control**: a fixture the pattern
  must match. **This closes a gap that predates the change**: no rule pattern in this repository has
  ever been shown to fire on a violation. `selfapply` proves they do not fire on *compliant* code
  (tier 1 is empty); nothing proves they fire on anything.
- **`pins` covers every pinned tool, and reports a superseded pin.** `ruff`, `ty`, `pytest` and `rg`
  join the interpreter: the declared pin is compared against the version that actually runs, and
  against the newest release available. **BREAKING for CI**: an upstream release now turns the build
  red until the pin is reviewed and moved.
- **`selfapply.py` is split along the concerns it has accumulated.** At 423 lines it holds five:
  parsing a Check into patterns, building the corpus, running a pattern, deciding a tier, and
  rendering. `crossref` already imports three of them, so it is a shared module wearing a check's
  name.
- **A code audit precedes the refactor**, and its findings — not a guess made now — decide what else
  moves. The two already on the list: `controls` is 44.5s of a 77s run because it rebuilds a corpus
  per control, and `_HELD` keeps every temporary directory alive for the life of the process.

## Capabilities

### New Capabilities

- `check-authoring`: what a rule's Check must be — when a predicate has to be written as a runnable
  command rather than prose, what a newly authored pattern must ship with before it can accuse, and
  how a Check that only narrows records that it does.

### Modified Capabilities

- `check-execution`: gains the requirement that a pinned tool's declared version is verified against
  the one that runs and against what has been released. The capability is introduced by
  `migrate-checks-to-ripgrep` and is amended here rather than duplicated.

## Impact

**Rule text** — 285 Checks across all four skills, weighted heavily toward the two that were written
without command discipline:

| skill | already commands | span to judge | pattern to author |
|---|---:|---:|---:|
| `bevy-style` | 14 | 49 | 26 |
| `python-style` | 81 | 0 | 3 |
| `rust-style` | 9 | 98 | 58 |
| `zig-style` | 29 | 39 | 12 |
| **total** | **133** | **186** | **99** |

**Harness** — `checks/selfapply.py` split; `checks/crossref.py` and `checks/dialect.py` re-pointed at
the extracted modules; `checks/pins.py` extended; `checks/controls.py` gains the positive controls;
`proc.py`'s `version_mismatch` reused rather than reimplemented.

**Risk** — a promoted Check that does not actually decide becomes a false failure, and unlike the
previous change there is no equality baseline to catch it: these Checks have no prior executable
spelling. What replaces it is per-rule judgement plus the positive controls, and the fact that
`selfapply` already fails on any tier-1 pattern that hits the standard's own compliant examples.
