## Context

See proposal.md for motivation. The state this design builds on:

- **One parser, one printer.** The harness reads every markdown file into one tree, and `fmt` is
  `print ∘ parse`. The chapter layer reads chapters, rules, `Decided by tools` rows, migration
  tables and a delta's departures table (`Departure`: anchor rule, relation, delta rule, tier,
  reason).
- **`revise` is the one ID-changing operation.** It merges, demotes, removes, renumbers and renames
  chapters. It rewrites every rule ID in the repository at once, as one permutation, and refuses any
  rewrite that would capture a citation. Its laws are property-tested on copies of the shipped tree.
  It has no move: Phase C moved rules by copying them into a new chapter and merging the original.
- **`Mirror`** (`profiles.record`, `checks/mirror.py`) holds title-keyed pairs against rust-style
  only: zig-style 12, python-style and bevy-style none. It has six branches: five FAIL, one NOTE.
- **Section 3** of python-style, rust-style and zig-style lists five design questions. bevy-style's
  section 3 is its departures table.
- **The vocabulary** (`vocabulary.CHAPTERS`) maps a chapter word to its family code. It says nothing
  about which words two standards share.
- **Tools available here:**
  - `claude` 2.1.319, which has `plugin eval`;
  - OpenSpec CLI 1.16.0. 1.16.1 was published on the day this was written, inside the seven-day
    cooldown PS-BUILD-11 states, so it is not used.
  - Node 22.
  - GitHub Actions cannot run here: the repository's workflow first runs on the pull request.

## Goals / Non-Goals

**Goals:**

- One representation of every shared concept, and one map from it to each standard, of the type a
  delta's departures already have.
- A concept's address (chapter and family) the same in every standard that has it.
- An eval suite that is a function of the standards, ready for the owner to run.
- The repository holding itself to the assets it ships: pinned actions and its own CI.

**Non-Goals:**

- Running the eval suite. The owner decided this; no task spends a model run on it.
- Shipping the abstract standard to readers. A skill still installs and reads alone. The abstract
  standard is the harness's and the authors'.
- Merging the standards into one document, or generating rules from the abstract statements. A
  realising rule keeps its own Why, Check and examples in its own language.
- Bevy-specific concepts in the abstract standard. A delta realises concepts through its anchor, and
  its domain chapters are its own.

## Decisions

### 1. The abstract standard is a document in the standards' own form

The abstract standard lives under `abstract/` at the repository root, one file per abstract chapter,
named from the vocabulary (`abstract/errors.md` holds `AS-ERR-*`), plus `abstract/principles.md`
for the design questions. A chapter follows the chapter template. An entry is rule-shaped:

```markdown
### AS-ERR-03 [M] An error carries the context its caller lacks

<statement: one paragraph, no inline code>

| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
| python-style | PS-ERR-07 | realises | [M] | |
| rust-style | RS-ERR-12 | realises | [M] | |
| zig-style | ZS-ERR-05 | overrides | [S] | An error value carries no payload; the context is logged where it is known |
```

It is read by the same parser and chapter layer. A profile-shaped record (prefix `AS`, no
toolchain) lets `revise`, `fmt` and `measure` treat it as a standard. An entry has no Why, Check or
example. Those are each realisation's, in its own language.

Alternatives rejected:

- **A Python table in the harness.** It is a second representation of what is prose. An author
  could not review it beside the rules, and `fmt` could not print it.
- **A `Concept:` line in every realising rule.** It spreads one statement across three files. It
  cites a document an installed skill does not have, which the "no shipped file cites the abstract
  standard" requirement forbids. And it leaves `absent` with nowhere to live.
- **A fifth skill.** It would install with the plugin, and a model given it learns nothing a
  language standard does not tell it better.

### 2. A realisation is a departure, and the relation type is shared

The realisation row and the delta's departures row are one type, and their relation is one enum in
`ids` (`Relation`):

