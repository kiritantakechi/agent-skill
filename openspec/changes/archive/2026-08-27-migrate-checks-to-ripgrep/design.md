## Context

See `proposal.md` — Why. Three facts about the current state shape the approach:

- **The engine shells out to whatever `grep` the host provides.** On the development machine that
  binary is **`ugrep 7.8.4`**, not GNU grep. The dialect a pattern is read in is therefore not a
  property of this repository at all; it is a property of the environment, and nothing pins it or
  reports it.
- **The corpus is a synthesized flat file.** `Corpus.build` concatenates every advisory example into
  `raw.txt` and `code.txt` and greps those. Directory traversal semantics — hidden files, ignore
  files, binary detection — do not affect the engine at all. They affect only the reader who copies
  a Check and runs it on a real tree.
- **144 command-form Checks exist**: 83 BRE, 61 ERE, the split determined by whether the author
  happened to type `-E`.

## Goals / Non-Goals

**Goals**

- One dialect, supplied by one pinned binary, for all four skills.
- A migration whose correctness is *demonstrated* rather than reviewed.
- Remove the `grep`/BRE failure class structurally, not by discipline.

**Non-Goals**

- `--multiline-dotall`. `-U` is enabled; the dotall switch is not. See Decision 7.
- Rewriting the 247 prose-form Checks ("grep for `X`") into commands. Different work, different
  change; touching them here would mean the equality argument no longer covers everything that moved.
- Changing which rules have checks, or what any check means.
- Writing new multi-line patterns. `-U` is switched on and the engine is rebuilt to support it; the
  rules that exploit it come later, once there is a mechanism to write them against.

## Decisions

### 1. `rg`, not `grep -E` everywhere

The cheaper alternative is real and worth naming: adding `-E` to the 83 BRE commands would achieve
dialect uniformity with no new dependency and a far smaller diff.

It was rejected because it fixes the symptom. `grep -E` leaves three things standing: the engine
still depends on an unpinned binary whose identity varies by host (here, ugrep); `grep -F` and the
`-F` retry keep a second grammar in the code; and BRE remains one forgotten flag away, so the defect
class is avoided by discipline rather than removed. `rg` has no BRE mode to fall back into, and
`ripgrep-bin` is on PyPI at the exact version verified here — so the tool becomes pinnable by the
same mechanism that already pins `ruff` and `ty`.

### 2. The `-F` retry is deleted, not ported

Today `hits()` retries a rejected pattern as `-F`. That retry exists because two grammars are in
play and the engine cannot tell which one a pattern was written for. Under one dialect the retry has
no meaning left: a pattern `rg` rejects is a defect in the pattern, and the spec requires it to be
reported as a failure rather than silently re-run as something else.

Removing it is the point rather than a side effect. A retry that turns a broken regex into a literal
string is precisely the mechanism by which a check stops being able to fire while still reporting.

### 3. `Pattern.mode` collapses from three values to two

`-G` disappears. What remains is a genuine distinction, not a dialect one:

| Source | Mode | Why |
|---|---|---|
| Pattern quoted in a Check's command | `rg` default regex | It is a regex; the author wrote it as one |
| Backticked span in Check prose | `rg -F` | It is literal source text the reader is told to look for |

The prose case stays fixed-string. Compiling those as regexes is what once turned `|x| f(x)` into an
alternation matching every line; that history is in `selfapply.py`'s docstring and the fix should
survive the migration.

### 4. `ripgrep-bin` is pinned exactly, like every other deciding tool

`ripgrep-bin==15.2.0` joins the `dev` group. The repository's rule is that a tool which decides
whether the build passes is pinned exactly and its bump is a reviewed change; `rg` now decides
whether 144 checks fire, so it qualifies. This also ends the situation where the engine's behaviour
depends on which `grep` the host installed.

### 5. The corpus becomes one file per example block

`Corpus.build` concatenates every advisory example into `raw.txt` and `code.txt` and keeps a parallel
`index` array to map a line number back to its file, rule, and original line. Under `-U` that design
is not merely awkward, it is wrong. Measured:

```
corpus:  try:            ← example A
             a()
         # unrelated example boundary
         finally:        ← example B

rg -U 'try:(?s).*?finally:'  →  1 match, spanning both examples
```

