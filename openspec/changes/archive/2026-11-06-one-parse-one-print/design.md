## Context

The harness is ~10.8k lines that parse markdown with regular expressions at the point of use. Each
check re-derives what it needs: the rule IDs in a file, the boundaries of a section, whether a line
is inside a fence. That is why a concept has many spellings, and why a defect in one spelling is
invisible to every check written against another. Phase L0 corrected the instances; this change
removes the mechanism.

The owner's criterion for the result is isomorphism in the mathematical sense: one representation
per concept, operations stated as maps with laws, structure that mirrors the domain rather than the
order in which code was written. That criterion decides every trade-off below.

Dense rule numbering is kept, by the owner's decision. An ID is therefore an ordinal within its
family, and renumbering is a permutation the harness must apply exactly.

## Goals / Non-Goals

**Goals:**

- One parser and one printer for every file; `fmt = print ∘ parse`, idempotent.
- One type, parser and printer for each of: rule ID, tier, location, version, pin, answer.
- One check signature; selection applied to findings, not inputs.
- Controls ↔ branches as a bijection, enforced by a test.
- Profiles as records; no skill or language name in generic code.
- Toolchains as extract/restore pairs with one driver.
- `revise` as one operation with tested laws.

**Non-Goals:**

- Changing what any rule says. The content work (canonical rule shape, tier as one predicate, core
  rules as a projection, lint bijection, migration as a symbol table) is `normalize-the-standards`,
  built on this model. Only mechanical re-printing happens to the skills here.
- Replacing `rg` as the executor of shipped patterns.
- Stable (non-dense) IDs.

## Decisions

### 1. The tree is the only reader of markdown

`agent_skill.doc` parses a file into `Doc(frontmatter, blocks)`. A block is one of `Heading`,
`Paragraph`, `Fence`, `Table`, `ListBlock`, `Quote`. Fences are recognised first, in one scanner,
so no later stage can mistake a `## ` or a `|` inside an example for structure. The chapter layer
(`agent_skill.doc.chapter`) reads a `Doc` into `Chapter(title, scope, contents, sections,
tools)` and a section into `Rule`s and other blocks.

`print` is the exact inverse on canonical input. Two laws are property-tested over every shipped
file and over generated trees:

- `parse(print(d)) == d` for every tree `d`.
- `print(parse(t)) == t` for every canonical text `t`, and `print(parse(·))` is idempotent on all
  text. `fmt` is that projection plus the toolchain formatters (decision 6).

A file that does not survive `print(parse(t)) == t` is not canonical, and the `layout` check reports
the first differing line. This subsumes the physical checks `layout` owns today (width, trailing
whitespace, fence balance, doubled blanks), which become properties of the printer rather than
separate scans.

*Alternative considered:* a CommonMark library. Rejected: the skills use a small, fixed subset, and
the rule layer needs positions and exact round-trip, which general libraries do not promise. The
subset is specified in the `document-model` spec, so "not canonical" has a definition.

As built (task 9):

- `model` reads no markdown. `Chapter` and `Skill` hold the files, parse each once and say
  where a finding is; every structure is read from `Doc` and the chapter layer. The line-wise
  readers the layer had shadowed since 2.3 are deleted with their types (`model.Rule`,
  `LintRow`, `Rename`, `RenameTable`, `prose_lines`, `unfenced`, `_section`, `_rows`), and
  `model.py` is 478 lines where it was 798.
- An example is a fence of the tree, nested ones included (none ships), under the rule
  `chapter.owned` puts it in: a rule runs from its `###` heading to the next heading of a rule,
  a section or the title. The line-wise readers carried the last rule on into the next
  section's heading and lead; on the shipped tree that changed no example's rule and no
  finding. `Block.rule` is a `RuleId`, None under no rule.
- A standard's own prose rules read each top-level block as printed, outside the paragraph a
  `**Check:**` label opens. That paragraph, not the whole Check part, is what the line-wise
  reader exempted; the part would exempt about 650 more lines (the tables after a Check in the
  migration chapters) and could only hide findings.
- `Quote.lazy`, like `Fence.closed`, records what printing changes and a check reports: a line
  straight after a quote's last `>` line. `prose` reads it there, so a `>` line inside an
  example is no longer a quote.
