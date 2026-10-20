# Documentation: Docstrings, Comments in Public Places, and What Ships

Scope: what a docstring must say and how it is shaped, which convention this standard picks and why,
and the documents that live outside the code. Comment typography and the say-why rule are in the
naming chapter; what a signature must promise is the API chapter.

Two sources are merged here: **PEP 257**, which is normative about docstring shape and deliberately
silent about section format, and the **Google Python Style Guide's section vocabulary**, which is
what `convention = "google"` implements and what the ecosystem largely settled on. Ruff's `D` family
decides the mechanical half — with the caveat that setting a convention *disables* rules, so which
ones apply is a consequence of the choice.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Shape**
  - PS-DOC-01 [M] Open with one imperative line that fits on the line
  - PS-DOC-02 [M] Use triple double quotes, always
- **Content**
  - PS-DOC-03 [M] Say what the caller needs, not what the code does
  - PS-DOC-04 [M] Put the type in the annotation, never in the docstring
  - PS-DOC-05 [M] Document what is raised, and only what the caller can act on
  - PS-DOC-06 [M] Document the cost and the ownership
  - PS-DOC-07 [S] Record the decision that is not visible from the code
- **Convention**
  - PS-DOC-08 [M] Set a docstring convention, and know what the choice disables
  - PS-DOC-09 [M] Never let the docstring and the signature disagree
  - PS-DOC-10 [S] Write examples as doctests, and run them
- **Beyond the code**
  - PS-DOC-11 [M] Give the package a README that answers "what" before "how"
  - PS-DOC-12 [M] Keep a changelog, and write the entry with the change
  - PS-DOC-13 [S] Document the decision, not only the outcome
  - PS-DOC-14 [M] Never document what was checked, only what is true
- Decided by tools

---

## Shape

### PS-DOC-01 [M] Open with one imperative line that fits on the line

`"""Return the parsed configuration."""` — not "Returns", not "This function returns".

**Why:** PEP 257 specifies the imperative mood, and it is not arbitrary: the docstring completes the
sentence "call this to ___", so it instructs the reader rather than describing the function. It
must fit on one line because tooling shows the first line alone in listings.

**Check:** ruff `D200` for the one-line form and `D415` for the closing punctuation. The
imperative mood is a review matter: the pydocstyle rule for it is one of the twelve that
`convention = "google"` switches off, so it is not enabled here.

```python
# verified — GOOD
def load_config(path: str) -> dict[str, str]:
    """Return the configuration at `path`.

    The file is read as UTF-8 regardless of the platform default, so the result
    does not depend on the machine it ran on.
    """
    return {"path": path}


assert load_config("a.toml") == {"path": "a.toml"}
```

### PS-DOC-02 [M] Use triple double quotes, always

`"""..."""`, even for a one-line docstring, even when it contains no quotes.

**Why:** PEP 257 says so, and uniformity means a docstring is recognisable by shape. The rule is
also what makes it safe to add a second line later without changing the delimiter.

**Check:** `D301` is enabled and requires a docstring containing a backslash to be raw. The rule
for the quote style itself sits on ruff's formatter-conflict list and is disabled here — the
formatter settles it instead.

## Content

### PS-DOC-03 [M] Say what the caller needs, not what the code does

The contract, the units, the edge cases, the failure modes. Not a paraphrase of the body.

**Why:** a docstring restating the implementation is a second copy that drifts, and it is worthless
to the caller who cannot see the body anyway. The useful content is exactly what is *not* derivable:
what the units are, what happens on an empty input, whether it retries.

**Check:** read the docstring with the body hidden. If it no longer says anything useful, it was
describing the body.

### PS-DOC-04 [M] Put the type in the annotation, never in the docstring

`path: Path` in the signature. Not `path (Path): ...` in the docstring.

**Why:** two statements of the same fact drift, and only one of them is checked. The annotation is
verified by `ty` on every run; the docstring is verified by nobody. Documentation tooling reads the
annotation, so repeating it also renders twice.

**Check:** `rg -n '^[ \t]+\w+ \([A-Za-z]' src/` inside docstrings — a parenthesised type is the
finding.

### PS-DOC-05 [M] Document what is raised, and only what the caller can act on

A `Raises:` section for the exceptions that are part of the contract. Not every exception that could
possibly escape.

**Why:** the point is to tell the caller what to handle. Listing `MemoryError` and
`KeyboardInterrupt` buries the two that matter. The contract is what you promise to raise for a
given condition — the rest is implementation.

**Check:** every `raise` in the body reachable from bad input. Each is a candidate; each internal
error is not.

### PS-DOC-06 [M] Document the cost and the ownership

Whether it does I/O, whether it is linear in the input, whether the caller owns the return.

**Why:** these are the two things a caller cannot see from the signature and most needs to know —
PS-PERF-04 and PS-API-13 state them from the other side. A function that does a network round trip
and reads like a property getter is a latency bug in every caller until someone reads the source.

