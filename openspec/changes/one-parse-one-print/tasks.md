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

- [ ] 3.1 Re-print all four skills canonically in one commit containing nothing else; verify
  `parse(old) == parse(new)` and that the full suite passes
- [ ] 3.2 Replace `layout`'s physical scans and `shared-text`'s copy comparison with the canonical
  comparison; keep each existing negative control firing

## 4. Findings, locations, branches

- [ ] 4.1 Give `Finding` a `Location` and a `Branch`; convert every check, deleting the intermediate
  `(message, where)`, `(row, message)` and `Verdict` forms
- [ ] 4.2 Introduce `per_skill`; delete `scope`; make `--skill` a post-filter on findings; reject
  unknown `--only`/`--skill` names
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
