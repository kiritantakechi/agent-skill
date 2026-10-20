# Tasks

Each milestone (groups 1–6, 7–8, 9–10) ends with exactly one full run (`uv run agent-skill check`),
started only after `pgrep -f "pytest|cargo test|zig test"` finds nothing. Capture the full output.
Every other verification step below is `--fast` or a targeted `pytest`, which can run at any time.

## 1. Harness: vocabulary, exemptions, markers

- [x] 1.1 Add the D3 vocabulary table (file → family code, `review-checklist.md` as the one fixed
  exception) as a single module in the package, and unit-test the lookup in both directions. Verify:
  `uv run pytest tests/test_vocabulary.py`.
- [x] 1.2 Add `Profile.exempt_from_structure` (D2). Declare it with a reason on `python-style`,
  `rust-style` and `bevy-style` ("converted in milestone 1 / 2 / 3 of refresh-skills") and on
  `zig-style` ("conforms with its own bump, once this machine's `zig` moves"). Until 6.8 no skill
  conforms. That is why groups 2–4 test against fixture inputs, and why the controls on the real tree
  land in 6.9. Verify that a test fails a profile which declares the field with an empty reason.
- [x] 1.3 Change the default `MARKERS` to `verified` / `fragment` / `rejected`, add `Profile.tools`,
  and make `markers` require `rejected — <tool>:` with a tool from that list (D9). Declare
  `does-not-compile` on `zig-style`. Verify: `uv run agent-skill check --fast --only markers` passes,
  and a control that injects `// does-not-compile` into a `python-style` block fails.

## 2. Harness: skeleton and shared text

- [x] 2.1 Write the shared templates under `src/agent_skill/shared/`, with `{slot}`s and `…` free
  regions (D4). Cover: the reading procedure, the tier table plus its opening and closing lines, the
  marker legend, the ID-citation and pointer paragraphs, the §6 and §7 intros, and the
  review-protocol severity table with its blocking paragraph (D8). Add the slot values to each
  profile. Verify that rendering each template for each profile succeeds in a unit test.
- [x] 2.2 Implement the `skeleton` check for every item listed in D5, skipping exempt skills, plus
  the dry run that reports an exemption that has outlived its reason (D2). Verify: unit tests cover
  one failing input per item, and one test covers the outlived-exemption report.
- [x] 2.3 Implement the `shared-text` check, comparing paragraphs with whitespace collapsed and
  free regions honoured. Extend `agent-skill fmt` to re-render, rewrap to the `layout` width and
  write each passage. Verify: `tests/test_fmt.py` gains a round trip in which drift is introduced,
  `fmt` repairs it, and the check passes.
- [x] 2.4 Add `skeleton` and `shared-text` rows to the README check table. Verify:
  `uv run agent-skill check --fast --only documented`.

## 3. Harness: rule anatomy, lint rows, rename table

- [x] 3.1 Make `anatomy` require dense numbering with no letter suffix, and a **Why** of at most
  three non-blank lines (D7), for skills that are not exempt. Verify with a unit test for a gap, a
  suffix, and a four-line Why.
- [x] 3.2 Parse `## Decided by tools` rows into `Chapter.lint_rows` (D6), keep them out of the rule
  set, and accept a `- Decided by tools` contents line. Verify in `tests/test_model.py`.
- [x] 3.3 Extend `citations` so that ruff and ty rows are verified against the catalogue and the
  shipped asset at the stated level (D6). Verify with a unit test whose row's level differs from
  the fixture's `ruff.toml` or `ty.toml`.
- [x] 3.4 Parse the `## Rule IDs before the <target> revision` table in `migration.md`, and make
  `skeleton` fail any `Now` value that resolves to no rule and no lint row. Verify with a unit test
  in which a rule is deleted while its row still names it.

## 4. Harness: the renumber command

- [x] 4.1 Implement `agent-skill renumber <skill> [--chapters old=new …]` per D10. It renames files
  through git, re-codes families from D3, numbers densely, rewrites `skills/`, `src/`, `tests/` and
  `README.md` in a single pass from one dictionary, composes the rename table, verifies identity by
  title before and after, and writes all or nothing. Verify with tests on a fixture tree covering:
  an overlapping old/new ID, a chapter rename, composing onto an existing table, and refusal leaving
  the tree byte-identical.
- [x] 4.2 Document `renumber` in the README's command block. Next to it, note that a stale ID cited
  by hand after a renumbering cannot be detected, so citations are never rewritten by hand.

