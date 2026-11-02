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

### 7. A profile is a record

Profiles become frozen dataclass literals in one module, collected in one mapping, with no import
side effects. Fields that are code today become data interpreted by one engine:

- conventions and prose rules → `LineRule(rule, pattern, message, scope, unless_own)`;
- toolchain configuration → `RustCrate | PythonSnippet | ZigBuild`;
- the delta anchor (`delta_of: str | None`), mirror pairs, sensitivity fixtures, compiler probes,
  `not_decisive`, the unproven-pattern set from L0.

A test asserts that no module outside `profiles/` and `lang/` contains a skill name or a toolchain
name as a string literal.

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

### 9. ID history moves to `references/renames.md`

The rename tables are 78% of rust-style's `migration.md` and are loaded on every migration lookup.
They move, unchanged in content, to `references/renames.md` in each skill. `migration.md` names
the file once; SKILL.md does not. `skeleton` follows the table to its new home. The file is shipped,
so a reader holding an old ID can still resolve it, but nothing on the reading path loads it.

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

- Whether `Location.line` should be the markdown line or the extracted line for toolchain findings.
  Decision 6 says markdown everywhere; Rust mutant reports currently use the extracted file and
  need a source map, which `Unit` carrying its `Block` provides.