- `layout` finds rule titles and contents entries in the tree (`doc.entry`, the one reader of
  `ID [T] title`, which the chapter layer uses too); `documented` reads the README's table as a
  table, so a row inside an example is not one; `frontmatter` reads `Doc.frontmatter`;
  `fmt.put_back` finds a block's fence in the tree by its line and prints the file.
- `dialect.wrapped` is deleted with its control. The tree reads a code span as one word, so a
  Check is read with its command on one line and the branch could not fire; a file holding a
  wrapped span is not canonical, which `layout` reports and `fmt` joins.

### 2. Paragraph filling has one implementation

`wrap(words, width)` is greedy fill at `WIDTH`, defined once. `text.reflow` (push-forward) and
`shared.wrap` (`textwrap.fill`) are both deleted. A paragraph's canonical form is the greedy fill of
its words, which is what makes `revise ∘ revise⁻¹ = id` hold byte-for-byte: renaming an ID changes
token lengths, and re-filling with the same function in both directions restores the original.

Inline code spans, links and hard breaks are atoms the filler never splits. The only exemption is a
line that cannot fit even alone (a long `rg` command in backticks); it is emitted on its own line,
and `layout` keeps reporting it as a note, as today.

### 3. One type per concept

| Concept | Type | Replaces |
|---|---|---|
| Rule ID | `RuleId(standard, family, number)`, ordered, `str()` zero-pads to two digits | 34 regexes; core rules as `tuple[str, str, str]` |
| Tier | `Tier` enum `M`, `M_BANG`, `S`; printed `[M]`, `[M!]`, `[S]` | `"M"` vs `"[M]"` |
| Location | `Location(skill, file, line, rule)` with all fields optional | 8 string shapes, 19 hand-written f-strings |
| Version | `Version` with release-candidate ordering | `_sort_key`, `_minor`, `RELEASE`, anatomy's ad hoc pattern |
| Pin | `Pin(tool, version, exact: bool)` | the uv key parsed twice, `Crate.rust_version`, `ZIG_VERSION`, a Bevy dependency string |
| Answer | `Answered[T] \| NoAnswer(reason)` | `None` and `""` with opposite meanings |
| Branch | `Branch(check, name)` | nothing: findings carry no origin today |

Suffixed IDs (`PS-DATA-17a`) are dropped: none exist in the data, and supporting them in one place
and not another is how the rename-table defect arose.

As built (task 9), the rest of the second spellings went into `ids`:

- `Version.try_parse`, `Version.search` (the first version among other words, as a tool's
  `--version` line names its own), `Version.series` (a pin's major.minor, which a title and a
  rename table name; `Profile.target`) and `releases` (a release prose names, from anatomy's
  `release_token`). `pins._sort_key`, `shared.major_minor`, Rust's `_minor`, Python's `RELEASE`
  and the harness's two version regexes are gone.
- `Version.released` is what a pin is compared with: three numbers and at most a stage, as
  `_sort_key` read. `Version` orders `15.2` before `15.2.0`, so an index answering at a coarser
  precision would have read as older than the pin; that is the one comparison that must never
  pass for agreement, so it is no answer instead. A `uv python list` key is read by its parts,
  `implementation-release+build-os-arch-libc` (`lang.python.listed`), and its release text by
  `Version.released`.
- A rename table's ranges have one parser and one printer, `ranges` and `print_range`, beside
  `DASH`; `cited_at` gives where a citation ends, for `prose` to read what follows it; a family
  count in the reference map is matched with `ids.FAMILY`.
- `tests/test_one_spelling.py` reads every module as source and fails on a literal that spells a
  concept outside its home: a rule-ID pattern or a version parser outside `ids`, a fence or a
  heading found by its text at a line's start, or a `WIDTH` assignment, outside `doc`.
  Composing from `rule_id()` is allowed for the three citation patterns in `anatomy` and only
  those, which the test holds as a set. Over the source at the baseline it reports 83 sites.
- Not done: a profile's maps still key rules by their printed ID (`exempt`, `not_decisive`,
  `fires`, `unproven`, `unless_own`); `self-application` and `crossref` print a hit list's
  `chapter:line [rule]` by hand inside a finding's message.

