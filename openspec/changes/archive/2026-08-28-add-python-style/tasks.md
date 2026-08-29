## 1. Pin the toolchain

- [x] 1.1 Install `cpython-3.15.0rc1+freethreaded` via `uv python install` and verify
  `uv python find` resolves a binary where `sys.version_info[:2] == (3, 15)`,
  `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`, and `sys._is_gil_enabled()` is `False` — all
  three, because `_is_gil_enabled()` returns `True` unconditionally on a GIL build and so cannot by
  itself prove which interpreter was resolved
- [x] 1.2 Pin `ty==0.0.74` and `ruff==0.16.4` exactly in the `dev` group and verify the reported
  versions match — exact pins, not floors, because ty states diagnostics may change between any two
  versions
- [x] 1.3 Install `pytest==9.1.1` for the pinned 3.15t interpreter, separately from the repo's own
  3.14t venv, and verify `pytest --version` under that interpreter reports 9.1.1 — four chapters
  depend on pytest 9 behaviour and nothing currently installs it
- [x] 1.4 Broaden the `toolchain` pytest marker description in `pyproject.toml` beyond "needs cargo
  or zig" and verify `uv run pytest --markers` shows the new text

## 2. Checker surface

Design Decision 17. The three existing skills are the regression control for this whole group: after
every task here, `uv run agent-skill check` must still report `ALL CHECKS PASSED` and
`git diff --stat skills/` must be empty.

- [x] 2.1 Move the marker vocabulary from the `MARKERS` module global in `model.py` onto `Profile`,
  defaulting to `("verified", "fragment", "does-not-compile")`, and have `checks/markers.py` build
  its `LEADS` from the profile rather than the global; verify rust, zig and bevy are unchanged and a
  profile declaring an extra marker accepts it while the others still reject it
- [x] 2.2 Teach `text.py::strip_comment` the comment syntax of the language it is reading, and verify
  `q = total // count` survives intact for Python while `url = "https://x"` still survives for Rust —
  today it returns `q = total `, silently truncating every line after a floor division
- [x] 2.3 Extend `checks/selfapply.py::FILE_ARG` to recognise `*.py` and the TOML asset names, and
  verify a `**Check:**` whose command names `pyproject.toml` treats it as a file argument rather than
  compiling it into a pattern — a command-kind hit is a hard failure, so this currently turns every
  example mentioning the filename into a build break
- [x] 2.4 Make `checks/mirror.py` operate over every registered pair rather than the hardcoded
  `ANCHOR, MIRRORED = "rust-style", "zig-style"`, and verify it reports a deliberate tier
  disagreement introduced between `python-style` and a sibling
- [x] 2.5 Generalise the empty-corpus guard in `checks/controls.py` beyond its literal
  `("rust-style", "rust"), ("zig-style", "zig")` list, and verify an extractor that returns zero
  units is reported rather than passing clean
- [x] 2.6 Add a third outcome to `report.py` meaning *could not run*, distinct from `FAIL` and
  `NOTE`, and verify a run containing one is not reported as a clean pass
- [x] 2.7 Replace the single `shutil.which` probe in `checks/toolchain.py` with one that can resolve
  a uv-managed interpreter and can probe several tools, and verify each of an absent interpreter, an
  absent `ty`, and an absent `ruff` is reported under 2.6's outcome
- [x] 2.8 Guard the `mutation` check against a toolchain that implements no `mutate`, and verify
  `agent-skill check` reports rather than raising `AttributeError` — `Toolchain` is a `Protocol`, so
  nothing enforces the method at runtime and the call sits in a check with no `try`
- [x] 2.9 Lift the `profile.crate is None` early return in `fmt.py` so a non-Rust toolchain can
  format, and verify `agent-skill fmt` is reachable for a profile with `crate = None`
- [x] 2.10 Update `cli.py`'s `fmt` help text, which reads "rewrite each rust example as rustfmt would
  have it", and verify `--help` no longer names one language

## 3. Walking skeleton

