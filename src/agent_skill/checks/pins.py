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

from ..proc import PACKAGE, have, pinned_version, run, tool_path, version_mismatch
from ..report import fail, unrun
from . import check

#: Every tool whose version decides whether a check passes. The binary and the
#: distribution are spelled differently for `rg`, and `version_mismatch` already
#: knows that mapping — this list is only who to ask.
TOOLS = ("ruff", "ty", "pytest", "rg")


def _tool_pins():
    """Each pinned tool against the version that runs and the version that exists.

    Both directions, because they fail differently. A running version that is
    not the pinned one means every claim about what was verified is false. A pin
    the index has moved past means the claim is still true and going stale, and
    moving it is a reviewed event rather than a note nobody reads.
    """
    for tool in TOOLS:
        if not have(tool):
            yield unrun(f"`{tool}` is not available, so its pin was not verified", "harness")
            continue
        answered = run([tool_path(tool), "--version"], timeout=30)
        if not answered.ok:
            yield unrun(f"`{tool}` did not answer `--version`", "harness")
            continue
        if complaint := version_mismatch(tool, answered.out):
            yield fail(complaint, "harness")
            continue

        pinned = pinned_version(tool)
        package = PACKAGE.get(tool, tool)
        # No environment involved: resolving a bare requirement asks the index
        # what the newest release is without installing anything.
        resolved = run(
            ["uv", "pip", "compile", "-", "--no-header", "--quiet"], timeout=120, stdin=package
        )
        if not resolved.ok or not resolved.out.strip():
            yield unrun(
                f"the index did not answer for `{package}`, so its pin was not compared", "harness"
            )
            continue
        found = re.search(rf"^{re.escape(package)}==(\S+)", resolved.out, re.M | re.I)
        if not found:
            yield unrun(f"could not read a version for `{package}` from the index", "harness")
            continue
        newest = found.group(1)
        here = _sort_key(pinned) if pinned else None
        there = _sort_key(newest)
        if here is None or there is None:
            yield unrun(
                f"`{package}` was not compared: "
                f"{(newest if there is None else pinned)!r} is not a version this can order, "
                f"and a release it cannot order is not one it has ruled out",
                "harness",
            )
            continue
        if there > here:
            yield fail(
                f"`{tool}` is pinned to {pinned} and {newest} is available — move the pin in "
                f"`pyproject.toml`, re-run the suite, and read what moved before trusting it",
                "harness",
            )


#: `cpython-3.15.0rc1+freethreaded-macos-aarch64-none` -> ("3.15.0rc1", True)
RELEASE = re.compile(r"^cpython-(?P<version>\d+\.\d+\.\d+[a-z0-9]*)(?P<ft>\+freethreaded)?-")


def _sort_key(version: str) -> tuple | None:
    """Order releases so `3.15.0rc2` follows `3.15.0rc1` and precedes `3.15.0`.

    A final release has no suffix and must sort *after* every candidate, which a
    plain string comparison gets backwards.

    `None` for a version this does not understand, because the alternative was
    `(0, 0, 0, 0, 0)` — which sorts below every real release, so `1.2.3.post1`
    from the index compared as older than the pin and the staleness check
    reported the pin current. That is the same shape `version_mismatch` was
    already fixed for: a value that could not be read must not be resolved into
    one that happens to compare as agreement.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$", version)
    if not m:
        return None
    major, minor, micro, kind, serial = m.groups()
    rank = {"a": 0, "b": 1, "rc": 2}.get(kind or "", 3)
    return (int(major), int(minor), int(micro), rank, int(serial or 0))


def local_pin(profile):
    """(level, message) for a pin that follows the local toolchain.

    Compared with the running version only. Upstream releasing something newer is
    not a finding — the standard is verified against what runs here, and that has
    not changed. The local toolchain moving past the pin is: the claim that the
    examples were verified on this version has just stopped being true.
    """
    reason = profile.follows_local
    if reason is None:
        return
    if not reason.strip():
        yield fail, f"{profile.name} follows the local toolchain and gives no reason why"
        return
    pinned, running = profile.pin(), profile.running_version()
    if running is None:
        yield (
            unrun,
            f"could not ask the local toolchain which version runs, so `{pinned}` was not compared",
        )
    elif running != pinned:
        moved = f"follows this machine's toolchain, which is now {running}"
        yield fail, f"{profile.name} is pinned to {pinned} and {moved} — the cue to bump it"


@check(
    "pins",
    "a superseded pin is a finding, not a diary entry",
    needs=("uv", "ruff", "ty", "pytest", "rg", "zig"),
)
def pins(skill):
    for level, message in local_pin(skill.profile):
        yield level(message, skill.name)
    if skill.profile.toolchain != "python":
        return
    yield from _tool_pins()
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

    # Two declarations, compared — the same reason the interpreter half exists.
    # The harness verifies against one pin and the reader installs the other, so
    # an asset naming a different version hands them a build these examples were
    # never checked on.
    shipped = skill.root / "assets" / "pyproject.toml"
    if shipped.exists():
        text = shipped.read_text()
        for tool in TOOLS:
            package = PACKAGE.get(tool, tool)
            named = re.search(rf'"{re.escape(package)}==(\S+?)"', text)
            harness = pinned_version(tool)
            if named and harness and named.group(1) != harness:
                yield fail(
                    f"assets/pyproject.toml pins `{package}=={named.group(1)}` where the harness "
                    f"verifies against {harness} — a reader would not be running what this was "
                    f"checked on",
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
    here = _sort_key(pinned)
    if here is None:
        yield fail(f"the pin `{INTERPRETER}` carries a version this cannot order", skill.name)
        return

    # version -> its order, so the best is picked without ordering by a key
    # function that is allowed to answer `None`.
    newer: dict[str, tuple] = {}
    unreadable: set[str] = set()
    for line in r.out.split("\n"):
        found = RELEASE.match(line.strip())
        if not found or bool(found["ft"]) != want_ft:
            continue
        version = found["version"]
        if not version.startswith(f"{series}."):
            continue
        # Scoped to the pinned series, so this reports what it could not rule
        # out rather than every oddity in a list of every CPython ever built.
        order = _sort_key(version)
        if order is None:
            unreadable.add(version)
        elif order > here:
            newer[version] = order

    if unreadable:
        yield unrun(
            f"`uv python list` offers {', '.join(sorted(unreadable))} in the {series} "
            f"series, which this cannot order against `{pinned}` — a release it cannot "
            f"compare is not a release it has ruled out",
            skill.name,
        )

    if newer:
        best = max(newer, key=newer.__getitem__)
        yield fail(
            f"the interpreter pin is `{pinned}` and `{best}` is available — move it in "
            f"`lang/python.py` and `assets/ci.yml`, re-verify the PS-MIG table against the "
            f"released What's New, and re-run the suite",
            skill.name,
        )
