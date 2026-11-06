## Context

`one-parse-one-print` gave the harness one tree, one type per concept and checks that are maps over
the tree. The four standards still differ below the level `skeleton` compares, as the proposal
measures. This change states the normal form each kind of statement takes, makes every one of them
a property a check decides, and brings the standards into it.

Three resolutions made after `one-parse-one-print` set the pattern every decision here follows:
"published" defined once and taken as the subject of four rules that had relaxed forms; PS-API-11's
exception handed to the rule that owns its boundary; a delta's assets defined as its anchor's with
departures. In each, a condition moved into the statement, a concept got one owner, and a relation
became a map the harness checks.

## Goals / Non-Goals

**Goals:** one normal form per kind of statement; tier as one predicate; section 4 as a projection;
lint claims, migration rows and the delta as maps the harness checks; one owner per concept; every
property enforced, so the next edit cannot undo it.

**Non-Goals:** a cross-standard concept registry and chapters re-derived from each domain's model
(the following change, `one-abstract-standard`); behavioural evals; stable rule IDs (the owner kept
dense numbering).

## Decisions

### 1. A chapter has one template

```
# <the chapter's concept>

Scope: <what it owns>. <the neighbouring concepts, by chapter name>.

<optional organising paragraphs>

<contents list>

## <section> … ### <rule> …

## Decided by tools        (optional, always last)
```

The title carries no family code (`# RS-BUILD — …` goes; the code is the file's, via the vocabulary).
`Scope:` is required. A chapter is named, outside section 6, only in a `Scope:` paragraph.

As built (task 2.2), in `skeleton`, for a standard whose profile is `normalized`:

- The template is a coded chapter's: one whose stem has a family code. The review protocol and
  `renames.md` own no rules, so they are outside it, and naming them is not naming a chapter —
  `revise.NAMED` and section 5's template keep their paths.
- `title_code`: the title's first word is the prefix and a family code of the vocabulary (or
  `CORE`). `no_scope`: the first block after the title is not a paragraph opening `Scope:`.
  `decided_last`: a section follows `## Decided by tools`. A missing contents line stays
  `anatomy.contents_missing`'s.
- `chapter_named`: a code span holding `references/<stem>.md` or `<stem>.md`, the stem a coded
  chapter's, outside `SKILL.md`'s section 6 and a chapter's `Scope:` paragraph, in any block but
  an example and rename history. A path a rule ID follows is a citation's, reported by
  `anatomy.path_citation` and dropped by `fmt`, so one defect is one finding. A chapter named in a
  phrase ("the errors chapter") is not found: no rule tells it from prose, and the scope paragraph
  names its neighbours that way on purpose.
- The how-to-use passage every `SKILL.md` carries named `references/migration.md`; it says "the
  migration chapter" now (`35d5f73`), the one template change of this step.

### 2. A rule has one shape

```
### <ID> [<tier>] <title>

<statement>                 optional; never a restatement of the title
*Relaxed form:* …           present exactly when the tier is [M!]
**Why:** …                  at most three lines
**Check:** …
<examples>                  at most one GOOD and one BAD; polarity-free fragments allowed
```

Elements appear in that order. A rule that needs a second BAD to show a second defect is two rules
or a tool row. `fmt` puts elements in order; `anatomy` fails on a restated title, a duplicate
polarity or a missing element.

As built (task 2.2):

- The chapter layer reads a rule's body as its elements, `Rule.parts`: a label opens its element,
  a fence is an example, and a block with neither carries the element before it on, as `_part`
  reads a second paragraph of a Why — except after an example, where nothing is carried. What no
  element holds is `Element.STRAY`: prose after an example, a heading inside a rule, a label the
  shape has none of (`**Deprecated:**`, `**`[M!]` trigger:**`). `anatomy` and `fmt` read this one
  reading.
- `anatomy`: `element_order` (the first element stated after one that follows it; the relaxed
  form's place beside the Why stays `relaxed_order`'s, so it is not compared twice), `stray`,
  `restated_title` (the statement's first paragraph opens with the title's words, compared
  lowercase without code ticks or emphasis: 84 in rust-style), `polarity` (two fences of one
  verdict), `relaxed_tier` (a relaxed form on a rule that is not `[M!]`). A missing Why or Check
  stays `unstated`, a missing relaxed form `no_relaxed`.
- `fmt` (`doc.normal.in_order`) sorts the elements stably, a stray part moving with the element
  before it, so prose after an example stays beside that example for a person to place.

### 3. A citation is a bare ID

A rule is cited by its ID, unquoted: `RS-ERR-03`, never `` `RS-ERR-03` ``, never
`` `references/errors.md` RS-ERR-03 ``, never "the errors chapter's rule". Section 6 maps prefix to
file, which is the one place a reader needs the path; references stay one level deep. `fmt`
rewrites the other forms; `anatomy` fails on them afterwards.

