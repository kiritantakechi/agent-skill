"""A minimal standard that follows standard-structure, to try checks on.

Built through the template machinery itself: the headings and the
skill's own text are written by hand, and `shared.rewrite` fills in
every shared passage — which also makes building it a round trip through
`fmt`.
"""

from dataclasses import dataclass
from typing import override
lazy from pathlib import Path

from agent_skill import shared
from agent_skill.model import Skill
from agent_skill.profiles import Profile


@dataclass
class Demo(Profile):
    """The profile of a demo standard verified against Demo 1.2.3."""

    name: str = "demo-style"
    prefix: str = "DS"
    languages: tuple[str, ...] = ("rust",)
    tools: tuple[str, ...] = ("rustc",)
    language: str = "Demo"
    verified_as: str = "compiles as written against Demo {pin}"
    strict_scope: str = "library"

    @override
    def pin(self) -> str:
        """A fixed version: the demo has no toolchain to ask."""
        return "1.2.3"


RULE = """### {id} [M] {title}

{title}.

**Why:** one line of reason.

**Check:** read it.
"""

STAGES = ("Soundness.", "Errors.")

SKILL_MD = """---
name: demo-style
description: >-
  A demo.
---

# Demo Style — 1.2

A demo standard.

## How to use this standard

## 1. Tiers

**Code is "library"** — if it is published.

## 2. Demo 1.2 reality check

Nothing changed.

## 3. Design principles

Subtract.

## 4. Core rules

None.

## 5. Review checklist

{stages}

## 6. Reference map

| File | Rule IDs | Covers |
|---|---|---|
| `references/errors.md` | `DS-ERR` (2) | errors |
| `references/migration.md` | `DS-MIG` (1) | migration |
| `references/review-checklist.md` | — | the protocol |

## 7. Bundled assets

None.
"""

REVIEW_MD = """# Review protocol

## Severity model

{rows}

## Review order

{stages}

## Mechanical pass

Run the tools.

## Output format

A table.

## Refactoring a codebase to this standard

In order.
"""


def chapter(title: str, ids: list[tuple[str, str]]) -> str:
    contents = "\n".join(f"- {rid} [M] {t}" for rid, t in ids)
    rules = "\n".join(RULE.format(id=rid, title=t) for rid, t in ids)
    return f"# {title}\n\n{contents}\n\n---\n\n{rules}"


def build(root: Path, profile: Profile | None = None) -> Skill:
    """Write the demo under `root/demo-style` and return it parsed."""
    skill_dir = root / "demo-style"
    refs = skill_dir / "references"
    refs.mkdir(parents=True)
    stages = "\n".join(f"{i}. **{s}** Look." for i, s in enumerate(STAGES, 1))
    (skill_dir / "SKILL.md").write_text(SKILL_MD.format(stages=stages))
    rows = "\n".join(
        ["| Severity | Meaning | Examples |", "|---|---|---|"]
        + [
            f"| **{label}** | {meaning} | an example |"
            for label, meaning in shared.SEVERITIES
        ]
    )
    (refs / "review-checklist.md").write_text(
        REVIEW_MD.format(rows=rows, stages=stages)
    )
    (refs / "errors.md").write_text(
        chapter("Errors", [("DS-ERR-01", "Return errors"), ("DS-ERR-02", "Name them")])
    )
    (refs / "migration.md").write_text(
        chapter("Migration", [("DS-MIG-01", "Use the new name")])
    )
    skill = Skill(skill_dir, profile or Demo())
    shared.rewrite(skill)
    return Skill(skill_dir, profile or Demo())


def reparse(skill: Skill) -> Skill:
    """The same skill read again, after a test edited its files."""
    return Skill(skill.root, skill.profile)


def edit(skill: Skill, rel: str, old: str, new: str) -> Skill:
    path = skill.root / rel
    text = path.read_text()
    assert old in text, f"{rel}: {old!r} not found"
    path.write_text(text.replace(old, new, 1))
    return reparse(skill)
