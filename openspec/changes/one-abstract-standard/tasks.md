# Tasks

Every task ends with `uv run agent-skill check --fast`, `uv run ruff check .`, `uv run ruff format
--check .` and `uv run ty check` clean, in addition to the verification it names. A task that moves,
merges or adds rules also runs `check --skill <each standard it touched> --only toolchain` once.

## 1. Repository items and harness debts

- [x] 1.1 Update OpenSpec to 1.16.0 with skills as the one delivery (`openspec config set delivery
  skills`, `openspec update`), removing `.claude/commands/opsx/` if the update leaves it; verify with
  a test that every `.claude/skills/openspec-*/SKILL.md` names one `generatedBy`, 1.16.0, that the
  commands directory is absent, that `openspec validate --all` passes, and that this change passes
  `--strict` (the main specs' 15 requirements over 500 characters, a warning 1.15.0 gives too, stay
  whole: OpenSpec splits an existing requirement only when its owner asks)
- [x] 1.2 Move `plugin.json` to 2.0.0; verify `check --only plugin` passes and the README states the
  version's reason (rule IDs renumbered, `CORE` removed)
- [x] 1.3 Give `crossref.apparatus` findings their line (`ids.cited` yields positions); verify its
  control's finding carries the line it injected
- [x] 1.4 Take cargo's lock on the target directory around the post-run cache cleanup; verify with a
  test that cleanup waits on a held lock, and one rust-style toolchain run
- [x] 1.5 Probe the Rust `env::*` rows by compiling the call outside `unsafe` under edition 2024,
  expecting E0133; verify `check --skill rust-style --only toolchain` reports them verified, not
  unprobed
- [x] 1.6 Make `test_control_fires` use the thread-pooled runner `check --only controls` uses;
  verify every control still fires its branch alone and record the time before and after
- [x] 1.7 Make `install` exit non-zero when it leaves a differing directory alone and zero when the
  directory is identical; verify with tests for both, and that no test runs a real install into the
  user's directory

## 2. Machinery

- [ ] 2.1 Add `Relation` to `ids` (`realises`, `extends`, `tightens`, `overrides`, `decided`,
  `absent`) and one tier law with its reason rule; make the delta's departures use it; verify the
  law table by unit tests and that every existing `crossref` control still fires
- [ ] 2.2 Read the abstract standard: a profile-shaped record (prefix `AS`), chapters in the
  template, entries (heading, statement, realisation table) and `principles.md`; add a demo abstract
  standard beside `checks.demo`; verify `print ∘ parse` is the identity on it, and `fmt` idempotent
- [ ] 2.3 Add the `concepts` check (branches of design decision 3) with one control each on the demo,
  and delete `checks/mirror.py`, `profiles.record.Mirror`, every `mirror=` and the mirror controls;
  verify the controls ↔ branches bijection both ways and `check --only concepts`
- [ ] 2.4 Make `fmt` render each realisation row's tier cell from its rule; verify the `stale_tier`
  control and `fmt`'s idempotence on `abstract/`
- [ ] 2.5 Add `domain` to profiles; create an empty abstract chapter, in the template, for every
  vocabulary word that two or more base standards ship; declare each base standard's other chapters
  as domain chapters with their features, and bevy-style's; verify `check --fast` passes with no
  entries yet, and the `undeclared_domain`, `domain_realises` and `domain_missing` controls
- [ ] 2.6 Add `move` to `revise` (target chapter, `after` a rule or a section heading, creation of a
  missing chapter and its section 6 row); verify the move-and-back law by property tests on copies of
  the shipped tree with random moves, beside the existing laws
- [ ] 2.7 Write `abstract/principles.md` and the section 3 check; decide zig-style's third question
  (the shared question, answered for Zig, or zig-style's own after the five) and make every base
  standard's section 3 open with the questions; verify the `principles` control and `check --fast`
- [ ] 2.8 Add the abstract rows to `measure` (design decision 12) and record the baseline here;
  verify `measure` prints them for all four standards and the demo
- [ ] 2.9 Document the abstract standard, `concepts`, domain chapters and `revise` `move` in the
  README; verify `check --only documented`

## 3. The sweep

Each task follows design decision 6 and its criteria. In each standard's chapter X, and wherever
else that standard states X's concepts, it does the following:

- register every concept two or more base standards state as an entry in `abstract/X.md`;
- name each standard's realisation, or why its domain has none;
- move realisations into X, and merge duplicates;
- add the rule for each gap;
- settle each tier disagreement.

Each task is verified when `check --fast` passes, each touched standard's toolchain passes, and
bevy-style's departures still resolve. Each task then records its counts here: entries,
realisations by relation, moves, merges, new rules, tier changes, and look-alike notes before and
after. Each is pushed when green.

- [ ] 3.1 `errors`
- [ ] 3.2 `testing`
- [ ] 3.3 `build`, including the concept that every third-party CI action is pinned to a commit,
  realised by a new rule in each base standard
- [ ] 3.4 `naming`
- [ ] 3.5 `documentation` (zig-style's doc-comment rules among the candidates for a move)
- [ ] 3.6 `modules` (zig-style's file and module layout among the candidates)
- [ ] 3.7 `api`
- [ ] 3.8 `data`
- [ ] 3.9 `types`
- [ ] 3.10 `concurrency` (python-style's `async.md` among the candidates)
- [ ] 3.11 `output` (rust-style's `cli.md` streams and exit codes among the candidates)
- [ ] 3.12 `performance`
- [ ] 3.13 `migration`
- [ ] 3.14 Remove an abstract chapter that holds no entry, or record why it stays; declare a chapter
  the sweep emptied of realisations as domain, or remove it; verify every look-alike note left has a
  recorded reason the two rules answer different questions

## 4. Actions and CI

- [ ] 4.1 Add the eight action repositories to the session read-only, and pin every `uses:` in the
  four `ci.yml` assets to the commit of its newest release at least seven days old, with the version
  comment; `dtolnay/rust-toolchain` is pinned to a `master` commit and takes `toolchain:`; verify the
  assets' checks and toolchains pass
- [ ] 4.2 Add `pins.movable_action` and `pins.unversioned_action`, with controls; verify both fire
  alone and pass on the shipped assets
- [ ] 4.3 Write `.github/workflows/check.yml` (design decision 10), and make `selfapply` hold its
  shared steps to python-style's `ci.yml`; verify `check --fast`, a control for a drifted step, and
  the first run's result on the pull request

## 5. Evals

- [ ] 5.1 Add `Evals` selections to the profiles (two review rules, two old spellings each) and the
  selection-validity branches, with controls; verify each invalid selection fires its branch alone
- [ ] 5.2 Write the generator and `agent-skill evals`, and the `evals` check (`drift`, `extra`), with
  controls; verify by tests that each escaped literal matches itself and nothing else, and that the
  negative case's prompt is another language's
- [ ] 5.3 Generate the suite, ignore `plugins/style-standards/evals/results/`, run the no-case load
  test and record what it showed, and give the owner's command in the README; verify `check --only
  evals` and `documented`

## 6. Close

- [ ] 6.1 Record `measure`'s rows after the change beside the baseline; run the full `agent-skill
  check` once and `pytest -q`; record both results and times here
- [ ] 6.2 Bring the README in line with everything above; verify `check --only documented`

## Workflow follow-up

- Archive with the OpenSpec CLI (`openspec archive one-abstract-standard`), syncing the specs, and
  check `openspec validate --all`, and `--strict` on every requirement this change added.
- Update the pull request's description, then stop for the owner's review of Phase D.
