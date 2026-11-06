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
from agent_skill.model import REFERENCES, SKILL_MD, Skill
from agent_skill.profiles import Profile
from agent_skill.profiles.record import rules

#: The demo's profile: Demo 1.2, in normal form. It names no language
#: and no toolchain, so nothing is compiled or searched; its two `rg`
#: patterns are listed unproven, as a shipped standard's are.
PROFILE = Profile(
    name="demo-style",
    prefix="DS",
    tools=("democ",),
    language="Demo",
    verified_as="compiles as written against Demo {pin}",
    strict_scope="library",
    subject=Pin.parse("demo==1.2.3"),
    unproven=rules("DS-ERR-02", "DS-MIG-01"),
    normalized=True,
)

#: Every profile a demo standard is read with, by its name.
PROFILES = {PROFILE.name: PROFILE}

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

| Old | New | Rule |
|---|---|---|
| `old_name()` | `new_name()` | DS-MIG-01 |

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

No tool decides any of this chapter on its own.
"""

_MIGRATION = """# Migration

Scope: the spellings Demo 1.2 renamed, and what replaces each.

## Contents

- DS-MIG-01 [M] Write the new name of a renamed function

---

## Renamed

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


def build(tree: Path) -> tuple[str, ...]:
    """Write the demo under `tree`, and say which files it wrote.

    Each path is relative to `tree`, as a control's edits are, so a
    per-skill check reads the demo and nothing else.
    """
    root = tree / PROFILE.name
    (root / REFERENCES).mkdir(parents=True)
    for rel, text in FILES.items():
        (root / rel).write_text(canonical(text))
    shared.rewrite(Skill(root, PROFILE))
    return tuple(f"{PROFILE.name}/{rel}" for rel in FILES)
