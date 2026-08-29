## Context

See `proposal.md` — Why. What shapes the approach is what the machine and the tools actually do,
all of it measured rather than assumed:

- The repository's own venv is `python3.14t`; `PATH` python is 3.14.7 **with a GIL**. `uv` 0.12.3
  offers `cpython-3.15.0rc1+freethreaded` as a download, so the examples can run on the version they
  are written for.
- `ruff` 0.16.4 has **969 rules across 59 linters**. `target-version = "py315"` warns unless preview
  is on. **0.16.0 changed the default rule set from 59 to 413**, so `select` and `extend-select` no
  longer mean what older configs assume.
- `ty` 0.0.74 has **128 rules** (93 error, 23 warn, 12 ignore), no `strict` preset, and no
  require-annotations rule. Its stated version policy: *breaking changes, including changes to
  diagnostics, may occur between any two versions* — on a cadence whose last twenty gaps ran from zero
  to six days.
- Ruff has **zero** free-threading rules; a search of all 969 names, summaries, and explanations
  returns nothing for gil, free-thread, nogil, or thread-safe.
- The sibling standards are mechanically enforced by `src/agent_skill/`: frontmatter shape and
  stated rule count, rule anatomy (`**Why:**` / `**Check:**`, `[M!]` must contain "elaxed form"),
  contents-equals-headings, ascending IDs, globally unique titles, the `---` boundary, 100 columns.
  Structural symmetry with the siblings is not a preference here; most of it is a check.

## Goals / Non-Goals

**Goals:**

- Every rule traceable to one of the three sources, with Ruff's catalogue usable as a source without
  transcribing 969 entries into prose.
- Every `# verified` block executed on free-threaded 3.15, type-checked, and linted — with an absent
  tool reported as absent.
- Structural parity with the siblings: an agent that knows `rust-style` or `zig-style` navigates this
  one without relearning anything.
- Rules that survive a tool bump. The pins will move; the chapters should not have to.

**Non-Goals:**

- Any interpreter below 3.14t, in the standard or in the harness.
- Moving the repository itself to 3.15. The checker stays on 3.14t; only the examples run on 3.15t.
- A framework delta skill (the `bevy-style`-to-`rust-style` relationship). This standard is an
  anchor, and an anchor is what a future Django or FastAPI delta would need first.
- Enumerating Ruff's catalogue, or re-deriving the Typing Spec.

## Decisions

### 0. The spine: a rule states the claim, a tool decides it, the tool is pinned, the claim outlives the pin

Every other decision follows from this one, and it is what keeps three volatile dependencies from
becoming three ways for the standard to rot:

- **The claim** is the engineering statement, sourced to PEP 8 / the Typing Spec / the stdlib. It is
  what the reader learns and what survives.
- **The check** is a ruff code, a `ty` rule, or a grep. It is what decides a diff.
- **The pin** is an exact version in an asset. It is what makes the check reproducible.
- **The invariant** ties them: the shipped configuration and the set of checks the rules cite must be
  the same set, in both directions.

So a `ty` release that renames a rule fails the invariant and moves a pin. It does not silently
change what the standard says, and it cannot leave a rule enforced by nothing.

### 1. Ruff is a source of *checks*, not a source of *text*

A catalogue of 969 machine rules cannot be a standard on its own — a rule people read has to state a
claim and a reason. So a rule states the claim and cites the ruff codes that decide it, and
`assets/ruff.toml` is tied to those citations:

**A code cited by a rule but not enabled in the asset is a failure**, because that rule is enforced
by nothing.

*Corrected during apply.* The first draft made this symmetric — "a code enabled but cited by no rule
is a failure" — and that direction is unworkable. The asset selects `ALL`, which is 786 rules, and no
standard cites 786 individual codes; measured against the first chapter it was 786 enabled against
zero cited. What the symmetric version was reaching for is served instead by checking the asset's
`ignore` list, since quietly adding a code there to make an example pass is the actual failure mode.
That half is future work; the cited-but-not-enabled half is built.

This is a *new* invariant, not a port. The existing `lints`
check compares the shipped `Cargo.toml` against the table the verified crate declares — two
independently-written tables, compared. Nothing in the repository yet compares an asset against what
the rules *cite*, so this check has to be built rather than adapted, and it needs its own module
registered in `checks/__init__.py`.

Two refinements the research forced:

- **18 codes are `Removed`** — `ANN101`, `ANN102`, `PT004`, `PT005`, `UP038`, `E999`, `TRY200` and
  eleven others. Selecting one by exact code is a hard `ruff failed`, not a warning. The invariant
  excludes them, and a rule citing one is itself a failure.