### 4. A check is `Tree → Iterable[Finding]`

```python
type Check = Callable[[Tree], Iterable[Finding]]


@dataclass(frozen=True, slots=True)
class Finding:
    level: Level
    message: str
    where: Location
    branch: Branch
```

A per-skill check is written as `Skill → Iterable[Finding]` and lifted by `per_skill`, which is
the only place the two shapes meet. `scope="all"` disappears as a string.

`check --skill X` runs every check over the whole tree and keeps the findings whose
`where.skill` is `X` or `None`. A cross-skill check therefore always sees its siblings. This is the
structural fix for the L0 symptom (`crossref` vacuous under `--skill`).

The intermediate forms — `(message, where)`, `(LintRow | None, message)`, pins' `Verdict` with a
constructor function as its level — are replaced by `Finding` at the point of creation.

### 5. Controls are a bijection onto branches

Every finding site names its branch, and every branch is declared with the one level it reports
at: `declare(check, name, level)` records it, and a `Finding` at another level than its branch's is
refused. A `Control(branch, inject)` asserts that a FAIL with exactly that branch is produced. One
test asserts, over every module of the harness imported:

```
{c.branch for c in CONTROLS} ∪ EXEMPT == {b declared at FAIL by a registered check}
```

and that the two sides are disjoint and each control's branch is its own, so no branch is both
controlled and exempt and none has two controls. A control that fires through a different branch
fails, which is what `BRANCHES` and the monkeypatching approximate today for 17 of 65 controls.

The domain is the branches that can fail a run. A branch at `UNRUN` withholds the pass for a tool
that is not there, so its control is the absent tool: `test_unrun` asserts that each one fires with
some declared tool made absent, or is listed with the reason no absence reaches it. A branch at
`NOTE` never fails a run and is outside both. `fmt` declares branches too and is a command, not a
check, so they are outside as well.

A control passes only when its branch fires. Another branch of the same check firing beside it
fails the control unless the control's `also` names that branch with why the defect cannot help
reaching it; injections that reach one branch are preferred. An exemption names its branch and its
reason; reasons are shared constants (a newer release upstream, another installed tool, a value
the harness or a profile declares rather than the tree, a branch of `toolchain` or `mutation`, a
branch of `controls` itself), and every exempt branch is still listed by name.

`inject` returns the paths it edited, so the runner scopes per-skill checks without a module-level
list, and controls run concurrently in a thread pool. The `controls` check and the pytest
parametrisation call the same function; there is one runner. It also holds a per-skill check to
reporting only in the skills it read, which a test used to do beside it.

### 6. A toolchain is an extract/restore pair

```python
class Toolchain(Protocol):
    def extract(self, skill: Skill) -> Extraction: ...  # units carry their source Block
    def restore(self, ex: Extraction) -> Mapping[Block, str]: ...
    def steps(self, unit: Unit) -> Sequence[Step]: ...  # compile, test, format
    def mutants(self, unit: Unit) -> Iterable[Mutant]: ...
```

`restore ∘ extract` is the identity on block bodies, property-tested. One driver runs `steps` with
one policy: a timeout or a failed step is a FAIL with the step's name and the tool's first error
line; a mutant that times out is inconclusive, never killed. `fmt` is `restore ∘ format ∘ extract`
for every language, so Zig gains `zig fmt` write-back without code of its own.

`Unit.path` is a file for every language. Rust compiles a crate of modules; its unit is the module
file, and the crate is the extraction's build context, not the unit.

As built (task 7):

```python
class Toolchain(Protocol):
    language: Language  # + statements, kept: the mutant grammar's vocabulary
    mutant_timeout: float
    outside: re.Pattern[str] | None  # what a block may not reach, or nothing asked

    def extract(self, skill: Skill, out: Path) -> Extraction: ...  # Unit(path, block)
    def restore(self, ex: Extraction) -> Mapping[Block, str]: ...
    def steps(self, ex: Extraction) -> Iterable[Step]: ...  # compile, lint, test
    def formatter(self, ex: Extraction) -> Step: ...  # write mode
    def tests(self, ex: Extraction, unit: Unit) -> Step | None: ...
```