| Relation | Rule cell | Tier |
|---|---|---|
| `realises` | a rule | equal to the entry's |
| `extends` | a rule | equal; the rule's domain is wider than the entry's |
| `tightens` | a rule | higher than the entry's |
| `overrides` | a rule | any; the rule says something else |
| `decided` | a row of the entry chapter's `Decided by tools` table, as the row spells it | none |
| `absent` | empty | none |

A delta's departures table uses `extends`, `tightens` and `overrides`, as decision 10 of
`normalize-the-standards` defined them. The tier law, and the requirement that every relation but
`realises` gives a reason, are one function that both tables use, so the delta's map and the
abstract map cannot diverge.

`decided` exists because Phase C turned a rule whose whole content was a lint into a row. A concept
such as "no wildcard imports" is realised by ruff and clippy rows, not rules. Calling it `absent`
would be false, and turning the row back into a rule would undo Phase C. The `decided` cell is
verified to be a row of the standard's table in the entry's chapter.

### 3. Pairs are derived, keyed by ID; `Mirror` goes

Two rules mirror each other exactly when they realise one entry, so a pair is no longer declared.
Rows are keyed by rule ID, not by title. `Mirror` used titles because a renumbering pass once pointed
an ID-keyed table at unrelated rules. `revise` now rewrites every ID in the repository, `abstract/`
included, under its capture law, so an ID-keyed row is the safe key. Titles changed throughout
Phase C, so a title-keyed one is not.

Branch mapping:

| `mirror` branch | Fate |
|---|---|
| `no_anchor_rule`, `ambiguous` | gone: an ID either names a rule or does not |
| `not_a_rule` | `concepts.not_a_rule`: a row names no rule (or row) of its standard |
| `tier` | `concepts.relation`: a relation its tiers contradict |
| `restated` | `concepts.look_alike` (note), now comparing a delta with its anchor. It never fired on a shipped pair: bevy-style declared none. |
| `unheld` | `concepts.look_alike` (note), now comparing every pair of base standards |

New FAIL branches:

- `missing_row`, `delta_row`
- `no_reason`
- `two_rows_one_rule`, `two_rules_one_entry`
- `stale_tier`, rendered by `fmt`
- `inline_code` in a statement
- `wrong_family`
- `abstract_cited` from a skill
- `wrong_chapter`
- `undeclared_domain`, `domain_realises`, `domain_missing`
- `principles`

Each has one control on a demo abstract standard written beside `checks.demo`.

### 4. A concept's chapter is its address; domain chapters are declared

A realising rule (or `decided` row) stands in the chapter named by the file that holds its entry.
Every chapter a base standard ships is one of two kinds:

- **Abstract:** its word names a file under `abstract/`.
- **Domain:** declared in the profile as `domain: Mapping[str, str]`, chapter word to the domain
  feature that owns it. Examples: rust-style `"ownership": "the borrow checker"`, zig-style
  `"comptime": "compile-time execution"`, bevy-style `"ecs": "Bevy's entity-component-system"`.

