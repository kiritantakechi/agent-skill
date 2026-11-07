# agent-skill

Builds and verifies four engineering standards as agent skills, ships them as the
`style-standards` Claude Code plugin, and links them into every agent on this machine
that reads them.

```bash
uv run agent-skill check             # every check
uv run agent-skill check --fast      # skip the ones that compile every example
uv run agent-skill fmt               # print every file in its normal form, and rewrite its examples
uv run agent-skill revise NAME PLAN  # merge, demote, remove or move rules, renumber, rewrite every citation
uv run agent-skill renumber NAME     # revise with no plan: rename chapters, renumber densely
uv run agent-skill demote NAME PLAN  # revise with a plan: rules to lint rows, merges or removals
uv run agent-skill install           # symlink each skill into every agent present
uv run agent-skill build             # package each as dist/<name>.skill
uv run agent-skill list              # each skill's prefix, counts and toolchain
uv run agent-skill measure           # count, per standard, what the normal form's checks find, and its concepts
uv run pytest                        # the same checks, as tests
```

`ALL CHECKS PASSED` means every check ran and every one of them passed.

## The harness keeps the standard it ships

`pyproject.toml` extends python-style's `assets/ruff.toml`, and ty runs under its
`assets/ty.toml`, so the harness is held to exactly what `python-style`
asks of a reader's code, on the interpreter it names. `tests/test_own_standard.py` runs both
tools over `src/` and `tests/`. The one relaxation, `print` in `cli.py`, is listed there with
its reason, so adding another is an edit beside its reason rather than a line in passing.

## Renumbering is a command, never an edit

Rules are numbered densely, so a renumbering reuses IDs: the old `-03` is the new
`-02` while a different rule becomes the new `-03`. Done as a chain of
replacements, every overlap turns into a citation of the wrong rule, and the result
reads exactly like a correct one. So merging, demoting, removing and renumbering
rules, and renaming chapters, are one operation, `agent-skill revise`. A plan names
some rules and what each becomes — the rule it merged into, the lint-table row that
replaces it, its removal and the reason, or its place in another chapter — and dense
renumbering closes it. One pass from one dictionary then rewrites every citation in
the skills, the abstract standard, `src/`, `tests/` and this file, and nothing is
written unless each kept rule still has its title under its new ID. `renumber` is
`revise` with no plan, and `demote` is `revise` with one. It is also how a concept
keeps one owner: two rules saying one thing are a merge, and a rule in the wrong
chapter is a move.

A move is a plan entry `{"<rule ID>": {"move": "<chapter>", "after": "<rule ID>"}}`,
or `"after": "## <section>"` to make the rule the first of that section, which the
chapter gains if it has none. The rule takes its new chapter's family code and both
families close up, its contents line and its §4 line go with it, and the rename
table records every ID that changed. A move into a chapter the standard does not
ship creates it in the chapter template, with a TODO where its `Scope:` belongs that
`skeleton` fails until it is written, and adds its row to §6; a chapter a plan
leaves with nothing in it is deleted, with its row.

It refuses, writing nothing, while a citation names a rule the plan takes away —
whether that citation should name the lint, another rule or nothing is for a person
to decide — and while a citation names an ID that no rule holds and that the
renumbering would give to one, which is the capture nothing could tell from a
correct citation afterwards. What it cannot catch is an old ID typed in by hand
later: under dense numbering that ID is now another rule's. So a citation is never
rewritten by hand.

For the same reason the passages every standard shares cite no rule. They used to
illustrate citation with `-ERR-03` and `-TEST-05`: a rule cited by a template is
cited in every standard, so `revise` refused to remove it while `fmt` kept writing
the citation back, and renaming the `errors` chapter left the template citing a
rule that did not exist, which the inverse renaming then refused as a capture.
`revise` followed by its inverse restores every byte of the repository; the tests
hold it to that on copies of the shipped standards, renaming `errors` and `testing`
among them, and so does a move followed by the move back to the rule's old place,
drawn at random across all four standards, a move that creates a chapter among them.