- **The enabled set is computed, not declared.** `select`, `ignore` and `preview` merge into
  `linter.rules.enabled`, which `ruff check --no-cache --show-settings` prints; there is no JSON
  form. **`per-file-ignores` does not merge into it** — it prints as a separate `linter.
  per_file_ignores` block, so a code suppressed everywhere it could fire still reads as enabled. The
  invariant parses both, or it demands a rule citation for a code that can never fire.

*Alternative rejected:* one rule per ruff code. Produces a standard nobody reads, and says nothing
about the chapters ruff cannot reach.

### 2. The interpreter is pinned by exact build, and its absence is a finding

The toolchain resolves `cpython-3.15.0rc1+freethreaded` through `uv`, never through `PATH`. `PATH`
here is 3.14.7 with a GIL, and silently verifying free-threading rules against a GIL build is exactly
the failure the README records for `zig --version`.

Absence is reported as *could not run*, distinctly from a clean pass, and does not produce a green
overall result.

### 3. Execution covers what runs; `ty` covers what does not

Zig's problem was that a function nobody calls is never analysed, so a block with a type error
reported success; `zig-style` solves it with a `comptime` block touching every declaration. Python
has the identical hazard and a better answer — an unexercised branch is invisible to the interpreter
and fully visible to a static type checker:

- **Run it** on 3.15t, in an isolated temporary working directory, under a timeout. If the block
  defines `test_*` functions, run them.
- **Check it** with `ty`, which analyses every declaration whether or not it executes.

Neither alone suffices. A block needing the network, a path outside the temp directory, or a
wall-clock sleep is not eligible to be `# verified`; it is a `# fragment`.

### 4. `ty` is mandated, and its configuration is enumerated rather than blanket-promoted

`ty` occupies the same position as `ruff`: the standard names it, ships its configuration as an
asset, and requires it in CI. That parity is the point — a standard that ships a `ty.toml` for the
reader to copy while declining to say whether they should run it is not saying anything.

Mandating means `ty` is the required gate, not the only permitted tool. A project may run a second
checker; nothing in the standard promises that it will agree, and **no rule is weakened to make one
agree**. The standard documents `ty` and nothing else — a second checker's diagnostics are the
reader's business, not a subject this standard covers.

`PS-TYPE` therefore carries the mandate as an `[M]` rule, states `ty`'s own version policy so a
reader pinning it understands why the pin is exact, and gives the migration procedure for a bump.

The obvious `[rules] all = "error"` is wrong here, for two reasons the research turned up:

- **`error-on-warning` has defaulted to `true` since ty 0.0.52.** Warnings already exit 1. Promoting
  the 23 warn-level rules to error changes the printed label and nothing else.
- **`all = "error"` means any release can add a rule that fails the build** — on a two-to-five-day
  cadence with no API stability. Astral's own documented strict configuration enumerates instead.

So the config names the twelve ignore-by-default rules explicitly and nothing else. Eight go to
`error`; the four Astral documents as false-positive-prone go to `warn`, which is still a promotion
from `ignore` and still blocks, because warn exits 1. No warn-by-default rule is listed at all —
promoting one would be exactly the no-op this decision just argued against:

```toml
# ty==0.0.74 — pinned exactly; ty has no stable API.
[environment]
python-version = "3.15"

[rules]
blanket-ignore-comment = "error"
dynamic-function-decorator-return = "error"
missing-override-decorator = "error"
missing-type-argument = "error"
unsound-assignment = "error"
unsound-return-statement = "error"
unsound-yield = "error"
unsupported-dynamic-base = "error"
division-by-zero = "warn"            # Astral documents these four as false-
possibly-missing-attribute = "warn"  # positive-prone. `warn` is still a promotion
possibly-missing-import = "warn"     # from their `ignore` default, and warn exits
possibly-unresolved-reference = "warn"  # 1, so they still block.

[analysis]
strict-equality-semantics = true
strict-generic-narrowing = true

[terminal]
error-on-warning = true
output-format = "concise"
```

`strict-literal-narrowing` is an accepted alias of `strict-equality-semantics` and is undocumented;
the standard uses the documented name.

### 5. `ruff` supplies the one thing `ty` structurally cannot

`ty` has no require-annotations rule, and Astral's own docs point at Ruff's `ANN` family for it. So the anchors compose rather than overlap: **`ty`
decides whether the types are right, `ruff ANN` decides whether they are there.** No rule cites both
for the same claim.