- `steps` takes the extraction, not a unit: a crate builds whole, and `ty` and `ruff` read a
  directory. A `Step` is data (`name`, `cmd`, `cwd`, `timeout`, `env`, the `unit` it runs or none,
  whether the tool prints `path:line:col:` lines, how to read what it said first), so the policy
  of running one is stated once, in `lang.judged`; `checks.toolchain` is the only code that runs
  one. The format step is `formatter` rather than one of `steps`: the check runs it in write mode,
  restores, and compares, and `fmt` runs the same three and writes the bodies back.
- `mutants` is not the toolchain's. One grammar, `lang.deletable`: a line holding one whole
  statement, outside the block's tests, that no word the language keeps opens (a declaration or
  binding, whose deletion only stops the build; an assertion; a brace). Each `Language` supplies
  the vocabulary: `statements` reads Python's with `ast`, and Rust and Zig share `terminated` (code
  ending in `;`, brackets balanced on the line); `tests` gains Rust's (`#[cfg(test)]`, `#[test]`).
  There were three: Python mutated only lines holding `=`, its tests' lines included; Rust only
  what came before a module's first `#[cfg(test)]`, assertions included; Zig skipped a statement a
  comment followed.
- A unit is a file holding one block whose line `i` is the body's: the harness writes after a body,
  never before it (Zig's analysis trailer follows a `SENTINEL` comment `restore` cuts at). Rust's
  unit is `src/<chapter>/<rule>.rs`, the block at column zero with `crate::` and `mycrate::`
  rebased by `rebase`, which `unrebase` inverts; `lib.rs` and the chapter files are the build
  context and carry `#![allow(dead_code, unused_imports)]` once, at the root. At column zero
  rustfmt judges the block a reader pastes; inside a `pub mod` it broke lines four columns early,
  and three blocks carried such a wrap (`16049c9`).
- `verified` blocks in `SKILL.md` are compiled in every language (`lang.extracted`). Rust named a
  module after its block's rule and skipped a block under none; it is now `block` in module
  `skill`. No Rust or Bevy block stands there today; Zig's one compiles as before.
- One policy: a step that times out is `<step> did not finish in Ns`; one that exits 0 in its time
  passed, whatever it printed; one that failed is a finding at each line of a unit its tool names,
  in markdown coordinates (cargo is asked for `--message-format=short`), and otherwise `<step>:
  <first error line>` at the unit or the skill. A unit's steps stop at its first failure; a step
  over the whole extraction always runs. Python's blocks are held to `ruff format` now, as Rust's
  and Zig's were to theirs. The unmutated tests run once per command; their failure or timeout is a
  FAIL in every language, where Python and Zig skipped the unit in silence. A mutant that times out
  is inconclusive; its timeout is the toolchain's (`mutant_timeout`), as each step's is.
- A surviving mutant is a **note** in every language, and is run twice first. Rust's failed;
  Python's and Zig's were notes, and only theirs said why: an illustrative example's test pins the
  case its name describes, and a guard outside that case is expected to survive. The shipped
  survivors bear it out — eight of the nine before this task were guard clauses or error exits
  outside the case the test is named for (`fatal("unrecognized flag…")`, `if (text.len == 0)
  return error.Invalid;`), and the ninth a line of a test. No mechanical rule tells such a guard
  from a test that cannot fail, and failing both would make every example's tests exhaustive over
  its statements, which the standards' rules on what an example shows argue against. Rust's FAIL
  was not argued; its second opinion, which kept a transient from failing a run, is now every
  language's. The check still fails on what it can decide — unmutated tests that fail or hang — and
  a survivor is reported at its markdown line for a reader to judge. No Rust or Bevy block had a
  survivor before or after, so no finding changed level.
- The 28 branches of `toolchain` and `mutation`, 24 of them declared per language, are 12, all the
  driver's; `COMPILES` exemptions 20 → 7 (35 → 22 in all), controls unchanged at 175. `fmt`'s
  `cargo_fmt`, `ruff_format` and `modules` are `formatter` and `formatter_timeout`, and `put_back`
  finds a block by its line rather than its text, so two blocks with one body are no longer skipped.

### 7. A profile is a record

Profiles become frozen dataclass literals in one module, collected in one mapping, with no import
side effects. Fields that are code today become data interpreted by one engine:

- conventions and prose rules → `LineRule(rule, pattern, message, scope, unless_own)`;
- toolchain configuration → `RustCrate | PythonSnippet | ZigBuild`;
- the delta anchor (`delta_of: str | None`), mirror pairs, sensitivity fixtures, compiler probes,
  `not_decisive`, the unproven-pattern set from L0.

A test asserts that no module outside `profiles/` and `lang/` contains a skill name or a toolchain
name as a string literal.

As built (task 6):

- The record types are in `profiles.record`, each profile is a `PROFILE` literal in its standard's
  module, and `profiles.PROFILES` is the one mapping. A branch is still declared where its rule is
  stated, so importing a profile declares branches and registers nothing else.
- A `LineRule` is `(branch, pattern, message, comments, unless_own, unless, needs)`. Its scope is
  the profile field it sits in, `conventions` or `prose`, not a field of its own; `branch` takes the
  place of `rule`, since the branch names the check and the level; `unless_own` is the rule ID whose
  own example or own prose shows the forbidden spelling on purpose. What excuses a hit, or must sit
  beside it, is a `Near(pattern, above, below, stop, own)`, gathered with `outside_tests` in an
  `Unless`; `self-application`'s exemptions are `Unless` records too, so one vocabulary says what a
  rule permits wherever its pattern runs. `checks.lines` is the one reader.
- A branch reports a line once, at its leftmost hit, so a rule stated as two patterns behaves as the
  alternation it was.
- A rule that reads an example's structure rather than its lines stays a function of one block,
  named in its profile's module and listed in `structural`. Four are left: Bevy's component shape
  and type suffixes, Rust's unreachable `Default`, Zig's import order.
- The toolchain configuration is `PythonSnippet | RustCrate | ZigBuild`, and `lang.toolchain_for`
  dispatches on its type. Every pin in it is a `Pin`; decision 3's `Pin` gains the operators the
  files it is copied into spell (`==`, `>=`, Cargo's `=`, `uv`'s `-`) and `Version` PEP 440's local
  label, so `cpython-3.15.2+freethreaded` and `bevy=0.20.1` are one type with `ruff==0.17.3`. A
  library is a `Library(pin, features)` that refuses an inexact pin, and a delta is one
  `Delta(anchor, step)`, so neither can be declared by halves. `Profile.subject` names what a
  standard is about when that is not its toolchain's release; `pin` and `release` are derived.
- What a check knew about one toolchain is that toolchain's: `Toolchain.cite`, `.pins`, `.asset`
  and `.format` (task 7 made the last a `formatter` step, and moved the steps' branches to the
  driver), with the branches they report through declared in `lang/` under the check's name,
  as the toolchain's own steps then were, and the tools each asks for (`needs`, `cites_with`,
  `pins_with`, `assets_with`) read by the checks for their `needs`. A `Language` record per
  toolchain holds the comment token, string quotes, file suffix and test reader.
