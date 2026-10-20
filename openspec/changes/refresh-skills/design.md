## Context

See `proposal.md` for the motivation. The requirements are in `specs/standard-structure`,
`specs/python-style` and `specs/check-execution`. This document covers how the work is done and in
what order.

The research behind the version work is in `research/`, one file per subject, with a source for
every claim. Items marked UNCONFIRMED there stay unconfirmed until the apply step checks them.

- `bevy-0.20.md`:
  - 38 rule impacts, nine of which change behaviour while still compiling;
  - four new forbidden-API rules, each with a tested `rg`;
  - the pins;
  - the status of `bevy_lint`;
  - the lint classification.
- `python-3.15.0.md`:
  - what changed between rc1 and final;
  - the uv key;
  - the ruff 0.17.1 and ty 0.0.89 deltas;
  - claims that are now stale;
  - the lint classification.
- `rust-1.99.md`: what changed in each release from 1.85 to 1.99, nine required fixes, the §2
  additions, and the lint table.
- `rust-lints-1.md` and `rust-lints-2.md`: the lint classification of every Rust rule, plus
  pointers, duplicate pairs and long Why sections.

The state these decisions start from:

- `pins` fails today, and only on `ruff`, `ty` and the interpreter. Every other fast check passes.
  So any red check after a step was caused by that step.
- Rule IDs appear outside the skills. Profiles, controls and tests cite 41 `RS-`, 27 `PS-` and
  24 `BV-` IDs, and `bevy-style` cites 12 `RS-` IDs. None appear in `openspec/specs/`.
- Only `zig-style` uses `does-not-compile` (23 blocks). `python-style` already declares
  `verified` / `fragment` / `rejected` in its profile, and has no `rejected` blocks.
- What the research says about lint rows: few rules collapse completely. Rust has about 40 of 770,
  Python 45 of 305, and Bevy 11 of 249, only 5 of which the shipped config enables. Most of the
  size saving therefore comes from the Why cap and from merging duplicates, not from the lint
  tables.

  | Skill | Why longer than 3 lines | Pointer rules | Duplicate pairs found |
  |---|---|---|---|
  | rust-style | 105 | 4 | 7 |
  | python-style | 182 | 0 | — |
  | bevy-style | 171 | 6 | — |

## Goals / Non-Goals

**Goals:**

- Every requirement in `specs/standard-structure` is decided by a check, and each check has a
  control that proves it fires.
- Each conversion step starts from a clean run. The full suite runs once at the end of each step,
  with nothing else running.
- Every rename is mechanical, so no citation is rewritten by hand.

**Non-Goals:**

- `zig-style` content, and its file names, codes and markers. They come with its own bump, once
  `zig version` moves.
- Running `rejected` blocks to prove that the named tool rejects them. The three converted skills
  have no `rejected` block, so a guarantee added now would apply to nothing. That is the failure
  `harness-integrity` forbids.
- Templating the frontmatter `description`. It is each skill's trigger text and stays its own.
- Rewriting the archived OpenSpec changes, which cite old IDs as history.

## Decisions

### D1. Order: harness and Python together, then Rust, then Bevy

There are three milestones. Each ends with the exemption for that skill removed and one full run.
The harness lands in the same milestone as `python-style` because the new checks need at least one
conforming subject. A check that skips every skill applies to nothing, and its controls would have
nothing to inject into. `python-style` is the smallest skill, so it goes first.

Every skill starts exempt, `python-style` included. While it is half-converted, it would otherwise
already fail every new check, and a control injected into it would "fire" on a defect that was
already there. So the harness groups are tested against fixture inputs. The controls on the real
tree land once `python-style` conforms and its exemption is removed. `rust-style` and `bevy-style`
stay exempt until their own milestones, and `zig-style` stays exempt.

*Alternative:* land the harness against a synthetic fixture skill. That only moves the problem: the
fixture would be the one subject every guarantee holds of, and it is not a standard anyone reads.

### D2. The exemption is a profile field with a reason

`Profile.exempt_from_structure` is either `None` or a reason string. The structure checks skip an
exempt skill. They also run on it once more in a dry run: if that run finds nothing, they report
that the exemption has outlived its reason. An exemption with an empty reason fails. This is the
pattern `harness-integrity` already uses for checks that have no control.

### D3. One vocabulary table for files and family codes

The table lives once in the package. A standard's chapter file name must be a key in the table, and
every rule in that file uses the code the table gives. Rows are only ever added. Zig's bump will add
`memory`, `assertions`, `comptime` and `interop` rows rather than renaming any.