The choice also earns something back: `ty` accepts PEP 728 `extra_items=` and PEP 661 `sentinel()` in
type expressions — specified constructs that the more established checkers have not implemented. For
a standard targeting 3.15, the beta checker is ahead on exactly the features that make 3.15 worth
targeting, so mandating `ty` removes a caveat from two chapters rather than adding one.

With both mandated, the two tools sit symmetrically: each is a source of checks, each ships a pinned
configuration as an asset, each is tied to the rules by an equality invariant, and neither is a
source of claims.

### 6. `[lint] preview = true` plus `explicit-preview-rules = true` — the drift is eliminated, not mitigated

Measured, with `select = ["ALL"]`:

| config | py315 warning | rules enabled |
|---|---|---|
| `target-version = "py315"` alone | fires | 810 |
| `+ [lint] preview = true` | silent | 949 — 139 preview rules pulled in |
| `+ explicit-preview-rules = true` | **silent** | **810 — byte-identical to preview off** |
| `[format] preview = true` alone | fires | 810 |

Two consequences. Preview is scoped to `[lint]`, because `[format] preview` does not silence the
warning and would opt into an unstable formatter style for nothing. And preview rules become
reachable only by exact code — which is the right gate for `TID254`/`TID255`, the two PEP 810
lazy-import rules, since citing them explicitly is a decision rather than a side effect.

The residual is that preview also gates behaviour changes to already-stable rules. That is why ruff
is pinned exactly, and why Decision 1's invariant is run as a regression test rather than only at
authoring time.

### 7. Markers name the tool that does the rejecting

`# verified` and `# fragment — …` carry over unchanged. `does-not-compile` does not: Python has three
distinct ways to be wrong, and a type error and a syntax error teach different lessons. The third
marker is `# rejected — <tool>: …`, naming the interpreter, `ty`, or `ruff`.

This is not a prose change. `model.py` holds `MARKERS = ("verified", "fragment",
"does-not-compile")` as a module global, and `checks/markers.py` builds its `LEADS` tuple from it, so
every `# rejected` block would fail `markers` on day one and fall out of `Marker.valid` — which also
drops it from the `advice()` exclusions that keep evidence blocks out of the self-application corpus.

The fix is to move the marker vocabulary onto `Profile`, defaulting to today's tuple, the way
`languages` and `marked_languages` already sit there. That keeps rust, zig and bevy byte-identical
and lets `python-style` add one word. A fourth global marker would instead offer `does-not-compile`
to Python and `rejected` to Rust, both meaningless.

`— GOOD` / `— BAD` and `(quoted from …)` keep their meanings and their effect on the
self-application corpus.

### 8. Line length 88 — and the disagreement is stated, because the standard requires that of itself

PEP 8 says 79, and 72 for docstrings and comments, with 99 permitted only *"for code maintained
exclusively or primarily by a team that can reach agreement on this issue"* — and that escape hatch
does not lift the 72-column docstring limit. Ruff's default is 88. CPython itself uses 79.

The standard takes 88, because the house standard is Ruff and deviating from a formatter's own
default is the sort of unmotivated divergence this standard exists to argue against. The rule states
the disagreement, per the spec's requirement that conflicting sources be resolved in the open —
`ruff format` also cannot guarantee the limit, so `E501` stays enabled as the backstop.

### 9. Cite the living specs, not the PEPs

Every packaging PEP the standard would otherwise cite — 621, 639, 735, 751 — now carries *"This PEP
is a historical document"* and redirects to `packaging.python.org/specifications`. The typing PEPs
carry the same banner and redirect to `typing.python.org/spec`, which moved from
`typing.readthedocs.io`. PEP 8, PEP 257 and PEP 20 remain Active and are cited directly.

So: normative citations point at the living spec, and name the PEP as provenance. This is not
pedantry — PEP 8's own annotation section still recommends `typing.Tuple`, which is a spelling this
standard forbids.

### 10. What a dead-API table may and may not contain

`zig-style`'s `ZS-MIG-14` ships the denylist as one runnable `rg`, and `PS-MIG` should too — but
Python has four categories where Zig had one, and conflating them produces false positives that
teach readers to route around the check:

| Category | Example | In the grep? |
|---|---|---|
| Removed name | `glob.glob0`, `pathlib.PurePath.is_reserved`, `sre_parse` | **Yes** |
| Removed spelling of a live name | `NamedTuple("P", x=int)`, `TypedDict("TD")` | Yes, as a shape |
| `__all__`-only, name still resolves | `collections.abc.ByteString` (real removal 3.17) | Yes, as a warning tier |
| **Soft-deprecated, no warning, no removal date** | `re.match` — *"We do not plan to remove the older `match()` name"* | **No** |

