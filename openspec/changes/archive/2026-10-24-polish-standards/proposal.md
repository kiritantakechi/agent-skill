## Why

The four standards are each on their latest version, and all four conform to `standard-structure`.
They still carry three kinds of residue:

- **History inside the rules.** 191 version mentions below the target sit in the bodies of 135
  rules: Rust's "(1.96)", "stable since 1.74"; Bevy's "Since 0.19"; Zig's "on 0.16 it…". A rule
  that annotates when its API arrived reads as written for an older reader. A standard that keeps
  its history in the migration chapter and §2 already has a place for that.
- **Redundancy.**
  - zig-style still has 26 rules that only point at another rule ("Owned by …"); the other three
    lost theirs in `refresh-skills`.
  - The harness keeps the code that checks the shape of pointer rules alive for those 26.
  - Rules that restate another rule have not been looked for since `refresh-skills`, and never in
    zig-style.
- **Small asymmetries.**
  - zig-style's CI asset still uses `actions/checkout@v4`; the other three use `@v7`.
  - rust-style's own RS-BUILD-38 says to commit a `rust-toolchain.toml`, and its assets ship none,
    while bevy-style's do.
  - The harness narrows a regex group two ways and tests "set and non-empty" three ways.

The versions themselves need no move: every pin, every GitHub Action except zig's checkout, and the
harness's own tools are at their latest release. What can still lag is the API a rule teaches. A
target release can offer a better call than the one an example uses.

## What Changes

- **A rule speaks of its target version only.** Version mentions below the target are allowed in the
  migration chapter, in `SKILL.md` §2, and in the review protocol, and nowhere in a rule's body.
  Each annotation in a rule is removed. Where it was the only record of a change, the fact moves to
  the migration chapter. A new branch in `anatomy`'s structural checks enforces this for every
  standard, with a control.
- **No rule only points at another.**
  - zig-style's 26 pointer rules merge into the rules they point at, through `agent-skill demote`,
    and the rename table records each.
  - Rules that duplicate another, found per standard, merge the same way.
  - A bevy-style rule that only restates a rust-style rule goes, and the rename table names the
    rust-style rule.
  - With no pointer left, the harness's pointer concept goes: `Rule.pointer`, `Rule.owner`,
    `Rule.owner_chapter`, the pointer branches of `anatomy`, and their controls. A rule without a
    Why and a Check then fails like any other.
- **The newest API a target offers.** For each standard, the examples and rules that use an older
  idiom move to the better API their target release offers. The research for each lists them. Each
  is compiled or run on the pinned toolchain.
- **Defects.** The research found rules that contradict each other, and claims that are false on
  the target. Each is fixed, and each correction is probed on the pinned toolchain.
- **Symmetry.**
  - zig-style's CI asset uses `actions/checkout@v7`.
  - rust-style ships the `rust-toolchain.toml` its RS-BUILD-38 prescribes.
  - The harness narrows a regex group, and tests a value for "set and non-empty", one way each.
- **The migration chapters keep their full history.** The readers of these standards are models
  whose training is mostly older releases, and the tables are what maps that knowledge to the
  current one. Only material repeated between a migration chapter and its §2 is removed.
- **BREAKING:** the rule IDs of every chapter that loses a rule change. Each standard is renumbered
  once, and its `migration.md` table records the moves.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `standard-structure` gains two requirements: a rule speaks of its target version only, and no
  rule only points at another.
- `python-style`'s rule-shape requirement no longer has a rule defer to its owner by pointing at it:
  it cites the ID, and a rule that would only point merges into its owner.

## Impact

- **Skills:**
  - Rule bodies in all four standards: the version annotations, the merges, and the API updates.
  - zig-style's chapters, which lose 26 pointers.
  - `skills/zig-style/assets/ci.yml`, and a new `skills/rust-style/assets/rust-toolchain.toml`.
  - Each standard's `migration.md`, whose rename table records the moves and which takes the facts
    removed from rules.
- **Harness:**
  - `checks/anatomy.py`: the target-version branch, with the pointer branches gone.
  - `model.py`: `Rule.pointer`, `owner` and `owner_chapter` gone, plus the regex-group helper used
    everywhere.
  - `checks/controls.py`: a control for the new branch, and the pointer controls gone.
  - The None-or-empty spelling, everywhere it appears.
  - The tests for each.
  - `README.md`.
- **Readers:** a citation of a merged rule resolves through the rename table.
- **Risks:**
  - An API update can change what an example demonstrates. Each update is compiled, and its rule
    is re-read with it.
  - A version annotation can carry a fact a reader needs, such as an MSRV requirement for a library
    below the target. The removal moves that fact to the migration chapter rather than deleting it.