| File | Code | rust-style (was) | python-style (was) | bevy-style (was) |
|---|---|---|---|---|
| `naming.md` | `NAME` | `naming` `RS-NAM` | `naming-and-layout` `PS-NAME` | |
| `api.md` | `API` | `api-design` `RS-API` | `api-and-modules` `PS-API` | |
| `errors.md` | `ERR` | `errors` `RS-ERR` | `errors-and-control-flow` `PS-ERR` | `errors` `BV-ERR` |
| `functional.md` | `FUNC` | `functional` `RS-FP` | | |
| `ownership.md` | `OWN` | `ownership` `RS-OWN` | | |
| `traits.md` | `TRAIT` | `traits-generics` `RS-TRG` | | |
| `types.md` | `TYPE` | | `typing` `PS-TYPE` | |
| `data.md` | `DATA` | | `data-modelling` `PS-DATA` | |
| `modules.md` | `MOD` | `structure` `RS-STR` | | |
| `concurrency.md` | `CONC` | `concurrency-async` `RS-CNC` | `free-threading` `PS-FT` | |
| `async.md` | `ASYNC` | | `async` `PS-ASYNC` | |
| `output.md` | `OUT` | | `strings-and-output` `PS-FMT` | |
| `performance.md` | `PERF` | `performance` `RS-PRF` | `performance` `PS-PERF` | |
| `testing.md` | `TEST` | `testing` `RS-TST` | `testing` `PS-TEST` | `testing` `BV-TST` |
| `documentation.md` | `DOC` | `documentation` `RS-DOC` | `documentation` `PS-DOC` | |
| `build.md` | `BUILD` | `cargo-toolchain` `RS-CAR` | `packaging` `PS-PKG` | `cargo` `BV-CAR` |
| `unsafe.md` | `UNSAFE` | `unsafe-ffi` `RS-UNS` | | |
| `cli.md` | `CLI` | `cli-apps` `RS-CLI` | | |
| `macros.md` | `MACRO` | `macros` `RS-MAC` | | |
| `migration.md` | `MIG` | *new* | `migration` `PS-MIG` | `migration` `BV-MIG` |
| `architecture.md` | `ARCH` | | | `architecture` `BV-ARC` |
| `ecs.md` | `ECS` | | | `ecs` `BV-ECS` |
| `scheduling.md` | `SCHED` | | | `scheduling` `BV-SCH` |
| `events.md` | `EVENT` | | | `events` `BV-EVT` |
| `state.md` | `STATE` | | | `state` `BV-STA` |
| `assets.md` | `ASSET` | | | `assets` `BV-ASS` |
| `view.md` | `VIEW` | | | `ui-render` `BV-UI` |
| `review-checklist.md` | — | ✓ | ✓ | *new* |

Some names were judgement calls:

- **`build`, not `cargo` or `packaging`.** It is the one concept three standards share, and the
  language-neutral word is what lets them share it.
- **`concurrency`, not `free-threading`.** Python's chapter is about threads and shared state, which
  is what Rust's `concurrency` covers. `async` stays separate because Python separates it.
- **`view`, not `ui-render`.** `bevy-style` already calls this "the view layer", and `view` covers
  both UI and rendering in one word.

*Alternative:* allow two-word names that are "one concept". A check cannot tell `free-threading`
(one concept) from `traits-generics` (two). A table can.

### D4. Shared text: a template with short slots and declared free regions

The template is markdown under `src/agent_skill/shared/`. It has one file per shared passage:

- in `SKILL.md`: the reading procedure, the tier table with its opening and closing lines, the
  marker legend, the ID-citation and pointer paragraphs, and the intro paragraphs of §6 and §7;
- in `review-checklist.md`: the severity table and its blocking paragraph.

There are three kinds of content:

- **`{slot}`** is a short value the profile declares: language name, target, comment token, ID
  examples, required tools, the strict-tier scope noun, the anchor standard, and the delta step.
- **A line that is just `…`** is a free region. The standard writes its own paragraphs there. The
  definition of what counts as "library or high-reliability" is the main example; it is real
  content and belongs to the skill, not to a Python string.
- **Everything else** must appear verbatim, in order.

Paragraphs are compared with whitespace collapsed, because a filled slot changes where the lines
wrap. `agent-skill fmt` re-renders each passage, rewraps it to the `layout` width, and keeps the
free regions.

The places where the standards now differ by accident are normalised in the template:

- Rust says "several entries silently change behaviour", Python says "most of its entries".
- Bevy has no closing line under its tier table.
- The §6 table columns appear in two orders.

*Alternative:* HTML-comment markers around each shared passage in `SKILL.md`. That costs every
reader tokens to delimit something the template already delimits.

### D5. The skeleton check owns structure, nothing else

`skeleton` checks the following:

- the H1 form, and that its target is the major.minor of the subject's pin (rust → `Crate`
  `rust_version`, python → the interpreter, bevy → the `bevy` dependency, zig → its compiler pin);