A grep that flags `re.match` as dead is wrong, and being wrong once is how a check loses its
authority. The chapter carries the table with the tier column, and only the first two categories
fail the build.

### 11. Chapter layout, prefix `PS-`, families held to one abbreviation style

Thirteen chapters plus the review protocol, sized against the siblings' measured range (11–15
chapters, 14–84 rules each, 15–66 lines per rule):

| Chapter | Family | Target | Delivered | Rests on |
|---|---|---|---|---|
| `SKILL.md` §4 | `PS-CORE` | ~26 | **26** | all three |
| `references/naming-and-layout.md` | `PS-NAME` | ~38 | **26** | PEP 8, ruff `E`/`N`/`I` |
| `references/typing.md` | `PS-TYPE` | ~48 | **22** | Typing Spec, `ty`, ruff `ANN`/`UP`/`TC` |
| `references/data-modelling.md` | `PS-DATA` | ~36 | **22** | stdlib (`dataclasses`, `enum`, `frozendict`, `sentinel`) |
| `references/errors-and-control-flow.md` | `PS-ERR` | ~34 | **22** | PEP 8, stdlib, ruff `B`/`TRY`/`RET` |
| `references/free-threading.md` | `PS-FT` | ~40 | **26** | PEP 703/779/803, stdlib — **no ruff coverage** |
| `references/async.md` | `PS-ASYNC` | ~32 | **22** | stdlib `asyncio`, ruff `ASYNC` |
| `references/strings-and-output.md` | `PS-FMT` | ~24 | **20** | PEP 686, PEP 750, ruff `G`/`LOG`/`ISC` |
| `references/performance.md` | `PS-PERF` | ~28 | **20** | stdlib, PEP 799, ruff `PERF`/`C4` |
| `references/api-and-modules.md` | `PS-API` | ~40 | **22** | Typing Spec distributing, PEP 810, stdlib |
| `references/documentation.md` | `PS-DOC` | ~26 | **18** | PEP 257, ruff `D` (convention `google`) |
| `references/testing.md` | `PS-TEST` | ~32 | **22** | stdlib, pytest 9, ruff `PT` |
| `references/packaging.md` | `PS-PKG` | ~34 | **22** | PyPA specs, uv, ruff `INP`/`TID` |
| `references/migration.md` | `PS-MIG` | ~16 | **16** | What's New 3.14 / 3.15 |
| `references/review-checklist.md` | — | — | — | — |

This is reading order, not size order, matching how the siblings lay out their reference maps: names
and types first, the language's own hard problems in the middle, testing and shipping late, migration
second-to-last, the review protocol last. The roster above and the reference map in `SKILL.md` §6 are
the same sequence — no dependency between chapters would justify two different orders.

The order the chapters are *written* in is that sequence with exactly one exception: Decision 14
promotes `free-threading.md` to first, because it is the seed the harness is proven against. That is
a build-order decision, not a reading-order one, and it is the only place the two diverge.

That totals ~428 chapter rules plus ~26 core — call the target **440–480**, between `zig-style`'s 435
and `rust-style`'s 769.

*Revised after writing.* The delivered standard is **306**: 280 chapter rules across thirteen
chapters plus 26 core. The 440–480 figure was set by sibling parity during planning and it was the
wrong instrument — `rust-style` and `zig-style` reached their counts over many passes, and a target
set from their totals prices in that history. What was actually built is thirteen chapters that each
cover their domain, sized 16 to 26 rules, inside the siblings' own observed band of 14 to 84. Closing
the gap would mean adding roughly ten rules per chapter that the domain does not ask for, which is
padding — and padding is what a standard whose first design principle is "what can be deleted" exists
to forbid. The count is a consequence of the coverage, not a target the coverage should be bent to.
The band in the acceptance task is corrected to match. No letter-suffixed IDs; the core list is numbered last, after the chapters
are final, so nothing needs renumbering.

`PS-DOC` and `PS-FMT` are split rather than merged, mirroring `RS-DOC` (40) and `ZS-FMT` (20), and
because docstrings now carry a real decision: `convention = "google"` is the only ruff convention
that keeps `D417` (undocumented-param), and not setting a convention leaves `D203`/`D211` and
`D212`/`D213` mutually contradictory, with ruff dropping one and
saying so in a warning that names the rule it ignored.