A pattern matched a `try:` in one example against a `finally:` in another. Nothing in either example
is defective; the hit exists only because the two were pasted together.

Writing each block to its own file removes the failure structurally rather than by escaping or
sentinel lines — a pattern cannot cross a file boundary, and no sentinel survives `(?s).*`. It is
also the more native shape: `rg` is a directory searcher, `--json` reports `path` per match, line
numbers become block-local, and the `index` array disappears along with the class of off-by-one bugs
that comes with maintaining a parallel array.

Verified: with the blocks in separate files, the same pattern matches zero times.

### 6. Results are read from `--json`, and a hit becomes a span

Parsing `-n` output means splitting on `:` and hoping no matched line contains one. `rg --json` is
an event stream that carries what the engine actually needs:

```
{"type":"match","data":{"path":…,"line_number":2,"absolute_offset":9,
                        "lines":{"text":"    try:\n        go()\n    finally:\n"},
                        "submatches":[{"start":4,"end":34,…}]}}
```

Note `lines.text`: under `-U` the match is a **region**, and `line_number` is only where it started.
The current model — a hit is an `int` — cannot express that, and every consumer of hits inherits the
problem. So the hit becomes a span.

This is the change that reaches furthest into existing code. `exempt` hooks are called as
`exempt(source, n - 1, in_test)` with a line index; they become span-aware. That signature change is
the "完全重构旧逻辑" part in practice: the line-number model is grep's model, and it does not survive
contact with multi-line matching.

`-F` composes with both `-U` and `--json`, verified, so prose spans need no special path.

### 7. `-U` on, `--multiline-dotall` off

The original plan excluded `-U` on the grounds that it would make hit-set equality unprovable. That
reasoning was wrong, and measuring it is what showed so:

| pattern | line mode | `-U` |
|---|---|---|
| `^    beta` | 1 | 1 |
| `alpha$` | 1 | 1 |
| `alpha.beta` (across a newline) | 0 | **0** |
| `alpha.*beta` with `--multiline-dotall` | 0 | **1** |

`rg` keeps `^` and `$` line-anchored under `-U`, and `.` still stops at a newline. `--multiline-dotall`
would change what existing patterns mean, so it stays off and a pattern that intends to span lines
opts in with an inline `(?s)`.

**A first version of this decision concluded from that table that `-U` is "inert for every
single-line pattern, all 144 of them". That is wrong, and the table is why: it tests `.`, `^` and
`$` and nothing else.** `.` excludes newline; `\s`, `\W`, `\D` and any negated class do not.
Measured, over four lines where three are indented `if`s:

```
grep -E '^\s+if'   3 matches
rg    '^\s+if'     3 matches
rg -U '^\s+if'     1 match, spanning all three lines — `\s+` ate the newlines
```

Sixteen of the 137 command patterns (11%) contain such a class. Under `-U` they merge adjacent hits
into one span, which changes both the reported location and the hit *count* — and the count decides
tiering, so a pattern that belongs in tier 3 can fall under `judgement` and be reported as a tier-1
failure.

Those sixteen are narrowed to `[ \t]` rather than left alone or special-cased. In every one of them
`\s` was written to mean horizontal whitespace — `^\s+import` is an indented import, not an import
several lines below something. Narrowing states the intent that was always there, and it keeps a
single execution mode: an engine that decides per pattern whether to pass `-U` would reintroduce
exactly the two-modes-in-one-tree split this change exists to remove.

### 8. Every invocation passes `--no-config`

`rg` reads `RIPGREP_CONFIG_PATH` if it is set. Verified: a config containing `-i` turned a pattern
that should not match into one that did. Verification results would then depend on whose machine ran
them.

This is a hazard `grep` did not have, introduced by the move — and it would undercut the very
argument for the move, which is that the current engine's behaviour depends on which binary the host
provides. Pinning the version and then letting the host's config change the semantics would fix half
the problem. `--no-config` on every invocation fixes the other half.

### 9. Translation is mechanical, guarded by a syntactic check; equality covers what it can

An earlier version of this decision claimed hit-set equality was "the only mechanism that can catch
the failure this migration risks". Implementation disproved it. The harness was built, it reproduced
the present exactly across 670 patterns, and then an untranslated BRE alternation was injected on
purpose — and it passed.

The reason is structural, not a bug in the harness:

| | patterns | empty hit set |
|---|---:|---:|
| all patterns | 670 | 492 (73%) |
| command patterns | 137 | 97 (70%) |

`selfapply` requires tier 1 to be empty — a decisive pattern **must not** match the standard's own
compliant examples. So the patterns most in need of protection are exactly the ones whose hit set is
empty before and after, and empty equals empty is indistinguishable from a pattern that has silently
stopped being able to match anything. The BAD-example corpus that might have carried counter-matches
is 14 blocks in total; it cannot close the gap.

So the guarantee is rebuilt on two legs that do not depend on matching:

**The translation is performed by code, not by hand.** BRE→ERE is a small total transformation:
`\(`→`(`, `\)`→`)`, `\|`→`|`, `\{`→`{`, `\}`→`}`, and the bare forms escaped in the other direction.
Writing it as a function replaces "did a person translate 83 patterns correctly" — unverifiable for
70% of them — with "is this function correct", which is exhaustively unit-testable against known
BRE/ERE pairs.

**A permanent check forbids BRE-only escapes in an `rg` pattern.** `\|`, `\(`, `\{` are literal
characters to any modern engine. Their presence in a pattern that will be run by `rg` is decidable
by looking at the pattern — no corpus, no matching, no execution. This is what actually catches the
silent class, and unlike the equivalence harness it survives the migration and stops the defect
being reintroduced.

Hit-set equality is kept, demoted to what it honestly is: a check over the 30% of patterns that
match something, useful and not sufficient. It remains a **migration instrument** — it compares
against a spelling that will not exist afterwards — and is deleted with the migration.

### 10. `Corpus` has two consumers, and it is built twice

`crossref.py` imports `Corpus` and `patterns_of` from `selfapply` and reads `corpus.index[…]`
directly, to run one standard's decisive patterns over a sibling's examples. Deleting the `index`
array — Decision 5 — breaks it, and breaks it silently, because `crossref` would still run and still
find hits; only their attribution would be wrong.

The two also build the corpus independently. Today that is 2 files per skill per consumer, 16 writes
in total, and unnoticeable. After the split it is **604 blocks written twice — 1208 files per run**.

So the corpus becomes a per-skill artefact constructed once and handed to both. This is not
optimisation for its own sake: it is what makes the split affordable, and it removes the second copy
of the "make a temp dir, build a corpus, remember to check `blocks`" dance, which is the kind of
duplication that lets two call sites drift apart.

### 11. Two tool-missing paths report the level that does not block

`Result.ok` is `not self.fails and not self.unrun`. `NOTE` does not withhold the pass; `UNRUN`
exists precisely so that "nobody looked" is distinguishable from "nothing was wrong".

`citations`, `pins`, and `toolchain` all use `unrun` when a tool is absent. `assets.py` uses `note`
in both of its tool-missing paths — `_zig` when `zig` is not on `PATH`, and `_build` when `uv` is
not. On a machine without `zig`, the run reports **ALL CHECKS PASSED** while nothing parsed the
shipped `build.zig`; without `uv`, while nothing built the shipped `pyproject.toml`.

This is unrelated to the `rg` migration and is fixable today, independent of it. It is recorded here
because it is the same defect class the migration is built to avoid — a check that did not run
looking exactly like a check that passed — and because the `_build` path was added by the change
that introduced asset building, with a comment citing `_zig` as its precedent. The precedent was
wrong, so the copy inherited it.

### 12. Traversal semantics are a reader-facing change, and the assertion does not cover them

`rg` and `grep` disagree about what to search before any pattern is applied:

```
tree: .github/ci.yml, target/x.yml, .gitignore(→target/)

command grep -rn 'X' .    → both files
rg -n 'X' .               → target/x.yml only   (.github skipped: hidden)
rg -n --hidden … 'X' .    → both files
```

`rg` skips hidden files and directories by default, and inside a git repository it also honours
ignore files. The engine is unaffected — its corpus is one flat file — so **hit-set equality proves
the pattern translated correctly and proves nothing about the command**.

The decision: Checks name their paths explicitly rather than relying on traversal defaults. An
explicit path argument overrides the hidden-file rule, so `rg 'PYTHON_GIL' .github/` works
unchanged, and this is already how the affected checks are written. Only a Check that searches a
bare `.` and genuinely needs ignored or hidden files gets explicit flags, and each such case is
decided individually rather than by blanket-adding `--hidden --no-ignore`, which would make every
check also search `node_modules` and `target`.

