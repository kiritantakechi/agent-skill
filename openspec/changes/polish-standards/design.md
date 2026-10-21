## Context

After `refresh-skills` and `refresh-zig`, the four standards are on their latest versions and share
one structure. Measured before this change:

| | python | rust | bevy | zig |
|---|---|---|---|---|
| Rules (chapters + core) | 258 + 26 | 709 + 28 | 220 + 24 | 405 + 29 |
| Pointer rules | 0 | 0 | 0 | 26 |
| Version mentions below the target in rule bodies | 13 in 11 rules | 44 in 34 | 29 in 26 | 105 in 64 |
| Lines, all chapters + `SKILL.md` | 5 529 | 16 078 | 8 806 | 17 686 |

Every pin is current, every GitHub Action but one is on its latest major, and the harness's tools
are at their latest release. The research for each standard is in `research/`: duplicate rules,
pointer owners, and newer APIs the target offers.

## Goals / Non-Goals

**Goals**

- A rule reads as written for its target version, and the history lives where history belongs.
- Every topic has one rule. No rule exists only to point at another.
- An example uses the best API its target offers.
- What the four standards share, they do the same way; so does the harness, in its own idioms.

**Non-Goals**

- No version moves; there is none to make.
- The migration chapters keep their full history (D5).
- No new topics. A rule changes because it is redundant, stale, or behind its target's API.

## Decisions

### D1. The target-version check

`anatomy`'s structural checks, which every conforming standard gets, gain one branch: a version of
the standard's subject below its target, in the prose of a rule's body.

- **The subject version** comes from the profile's pin: major `1`, target minor `99` for Rust.
  The token is `\b<major>\.(\d{2,})\b` with a minor below the target's. A minor of two digits or
  more avoids `3.5x faster` and `0.5` in prose; Python 3.10 is the earliest release a Python 3.15
  standard has reason to name.
- **Scope:**
  - The body of every chapter rule outside `migration.md`, and every core rule in `SKILL.md`.
  - Prose only: fenced examples are excluded, because a manifest's `rust-version` or a 0.16
    reproduction is the example's content.
  - §2, the migration chapter and the review protocol hold no rules, so they are outside the scope
    by construction.
- **The finding** names the rule and the version.
- **A control** inserts "(stable since 3.13)" into a python-style rule.

### D2. Removing an annotation

For each hit, one of three outcomes:

- **The annotation is a date.** "(1.96)", "stable since 1.74", "Since 0.19": it is deleted, and the
  sentence reads as true of the target.
- **The rule's point is a change from an older release.** For example, "0.16 removed …, write …": the
  rule states the target's spelling, and the change moves to the migration chapter's table for that
  release, unless it is already there.
- **The rule only exists to reject an old API.** It is a duplicate of a migration rule, and merges
  into it (D3).

### D3. Merges: pointers and duplicates

Each merge goes through `agent-skill demote` with `{"merge": "<owner>"}`, so the rename table
records it. Before a rule merges, its owner absorbs whatever the rule says that the owner lacks:
usually one line applying the rule to the chapter's context. Each standard is renumbered once, after
all its merges.

bevy-style is a delta on rust-style. A bevy rule that restates a rust-style rule and adds no Bevy
content goes through `{"remove": "RS-… states it"}`, since a merge target must be in the same
standard. Where it adds a line of Bevy content, it stays as that line and cites the rust-style rule.

A core rule in `SKILL.md` that misstates the chapter rule it summarises, or cites the wrong one, is
rewritten to match it.

A rule whose whole content a shipped lint decides is a duplicate of that lint's row, which
`standard-structure` already forbids. It goes through `{"rows": …}` or `{"lint": …}`. Where the lint
decides only part of the rule, the row is added and the rule's Check names it. A row is added only
for a lint the shipped configuration enables, so `citations` can verify it; a nursery lint the
config leaves off is not a row.

**Order.** `renumber` rewrites citations in every skill, in `src` and in `tests`, but not in a
change's `research/`. So a standard's research IDs are valid until that standard's renumber, and
bevy-style, whose research cites rust-style IDs, is done before rust-style.

