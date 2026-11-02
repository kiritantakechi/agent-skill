"""The block Claude Code reads before anything else."""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.ids import Branch
from agent_skill.report import Finding, fail
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
MISSING = Branch("frontmatter", "missing")
EXTRA_KEYS = Branch("frontmatter", "extra_keys")
REQUIRED = Branch("frontmatter", "required")
NAME = Branch("frontmatter", "name")
FOLDED = Branch("frontmatter", "folded")
LENGTH = Branch("frontmatter", "length")
ANGLE_BRACKET = Branch("frontmatter", "angle_bracket")
RULE_COUNT = Branch("frontmatter", "rule_count")


@check("frontmatter", "the block Claude Code reads first")
@per_skill
def frontmatter(skill: Skill) -> Iterator[Finding]:
    """A missing or reshaped field is a finding, not a traceback.

    This was three unguarded `.group(1)` calls, so a malformed
    frontmatter crashed the checker instead of being reported by it.
    """
    text = skill.text
    where = skill.at()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        yield fail("SKILL.md has no frontmatter block", where, MISSING)
        return
    body = m.group(1)
    keys = set(re.findall(r"^([a-z-]+):", body, re.MULTILINE))
    if extra := keys - ALLOWED:
        yield fail(f"non-spec frontmatter keys {sorted(extra)}", where, EXTRA_KEYS)
    for required in ("name", "description"):
        if required not in keys:
            yield fail(f"frontmatter has no `{required}`", where, REQUIRED)

    name = re.search(r"^name:\s*(\S+)", body, re.MULTILINE)
    if name and name.group(1) != skill.name:
        yield fail(f"frontmatter name {name.group(1)!r} != directory", where, NAME)

    desc_block = re.search(r"description: >-\n((?:  .*\n)+)", body)
    if "description" in keys and not desc_block:
        yield fail("description is not a `>-` folded block", where, FOLDED)
    desc = (
        " ".join(ln.strip() for ln in desc_block.group(1).splitlines())
        if desc_block
        else ""
    )
    if len(desc) > MAX_DESCRIPTION:
        yield fail(f"description {len(desc)} > {MAX_DESCRIPTION}", where, LENGTH)
    if "<" in desc or ">" in desc:
        yield fail("angle bracket in description", where, ANGLE_BRACKET)

    stated = re.search(r"(\d+)-rule \w+", desc)
    actual = len(skill.rules) + len(skill.core_rules)
    if stated and int(stated.group(1)) != actual:
        yield fail(
            f"description says {stated.group(1)} rules, actual {actual}",
            where,
            RULE_COUNT,
        )
