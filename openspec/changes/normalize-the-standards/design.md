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

### 3. A citation is a bare ID

A rule is cited by its ID, unquoted: `RS-ERR-03`, never `` `RS-ERR-03` ``, never
`` `references/errors.md` RS-ERR-03 ``, never "the errors chapter's rule". Section 6 maps prefix to
file, which is the one place a reader needs the path; references stay one level deep. `fmt`
rewrites the other forms; `anatomy` fails on them afterwards.

### 4. A Check that names a pattern runs it

A Check is either judgement in prose or one or more runnable `rg` commands followed by the finding
they report. Prose that names a pattern without running it ("grep for `X`", "search for …") fails:
it escapes self-application while reading like a command. The 52 such Checks in bevy-style and
their kin elsewhere become `rg` commands, each with its `fires` fixture or an `unproven` entry.

### 5. Section 2 has three subsections, in one order

`2.1 Compiles, and behaves differently` · `2.2 No longer compiles` · `2.3 What <target> gained`.
2.2 is one table (old | new | rule). Each item names the rule or migration row that owns it, so
section 2 is an index into the chapters, not a second home for their content. Toolchain notes that
are neither (ZLS support, `zig reduce`) leave section 2.

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
