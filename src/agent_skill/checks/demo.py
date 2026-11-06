"""A small standard in normal form, for the controls of the normal form.

No shipped standard is normalised yet, so nothing in the tree reaches a
property only a normalised standard is held to, and a control cannot
flip a shipped standard's flag instead: each of them breaks most of
those properties at once, and a control fires its branch alone. This
standard keeps every property `anatomy` and `skeleton` hold any
standard to, and the normal form's besides, so one edit breaks one.

It is written into the controls' throwaway tree and read with `PROFILE`,
which no skill ships with, so the copy is read as `normalized` while
every shipped profile stays as it is. Its shared passages are filled by
`shared.rewrite`, as `fmt` fills a shipped standard's, and every file is
printed canonically.
"""

lazy from pathlib import Path

from agent_skill import shared
from agent_skill.doc import canonical
from agent_skill.ids import Pin
from agent_skill.lang.python import PythonSnippet
from agent_skill.model import REFERENCES, SKILL_MD, Skill
from agent_skill.profiles import Delta, Mirror, Profile
from agent_skill.profiles.record import rules

#: The demo's profile: Demo 1.2, in normal form. It names no language,
#: so no example is compiled or searched; its two `rg` patterns are
#: listed unproven, as a shipped standard's are. Its lint configuration
#: is a `ty.toml`, read as Python's toolchain reads one, so the lint
#: bijection has a configuration to hold its rows to; it ships no
#: `ruff.toml`, so nothing is asked of `ruff`.
PROFILE = Profile(
    name="demo-style",
    prefix="DS",
    tools=("democ", "ty"),
    language="Demo",
    verified_as="compiles as written against Demo {pin}",
    strict_scope="library",
    toolchain=PythonSnippet(),
    subject=Pin.parse("demo==1.2.3"),
    unproven=rules("DS-ERR-02", "DS-MIG-01"),
    normalized=True,
)

#: The stages of the review, in §5 and in the protocol's review order.
_STAGES = "1. **Soundness.** Look.\n2. **Errors.** Look.\n"

_SKILL_MD = f"""---
name: {PROFILE.name}
description: >-
  A demo standard in normal form.
---

# Demo Style — 1.2

A demo standard in normal form.

## How to use this standard

## 1. Tiers

**Code is "library"** — if it is published.

## 2. Demo 1.2 reality check

### 2.1 Compiles, and behaves differently

- `open()` on a missing file returns an error where it stopped the program (DS-ERR-01).

### 2.2 No longer compiles

| Old | Demo 1.2 | Rule |
|---|---|---|
| `old_name` | `new_name` | DS-MIG-01 |

### 2.3 What Demo 1.2 gained

- `close()` reports a failed flush as an error (DS-ERR-02).

## 3. Design principles

Subtract.

## 4. Core rules

- **Errors**
  - DS-ERR-01 [M!] Return an error for a failure the caller can handle
- **Migration**
  - DS-MIG-01 [M] Write the new name of a renamed function

## 5. Review checklist

{_STAGES}
## 6. Reference map

| File | Rule IDs | Covers |
|---|---|---|
| `{REFERENCES}/errors.md` | `DS-ERR` (2) | errors |
| `{REFERENCES}/migration.md` | `DS-MIG` (1) | migration |
| `{shared.REVIEW}` | — | the protocol |

## 7. Bundled assets

None.
"""

_ERRORS = """# Errors

Scope: what a function does when it fails, and how its caller learns of it.
Naming a failure is the naming chapter's.

## Contents

- **Failing**
  - DS-ERR-01 [M!] Return an error for a failure the caller can handle
  - DS-ERR-02 [M] Never stop the program from a library

- Decided by tools

---

## Failing

### DS-ERR-01 [M!] Return an error for a failure the caller can handle

A caller decides what a failure means to it, so the function that meets one reports it.

*Relaxed form:* outside a library, a program may stop where no caller is left to decide.

**Why:** only the caller knows whether a missing file is fatal or expected.

**Check:** read each function that can fail; one that stops the program instead
of returning is the finding.

```text
// verified — GOOD
open(path) -> Result
```

```text
// verified — BAD
open(path) -> File
```

### DS-ERR-02 [M] Never stop the program from a library

Library code returns every failure, as DS-ERR-01 says, and leaves stopping to
the program.

**Why:** a library that stops its host takes the decision from the one place
that can make it.

**Check:** `rg -n 'process::exit' src/` — every hit in library code is the finding.

## Decided by tools

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ty | `division-by-zero` | error | a division the checker proves is by zero |
"""

_MIGRATION = """# Migration

Scope: the spellings Demo 1.2 renamed, and what replaces each.

## Contents

- DS-MIG-01 [M] Write the new name of a renamed function

---

## Renamed

| Old | Demo 1.2 | Status | Rule |
|---|---|---|---|
| `old_name` | `new_name` | gone | DS-MIG-01 |
| `old_flag` | `new_flag` | alias | DS-MIG-01 |

```sh
rg -n -F \\
  -e 'old_name' \\
  -e 'old_flag' \\
  .
```

### DS-MIG-01 [M] Write the new name of a renamed function

`old_name()` is `new_name()` now, and only the new name builds.

**Why:** the old name fails the build, so code carried over from an older
release stops at it.

**Check:** `rg -n 'old_name' src/` — every hit is the finding.
"""

