# agent-skill

Builds and verifies the agent skills in `skills/`, and links them into every
agent on this machine that reads them.

```bash
uv run agent-skill check          # every check
uv run agent-skill check --fast   # skip the ones that need cargo or zig
uv run agent-skill fmt            # rewrite examples and shared text as they are required to read
uv run agent-skill renumber NAME  # rename chapters, renumber rules densely, rewrite every citation
uv run agent-skill install        # symlink each skill into every agent present
uv run agent-skill build          # package each as dist/<name>.skill
uv run pytest                     # the same checks, as tests
```

`ALL CHECKS PASSED` means every check ran and every one of them passed.

## Renumbering is a command, never an edit

Rules are numbered densely, so a renumbering reuses IDs: the old `-03` is the new
`-02` while a different rule becomes the new `-03`. Done as a chain of
replacements, every overlap turns into a citation of the wrong rule, and the result
reads exactly like a correct one. `agent-skill renumber` rewrites every citation in
`skills/`, `src/`, `tests/` and this file in one pass from one dictionary, checks
that each old ID still reaches a rule with the same title, and writes nothing
unless it does. It keeps the standard's `migration.md` rename table current, so a
reader holding an old ID can look it up: the table states the range each family ran
before the revision and lists only the IDs that changed, and `skeleton` fails if an
unlisted ID in range no longer names a rule.

What it cannot do is catch an old ID typed in by hand afterwards: under dense
numbering that ID is now another rule's, and nothing can tell the two apart. So a
citation is never rewritten by hand.

## Layout

```
skills/<name>/                 content only — symlinked live into each agent
  rust-style/                    an anchor
  python-style/                  an anchor; its toolchain runs rather than compiles
  bevy-style/                    a delta on rust-style
  zig-style/                     an anchor, exempt from the shared shape until its own bump
src/agent_skill/
  model.py                     what a skill is made of; one parse, shared
  vocabulary.py                what a chapter may be called, and its rules' family code
  shared/                      the passages every standard carries, as templates
  checks/                      what a skill must be true of
  lang/                        turning examples back into code a compiler accepts
  fmt.py                       rewriting examples and shared passages as required
  renumber.py                  renaming chapters and renumbering rules, citations and all
  profiles/<name>.py           what a check needs to know about one skill
```

## Every standard has one shape

`rust-style`, `python-style` and `bevy-style` share it, and checks hold them to
it rather than imitation:

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
  with a Why to drift.
- A Why is three lines at most, and rule numbers are dense; `migration.md` maps
  every old ID to what it became.

`zig-style` is exempt by declaration, with its reason, and the exemption is
reported the moment it is no longer needed. Its compiler pin follows this
machine's `zig` rather than upstream's newest release, so the zig bump starts
when `pins` reports the local compiler has moved.

A skill directory holds nothing but the skill. Configuration lives in a profile
inside the package, because `skills/<name>/` is symlinked into each agent and
packaged into the shipped `.skill` — tooling settings there would be shipped to
the reader.

## Installing

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
same name.

## Adding a skill

Drop it in `skills/` and it gets every generic check: frontmatter, rule anatomy,
contents agreement, cross-references, layout, marker discipline, prose, assets.
It needs a profile in `src/agent_skill/profiles/` only to have *its own* rules
applied to its own examples, or to be compiled. A profile that names the `rust`
toolchain also names the `Crate` its examples are compiled as — the dependency
line and the lint table are per skill, not per language: `bevy-style` needs Bevy
on the dependency line and two lint entries `rust-style` does not relax, and one
shared manifest would have left one of them unverifiable. A toolchain that needs
no manifest carries none: `python-style` names `toolchain = "python"` and
`crate = None`, and declares instead the ruff selection and the `ty` rule levels
its examples are checked under.

## The checks

Every one was added because a real defect shipped past the checks that existed at
the time. The note after each is the defect it would have caught.

