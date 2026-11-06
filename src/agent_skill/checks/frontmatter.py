"""The block Claude Code reads before anything else."""

import re
lazy from collections.abc import Iterator

from agent_skill import shared
from agent_skill.checks import check, per_skill
from agent_skill.report import Finding, Level, declare, fail
lazy from agent_skill.model import Skill

ALLOWED = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
}
MAX_DESCRIPTION = 1024

# The branches a finding of this check comes from.
MISSING = declare("frontmatter", "missing", Level.FAIL)
EXTRA_KEYS = declare("frontmatter", "extra_keys", Level.FAIL)
REQUIRED = declare("frontmatter", "required", Level.FAIL)
NAME = declare("frontmatter", "name", Level.FAIL)
FOLDED = declare("frontmatter", "folded", Level.FAIL)
LENGTH = declare("frontmatter", "length", Level.FAIL)
ANGLE_BRACKET = declare("frontmatter", "angle_bracket", Level.FAIL)
RULE_COUNT = declare("frontmatter", "rule_count", Level.FAIL)

# The branches only a normalised standard is held to (decision 13).
TEMPLATE = declare("frontmatter", "template", Level.FAIL)
COUNTED = declare("frontmatter", "counted", Level.FAIL)
BOUNDED = declare("frontmatter", "bounded", Level.FAIL)

#: A normalised standard's description is this short or shorter: a
#: use case, what triggers it, and a target.
BOUND = 500

#: A count of rules, as a description states one: `a 262-rule library`.
_COUNT = re.compile(r"\b\d+[- ]rules?\b", re.IGNORECASE)


def described(body: str) -> str | None:
    """The description a frontmatter block folds, on one line.

    None when it holds no `>-` folded description, which is the one
    shape every standard's takes.
    """
    # The body ends without a newline, so the last line of a
    # description that is the last key ends at the end of the body.
    block = re.search(r"description: >-\n((?:  .*(?:\n|\Z))+)", body)
    if block is None:
        return None
    return " ".join(line.strip() for line in block.group(1).splitlines())


@check("frontmatter", "the block Claude Code reads first")
@per_skill
def frontmatter(skill: Skill) -> Iterator[Finding]:
    """A missing or reshaped field is a finding, not a traceback.

    This was three unguarded `.group(1)` calls, so a malformed
    frontmatter crashed the checker instead of being reported by it.
    The block is the one the document model reads, as every other
    reader of `SKILL.md` reads it; its keys are YAML's to say.
    """
    where = skill.at()
    body = skill.doc.frontmatter
    if body is None:
        yield fail("SKILL.md has no frontmatter block", where, MISSING)
        return
    keys = set(re.findall(r"^([a-z-]+):", body, re.MULTILINE))
    if extra := keys - ALLOWED:
        yield fail(f"non-spec frontmatter keys {sorted(extra)}", where, EXTRA_KEYS)
    for required in ("name", "description"):
        if required not in keys:
            yield fail(f"frontmatter has no `{required}`", where, REQUIRED)

    name = re.search(r"^name:\s*(\S+)", body, re.MULTILINE)
    if name and name.group(1) != skill.name:
        yield fail(f"frontmatter name {name.group(1)!r} != directory", where, NAME)

    folded = described(body)
    if "description" in keys and folded is None:
        yield fail("description is not a `>-` folded block", where, FOLDED)
    desc = folded or ""
    if "<" in desc or ">" in desc:
        yield fail("angle bracket in description", where, ANGLE_BRACKET)
    if skill.profile.normalized:
        yield from _templated(skill, desc)
    else:
        yield from _counted(skill, desc)


def _counted(skill: Skill, desc: str) -> Iterator[Finding]:
    """A description under the limit, and any count it states true."""
    where = skill.at()
    if len(desc) > MAX_DESCRIPTION:
        yield fail(f"description {len(desc)} > {MAX_DESCRIPTION}", where, LENGTH)
    stated = re.search(r"(\d+)-rule \w+", desc)
    actual = len(skill.chapter_rules) + len(skill.core)
    if stated and int(stated.group(1)) != actual:
        yield fail(
            f"description says {stated.group(1)} rules, actual {actual}",
            where,
            RULE_COUNT,
        )


def _templated(skill: Skill, desc: str) -> Iterator[Finding]:
    """A normalised standard's description fills the shared template.

    The use case first, the artifacts that trigger it, the target
    (`shared/description.md`); no count of rules, which every revision
    changes and which tells a reader nothing; and well under the limit.
    A count stated is no longer compared with the rules: it is not
    stated at all.
    """
    where = skill.at()
    if desc and shared.description(skill).fullmatch(desc) is None:
        template = " ".join((shared.HERE / shared.DESCRIPTION).read_text().split())
        yield fail(
            f"description does not fill the shared template `{template}`",
            where,
            TEMPLATE,
        )
    if (m := _COUNT.search(desc)) is not None:
        yield fail(
            f"description counts rules (`{m.group(0)}`); the count changes with every "
            "revision and tells a reader nothing",
            where,
            COUNTED,
        )
    if len(desc) > BOUND:
        yield fail(f"description {len(desc)} > {BOUND}", where, BOUNDED)