#: The shared severity model, label and meaning.
_SEVERITY = shared.SEVERITIES

_REVIEW = f"""# Review protocol

## Severity model

| Severity | Meaning | Examples |
|---|---|---|
{"".join(f"| **{label}** | {said} | an example |\n" for label, said in _SEVERITY)}
## Review order

{_STAGES}
## Mechanical pass

Run the tools.

## Output format

A table.

## Refactoring a codebase to this standard

In order.
"""

#: Each file of the demo, by its path in the skill.
FILES = {
    SKILL_MD: _SKILL_MD,
    f"{REFERENCES}/errors.md": _ERRORS,
    f"{REFERENCES}/migration.md": _MIGRATION,
    shared.REVIEW: _REVIEW,
}


#: The configuration the demo ships, by its path in the skill: one lint,
#: set to fail a run, and listed by the errors chapter.
ASSETS = {"assets/ty.toml": '[rules]\ndivision-by-zero = "error"\n'}


def build(tree: Path) -> tuple[str, ...]:
    """Write the demo under `tree`, and say which files it wrote.

    Each path is relative to `tree`, as a control's edits are, so a
    per-skill check reads the demo and nothing else.
    """
    return _write(tree, PROFILE, FILES, ASSETS)


def _write(
    tree: Path, profile: Profile, files: dict[str, str], assets: dict[str, str]
) -> tuple[str, ...]:
    """Write one demo standard under `tree`, and say which files."""
    root = tree / profile.name
    (root / REFERENCES).mkdir(parents=True)
    (root / "assets").mkdir()
    for rel, text in files.items():
        (root / rel).write_text(canonical(text))
    for rel, text in assets.items():
        (root / rel).write_text(text)
    shared.rewrite(Skill(root, profile))
    return tuple(f"{profile.name}/{rel}" for rel in (*files, *assets))


# ------------------------------------------------------------------
# a delta on the demo, for the controls of the delta map (decision 10)

#: A delta on the demo: Delta 1.2, which departs from one demo rule and
#: defers to it for the rest. Its examples are `text`, the language the
#: anchor's patterns are run over; its `[M!]` is the demo's, scope and
#: all.
DELTA = Profile(
    name="delta-style",
    prefix="DL",
    languages=("text",),
    tools=("democ", "ty"),
    language="Delta",
    verified_as="compiles as written against Delta {pin}",
    strict_scope=PROFILE.strict_scope,
    delta=Delta(
        anchor=PROFILE.name,
        step=f"**Load `{PROFILE.name}` as well** for anything the delta leaves alone.",
    ),
    toolchain=PythonSnippet(),
    subject=Pin.parse("delta==1.2.3"),
    unproven=rules("DL-ERR-02", "DL-MIG-01"),
    mirror=Mirror(PROFILE.name),
    normalized=True,
)

#: The delta's one departure, as its table states it.
DEPARTURE = (
    f"| {PROFILE.name} rule | Relation | {DELTA.name} rule | Tier | Reason |\n"
    "|---|---|---|---|---|\n"
    "| DS-ERR-01 | tightens | DL-ERR-01 | [M!] → [M] | every delta program is a "
    "library, so no caller is ever absent |\n"
)


def _delta(text: str) -> str:
    """A demo file, as the delta states it: its own names and IDs."""
    for old, new in (
        ("DS-", "DL-"),
        (PROFILE.name, DELTA.name),
        ("Demo", "Delta"),
        ("demo standard", "delta standard"),
    ):
        text = text.replace(old, new)
    return text


def _delta_files() -> dict[str, str]:
    """The delta's files: the demo's, departing from DS-ERR-01."""
    files = {rel: _delta(text) for rel, text in FILES.items()}
    files[SKILL_MD] = (
        files[SKILL_MD]
        .replace("DL-ERR-01 [M!]", "DL-ERR-01 [M]")
        .replace("Subtract.\n", f"Subtract, and depart only here.\n\n{DEPARTURE}")
    )
    errors = f"{REFERENCES}/errors.md"
    files[errors] = (
        files[errors]
        .replace("DL-ERR-01 [M!]", "DL-ERR-01 [M]")
        .replace("A caller decides", "Departs from DS-ERR-01. A caller decides")
        .replace(
            "*Relaxed form:* outside a library, a program may stop where no caller "
            "is left to decide.\n\n",
            "",
        )
        .replace(
            "| ty | `division-by-zero` | error | a division the checker proves is by "
            "zero |",
            "| ty | `possibly-missing-attribute` | warn | an attribute the checker "
            "cannot prove is there |",
        )
    )
    return files


#: The delta's configuration: the demo's lint, set as the demo sets it
#: and so the demo's row, and one of its own, which its row lists.
DELTA_ASSETS = {
    "assets/ty.toml": (
        '[rules]\ndivision-by-zero = "error"\npossibly-missing-attribute = "warn"\n'
    )
}


def build_delta(tree: Path) -> tuple[str, ...]:
    """Write the delta beside the demo, and say which files it wrote."""
    return _write(tree, DELTA, _delta_files(), DELTA_ASSETS)


#: Every profile a demo standard is read with, by its name.
PROFILES = {PROFILE.name: PROFILE, DELTA.name: DELTA}