| Check | Catches | Added because |
|---|---|---|
| `frontmatter` | the block an agent reads first: spec keys, name, description length, stated rule count | A malformed frontmatter crashed the checker instead of being reported by it — three unguarded `.group(1)` calls. |
| `anatomy` | rule shape (Why/Check, or a pointer at the owner), contents agreement and order, duplicate titles, dangling and mis-filed references, per-family counts, near-duplicate rationales, ids that run backwards within a chapter, a summary that cites a sibling of the rule it is about | A rule that pointed at the chapter owning its topic then kept a stale two-row copy of that chapter's table — whose rows were already in it. Later, a core rule summarised one rule and cited the one above it: the id existed and lived in the cited chapter, which was all anything asked. |
| `skeleton` | the shape every standard shares: the title and its target version, the eight sections, chapter names and family codes from one vocabulary, the review protocol's sections and severity model, §5 against the protocol's review order; a structure exemption without a reason, or one standing over a standard that already conforms | Four standards shared a shape only because each copied the last: chapters named in two conventions, one concept coded `TST` in one standard and `TEST` in the next, three severity models, and a review protocol in three of four. |
| `shared-text` | every passage the standards share is the template in `agent_skill/shared/`, filled in with that standard's values; `agent-skill fmt` rewrites a drifted copy | The reading procedure, tier table and marker legend were copied between `SKILL.md` files and edited in place, so they agreed only nearly — "several of its entries" in one, "most of its entries" in the next. |
| `layout` | line width, trailing whitespace, tabs, CR, fence balance, doubled blanks, list numbering; long rule titles as notes | A 135-column line shipped and every check passed: nothing measured width. Sole owner of the physical checks, because when a second check repeated them one defect produced two findings at two severities. |
| `markers` | one block, one marker, and the marker leads it | 56 blocks spelled the marker across two lines, which left the tools unable to recognise the illustration blocks they exist to exempt. |
| `conventions` | the standard's own rules over its own examples | Review rounds each found an example edited to satisfy one rule while breaking a rule in another chapter. Nothing checked across chapters. |
| `prose` | no build provenance, one marker legend, unbroken blockquotes, no positional cross-references | Sixty-odd lines said *we checked X* where the standard should say *X*, and twelve chapters each restated the legend in their own wording — two of them describing a convention the library had stopped using. |
| `assets` | the files a reader copies verbatim: `zig fmt` and `ast-check`, a TOML parse, workflow keys and indentation, and that nothing is shipped unreferenced | Six assets shipped and nothing validated any of them. |
| `lints` | the shipped lint table and `clippy.toml` equal the ones the examples are verified against | The asset set `indexing_slicing = "warn"` where a rule requires deny, and the verified crate quietly omitted a third lint while its comment named two. |
| `mirror` | rules that say the same thing in two skills agree on tier | A renumbering pass twice pointed the table at unrelated rules. It is anchored on titles now, and notices a pair it does not yet hold. |
| `crossref` | ids cited into another skill, the override table that says the two disagree, and the anchor's own patterns run over the delta's examples | `bevy-style` is a delta on `rust-style` and cites it by id, which nothing was checking; its "where this standard departs" table quoted eight `rust-style` titles that nothing compared against the originals; and two `rust-style` `[M]` rules were firing on nineteen and thirty-five lines of its examples with nothing saying so. |
| `self-application` | every `rg` command a `**Check:**` ships, run over every `// verified` block | A standard whose examples fail its own patterns is not a standard, and nobody was running them. |
| `toolchain` | every `// verified` block compiles, with every declaration analysed, and the tests it ships run | 210 zig blocks claimed `// verified` and nothing compiled them; only 61 actually did. |
| `citations` | a rule's cited check is one the shipped configuration actually enables | A standard that cites its checks by tool code can cite one the config disables, one the tool withdrew, or one that never existed — `ASYNC101` was invented, four more were preview and therefore unreachable, and every one of them read as enforced. |
| `pins` | a pinned version that has been superseded — the Python tools and interpreter, the Rust toolchain, the Bevy crate — a pin that follows the local toolchain against what runs here, and an asset installing a build the harness did not verify against | The plan said "on 1 September, move the interpreter pin" — a note nobody reads, in a place nobody looks, about a date nobody remembers. |
| `dialect` | a pattern carrying syntax from a grammar it will not be read in | `\|` is alternation to `grep` and a literal pipe to `rg`. Twenty patterns carried it through the migration, and each one matched nothing while reporting clean. The same defect from the reader's side: two commands wrapped at the column limit put a raw newline in the pattern, which the harness accepts under `--multiline` and `rg` rejects for anyone running the command as printed. |
| `sensitivity` | every pattern a rule ships, shown to catch the defect it was written for | `self-application` proves a pattern does not fire on compliant code. Nothing proved one fires at all, and a pattern that matches nothing passes that test perfectly. It then asserted `any`: `ZS-MIG-13` ships four patterns over four disjoint families and one fixture, so three were counted as proven by a snippet none of them matched. |
| `documented` | the README's claims about the checks, against the checks | This table said sixteen rows against eighteen checks, and the `controls` row claimed "every other check" while three were exempt — in the file whose note on `controls` records that an unverified claim in a README is what `controls` exists for. |
| `mutation` | statements a shipped test does not pin | A shipped test passed whether or not the function it tested did anything. |
| `controls` | that every check except those exempted still fails on the defect it owns, with each exemption naming its reason | "Every check carries a negative control" was a claim in a file, verified by hand once and never again. |

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
declared on its profile. `zig-style` still declares the older `does-not-compile`,
until its own bump.