## 5. Harness: pins

- [x] 5.1 Add local-following pins to `pins` (D11), with a required reason, and declare the
  `zig-style` compiler pin `0.16.0` as local-following. Verify: `uv run agent-skill check --fast
  --only pins` reports zig as compared against `zig version` only, and a control that empties the
  reason fails.
- [x] 5.2 Move the repository's dev pins to `ruff==0.17.1` and `ty==0.0.89` in `pyproject.toml`,
  run `uv sync`, and update `citations.py`'s hard-coded "786" so the number is derived rather than
  stated. Verify: `pins` no longer reports ruff or ty.

## 6. python-style (milestone 1)

- [x] 6.1 Pins and assets:
  - interpreter `cpython-3.15.0+freethreaded` in `lang/python.py` and `assets/ci.yml`;
  - `setup-uv` at 0.13.0 or later;
  - `ruff==0.17.1` and `ty==0.0.89` in `assets/pyproject.toml`;
  - the literal pin strings in `controls.py` (old lines 147 and 482);
  - `uv python install 3.15.0t`, but only after confirming the download with the user.

  Verify: `pins` passes for python-style.
- [x] 6.2 Assets:
  - **`ruff.toml`:** drop `preview` unless a code that stays cited needs it, and record the reason
    whichever way it goes. Update the TC001–TC003 comment for the lazy-import fix.
  - **`ty.toml`:** name each of the six new default-off rules (`research/python-3.15.0.md` § ty)
    as either enabled or deliberately off, with a reason, and correct the "twelve" count in the
    asset, in SKILL.md §7 and in `python.py`.

  Verify: `uv run agent-skill check --fast --only lints --only citations --only assets`.
- [x] 6.3 Step A: `agent-skill renumber python-style --chapters` mapping each old name to its D3
  name. Verify: `uv run agent-skill check --fast` is no worse than before the run, and
  `migration.md` has the table.
- [x] 6.4 Bring `SKILL.md` and `review-checklist.md` onto the skeleton and the templates:
  - **Titles:** the H1 is `Python Style — 3.15`, §2 is `2. Python 3.15 reality check`, and §3
    drops its subtitle.
  - **Review protocol:** §5 is the review-order stages, the severity table moves to D8 with Silent
    merged into Stale, and the protocol gains `Refactoring a codebase to this standard`.

  Then `agent-skill fmt`. Verify that `skeleton` and `shared-text` pass for python-style.
- [x] 6.5 Content fixes from `research/python-3.15.0.md` § Stale claims A–C:
  - **§2.2 and PS-FT-05:** replace the deleted HOWTO quote with the new Thread Safety Guarantees
    page, including that `L.sort()` is not atomic.
  - **Migration chapter:**
    - fix the dated claims in MIG-14 and MIG-16;
    - add the four removals MIG-04 is missing;
    - fix the MIG-09 regex;
    - add RUF071 to the migration chapter.
  - **Other rules:** FMT-08, PERF-02, CORE-14/ERR-15, TYPE-22, CORE-19, TYPE-03, DOC-13, and the
    `typing.md` cadence sentence.
  - **TID255:** cite it where PS-NAME-15 is.

  Verify: `--fast` passes, and the fixed MIG-09 pattern matches its `fires` fixture.
- [x] 6.6 Lint rows: demote each LINT rule in `research/python-3.15.0.md` § Lint classification
  whose code the asset enables (D6). Cite B012 and RUF017 where the research places them. Decide the
  three asset settings it lists (`ban-relative-imports`, `raises-require-match-for`,
  `max-doc-length`). Record each demoted ID's disposition in the rename table. Verify:
  `citations` passes.
- [x] 6.7 Cut every **Why** to three lines or fewer. Move excess text into the statement or an
  example, or split a rule that is carrying two. Verify: `anatomy` passes with python-style not
  exempt.
- [ ] 6.8 Step C: `agent-skill renumber python-style`. Remove python-style's exemption, and update
  the frontmatter rule count and the §6 counts. Verify: `uv run agent-skill check --fast` passes,
  with nothing reporting an outlived exemption.