**Ordering correction found during apply:** task 5.1 (the profile) must land
*before* this group. Without it `profile_for("python-style")` falls back to a
guessed `Profile` whose `languages` is empty, so `all_marked` is empty and
`markers`, `selfapply` and `conventions` iterate nothing — the skeleton would
report green while no check had looked at a single example. 5.1 is done.

Design Decision 14: the checker has no partial-credit mode. `anatomy` sums the reference map's
per-family counts against the rules present and `frontmatter` checks the stated `<N>-rule` count, so
the first deliverable is a skill that is check-clean while nearly empty.

- [x] 3.1 Write `skills/python-style/SKILL.md` with all seven sections present — frontmatter, `How to
  use this standard`, §1 Tiers, §2 reality check, §3 Design principles, §4 Core rules, §5 Review
  checklist, §6 Reference map, §7 Bundled assets — and verify `frontmatter`, `layout` and `prose`
  pass with the stated rule count equal to the rules actually present
- [x] 3.2 Write `references/free-threading.md` (`PS-FT`) as the one real chapter, and verify
  `anatomy` passes with the §6 reference map's per-family count equal to its rules
- [x] 3.3 Write the four assets — `ruff.toml`, `ty.toml`, `pyproject.toml`, `ci.yml` — and verify the
  `assets` check parses each and reports nothing unreferenced, which requires each to be named from
  §7
- [x] 3.4 Verify `uv run agent-skill check` reports `ALL CHECKS PASSED` with the skeleton in place —
  this is the state every later task must return to

## 4. Assets, in detail

- [x] 4.1 In `assets/ruff.toml` set `target-version = "py315"`, `line-length = 88`, `[lint] preview =
  true` with `explicit-preview-rules = true`, `select` replacing rather than extending the 413-rule
  default set, the 15 formatter-conflicting rules ignored, `D203`/`D213` resolved against
  `D211`/`D212`, `[lint.flake8-type-checking] runtime-evaluated-base-classes` set, `[format]
  line-ending = "lf"`, and **top-level** `output-prefer-rule-codes = true` — verify ruff parses it,
  and specifically that `output-prefer-rule-codes` is rejected if placed under `[lint]`
- [x] 4.2 In `assets/ty.toml` name the twelve ignore-by-default rules and nothing else per design
  Decision 4 — eight at `error`, the four Astral documents as false-positive-prone at `warn` — and
  verify `ty` accepts it, that every name resolves in the pinned `ty`'s catalogue, and that no
  warn-by-default rule is listed, since promoting one changes only the printed label
- [x] 4.3 In `assets/pyproject.toml` cover PEP 621 metadata, SPDX `license` as a string with
  `license-files`, `[dependency-groups]` rather than `[project.optional-dependencies]` for dev tools,
  `py.typed`, and src layout; verify it parses and no deprecated `License :: OSI Approved ::`
  classifier appears
- [x] 4.4 Configure pytest in that asset under `[tool.pytest]` with native TOML types and
  `strict = true`, never `[tool.pytest.ini_options]`; verify pytest 9 accepts it and that the two
  tables cannot coexist, its own error naming `[tool.pytest]` as recommended
- [x] 4.5 In `assets/ci.yml` pin the interpreter, `ruff`, `ty` and `pytest` by exact version and run
  them as required gates, and verify the `assets` check validates its workflow keys and indentation
  and that the pinned versions match the mandate rule in `PS-TYPE`

## 5. Harness

- [x] 5.1 Add `src/agent_skill/profiles/python_style.py` declaring prefix `PS`, `languages` matching
  the fence tag exactly, `marked_languages` covering the TOML assets shown in `PS-PKG` and `PS-TEST`,
  the toolchain, the marker set from 2.1, `inside_tests`, and non-empty `conventions()` and
  `prose()`; verify `profile_for("python-style")` returns it and that `conventions` is not a silent
  no-op, since it will still be required to carry a control
- [x] 5.2 Add `src/agent_skill/lang/python.py` extracting every `# verified` block into the temporary
  directory `checks/toolchain.py` supplies — not a persistent cache root, which the extractor does not
  choose — and verify one file per block with line numbers pointing back at the markdown