- the eight H2s;
- chapter names against D3, and family codes against D3;
- that the two required chapters are present;
- the H2s of `review-checklist.md`: `Severity model`, `Review order`, `Mechanical pass`,
  `Output format`, `Refactoring a codebase to this standard`;
- the severity labels against D8;
- that the numbered items of §5 are, in order, the stage titles under `Review order`;
- the column order of the §6 table: `File | Rule IDs | Covers`.

The §5 rule removes a drift `rust-style` already has: its §5 lists 14 items, and its protocol lists
nine stages.

`shared-text` is a separate check, so each has its own control. A skeleton defect then never
satisfies a shared-text control, which `harness-integrity` requires.

### D6. Lint-table rows

A chapter that has rows ends with this section:

```markdown
## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `unwrap_used` | deny | `unwrap()` outside tests |
| ruff | `B006` | error | a mutable default argument |
```

The chapter's contents list ends with a `- Decided by tools` line. It carries no count, because a count nothing re-measures goes stale. `model.py` parses the rows
into `Chapter.lint_rows`, and the rows are not rules for `anatomy`. They are verified the way
citations already are:

- **ruff and ty:** the existing `citations` machinery. The code must exist in the pinned catalogue,
  and the shipped asset must enable it at the stated level.
- **rustc, clippy and rustdoc:** new in milestone 2. The catalogue comes from `rustc -W help`,
  `clippy-driver -W help` and `rustdoc -W help`. The effective level is the asset's explicit entry,
  or else the level of the group the lint belongs to. A `rustdoc` row needs an explicit
  `[workspace.lints.rustdoc]` entry in the asset. That way all three tools are checked against one
  table. It also lets `ci.yml` drop `RUSTDOCFLAGS: -D warnings`, which the research found redundant
  with `CARGO_BUILD_WARNINGS=deny`.

A rule becomes a row only if the shipped configuration enforces its lint once this change is done.
Where the research says a row needs a setting, the setting is shipped and the row follows. Rust
needs a `clippy.toml` with `avoid-breaking-exported-api = false`, `allow-unwrap-in-tests`,
`allow-expect-in-tests` and `upper-case-acronyms-aggressive`. A lint that is preview-only, or
nightly-only, stays cited in a rule's Check and is not a row.

### D7. Why length

A Why may take at most three non-blank lines inside `Rule.why`, at the existing 100-column width.
Lines are counted as they appear in the file, so `fmt` cannot hide length by reflowing. Exempt
skills are not measured.

### D8. One severity model

The severity labels, their order and the blocking rule are shared across every standard. Each
standard writes its own examples column.

| Severity | Meaning |
|---|---|
| **Unsound** | Corrupts memory or data, or crashes the runtime, from code that looks safe |
| **Stale** | A spelling the target superseded — fails to build, or worse, builds and means something else |
| **Incorrect** | Produces wrong results or crashes on reachable input |
| **Contract** | Breaks or under-specifies the public surface |
| **Design** | Works, but the shape will cost later |
| **Performance** | Measurable, avoidable cost |
| **Style** | Idiom and readability |

The blocking rule:

- Unsound, Stale and Incorrect block a merge.
- Contract blocks a release.
- Design and Performance need a decision, not necessarily a change.
- Style findings are batched.

This changes each existing model a little:

- Python's **Silent** label merges into **Stale**, whose meaning ("builds and means something else")
  is what Silent covered.
- Rust gains **Stale**, for pre-2024 idioms and crates that std has replaced.
- Zig's **Illegal** becomes **Unsound** when Zig converts.

### D9. Markers

The default `MARKERS` becomes `verified` / `fragment` / `rejected`. The rejected form is
`rejected — <tool>: <reason>`, and `markers` checks that `<tool>` is in `Profile.tools`:

- rust and bevy: `rustc`, `clippy`;
- python: `python`, `ty`, `ruff`.

`zig-style`'s profile keeps `does-not-compile` as its declared vocabulary until its bump. That is
the D2 exemption for markers.

### D10. Renumbering is a command, run twice per skill

`agent-skill renumber <skill> [--chapters old=new …]` does the whole renumbering in one operation:

- It parses the current tree and computes the new layout. Files are renamed per `--chapters`,
  codes come from D3, and rules are numbered densely in their current order.
- It rewrites every `<PREFIX>-<CODE>-<NN>` and every `references/<file>.md` in `skills/`, `src/`,
  `tests/` and `README.md` in **one pass**, from a dictionary built from the old numbering. A pass
  that chained replacements (03→02, then 02→01) would corrupt any ID that is both an old and a new
  number, which dense numbering makes routine.
- It verifies by identity. Each citation's target title before the pass must equal its title after.
  Titles are already unique, which `anatomy` enforces.