### What the equivalence harness actually reported

Recorded here because the harness is deleted with this change and the number is
the evidence that the rewrite was faithful.

**668 patterns compared.** Every difference fell into one of two classes, neither
of which is a change in what a pattern matches:

- **Two intended reclassifications.** `'*.c'` and `'*.h'` in `PS-MIG-05` were file
  arguments being read as patterns, because `FILE_ARG` listed Zig, Rust, Python,
  Markdown and TOML but no C sources. Under the old grammar `*.c` was a valid
  expression that matched nothing in particular; under the new one it is a syntax
  error, which is how a latent defect the docstring already warned about —
  "a miss here is not a false negative, it is a build break" — finally surfaced.
- **Line-number shifts inside one file.** Narrowing `\s` to `[ \t]` pushed two
  prose lines past the 100-column limit, and rewrapping them moved every example
  below in `assertions-and-limits.md`. 77 of the reported differences are exactly
  `+1` in that one file, and the rest are the same shift with the comparison's
  naive pairing misaligned.

The harness's own blind spot is recorded in Decision 9 and is why it was never
the whole argument: it cannot see the 70% of command patterns whose hit set is
empty on a compliant corpus. Those rest on the mechanical translator, its
unit-tested table, and the permanent `dialect` check.

## Risks / Trade-offs

- **A pattern is mistranslated and silently stops matching** → the equivalence assertion; this is
  the risk the whole approach is built around.
- **Hit-set equality is proven on the standard's own corpus only** → that corpus is compliant code,
  so equality there does not prove equality on arbitrary code. Accepted: it is the same corpus the
  checks have always been calibrated against, and the alternative is a sensitivity programme that
  does not exist yet for `grep` either.
- **The command a reader runs changes meaning even when the pattern does not** → Decision 6;
  explicit paths, case-by-case flags.
- **`rg` becomes a hard dependency of the harness** → it already effectively was, as `grep`; the
  difference is that the dependency is now named, pinned, and reported when missing.
- **The diff is large and mostly mechanical** → mechanical is what makes the assertion possible;
  a hand-crafted diff of 144 sites is what it protects against.
- **The refactor is not mechanical, and touches the hit model every consumer depends on** → the
  engine migration (Decisions 5, 6) lands and is proven green *before* any pattern is translated, so
  a failure is attributable to one of the two halves rather than to their interaction.
- **Splitting the corpus into files changes what the block count means** → the `blocks`/`excluded`
  bookkeeping and the "nothing to check" guard both read that count; verify the empty-corpus guard
  still fires, since an empty temp directory is exactly what a broken split produces and it would
  otherwise pass every pattern in the library.

## Migration Plan

Order matters, because each step is verified by the one before it still holding:

1. **Pin the tool.** `ripgrep-bin==15.2.0` into `dev`, probe registered, missing-tool path reported.
2. **Build the equivalence harness** against the current tree, while every pattern is still in its
   old spelling. It must reproduce today's hit sets exactly before it is trusted to judge anything.
3. **Split the corpus into per-block files**, still executing with the old tool and no `-U`. Hit sets
   must be unchanged. This is the step that makes `-U` safe, so it lands before `-U` does.
4. **Migrate execution** to `rg` with `--json`, `--no-config`, and `-U`; convert hits to spans;
   delete the `-F` retry; collapse `Pattern.mode`. Still with the old patterns, which remain valid.
5. **Translate the 144 patterns**, one skill at a time, with the assertion green after each.
6. **Strip the word `grep`** from the engine, profiles, `README.md`, and the tests — including the
   `NotDecisive` reasons, which are report text.
7. **Delete the equivalence harness** and record in this document that it passed and on what.

Steps 3 and 4 are deliberately separate. Both change the engine, and either alone is provable by
unchanged hit sets; together they would not be, because a phantom cross-block match and a
mistranslated pattern are indistinguishable in the aggregate.

**Rollback**: steps 1–4 are independently revertible. After step 5 begins, rollback is `git revert`
of the whole change rather than a partial retreat, because a tree with half its patterns in each
dialect is exactly the state this change exists to abolish.