`references/free-threading.md` is the chapter with no ruff coverage at all and the strongest reason
the standard exists. It has more measured material than any other: `obj.n += 1` across eight threads
loses 72% of its updates and `d["k"] += 1` loses 77%, while the library FAQ's atomicity list still
carries no free-threading caveat; a shared generator raises `ValueError: generator already
executing`; `lru_cache` is coherent but not single-flight; `TextIOWrapper` — and therefore `print`
and the standard streams — is documented not thread-safe; `thread_inherit_context` silently defaults
differently on the two builds; and a free-threaded build can re-enable the GIL at import time,
process-wide and for the life of the process, which `PYTHON_GIL=0` then hides by suppressing the
warning.

### 12. Test configuration is native TOML, and the empty-file trap is a rule

pytest 9.0 added a native TOML table, and pytest 9.1.1 is current. `[tool.pytest]` takes real TOML
types — arrays, booleans, integers — where `[tool.pytest.ini_options]` takes INI strings that each
option parses itself. The two **cannot coexist**; pytest errors out and names its own preference:

```
Cannot use both [tool.pytest] (native TOML types) and [tool.pytest.ini_options] (string-based INI
format) simultaneously. Please use [tool.pytest] with native TOML types (recommended) or
[tool.pytest.ini_options] for backwards compatibility.
```

So `assets/pyproject.toml` ships `[tool.pytest]`, and `PS-TEST` states the native table as `[M]` with
the tool's own error as the check. A standalone `pytest.toml` is the alternative for a project with
no `pyproject.toml`.

The part that earns a rule of its own is the discovery order. `pytest.toml` and `.pytest.toml` win
over `pytest.ini`, `.pytest.ini`, `pyproject.toml`, `tox.ini`, and `setup.cfg` — **even when empty**,
and configuration files are never merged, first match wins. So an empty `pytest.toml` discards a
fully-configured `pyproject.toml`.

It is not silent, and the rule must not claim it is: pytest prints
`configfile: pytest.toml (WARNING: ignoring pytest config in pyproject.toml!)` in the session header.
That makes it a precedence trap rather than a silent-behaviour change — one line in a header nobody
reads, which is a different and lesser hazard. It belongs in `PS-TEST` with the warning quoted, and
**not** in the `SKILL.md` §2 reality check, which is reserved for changes that produce no diagnostic
at all.

`PS-TEST` also takes the 9.0 `strict` umbrella (`strict_config`, `strict_markers`,
`strict_parametrization_ids`, `strict_xfail` in one option), subtests as the alternative to
parametrization where the cases are not a product, and the argument-deduplication change — `pytest a/
a/b` now means `pytest a`, with `--keep-duplicates` restoring the old behaviour. CI detection now
requires `$CI` or `$BUILD_NUMBER` to be defined **and non-empty**, which is a silent behaviour change
for anyone exporting `CI=`.

`PS-MIG` carries pytest's own removal ladder: `PytestRemovedIn9Warning` became an error in 9.0 and
the features went in 9.1, and 9.1 opened `PytestRemovedIn10Warning` on class-scoped fixtures as
instance methods, `request.getfixturevalue()` during teardown, non-Collection iterables in
`parametrize`, `config.inicfg`, `--pastebin`, and `pytest.console_main()`.

### 13. `SKILL.md` follows the anchor skeleton, not the delta one

All three siblings share H1 → `How to use this standard` → §1 Tiers → §2 reality check → §3 → §4 Core
rules → §5 → §6 Reference map, numbered identically. `bevy-style` diverges at §3 (it substitutes the
delta-override table), truncates §5, and omits §7 — divergences that belong to being a delta, and two
of which read as omissions.

`python-style` is an anchor, so it takes the `rust-style`/`zig-style` shape throughout: a real
§3 **Design principles**, a full §5 **Review checklist** with `references/review-checklist.md` behind
it, and §7 **Bundled assets**.

§3's axis is Python's own: **`## 3. Design principles — one obvious way, and symmetry`**. PEP 20 is
already a chosen source and supplies the first half; the second is what `rust-style` established and
what the `mirror` check compares across skills. It closes with the five-question tie-breaker both
siblings carry, in Python's terms — what can be deleted, what can be made unrepresentable in the type
system, what can be a value rather than an effect, what is asymmetric, what is special-cased.

### 14. A walking skeleton first, because the checker has no partial-credit mode

The README records 210 Zig blocks claiming `// verified` where 61 actually compiled, so the harness
must exist before the rules. But the obvious ordering — harness, then skeleton, then chapters — is
circular, and the checker says so:

- `model.discover` only sees a directory once it contains `SKILL.md`, so nothing written under
  `skills/python-style/assets/` is checkable until the skill exists.
- `checks/controls.py` copies the tree and injects a defect; with no skill there is nothing to
  inject into.
- `anatomy` sums the per-family counts in the reference map and fails unless they equal the rules
  actually present; `frontmatter` fails unless the stated `<N>-rule` count equals them too. Both are
  wrong at every intermediate state, not just at the end.

So the first deliverable is a **walking skeleton**: a `SKILL.md` with all seven sections, one real
chapter, a reference map whose counts are right, and a frontmatter count that matches — a skill that
is check-clean while being almost empty. `free-threading.md` is that chapter, because it has the most
examples that are hard to verify. Every later chapter updates the reference map and the frontmatter
count in the same commit that adds it, which is the only state the checker accepts.

The profile is the one piece that precedes even the skeleton. `profile_for` falls back to a guessed
`Profile` with no `languages` for an unregistered skill, and an empty `languages` makes `all_marked`
empty, which makes `markers`, `selfapply` and `conventions` iterate nothing — a skeleton that reports
green because nothing looked at it. So: profile, skeleton, harness, chapters.

The harness is built against that skeleton, and only then do the remaining twelve chapters land.

### 15. Diagnostics decide; the exit code only corroborates

An earlier draft gated `ty` on its exit status. That is the defect the README already records: *"`clippy` was reported clean because half the shipped lint table is `warn` and clippy exits 0 on a
warning."* `specs/python-verification/spec.md` forbids it outright — *when the tool's exit status is
zero but its output contains diagnostics, the check reads the diagnostics rather than the exit
status.*

So every tool is read the same way: parse the diagnostics, and treat a non-zero exit with no parsed
diagnostic as its own finding — that combination means the harness failed to understand the output,
which is worse than either a pass or a fail. `ty`'s exit code happens to be trustworthy today
(`error-on-warning` has defaulted true since 0.0.52), and that is exactly the kind of fact a pinned
beta tool can change without telling anyone.

### 16. The verification configuration is declared twice, or the invariant checks nothing

An earlier draft had verification run *under* `assets/ty.toml` and `assets/ruff.toml`, and then
claimed to check that the asset equals the configuration verification runs under. That comparison is
unreachable: the asset would be both sides of it.

The working model is already in the tree. `lang/rust.py::Crate` declares its lint table in Python;
`checks/lints.py` reads the shipped `Cargo.toml` separately and compares the two, which is how it
caught an asset shipping `indexing_slicing = "warn"` where a rule required deny. Python follows it:

- The **harness** holds its own declaration of the ruff selection and the `ty` rule levels.
- The **assets** are written independently, as the thing a reader copies.
- The check compares them, in both directions, and a divergence is a failure.

Verification runs under the harness's declaration. The asset is data to be checked, never the
configuration in force.

### 17. The checker surface is roughly half this change

The audit of `src/agent_skill/` found the Python toolchain reaches well past a new `lang/` module.
Naming them here so the task list can carry them rather than discovering them one failure at a time:

| File | Why it must change |
|---|---|
| `model.py` | `MARKERS` is a module-global tuple; the vocabulary moves onto `Profile` |
| `checks/markers.py` | builds `LEADS` from that tuple |
| `text.py` | `strip_comment` breaks on `//`; in Python that is floor division, so `q = total // count` truncates to `q = total ` and `#` comments survive into the code corpus |
| `checks/selfapply.py` | `FILE_ARG` does not match `*.py` or the TOML assets, so a Check's own filename arguments become patterns — and a command-kind hit is a hard failure |
| `checks/layout.py` | its doubled-blank test reads any `#` line as a heading without tracking fences — harmless for `//` languages, wrong for Python, where `ruff format` legitimately puts two blank lines before a top-level comment (found during apply) |
| `checks/mirror.py` | `ANCHOR, MIRRORED = "rust-style", "zig-style"` is hardcoded; it never reads a third skill |
| `checks/controls.py` | its empty-corpus guard iterates `("rust-style", "rust"), ("zig-style", "zig")` literally |
| `checks/__init__.py` | a check is unreachable unless its module is imported in `all_checks` |
| `checks/toolchain.py` | probes one tool via `shutil.which`, which cannot see a uv-resolved interpreter; and `mutation` calls `tc.mutate` unconditionally, so a toolchain without it raises `AttributeError` inside a check with no `try` |
| `fmt.py` | returns early on `profile.crate is None` |
| `report.py` | has `FAIL` and `NOTE` and nothing that means *could not run* |
| `lang/__init__.py`, `profiles/__init__.py`, `cli.py`, `README.md`, `pyproject.toml` | registration, the profile contract, help text, docs, dev pins |