A trailing `— GOOD` or `— BAD` names which side of the rule the block
illustrates. Two qualifiers carry meaning to the tools: a `BAD` block and a
`(quoted from …)` block are evidence rather than advice, so the standard's own
rules are not applied to them and their lines stay out of the self-application
corpus — ten `// verified — BAD` blocks sat in it, so a rule whose pattern matched
its own illustration would have failed for demonstrating itself correctly.

## Formatting is a command, not a diff to read

`cargo fmt --check` judges an example as the extractor wrote it — indented inside
a `pub mod`, where rustfmt's `chain_width` and `struct_lit_width` bite earlier
than they do at column zero. That made the check report diffs a reader of the
markdown could not have predicted, so `agent-skill fmt` runs the same extraction,
formats it, and writes the result back. It rewrites a drifted shared passage from
its template the same way, keeping what the skill wrote in the passage's free
regions.

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
itself contains `//` — a Check that searches for a comment means the comment.

Hits are reported in three tiers: a shipped `rg` command that decides (**fails**), a
prose span or a Check listed in the profile's `not_decisive` table (notes), and a
pattern with more hits than `judgement`, which enumerates rather than accuses.
`bevy-style` uses the first tier deliberately: its `**Check:**` sections over
the APIs Bevy removed since 0.15, over the plugin forms it forbids, and over the
boundary itself are literal `rg` commands, so an example written against an older
engine, written as a function, or naming the engine from a simulation crate fails
the build rather than being noticed by a reader. The README states no count of
them: a count is the one thing every engine bump changes, and the last one was
wrong by one.

Each `not_decisive` entry quotes a literal substring of that rule's own Check,
verified to still be there, so rewriting a rule cannot leave a stale entry
quietly suppressing its pattern.

## The negative controls run

`check_controls` copies the tree once per control, injects one defect, and asserts
that the check owning it reports a failure. A control that stops firing is itself
a failure, and so is a fixture whose anchor text has drifted out of the skill.
`pytest` runs the same table one test per control.

Not every finding becomes a check, and two did not.

A summary that cites the wrong rule looked mechanical and is not: a good summary
says the same thing in different words, so absolute word overlap separates
nothing — a correct citation scores 0.000. What separates is *relative*, another
rule in the same chapter scoring much higher, and even that was coincidence twice
in five hits. It ships as a note inside `anatomy` rather than as a check that
fails, because a check people learn to route around is worse than no check.

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