- The harness's own tool pins are one `Harness` record in `harness.py`, read from `pyproject.toml`.
- The test reads the names off `PROFILES`: each skill's name, and each toolchain's name and fence. A
  literal equal to a toolchain's name fails even where it is a binary (`zig`), which is why the
  code that runs `zig` on a probe or a shipped `build.zig` lives in `lang.zig`; a skill's name fails
  anywhere in a literal, as a path's first part too. Docstrings and comments are not read.
- Every standard other than the anchor declares the standard it is mirrored against, those with no
  pairs as well, since an unheld pair is noted in any of them.
- A branch that fired only on a declaration is a test over the records (`tests/test_profiles.py`)
  and is gone; three are impossible by type besides.

### 8. `revise` is one operation with laws

```python
type Becomes = RuleId | LintRow | Removed     # Removed carries its reason
type Plan = Mapping[RuleId, Becomes]

def revise(tree: Tree, plan: Plan, chapters: Mapping[str, str] = {}) -> Tree
```

1. Apply the plan: drop removed and demoted rules, add lint rows, record merges.
2. Close by dense renumbering: σ maps the surviving IDs of each family, in order, onto 1..n.
3. Refuse if any cited ID that names no rule before the revision is in σ's image — the L0 defect
   rebinding a dangling citation, now impossible by construction.
