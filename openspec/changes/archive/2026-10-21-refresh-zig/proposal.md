## Why

This machine's `zig` is now 0.17.0, and `pins` reports it as the cue the refresh planned for: zig-style's
pin follows the local toolchain, and the local toolchain has moved past 0.16.0. zig-style is also the
one standard still exempt from `standard-structure`. With the exemption lifted, it has 323 findings:

- 297 of its 406 chapter rules have a Why longer than three lines;
- 13 chapter names are outside the shared vocabulary;
- its review protocol uses its own severity model;
- its `SKILL.md` departs from the skeleton and the shared text;
- 25 blocks still use the `does-not-compile` marker.

Doing the version bump and the conversion in one pass renumbers once instead of twice, as
`refresh-skills` did for the other three standards. When zig-style conforms, nothing is exempt, and the
exemption machinery has nothing left to do.

## What Changes

- **Version.**
  - zig-style moves from 0.16.0 to 0.17.0. The pin keeps following the local toolchain.
  - Every verified example compiles on 0.17 and is `zig fmt` clean. Today 11 do not, after one
    harness fix: the wrapper that forces analysis reads `decls`, which 0.17 replaced with
    `decl_names`.
  - Every API, builtin, syntax and build-system spelling that 0.17 renamed, removed or deprecated is
    replaced. A deprecated name still compiles, so the toolchain alone cannot find those.
  - §2 becomes a 0.17 reality check, and the migration chapter gains the 0.16 → 0.17 table.
- **One skeleton.**
  - zig-style takes the eight-section `SKILL.md`, the shared text, the shared severity model and the
    one marker vocabulary.
  - Its chapters are renamed into the shared vocabulary, which gains four words: `assertions`,
    `comptime`, `memory` and `interop`.
  - Every Why is three lines at most.
- **Rules the compiler decides become rows.**
  - Zig ships no lint configuration. What decides a rule mechanically is a compile error that is
    always on, or `zig fmt`.
  - A rule whose whole content is such an error becomes a `Decided by tools` row with tool `zig`. The
    Lint cell is a stable phrase from the 0.17 error message, and the level is `error`.
  - Each row is verified by compiling a probe the harness keeps, which must fail with that phrase.
    Each probe must have a row.
  - A rule that says more than its error stays a rule, and its Check names the error.
- **BREAKING — every `ZS-` rule ID and every zig-style reference path changes.**
  - Chapters are renumbered densely under the unified family codes, by `agent-skill renumber`.
  - Removals and demotions go through `agent-skill demote`.
  - `migration.md` carries the rename table with each family's prior range.
- **The exemption mechanism is removed.** Once zig-style conforms, these go:
  - `exempt_from_structure` on profiles;
  - the per-profile marker vocabulary, and with it `does-not-compile`;
  - the branches that skip an exempt standard;
  - the outlived-exemption report.

  A standard added later conforms from its first commit. The template, the vocabulary and the
  commands already exist to make that the easy path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `standard-structure`:
  - **REMOVED:** "A standard that does not yet conform is exempt by declaration".
  - **MODIFIED:** "One marker vocabulary" no longer speaks of exempt standards.
  - **ADDED:** a requirement for compiler-decided rows: each is verified by a probe that must fail
    with the row's error, and each probe has a row.
- `check-execution`: the pinned-tool requirement's scenario for a local-following pin with no reason
  no longer leans on an exemption that does not exist.

## Impact

- **Skills:**
  - `skills/zig-style/` is rewritten end to end: `SKILL.md`, every chapter (renamed, renumbered and
    trimmed), and `assets/` (`build.zig`, `build.zig.zon`, `ci.yml`).
  - The installed skill is a symlink, so it updates in place.
- **Harness:**
  - `lang/zig.py`: the 0.17 pin and the `decl_names` wrapper.
  - `vocabulary.py`: the four new words.
  - `checks/citations.py`: `zig` rows and their probes.
  - `profiles/zig_style.py`: the probes; no exemption and no marker override.
  - `profiles/__init__.py`, `model.py`, `checks/skeleton.py`, `checks/shared.py`, `checks/anatomy.py`,
    `checks/markers.py`, `fmt.py`, `renumber.py`: the exemption and the per-profile marker vocabulary
    removed.
  - `checks/controls.py`: new controls for the row branches.
  - The tests that exercised the exemption are removed, and new ones are added for the rows.
  - `README.md`.
- **Readers:** a citation of an old `ZS-` ID or a zig-style reference path is looked up in the
  rename table.
- **Risks:**
  - A probe's message can change between Zig releases. That is the point: the row fails, and the
    bump that moved it fixes it.
  - The full suite must still run alone.