### D4. The pointer concept goes

Once zig-style has no pointer, `Rule.pointer`, `Rule.owner`, `Rule.owner_chapter`, the pointer
branches in `anatomy`'s rule shape and its `_pointers` check, and the two pointer controls are
removed. A rule without its own Why and Check then fails the existing "needs Why and Check" branch,
which is how the requirement "no rule only points at another" is enforced. A core rule's "(owned by
…)" in `SKILL.md` is a summary naming its chapter, not a pointer rule, and stays.

### D5. Migration chapters keep their history

The readers of these standards are models whose training is mostly older releases. A migration
table maps a spelling the model will reach for to the current one, and that value grows with the
table's depth. So the chapters keep every release they cover.

What goes is repetition between a migration chapter and its §2. §2 keeps the changes that alter
behaviour without failing the build, and the handful of loud changes a reader meets first, each
citing the migration rule that owns it. Long removal tables live only in the migration chapter.

### D6. Newer APIs

Each item in a research report's newer-API table is applied where it makes the code simpler or
more correct. It is compiled or run on the pinned toolchain, and the rule's prose is re-read so it
still describes the example. An item whose only effect is churn is skipped and listed as skipped.

### D7. Defects the research found

The research also found rules that contradict each other and claims that are false on the target.

- **A contradiction** is settled in the rule that owns the topic, and the other rule is changed to
  agree. For example, python's PS-OUT-15 prescribes a `print` that its own shipped `T201` rejects.
- **A false claim** is corrected and probed on the pinned toolchain. For example, bevy's "a skipped
  frame, not a crash" is false for an un-annotated `?`, and python seeds a "reproducible" random
  generator with a salted `hash`.

### D8. Symmetry

- **zig-style's CI asset** uses `actions/checkout@v7`.
- **rust-style ships `assets/rust-toolchain.toml`**, the file its RS-BUILD-38 prescribes, in the
  same shape as bevy-style's. Its §7 lists it.
- **One regex-group helper** in `text.py` replaces `model._group` and the scattered
  `str(m.group(…))`.
- **"Set" is one test.** Where `None` and `""` mean the same thing on a profile field or a
  parameter, its type becomes `str` with `""` as the default, and readers test it as a plain truth
  value. `follows_local` keeps its `None`: a blank reason there is a third state, and it is the one
  that fails.

## Risks / Trade-offs

- **An annotation can carry a fact.** A library with an MSRV below the target needs to know when an
  API arrived. Such a fact moves to the migration chapter (D2) rather than being lost. A standard
  that targets 1.99 is not, however, a guide for supporting 1.74.
- **Merging changes IDs.** The rename tables record every move, as before. Each standard already
  has a table for its current revision, from `refresh-skills` or `refresh-zig`, and `renumber`
  carries this change's moves into it rather than starting a second. The table then maps the IDs
  from before the revision to the IDs after this change. An ID that existed only between those
  changes and this one gets no row: all three land on the same release, and a table per change
  would split one release's renames across two.
- **The check's version token can match a crate version.** For example `tokio 1.40` in a Rust
  standard. Such a prose mention is reworded to the major version, as a version requirement in a
  manifest would be written.

## Migration Plan

1. **Harness:** the idioms (D8), then the target-version branch with its control (D1). The branch is
   introduced together with the content work that satisfies it.
2. **Per standard:** remove annotations (D2), merge pointers and duplicates (D3), apply newer APIs
   (D6), fix the defects (D7), and de-duplicate §2 against the migration chapter (D5). Then renumber
   once.
3. **Harness:** remove the pointer concept (D4). Then the assets (D8) and the README.
4. **Close:** one full run alone, `openspec validate --strict`, archive, and a fast-forward of
   `main`.

## Open Questions

None. The user chose each direction before planning: target-version annotations only, full
migration history, merging pointers and duplicates, symmetric assets and idioms, and the newer-API
sweep.