As built (task 2.3): `doc.normal.bare` unquotes a code span that is exactly a rule ID, then drops
a `references/*.md` span that a word opening with an ID follows, keeping punctuation that opened
its word: `` (`references/naming.md` RS-NAME-25). `` becomes `(RS-NAME-25).`. It reads every block
that cites — paragraphs, list items, quotes, headings and, decided here, table cells, since a
cell's ID is a citation (section 2.2's Rule column, decision 9's); a cell's quoted title is left
as it is, since only a span that is exactly an ID changes. Examples are code and rename history
names IDs that no longer exist; neither is read. A family's span (`` `RS-ERR` (12) ``) is not a
rule and stays, as section 6's counts read it. `anatomy.quoted_citation` and `path_citation` fail
on each form left. "The errors chapter's rule" names no ID, so nothing can rewrite it; it is
prose for the standard's own step.

### 4. A Check that names a pattern runs it

A Check is either judgement in prose or one or more runnable `rg` commands followed by the finding
they report. Prose that names a pattern without running it ("grep for `X`", "search for …") fails:
it escapes self-application while reading like a command. The 52 such Checks in bevy-style and
their kin elsewhere become `rg` commands, each with its `fires` fixture or an `unproven` entry.

As built (task 2.4): `anatomy.prose_grep` fails a Check whose text, every code span taken out,
says `grep` (in any form), `rg`, `ripgrep` or "search for/over/through" — whether or not it also
ships a command, since a normal Check is commands with their findings or judgement, and "the
grep" is neither. Measured: bevy 66, python 5, rust 122, zig 49.

### 5. Section 2 has three subsections, in one order

`2.1 Compiles, and behaves differently` · `2.2 No longer compiles` · `2.3 What <target> gained`.
2.2 is one table (old | new | rule). Each item names the rule or migration row that owns it, so
section 2 is an index into the chapters, not a second home for their content. Toolchain notes that
are neither (ZLS support, `zig reduce`) leave section 2.

As built (task 2.5), in `skeleton`:

- `reality_sections`: the `###` headings of section 2 are exactly `2.1 Compiles, and behaves
  differently`, `2.2 No longer compiles` and `2.3 What <language> <target> gained` (the profile's:
  `What Python 3.15 gained`), and nothing precedes the first.
- `reality_table`: a `2.2` subsection holds one table, headed `| Old | New | Rule |`, and nothing
  else.
- `reality_owner`: an item is a paragraph, a list item or a table row anywhere in section 2, under
  whichever subsection or none, so a section still to be laid out is read too. Its owner is any
  rule ID of this standard the item cites (`ids.cited(item, prefix)`); that the ID names a rule is
  `anatomy.dangling`'s. A migration row is owned by the rule in its Rule column (decision 9), so
  an item naming that rule names the row's owner; when 2.9 keys rows by old spelling, naming the
  old spelling could count as well, and is not read yet. Any other block — an example, a quote —
  is an item naming no owner.

### 6. Tier is one predicate

`[M!]` means mandatory within section 1's scope; its relaxed form says what applies outside that
scope, and nothing else. A condition on the subject belongs in the statement (the RS-API-15
resolution is the model); an exception that holds inside the scope means the rule's domain is
misstated. Consequences checked by `anatomy`:

- no local restatement of the `[M!]` scope (`` `[M!]` applies to ``, `**[M!] trigger:**`,
  `[M!] sharpening`);
- an `[M]` or `[M!]` title commands or prohibits: it does not begin "Prefer", "Consider", "Know",
  "Remember", "Understand", "Treat", "Expect", "Assume" or "Budget";
- a core rule's tier is its chapter rule's (decision 7 makes this structural).

As built (task 2.6), in `anatomy`: `local_scope` fails a chapter rule whose prose, examples left
out, contains `[M!]` at all (30 rules in zig-style); `advice_title` fails an `[M]` or `[M!]` rule
whose title's first word is one of the nine. The core rule's tier is decision 7's, in 2.7.

