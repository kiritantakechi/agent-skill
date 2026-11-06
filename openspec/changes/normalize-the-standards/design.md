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

### 8. Lint claims are a bijection

Every lint the shipped configuration sets explicitly has exactly one row, in the chapter that owns
its subject; a row for a lint on by default says why it is listed. A rule whose Check is only a lint
code is that row, and `revise` demotes it. `citations` gains both directions.

### 9. Migration is a function from old spelling to row

Each migration chapter holds one table keyed uniquely by old spelling:

| Old | `<target>` | Status | Rule |

Status is one of `gone`, `alias`, `changed`, `deprecated`. The migration rules shrink to the ones
that state a behaviour or a procedure; the rest become rows. The grep a reader runs is generated by
`fmt` from the `gone` and `alias` rows, and each toolchain verifies its rows against the pinned
release (Python: the name is absent from, or an alias in, the module; Rust and Bevy: `rg` over the
pinned crate sources; Zig: a compile probe), so a row naming a live API fails.

### 10. The delta is a typed map

bevy-style's departures are one table: rust-style rule | relation (`overrides`, `tightens`,
`extends`) | bevy-style rule | tier before → after | reason. A departing bevy-style rule opens
"Departs from RS-x." A bevy-style rule that restates a rust-style rule becomes a citation. A
silent tier change against the anchor fails; the `[M!]` predicate is rust-style's, not redefined.
The asset rule already landed is the same map for files.

### 11. One concept, one owner

The duplicate pairs and multiple homes the review measured are merged with `revise`. `anatomy`'s
near-duplicate note stays a note: overlap of words decides nothing on its own.

### 12. Examples obey what ships

Python examples are linted with the shipped `ruff.toml` minus a named allowlist of rules about
project shape (`D100`, `D103`, `INP001`, `N999`, `S101`, `PLR2004`), each with its reason. Rust
examples already compile under the shipped lint table.

### 13. The frontmatter and SKILL.md are bounded

The description is one shared template: the use case first, the artifacts that trigger it, the
target version; no rule count, no source list; at most 500 characters. SKILL.md is under 500 lines.
`prose` fails on time-sensitive and build-provenance phrasing ("currently", "not yet", "as of",
"compiled against", "measured", a date outside a migration table).

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
  Status, Rule; 2.9 may want one convention for both.

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
