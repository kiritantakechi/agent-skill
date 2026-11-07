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
2.1 and 2.2 are the migration table's `changed` and `gone` rows the target made, each one table
(old | target | rule) rendered from it (decision 9): the statuses and the two subsections are one
partition. 2.3 is an index of rules, since a gain is no old spelling. Each item names the rule or
migration row that owns it, so section 2 is an index into the chapters, not a second home for their
content. Toolchain notes that are neither (ZLS support, `zig reduce`) leave section 2.

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

| Old | `<target>` | Status | Since | Rule |

Status is one of `gone`, `alias`, `changed`, `deprecated`, and says what the target does with the old
spelling: `gone`, it rejects it — a compile, import or attribute error; `changed`, it accepts it and
it means something else; `alias` and `deprecated`, it accepts it and it means what it did. Since is
the release from which the row's status holds — for a language whose changes land in editions as well as releases (Rust), the
edition when the edition made the change — in one form per standard, read by `ids.Version`. The
migration rules shrink to the ones that state a behaviour or a procedure; the rest become rows. The
grep a reader runs is generated by `fmt` from the `gone` and `alias` rows, and each toolchain
verifies its rows against the pinned release (Python: the name is absent from, or an alias in, the
module; Rust and Bevy: `rg` over the pinned crate sources; Zig: a compile probe), so a row naming a
live API fails.

Sections 2.1 and 2.2 are this function restricted to the `changed` and to the `gone` rows whose
Since is the target's, each `| Old | <target> | Rule |`, then one line saying where that status's
other rows are and how a reader finds them. Each is a projection of the migration table as section
4 is of the chapters: `fmt` renders it, and `skeleton` fails one that differs from its rendering. No
person sizes either, and an `alias` or `deprecated` row, which still compiles and means what it
did, is in neither: it is the table's, and an `alias` is the command's.

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

As built (section 2.2 as a projection, after task 5.1). Decision 9 said section 2.2 was "a
restriction of the same function" and not which one, and the three standards normalised by then
chose three — python-style 27 rows (what raises, its C API left out), rust-style 8 (edition changes
that fail), bevy-style 155 of 180 (every `gone` row and the rejected `changed` ones), its `SKILL.md`
415 lines — each copied by hand. The restriction is now a predicate on a column of the table:

- The table is `| Old | <target> | Status | Since | Rule |` (`chapter.migration_header`); a row is
  `Migration(old, new, status, since, rule)`, and `Migration.landed` reads its Since. A Since is a
  `Version` in one form per standard: a release as its series (`3.15`, `0.20`, `1.80`), or, in a
  standard whose profile names an edition (`Profile.edition`, rust-style's `2024`), that edition.
  `ids.Version` reads an edition as a version of one number, a four-digit year: `Version.parse`
  takes `2024` and prints it back, `edition` says which it is, `search` never finds one among other
  words and `released` never takes one for a release; `3` is still no version. The round-trip test
  draws editions among the versions it prints and parses.
- What Since means: the first release in which the old spelling does what its Status says — for
  `gone` the first release without it, which for a name deprecated first is a release after the
  one that renamed it; for `alias` the release that stabilised or added the replacement; for
  `changed` and `deprecated` the release that changed or deprecated it. So the rows whose Since is
  the target are exactly what moving from the release before it changes, and code written for an
  older release reads the rows since that one.
- The target is `Profile.since`: the series the pin belongs to, and the edition where the profile
  names one. Python `{3.15}`; Bevy `{0.20}`; Zig `{0.17}` (its table not yet keyed; the harness reads
  one when 6.1 writes it). Rust `{1.99, 2024}`: rust-style's examples compile under release 1.99 and
  edition 2024 (`verified_as`), and both are the target. An edition change is keyed by the edition,
  not the release that shipped it (1.85), because that is where a crate meets it — when it moves its
  `edition` — and it is where Rust breaks code at all; 1.99's own rows are what 1.99 stabilised or
  deprecated (`fs::set_times`, `fetch_update`, the module constants).
- `skeleton.migration_row` reads Since as it reads the other cells: a row fails whose Since is no
  release (or edition, where the profile names one), is a release but not its series (`3.15.0`), or
  is after the target's (`3.16`): a change the target has not reached is no row.
- The rendering is `doc.normal.reality(rows, since, header, family)`: a table of each row whose
  Since is one of the target's — Old, target cell, Rule, in the table's order — and none when no
  row is, then `doc.normal.older(family)`, the one generated line: "What an earlier release changed
  is in the migration table, `PS-MIG` in section 6, each row with its Since; the `rg` command after
  that table finds every `gone` and `alias` spelling, whatever its release." It names the migration
  family, not the chapter's path, since a chapter is named only in section 6 and a `Scope:`
  (`chapter_named`). `skeleton.reality_rendered` computes it from the one migration table;
  `fmt._gone_rendered` writes it under the `2.2` heading of a normalised standard, after section 4's
  projection.
- `skeleton.reality_drift` fails a section 2.2 that is not its rendering — a row the target did not
  make, a row of the target left out, another order or another closing line — and is not read while
  the migration table is not one table, as `core_drift` is not while a core rule stands. It
  replaces `reality_table` (task 2.5) and `reality_row` (2.9): each was a property the rendering has
  by construction. `reality_owner` reads 2.1 and 2.3 and no longer 2.2, which holds nothing a person
  wrote: each row names its rule in its Rule column, and the line is the rendering's. FAIL branches
  243 → 242, controls 220 → 219. Section 2.2's title stays decision 5's.
- Control: `reality_drift` on the demo, its section 2.2 kept by hand with the migration table's 1.1
  alias row beside the 1.2 one. The demo's table now has a row of each release (`old_name`, `gone`,
  1.2; `old_flag`, `alias`, 1.1), so `migration_row` and `migration_twice` edit the 1.1 row and leave
  section 2.2 as rendered; `tests/test_normal_form.py` holds that `fmt` adds a row given the target's
  Since, drops one moved off it, writes the line alone when no row is the target's, and that each
  wrong Since is `migration_row`.