- [ ] 6.9 Add controls in `checks/controls.py`, injecting into `python-style`, which now conforms:
  - **`skeleton`:** one control per branch — a renamed H2, a chapter missing from the vocabulary, a
    wrong family code, a severity label, §5 drifting from the review order, and a rename-table row
    naming a deleted rule;
  - **`shared-text`:** an edited shared sentence;
  - **`anatomy`:** a gap in the numbering, and a four-line Why;
  - **`citations`:** a lint row at the wrong level.

  Each injected defect must be one that only the named branch reports (`harness-integrity`).
  Verify: `uv run pytest tests/test_controls.py` passes, and each new control fails with its branch
  disabled.
- [ ] 6.10 Milestone 1: one full run, alone. Verify: `ALL CHECKS PASSED`. Commit.

## 7. Harness for Rust

- [x] 7.1 Add the Rust toolchain pin (D11): `Crate.rust_version = "1.99"`, compared at major.minor
  against `rustc -V` and the stable channel manifest, and reported not-run when offline. Verify:
  `pins` passes on rustc 1.99.x, and a control set to `1.98` fails.
- [x] 7.2 Extend lint-row verification to rustc, clippy and rustdoc. The catalogue comes from
  `-W help`, and the effective level from the explicit entry or the lint's group (D6). Declare
  `needs`. Verify with a control whose row names a lint the asset sets at a different level, and one
  whose row names a lint that does not exist.

## 8. rust-style (milestone 2)

- [ ] 8.1 Assets and verified crate:
  - **`rust-version`:** set `1.99` in all five places named in `research/rust-1.99.md` § MSRV.
  - **New `assets/clippy.toml`:** `avoid-breaking-exported-api = false`,
    `allow-unwrap-in-tests`, `allow-expect-in-tests`, `upper-case-acronyms-aggressive`. Use it in
    the verified crate too.
  - **Lint table:**
    - remove the dead `module_name_repetitions` allow, in the asset, `lang/rust.py` (both places),
      `cargo-toolchain.md` and the bevy asset;
    - add `dead_code_pub_in_binary = "warn"`;
    - add `[workspace.lints.rustdoc]`, and drop `RUSTDOCFLAGS` from `ci.yml`.

  Verify: `--only lints --only assets` passes.
- [ ] 8.2 Step A: `agent-skill renumber rust-style --chapters` per D3 (`api-design=api`,
  `cargo-toolchain=build`, `cli-apps=cli`, `concurrency-async=concurrency`, `structure=modules`,
  `traits-generics=traits`, `unsafe-ffi=unsafe`). This also rewrites `bevy-style`'s twelve `RS-`
  citations. Verify: `--fast` is no worse, and `mirror` still resolves every title.
- [ ] 8.3 Create `references/migration.md` (`RS-MIG`). It holds:
  - the edition-2024 changes and the crates std replaced (moved out of SKILL.md §2, where a summary
    stays);
  - the std APIs deprecated through 1.99 (e.g. `fetch_update`), each with an `rg` Check and a
    `fires` fixture;
  - the rename table.

  Verify that `sensitivity` proves each new pattern fires.
- [ ] 8.4 Bring `SKILL.md` and `review-checklist.md` onto the skeleton and the templates:
  - **Titles:** the H1 is `Rust Style — 1.99` and §2 is `2. Rust 1.99 reality check`.
  - **Review protocol:** §5 is replaced by the protocol's review-order stages, and the severity
    table moves to D8, adding Stale.

  Then `fmt`. Verify that `skeleton` and `shared-text` pass for rust-style.
- [ ] 8.5 Content from `research/rust-1.99.md`:
  - **Required fixes 1–6:** including RS-TST-40 and RS-CNC-48 `#[ignore = "…"]`, RS-TST-14
    `assert_matches!`, RS-OWN-06, RS-CAR-26, RS-CLI-22 SIGPIPE, RS-CAR-10/RS-DOC-34 docs.rs, and
    RS-CAR-08 default-features.
  - **§2 tables:** the §2.2 and §2.3 additions.
  - **Should-level edits:** the rule changes the research lists.
  - **Factual slips:** those in `rust-lints-1.md` and `rust-lints-2.md` (NAM-01, UNS-24,
    review-checklist PRF-11, and `cargo-toolchain.md:499`).

  Verify: `--fast` passes. `toolchain` is deferred to 8.9.
- [ ] 8.6 Lint rows and merges:
  - demote the LINT rules in `rust-lints-1.md` and `rust-lints-2.md` that the shipped config now
    enforces;
  - merge the duplicate pairs (ERR-03/CAR-28, ERR-34/FP-08, ERR-46/CLI-20, ERR-50/CLI-22,
    OWN-22/TRG-39, OWN-25/UNS-18, STR-09/TST-04);
  - delete the pointer rules (API-73, CLI-31, ERR-39, PRF-11);
  - trim trailing cross-references that restate their target.

  Record every disposition in the rename table. Verify: `citations` and `anatomy` pass.
