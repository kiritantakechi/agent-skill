## Why

`skills/` ships three standards — `rust-style` (769 rules), `zig-style` (435), `bevy-style` (249) —
and nothing for Python, which is the language this repository is itself written in. Python has just
had its Zig moment. PEP 779 promoted free-threading to officially supported in 3.14; PEP 649 made
annotations lazy and PEP 563 is now formally *Superseded*; and 3.15 adds lazy imports, `frozendict`,
`sentinel`, UTF-8 as the default encoding, and unpacking in comprehensions.

The dangerous part is not the new spellings — it is that a dozen of these changes produce **silently
different behaviour** rather than an error. `contextlib.contextmanager` used as a decorator now holds
its context open across the whole generator instead of closing when the generator object is created,
which silently changes every lock, transaction, and `chdir` hold time. `frozendict` is not a `dict`
subclass, so `isinstance(x, dict)` is now wrong. UTF-8 mode moves six surfaces at once, including
`sys.stdout` gaining `surrogateescape` — turning loud failures into silent ones.

And free-threading invalidates a *reason* rather than a list. The library FAQ's roster of atomic
operations still holds — `L.append(x)`, `D[x] = y`, `D1.update(D2)` are individually locked in the
free-threaded build — but the sentence that justifies it, that each bytecode instruction is therefore
atomic, is no longer the mechanism. The free-threading HOWTO says outright that built-in-type locking
is "a description of the current implementation, not a guarantee". Readers generalise from the
reason, not the roster: a compound `obj.n += 1` was never atomic and the FAQ always said so, but
under the GIL you could ship it for years, and on 3.15t eight threads lose roughly three-quarters of
its updates immediately.

Every one of those is invisible to a reader who learned Python before 2026, and most are invisible to
a linter. That is the gap this standard fills.

## What Changes

- **New skill `skills/python-style/`** — `SKILL.md` + `references/` + `assets/`, structurally
  identical to the three siblings: the same seven-section `SKILL.md` skeleton, the same tier tags
  (`[M]` / `[M!]` / `[S]`), IDs under a `PS-` prefix, a per-chapter contents table, `**Why:**` and
  `**Check:**` on every rule, a core section, a review protocol, a reference map, and an asset table.
  Thirteen chapters and 306 rules — 280 chapter rules plus 26 core. The planning target was 440–480
  by parity with the siblings; design Decision 11 records why that was the wrong instrument, since
  those totals price in many passes of growth that this change does not have.
- **Target: CPython 3.15, free-threaded.** Nothing below 3.14t is supported and no compatibility
  shim is described. Examples are verified against `cpython-3.15.0rc1+freethreaded`, which `uv` can
  install today; the pin moves to `3.15.0` final on 1 October 2026.
- **Three sources, merged and attributed:**
  - *Normative* — PEP 8, PEP 257, PEP 20, and the Python Typing Spec. Cited from the **living specs**
    (`typing.python.org/spec`, `packaging.python.org/specifications`) rather than the PEPs, because
    every packaging and typing PEP now carries a "This PEP is a historical document" banner and
    points at those pages.
  - *Empirical* — the conventions of the CPython 3.15 standard library, and its documented
    thread-safety guarantees, which are the only source for the chapters a linter cannot reach.
  - *House standard* — Ruff's rule catalogue (969 rules across 59 linters, already subsuming
    pycodestyle, pyflakes, bugbear, pyupgrade, pylint and the flake8 family).
- **One spine: a rule states the claim, a tool decides it, the tool is pinned, the claim outlives the
  pin.** Every rule that can cite a ruff code or a `ty` rule does; the shipped configuration is tied
  to those citations by an equality invariant in both directions. Rules are written to hold under the
  Typing Spec rather than under one checker's quirks, so a tool bump moves a pin and not a chapter.
- **One tool per role, all four from Astral.** `uv` resolves and locks, `uv_build` builds, `ruff`
  lints and formats, `ty` type-checks. Each is named in a rule, shipped as a pinned configuration
  asset, required in CI, and tied to the rules by the same invariant. `ty` is beta and says so; the
  standard states that policy and the bump procedure rather than shipping a configuration whose use
  it declines to prescribe. No role is offered as a choice, and no tool the standard does not
  require is documented — a rule's claim still rests on the Typing Spec rather than on `ty`, which
  is what lets the standard require a construct its own checker has not implemented yet.
