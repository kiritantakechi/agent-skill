## Why

The skeleton check makes the four standards agree at the level a reader navigates by: the H1, the
eight H2 sections, chapter file names and family codes. Below that level they differ, and they
differ in ways a reader cannot see until they act on a rule.

**Same name, different structure.** Seven rust-style chapters open `# RS-XXX — Topic` with no
`Scope:` paragraph and 85 rules that restate their title as their first sentence; the other 41
chapters across the four standards open with a title and a scope. A rule's elements come in one
order in rust-style and six in zig-style, with zero to five code blocks. Section 2 of zig-style is
206 lines in ten subsections; its siblings are about 50 lines in three or four, and the four put
their subsections in four different orders.

**One tier, several predicates.** Section 1 defines `[M!]` once, as a scope. In rust-style 8 of 21
relaxed forms are not that complement but exceptions that hold in libraries too, and 2 relax
frequency rather than scope; zig-style redefines the scope locally in 25 rules, five ways; bevy-style
replaces the predicate outright. Fourteen `[M]` statements in rust-style contain an "unless", and 16
`[M]` titles there begin "Prefer", "Know" or "Remember" — mandatory in tier, optional in mood.

**Maps that are not functions.** A core rule in section 4 cites one to four chapter rules for no
stated reason, and in three standards some core rules carry a different tier from the rules they
cite. In rust-style, 25 rules have a Check that is only a lint, and 4 explicit config entries have no
row. The migration chapters are keyed by release rather than by symbol: zig-style declares three
status values and uses 28, bevy-style lists one symbol twice and another as removed while it is
live, and every migration grep is maintained by hand. bevy-style relates to rust-style in five
forms, of which only the override table is structured.

**One concept, several homes.** python-style states the PEP 686 change in six places; zig-style
has four overlapping tables for choosing a failure channel; rust-style says "lazy global" four
times.

The `one-parse-one-print` change gives the harness a tree in which each of these is a checkable
property. This change states the properties and brings the standards into them.

## What Changes

- **One chapter template and one rule shape**, printed by `fmt` and enforced by `skeleton`: title
  and `Scope:`; contents; sections; rules as heading, statement, relaxed form if and only if `[M!]`,
  Why, Check, then at most one GOOD and one BAD example; "Decided by tools" last.
- **One cross-reference form**: a rule is cited by its bare ID, never by a path or a chapter phrase;
  a chapter is named only in section 6.
- **One Check form**: either runnable `rg` commands followed by the finding they report, or a
  judgement stated as "Read: …". Prose "grep for …" is neither and fails.
- **Section 2 has three fixed subsections in one order** in every standard: what compiles and
  behaves differently, what no longer compiles (one table), what the target gained.
- **Tier is one predicate.** `[M!]` means mandatory within section 1's scope and nothing else; its
  relaxed form is the complement and nothing else. A condition belongs in the statement. Title
  modality follows the tier: `[M]` and `[M!]` titles command or prohibit; only `[S]` may prefer.
- **Section 4 becomes a projection.** Core rules stop being a family: section 4 lists chapter rule
  IDs grouped by chapter in section 6's order, and `fmt` renders each line's tier and title from the
  chapter, so the two cannot drift. `CORE` IDs are revised to the chapter rules they abbreviated.
  **BREAKING** for citations of `*-CORE-*`; the rename tables record each.
- **Lint claims are a bijection.** Every lint the shipped configuration sets explicitly has exactly
  one row; a rule whose Check is only a lint becomes that row; a row for a default lint states why
  it is listed.
- **Migration is a function from old symbol to row.** One table per standard with fixed columns —
  old spelling, target spelling, status from a closed set, rule — keyed uniquely by old spelling.
  The migration Checks are generated from it, and every `gone` pattern is verified to match nothing
  in the pinned toolchain's public API.
- **The delta is a typed map.** bevy-style's departures become one table of (rust-style rule,
  relation ∈ {overrides, tightens, extends}, bevy-style rule, tier before → after, reason); every
  departing rule opens by naming what it departs from; restatements of rust-style become citations.
- **One concept, one owner.** The duplicate pairs and multiple homes the review measured are merged
  through `revise`.
- **Examples obey the shipped configuration.** Python examples are linted with the shipped
  `ruff.toml` minus a named snippet allowlist, as Rust examples already compile under the shipped
  lint table.
- **The frontmatter description is one template**, use case first, no rule counts, no source lists,
  and well under the 1024-character limit; time-sensitive and provenance text is removed and the
  `prose` check learns its patterns; every SKILL.md is under 500 lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `standard-structure`: the chapter template, rule shape, cross-reference and Check forms, the
  section 2 skeleton, the tier predicate, section 4 as a projection, the lint bijection, migration
  as a symbol table, the typed delta, and the description template.
- `python-verification`: examples are linted under the shipped configuration minus a named
  allowlist.

## Impact

- **Skills:** every chapter is re-printed; roughly 150–250 rules move, merge or are demoted across
  the four standards; core IDs disappear into chapter IDs; migration chapters shrink to a few rules
  and a table each; `zig-style/SKILL.md` falls under 500 lines.
- **Harness:** new properties in `skeleton`, `anatomy`, `citations`, `crossref` and `prose`; `fmt`
  renders section 4 and the migration Checks.
- **Readers:** citations of `CORE` IDs and of merged rules resolve through `renames.md`.
- **Depends on:** `one-parse-one-print`.