- [ ] 8.7 Cut every **Why** to three lines or fewer. Verify: `anatomy` passes with rust-style not
  exempt.
- [ ] 8.8 Step C: `agent-skill renumber rust-style`. Remove rust-style's exemption, update the
  frontmatter count and the §6 counts, and update `mirror`'s anchor titles where trimming changed
  them. Verify: `--fast` passes.
- [ ] 8.9 Milestone 2: one full run, alone. Verify: `ALL CHECKS PASSED`. Commit.

## 9. Harness for Bevy

- [ ] 9.1 Add the library pin kind (D11). The `bevy` requirement must be exact, and it is compared
  against crates.io's newest stable release. Verify: `pins` reports `0.19.1` as superseded by
  `0.20.0` before 10.1, and passes after it.

## 10. bevy-style (milestone 3)

- [ ] 10.1 Pins and assets:
  - `bevy = "=0.20.0"` in `lang/rust.py` and `assets/Cargo.toml`;
  - `rust-toolchain.toml` at `1.99.1`;
  - `ci.yml` at `@1.99`;
  - the `bevy-lint` job stays disabled, and its comment says no release supports 0.19 or 0.20 and
    names the open support PRs.

  Verify: `pins` and `assets` pass.
- [ ] 10.2 Step A: `agent-skill renumber bevy-style --chapters cargo=build,ui-render=view`, with
  codes per D3. Verify: `--fast` is no worse.
- [ ] 10.3 Skeleton and templates:
  - **`SKILL.md`:**
    - the H1 is `Bevy Style — 0.20`;
    - §3 is `3. Design principles`, with the departures from `rust-style` as an H3;
    - §5 is the review-order stages;
    - a new §7 lists the three assets.
  - **New `references/review-checklist.md`:** use the D8 model with Bevy examples, and every H2
    from D5.

  Then `fmt`. Verify that `skeleton` and `shared-text` pass for bevy-style.
- [ ] 10.4 Content from `research/bevy-0.20.md`:
  - every row of § Rule impacts;
  - §2.1 additions A–F, plus the `set_if_different` rename;
  - in § Forbidden-API additions: the four new rules with their `rg` Checks and `fires` fixtures,
    the nine row edits, and the `iter_many` silent-change rule with its `not_decisive` entry;
  - the pre-existing errors: BV-EVT-14 `Discard`, BV-ECS-10 lint names, `Pressed`, and the
    BV-MIG-05 grep.

  Verify that `sensitivity` proves every new pattern fires.
- [ ] 10.5 Lint rows: demote the five LINT rules the asset enables, and delete BV-ECS-19's `fires`
  fixture if it is demoted. Delete the six pointer rules and record their dispositions. Verify:
  `citations`, `anatomy` and `sensitivity` pass.
- [ ] 10.6 Cut every **Why** to three lines or fewer. Verify: `anatomy` passes with bevy-style not
  exempt.
- [ ] 10.7 Step C: `agent-skill renumber bevy-style`. Remove bevy-style's exemption, update the
  frontmatter count and the §6 counts, and make the README's count of literal `rg` Checks derived
  rather than stated (the research counts 16 where it says fifteen). Verify: `--fast` passes.
- [ ] 10.8 Milestone 3: one full run, alone. Verify: `ALL CHECKS PASSED`. Commit.

## 11. Integration

- [ ] 11.1 Update the README layout for the renamed chapters. Confirm that `zig-style` is the only
  exempt skill, and that its exemption and local-following pin carry their reasons. Verify:
  `--only documented --only skeleton` passes.
- [ ] 11.2 Run `uv run agent-skill build` and `uv run agent-skill install`. Confirm that each
  installed skill resolves to `skills/<name>`. Verify: `ls -l ~/.claude/skills/` shows the
  symlinks, and `dist/*.skill` rebuilds.
- [ ] 11.3 Verify: `openspec validate refresh-skills --strict` passes.

## Workflow follow-up

- Archive the change with `/opsx:archive` after review, which syncs `standard-structure`,
  `python-style` and `check-execution` into `openspec/specs/`.
- When `zig version` moves past 0.16.0, `pins` fails. That is the cue for the zig bump, which
  removes its exemption.