**Check:** every public function that does I/O, loops over its input, or returns a container.

### PS-DOC-07 [S] Record the decision that is not visible from the code

Why this algorithm, why this default, what was tried and rejected. It is `[S]` because not every
decision has a reason worth recording.

**Why:** the code shows what was decided and never why, so the reasoning is lost at the moment the
author moves on — and the next person re-derives it, usually by reverting the decision and
rediscovering the reason. One sentence prevents that.

**Check:** every non-obvious constant, every hand-rolled algorithm, every `# noqa`.

## Convention

### PS-DOC-08 [M] Set a docstring convention, and know what the choice disables

`[tool.ruff.lint.pydocstyle] convention = "google"`. `numpy` for array-oriented projects: the
ecosystem splits by domain, not by recency — the array stack is uniformly numpydoc and everything
else is largely Google.

**Why:** with none, mutually contradictory rules stay enabled and ruff drops one with a warning;
with one, rules are *disabled*, so the choice decides which checks you get. `google` alone of the
three keeps `D417`, the check that a documented parameter list matches the signature.

**Check:** the absence of a `convention` setting. Run `ruff check` and read stderr for the
"incompatible" warnings.

### PS-DOC-09 [M] Never let the docstring and the signature disagree

A renamed parameter, a changed default, a removed exception — all must move together.

**Why:** a wrong docstring is worse than none, because the reader trusts it and stops reading the
signature. This is the failure mode that makes people distrust documentation generally, and it comes
from editing one and not the other.

**Check:** ruff `D417` catches a parameter the docstring does not document. The reverse, a
documented parameter the signature lost, has only a preview rule, which the shipped configuration
does not run — so that half is review, with defaults, exceptions and units.

### PS-DOC-10 [S] Write examples as doctests, and run them

`>>>` in the docstring, and `--doctest-modules` in the test run. The shipped `ruff.toml` sets
`docstring-code-format = true`, so the formatter keeps them formatted too.

**Why:** an example that is not executed will be wrong, usually within two releases, and a wrong
example is more damaging than none because it is what people copy. Running them also tests the
API's ergonomics — an example that is awkward to write is an API that is awkward to use.

**Check:** `rg -n '>>>' src/` against the test configuration. Doctests present but not run is the
finding.

## Beyond the code

### PS-DOC-11 [M] Give the package a README that answers "what" before "how"

What problem it solves, who it is for, and one example — before installation instructions.

**Why:** a reader arrives not knowing whether this is the right library, and installation
instructions do not answer that. One paragraph and one example decide it in ten seconds, which is
all the attention the decision gets.

**Check:** the first screen of the README. If it starts with an install command, it answers the
second question first.

### PS-DOC-12 [M] Keep a changelog, and write the entry with the change

In the same commit, in the same pull request. Not assembled at release time.

**Why:** written at release time it is assembled from commit messages by someone who did not make
the change, which is how "various fixes" happens. Written with the change it is written by the
person who knows whether it breaks anything — and the act of writing it is what surfaces that.

**Check:** every merge touching the public surface. See PS-API-20.

### PS-DOC-13 [S] Document the decision, not only the outcome

An architecture note recording the alternatives and why this one, kept with the code.

**Why:** the largest decisions leave the least trace: a choice between two designs shows up as one
design and no record that the other was considered. The next person to face the question has to redo
the analysis, and may reach a different answer for reasons that were already rejected.

**Check:** for each significant component, is there a note saying why it is shaped that way? Its
absence is not a defect, but its presence pays repeatedly.

### PS-DOC-14 [M] Never document what was checked, only what is true

"This function is thread-safe" — not "we verified this function is thread-safe on 2026-08-14".

**Why:** the reader cannot act on who checked, or when, or on what machine. It is the residue of
writing the thing rather than content of the thing, and it goes stale in a way the statement itself
does not. State the property; if it needs evidence, that is a test.

**Check:** `rg -ni 'we (verified|checked|tested)|as of [0-9]{4}' src/`, plus any sentence
naming a date, a host, or a person. Every hit is provenance rather than content.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `D100` | error | a public module without a docstring |
| ruff | `D101` | error | a public class without a docstring |
| ruff | `D102` | error | a public method without a docstring |
| ruff | `D103` | error | a public function without a docstring |
| ruff | `D104` | error | a public package without a docstring |
| ruff | `D105` | error | a magic method without a docstring |
| ruff | `D106` | error | a public nested class without a docstring |
| ruff | `D107` | error | `__init__` without a docstring |
| ruff | `D205` | error | no blank line between a docstring's summary and its body |
| ruff | `D209` | error | a multi-line docstring's closing quotes not on their own line |
| ruff | `W505` | error | docstring or comment text past 72 columns, PEP 8's limit for prose |
| ruff | `D417` | error | a parameter missing from a docstring's `Args:` — document every one, or none |