- [x] 5.3 Execute each block on the pinned interpreter in an isolated working directory under a
  timeout, and verify a block that raises is reported at its markdown line, proven with a fixture
- [x] 5.4 Run `test_*` functions with the pinned `pytest` on the pinned interpreter, and verify a
  block whose shipped test fails is reported
- [x] 5.5 Implement `mutate` for Python — delete one statement from a block that ships tests and
  assert a test fails — and verify a block whose test passes either way is reported, satisfying the
  `mutation` check that 2.8 makes safe to call
- [x] 5.6 Type-check every block with `ty` and lint it with `ruff`, parsing diagnostics rather than
  gating on exit status per design Decision 15, and verify a non-zero exit with no parsed diagnostic
  is itself a finding
- [x] 5.7 Verify a type error in a branch execution never reaches is still reported, and that a lint
  violation is reported at its markdown line by code rather than by rule name
- [x] 5.8 Register `"python"` in `toolchain_for` and the new check module in `checks/__init__.py`,
  and verify `agent-skill check` dispatches both — a check is unreachable until its module is
  imported in `all_checks`

## 6. The two equality invariants

Design Decision 16: verification runs under the harness's own declaration, and the assets are data
compared against it. An asset that is also the configuration in force cannot be checked.

- [x] 6.1 Declare the ruff selection and the `ty` rule levels in the harness, independently of the
  assets, and verify verification uses the harness declaration rather than reading the asset
- [x] 6.2 Implement the ruff-code invariant of design Decision 1 — every code a rule cites must be
  enabled by the asset — computing the enabled set from `ruff check --no-cache --show-settings` and
  parsing **both** `linter.rules.enabled` and `linter.per_file_ignores`, since the latter does not
  merge into the former; verify a rule citing a disabled code is reported
- [x] 6.3 Exclude ruff's 18 `Removed` codes, sourced from `ruff rule --all --output-format json`, and
  verify a rule citing `ANN101` or `UP038` is reported — selecting one is a hard `ruff failed`
- [x] 6.4 Implement the `ty` invariant — the harness declaration equals `assets/ty.toml` — and verify
  a divergence in either direction is reported
- [x] 6.5 Validate every rule name in `assets/ty.toml` against the pinned `ty`'s own catalogue, and
  verify a name it does not recognise is reported, so a rename in a release cannot leave a setting
  that silently stopped applying
- [x] 6.6 Add a regression test asserting the enabled rule set under `[lint] preview = true` with
  `explicit-preview-rules = true` is identical to the set under `preview = false`, and verify it
  fails if `explicit-preview-rules` is removed
- [x] 6.7 Populate `not_decisive` only once the rules it names exist, and verify a stale anchor is
  reported — `selfapply` fails on an entry naming a rule the skill does not define, and `crossref`
  scans `src/**/*.py` for rule ids, so an early entry breaks two checks

## 7. Formatting

- [x] 7.1 Extend `fmt.py` to reformat Python examples in place with `ruff format` using the same
  extraction the check uses, and verify a deliberately misformatted example is rewritten by
  `agent-skill fmt` and then reports clean
- [x] 7.2 Verify no enabled lint rule conflicts with the formatter by comparing the selection against
  ruff's documented 15-rule list directly — **not** by checking that `ruff format --check` is
  warning-free, which detects only `COM812` and `D203` of the fifteen and would pass a config that
  ignores two of them

## 8. Negative controls

- [x] 8.1 Add a control per new check from groups 5 and 6, each injecting the defect that check owns
  into a copy of the tree, and verify `agent-skill check` reports a failure for each
- [x] 8.2 Verify each control fails when its own check is disabled, and fails rather than silently
  injecting nothing when its anchor text has drifted out of the skill
- [x] 8.3 Make `controls` skip controls whose owning check is `slow`, and verify `check --fast`
  does not execute the interpreter, `ty` or `ruff` — `controls` is not itself marked slow and re-runs
  each owning check, so without this `--fast` runs the whole Python toolchain once per control
- [x] 8.4 Verify `uv run pytest` runs the new controls as one test each, and that
  `test_every_check_has_a_control` still passes without adding the new checks to its exemption set

## 9. Chapters