- **Pure Python is the whole subject.** Authoring, building, and distributing compiled extension
  modules are out of scope: no chapter covers them, and the build backend the standard mandates
  cannot produce them. What survives is the consumer-side fact a pure-Python reader still needs —
  that a free-threaded build can re-enable the GIL at import time, permanently and process-wide.
- **A stated limit, not a hidden one.** Ruff has **zero** free-threading rules — verified by
  searching all 969 rule names, summaries, and explanations. `PS-FT` is therefore the one chapter
  with no mechanical coverage at all, and rests entirely on the normative and empirical sources plus
  hand-written checks. Every other chapter has partial ruff coverage — `ASYNC` has 16 rules, `INP`
  and `TID` cover packaging — so the honest statement is per-rule, not per-chapter: a rule that ruff
  cannot decide says so and ships its own check.
- **New verification capability in `agent-skill`** — a `python` toolchain that extracts every
  `# verified` block, executes it on 3.15t, type-checks it with `ty`, and lints it with `ruff`; plus
  `agent-skill fmt` via `ruff format`, so a formatting finding is a command rather than a diff.
- **Negative controls** for every new check, per the repo's standing rule that a check which cannot
  fail looks exactly like a check that passes.
- **README** gains `python-style` in the layout, the check table, and the toolchain notes.

## Capabilities

### New Capabilities

- `python-style`: the standard itself — what it targets, which sources it merges and how it resolves
  their conflicts, the tier model, rule anatomy and ID scheme, chapter coverage, the 3.14/3.15
  reality check, the dead-API discipline, the review protocol, and the bundled assets.
- `python-verification`: `agent-skill`'s ability to verify a Python skill — extracting blocks,
  running them on a pinned free-threaded interpreter, type-checking, linting, formatting, applying
  the standard's own checks to its own examples, and failing when any of that cannot be run.

### Modified Capabilities

None. `openspec/specs/` is empty; these are the first two capabilities in the repo.

## Impact

- **New**: `skills/python-style/SKILL.md`, `skills/python-style/references/*.md` (13 chapters plus
  `review-checklist.md`), `skills/python-style/assets/{pyproject.toml,ruff.toml,ty.toml,ci.yml}`,
  `src/agent_skill/lang/python.py`, `src/agent_skill/profiles/python_style.py`.
- **Modified — this is roughly half the change, not a prelude to it.** The audit of
  `src/agent_skill/` found the Python toolchain reaches further than a new `lang/` module:
  `model.py` (the marker vocabulary is a module-global tuple), `checks/markers.py` (same),
  `text.py` (`strip_comment` is `//`-only, and `//` is floor division in Python — it truncates real
  code), `checks/selfapply.py` (`FILE_ARG` does not recognise `*.py` or the TOML assets, so they
  would be grepped as patterns and fail as tier-1 findings), `checks/mirror.py`
  (hardcoded to the rust/zig pair), `checks/controls.py` (its empty-corpus guard names rust and zig
  literally), `checks/__init__.py` (a check is only reachable if its module is imported there),
  `checks/toolchain.py` (its tool probe is `shutil.which`, which cannot see a uv-resolved
  interpreter), `fmt.py` (gated on `profile.crate is not None`), `report.py` (two levels, neither of
  which means *could not run*), `cli.py`, `lang/__init__.py`, `profiles/__init__.py`, `README.md`,
  and `pyproject.toml`.
- **External dependencies**, all pinned exactly because all three can move under the standard:
  `cpython-3.15.0rc1+freethreaded` via `uv`; `ruff==0.16.4` with lint-scoped preview, without which
  `target-version = "py315"` warns on every run; `ty==0.0.74`, which is beta.
- **Risks**: 3.15 is at rc1 until 1 October 2026. `ty` is `0.0.x` and states that breaking changes,
  *including changes to diagnostics*, may occur between any two versions, on a release cadence whose last twenty gaps
  ran from zero to six days, half of them a day or less. Ruff changed its default rule set from 59 to 413 in 0.16.0. All three are pinned
  by exact version and guarded by the equality invariant, so drift surfaces as a failing check rather
  than as prose that quietly stopped being true.