4. Apply σ and the plan's redirections to every ID token in the tree, including the harness's own
   sources and README, and re-print.
5. Append the composition to `references/renames.md`.

Laws, property-tested on generated plans over the shipped skills:

- `revise(revise(t, σ), σ⁻¹) == t` byte-for-byte when σ is a pure renumbering or chapter rename.
- `revise(t, {}) == t` (an empty plan writes nothing and reports nothing).
- Every ID cited before the revision either names the same rule title after it, or is listed in
  `renames.md` with what it became.

`renumber` and `demote` remain as thin CLI aliases.

As built (task 8):

```python
type Becomes = RuleId | LintRow | Removed
type Plan = Mapping[RuleId, Becomes]


def revise(
    tree: Tree, plan: Plan | None = None, chapters: Mapping[str, str] | None = None
) -> Revision: ...  # moves, writes, renamed, leftovers; .apply() writes
```

- `revise` is pure and returns a `Revision`; `Revision.apply()` moves and writes. A `Tree` reads
  from disk, so there was no tree to return, and a dry run and the run that writes are one
  computation. `revise(t, {})` is the identity as `Revision.empty`: nothing moved, written or
  reported.
- A plan's `LintRow` is the whole row, since a demotion may add it to its chapter's `Decided by
  tools`; the rename table records its key, `chapter.Demoted`, which is all a cell says.
  `print_becomes` is the cell's printer beside `parse_becomes`, its parser. A row the standard lists
  already must be the row listed, level and forbids. A demotion becomes one row: a plan file's
  `rows` holds exactly one, and a second lint is a row added by hand, which renames nothing.
- Every standard in `tree` is renumbered; `chapters` renames a chapter by stem in every standard of
  the tree that has it, as the vocabulary means a name. The command line passes a tree of one skill;
  the rewrite reaches the repository the tree sits in.
- The plan is applied on the chapter layer: a rule leaves with its contents entry, a section left
  with nothing goes with its contents label, and a row joins or starts `Decided by tools`. σ maps
  each family's kept rules, in order, onto 1..n under the (renamed) chapter's code. σ is the
  identity on `CORE`: core rules are `SKILL.md`'s, no revision renumbered them, and `ZS-CORE-01b`
  ships, so closing that family would rewrite zig-style on every revision.
- Two refusals, both before anything is composed: a citation, outside the standard's own history,
  of a rule the plan removes or demotes, which would name nothing or the next rule down — the
  two-step `demote` wrote and reported it, so `demote` now asks for it to be resolved first; and
  L0's capture. A merge redirects its citations to the rule it went into.
- One rewrite: `ids.respell` (an ID, or a family alone, on the one pattern) and chapter paths. A
  standard's markdown goes through its tree, its own history kept and the file printed
  canonically when it changed; another standard's file is parsed only if its text changes; `src/`,
  `tests/` and the README are text. Then `renames.md` is composed — every table carried, the
  current revision's started if an ID changed, from every chapter rule before, an inserted `-02a`
  included — and every kept rule's title is read back under its new ID from the text to be
  written.
- `apply` moves through a name of its own first: chapters that swap names are a permutation, like
  any renumbering, and landed on each other.
- Laws, `tests/test_revise_laws.py`, on copies of the standards, `src/`, `tests/` and README, seeded
  and sampled, about eleven seconds: a renaming (a rename, a swap, a cycle) and its inverse restore
  every byte; an empty plan over all four standards writes and reports nothing; after a plan of
  merges, a removal and a demotion every citation names the rule with its title, or its merge's,
  and every original in the rename table goes where the plan sent it; a citation a renaming or a
  hand-made gap would hand to a rule stops the run with nothing written. Renaming `errors` or
  `testing` was outside the first law: the shared how-to-use passage illustrated with
  `{prefix}-ERR-03` and `{prefix}-TEST-05`, `shared.rewrite` restored them after the rename, and
  the inverse refused them as captures — rightly.
