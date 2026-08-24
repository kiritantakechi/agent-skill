# agent-skill

Builds and verifies the agent skills in `skills/`, and links them into every
agent on this machine that reads them.

```bash
uv run agent-skill check          # every check
uv run agent-skill check --fast   # skip the ones that need cargo or zig
uv run agent-skill fmt            # rewrite each rust example as rustfmt would have it
uv run agent-skill install        # symlink each skill into every agent present
uv run agent-skill build          # package each as dist/<name>.skill
uv run pytest                     # the same checks, as tests
```

`ALL CHECKS PASSED` means every check ran and every one of them passed.

## Layout

```
skills/<name>/                 content only — symlinked live into each agent
src/agent_skill/
  model.py                     what a skill is made of; one parse, shared
  checks/                      what a skill must be true of
  lang/                        turning examples back into code a compiler accepts
  fmt.py                       rewriting an example the way the check will demand
  profiles/<name>.py           what a check needs to know about one skill
```

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
applied to its own examples, or to be compiled. A profile that names a
`toolchain` also names the `Crate` its examples are compiled as — the dependency
line and the lint table are per skill, not per language: `bevy-style` needs Bevy
on the dependency line and two lint entries `rust-style` does not relax, and one
shared manifest would have left one of them unverifiable.

## The checks

Every one was added because a real defect shipped past the checks that existed at
the time. The note after each is the defect it would have caught.

| Check | Catches | Added because |
|---|---|---|
| `frontmatter` | the block an agent reads first: spec keys, name, description length, stated rule count | A malformed frontmatter crashed the checker instead of being reported by it — three unguarded `.group(1)` calls. |
| `anatomy` | rule shape (Why/Check, or a pointer at the owner), contents agreement and order, duplicate titles, dangling and mis-filed references, per-family counts, near-duplicate rationales, ids that run backwards within a chapter, a summary that cites a sibling of the rule it is about | A rule that pointed at the chapter owning its topic then kept a stale two-row copy of that chapter's table — whose rows were already in it. Later, a core rule summarised one rule and cited the one above it: the id existed and lived in the cited chapter, which was all anything asked. |
| `layout` | line width, trailing whitespace, tabs, CR, fence balance, doubled blanks, list numbering; long rule titles as notes | A 135-column line shipped and every check passed: nothing measured width. Sole owner of the physical checks, because when a second check repeated them one defect produced two findings at two severities. |
| `markers` | one block, one marker, and the marker leads it | 56 blocks spelled the marker across two lines, which left the tools unable to recognise the illustration blocks they exist to exempt. |
| `conventions` | the standard's own rules over its own examples | Review rounds each found an example edited to satisfy one rule while breaking a rule in another chapter. Nothing checked across chapters. |
| `prose` | no build provenance, one marker legend, unbroken blockquotes, no positional cross-references | Sixty-odd lines said *we checked X* where the standard should say *X*, and twelve chapters each restated the legend in their own wording — two of them describing a convention the library had stopped using. |
| `assets` | the files a reader copies verbatim: `zig fmt` and `ast-check`, a TOML parse, workflow keys and indentation, and that nothing is shipped unreferenced | Six assets shipped and nothing validated any of them. |
| `lints` | the shipped lint table equals the one the examples are verified against | The asset set `indexing_slicing = "warn"` where a rule requires deny, and the verified crate quietly omitted a third lint while its comment named two. |
| `mirror` | rules that say the same thing in two skills agree on tier | A renumbering pass twice pointed the table at unrelated rules. It is anchored on titles now, and notices a pair it does not yet hold. |
| `crossref` | ids cited into another skill, the override table that says the two disagree, and the anchor's own greps run over the delta's examples | `bevy-style` is a delta on `rust-style` and cites it by id, which nothing was checking; its "where this standard departs" table quoted eight `rust-style` titles that nothing compared against the originals; and two `rust-style` `[M]` rules were firing on nineteen and thirty-five lines of its examples with nothing saying so. |
| `self-application` | every `grep` a `**Check:**` ships, run over every `// verified` block | A standard whose examples fail its own greps is not a standard, and nobody was running them. |
| `toolchain` | every `// verified` block compiles, with every declaration analysed, and the tests it ships run | 210 zig blocks claimed `// verified` and nothing compiled them; only 61 actually did. |
| `mutation` | statements a shipped test does not pin | A shipped test passed whether or not the function it tested did anything. |
| `controls` | that every other check still fails on the defect it owns | "Every check carries a negative control" was a claim in a file, verified by hand once and never again. |

## Block markers

Every fenced example carries a marker on its first line, in that language's
comment syntax:

```
// verified            compiles as written, and any test it ships passes
// fragment — …        shown in context rather than compiled as a unit
// does-not-compile    the error is the point
```

A trailing `— GOOD` or `— BAD` names which side of the rule the block
illustrates. Two qualifiers carry meaning to the tools: a `BAD` block and a
`(quoted from …)` block are evidence rather than advice, so the standard's own
rules are not applied to them and their lines stay out of the self-application
corpus — ten `// verified — BAD` blocks sat in it, so a rule whose grep matched
its own illustration would have failed for demonstrating itself correctly.

## Formatting is a command, not a diff to read

`cargo fmt --check` judges an example as the extractor wrote it — indented inside
a `pub mod`, where rustfmt's `chain_width` and `struct_lit_width` bite earlier
than they do at column zero. That made the check report diffs a reader of the
markdown could not have predicted, so `agent-skill fmt` runs the same extraction,
formats it, and writes the result back.

## `self-application` runs the real grep

The greps are run by `grep`, not reimplemented. Compiling a rule's pattern with
Python's `re` looked equivalent and was not:

- `[[:space:]]` parses as a character class of `[:space` plus a literal `]` and
  matches nothing, so one Check was reported as ran-and-clean while being
  incapable of firing.
- Five Checks whose pattern ends in a bare `(` were dropped as "unparseable".
- `grep` without `-E` is **BRE**, where `(` and `)` are literal. Reading
  `grep -rn 'pub fn main()' src/` as an ERE accused eight correct examples of
  being the old entry point.

The command's own flags select the dialect, and a pattern grep rejects is retried
as a fixed string. Patterns match the code half of each line unless the pattern
itself contains `//` — a Check that greps for a comment means the comment.

Hits are reported in three tiers: a shipped `grep` that decides (**fails**), a
prose span or a Check listed in the profile's `not_decisive` table (notes), and a
pattern with more hits than `judgement`, which enumerates rather than accuses.
`bevy-style` uses the first tier deliberately: fifteen of its `**Check:**`
sections are literal `grep` commands — thirteen over the APIs Bevy removed
between 0.15 and 0.19, one over the plugin forms it forbids, and one over the
boundary itself — so an example written against an older engine, written as a
function, or naming the engine from a simulation crate fails the build rather
than being noticed by a reader.

Each `not_decisive` entry quotes a literal substring of that rule's own Check,
verified to still be there, so rewriting a rule cannot leave a stale entry
quietly suppressing its grep.

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