- It writes everything or nothing, and on any failure it leaves the tree untouched.
- It composes into the table in `migration.md` (`## Rule IDs before the <target> revision`,
  columns `Before | Now`). An existing row whose `Now` is renumbered gets the new value. Every ID
  defined before the run must end up in the `Before` column.

Per skill, the command runs twice:

- **Step A — first, mechanically.** It moves files and codes and renumbers densely before any
  content is touched, so identity is purely positional.
- **Content edits.** These include demotions, merges, pointer removal and deletions. Each removed
  rule's row is edited by hand to its disposition: a new ID, `` lint `tool:name` ``, or
  `removed — <reason>`.
- **Step C — last.** It closes the gaps, composing onto the rows step A wrote.

Between the two runs, `skeleton` verifies that every `Now` value resolves to a rule or a lint row.
That catches a deleted rule whose row was not edited. Per `standard-structure`, nothing can catch a
stale ID typed in by hand later, and the README says so.

*Alternative:* match rules across one large edit by title. Trimming changes titles, so that is the
one match that cannot be trusted.

### D11. Pins for every target

There are three new pin kinds, each built on the comparison `pins` already performs:

- **Rust toolchain:** the `rust_version` on `Crate`, at major.minor. It is checked against
  `rustc -V`, and against the stable channel manifest (`static.rust-lang.org`). When the manifest
  cannot be reached, the check reports not-run.
- **Bevy crate:** the `bevy` requirement in the crate's dependency line. It must be exact (`=x.y.z`),
  which is what makes the running-version direction hold. It is checked against crates.io's newest
  stable release.
- **Zig compiler:** `0.16.0`, declared local-following with the reason "follows this machine's
  `zig`; bumped with the skill, never ahead of it". It is checked against `zig version` only.

The existing tools (`ruff`, `ty`, `pytest`, `rg`) and the interpreter pin are unchanged in
mechanism, and only move their values.

### D12. Pointer rules and duplicates are removed

For the three converted skills, pointer rules (`Owned by …`) are deleted. The owning rule stays,
and the rename table points the pointer's old ID at it. The research also found pairs where two
rules say one thing. Each pair keeps one owner, and the other's ID maps to that owner. The pointer
machinery in `anatomy` stays, because `zig-style` still uses it.

## Risks / Trade-offs

- **A citation rewrite corrupts an ID.** → The single-pass dictionary rewrite (D10), the
  before/after title comparison, and an all-or-nothing write. The step C run on a clean tree is also
  a dry rerun of step A's verification.
- **The Rust pin goes red every six weeks.** 1.100 is due on 2026-11-12. → The `check-execution`
  spec intends this: moving a pin is a reviewed event. It costs one line plus the §2 entries that
  release earns.
- **Template paragraphs read as generic.** → Free regions keep the skill-specific definitions in
  the skill. The template holds only what was already nearly identical.
- **Python and Bevy lose most of their long Why sections.** → Excess text moves into the statement
  or an example before anything is deleted. A Why that cannot be shortened usually means two rules
  are sharing one heading, and they are split.
- **`bevy_lint` supports no Bevy after 0.18.** → The CI job stays disabled, and says why, naming
  the open support PRs. No nightly is pinned for a linter that cannot load the engine.
- **CPython 3.15.0's thread-safety page contradicts PS-FT-05 on `L.sort()`.** → The rule is
  rewritten against the new page, and §2.2's quote, which was deleted upstream in rc3, is replaced.
  This is a correctness fix, not a trim.
- **The full suite takes about 70 minutes and must run alone.** → It runs three times, once per
  milestone. `pgrep -f "pytest|cargo test|zig test"` comes first, and the full output is captured.
  If a failure set changes between runs, treat it as contention until proven otherwise.
- **Readers outside this repository cite old IDs.** → Every standard's `migration.md` carries the
  table, and the installed skills are symlinks, so the table arrives with the change.

## Migration Plan

The work happens on branch `skill-refresh`, with one commit per task group, so any milestone can be
reverted on its own.

1. Milestone 1 (harness + python). Ends with one full run.
2. Milestone 2 (rust). Ends with one full run.
3. Milestone 3 (bevy). Ends with one full run.
4. Close: README, `agent-skill build`, `openspec validate --strict`.

To roll back, revert the milestone's commits. The installed skills are symlinks into `skills/`, so
they follow the checkout.

## Open Questions

- Which nightly `bevy_lint` will need for 0.20 (UNCONFIRMED; PR #943 proposes
  `nightly-2026-05-28`). This matters only once a release exists. Until then the CI job stays off.
- Whether Rust 1.100 ships the never type and `Allocator`. If it lands during this change, it is
  the next pin bump, not this one.