The history lives in each standard's `references/renames.md`, which `revise` keeps
current: a table per revision, stating the range each family ran before it and
listing only the IDs that changed, each with the ID, lint row or removal it became.
`migration.md` names the file once and `SKILL.md` not at all, so a reader holding an
old ID can look it up and nothing on the reading path loads it. `skeleton` fails if
an unlisted ID in range no longer names a rule, or a rename table sits anywhere
else.

## Layout

```
.claude-plugin/marketplace.json  the marketplace this repository is: one plugin
abstract/                        the abstract standard: every shared concept, once; installs with nothing
plugins/style-standards/         the plugin, the only part an install copies
  .claude-plugin/plugin.json     its manifest: name, the one version, license, icon
  skills/<name>/                 content only — symlinked live into each agent
    rust-style/                  an anchor
    python-style/                an anchor; its toolchain runs rather than compiles
    bevy-style/                  a delta on rust-style
    zig-style/                   an anchor; its pin follows this machine's `zig`
src/agent_skill/
  doc/                           the one parser and printer of markdown, and the chapter layer
  ids.py                         rule ID, tier, location, version, pin, answer: one type each
  model.py                       a skill's files, each parsed once; where an example sits
  abstract.py                    the abstract standard, read as a standard's chapters are
  vocabulary.py                  what a chapter may be called, and its rules' family code
  layout.py                      where the plugin and its skills live
  shared/                        the passages every standard carries, as templates
  checks/                        what a skill must be true of
  lang/                          turning examples back into code a compiler accepts
  fmt.py                         rewriting examples and shared passages as required
  revise.py                      merging, demoting, moving, renumbering, renaming: one map, citations and all
  profiles/<name>.py             what a check needs to know about one skill
```

## One reader per concept

Every markdown file is read by one parser into a tree and written by one printer.
Fences are recognised first, so nothing inside an example is ever read as a
heading, a table row or a list item; the chapter layer reads that tree as
sections, rules and their parts, contents lists, tool tables and rename tables.
Before it, a `## ` boundary was found in thirteen places and only some knew about
fences, so a demotion cut a rule in half at a `## ` line inside its own example and
every guard still passed: each reader agreed with the others on the files it was
written against and on nothing else. `fmt` is the printer applied to the tree the
file parses to, which is why formatting a formatted file changes nothing, and
`layout` holds every file to that printed form rather than scanning for widths and
blank lines a second way. A rule's Why is measured, and a finding's line counted,
in the text as printed — in a file `layout` passes, the file's own.

The values the harness reasons about have one type each in `ids`, with one parser
and one printer: a rule ID (which keeps an inserted letter, as `XS-ERR-12a`
would), a tier, a location, a version, a pin, an answer a tool did or did not give,
and the branch a finding came from. A rule-ID pattern that dropped the inserted
letter is how a renumbering once left a rename row pointing at an ID that no
longer existed; a version read by hand as three numbers is how an index's
`1.2.3.post1` compared as older than the pin. `tests/test_one_spelling.py` reads
every module as source and fails on a second spelling: a rule-ID or version
pattern outside `ids`, a fence or a heading found by its text, or a column limit,
outside `doc`. The one allowance is the citation grammar `anatomy` reads inside a
block's text, composed from `ids.rule_id()` in two named places.

## One abstract standard

Where two or more standards say the same thing, `abstract/` says it once. It holds
one file per abstract chapter, named from the vocabulary, for every chapter word two
base standards ship, and `principles.md`, the design questions every §3 opens with.
A chapter is in the chapter template, and an entry is rule-shaped: `### AS-ERR-03
[M] Title`, a statement that names no construct of any one language, then one table
with a row for each base standard:

```markdown
| Standard | Rule | Relation | Tier | Reason |
|---|---|---|---|---|
```

