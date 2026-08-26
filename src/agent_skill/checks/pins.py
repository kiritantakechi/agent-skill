"""A pinned version that has been superseded should say so, not be remembered.

The alternative is a calendar entry: "on 1 September, move the interpreter pin."
That is a note nobody reads, in a place nobody looks, about a date nobody
remembers — and this repository's whole position is that a check which cannot
fail looks exactly like a check that passes. So the expiry is a check.

It fails rather than notes, because moving a pin is a reviewed event by Decision
0 of the design, and a red build is what causes a review to happen.
"""

from __future__ import annotations

import re

from ..proc import have, run
from ..report import fail, unrun
from . import check

#: `cpython-3.15.0rc1+freethreaded-macos-aarch64-none` -> ("3.15.0rc1", True)
RELEASE = re.compile(r"^cpython-(?P<version>\d+\.\d+\.\d+[a-z0-9]*)(?P<ft>\+freethreaded)?-")


def _sort_key(version: str) -> tuple:
    """Order releases so `3.15.0rc2` follows `3.15.0rc1` and precedes `3.15.0`.

    A final release has no suffix and must sort *after* every candidate, which a
    plain string comparison gets backwards.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$", version)
    if not m:
        return (0, 0, 0, 0, 0)
    major, minor, micro, kind, serial = m.groups()
    rank = {"a": 0, "b": 1, "rc": 2}.get(kind or "", 3)
    return (int(major), int(minor), int(micro), rank, int(serial or 0))


@check("pins", "a superseded pin is a finding, not a diary entry")
def pins(skill):
    if skill.profile.toolchain != "python":
        return
    from ..lang.python import INTERPRETER

    m = RELEASE.match(f"{INTERPRETER}-")
    if not m:
        yield fail(f"the pin `{INTERPRETER}` is not a release identifier", skill.name)
        return
    pinned, want_ft = m["version"], bool(m["ft"])

    # Two declarations, compared — the harness verifies against one and the reader
    # copies the other, so an asset that installs a different build than the one
    # these examples were verified on is the defect this half exists to catch.
    workflow = skill.root / "assets" / "ci.yml"
    if workflow.exists():
        stated = set(re.findall(r"uv python install (\S+)", workflow.read_text()))
        for named in sorted(stated - {INTERPRETER}):
            yield fail(
                f"assets/ci.yml installs `{named}` where the harness verifies against "
                f"`{INTERPRETER}` — a reader would not be running what this was checked on",
                skill.name,
            )

    if not have("uv"):
        yield unrun("`uv` is not on PATH, so no release list was consulted", skill.name)
        return
    r = run(["uv", "python", "list", "--all-versions"], timeout=120)
    if not r.out:
        yield unrun("`uv python list` returned nothing to compare against", skill.name)
        return

    # Scoped to the pinned minor series on purpose: a newer patch or candidate is
    # a pin refresh, and a newer *minor* is a deliberate change of target that
    # this check has no business demanding.
    series = re.match(r"^(\d+\.\d+)", pinned).group(1)  # 3.15.0rc1 -> 3.15
    newer = set()
    for line in r.out.split("\n"):
        found = RELEASE.match(line.strip())
        if not found or bool(found["ft"]) != want_ft:
            continue
        version = found["version"]
        if version.startswith(f"{series}.") and _sort_key(version) > _sort_key(pinned):
            newer.add(version)

    if newer:
        best = max(newer, key=_sort_key)
        yield fail(
            f"the interpreter pin is `{pinned}` and `{best}` is available — move it in "
            f"`lang/python.py` and `assets/ci.yml`, re-verify the PS-MIG table against the "
            f"released What's New, and re-run the suite",
            skill.name,
        )