- Filling Since: each row's history — the per-release tables and headings the chapters had before
  tasks 3.1, 4.1 and 5.1 — checked against what each release ships. Python: What's New 3.14 and
  3.15 (and 3.13, 3.11 for older deprecations), section by section: 51 rows 3.15 (every `gone` row,
  the C API's among them), 9 3.14, 3 3.13, 1 3.11. Rust: the edition guide for the edition rows; the
  pinned standard library's `#[stable(since)]` and `#[deprecated(since)]` (`rust-src`) for the rest,
  which agree with the chapter's table of when an API arrived: 11 rows 2024; 3 1.99; 1 each 1.98,
  1.96, 1.95, 1.82, 1.59, 1.57; 3 each 1.89, 1.87, 1.70; 2 each 1.80, 1.66. Bevy: the old chapter's
  per-release tables, the migration guides 0.15 to 0.20, and each name looked up in every release's
  crates (0.15.0 to 0.19.0 from crates.io beside the registry's 0.20.1, by the probe's own
  definition pattern) or manifest features: 13 rows 0.15, 23 0.16, 15 0.17, 43 0.18, 34 0.19, 52
  0.20. Where the history filed a row under the release that renamed or deprecated it and a later
  one removed it, the removal is its Since: the 0.15 bundles are 0.16, the 0.16 hierarchy and query
  methods that 0.16 deprecated are 0.17, the 0.17 event, observer-event and system-set names that
  0.17 kept as deprecated aliases are 0.18, the non-send and hierarchy-command names 0.18 and 0.19
  deprecated are 0.20. Where it filed a row under the wrong release outright, the guides correct it:
  `JustifyText` 0.17, `TextLayout::new_with_*`, `ComputedNode::stack_index` and `Core*` 0.19,
  `push_children` and `App::observe` 0.15, `weak_handle!` 0.17.
- After: section 2.2 rows / `SKILL.md` lines — python-style 51 / 312 (27 / 284 before), rust-style
  14 / 277 (8 / 267), bevy-style 52 / 316 (155 / 415). Each chapter's description of its table
  says what Since is and that section 2.2 lists the target's rows.
- Open: the restriction is by Since alone, as decided, so section 2.2, titled "No longer compiles",
  lists every row the target made whatever its status — python-style's 51 are 34 `gone`, 12
  `changed` (7 rejected shapes, 5 that compile and differ), 1 `alias` and 4 `deprecated`;
  rust-style's 14 are 1 `gone`, 10 `changed`, 1 `alias`, 2 `deprecated`; bevy-style's 52 are 32
  `gone`, 16 `changed`, 4 `deprecated`. Whether 2.2 restricts on Status as well (`gone` alone is a
  predicate the table decides; "rejected" `changed` is not), or is retitled, is the owner's.
- Uncertain: `obj.n += 1` (python-style) is 3.13, the first free-threaded build, where the old
  chapter filed it under 3.15; `typing.Text` is 3.11, its deprecation, though it has been an alias
  of `str` since `typing` began; `memoffset::offset_of` is 1.82, when `offset_of!` took nested
  fields as the row's target cell says, not 1.77; bevy-style's `CoreButton` names a family no
  release spelled so (0.17's widget was `Button`; 0.19 dropped `Core` from the rest), and
  `"experimental_ui_widgets"` a feature 0.17 and 0.18 spelled `experimental_bevy_ui_widgets`.

As built (statuses as section 2's partition, after task 5.1). This resolves the open question of
the note above: section 2.2 restricted by Since alone listed every row the target made under "No
longer compiles", and `changed` named two things — a spelling the target rejects in a shape no fixed
string finds (Rust 2024's `extern "C" { … }`, Bevy's `TextFont { line_height }`) and one it accepts
and reads otherwise (RPIT capture). Neither a Status filter on 2.2 alone nor a retitle makes the
statuses mean the sections; both projections do.

- The statuses are defined by what the target does (`chapter.STATUSES`): `gone`, it rejects the old
  spelling — a compile, import or attribute error, or in Python a call shape that raises `TypeError`
  or `ValueError` where it was accepted; `changed`, it accepts it and it means something else;
  `alias` and `deprecated`, it accepts it and it means what it did. `chapter.PROJECTED` is
  `("changed", "gone")`, the status of 2.1 and of 2.2 in decision 5's order; 2.3 projects none.
- Rendering: `doc.normal.reality(rows, since, header, family, status)` renders the rows of `status`
  whose Since is the target's (`landed`), then `older(family, status)`, one line a status: "A
  `changed` row of an earlier release is in the migration table, `PS-MIG` in section 6, with its
  Since; its owning rule's Check finds it." and "A `gone` row … with its Since; the `rg` command
  after that table finds every `gone` and `alias` spelling but a shape, whatever its release."
  `skeleton.reality_rendered` returns both by title; `fmt._reality_rendered` writes both.
- `skeleton`: `changed_drift` fails a 2.1 that is not its rendering, `gone_drift` (was
  `reality_drift`) a 2.2; each says which row it lists or leaves out. `reality_owner` reads 2.3 and
  anything outside the subsections: 2.1 and 2.2 hold nothing a person writes. FAIL branches 242 →
  243, controls 219 → 220. The demo's table has a `changed` row of 1.2 (`open()`, DS-ERR-01), its
  2.1 is rendered, and `reality_owner`'s control takes the owner from the 2.3 item; `changed_drift`'s
  control keeps 2.1 by hand with the `gone` row of 1.2 beside the `changed` one, `gone_drift`'s keeps
  2.2 by hand with the 1.1 `alias` row. `tests/test_normal_form.py` holds that a `changed` row of 1.2
  is rendered in 2.1 and a `gone` one in 2.2, that an `alias` or `deprecated` row of 1.2 is in
  neither, that each subsection over no row is its line alone, and that a shape is no pattern.
- A shape: once a rejected shape is `gone`, the command would search for it as a fixed string. An
  old spelling with `…` in it is a shape, code left out where the `…` stands (`chapter.ELIDED`,
  `Migration.shape`); `sought` skips it, and its owning rule's Check finds it. Each chapter's
  description of its table says so. The command is `rg -n -F -w`: a fixed string, matched as a whole
  word, so `gen` (edition 2024's keyword, now `gone`) is not `generic` and `Style` not `TextStyle`.
- Verification of the new `gone` rows: `Toolchain.probe` takes the row's Since. Rust compiles a row
  the edition made under 2021 and then 2024 — an attribute on an exported function, as before; an
  item with its body elided (`extern "C" { … }`) with the body empty; a name as a function's
  (`gen`) — and has no source for a call (`env::set_var`), which is noted unprobed. A method of a
  type, `App::observe`, is searched for in the files that implement the type, so a live
  `EntityCommands::observe` no longer keeps a removed `App::observe` alive: that is what made
  `App::observe`, `NextState::set_if_neq` and `.get_single()` `changed` rather than `gone`.
  `tests/test_gone.py` holds both. The rows no probe reads were checked by hand against the pin:
  Python's seven call shapes on 3.15.2 (each raises), Rust's `env` rows under both editions (E0133
  in 2024), and Bevy's shapes compiled against 0.20.1 in a scratch crate beside the verify crate's
  dependencies (each an error).
- Reclassified: python-style 7 (the PS-MIG-04 call shapes, `changed` → `gone`, their Old written
  with `…`), and 2 rows added from section 2.1's UTF-8 item (`sys.getfilesystemencoding`,
  `sys.stdout`, `changed`, PS-OUT-02). rust-style 6: `env::remove_var`, `env::set_var`,
  `extern "C" { … }` and `gen` `changed` → `gone`; `static mut` and `unsafe fn` `changed` →
  `deprecated` (each still compiles and means what it did; the edition denies a reference to a
  `static mut` and warns on an unsafe operation in an `unsafe fn` body); and 7 rows RS-MIG-03 kept in
  a table of its own became `changed` rows it owns (`RangeInclusive` 1.99, `#[derive(PartialOrd,
  Ord)]`, `TcpStream::shutdown`, `BTreeMap::append`, `#[non_exhaustive]`, `panic!`, `extern "C"
  fn`), its table keeping the five changes no spelling keys. bevy-style 23 `changed` → `gone`: the
  struct-literal and generic shapes (`TextFont { line_height: … }`, `Camera { hdr: … }`,
  `On<Add, …>`, `Trigger<…>`, `MeshTag(…)` …), the names 0.20 does not have (`Condition`,
  `bevy_pbr::mesh_view_bindings`), and the methods (`App::observe`, `App::add_event`,
  `Query::get_single`, `NextState::set_if_neq`); one row added from section 2.1 (`Aabb`, `changed`
  0.18, BV-VIEW-16).
- Section 2.1's hand-written items: each that was a construct's behaviour change is its row — every
  one already was but python's UTF-8 item's other two effects and bevy's `Aabb`; each general fact
  (Rust's overflow, `as`, a dropped future; python's thread-safety guarantees page) was already
  stated by the rule it cited (RS-ERR-28, RS-PERF-30, RS-CONC-33, PS-CONC-05), and is now only
  there. Rust's tail-expression temporary scope has no spelling to key it and stays RS-BUILD-01's.
- After, section 2.1 rows / 2.2 rows / `SKILL.md` lines: python-style 7 / 41 / 298 (2.2 51 and 312
  lines before), rust-style 5 / 5 / 265 (14, 277), bevy-style 10 / 38 / 292 (52, 316). A row of the
  target that still means what it did is in neither: python's `cProfile` and four `deprecated`,
  rust's three of 1.99 and two of 2024, bevy's four of 0.20.
- The two bevy-style rows the note above doubted are corrected: no release spelled `CoreButton` —
  0.19 dropped `Core` from `CoreScrollbarThumb`, `CoreScrollbarDragState` and `CoreSliderDragState`,
  the only `Core*` names 0.17 and 0.18 shipped, so the row is `CoreScrollbarThumb`; and 0.17's and
  0.18's feature was `"experimental_bevy_ui_widgets"`, which 0.19 renamed `"bevy_ui_widgets"` and
  0.20.1's manifest does not have.
- zig-style is not normalised: its table, once keyed (task 6.1), renders through the same
  functions, and its probe takes the Since it ignores.
- Uncertain: `static mut` as `deprecated` (the declaration compiles and means what it did; most uses
  take a reference, which the edition denies); Python's call shapes as `gone` rather than `changed`
  (a `TypeError` where a call was accepted, as an `AttributeError` is where a name was).

As built (after task 7.1): 2.2's line said the command "finds every `gone` and `alias` spelling but
a shape", which a row whose Old is a member (`Timer::finished`, `pathlib.PurePath.is_reserved`,
`std.Build.LazyPath.getPath`) belies: code calls it on a value, which names no type a fixed string
sees, and a bare `.finished(` would hit live members of the name. The line now says the command finds
each spelling the code writes out, and the type checker each `gone` member reached through a value
(`ty`'s `unresolved-attribute`, verified; rustc and zig on code they analyse), and PS-MIG-01, -03,
BV-MIG-01, ZS-MIG-02 and their chapters' leads say the same.

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
  own: RS-FUNC-06 is `[S]`, as RS-FUNC-03 to -05 and RS-CORE-17 were, since its Check's "then it
  is a pipeline" gave the loop RS-FUNC-03 calls `[S]` a second, `[M]` reading; RS-UNSAFE-30 became
  `[M]` for its own reasons, below.
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

As built (task 5.1), bevy-style normalised; what a delta decided beyond tasks 3.1 and 4.1:

- The delta map (decision 10): a departure is from the anchor rule whose *statement* the delta
  contradicts, not its title — RS-BUILD-21 opens "Use caret requirements" for every crate, so a
  game binary's exact pin departs from it (the old table's note that the two "never meet" read the
  title's library clause alone). The departing rule is the one whose statement says the different
  thing: RS-ERR-13's row names BV-ERR-02 (`BevyError` in a system's signature), not BV-ERR-03, which
  keeps it out of the domain as the anchor asks. `extends` is a delta rule that widens the anchor's
  domain (RS-API-36 to every component, RS-TEST-19 to every test); a delta rule that is an instance
  of an anchor rule takes the anchor's tier and cites it (BV-ECS-22, -23 of RS-CONC-01, RS-PERF-01),
  and one that says what the anchor rule says goes, `revise` removing it with the anchor rule as its
  reason and the chapter's lead citing it with the Bevy part (BV-TEST-08 for RS-TEST-02, BV-ERR-09
  for RS-CLI-24). Non-departures a reader would expect stay as one sentence after the table, each
  citing why (`wildcard_imports` exempts preludes; RS-NAME-02 holds).
- Tier (decision 6): a delta's section 1 is its anchor's word for word, and the profile's
  `strict_scope` its anchor's, since `redefines` compares both. How the delta's domain reads the
  predicate goes in `SKILL.md`'s opening, outside section 1: for a game, a shipped game is
  high-reliability (a panic takes down the player's process or their session's server, an
  authoritative server parses what clients send, saves and replays are data others cannot
  reconstruct), a plugin crate is library code, and a jam prototype takes the relaxed forms. A rule
  that requires CI is `[M]` where the anchor requires CI of every crate at `[M]` (RS-BUILD-27): the
  delta adds a line to a job that exists in or out of section 1's scope (BV-ARCH-07).
- Lint rows (decision 8): a delta's row of a lint its anchor sets alike goes, and its chapter's
  `Decided by tools` with it when nothing is left; the chapter's lead cites the anchor's rows. A rule
  demoted to such a row before still resolves: `skeleton`'s rename check reads a delta's anchor's
  rows as well as its own, as `citations` reads its anchor's configuration. Two allows of one
  decision — which of the anchor's lints the delta relaxes — are one rule (BV-BUILD-12, merging
  -13 and -14, which BV-CORE-24 had stated as one sentence).
