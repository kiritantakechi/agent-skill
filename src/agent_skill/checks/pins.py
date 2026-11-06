"""A superseded pin should say so, not be remembered.

The alternative is a calendar entry: "on 1 September, move the
interpreter pin." That is a note nobody reads, in a place nobody looks,
about a date nobody remembers — and this repository's whole position is
that a check which cannot fail looks exactly like a check that passes.
So the expiry is a check.

It fails rather than notes, because moving a pin is a reviewed event by
Decision 0 of the design, and a red build is what causes a review to
happen.

The harness's own tool pins are compared here. A skill's pins are its
toolchain's to compare (`Toolchain.pins`): what a release of Rust, of
CPython or of Zig is, and where to ask for the newest, differs for each.
"""

import re
lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.harness import HARNESS, pinned, version_mismatch
from agent_skill.ids import Version
from agent_skill.lang import needs, toolchain_for
from agent_skill.proc import have, run, tool_path
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from. Each toolchain
# declares those its pins report through.
TOOL_ABSENT = declare("pins", "tool_absent", Level.UNRUN)
TOOL_SILENT = declare("pins", "tool_silent", Level.UNRUN)
TOOL_MISMATCH = declare("pins", "tool_mismatch", Level.FAIL)
INDEX_SILENT = declare("pins", "index_silent", Level.UNRUN)
INDEX_UNREAD = declare("pins", "index_unread", Level.UNRUN)
INDEX_UNORDERED = declare("pins", "index_unordered", Level.UNRUN)
TOOL_STALE = declare("pins", "tool_stale", Level.FAIL)


def _tool_pins() -> Iterator[Finding]:
    """Each tool pin against the running version and the newest release.

    Both directions, because they fail differently. A running version
    that is not the pinned one means every claim about what was verified
    is false. A pin the index has moved past means the claim is still
    true and going stale, and moving it is a reviewed event rather than
    a note nobody reads.
    """
    where = HARNESS.where
    for pinned_tool in HARNESS.tools:
        tool, package = pinned_tool.binary, pinned_tool.package
        if not have(tool) or (located := tool_path(tool)) is None:
            yield unrun(
                f"`{tool}` is not available, so its pin was not verified",
                where,
                TOOL_ABSENT,
            )
            continue
        answered = run([located, "--version"], timeout=30)
        if not answered.ok:
            yield unrun(f"`{tool}` did not answer `--version`", where, TOOL_SILENT)
            continue
        if complaint := version_mismatch(tool, answered.out):
            yield fail(complaint, where, TOOL_MISMATCH)
            continue

        pin = pinned(tool)
        pinned_at = str(pin.version) if pin else ""
        # No environment involved: resolving a bare requirement asks the
        # index what the newest release is without installing anything.
        resolved = run(
            ["uv", "pip", "compile", "-", "--no-header", "--quiet"],
            timeout=120,
            stdin=package,
        )
        if not resolved.ok or not resolved.out.strip():
            yield unrun(
                f"the index did not answer for `{package}`, "
                "so its pin was not compared",
                where,
                INDEX_SILENT,
            )
            continue
        found = re.search(
            rf"^{re.escape(package)}==(\S+)", resolved.out, re.MULTILINE | re.IGNORECASE
        )
        if not found:
            yield unrun(
                f"could not read a version for `{package}` from the index",
                where,
                INDEX_UNREAD,
            )
            continue
        newest = found.group(1)
        here, there = Version.released(pinned_at), Version.released(newest)
        if here is None or there is None:
            yield unrun(
                f"`{package}` was not compared: "
                f"{(newest if there is None else pinned_at)!r} is not a version "
                "this can order, and a release it cannot order is not one it "
                "has ruled out",
                where,
                INDEX_UNORDERED,
            )
            continue
        if there > here:
            yield fail(
                f"`{tool}` is pinned to {pinned_at} and {newest} is available — "
                f"move the pin in `{HARNESS.declared_in}`, re-run the suite, and read "
                "what moved before trusting it",
                where,
                TOOL_STALE,
            )


@check(
    "pins",
    "a superseded pin is a finding, not a diary entry",
    needs=tuple(
        dict.fromkeys(("uv", *HARNESS.binaries, *needs(lambda tc: tc.pins_with)))
    ),
)
def pins(tree: Tree) -> Iterator[Finding]:
    """Each skill's pins and the harness's, against what runs and ships.

    The harness's tool pins are asked once, when a skill verified with
    those tools is read; they pin the repository rather than a skill,
    so their findings lie in no skill.
    """
    yield from per_skill(_skill_pins)(tree)
    if any(set(_verifies_with(skill)) & set(HARNESS.binaries) for skill in tree):
        yield from _tool_pins()


def _skill_pins(skill: Skill) -> Iterator[Finding]:
    """One skill's pins, as its toolchain compares them."""
    if (toolchain := toolchain_for(skill.profile.toolchain)) is not None:
        yield from toolchain.pins(skill)


def _verifies_with(skill: Skill) -> tuple[str, ...]:
    """The tools `skill`'s examples are verified with, if any."""
    toolchain = toolchain_for(skill.profile.toolchain)
    return toolchain.needs if toolchain is not None else ()