The rule is the standard's realisation of the concept, in the chapter whose word
holds the entry. The relation is one of six, the type a delta's departures have:
`realises` and `extends` keep the entry's tier, `tightens` raises it, `overrides`
says something else at any tier, `decided` names the row of the chapter's `Decided
by tools` table a tool settles it by, and `absent` says why the domain has no
instance; every relation but `realises` gives its reason. One function holds both
maps to that law (`ids.breaches`). The Tier cell is the rule's, rendered by `fmt`. A
delta has no row: it realises a concept through its anchor's, unless its departures
table departs from the anchor's realising rule. Two rules that realise one entry
are the pair `mirror` used to declare by title; a rule realises one entry, and a
standard has one rule for an entry.

No skill cites the abstract standard: a skill is installed alone, and its reader has
none to look in. It is the harness's and the authors': `concepts` holds it, `fmt`
prints it, `revise` rewrites its rows with every other citation, and `measure`
counts each standard's realisations of it. Rules of two standards whose titles
overlap and that no entry holds are noted, for every pair of base standards and a
delta with its anchor, so a concept a sweep missed is still seen.

## Every standard has one shape

All four standards share it, and checks hold them to it rather than imitation:

- `SKILL.md` has the same title form and the same eight sections, and its §5 is
  the review protocol's review order, stage for stage (`skeleton`).
- The passages every standard says alike — how to read it, the tiers, the marker
  legend — live once in `agent_skill/shared/`, and each `SKILL.md` carries the
  filled-in copy, because a skill is installed alone (`shared-text`, rewritten by
  `fmt`).
- A chapter is named from one vocabulary, and its rules carry that vocabulary's
  family code, so `errors.md` and `ERR` mean the same thing in every standard.
- A claim a lint decides on its own is a row in its chapter's `Decided by tools`
  table, checked against the shipped configuration (`citations`), not a rule
  with a Why to drift. A compiler ships no configuration, so a `zig` row names
  the error it reports, with `…` for the identifiers, and is proved by a probe
  in the profile that the compiler must reject with that error; a probe with
  no row fails too.
- A rule states its own Why and Check, so one that would only point at another
  is merged into it, and a Why is three lines at most (`anatomy`).
- A rule's prose names no release older than the target: history is the
  migration chapter's and §2's (`anatomy`).
- Rule numbers are dense; `renames.md` maps every old ID to what it became.
- §3 opens with the abstract standard's design questions, in order and word for
  word, each answered in the standard's own terms; a standard's own questions
  follow them. A delta's §3 is its departures table (`concepts`).
- A chapter is an abstract chapter's, named by a file under `abstract/`, or a
  domain chapter its profile declares with the feature of the domain that owns it
  — rust-style's `ownership`, the borrow checker (`concepts`).

Below the sections and chapters, every statement has one normal form, which `fmt`
prints where a formatter can and a check holds where only a person can:

- A chapter opens with a title naming its concept, never its family code, then a
  `Scope:` paragraph, its contents and its sections, `Decided by tools` last.
  Outside §6, a chapter is named only in a `Scope:` paragraph (`skeleton`).
- A rule is its heading; a statement that does not restate the title; a relaxed
  form exactly when it is `[M!]`; its Why; its Check; then at most one GOOD and
  one BAD example — in that order, which `fmt` restores. A second BAD is a second
  rule or a tool row (`anatomy`).
- A rule is cited by its bare ID: never quoted, never behind its chapter's path,
  since §6 maps every family to its file. `fmt` rewrites the other forms
  (`anatomy`).
- A Check is either judgement in prose or runnable `rg` commands followed by the
  finding each reports. Prose that says "grep for" runs nothing and reads like a
  command, so it fails (`anatomy`).
- A tier is one predicate. `[M!]` is mandatory within §1's scope, and its relaxed
  form says what holds outside it and nothing else; no rule restates that scope,
  and an `[M]` or `[M!]` title commands or prohibits rather than advises
  (`anatomy`).
- §4 is a projection of the chapters: it lists chapter rule IDs, grouped by
  chapter in §6's order, and `fmt` renders each line's tier and title from the
  chapter, so §4 states no rule of its own and cannot drift (`skeleton`).
- The migration chapter holds one table, keyed uniquely by the old spelling:
  `| Old | <target> | Status | Since | Rule |`. Status says what the target does
  with it — `gone`, it rejects it; `changed`, it accepts it and it means
  something else; `alias` and `deprecated`, it accepts it and it means what it
  did — and Since is the release, or for Rust the edition, from which that holds.
  The `rg` command after the table is generated by `fmt` from its `gone` and
  `alias` rows, and `toolchain` looks every `gone` row up in the pinned release,
  so a row naming a live API fails (`skeleton`, `toolchain`).
- §2 is three subsections in one order. 2.1 and 2.2 are the migration table's
  `changed` and `gone` rows whose Since is the target's, rendered by `fmt`, so the
  statuses and the two subsections are one partition; each item of 2.3 names the
  rule that owns it (`skeleton`).
- Lint claims are a bijection: every lint the shipped configuration sets one by
  one has exactly one row, a row of a lint on by default says why it is listed,
  and a rule whose Check is only a lint is that row (`citations`). Python's
  examples are linted with the `ruff.toml` the standard ships, less a named
  allowlist of rules about a project's shape, each with its reason.
- A delta states every departure from its anchor in one table — the anchor's
  rule, `overrides`, `tightens` or `extends`, its own rule, the tier before and
  after, and the reason — and each departing rule opens `Departs from <ID>.`. A
  relation its tiers contradict, a departure with no reason, a tier changed with
  no row, and an `[M!]` scoped otherwise than the anchor's all fail (`crossref`),
  and a delta rule that looks like an anchor rule it does not depart from is
  noted (`concepts`).
- The description fills one template, in at most 500 characters and with no
  count of rules: `Use when …. Applies to …. Targets <language> <target>.`
  `SKILL.md` is under 500 lines, and no statement is dated by its writing
  (`frontmatter`, `skeleton`, `prose`).

`agent-skill measure` prints, a row per property and a column per standard, how
far each standard is from that form, and its realisations of the abstract standard
by relation, a delta's through its anchor, with a table of each abstract chapter's
entries. A count a check decides is that check's findings, so a check and its count
cannot disagree.

`zig-style`'s compiler pin
follows this machine's `zig` rather than upstream's newest release, so the zig
bump starts when `pins` reports the local compiler has moved.

A skill directory holds nothing but the skill. Configuration lives in a profile
inside the package, because a skill's directory is what ships — copied with the
plugin, symlinked into each agent and packaged into its `.skill` — so tooling
settings there would reach the reader. `agent_skill/layout.py` names where the
plugin and its skills live; nothing else spells the path.

## The Claude Code plugin

The repository is a plugin marketplace, `kiritantakechi`, holding one plugin,
`style-standards`. In Claude Code:

```
/plugin marketplace add kiritantakechi/agent-skill
/plugin install style-standards@kiritantakechi
```

or, on Claude Code 2.1.275 or later, in one step:

```
/plugin install style-standards --marketplace kiritantakechi/agent-skill
```

The repository is private, so Claude Code clones it with the git credentials on
the machine: run `gh auth login` and `gh auth setup-git` first. The skills are
then `/style-standards:python-style`, `/style-standards:rust-style`,
`/style-standards:bevy-style` and `/style-standards:zig-style`, and load on their
own when the work matches their descriptions.

The version is stated once, in `plugin.json`, and an install stays on it until it
changes: a release bumps it, and `claude plugin tag plugins/style-standards`
tags the commit `style-standards--v<version>`. The `plugin` check holds both
manifests to the layout and the skills, and runs `claude plugin validate` over
them. Install either the plugin or the links below on one machine, not both:
both would load every skill twice.

The version is 2.0.0 because an ID cited under 1.0.0 may now name another rule,
or none. `revise` renumbered the rule IDs of every standard, and removed the
`CORE` family: each `*-CORE-NN` is now a rule of the chapter that owns its
subject. Each standard's `references/renames.md` maps every ID that changed to
the rule, lint row or removal it became.

## Installing for development

`install` symlinks each skill into every agent on this machine that reads the
same shape — a directory per skill, a `SKILL.md` with `name` and `description`
frontmatter, optional `references/` beside it:

| Agent | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Antigravity | `~/.gemini/config/skills/` |

An agent whose config directory is absent is skipped. `--target` limits it to
one.

A symlink rather than a copy, so there is no installed second copy to drift from
the source — Antigravity held one taken a week earlier that differed in every
file, which is the failure this whole apparatus exists to prevent.

A real directory standing in the way is moved to `skills-replaced/` *beside* the
skills directory rather than renamed inside it: discovery walks
`skills/*/SKILL.md` and reads the name from the frontmatter, so a
`rust-style.replaced` sitting next to `rust-style` is a second skill claiming the
same name. A directory already moved there is never overwritten, so a second
copy in the way is left alone. `install` then exits 1 if that copy differs from
the skill, since the agent still reads it, and 0 if it holds exactly what a
package of the skill would.

## Adding a skill

Drop it in `plugins/style-standards/skills/` and it gets every generic check:
frontmatter, rule anatomy, contents agreement, cross-references, layout, marker
discipline, prose, assets. It needs a profile in `src/agent_skill/profiles/` — a
`Profile` record, named in `PROFILES` — only to have *its own* rules applied to its
own examples, or to be compiled. A profile's `toolchain` is that toolchain's settings
for the skill, and names the toolchain by its type. For Rust it is the `RustCrate` the
examples are compiled as — the dependency line and the lint table are per skill, not
per language: `bevy-style` needs Bevy on the dependency line and two lint entries
`rust-style` does not relax, and one shared manifest would have left one of them
unverifiable. A toolchain that needs no manifest carries none: `python-style`'s is a
`PythonSnippet`, which declares instead the interpreter, the `ty` rule levels its
examples are checked under, and the rules of the shipped `ruff.toml` a snippet is
excused from, each with its reason.

## The checks

Every one was added because a real defect shipped past the checks that existed at
the time. The note after each is the defect it would have caught.

| Check | Catches | Added because |
|---|---|---|
| `frontmatter` | the block an agent reads first: spec keys, name, and a description that fills the shared template, in at most 500 characters and with no count of rules | A malformed frontmatter crashed the checker instead of being reported by it — three unguarded `.group(1)` calls. |
| `anatomy` | rule shape (its own Why and Check, its elements in one order, a statement that does not restate its title, one GOOD and one BAD at most), contents agreement and order, duplicate titles, dangling and mis-filed references, a citation quoted or behind a path, per-family counts, near-duplicate rationales, ids that run backwards within a chapter, a release older than the target in a rule's prose, an abbreviated ID list, a relaxed form labelled otherwise, placed after its Why or on a rule that is not `[M!]`, a Check that names a search and runs none, a rule restating the `[M!]` scope, a mandatory title that advises | A rule that pointed at the chapter owning its topic then kept a stale two-row copy of that chapter's table — whose rows were already in it. And 135 rules told a reader of a target-version standard when an API arrived — "(1.96)", "Since 0.19" — which is history they cannot act on, in the one place the migration chapter is not. And `ZS-ASSERT-03, -07, -08 and -20` survived a renumbering with three of its numbers naming other rules, because only whole IDs are rewritten. |
| `skeleton` | the shape every standard shares: the title and its target version, the eight sections, chapter names and family codes from one vocabulary, a chapter's title and `Scope:`, the review protocol's sections and severity model, §5 against the protocol's review order, §2's three subsections and 2.1 and 2.2 as the migration table renders them, §4 as the projection of the rules it lists, one migration table keyed by old spelling and the command it generates, `SKILL.md` under 500 lines | Four standards shared a shape only because each copied the last: chapters named in two conventions, one concept coded `TST` in one standard and `TEST` in the next, three severity models, and a review protocol in three of four. |
| `shared-text` | every passage the standards share is the template in `agent_skill/shared/`, filled in with that standard's values; `agent-skill fmt` rewrites a drifted copy | The reading procedure, tier table and marker legend were copied between `SKILL.md` files and edited in place, so they agreed only nearly — "several of its entries" in one, "most of its entries" in the next. |
| `layout` | a file that is not in its canonical form — the text `agent-skill fmt` prints from the file's tree, which settles width, trailing whitespace, blank lines and list numbering — named at its first differing line; then what printing keeps as written: an example's tabs, CRs and line width, a fence never closed, three backticks inside running text, a table row with more cells than its header; long rule titles and code spans no line can hold as notes | A 135-column line shipped and every check passed: nothing measured width. Later, `X \| None` in a code span split a table cell on GitHub, because a code span does not protect a pipe. Sole owner of the physical checks, because when a second check repeated them one defect produced two findings at two severities. |
| `markers` | one block, one marker, and the marker leads it | 56 blocks spelled the marker across two lines, which left the tools unable to recognise the illustration blocks they exist to exempt. |
| `conventions` | the standard's own rules over its own examples | Review rounds each found an example edited to satisfy one rule while breaking a rule in another chapter. Nothing checked across chapters. |
| `prose` | no build provenance, one marker legend, unbroken blockquotes, no positional cross-references, no statement dated by its writing | Sixty-odd lines said *we checked X* where the standard should say *X*, and twelve chapters each restated the legend in their own wording — two of them describing a convention the library had stopped using. |
| `assets` | the files a reader copies verbatim: `zig fmt` and `ast-check`, a TOML parse, workflow keys and indentation, and that nothing is shipped unreferenced | Six assets shipped and nothing validated any of them. |
| `lints` | the shipped lint table and `clippy.toml` equal the ones the examples are verified against | The asset set `indexing_slicing = "warn"` where a rule requires deny, and the verified crate quietly omitted a third lint while its comment named two. |
| `concepts` | the abstract standard under `abstract/` — each chapter in the template and as `fmt` prints it, entries dense, in their chapter's family, a statement then one realisation table, no construct of one language — and its map: one row per base standard and none for a delta, each naming a rule (or a `Decided by tools` row) of its standard in the entry's chapter, a relation its tiers obey with its reason, a Tier cell as `fmt` renders it, no rule the row of two entries; every chapter an abstract chapter's or a domain chapter its profile declares, and a domain chapter realising nothing; §3 opening with the design questions; no skill citing an abstract ID; and, as notes, rules of two standards that look alike and that no entry holds | `mirror` held twelve pairs, keyed by title against rust-style alone: python-style and zig-style were never compared, and a concept three standards state was at best three pairs, none saying which was wrong. |
| `crossref` | ids cited into another skill, the departures table a delta must state against the anchor its profile names — each row's relation, held to the tier law the abstract standard's rows are with its reason, and its two tiers against the rules, each departing rule's opening against the rows, and `[M!]` the anchor's — and the anchor's own patterns run over the delta's examples | `bevy-style` is a delta on `rust-style` and cites it by id, which nothing was checking; its "where this standard departs" table quoted eight `rust-style` titles that nothing compared against the originals; and two `rust-style` `[M]` rules were firing on nineteen and thirty-five lines of its examples with nothing saying so. |
| `self-application` | every `rg` command a `**Check:**` ships, run over every `// verified` block | A standard whose examples fail its own patterns is not a standard, and nobody was running them. |
| `toolchain` | every `// verified` block compiles, with every declaration analysed, and the tests it ships run; every `gone` migration row is absent from the pinned release | 210 zig blocks claimed `// verified` and nothing compiled them; only 61 actually did. |
| `citations` | a rule's cited check is one the shipped configuration actually enables; every lint the configuration sets one by one has exactly one row, a row of a default lint says why it is listed, no Check is only a lint, and each lint the examples are excused from says why | A standard that cites its checks by tool code can cite one the config disables, one the tool withdrew, or one that never existed — `ASYNC101` was invented, four more were preview and therefore unreachable, and every one of them read as enforced. |
| `plugin` | the plugin and marketplace manifests against the layout and the skills: the plugin's name, one version, a license, the marketplace entry's source; `claude plugin validate` over both, strict on the plugin | The skills became a Claude Code plugin, and the two JSON files that decide what a reader installs were read by nothing. |
| `pins` | a pinned version that has been superseded — the Python tools and interpreter, the Rust toolchain, the Bevy crate — a pin that follows the local toolchain against what runs here, an asset installing a build the harness did not verify against, and an action a shipped or repository workflow names by a ref that can move, or by a commit with no release beside it | The plan said "on 1 September, move the interpreter pin" — a note nobody reads, in a place nobody looks, about a date nobody remembers. |
| `dialect` | a pattern carrying syntax from a grammar it will not be read in | `\|` is alternation to `grep` and a literal pipe to `rg`. Twenty patterns carried it through the migration, and each one matched nothing while reporting clean. The same defect from the reader's side: two commands wrapped at the column limit put a raw newline in the pattern, which the harness accepts under `--multiline` and `rg` rejects for anyone running the command as printed. That half is `layout`'s now: the tree reads a code span as one word, so a wrapped command is a line not in canonical form, and `fmt` joins it. |
| `sensitivity` | the `rg` patterns of each rule its profile gives fixtures, every one shown to hit one of them and every fixture hit by one; each other rule that ships a pattern is listed in the profile as unproven, and an entry that stopped being true fails | `self-application` proves a pattern does not fire on compliant code. Nothing proved one fires at all, and a pattern that matches nothing passes that test perfectly. It then asserted `any`: a migration rule shipped four patterns over four disjoint families and one fixture, so three were counted as proven by a snippet none of them matched. And it skipped a rule with no fixture without a word, so this row claimed every pattern while most had none. |
| `documented` | the README's claims about the checks, against the checks | This table said sixteen rows against eighteen checks, and the `controls` row claimed "every other check" while three were exempt — in the file whose note on `controls` records that an unverified claim in a README is what `controls` exists for. |
| `mutation` | statements a shipped test does not pin | A shipped test passed whether or not the function it tested did anything. |
| `controls` | that every branch that can fail a run, except those exempted, still fails on the defect it owns and no other branch does, with each exemption naming its reason | "Every check carries a negative control" was a claim in a file, verified by hand once and never again. |

## Block markers

Every fenced example carries a marker on its first line, in that language's
comment syntax:

```
// verified               compiles as written, and any test it ships passes
// fragment — …           shown in context rather than run as a unit
// rejected — clippy: …   the rejection is the point, and the tool that rejects it is named
```

`rejected` names its tool because a language has several ways to be wrong —
Python's interpreter, type checker and linter, Rust's compiler and clippy — and
one word for all of them names none of them. The tools a standard may name are
declared on its profile.

A trailing `— GOOD` or `— BAD` names which side of the rule the block
illustrates. Two qualifiers carry meaning to the tools: a `BAD` block and a
`(quoted from …)` block are evidence rather than advice, so the standard's own
rules are not applied to them and their lines stay out of the self-application
corpus — ten `// verified — BAD` blocks sat in it, so a rule whose pattern matched
its own illustration would have failed for demonstrating itself correctly.

## Formatting is a command, not a diff to read

A toolchain's formatter judges an example as the extractor wrote it, so
`agent-skill fmt` runs the same extraction, formats it, and writes the result
back: extract, format, restore, the same three steps for every language. The
extractor writes each block to a file of its own, at column zero. A Rust block
used to sit indented inside a `pub mod`, where rustfmt breaks lines four columns
earlier than a reader's `cargo fmt` would, so the markdown carried wraps no reader
could have predicted. A formatted body goes back into the fence the tree found it
in, by the fence's line, so two blocks with one body are never confused. `fmt` also
rewrites a drifted shared passage from its template, keeping what the skill wrote in
the passage's free regions, and prints every markdown file in its canonical form:
the one fill of each paragraph that `layout` holds the file to, which `revise`
writes too. It prints each standard in its normal form as well: every citation
bare, each rule's elements in order, §4 and §2's 2.1 and 2.2 rendered as the
projections they are, and the command after the migration table generated from its
rows. What it cannot place — a block no element of a rule holds, a §4 that states a
rule of its own — it leaves where it stands, for a person, and the checks report.

## `self-application` runs the real `rg`

The patterns are run by `rg`, not reimplemented. Compiling one with Python's `re`
looked equivalent and was not:

- `[[:space:]]` parses as a character class of `[:space` plus a literal `]` and
  matches nothing, so one Check was reported as ran-and-clean while being
  incapable of firing.
- Five Checks whose pattern ends in a bare `(` were dropped as "unparseable".
There is one dialect. The library used to hold two, selected by whether a command
happened to carry `-E`, and the basic half is where the silent failures lived:
`\|` is alternation there and a literal pipe everywhere else, so a pattern read in
the wrong grammar matches nothing and reports clean. A pattern `rg` rejects is now
a failure rather than a retry as a fixed string — turning a broken regex into a
literal is how a check stops being able to fire while still reporting.

Each example is written to its own file, because `--multiline` matches across
whatever it is given and a concatenated corpus manufactures hits that straddle two
unrelated examples. Patterns match the code half of each line unless the pattern
itself contains the language's comment token — `//`, or Python's `#` — since a
Check that searches for a comment means the comment.

Hits are reported in three tiers: a shipped `rg` command that decides (**fails**), a
prose span or a Check listed in the profile's `not_decisive` table (notes), and a
pattern with more hits than `judgement`, which enumerates rather than accuses.
`bevy-style` uses the first tier deliberately: its `**Check:**` sections over
the shapes Bevy rejected since 0.15, over the plugin forms it forbids, and over
the boundary itself are literal `rg` commands, so an example written against an
older engine, written as a function, or naming the engine from a simulation crate
fails the build rather than being noticed by a reader. The README states no count of
them: a count is the one thing every engine bump changes, and the last one was
wrong by one.

Each `not_decisive` entry quotes a literal substring of that rule's own Check,
verified to still be there, so rewriting a rule cannot leave a stale entry
quietly suppressing its pattern.

## The negative controls run

`controls` copies the tree once per control, injects one defect, and asserts that
the branch the control names reports a failure, and that no other branch of the
check does; the controls run at once, each over its own copy. A control that stops
firing is itself a failure, and so is a fixture whose anchor text has drifted out
of the skill. `pytest` runs the same table one test per control, through the same
runner, and holds the table to the branches: every branch that can fail a run has
one control or one stated exemption. A branch the tree made unreachable goes with
its control: `dialect` lost its wrapped-command branch when a code span became one
word, because a defect no input can produce is not a branch to keep a control for.

Not every finding becomes a check, and two did not.

A summary that cites the wrong rule looked mechanical and is not: a good summary
says the same thing in different words, so absolute word overlap separates
nothing — a correct citation scores 0.000. What separates is *relative*, another
rule in the same chapter scoring much higher, and even that was coincidence twice
in five hits. It shipped as a note inside `anatomy` rather than as a check that
fails, because a check people learn to route around is worse than no check, and
it went when §4 became a projection: a line rendered from the rule it names
summarises nothing, so it cannot cite the wrong rule.

A title that no longer describes its own body was not built at all. The stale
title scored 0.50 against its statement and the corrected one scored 0.50 too,
while fourteen perfectly good titles scored 0.00 — for the same reason, a title
and its statement deliberately do not repeat each other. That one is caught by
reading, and saying so here is cheaper than the next person re-deriving it.

A check that cannot fail looks exactly like a check that passes. An early zig
probe reported all 375 symbols present, including a deliberately fake one,
because it lived in a function Zig never analyses. `clippy` was reported clean
because half the shipped lint table is `warn` and clippy exits 0 on a warning.
`zig` was reported absent because the probe ran `zig --version`, which is not how
zig spells it.

## The skill says nothing about how it was built

A standard states facts and cites sources. It does not report that someone
checked, on which machine, or on what date — a reader cannot act on any of that,
and it is the residue of writing the thing rather than content of the thing. The
`prose` check enforces this.
