"""The block Claude Code reads before anything else."""

from __future__ import annotations

import re

from ..report import fail
from . import check

ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
MAX_DESCRIPTION = 1024


@check("frontmatter", "the block Claude Code reads first")
def frontmatter(skill):
    """A missing or reshaped field is a finding, not a traceback.

    This was three unguarded `.group(1)` calls, so a malformed frontmatter
    crashed the checker instead of being reported by it.
    """
    text = skill.text
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        yield fail("SKILL.md has no frontmatter block", skill.name)
        return
    body = m.group(1)
    keys = set(re.findall(r"^([a-z-]+):", body, re.M))
    if extra := keys - ALLOWED:
        yield fail(f"non-spec frontmatter keys {sorted(extra)}", skill.name)
    for required in ("name", "description"):
        if required not in keys:
            yield fail(f"frontmatter has no `{required}`", skill.name)

    name = re.search(r"^name:\s*(\S+)", body, re.M)
    if name and name.group(1) != skill.name:
        yield fail(f"frontmatter name {name.group(1)!r} != directory", skill.name)

    desc_block = re.search(r"description: >-\n((?:  .*\n)+)", body)
    if "description" in keys and not desc_block:
        yield fail("description is not a `>-` folded block", skill.name)
    desc = " ".join(ln.strip() for ln in desc_block.group(1).splitlines()) if desc_block else ""
    if len(desc) > MAX_DESCRIPTION:
        yield fail(f"description {len(desc)} > {MAX_DESCRIPTION}", skill.name)
    if "<" in desc or ">" in desc:
        yield fail("angle bracket in description", skill.name)

    stated = re.search(r"(\d+)-rule library", desc)
    actual = len(skill.rules) + len(skill.core_rules)
    if stated and int(stated.group(1)) != actual:
        yield fail(f"description says {stated.group(1)} rules, actual {actual}", skill.name)