`README.md` also carries two statements this change falsifies: that a profile naming a `toolchain`
also names the `Crate` its examples compile as, and a three-line marker legend.

### 18. One tool per role, all four Astral, and `uv_build` is the reason the scope is pure Python

The standard names four roles — resolve/lock, build, lint/format, type-check — and fills each with
exactly one tool: `uv`, `uv_build`, `ruff`, `ty`. No role is presented as a choice. A standard that
says "`hatchling` or `uv_build`" has not made the decision, it has moved it to the reader, and the
reader has less information than the standard does.

`uv_build` went stable on 3 June 2026 and is what `uv init` produces. It **only supports pure
Python** — it cannot build extension modules, and Astral's own documentation sends those projects to
another backend. That limitation is not a cost here, it is the scope decision made concrete: the
standard's subject is pure Python, so a backend that refuses to build anything else is a backend
that cannot silently carry the reader out of scope.

The pin carries an upper bound — `uv_build>=0.12.6,<0.13` — because the backend follows uv's
versioning policy and may break across minor versions. This does not contradict `PS-PKG-04`'s
floor-and-no-ceiling rule: that rule governs `requires-python`, which is a claim about interpreters
the author cannot test, while this is a build-time dependency the author does test.

Two things fall out of the choice that are worth stating. Distribution name and module name must
match — `acmewidget`, not `acme-widget` — or every backend needs an explicit override to find the
package; with them matched, both the metadata and the layout are inferred and the `[build-system]`
table is the only thing that distinguishes one backend from another. And `pip`, `python -m build`,
and the `pylock.toml` export leave with `hatchling`: an export nobody in the mandated toolchain
consumes is a second source of truth maintained for a reader the standard no longer serves.

### 19. Extension modules are out of scope, and the consumer-side GIL fact stays

No chapter covers authoring, building, or distributing compiled extensions, and `PEP 803`'s `abi3t`
is not taught despite being 3.15's most consequential packaging addition for free-threaded builds.
That is a real cost, accepted deliberately: `abi3t` is an extension-author's concern, and an
extension author is not this standard's reader.

What does **not** leave is the fact a pure-Python reader still needs: a free-threaded build can
re-enable the GIL at import time, permanently and process-wide. That is the answer to "why is my
free-threaded program not running in parallel", and it is a consumer-side observation about a
program's own behaviour, not an instruction for writing extensions. `PS-FT-01` keeps it and states
it without naming the C-API slot that causes it, because the reader who needs the fact cannot act on
the slot and the reader who can act on the slot is out of scope.

## Risks / Trade-offs

- **3.15 is at rc1 only until 1 September 2026, when rc2 lands; final is 1 October, and the
  What's New is marked draft until then.** → The pin is one string
  in one asset and one line in the toolchain, and a task covers re-verifying against 3.15.0 final.
- **`ty` is mandated while being beta, `0.0.x`, shipping every two to five days, and stating that
  diagnostics may change between any two versions.** This is the largest deliberate risk in the
  change, and mandating it raises the stakes rather than lowering them: a reader who adopts the
  standard adopts the pin. → Exact pin, enumerated rule table rather than `all`, Decision 0's
  invariant, and an `[M]` rule in `PS-TYPE` that states the version policy and the bump procedure
  instead of leaving a reader to discover it. The exposure is bounded by the claim/check separation:
  every rule is justified from the Typing Spec, so a `ty` release can invalidate a *citation* but
  not a *rule*. A rule forbidding `ty`'s non-standard intersection types keeps that boundary from
  eroding in the direction the mandate makes tempting.
- **`ty` output has no SARIF form and no `json` on `check`.** The four machine formats
  (`concise`, `gitlab`, `github`, `junit`) each do preserve severity — `gitlab` is JSON and uses
  `minor`/`major`, `github` uses `::warning`/`::error`, `junit` carries a `severity` property. →
  `concise` is chosen for being the cheapest stable line format to parse, not for being the only one
  that keeps severity, and per Decision 15 the diagnostics decide rather than the exit code.
- **Ruff changed its default rule set from 59 to 413 in 0.16.0, and prints rule names rather than
  codes under preview.** → `select` is used to replace wholesale rather than `extend-select`, and
  `output-prefer-rule-codes = true` is pinned so the harness parses codes.