- Task 9 made it a law like the others. A slot deriving the examples from the skill (the first
  rule of each of the first two chapters its map lists) survived a renaming, and failed the
  next test: a rule a template cites is cited in every standard, so `revise` refused to remove
  it while `fmt` kept writing it back. Any concrete ID there has that flaw, so the passage cites
  none — `Rules are cited by ID: {prefix}-, then the family of the chapter that owns the rule,
  then its number` — and a test holds every template to citing no rule. The law test renames
  `errors` and `testing` and back in python-style and zig-style, and fails on the old template.

### 9. ID history moves to `references/renames.md`

The rename tables are 78% of rust-style's `migration.md` and are loaded on every migration lookup.
They move, unchanged in content, to `references/renames.md` in each skill. `migration.md` names
the file once; SKILL.md does not. `skeleton` follows the table to its new home. The file is shipped,
so a reader holding an old ID can still resolve it, but nothing on the reading path loads it.

As built (task 8.3):

- `renames.md` is `# Renamed Rule IDs`, a scope paragraph (`revise.SCOPE`), then each table's
  section byte for byte as it stood in `migration.md`. `migration.md` ends its scope with
  `revise.NAMED`, the sentence `revise` writes when it opens the file; rust-style's scope and
  reference map stop claiming the table, and the shared how-to-use passage says the migration
  chapter names the file that maps every old ID. 871 fenced examples identical before and after.
- `renames.md` is in `vocabulary.UNCODED` with the review protocol: a file under `references/`
  that owns no rules, so it has no code and `allowed` admits it. It is not `REQUIRED`: a standard
  no revision renumbered has none. A separate allowance — keeping it out of `Skill.chapters` — was
  rejected: `layout` holds it canonical, and `anatomy` checks the files its cells name, as for any
  file there; `assets` and the reference-map counts needed nothing.
- `skeleton` reads rename tables there and only there, and fails on one anywhere else
  (`rename_elsewhere`), on a migration chapter that names `renames.md` other than once
  (`renames_named`), and on a `SKILL.md` that names it (`renames_on_path`), each with a control:
  FAIL branches 197 → 200, controls 175 → 178, exemptions 22. The `unread` control refuses
  `renames.md` and `required_chapter` removes the review protocol, since a refused or missing
  migration chapter now strands rename rows as well.

## Risks / Trade-offs

- **A rewrite of most of the harness at once** → staged so the suite is green after every stage:
  the tree and types land first behind the existing checks (old code reads the new tree through
  adapters), then checks move one at a time, then the adapters go. Each stage is one commit range
  with the full suite passing.
- **Canonical re-printing touches every skill file** → it happens in one commit that contains
  nothing else, and the commit is verified to change whitespace and order only:
  `parse(old) == parse(new)` modulo the documented normalisations.
- **The branch bijection will expose branches with no control** → expected; each gets a control or
  an exemption with its reason in the same change. The number is reported, not hidden.
- **Property tests on the shipped corpus are slow** → generated trees cover the laws; the corpus
  round-trip runs once per file, which is fast.

## Migration Plan

1. Land `doc` and the typed values with round-trip tests; no check uses them yet.
2. Re-print the skills canonically in one commit; verify the tree is unchanged.
3. Move `layout`, `shared-text`, `skeleton` and `anatomy` onto the tree; delete their scanners.
4. Introduce `Finding.branch` and `Location`; convert every check; introduce `per_skill` and
   post-filtering for `--skill`.
5. Convert controls to the bijection; add missing controls or exemptions.
6. Convert profiles to records and the line-rule engine; remove skill names from generic code.
7. Convert `lang/` to extract/restore with one driver; derive `fmt`.
8. Implement `revise`; move rename tables to `renames.md`; alias `renumber`/`demote`.
9. Delete every superseded parser, regex and helper; verify no second spelling survives
   (a test greps `src/` for rule-ID regex literals outside `ids.py`).

Rollback is per stage: each stage is a contiguous range of commits on the branch.

## Open Questions

- ~~Whether `Location.line` should be the markdown line or the extracted line for toolchain
  findings.~~ Resolved by task 7: the markdown line, for every toolchain and every finding — a
  diagnostic, a survivor, an inconclusive mutant. No source map was needed: a unit is a file of
  one block whose line `i` is the body's line `i`, Rust's included now that each block is its own
  module file at column zero, so `Unit.where_at(i)` is `Block.where_at(i)`. A line past the body
  (the harness's own) is placed at the block.