A domain chapter realises no entry. An abstract chapter may hold rules that realise nothing, which
are domain rules about a shared concern (python-style's GIL rules in `concurrency.md`). The
checks are those of the `standard-structure` delta.

The abstract chapters are created, with template and no entries, before the sweep starts, for every
word that two or more base standards ship. Each profile declares its other chapters as domain. So
the checks hold from the first commit, and no gate is needed. The sweep may then turn a chapter from
one kind into the other, through `revise --chapters` or by moving its rules, and it updates the
profile in the same commit.

### 5. `revise` gains `move`, with laws

A plan entry `{"RS-CLI-07": {"move": "output", "after": "RS-OUT-03"}}` moves a rule into another
chapter of its standard, after the named rule, or as the first rule under a named section heading
(`"after": "## Streams"`). It takes the target family's code; dense renumbering closes both
families, and the rename table records the old ID against the new one. The existing machinery is
unchanged: a move is a permutation of positions before renumbering, so the identity-based citation
law and the capture refusal hold as they are.

A move into a chapter the standard does not ship creates it in the chapter template, with a `TODO`
scope the skeleton check fails until it is written, and adds its row to section 6.

Laws, property-tested on copies of the shipped tree with random moves:

- a move and the move back to the rule's old predecessor restore every byte;
- the existing laws are unchanged.

### 6. The sweep: one abstract chapter at a time, by judgement held to written criteria

The sweep runs serially, one agent per abstract chapter, in this order:

1. `errors`
2. `testing`
3. `build`
4. `naming`
5. `documentation`
6. `modules`
7. `api`
8. `data`
9. `types`
10. `concurrency`
11. `output`
12. `performance`
13. `migration`

The order runs from the chapters most alike across standards to the least, so the criteria settle
on easy cases first. For chapter X, the agent reads X in each base standard, then searches every
other chapter of each for rules about X's subject: the look-alike detector's notes, and a body
search for X's terms.

Criteria, which every sweep agent is given verbatim:

- **A concept** is a claim two or more base standards make, the same up to the spelling of their
  language. Two rules answering different questions about one construct are two concepts.
- **An entry's tier** is the tier its concept deserves under section 1's definitions, which is
  usually the tier most realisations hold. A realisation at another tier is re-tiered when the
  difference is drift, or departs with its domain reason when the difference is the domain.
- **`absent`** means the domain has no instance: Python has no raw pointers; Zig has no exception
  hierarchy. It never means the standard happens to be silent.
- **A gap** is a concept the domain has and the standard does not state. The standard gains the
  rule, with Why, Check and verified examples, in the entry's chapter. A gap a tool decides gains
  the row instead.
- **Two rules of one standard realising one entry** are merged with `revise` first.
- **Each chapter is one commit or a short series.** `check --fast` passes after each, and every
  standard whose rules moved passes its toolchain once at the end of the chapter.

The design questions are settled before the sweep, with their check (task 2.7), because they are
the shortest list and zig-style's third question must be decided. Either "What can be made a value
instead of an effect?" holds for Zig, or zig-style's question becomes its own, after the five.

### 7. Section 3 opens with the questions

`abstract/principles.md` holds the questions as an ordered list, each a bold question and one
abstract sentence. `skeleton` reads section 3 of each base standard. Its first items' bold text
equals the list, in order; further items are the standard's own. A delta is exempt: its section 3
is its departures table.

### 8. Evals: a generator, a selection, and a check

- **Selection.** Each profile gains `evals: Evals(review=(RuleId, ...), migrate=(str, ...))`, two of
  each by default: 20 cases in all, so the owner's run at `--runs 1` is 40 sessions with the
  no-plugin arm.
- **Validity.** A selected rule has a verified BAD block whose body cites no rule ID; otherwise the
  grader would pass on the prompt alone. A selected spelling is a `gone` row whose Since is the
  target's, is no shape, and whose target cell opens with a code span: the grader's literal.
- **Layout.** `plugins/style-standards/evals/<standard>/<kind>-<slug>/prompt.md` and
  `graders/*.md`, tagged `[<standard>, <kind>]`. The defaults are `runs: 1`, `max_turns: 10`, and
  `allowed_tools: [Read, Glob, Grep, Skill]`, so the skill can load its references.
- **Graders.**
  - review: `regex` on the rule ID, as a literal.
  - migration: `regex` on the target's code span and on the owning rule's ID, both literal.
  - Every case: `tool_used Skill` on its own skill, as an unscored indicator.
  - negative: `tool_used Skill` on its own skill with `max: 0, arm: both`. Its prompt is the review
    prompt of the first standard, in profile order, whose language differs.
- **Escaping.** A literal is escaped for JavaScript's `RegExp`. Generation tests that each escaped
  literal matches the literal and only it.
- **The check.** `agent-skill evals` writes the suite, and the `evals` check compares disk with the
  generation:
  - `drift`: a file differs;
  - `extra`: a case is not generated, which is how a hand-written judge grader fails;
  - `selection`: one branch per invalid selection.
- **Load test.** The implementation runs `claude plugin eval plugins/style-standards --case
  '__none__'` once, to confirm the suite loads and no run starts. If the CLI starts runs or
  validates nothing that way, the task records it and relies on the documented schema.
- **Gitignore.** `plugins/style-standards/evals/results/` is ignored. The README gives:

  ```bash
  claude plugin eval plugins/style-standards --runs 1 --max-cost-usd 20 --no-publish
  ```

### 9. Actions pinned to commits, as a build concept

- **Each `uses:`** becomes `owner/repo@<40-hex>  # vX.Y.Z`.
- **The commit** is the newest release at least seven days old, the cooldown PS-BUILD-11 applies to
  packages: the same concept.
- **`dtolnay/rust-toolchain`** publishes no releases; its toolchain was chosen by branch. It is
  pinned to a commit of `master` and given `toolchain:`, and its comment names the branch the commit
  was taken from.
- **The SHAs** are read once, through `add_repo` (read) on the eight action repositories, and no
  check needs the network.
- **`pins` gains `movable_action` and `unversioned_action`.** It reads the four assets and the
  repository's own workflow.
- **The rule** is registered by the `build` sweep as an entry, with a new rule in python-style,
  rust-style and zig-style.

### 10. The repository's CI is python-style's, plus the toolchains

`.github/workflows/check.yml` has two jobs:

- **`fast`**, on push to `main` and on pull requests: python-style's lint and test steps, with its
  uv and Python pins, running `check --fast`, `pytest -m "not toolchain"`, `ruff check`, `ruff format
  --check` and `ty check`.
- **`full`**, weekly and on `workflow_dispatch`: those steps, plus Rust 1.99 with clippy, rustfmt and
  rust-src, and Zig 0.17.0 through the assets' own actions. It runs `agent-skill check` and `pytest
  -q`.

`selfapply` fails a step that both files share and that differs in its `uses:` or `with:`. The first
real run happens on the pull request, and its result arrives as a PR event.

### 11. Repository items

- **OpenSpec.** `openspec config set delivery skills` and `openspec update`; `.claude/commands/opsx/`
  is removed if the update leaves it. A test holds every `generatedBy` to one version and the
  command directory absent.
- **The plugin version.** `plugin.json` becomes 2.0.0: rule IDs renumbered, `CORE` removed, and the
  sweep's moves.
- **Harness debts:**
  - `crossref.apparatus` reports its line: `ids.cited` yields positions.
  - Cache cleanup takes cargo's lock on the target directory.
  - `env::*` rows are probed by compiling the call outside `unsafe` under edition 2024, expecting
    E0133.
  - `test_control_fires` calls the thread-pooled runner `check --only controls` uses.
  - `install` exits non-zero when it leaves a differing directory alone, and zero when the directory
    is already identical.

### 12. `measure` gains the abstract rows

- entries per abstract chapter;
- realisations per standard by relation, the delta's derived through its anchor;
- look-alikes no entry holds;
- domain chapters per standard;
- rules in abstract chapters that realise nothing (informational).

### As built (group 2)

What the machinery decided beyond decisions 1 to 7 and 12, task by task:

- **One law (2.1).** `ids.Relation` is the six relations, and `ids.breaches(relation, held, tier,
  reason)` the one law: `realises` and `extends` keep the tier, `tightens` raises it, `overrides`
  sets any, `decided` and `absent` name no rule and so no tier, and every relation but `realises`
  gives its reason, `decided` and `absent` included. "Higher" is `Tier.binding`, the order in which
  a tier binds more code: `[S]`, `[M!]`, `[M]`. Both maps apply the law to the rules' own tiers,
  never to a cell: a delta's stated tiers are `departure_tier`'s, an entry's Tier cell
  `stale_tier`'s, so one defect is one finding. `crossref` gained `departure_reason`; a tier the
  law forbids is its `relation` branch, as a relation no delta may state was.
- **The record (2.2).** `profiles.abstract.PROFILE` is `Profile(name="abstract", prefix="AS",
  language="Abstract")`, and nothing else: no toolchain, languages or domain, and it is not in
  `PROFILES`, since no skill ships it. `agent_skill.abstract` reads `abstract/` beside the skills,
  found from the tree as `documented` finds the README, so a control's copy reads its own; a tree
  outside a repository's layout reads as an abstract standard with no files, so what it would hold
  is reported missing rather than passed over. A finding in it lies in no skill (`./abstract/
  errors.md:12 [AS-ERR-01]`), so no `--skill` hides one. How each command takes it as a standard:
  - `concepts` reads its prefix for `wrong_family` and `abstract_cited`;
  - `fmt` prints its files in the normal form a standard's chapters are printed in, and renders
    each Tier cell from the rules of every skill read, when the run names no skill;
  - `measure` counts its entries per chapter;
  - `revise` reads its files as part of the corpus: through the tree, so a respelled row is printed
    canonically, and under the capture law, so a row naming no rule cannot be handed one. It does
    not take the abstract standard as a revision's subject. Its IDs are cited by nothing, which
    `abstract_cited` holds, so an entry is renumbered by editing it, `numbering` holds them dense,
    and no rename history is owed to a reader who cannot hold an old one. The requirement that the
    abstract standard is "revised by `revise` like any standard" is read as this: every revision
    rewrites its rows as it rewrites a standard's citations.
- **An empty chapter (2.5).** The layer reads a contents list only as a list with an item, so an
  abstract chapter with no entry is its title, its `Scope:`, `- **Concepts**` as its contents and an
  empty `## Concepts` section, which the sweep fills or replaces.
- **`concepts` (2.3 to 2.7).** 23 FAIL branches and one note, each FAIL branch with one control on
  the demo and its abstract standard. Those controls read the demo alone: the shipped standards go
  from the copy and the demo abstract standard takes the shipped one's place, since a shipped
  standard read beside the demo's entries would answer none of them.
  - The abstract standard's form, seven, five of them beyond the design's list: `unread` (a file
    the layer refuses, or named by no vocabulary word), `template` (a coded or missing title, no
    `Scope:`, contents disagreeing with the entries), `canonical`, `numbering`, `wrong_family`,
    `entry_shape` (a statement, then one realisation table, and nothing else: no Why, Check or
    example), `inline_code` (in the title or the statement). A chapter that read as nothing, or an
    entry that was not one, would otherwise pass every other branch silently.
  - The map, ten: `missing_row`, `delta_row`, `unknown_standard` (beyond the design: a row for no
    standard here), `two_rules_one_entry`, `two_rows_one_rule`, `not_a_rule` (a ruled row naming no
    rule of its standard, a `decided` row naming no lint of the entry chapter's table, an `absent`
    row naming anything), `relation` (no relation, or one the law forbids), `no_reason`,
    `stale_tier` and `wrong_chapter`. `wrong_chapter` landed with the map in 2.3, as it needs no
    domain declaration.
  - The chapters, four: `undeclared_domain`, `domain_realises`, `domain_missing`, and
    `domain_abstract` (beyond the design: a declared domain chapter whose word is an abstract
    chapter's). A rule realising an entry from another chapter is `domain_realises` when that
    chapter is declared domain and `wrong_chapter` otherwise, never both. A delta's realisations,
    derived through its anchor, are not held to a chapter: bevy-style's departing rules stand in
    Bevy's subsystems by design.
  - `principles`, in `concepts` rather than `skeleton` (decision 7 put it there), since it reads
    the abstract standard: section 3's first numbered items' bold questions equal `principles.md`'s,
    in order, and a delta is exempt. And `abstract_cited`, over every text file of every skill.
  - `look_alike`, the note: titles whose three-word runs (lowercased letters only) overlap, by
    Jaccard index, above 0.5, `mirror`'s threshold, compared only where two titles share a run.
    Held, and so not noted: two rules one entry's rows name, and a delta rule and the anchor rule
    its departures table names. Every pair of base standards and each delta with its anchor gives
    14 notes on the shipped tree, where `mirror` gave 3.
  - FAIL branches 236 → 255 and controls 213 → 232 over the group: `departure_reason` +1, the five
    `mirror` FAIL branches and their controls −5, `concepts` +23. Exemptions stay 23.
- **Domain chapters (2.5).** The twelve abstract chapters are the words two or more base standards
  ship. Every other chapter is declared domain: python-style's types and async; rust-style's
  ownership, traits, functional, macros, unsafe and cli; zig-style's comptime, memory, assertions
  and interop; bevy-style's architecture, ecs, scheduling, events, state, assets and view. A delta
  is held to the declaration as a base standard is. `revise --chapters` does not rewrite a
  profile's `domain`: the sweep updates the profile in the commit that turns a chapter from one
  kind into the other, as decision 4 says.
- **`move` (2.6).** `revise.Moved(chapter, after)`, read from `{"move": stem, "after": ID}` or
  `"after": "## Title"`. A section title the target lacks opens a new section before `Decided by
  tools`. A created chapter's title is the vocabulary word, capitalised, and its scope a TODO
  paragraph that `skeleton.no_scope` fails until it is written; its §6 row goes before the
  migration chapter's, with "TODO" for what it covers. A chapter any plan leaves with no rule and
  no section is deleted, with its §6 row, which is what lets the move back undo a creation. A move
  renames no family, even when it empties one. §4 is re-rendered, as `fmt` renders it, in a
  revision that moves a rule. The law is drawn over rules that share their section with another,
  since moving a rule alone in its section takes the section with it, and the move back would have
  no section to open: six seeded draws in the suite, across the four standards, both kinds of
  `after`, and first-in-section moves back; 22 were run once.
- **Section 3 (2.7).** The shared third question holds for Zig: zig-style's own ZS-PERF-12 is its
  answer, a helper returning the change and its parent applying it, so the leaves stay pure and one
  apply site asserts the invariant. "What can be asserted instead of assumed?" is TigerStyle's
  safety-first, the domain's, so it is zig-style's sixth question, after the five, and its section
  3 asks six. No example changed.
- **`measure` (2.8).** The per-standard rows join the normal form's table; the entries per abstract
  chapter are a second table, since a chapter is no column.
- **The seeds.** `Mirror`'s 12 zig-style pairs, resolved to rust-style's IDs, and the three notes
  of its detector are recorded in tasks.md for the sweep.

## Risks / Trade-offs

- **Cost.** The sweep is 13 agent passes over about 1,350 rules. Each pass reads three chapters
  and the detector's notes; Phase C's passes cost about 0.7M tokens each.
  → One agent at a time, as the owner asked. Each chapter is pushed when it is green, so an
  interrupted sweep resumes at the next chapter.
- **Churn in IDs.** Moves renumber two families at once, and many citations change.
  → `revise` rewrites every citation under its capture law, `renames.md` records every old ID, and
  2.0.0 says so.
- **Judgement.** Concept identity, entry tiers and `absent` are judgements; no check can verify a
  statement's meaning.
  → The written criteria. The look-alike detector catches pairs a pass missed. The owner reviews at
  the phase stop.
- **Concerns pulled apart.** "Same concept, same chapter" can split a chapter a reader found
  coherent. For example, python-style's `async.md` may lose its task-ownership rules to
  `concurrency.md`.
  → That is the requirement's intent: the reader finds task ownership where every standard keeps
  it. A chapter left with only domain rules is declared domain, and an empty one is removed.
- **Evals unrun.** A format error would surface only when the owner runs the suite.
  → The documented schema, the no-case load test, and deterministic graders whose literals are
  tested.
- **CI unrun here.**
  → The workflow mirrors the shipped asset, `selfapply` holds it to that asset, and the PR shows its
  first run.
- **External reads.** `add_repo` may be declined for an action repository.
  → That asset keeps its tag, the `pins` branch stays red for it, and the task reports the block
  rather than inventing a SHA.

## Migration Plan

The order is in tasks.md:

1. hygiene and debts;
2. machinery, with the abstract chapters seeded empty and domain chapters declared;
3. the sweep, chapter by chapter;
4. action pins and CI;
5. evals;
6. close: measure, full check, README, archive.

The change archives into `openspec/specs/` with the new capabilities `abstract-standard` and
`behavioural-evals`. Rollback is a revert: every ID change is in `renames.md`, and `revise` can
apply the inverse plan.