Exception-shaped relaxed forms (rust-style's 8, bevy-style's 3, zig-style's local triggers) are
rewritten as statements, with the tier each then deserves.

### 7. Section 4 is a projection

Section 4 lists chapter rule IDs, grouped by chapter in section 6's order. `fmt` renders each line
— ID, tier, title — from the chapter, so section 4 cannot drift from it, and a core rule's tier is
its chapter rule's by construction. The `CORE` family goes: `revise` maps each `*-CORE-NN` to the
chapter rule it abbreviated, and the rename table records it. A core rule with no chapter
counterpart (RS-CORE-07's content, zig's suffixed core IDs) either becomes a chapter rule or goes.

As built (task 2.7):

- The source of the ID list is section 4 itself: the IDs its lines name. `doc.normal.listed` reads
  them, from one list whose items are contents lines, flat or under labels; `projection` renders the
  set again — for each chapter section 6 maps, in its order, a label `**<chapter title>**` over a
  contents line (`ID [T] title`, the chapter's) per listed rule, in the chapter's order. So the
  rendering is a function of the set alone and its own fixed point: `listed ∘ projection` is the
  identity on the IDs, and a second `fmt` changes nothing. Section 4 is one `Contents`, read and
  printed by the chapter layer's own reader and printer, and nothing else — no lead paragraph; the
  reading procedure says what section 4 is.
- `skeleton.core_rule` fails each rule section 4 states of its own (`skill.core`, the `CORE`
  family); `skeleton.core_drift` fails a section 4 that is not the projection of the IDs it lists
  — a drifted tier or title, an order or grouping that is not section 6's, an ID no chapter in
  section 6 holds, a block that is not the one list. While a core rule stands, drift is not
  reported: that section 4 is no list to project, and the rule is the one defect.
- `fmt` renders section 4 for a normalised standard, after the normal form. A section 4 holding
  what rendering would drop — a core rule, prose, a label over no line, an ID section 6 does not
  map — is left as it is and reported (`fmt.core_unrendered`): which chapter rule a core rule
  meant is `revise`'s to say, by a person.
- The core-rule citation branches (`anatomy.core_uncited`, `core_not_a_rule`,
  `core_wrong_chapter`, and the `mis_cited` note) read a core rule's `` `references/x.md` ID ``,
  which `fmt` drops; for a normalised standard they are not run, since it has no core rule to
  cite one and `core_rule` reports any left.
- Two shared sentences followed section 4's old form: the reference map's "the N `XX-CORE-*`
  rules live in section 4 above; the other M live here", and the reading procedure's "the chapter
  is the detailed statement and wins". Each is a slot now (`held_here`, `conflict`), filled for a
  normalised standard with what holds of a projection — "All M rules live here; section 4 lists
  by ID those that bind on their own", "When two rules appear to conflict, sections 1 and 3 govern
  how to break the tie" — and with the old text, byte for byte, otherwise. 7.1 keeps the first.
- A chapter's title labels its rules in section 4, so retitling a chapter drifts section 4 until
  `fmt` renders it: `title_code`'s control allows `core_drift` beside it for that reason.

### 8. Lint claims are a bijection

Every lint the shipped configuration sets explicitly has exactly one row, in the chapter that owns
its subject; a row for a lint on by default says why it is listed. A rule whose Check is only a lint
code is that row, and `revise` demotes it. `citations` gains both directions.

As built (task 2.8), in `citations` (`bijection`), for a normalised standard:

- What is owed a row: each lint the shipped configuration sets one by one
  (`Toolchain.configured`, which now gives each lint's level as well) at a level that fails a run —
  a lint set to `allow` forbids nothing, so no row could say what it forbids. A compiler sets
  nothing; ruff's `ALL` and clippy's `pedantic` set nothing one by one.
- A delta owes rows only for the entries its configuration departs in: one its anchor sets
  otherwise, or not at all. An entry equal to the anchor's is the anchor's row — one owner, as a
  delta ships only the assets it departs in (`assets.delta_*`). bevy-style's two departures are
  `allow`, so it owes none, and its seven rows of lints it sets as rust-style does are second homes.
- `unrowed`: an owed lint no row lists. `rowed_twice`: a lint's second row, or a delta's row of a
  lint whose row is the anchor's. Which chapter owns a lint's subject is a reader's judgement; one
  row is the harness's.
- `row_reason`: a row of a lint the configuration does not set one by one — on by default, or
  through a group or `ALL`, which is the configuration's default for its members — states why it is
  listed, in its Forbids cell after what it forbids, as `… — listed because <reason>`. "On by
  default" is read so because a reader learns what the build forbids from the configuration, and a
  row it does not name adds only its reason. A compiler's row is exempt: no configuration sets a
  compiler error, and the row is proved by its probe.
- `only_lint`: a rule whose Check, its label and code spans aside, is tools' names, lint codes and
  joining words (`citations.only_lint`, which `measure` counted as `_only_lints` and now calls).
- Read as normalised: python-style 17 unrowed (its `ty.toml`), 46 rows owing a reason, 2 only-lint
  Checks; rust-style 3 unrowed, 47 rows owing a reason; bevy-style 7 rows its anchor owns and 3
  owing a reason; zig-style nothing. `measure` prints the last two as rows of their own.
- Controls run on the demo, which ships an `assets/ty.toml` read as Python's toolchain reads one,
  setting one lint its errors chapter lists; it ships no `ruff.toml`, so `cite` asks nothing of
  ruff there.

### 9. Migration is a function from old spelling to row

Each migration chapter holds one table keyed uniquely by old spelling:

| Old | `<target>` | Status | Rule |

Status is one of `gone`, `alias`, `changed`, `deprecated`. The migration rules shrink to the ones
that state a behaviour or a procedure; the rest become rows. The grep a reader runs is generated by
`fmt` from the `gone` and `alias` rows, and each toolchain verifies its rows against the pinned
release (Python: the name is absent from, or an alias in, the module; Rust and Bevy: `rg` over the
pinned crate sources; Zig: a compile probe), so a row naming a live API fails.

As built (task 2.9):

- The headers, exactly, with `<target>` the profile's language and series as section 2 names them
  (`skeleton.target`: `Python 3.15`, `Bevy 0.20`): the migration table is
  `| Old | <target> | Status | Rule |` (`chapter.migration_header`), and section 2.2's is the same
  with Status left out, `| Old | <target> | Rule |` (`reality_header`). 2.5's `| Old | New | Rule |`
  is replaced: one convention for both. A row's Old is one code span, the old spelling; its Status
  one of `gone`, `alias`, `changed`, `deprecated` (`chapter.STATUSES`), as a bare word; its Rule one
  bare rule ID of the standard. The target cell is free.
- `skeleton`, for a normalised standard: `migration_table` — the migration chapter holds not
  exactly one top-level table with that header, or another table with an `Old` or `Status` column
  (a second map); `migration_row` — a row whose Old, Status or Rule cannot be read so;
  `migration_twice` — an old spelling in two rows; `migration_command` — the fence after the table
  is not the command its rows generate; `reality_row` — a section 2.2 row whose (Old, target, Rule)
  is no migration row's, so section 2.2 is the function restricted to what no longer compiles (not
  read while the migration table is not one table).
- The command is `doc.normal.command`: an `sh` fence straight after the table, one fixed-string
  pattern a line, in row order, from each `gone` and `alias` row —
  `rg -n -F \` / `  -e '<old>' \` … / `  .` — single-quoted for the shell. `fmt` writes it
  (`with_command`), replacing an `sh` fence that stands there and writing none for a table with
  nothing to seek. It sits outside every rule, so it is no rule's Check and owes no `fires`
  fixture: the table is its specification, and the toolchain verifies the `gone` half. A rule that
  asks the reader to run it says so in judgement ("the command after the migration table"), since
  "grep" in a Check is `prose_grep`.
- Verification: `Toolchain.probe(skill, spelling, out) -> Step | None`, a step that exits 0 while
  the pinned release provides the spelling and 1 once it does not. Python imports the longest
  module the dotted name opens with on the pinned interpreter (`-I`), then reads the rest as
  attributes, a builtin's when no module opens it; Rust searches the pinned library's crates in
  Cargo's registry (`bevy-0.20.1`, `bevy_*-0.20.1`) — or the standard library's source when the
  language is the subject and the toolchain ships it — with `rg` for a public item, an exported
  macro or an indented `fn` of the path's last segment; Zig compiles `_ = std.a.b;` in a
  `comptime` block (`build-obj -fno-emit-bin`, about 40 ms each, cached). A spelling a toolchain
  cannot look up (a call shape, a command line, a builtin) gets no step. The driver
  (`checks.toolchain.gone`) runs each `gone` row's step with `toolchain`, never with `--fast`:
  `toolchain.gone_live` fails a row the release provides, with what the search found;
  `gone_unprobed` notes a row nothing could look up; a timeout or a probe that could not run is the
  driver's `timeout`/`failed`.
- `gone_live` is exempt from the controls as every branch of `toolchain` is (`COMPILES`): a control
  would cost a toolchain run, and `--fast` runs none on a slow check. Each verifier is exercised by
  `tests/test_gone.py` (marked `toolchain`): live and gone spellings on the pinned interpreter, in
  the registry's Bevy 0.20.1 source and on Zig 0.17, and the driver over the demo's migration table
  with a live row, a gone row and a row no probe reads.

### 10. The delta is a typed map

bevy-style's departures are one table: rust-style rule | relation (`overrides`, `tightens`,
`extends`) | bevy-style rule | tier before → after | reason. A departing bevy-style rule opens
"Departs from RS-x." A bevy-style rule that restates a rust-style rule becomes a citation. A
silent tier change against the anchor fails; the `[M!]` predicate is rust-style's, not redefined.
The asset rule already landed is the same map for files.

As built (task 2.10), for a delta whose profile is `normalized`:

- The table's header, exactly: `| <anchor> rule | Relation | <delta> rule | Tier | Reason |`, the two
  standards by name (`| rust-style rule | Relation | bevy-style rule | Tier | Reason |`;
  `chapter.departures_header`). Each row: the anchor rule's bare ID, one of `overrides`,
  `tightens`, `extends`, the delta rule's bare ID, `[T] → [T]` (before, an arrow, after), and the
  reason. It may stand anywhere in `SKILL.md`; bevy's sits in section 3 today.
- `crossref` reads it in place of the override table: `delta_no_table` when there is none (the
  branch the override table already had), `override_target` for a delta cell that names no rule
  here (likewise); new: `relation` (not one of the three), `departure_tier` (the cell does not
  read, or is not the anchor rule's tier then the delta rule's), `departs` (the pairs the table
  states and the rules whose statement opens `Departs from <ID>.` are not one set — each side's
  extra pair reported), `redefines` (the delta's `strict_scope`, or the words its section 1 gives
  `[M!]` in its own region, differ from the anchor's). An anchor ID that names no rule is
  `crossref.citation`'s, as any citation into the anchor is.
- Restatement: the harness knows a delta rule says what an anchor rule says only where the
  profile's `Mirror` pairs it, since word overlap decides nothing (decision 11; `mirror.unheld`
  stays a note). For a normalised delta every held pair fails, `mirror.restated`, in the check
  that reads the pairs, naming the tier change when there is one: a restatement becomes a
  citation, or a departure its table states. So a silent tier change has nowhere to stand: a rule
  related to an anchor rule is a citation (no tier), a departure (its row states both tiers, and
  `departure_tier` holds them to the rules), or a declared restatement (`restated`).
- C1's note: an override row's cells open with an ID quoted or bare (`chapter._opening_id`), so
  `fmt` setting a delta's cells bare does not empty its table; on today's tree the rows read are
  the same.
- `crossref.apparatus` checks the IDs `src/`, `tests/` and the README cite against the standards
  the harness ships (`PROFILES`), not every standard in the tree: a demo standard in a control's
  tree made the tests' deliberately wrong `DS-…` IDs read as citations.
- Controls run on `checks.demo.DELTA`: a delta on the demo, built from the demo's files under its
  own prefix, departing from DS-ERR-01 (`tightens`, `[M!] → [M]`), its `[M!]` the demo's, its
  `ty.toml` the demo's lint (the demo's row) and one of its own (its row) — so it holds 2.8's
  delta rule too. `tests/test_delta_map.py` holds it to every property.

### 11. One concept, one owner

The duplicate pairs and multiple homes the review measured are merged with `revise`. `anatomy`'s
near-duplicate note stays a note: overlap of words decides nothing on its own.

### 12. Examples obey what ships

Python examples are linted with the shipped `ruff.toml` minus a named allowlist of rules about
project shape (`D100`, `D103`, `INP001`, `N999`, `S101`, `PLR2004`), each with its reason. Rust
examples already compile under the shipped lint table.

As built (task 2.11):

- `PythonSnippet.allowlist`, code → reason, holds the six codes with their reasons. For a
  normalised standard the `ruff` step is `ruff check --no-cache --config <the shipped ruff.toml>
  --ignore=<the allowlist> --output-format=concise <files>` (`_shipped`, `ruff_args(shipped)`); the
  narrower `select`/`ignore` stays for the others, so their runs are unchanged. The configuration
  is the asset itself, resolved through `Skill.asset`, so nothing else can differ between what ships
  and what the examples are linted with: the divergence the spec's scenario names is impossible by
  construction, but for the allowlist.
- Only advice is linted so: an evidence block (`— BAD`, or quoted from someone else's source) shows
  the shape a rule forbids, which the shipped configuration forbids as well, so `ruff` is given the
  advice units' files. `ty` and the run still take every block.
- `Toolchain.excused(skill)` is what a skill's examples are excused from (Python's allowlist; Rust
  and Zig nothing), and `citations.allow_reason` fails an entry with no reason, for a normalised
  standard; its control reads the demo with an allowlist entry whose reason is empty.
- Measured: python-style's 51 verified blocks, read as normalised, give 23 findings under the
  shipped configuration less the allowlist — `D101` 10, `D102` 7, `D107` 4, `D105` 1, `S311` 1 —
  for its step to resolve: a docstring each, or an allowlist entry with its reason.

### 13. The frontmatter and SKILL.md are bounded

The description is one shared template: the use case first, the artifacts that trigger it, the
target version; no rule count, no source list; at most 500 characters. SKILL.md is under 500 lines.
`prose` fails on time-sensitive and build-provenance phrasing ("currently", "not yet", "as of",
"compiled against", "measured", a date outside a migration table).

As built (task 2.12), for a normalised standard:

- The template is `src/agent_skill/shared/description.md`, beside the other shared passages:

  ```text
  Use when …. Applies to …. Targets {language} {target}.
  ```

  The use case first, then the artifacts that trigger it, then the target as the profile names it
  (`Targets Python 3.15.`); each `…` is the standard's own words and says something.
  `shared.description` fills the slots and reads the rest as a pattern (fixed words as written, a
  run of spaces as one), matched against the folded description: a frontmatter field is one line
  of text, not blocks to align, so it is not a `Passage`.
- `frontmatter`: `template` (the description does not fill the template), `counted` (it counts
  rules, `\d+[- ]rules?`), `bounded` (over 500 characters). The count-against-rules property
  (`rule_count`) and the 1024 limit (`length`) are not run for a normalised standard: no count is
  stated, and 500 is the bound. A list of sources is not detected — nothing tells "PEP 8, PEP 257"
  from an artifact list — so the template's shape is the guard, and a person's reading the rest.
- `skeleton.skill_md_lines`: `SKILL.md` is under 500 lines (`SKILL_MD_BOUND`); zig-style's 560 is
  the one over.
- `prose.dated`: "currently", "not yet", "as of", "compiled against", "measured" (any case), or a
  date (`2026-09-01`, `September 2026`), in any block outside an example and rename history, code
  spans taken out; a date in the migration table — the one headed as decision 9 says — is the
  table's key, and stands. Read as normalised: bevy 6, python 7, rust 14, zig 27, as `measure`'s
  last row prints them.
- `frontmatter.described` read a description without its last line (task 2.10 fixed it), so the
  lengths the baseline recorded were short by that line.
- Read as normalised, each of the four fails `template`, `counted` and `bounded` today.

### 14. Rolled out one standard at a time

Each property lands as a check that applies to the standards whose profile declares
`normalized = True`. A standard is normalised in one step and flips its flag; when all four have,
the field and every condition on it are deleted, so it is scaffolding with a stated end. Order:
python-style (the smallest), rust-style, bevy-style (it depends on rust-style's final IDs), zig-style
(the largest section 2 and the most local tiers).

As built (tasks 2.1–2.6):

- `Profile.normalized: bool = False`; `anatomy` and `skeleton` each call one `_normal_form` when it
  is set, and nowhere else. All four stay false, so the tree's findings are unchanged:
  `check --fast --verbose` is byte-identical before and after.
- `fmt` prints the normal form (`doc.normal.normal`: citations bare, then a chapter's rules in
  order) for a normalised standard only. Not tree-wide: the other standards cite a core rule's
  chapter by its path, which `anatomy._core_citations` reads until section 4 is a projection, and
  zig-style's 153 stray blocks and 21 doubled verdicts are a person's to place. So `fmt` leaves the
  shipped tree as it is, and no re-print commit was needed. `normal` is a map on trees before
  printing, so `print ∘ parse` keeps its laws; on every shipped file it is idempotent, reads back
  as printed and keeps every fence body (`tests/test_normal_form.py`).
- Controls: a small standard in normal form, `checks.demo` (Demo 1.2: two chapters of rules, the
  review protocol, section 2 laid out as decision 5 says), written into the throwaway tree and
  read with a profile of its own through `Control.profiles`, which the runner reads a skill of
  the copy with in place of `PROFILES`'. Each of the 17 controls builds it and makes one edit, and
  fires its branch alone. Flipping a shipped profile was rejected: python-style read as normalised
  already fails seven of the seventeen branches, so no control on it could be branch-precise. A
  test holds the demo clean under `anatomy`, `skeleton`, `layout` and `shared-text`, so no control
  can pass on a defect it did not inject. FAIL branches 203 → 220, controls 181 → 198.
- `tests/structure_fixture.py`'s demo stays the un-normalised one the older tests edit; the two
  converge when 7.1 deletes the gate.

What this leaves for the standards' own steps:

- 2.7 lands before python-style is normalised: `fmt` drops a core rule's chapter path, which
  `core_uncited` and `core_wrong_chapter` read.
- 2.10 lands before bevy-style is: its override table's cells open `` `RS-…` ``, which
  `crossref` reads as a quoted ID only, and `fmt` sets them bare.
- When a standard is normalised, the older controls that inject into it may reach a normal-form
  branch beside their own — `relaxed_label`'s `**Relaxed form:**` is a label the shape has none
  of, so `stray` fires too — and move to the demo or say why in `also`. Most of those controls
  inject into python-style, the first to be normalised.
- Section 2.2's table is headed Old, New, Rule, and decision 9's migration table Old, the target,
  Status, Rule; 2.9 may want one convention for both. (2.9: one — section 2.2 is the migration
  header without Status.)

As built (task 3.1), python-style normalised; what it decided for the standards after it:

- Core rules (decision 7): `revise` takes a `*-CORE-NN` in a plan, as a `merge` into the chapter
  rule it abbreviated or a `remove` with its reason, never a row (a row is a chapter's). Its item in
  section 4 becomes that rule's contents line, written with the pre-revision ID so the one rewrite
  respells it; every citation of the core ID follows the merge; and the rename table states the
  core family's range and a row per core rule — joining the table the revision already started,
  whose ranges sentence is restated, or stopping when that sentence is not the one `revise` writes.
  Section 4 then lists the union of the chapter rules the core rules cited, less any about to be a
  row; `fmt` renders it. All 26 of python-style's merged; none said what no chapter rule says.
- Moving a rule to another chapter (decision 11): `revise` has no move, so a rule moves as a copy
  under its new ID and a merge of the original into the copy; renames.md records where it went.
  Python's module rules moved that way into a new `modules` chapter, the vocabulary's.
- Chapter titles (decision 1): `<concept>: <what it covers>`, the concept the file's (`Concurrency`,
  not `Free Threading`; `Build`, not `Packaging`). A title labels its rules in section 4, so a long
  one costs every reader of section 4.
- Lint rows (decision 8): a row of a lint `ALL` sets is kept when it says what the configuration
  does not — the option that widens or decides it (`convention = "google"` for the `D` rows,
  `max-doc-length` for `W505`, `raises-require-match-for` for `PT011`), or the rule a demotion
  replaced, which renames.md resolves to it — and goes otherwise: a sibling of a kept row, or a row
  a rule's Check already names, whose Check then cites the code itself. A rule whose Check reads as
  only a lint is demoted only when the lint decides its whole statement: `UP040` decides
  PS-TYPE-10's `TypeAlias` half and not its bare-assignment half, so its Check gained the review
  half it always had, and it stays a rule.
- Migration (decision 9): Old is the spelling a toolchain can look up, so Python's are fully
  qualified (`glob.glob0`, `wave.Wave_read.getmark`), and the generated `rg -F` finds the qualified
  form only; a call shape a release rejects (`RLock(*args)`, a field-less `TypedDict`) is `changed`,
  since no fixed string finds it, and its owning rule's Check does; one row may stand for a family
  of spellings its rule lists (`<module>.__version__`). Python's probe reads a C API name as absent
  — it is no Python object — so a C row passes vacuously, and a live one would too; a command line
  (`python -m http.server --cgi`) is unprobed, a note. Section 2.2 is the table restricted to what
  raises: the Python `gone` rows and the rejected shapes.
- Tier (decision 6): a relaxed form states what is acceptable outside section 1's scope and nothing
  conditional on the subject; where one stated the complement of its own rule's domain (PS-CONC-16:
  a pure, cheap memo has no expensive miss), it said nothing, and was rewritten.
- Controls (decision 14's last item): the older controls that inject into python-style were each
  retargeted to a rule or chapter the normal form leaves alone, or given an `also` where the normal
  form reads the same defect a second way by construction (`relaxed_label`'s unknown label is
  `stray`; a path-qualified citation is `path_citation`). The core-citation controls and the map's
  "other N live here" count moved to rust-style, which still states core rules.

As built (task 4.1), rust-style normalised; what it decided beyond task 3.1:

- Core rules (decision 7): a core rule merges into the chapter rule that states its concept, which
  need not be one it cited — RS-CORE-09, "make illegal states unrepresentable", cited three of its
  instances and merged into RS-API-27, which states it; section 4 lists the instances too. A core
  rule's sentence that is a lint (RS-CORE-07's `&Vec<T>`, `ptr_arg`) is that lint's row already.
  The five core/chapter tier mismatches went by projection; each chapter tier was then read on its
  own (RS-UNSAFE-30 became `[M]` for its own reasons, below).
- One concept, one owner (decision 11): a pair is one concept when one rule is an instance of the
  other (RS-ERR-20's error taxonomy of RS-DOC-03's crate-wide facts, RS-CLI-18's stdout of
  RS-PERF-19's buffering) or the two halves of one choice (RS-MOD-10/11's `pub(super)` and
  `pub(crate)`); the merged rule takes the higher tier with its condition in the statement
  (RS-ERR-26 into RS-ERR-37, RS-API-39 into RS-API-28, both `[M]`). Two rules that share an example
  but answer different questions are not merged: the overlap goes, and each cites the other's owner
  (RS-FUNC-16 when to return an iterator, RS-TRAIT-15 how to spell it; RS-ERR-35 the exit code,
  RS-CLI-16 the usage message). A rule the compiler always enforces is removed with that reason
  (RS-TRAIT-29, E0119): Rust has no compiler rows.
- Migration (decision 9): a Rust row's Old is the spelling the code names, so the generated `rg -F`
  finds it and nothing else — a crate's API path (`once_cell::sync::Lazy`, `num_cpus::get`), a macro
  (`lazy_static!`), an attribute (`#[no_mangle]`), an edition-changed construct (`if let`, `gen`) —
  never a crate name, which finds its replacement and prose too. `alias` is a crate's API the
  standard library replaced: it still builds and is rewritten wherever it stands, python's alias
  read operationally. A crate still right for part of its use (`async-trait` behind a `dyn`) has no
  row, as a discouraged name has none. An idiom a newer feature superseded (`let ... else` for a
  `match`, `#[expect]` for `#[allow]`) is no spelling; its rule owns it, and its date joins the
  table of when an API arrived, which maps an API to a release, not an old spelling to a new one.
  A change no spelling keys (Cargo's incremental default in CI) stays in RS-MIG-03's table, keyed by
  release. Edition rows with no topical rule are RS-BUILD-01's, the edition's own rule.
- `gone` verification for Rust: a path is searched for in the standard library's source, which the
  pinned toolchain ships only with `rust-src` (task 4.1 added it to the 1.99 toolchain here with
  `rustup component add rust-src --toolchain 1.99`); without it a path row is `gone_unprobed`, a
  note, never a pass. An attribute is compiled on an exported function under edition 2021 and then
  2024 (`lang.rust._compiled`): 0 while 2024 accepts it, 1 when only 2021 does, 2 when neither does,
  so a malformed probe is the driver's `failed` rather than a verified row.
- Tier (decision 6): a relaxed form that relaxed frequency (RS-CONC-41, RS-UNSAFE-30) states the
  floor every crate meets — run before every release, on every push where CI's time allows — and
  the rule is `[M]`; a rule whose relaxed form, once its condition moved into the statement, has
  nothing left to relax is `[M]` too (RS-CONC-09, -33, -40, RS-CLI-27, RS-PERF-31, RS-TEST-23,
  whose untrusted input section 1 puts inside the scope by definition). A relaxed form that restates
  the scope ("for an internal binary") loses the restatement.
- Checks (decision 4): a prose "grep" became an `rg` command where the pattern is the defect, each
  with a `fires` fixture and none unproven, and judgement where the code around the hit decides; a
  `not_decisive` entry whose span no longer runs goes. The anchor's commands run over the delta's
  examples too (`crossref`), which found RS-CONC-27's `static mut ` inside bevy-style's
  `&'static mut`. RS-API-04's command found RS-NAME-19's and RS-FUNC-10's examples returning
  `std::slice::Iter` from a public `iter()`, as an `IntoIterator` impl must name it: RS-API-04's
  Check is judgement naming both places, and the tension is the iterator examples' to resolve.
- Controls (decision 14's last item): the core-citation controls, `map_here`, and the
  `frontmatter` branches a normalised standard does not run (`length`, `rule_count`) inject into
  zig-style, the one standard still stating core rules; `no_cargo_toml` says in `also` why every
  row owes a reason once no lint is set one by one.

## Risks / Trade-offs

- **CORE IDs disappear** → every citation of one resolves through `renames.md`; `revise` checks
  that each still names the same rule's title.
- **Bulk demotions and merges change rule counts** → the frontmatter no longer states a count
  (decision 13), so nothing else drifts with them.
- **Migration verification needs each toolchain** → it runs with `toolchain`, not `--fast`.

## Migration Plan

1. Land the checks and `fmt` support, gated by `normalized`; carry `one-parse-one-print`'s two open
   items (profile maps keyed by `RuleId`, hit lists through the location printer).
2. Normalise python-style; flip it. 3. rust-style. 4. bevy-style. 5. zig-style.
6. Delete the gate; re-measure; full check; archive.

Step 1 as built, besides the checks above:

- The baseline is `agent-skill measure` (task 1.1): a row per count and a column per standard,
  read from the chapter layer, and for each property a gated check decides, that check's findings
  on the standard read as normalised — so the baseline is what the checks will report, not a
  second reading of the property. 7.2 prints it again. On the way the toolchain gained
  `configured`, each lint a shipped configuration sets one by one as a row names it (Rust's
  `[workspace.lints]` without its groups, ty's rules, nothing for ruff's `ALL` or for zig), which
  2.8's bijection reads.
- The carried items (task 1.2): a profile spells each rule as a reader cites it, and the record
  holds a `RuleId`, read once by `keyed` and `rules` — `exempt`, `not_decisive`, `fires`,
  `unproven`, `unless_own`, and `Mirror.pairs`, which had the same shape. A hit list prints each
  hit with `Location`'s printer (`Corpus.origin` returns one), so a hit reads
  `bevy-style/references/events.md:110 [BV-EVENT-01]` as every finding does, and one under no
  rule no longer says `[?]`. Findings identical; only the hit lines re-render.