- **Ruff's `TC001`–`TC003` at py314+ move imports into `TYPE_CHECKING` and leave the annotation
  unquoted**, which is correct for a checker and breaks anything resolving annotations at runtime. →
  The shipped config sets `runtime-evaluated-base-classes` and `runtime-evaluated-decorators`, and
  `PS-TYPE` states the hazard rather than leaving it to the config.
- **Executing example code has side effects.** → Isolated temp working directory, a timeout, and
  network- or clock-dependent blocks demoted to `# fragment`.
- **Running every block through an interpreter, `ty`, and `ruff` is slower than compiling a crate,
  and `check --fast` will not save you.** `cli.py` skips only checks marked `slow`, and
  `checks/controls.py` is not one — it re-runs each owning check per control, so a control for a slow
  Python check executes the interpreter, `ty` and `ruff` inside `--fast`. Meanwhile
  `tests/test_controls.py` exempts only `controls`, `toolchain` and `mutation` from needing a
  control. → Either `controls` learns to skip controls whose owning check is slow, or the new checks'
  controls join that exemption set. The task list picks the first; the second hides a check from its
  own control, which is the thing `controls` exists to prevent.
- **Free-threading numbers are a moving target and the official ones are optimistic.** The docs say
  1–8% single-threaded overhead; the daily benchmark runs have sat at 9–11% on Linux x86_64 for
  seventeen months, and memory is 1.19–1.22x, at PEP 779's ceiling. → `PS-PERF` and `PS-FT` cite the
  dashboards and the measurement date rather than the doc sentence, and state the shape (allocation-
  and refcount-heavy code pays most; `asyncio` is at parity; the JIT is unavailable on free-threaded
  builds entirely) rather than a single number that will be stale by 3.16.
- **pytest 9 is required by four chapters and installed by nothing.** The repo's dev group floors at
  `pytest>=8`, resolves into the 3.14t venv, and the examples run on 3.15t. → The pinned interpreter
  gets its own `pytest==9.1.1`, and the repo's own `[tool.pytest.ini_options]` — the very table
  `PS-TEST` will forbid — is being migrated separately.
- **Two sources will contradict each other where Ruff has an opinion and PEP 8 does not, or the
  reverse.** → The specs require the disagreement to be stated in the rule. A writing cost on every
  affected rule, not a design hole.

## Migration Plan

Additive; nothing existing changes behaviour for the three existing skills. Sequencing is the part
the checker constrains, per Decision 14:

1. **Checker surface** — the Decision 17 table: the marker vocabulary onto `Profile`, `strip_comment`
   taught Python, `FILE_ARG`, `mirror`, the empty-corpus guard, `report.py`'s third outcome, the
   `mutate` and tool-probe paths in `toolchain.py`. The three existing skills must stay byte-identical
   and check-clean throughout; that is the regression test for this step.
2. **Walking skeleton** — `SKILL.md` with all seven sections, `free-threading.md`, matching reference
   map and frontmatter counts, and the four assets. Check-clean while nearly empty.
3. **Harness** — `lang/python.py`, `profiles/python_style.py`, the two equality invariants, `fmt`,
   and a negative control per new check, all proven against the skeleton.
4. **The remaining twelve chapters**, in the Decision 11 order, each updating the reference map and
   the frontmatter count in the same commit.
5. `PS-CORE` numbered last; review protocol; `README.md`; CI.
6. **After landing**, move the pin twice: `3.15.0rc2` on 1 September 2026 and `3.15.0` final on 1
   October. This is maintenance of the delivered artefact rather than part of delivering it, so it
   does not sit in the task list — `checks/pins.py` fails the moment either release appears and its
   message carries the procedure, which is the same information without depending on anyone
   remembering a date.

Rollback is deleting `skills/python-style/` and reverting the checker additions. The checker changes
are the part that is not trivially reversible, which is why step 1 keeps the existing skills as its
control.

## Open Questions

- Whether `python-style` should later anchor a framework delta the way `rust-style` anchors
  `bevy-style`. Deferrable: it changes nothing here, and the `crossref` check already supports the
  relationship.
- Whether `PS-DOC` mandates `convention = "google"` outright or permits `numpy` for
  scientific projects. Deferrable to the chapter: the adoption evidence is roughly 79% google to 16%
  numpy, split cleanly by domain rather than by recency, and either way the rule must state that a
  convention has to be chosen because not choosing one leaves contradictory rules enabled.