The reading order of design Decision 11. `references/free-threading.md` is absent because it is the
walking skeleton's chapter, written in task 3.2. Each task here updates the §6 reference map count
and the frontmatter rule count in the same change, because `anatomy` and `frontmatter` fail otherwise.

- [x] 9.1 Write `references/naming-and-layout.md` (`PS-NAME`), stating the PEP 8 line-length
  disagreement explicitly per design Decision 8, and verify the full suite passes
- [x] 9.2 Write `references/typing.md` (`PS-TYPE`) — forbidding `from __future__ import annotations`
  outright, since it silently degrades `annotationlib` `VALUE` and `FORWARDREF` to bare strings — and
  verify the full suite passes
- [x] 9.3 Write the `[M]` rule in `PS-TYPE` mandating `ty` at the pinned version with
  `assets/ty.toml`, quoting ty's own `0.0.x` version policy, the bump procedure, and that a second
  checker is permitted but not promised to agree; verify the rule's `**Check:**` is the runnable `ty
  check` invocation and that the cited version matches the asset and the CI workflow
- [x] 9.4 Verify the standard nowhere weakens a rule to make a second checker agree — PEP 728
  `extra_items=` and PEP 661 `sentinel()` appear without a caveat, both being specified and accepted
  by `ty`
- [x] 9.5 Write `references/data-modelling.md` (`PS-DATA`) and verify the full suite passes
- [x] 9.6 Write `references/errors-and-control-flow.md` (`PS-ERR`) and verify the full suite passes
- [x] 9.7 Write `references/async.md` (`PS-ASYNC`) using `asyncio.Runner`/`loop_factory` and
  `inspect.iscoroutinefunction` so the examples survive 3.16's removal of the event-loop policy
  system, and verify the full suite passes
- [x] 9.8 Write `references/strings-and-output.md` (`PS-FMT`) and verify the full suite passes
- [x] 9.9 Write `references/performance.md` (`PS-PERF`), citing the benchmark dashboards and the date
  read rather than the docs' single overhead figure, and verify the full suite passes
- [x] 9.10 Write `references/api-and-modules.md` (`PS-API`) covering re-export form, `py.typed` and
  PEP 810 lazy imports, and verify the full suite passes
- [x] 9.11 Write `references/documentation.md` (`PS-DOC`) and verify the full suite passes
- [x] 9.12 Write `references/testing.md` (`PS-TEST`) per design Decision 12 — the native
  `[tool.pytest]` table, the `strict` umbrella, subtests versus parametrization, argument
  deduplication and CI detection — and verify the full suite passes
- [x] 9.13 Write the `PS-TEST` rule on config discovery order, quoting pytest's actual warning
  `configfile: pytest.toml (WARNING: ignoring pytest config in pyproject.toml!)`; verify the rule
  does **not** describe it as silent and that it is not added to the §2 reality check, which is
  reserved for changes producing no diagnostic at all
- [x] 9.14 Write `references/packaging.md` (`PS-PKG`) — including that a `cp3XXt` wheel tag is not a
  free-threading declaration, with the SQLAlchemy 2.0.49 and lxml cases as evidence — and verify the
  full suite passes
- [x] 9.15 Write `references/migration.md` (`PS-MIG`) with the dead-API table tiered per design
  Decision 10, and verify the runnable grep finds every removed name in a fixture, finds none in the
  skill, and does **not** flag `re.match`, which is soft-deprecated with no warning and no removal
- [x] 9.16 Add pytest's own removal ladder to `PS-MIG` — what `PytestRemovedIn9Warning` took in 9.1
  and what `PytestRemovedIn10Warning` opened — tiered by the same rule, so a deprecation is not
  reported as a removal

## 10. Cross-cutting content

- [x] 10.1 Complete `SKILL.md` §2 covering every item its spec requires at minimum — free-threading,
  lazy annotations, lazy imports, `frozendict`, `sentinel`, UTF-8 as the default encoding, unpacking
  in comprehensions, and the typing additions — plus the `contextlib` `ContextDecorator` lifetime
  change and `singledispatchmethod`'s dispatch argument; verify each entry produces no diagnostic at
  all, which is the section's admission criterion, and that every example passes the harness
- [x] 10.2 Write §3 `Design principles — one obvious way, and symmetry`, closing with the
  five-question tie-breaker both anchor siblings carry, and verify `layout` and `prose` pass
- [x] 10.3 Write §4 `PS-CORE` last, with no letter suffixes so no chapter needs renumbering, each
  rule citing the chapter that owns it; verify `anatomy` reports no dangling or mis-filed reference
- [x] 10.4 Write §5 and `references/review-checklist.md` with the severity model, review order,
  mechanical commands and output format, and verify `prose` and `layout` pass
- [x] 10.5 Complete §6 and §7 and verify every chapter and asset is listed, the per-family counts sum
  to the rules present, and the frontmatter count matches — the two checks that fail at every
  intermediate state
- [x] 10.6 Verify by reading, not by `anatomy`, that each chapter opens with a scope paragraph and a
  sources paragraph and that no rule sits in a chapter its ID prefix does not name; `anatomy` checks
  contents-equals-headings, ascending ids and unique titles, and none of these three
- [x] 10.7 Verify no rule anywhere cites a ruff code as its sole check where ruff cannot decide it,
  and that `PS-FT` cites none at all, ruff having zero free-threading rules
- [x] 10.8 Add the rule forbidding `ty`'s non-standard intersection types as non-portable, and verify
  no example relies on a checker extension outside the Typing Spec — the boundary being that
  specified-but-unimplemented is permitted while implemented-but-unspecified is not
- [x] 10.9 Verify the rule count is a consequence of the coverage rather than a target the coverage
  was bent to: no chapter below 14 rules, each inside the siblings' observed 14–84 rules-per-chapter
  band, and the frontmatter count equal to what is shipped. Delivered **306** — 280 chapter rules
  plus 26 core — against a planning target of 440–480; design Decision 11 records why that target
  was the wrong instrument and is revised rather than met. Chapters run 16 to 26 rules at 14.2 to
  34.4 lines per rule

## 11. Repository integration

- [x] 11.1 Update `README.md` — the layout, the check table with each new check and the defect it
  catches, the marker legend gaining a per-language fourth form, the toolchain notes, and the two
  statements this change falsifies: that a profile naming a `toolchain` also names a `Crate`, and the
  three-line marker legend; verify `crossref` still passes, since it is the check that reads the
  README
- [x] 11.2 Verify `uv run agent-skill install` symlinks `python-style` into every agent directory
  present, and `uv run agent-skill build` packages `dist/python-style.skill`
- [x] 11.3 Verify the three existing skills are byte-identical to their pre-change state and still
  check clean — the regression control for every task in group 2

## 12. Final verification

- [x] 12.1 Run `uv run agent-skill check` and verify `ALL CHECKS PASSED`
- [x] 12.2 Run `uv run agent-skill check --fast` and verify it completes without executing the
  interpreter, `ty` or `ruff`
- [x] 12.3 Run `uv run pytest` and verify every test passes, including every negative control
- [x] 12.4 Make the interpreter pin's expiry a check rather than a diary entry: `checks/pins.py`
  fails when a release newer than the pin exists **within the pinned minor series**, so a newer patch
  or candidate is a pin refresh while a newer minor stays a deliberate change of target this check
  has no business demanding. Verify both directions — clean at `3.15.0rc1`, and reporting `3.14.7`
  when pinned at `3.14.0` — and verify the release ordering puts `rc2` after `rc1` and before the
  final `3.15.0`, which a string comparison gets backwards
- [x] 12.5 Make the pin verifiable rather than merely stated: `assets/ci.yml` installs the exact
  build the harness verifies against, `pins` compares the two declarations, and its failure message
  carries the whole procedure — move the pin in `lang/python.py` and `assets/ci.yml`, re-verify the
  `PS-MIG` table against the released What's New, re-run the suite. Add the negative control and
  verify `test_every_check_has_a_control` still passes without an exemption

**Why these two changed.** As written they said "on 1 September move the pin to `3.15.0rc2`" and "on
or after 1 October move it to `3.15.0`". Neither release exists — `uv python list` offers `rc1` as
the newest 3.15 today — so neither task could be executed, and neither traced to any requirement in
either spec. They were calendar maintenance of a delivered artefact, parked inside the change that
delivers it, which would leave this change permanently incomplete for reasons outside its own scope.
The dated steps now live in design.md's Migration Plan, where post-landing work belongs, and the
thing that was actually buildable today — making the expiry announce itself — is built and
controlled. A check that fails is this repository's answer to a note nobody reads.

## 13. Astral-exclusive toolchain

- [x] 13.1 Rewrite `PS-PKG-12` to name `uv_build` as the sole backend, `requires =
  ["uv_build>=0.12.6,<0.13"]` / `build-backend = "uv_build"`, and state why the upper bound does not
  contradict `PS-PKG-04`'s floor-and-no-ceiling rule for `requires-python`
- [x] 13.2 Fix `assets/pyproject.toml`, which does not build: rename the distribution to
  `acmewidget` so it matches the module, switch `[build-system]` to `uv_build`, and verify with
  `uv build` that a wheel is produced containing `acmewidget/py.typed`
- [x] 13.3 Add a rule requiring distribution name and module name to match, with the override each
  backend needs when they do not as the counter-example — this is what makes 13.2's fix a rule
  rather than a one-off repair
- [x] 13.4 Remove `hatchling` from every chapter and asset, including the `PS-PKG-13` claim about
  which backends ship `py.typed` automatically
- [x] 13.5 Remove `pip`, `python -m build`, and the `pylock.toml` export: rewrite `PS-PKG-10` so
  `uv.lock` is the only lock artefact, and drop the `--uploaded-prior-to` half of the supply-chain
  cooldown rule, keeping `uv`'s `--exclude-newer`
- [x] 13.6 Re-run `citations` and `pins` after the removals and confirm no rule now cites a tool the
  standard no longer requires

## 14. Pure-Python scope

- [x] 14.1 Remove `Py_mod_gil` as a named C-API slot from `PS-FT-01` and anywhere else it appears,
  rewriting each site to state the consumer-side fact instead: a free-threaded build can re-enable
  the GIL at import time, permanently and process-wide
- [x] 14.2 Verify `PS-FT-01`'s rationale still stands on its own after 14.1 — the rule distinguishes
  a build probe from a runtime probe, and that distinction must remain justified
- [x] 14.3 Drop `PEP 803` from the free-threading chapter's source list, since `abi3t` is not taught
- [x] 14.4 Grep for every remaining reference to compiled extensions, wheels-per-platform, and ABI
  tags; remove or rewrite each, and record in `design.md` anything deliberately kept

## 15. Type-checker exclusivity

- [x] 15.1 Remove every `mypy` and `pyright` mention from `SKILL.md`, `references/typing.md`, and
  `references/api-and-modules.md`, rewriting each claim to rest on the specification rather than on
  what another checker does — a construct is used because it is specified, not because `ty` accepts
  it where others do not
- [x] 15.2 Verify no rule lost its justification in 15.1: each rewritten site must still say why the
  construct is permitted, and `specs/python-style`'s portability requirement must still hold

## 16. Close the asset-verification blind spot

- [x] 16.1 Extend the `assets` check to build `assets/pyproject.toml` with the pinned backend in a
  temporary tree and fail if the build fails — the defect 13.2 fixes passed all sixteen checks and
  109 tests because nothing ever built the template
- [x] 16.2 Assert the built wheel contains `acmewidget/py.typed`, so `PS-PKG-13`'s claim about the
  built artefact is verified against the artefact rather than against the backend's documentation
- [x] 16.3 Add the negative control: break the template's build, assert the check reports it

## 17. Re-verification

- [x] 17.1 Run `uv run agent-skill check` and confirm all checks pass on all four skills
- [x] 17.2 Run the full `pytest` suite on an idle machine with the disk checked first, and confirm
  no regression
- [x] 17.3 Re-run the rule count and update it wherever `design.md`, `proposal.md`, and `SKILL.md`
  state it, since 13, 14, and 15 all delete rules