- Migration (decision 9): a Bevy row's Old is the spelling a game writes — a type, a free function,
  a method by its bare name where that name is Bevy's alone (`despawn_recursive`), a call shape where
  it is not (`.get_single()`, beside the live `Gradient::get_single`), a feature as the manifest
  quotes it (`"animation"`), a shader directive as the shader writes it (`#import`). A row may stand
  for a family its 0.20 column names (`Pointer<Click>` for every `Pointer<X>`, `FontSource::SansSerif`
  for the generic families). A `changed` row is a shape 0.20 rejects that no fixed string isolates
  (`On<Add, T>`, `Camera { hdr }`) or a spelling that compiles and means something else, which keys
  the silent changes the old chapter tabled by prose (`NextState::set`, `Bloom`); its owner's Check
  carries the pattern, with its fixture. Section 2.2 is the table restricted to what no longer
  compiles: every `gone` row and the rejected `changed` ones, 155 of 180. Rows about rendering and
  reflection internals go, as the chapter's scope already excluded them. No row is an `alias`:
  Bevy keeps no old name working beside its new one.
- `gone` verification for Bevy: the registry holds every Bevy crate the standard names
  (`bevy_pbr`, `bevy_feathers`, `bevy_post_process`, … fetched here with a manifest naming their
  features), since a crate absent from it passes a `gone` row vacuously. The probe had two defects
  the table showed: a doc example's `/// pub struct Parent<…>` read as a definition (a definition now
  has no `/` before it), and a crate-qualified path was looked up by its last segment in every crate
  (`bevy_math::primitives` through `bevy_gizmos`'s `mod primitives`); a path opening with a `bevy_*`
  crate is looked up in that crate alone, and is unprobed when the registry lacks it.
- Controls (decision 14's last item): the override table's branches (`override_title`, and
  `delta_no_table` and `override_target` on the old path) read only a delta not yet normalised, and
  none ships now: `override_title` runs on the demo delta read with `normalized` off and its
  departure stated as an override row. The departures table's controls give `departs` in `also`
  where the defect breaks a pair by construction — a missing table, a row naming no rule.

As built (task 6.1), zig-style normalised; what it decided beyond tasks 3.1, 4.1 and 5.1:

- Core rules (decision 7): all 29 merged, the suffixed ZS-CORE-01b, -12a and -12b among them, which
  showed `revise` a defect: its ranges sentence dropped a suffixed ID, so a rename row named an ID
  no range stated. `_stated` gives a suffixed ID a range of its own and `RenameTable.originals`
  reads a range of one as that ID. None said what no chapter rule says; what only a core rule said
  was a dated std count, and went with it.
- Migration (decision 9): fifteen maps, a hand-kept denylist and four section 2 maps are one table
  of 277 rows (`gone` 153, `alias` 105, `changed` 15, `deprecated` 4), each Since found by looking
  the row up in every release from 0.12.1 to 0.17.0; a `deprecated` row is one only the release
  notes deprecate, or one no fixed string tells from a live name. A Zig row keys a method std's
  types alone had by its bare name, as code calls it, and a namespace by its `std.` path, which the
  probe compiles. The eleven per-topic migration rules merged into the rules owning their rows.
- Compiler rows (decision 8, for a compiler): seven rules stated a compiler error, wholly or in
  part; each error is a row proved by a probe 0.17.0 rejects, and the rule keeps what the compiler
  does not decide (ZS-TEST-21 forbids `Smith.value(usize)`, which builds, beside the row for the
  `valueRange*` calls that do not).
- Tier (decision 6): a restatement `local_scope` cannot see names `[M]`, not `[M!]`: ZS-INTEROP-02's
  "Trigger criteria — treat as `[M]`" widened the scope to every C caller not built from the
  repository. That condition is the subject's, so it is the statement's, and the relaxed form covers
  only a shim built here. Prose saying which side of a disagreement the standard takes no longer
  names a tier (ZS-NAME-01, -02, -13, ZS-ERR-17: "Recommendation … ([M])").
- One concept, one owner (decision 11), as task 4.1 judged pairs, three classes more. A concept with
  two homes moves whole to the chapter whose Scope claims it, by copy and merge: logging (ZS-ERR-28,
  -29 to ZS-OUT-18, -19 beside the `logFn` rule), where bytes go (ZS-CONC-05 to ZS-OUT-16); rules of
  one concept in two sections of one chapter become adjacent and `revise` renumbers them (the
  filesystem rules, ZS-CONC-18 to -22). Two rules whose relaxed forms differ for one choice are
  halves of it ("Production builds are `safe`", ZS-BUILD-24, into "Ship `safe` builds, or define a
  project-local always-on assert", now ZS-ASSERT-04), as is a rule that says it adds a column to
  another's table ("Pick deliberately among `assert`, `unreachable`, `@panic`, and `fatal`",
  ZS-ASSERT-04 then, into ZS-ERR-01). A title that names a second concept splits (ZS-CONC-21's
  `createMemoryMap`, no race, is ZS-CONC-22, its synchronization read off std's `MemoryMap`). Rules
  356 → 343.
- Rule shape (decision 2): zig-style alone put `---` between sections, and the chapter layer reads
  one as a block of the section's last rule: 42 stray rules held one, and only the break after the
  contents list stays. A second GOOD or BAD that shows a case the statement names, not a second
  defect, loses its side (18 of the 20 doubled verdicts: ZS-ERR-21's second block is its relaxed
  form, ZS-NAME-12's the generic container its title allows); one that states a second claim is a
  rule of its own (ZS-TEST-03, a scenario test's name). Prose after an example joins the statement
  and cites the example by its place, as "the second example"; a label the shape lacks (`**What it
  costs:**`) and a `> [!NOTE]` are statement prose.
- Checks (decision 4): of the 36 prose greps the migration merges left, 13 name a shape that is
  itself the defect and run it with a `fires` fixture (ZS-ERR-26's `rg -n -F '.?'`), re-anchoring
  `not_decisive` where the file a hit is in decides (ZS-INTEROP-08's boundary module); 23 are
  judgement, and eight `not_decisive` entries whose span no longer runs went. A passage outside
  every rule that holds no rule moves to where it is read: comptime's anti-pattern index to the
  chapter's lead, interop's boundary checklist to the review protocol, under Review order, since
  `review_sections` fixes the protocol's `##` sections.
- Controls (decision 14's last item): no shipped standard is un-normalised, so the controls of the
  branches only such a standard runs — the core-citation three, `map_here`, `frontmatter.length` and
  `rule_count` — read the demo with `normalized` off (`_on_unnormal`), its shared passages rewritten
  for that profile after the edit, so a core rule the edit states is counted. `prose.provenance`'s
  injected line no longer says "Measured", which `prose.dated` reads too.

As built (task 7.1), the gate deleted:

- `Profile.normalized` is gone, and every condition on it: `anatomy`, `skeleton`, `citations`,
  `crossref`, `mirror`, `frontmatter`, `prose` and `toolchain` hold every standard to the normal
  form, `fmt` prints it for every standard, `measure` counts a standard as it is, and Python's
  examples are linted with the `ruff.toml` a standard ships (the snippet's own selection is for one
  that ships none, as the demo does).
- What only a standard not yet normalised reached went with its controls and the `_on_unnormal`
  helpers: the core-citation branches (`anatomy.core_uncited`, `core_not_a_rule`,
  `core_wrong_chapter`, and the `mis_cited` note), `anatomy.map_here`, `frontmatter.length` and
  `rule_count`, and the override table — `crossref.override_title`, the `no_table` note and the
  layer's `Override` reader. A core rule is `skeleton.core_rule`'s alone, so `below_target` no
  longer reads one. FAIL branches 243 → 236, controls 220 → 213, exemptions 23.
- The reference map's and the reading procedure's slots (`held_here`, `conflict`) are the shared
  templates' own text, the map's count a `{rules}` slot: every `SKILL.md` renders as it did.
- One demo: `tests/structure_fixture.py` builds `checks.demo` and reads it with its profile, and the
  tests that edited the older demo edit this one. Each of its rules is cited, so `revise` refuses to
  remove one; the tests that removed one merge it instead, and the one that holds a revision to the
  skeleton runs `fmt` after it, which renders section 4's line for the merged rule.
- `fmt`, ungated, changes nothing in the shipped tree, and `check --fast --verbose` prints what it
  printed before.

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
