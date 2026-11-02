## 1. Baseline

- [x] 1.1 Record the baseline the change is judged against: full `check` result, pytest result and
  wall-clock, `check --fast` wall-clock, per-check timings, the number of rule-ID regex literals,
  `## `-boundary scanners, fence trackers and `WIDTH` definitions in `src/` — see "Baseline
  (measured)"; the full `check` (≈22 min) and the pytest run were reported, not re-run, and
  `toolchain` and `mutation` were not timed alone
- [ ] 1.2 Enumerate every failure site in every check as a candidate branch, and record which of the
  current 65 controls fires through which branch (stub each branch, re-run its control)

## 2. The tree and the typed values

- [x] 2.1 Add `agent_skill.ids` with `RuleId`, `Tier`, `Location`, `Version`, `Pin`, `Answer`,
  `Branch`, each with one parser and one printer and property tests for `parse ∘ print = id`
  — deviates from decision 3: `RuleId` keeps the inserted letter (`ZS-CORE-12a` ships), and
  `NUMBER`/`rule_id` moved here from `vocabulary`; parsers raise `ValueError` (reading text asks the
  world nothing, so it is not a `NoAnswer`); a location outside any skill prints as `./file`
- [x] 2.2 Add `agent_skill.doc`: the fence-first block parser, the printer, and `wrap`; property
  tests for `parse(print(d)) == d` on generated trees and idempotence of `print ∘ parse`
  — the printer is `str(Doc)` and the parser `Doc.parse`, as in `ids`; blocks add `Divider` (the
  `---` after a contents list) and `Quote.alert` (GitHub's `> [!NOTE]`); seeded generators, not
  hypothesis; `WIDTH` now lives here and `text`, `shared` and `layout` import it
- [x] 2.3 Add the chapter layer (`Chapter`, `Section`, `Rule`, contents list, tool table, rename
  table) over `Doc`; verify it reads every shipped chapter and SKILL.md — `agent_skill.doc.chapter`;
  `Chapter.read(doc).doc() == doc` for every chapter and `SkillMd`, and a test holds it to `model`
  (rules, lines, contents, tool rows, rename ranges and rows, core rules, Why, Check, examples);
  `Rule` keeps its blocks in order with `relaxed`/`why`/`check`/`examples` as views rather than
  fields, `tools` and `renames` are views of their sections, and a contents label may nest labels
  (zig's `SMELL TEST`)
- [x] 2.4 Define the canonical form for the subset the skills use, and print every shipped file
  through it in a scratch tree; list every difference and classify each as a normalisation the
  spec allows or a parser bug; fix the bugs — classes and counts below; a contents entry is kept
  on one line however long, as its heading is, which decision 2 did not say

  All 61 shipped files change; `print ∘ parse` is idempotent on every one, and the parsed tree of
  the canonical text equals that of the original. 1,839 of 45,914 lines are rewritten. Counted by
  block, top level, against the original lines:

  | Normalisation (a) | Count | Files |
  |---|---|---|
  | paragraph re-filled greedily to 100 columns | 527 | 60 |
  | list whose item text is re-filled (core rules, numbered steps, bullets) | 53 | 17 |
  | block quote re-filled | 7 | 4 |
  | blank line added after a heading (zig's rule headings sit on their first line) | 247 | 9 |
  | blank line added before a heading (`## Contents` straight after the scope) | 23 | 23 |
  | blank line added between a paragraph and the list it introduces | 9 | 3 |
  | blank line added after a fence | 1 | 1 |
  | loose contents list gets a blank before its last item, `- Decided by tools` | 17 | 17 |

  Re-filling also joins about 64 code spans that were broken across two lines (128 unfenced lines
  hold an odd number of backticks), so a span such as `` `b: *Build` `` or a citation such as
  `` `references/memory.md` ZS-MEM-06 `` now sits on one line; and it folds
  `rust-style/references/traits.md:801`, a wrapped line that began `+ Send>>` and so rendered as a
  list item, back into its paragraph. Five zig quotes open `> [!NOTE] text` on one line, which
  GitHub does not render as an alert; the canonical form keeps them as written, for the content
  change to decide.

  | Parser or printer bug (b), fixed | Where |
  |---|---|
  | a GitHub alert's `> [!NOTE]` line was filled into the paragraph after it, ending the alert | 3 quotes, `zig-style` memory and migration — `Quote.alert` |
  | a contents entry over 100 columns was wrapped, which every line-wise reader truncates | 9 entries, 6 files — printed on one line |
  | an empty table cell printed as `\|  \|` where every table writes `\| \|` | 3 rows, 2 files |
  | two same-kind lists at different indents parsed as two lists that print as one | found by the noise generator, not the corpus — merged on parse |

  Risk for 3.1, not a defect here: the old line-wise readers will see the joined citations and code
  spans for the first time (`anatomy`'s citation pattern needs a citation on one line), so 3.1 may
  surface findings the split lines hid.

## 3. Canonical re-print

- [x] 3.1 Re-print all four skills canonically in one commit containing nothing else; verify
  `parse(old) == parse(new)` and that the full suite passes — `18315b8`, held to it by
  `tests/test_reprint.py` (tree equal, `new == canonical(old)`, fence bodies and `Skill.blocks`
  identical); four line-wise readers fixed first, two Whys fixed after (below)
- [x] 3.2 Replace `layout`'s physical scans and `shared-text`'s copy comparison with the canonical
  comparison; keep each existing negative control firing — `layout` reports the first line that
  differs from `canonical(file)` and keeps branches only for what printing leaves as written;
  `shared-text` aligns template and passage as trees; every control fires, one added

  Before the re-print every writer was aligned with the printer: `fmt`, `shared.rewrite`,
  `renumber` (with `carry`) and `demote` all write `doc.canonical`, and `text.reflow` and
  `shared.wrap` are deleted. Decisions made on the way:

  - `renumber` re-prints only a standard's markdown. The README, sources and tests keep their
    line breaks: nothing holds them to the canonical form, and re-printing them would rewrite text
    the renumbering did not touch.
  - `shared.render` returns blocks and a list is numbered by printing, so `_renumber` went too;
    `shared.rewrite` splices the template's blocks into the file's tree and prints the whole file.
  - `Fence.closed` (not compared) records a fence the file ends inside, so `layout` reports it as
    a file that does not parse as written instead of as a non-canonical last line.
  - `layout` measures widths, kept tabs and CRs on the canonical text, so a defect the printer
    removes is reported once. A table row inside an example stays unmeasured, as before. Files
    are read with `newline=""`: read the usual way every CR was already a line break, so the old
    `CR present` branch could not fire. `fmt` reads the same way.
  - A code span or link wider than the line is a note (decision 2); the re-print joins twelve
    such spans that the old wrapping had split, mostly `rg` commands in bevy's migration chapter.

  What the re-print surfaced, checked by diffing every finding of `check --fast --verbose` before
  and after, and by counting what the line-wise citation reader matched:

  | Finding | Kind | Resolution |
  |---|---|---|
  | ZS-CONC-25, ZS-CONC-33, ZS-TEST-10 "is [M!] with no relaxed form" | reader | `*Relaxed`/`form:*` on two lines; the label is matched across whitespace |
  | zig `performance.md` "bold-inline rule definitions" | reader | `**ZS-BUILD-25**` mid-paragraph opened a line; a definition is a paragraph that opens with one |
  | twelve "prose line is N columns" | reader | code spans no line can hold; notes, as decision 2 says |
  | none: `_paths` read 302 citations before and 294 after | reader | read across a line break, not a blank line: 323 both ways |
  | RS-TRAIT-36 "Why runs 4 lines" | content | the 101-column type moves into the statement the rule lacked |
  | ZS-ERR-18 "Why runs 4 lines" | content | two words cut |

  The `_core_citations` control relied on line-wise `_paths` missing a citation split across
  lines; it now puts the wrong chapter on a list's second ID, which `_paths` does not read. The
  prose-width control is now a non-canonical paragraph, owned by `_canonical`; a new control, an
  example line over the limit, keeps `_widths` covered.

## 4. Findings, locations, branches

- [x] 4.1 Give `Finding` a `Location` and a `Branch`; convert every check, deleting the intermediate
  `(message, where)`, `(row, message)` and `Verdict` forms — `ee747de`; 265 branches over 22
  checks and 8 of `fmt`, each a module constant beside the sites that fire it
- [x] 4.2 Introduce `per_skill`; delete `scope`; make `--skill` a post-filter on findings; reject
  unknown `--only`/`--skill` names — `ee747de`; `model.Tree` is the skills, `PerSkill` lifts a
  check of one skill, `Result.within` filters, and per-skill checks read only the chosen skills

  Decisions made on the way:

  - A branch name is snake case and its check's name stays kebab case (`shared-text.differs`), so
    `Branch` takes two grammars (`e70b04d`).
  - Branches are module-level constants (`DISABLED_CODE = Branch("citations", "disabled_code")`)
    beside the sites that fire them, so 5.2 can collect them without running anything. A profile's
    own rules fire through `conventions` or `prose` with the standard's prefix (`rs_setter`,
    `zs_unwrap`), declared in the profile; a toolchain's steps through `toolchain` or `mutation`
    with the language's (`py_run`, `zig_fmt`), declared in `lang/`. `fmt` reports through
    `Branch("fmt", …)`: a command, not a check, so outside the bijection.
  - `Tree` is `tuple[Skill, ...]` and nothing else. The checks that read beside the skills
    (`plugin`, `documented`, `controls`) still find the repository from the first skill's root.
  - `@check(...)` sits above `@per_skill`, so the module name is the lifted check and `.each` the
    function of one skill; `PerSkill.__wrapped__` lets `inspect.unwrap` find its source.
  - A per-skill check reads only the chosen skills, which keeps every finding the filter would
    only if each finding lies in the skill it was reading. `tests/test_controls.py` holds every
    per-skill control to that. The controls narrow through the same `Check.run(about=…)`.
  - `pins` is a tree check: the harness's tool pins lie at `./pyproject.toml`, in no skill, so a
    per-skill `pins` would have broken that law. Reading every skill made each pin control ask the
    network about Rust and Bevy too, so `_stable` and `_crates_io` answer once a process; the
    controls cost what they did (21.8 s against 23.6 s at `a7b3094`, same machine, same script).
  - `fast` stays a keyword only `controls` takes: it is a fact about the run, not the tree.
  - A location names a chapter by its path in the skill (`references/errors.md`), and a finding
    about a rule now carries its heading's line where the old one named only the chapter. A
    message that spelled its file by hand (`assets/ci.yml …`, `` `plugin.json` is missing ``) gave
    the file to the location; `shared-text` gives the line of the differing block, not `§ section`.
  - A Rust mutant is found in the crate's module file, which no `Location` can name until a unit
    keeps its block (decision 6's open question): it lies in the skill, and the module's line leads
    its message.
  - For 5.1: 22 of the 23 controls in `BRANCHES` fire exactly one branch, and it is a branch of
    the function their entry names (`citations.disabled_code`, `layout.canonical`,
    `skeleton.rename_self`, …). The compiler row control fires `citations.zig_no_probe` and
    `citations.zig_probe_no_row`: misspelling the row's lint leaves a row without a probe and a
    probe without a row, never a probe printing another error (`zig_probe_other`).

  `check --fast --verbose` before and after differ in 32 lines, all rendering: 30 `layout` notes
  name `skill/references/x.md` for `skill/x.md`, and 2 `mirror` notes are located at
  `python-style [PS-NAME-18]` and `[PS-NAME-19]` where they printed the check's name. With those
  two spellings mapped back the outputs are identical. `check --skill zig-style --only toolchain
  --only mutation` passes in 2 min; its nine mutation notes now name their skill
  (`zig-style/references/build.md:1297 [ZS-BUILD-38]`), which the unit's `chapter:line [rule]`
  left out.
- [ ] 4.3 Move `skeleton`, `anatomy`, `crossref`, `mirror`, `citations` and `assets` onto the tree,
  deleting their own scanners; verify the regex-literal count from 1.1 falls to the one in `ids`

## 5. Controls as a bijection

- [ ] 5.1 Convert every control to `Control(branch, inject)` with `inject` returning touched paths;
  delete `TOUCHED`, `BRANCHES` and the test monkeypatching; one runner, run concurrently
- [ ] 5.2 Add the bijection test; for each uncovered branch add a control or an exemption with its
  reason; report the count added

## 6. Profiles as records

- [ ] 6.1 Convert each profile to a frozen record; move `MIRROR`, `FIXTURES`, the delta anchor, the
  ty rule table, the harness tool pins and every other per-skill constant out of `checks/`
- [ ] 6.2 Replace convention and prose functions with `LineRule` data and one engine; verify every
  existing finding is reproduced
- [ ] 6.3 Add the test that no generic module contains a skill or toolchain name literal

## 7. Toolchains

- [ ] 7.1 Express Python, Rust and Zig as extract/restore pairs with `Unit` carrying its `Block`;
  property-test `restore ∘ extract = id` on every shipped skill
- [ ] 7.2 One driver for compile, test, format and mutate with one timeout policy; delete the
  per-language loops
- [ ] 7.3 Derive `fmt` from the pair for every toolchain; verify `fmt` is idempotent on the repo

## 8. Revision

- [ ] 8.1 Implement `revise(tree, plan, chapters)` over the tree with the dangling-capture refusal
- [ ] 8.2 Property-test the laws: inverse round trip byte-for-byte, empty plan writes nothing,
  citation identity preserved
- [ ] 8.3 Move each rename table to `references/renames.md`; `migration.md` names it once; update
  `skeleton`; keep `renumber` and `demote` as CLI aliases

## 9. Close

- [ ] 9.1 Delete every superseded parser, regex, helper and adapter; add the test that fails on a
  second spelling of any concept from 2.1
- [ ] 9.2 Re-measure everything in 1.1 and record the deltas in this file
- [ ] 9.3 Update README sections that describe the harness's internals; `documented` passes

## Baseline (measured)

Taken at `4b46e84`, on a 4-core container, Python 3.15.2 (free-threaded), before any code of this
change landed. Times are one wall-clock run each, through `uv run`; every `--only` run includes the
≈0.18 s that `uv run agent-skill --help` takes to start and exit.

| Measure | Value | How |
|---|---|---|
| full `check` | ≈22 min | reported for this commit; not re-run in this step |
| `check --fast` | 33.4 s, all passed | `time uv run agent-skill check --fast` |
| pytest, not toolchain | 543 passed, 4 deselected, ≈2 min 35 s | `uv run pytest -q -m "not toolchain" -p no:cacheprovider` |
| rule-ID regex literals | 33 lines | `rg -n --type py '\[A-Z\]\+\)?-\(?\\d\|rule_id\(\|NUMBER' src/` |
| heading scanners | 24 lines | `rg -n --type py -g '!**/checks/controls.py' -e 'startswith\("#+ ' -e '\^#' -e '\\n##' src/` |
| fence trackers | 19 lines | `rg -n --type py -F '```' src/ \| grep -v '^\S*:\s*#'` |
| `WIDTH` definitions | 3 | `rg -n --type py 'WIDTH\s*=' src/` (`text.py`, `shared/__init__.py`, `checks/layout.py`) |

The heading-scanner pattern counts every line that finds a heading by its `#` text (`## ` boundaries,
`### ` rule heads, the H1 lookups in `skeleton`); `controls.py` is excluded because its hits are
injected fixture text, not scanners. The fence count includes the two lines in `fmt.py` that locate a
block by rebuilding its fence text.

Per-check, `uv run agent-skill check --fast --only NAME` (seconds):

| Check | s | Check | s | Check | s |
|---|---|---|---|---|---|
| `anatomy` | 2.34 | `dialect` | 0.62 | `pins` | 1.37 |
| `assets` | 0.78 | `documented` | 0.14 | `plugin` | 1.62 |
| `citations` | 2.35 | `frontmatter` | 0.61 | `prose` | 0.38 |
| `controls` | 19.93 | `layout` | 0.26 | `self-application` | 3.13 |
| `conventions` | 0.25 | `lints` | 0.16 | `sensitivity` | 1.08 |
| `crossref` | 0.72 | `markers` | 0.25 | `shared-text` | 0.70 |
| `mirror` | 0.94 | `skeleton` | 0.65 | | |

`toolchain` and `mutation` are the two slow checks; they are most of the 22 minutes and were not
timed alone, for the same reason the full check was not re-run.
