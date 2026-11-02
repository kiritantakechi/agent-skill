"""A superseded pin should say so, not be remembered.

The alternative is a calendar entry: "on 1 September, move the
interpreter pin." That is a note nobody reads, in a place nobody looks,
about a date nobody remembers — and this repository's whole position is
that a check which cannot fail looks exactly like a check that passes.
So the expiry is a check.

It fails rather than notes, because moving a pin is a reviewed event by
Decision 0 of the design, and a red build is what causes a review to
happen.
"""

import json
import re
import tomllib
from functools import cache
from typing import Any
lazy import urllib.request
lazy from collections.abc import Iterator

from agent_skill.checks import check, per_skill
from agent_skill.ids import Branch, Location
from agent_skill.proc import (
    PACKAGE,
    have,
    pinned_version,
    run,
    tool_path,
    version_mismatch,
)
from agent_skill.report import fail, unrun
from agent_skill.text import group
lazy from agent_skill.lang.python import INTERPRETER
lazy from agent_skill.lang.rust import Crate
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.profiles import Profile
lazy from agent_skill.report import Finding

#: Every tool whose version decides whether a check passes. The binary
#: and the distribution are spelled differently for `rg`, and
#: `version_mismatch` already knows that mapping — this list is only who
#: to ask.
TOOLS = ("ruff", "ty", "pytest", "rg")

#: Where the harness pins those tools, and where a finding about one
#: lies: in the repository, not in any skill.
HARNESS = Location(file="pyproject.toml")

#: The asset whose interpreter is compared.
WORKFLOW = "assets/ci.yml"

#: The asset whose tool requirements are compared.
PROJECT = "assets/pyproject.toml"

#: A release's position in the order `_sort_key` defines.
type SortKey = tuple[int, int, int, int, int]

# The branches a finding of this check comes from.
TOOL_ABSENT = Branch("pins", "tool_absent")
TOOL_SILENT = Branch("pins", "tool_silent")
TOOL_MISMATCH = Branch("pins", "tool_mismatch")
INDEX_SILENT = Branch("pins", "index_silent")
INDEX_UNREAD = Branch("pins", "index_unread")
INDEX_UNORDERED = Branch("pins", "index_unordered")
TOOL_STALE = Branch("pins", "tool_stale")
LOCAL_NO_REASON = Branch("pins", "local_no_reason")
LOCAL_SILENT = Branch("pins", "local_silent")
LOCAL_MOVED = Branch("pins", "local_moved")
RUST_UNREADABLE = Branch("pins", "rust_unreadable")
RUSTC_SILENT = Branch("pins", "rustc_silent")
RUSTC_DIFFERS = Branch("pins", "rustc_differs")
STABLE_SILENT = Branch("pins", "stable_silent")
RUST_STALE = Branch("pins", "rust_stale")
LIBRARY_INEXACT = Branch("pins", "library_inexact")
CRATES_SILENT = Branch("pins", "crates_silent")
LIBRARY_UNORDERED = Branch("pins", "library_unordered")
LIBRARY_STALE = Branch("pins", "library_stale")
INTERPRETER_ID = Branch("pins", "interpreter_id")
WORKFLOW_NONE = Branch("pins", "workflow_none")
WORKFLOW_OTHER = Branch("pins", "workflow_other")
PROJECT_UNPARSED = Branch("pins", "project_unparsed")
PROJECT_PIN = Branch("pins", "project_pin")
UV_ABSENT = Branch("pins", "uv_absent")
UV_SILENT = Branch("pins", "uv_silent")
INTERPRETER_UNORDERED = Branch("pins", "interpreter_unordered")
RELEASE_UNORDERED = Branch("pins", "release_unordered")
INTERPRETER_STALE = Branch("pins", "interpreter_stale")


def _tool_pins() -> Iterator[Finding]:
    """Each tool pin against the running version and the newest release.

    Both directions, because they fail differently. A running version
    that is not the pinned one means every claim about what was verified
    is false. A pin the index has moved past means the claim is still
    true and going stale, and moving it is a reviewed event rather than
    a note nobody reads.
    """
    for tool in TOOLS:
        if not have(tool) or (located := tool_path(tool)) is None:
            yield unrun(
                f"`{tool}` is not available, so its pin was not verified",
                HARNESS,
                TOOL_ABSENT,
            )
            continue
        answered = run([located, "--version"], timeout=30)
        if not answered.ok:
            yield unrun(f"`{tool}` did not answer `--version`", HARNESS, TOOL_SILENT)
            continue
        if complaint := version_mismatch(tool, answered.out):
            yield fail(complaint, HARNESS, TOOL_MISMATCH)
            continue

        pinned = pinned_version(tool)
        package = PACKAGE.get(tool, tool)
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
                HARNESS,
                INDEX_SILENT,
            )
            continue
        found = re.search(
            rf"^{re.escape(package)}==(\S+)", resolved.out, re.MULTILINE | re.IGNORECASE
        )
        if not found:
            yield unrun(
                f"could not read a version for `{package}` from the index",
                HARNESS,
                INDEX_UNREAD,
            )
            continue
        newest = found.group(1)
        here, there = _sort_key(pinned), _sort_key(newest)
        if here is None or there is None:
            yield unrun(
                f"`{package}` was not compared: "
                f"{(newest if there is None else pinned)!r} is not a version "
                "this can order, and a release it cannot order is not one it "
                "has ruled out",
                HARNESS,
                INDEX_UNORDERED,
            )
            continue
        if there > here:
            yield fail(
                f"`{tool}` is pinned to {pinned} and {newest} is available — "
                "move the pin in `pyproject.toml`, re-run the suite, and read "
                "what moved before trusting it",
                HARNESS,
                TOOL_STALE,
            )


#: `cpython-3.15.0rc1+freethreaded-macos-aarch64-none` -> ("3.15.0rc1",
#: True)
RELEASE = re.compile(
    r"^cpython-(?P<version>\d+\.\d+\.\d+[a-z0-9]*)(?P<ft>\+freethreaded)?-"
)


def _sort_key(version: str) -> SortKey | None:
    """Order releases so a final release follows its candidates.

    `3.15.0rc2` follows `3.15.0rc1` and precedes `3.15.0`. A final
    release has no suffix and must sort *after* every candidate, which a
    plain string comparison gets backwards.

    `None` for a version this does not understand, because the
    alternative was `(0, 0, 0, 0, 0)` — which sorts below every real
    release, so `1.2.3.post1` from the index compared as older than the
    pin and the staleness check reported the pin current. That is the
    same shape `version_mismatch` was already fixed for: a value that
    could not be read must not be resolved into one that happens to
    compare as agreement.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$", version)
    if not m:
        return None
    major, minor, micro = (int(group(m, i)) for i in (1, 2, 3))
    rank = {"a": 0, "b": 1, "rc": 2}.get(group(m, 4), 3)
    return (major, minor, micro, rank, int(group(m, 5) or 0))


def local_pin(profile: Profile, where: Location) -> Iterator[Finding]:
    """A pin that follows the local toolchain, if it should move.

    Compared with the running version only. Upstream releasing something
    newer is not a finding — the standard is verified against what runs
    here, and that has not changed. The local toolchain moving past the
    pin is: the claim that the examples were verified on this version
    has just stopped being true.
    """
    reason = profile.follows_local
    if reason is None:
        return
    if not reason.strip():
        yield fail(
            f"{profile.name} follows the local toolchain and gives no reason why",
            where,
            LOCAL_NO_REASON,
        )
        return
    pinned, running = profile.pin(), profile.running_version()
    if not running:
        yield unrun(
            "could not ask the local toolchain which version runs, "
            f"so `{pinned}` was not compared",
            where,
            LOCAL_SILENT,
        )
    elif running != pinned:
        moved = f"follows this machine's toolchain, which is now {running}"
        yield fail(
            f"{profile.name} is pinned to {pinned} and {moved} — the cue to bump it",
            where,
            LOCAL_MOVED,
        )


#: Where the Rust project publishes what the current stable release is.
STABLE = "https://static.rust-lang.org/dist/channel-rust-stable.toml"


def rust_pin(
    pinned: str, running: str, newest: str, where: Location
) -> Iterator[Finding]:
    """What is wrong with a `rust-version` pin, if anything.

    Compared at the pin's own precision. `running` is what `rustc -V`
    reports and `newest` what the stable channel names; either is ""
    when it could not be asked.
    """
    want = _minor(pinned)
    if want is None:
        yield fail(
            f"the Rust pin `{pinned}` is not a version this can compare",
            where,
            RUST_UNREADABLE,
        )
        return
    if not running:
        yield unrun(
            "could not ask `rustc` its version, "
            f"so the Rust pin {pinned} was not compared",
            where,
            RUSTC_SILENT,
        )
    elif _minor(running) != want:
        yield fail(
            f"the examples are pinned to Rust {pinned} and `rustc` here is {running}",
            where,
            RUSTC_DIFFERS,
        )
    if not newest:
        yield unrun(
            "the stable channel did not answer, "
            "so the Rust pin was not compared with it",
            where,
            STABLE_SILENT,
        )
    elif (there := _minor(newest)) is not None and there > want:
        yield fail(
            f"the Rust pin is {pinned} and {newest} is stable — move "
            "`rust_version` in `lang/rust.py` and the assets, re-read the "
            "release notes, and re-run the suite",
            where,
            RUST_STALE,
        )


def _minor(version: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d+)\.(\d+)", version)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _rustc() -> str:
    if not have("rustc"):
        return ""
    answered = run(["rustc", "-V"], timeout=30)
    return group(re.match(r"^rustc (\S+)", answered.out)) if answered.ok else ""


@cache
def _stable() -> str:
    """What the stable channel names, asked once a run.

    `pins` reads every skill even when a control broke one of them, so
    two Rust skills and four pin controls would otherwise ask the
    network the same question ten times.
    """
    try:
        with urllib.request.urlopen(STABLE, timeout=30) as response:
            text = response.read().decode()
    except OSError:
        return ""
    return group(re.search(r'^\[pkg\.rust\]\nversion = "(\S+)', text, re.MULTILINE))


def library_pin(
    name: str, requirement: str, newest: str, where: Location
) -> Iterator[Finding]:
    """What is wrong with the pin on the library the examples use.

    The requirement must be exact (`=0.20.0`): a caret requirement lets
    the resolver pick a release the examples were never compiled
    against, so the running version would no longer be the pinned one.
    """
    if not requirement.startswith("="):
        stated = f"is `{requirement}`" if requirement else "names no version"
        yield fail(
            f"`{name}` must be pinned exactly (`=x.y.z`), and {stated}",
            where,
            LIBRARY_INEXACT,
        )
        return
    pinned = requirement.removeprefix("=")
    if not newest:
        yield unrun(
            f"crates.io did not answer, so the `{name}` pin {pinned} was not compared",
            where,
            CRATES_SILENT,
        )
        return
    here, there = _sort_key(pinned), _sort_key(newest)
    if here is None or there is None:
        yield unrun(
            f"`{name}` was not compared: {pinned} or {newest} is not a "
            "version this orders",
            where,
            LIBRARY_UNORDERED,
        )
    elif there > here:
        yield fail(
            f"`{name}` is pinned to {pinned} and {newest} is released — move "
            "the pin in `lang/rust.py` and the assets, read the migration "
            "guide, and re-run the suite",
            where,
            LIBRARY_STALE,
        )


def _requirement(crate: Crate | None, name: str) -> str:
    for dep in crate.dependencies if crate else ():
        if m := re.match(rf'{re.escape(name)} = \{{ version = "([^"]+)"', dep):
            return group(m)
    return ""


@cache
def _crates_io(name: str) -> str:
    """The newest release of crate `name`, asked once a run."""
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"https://crates.io/api/v1/crates/{name}",
                headers={"User-Agent": "agent-skill pins check"},
            ),
            timeout=30,
        ) as response:
            newest = json.load(response)["crate"]["max_stable_version"]
    except OSError, KeyError, ValueError:
        return ""
    # An answer that is not a version string is no answer, the same as
    # one that never arrived.
    return newest if isinstance(newest, str) else ""


@check(
    "pins",
    "a superseded pin is a finding, not a diary entry",
    needs=("uv", "ruff", "ty", "pytest", "rg", "zig", "rustc"),
)
def pins(tree: Tree) -> Iterator[Finding]:
    """Each skill's pins and the harness's, against what runs and ships.

    The harness's tool pins are asked once, when a skill verified with
    those tools is read; they pin the repository rather than a skill,
    so their findings lie in no skill.
    """
    yield from per_skill(_skill_pins)(tree)
    if any(skill.profile.toolchain == "python" for skill in tree):
        yield from _tool_pins()


def _skill_pins(skill: Skill) -> Iterator[Finding]:
    """One skill's pins, against what runs and what exists."""
    yield from _subject_pins(skill)
    if skill.profile.toolchain != "python":
        return
    m = RELEASE.match(f"{INTERPRETER}-")
    if not m:
        yield fail(
            f"the pin `{INTERPRETER}` is not a release identifier",
            skill.at(),
            INTERPRETER_ID,
        )
        return
    pinned, want_ft = m["version"], bool(m["ft"])
    yield from _asset_pins(skill)
    yield from _interpreter_pin(skill, pinned, want_ft=want_ft)


def _subject_pins(skill: Skill) -> Iterator[Finding]:
    """Pins on the standard's subject: its toolchain and its library."""
    where = skill.at()
    yield from local_pin(skill.profile, where)
    if skill.profile.crate is not None:
        rust = skill.profile.crate.rust_version
        yield from rust_pin(rust, _rustc(), _stable(), where)
    if name := skill.profile.library:
        requirement = _requirement(skill.profile.crate, name)
        yield from library_pin(name, requirement, _crates_io(name), where)


def _asset_pins(skill: Skill) -> Iterator[Finding]:
    """What the assets install, against what the harness verifies."""
    # Two declarations, compared — the harness verifies against one and
    # the reader copies the other, so an asset that installs a different
    # build than the one these examples were verified on is the defect
    # this half exists to catch.
    workflow = skill.root / WORKFLOW
    if workflow.exists():
        yield from workflow_pins(workflow.read_text(), INTERPRETER, skill.at(WORKFLOW))

    # Two declarations, compared — the same reason the interpreter half
    # exists. The harness verifies against one pin and the reader
    # installs the other, so an asset naming a different version hands
    # them a build these examples were never checked on.
    shipped = skill.root / PROJECT
    if shipped.exists():
        try:
            project = tomllib.loads(shipped.read_text())
        except tomllib.TOMLDecodeError:
            yield unrun(
                "does not parse (`assets` says where), so no pin in it was compared",
                skill.at(PROJECT),
                PROJECT_UNPARSED,
            )
            return
        harness = {PACKAGE.get(tool, tool): pinned_version(tool) for tool in TOOLS}
        yield from project_pins(project, harness, skill.at(PROJECT))


def workflow_pins(text: str, interpreter: str, where: Location) -> Iterator[Finding]:
    """What is wrong with the interpreter a workflow installs, if any.

    It must install `interpreter` with `uv python install`, and nothing
    else. Comparing only the lines that were there passed a workflow
    with none: the runner's own interpreter then runs every job, which
    is the one build nobody verified anything on.
    """
    stated = set(re.findall(r"uv python install (\S+)", text))
    if not stated:
        yield fail(
            f"installs no interpreter with `uv python install`, so a reader runs "
            f"whatever the runner has rather than `{interpreter}`",
            where,
            WORKFLOW_NONE,
        )
    for named in sorted(stated - {interpreter}):
        yield fail(
            f"installs `{named}` where the harness verifies against "
            f"`{interpreter}` — a reader would not be running what this was "
            "checked on",
            where,
            WORKFLOW_OTHER,
        )


#: `ty>=0.0.60`, `ruff [extra] == 0.17.3 ; python_version >= "3.15"`:
#: the name, then the version clauses up to any marker.
REQUIREMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;]*)"
)


def project_pins(
    project: dict[str, Any], harness: dict[str, str], where: Location
) -> Iterator[Finding]:
    """Each requirement on a harness tool that is not exactly its pin.

    `harness` maps a distribution to the version the harness verifies
    against. Only `==` that version will do: a floor such as
    `ty>=0.0.60` lets the resolver hand the reader any build at all,
    and it passed, because only a requirement already spelled `==` was
    compared.
    """
    for requirement in _requirements(project):
        m = REQUIREMENT.match(requirement)
        if m is None:
            continue
        name = m["name"].lower().replace("_", "-")
        want = harness.get(name)
        if want is None:
            continue
        spec = "".join(m["spec"].split())
        if spec != f"=={want}":
            yield fail(
                f"requires `{requirement}` where the harness verifies against "
                f"`{name}=={want}` — anything but that exact pin lets a reader "
                "resolve a build this was never checked on",
                where,
                PROJECT_PIN,
            )


def _requirements(project: dict[str, Any]) -> Iterator[str]:
    """Every requirement string a `pyproject.toml` declares.

    The build system's, the project's, its extras' and its dependency
    groups'. An `include-group` table is not a requirement.
    """
    lists: list[object] = [
        project.get("build-system", {}).get("requires", []),
        project.get("project", {}).get("dependencies", []),
        *project.get("project", {}).get("optional-dependencies", {}).values(),
        *project.get("dependency-groups", {}).values(),
    ]
    for entries in lists:
        if isinstance(entries, list):
            yield from (e for e in entries if isinstance(e, str))


def _interpreter_pin(skill: Skill, pinned: str, *, want_ft: bool) -> Iterator[Finding]:
    """The interpreter pin against what `uv` offers in its series."""
    if not have("uv"):
        yield unrun(
            "`uv` is not on PATH, so no release list was consulted",
            skill.at(),
            UV_ABSENT,
        )
        return
    r = run(["uv", "python", "list", "--all-versions"], timeout=120)
    if not r.out:
        yield unrun(
            "`uv python list` returned nothing to compare against",
            skill.at(),
            UV_SILENT,
        )
        return

    # Scoped to the pinned minor series on purpose: a newer patch or
    # candidate is a pin refresh, and a newer *minor* is a deliberate
    # change of target that this check has no business demanding.
    series = ".".join(pinned.split(".")[:2])  # 3.15.0rc1 -> 3.15
    here = _sort_key(pinned)
    if here is None:
        yield fail(
            f"the pin `{INTERPRETER}` carries a version this cannot order",
            skill.at(),
            INTERPRETER_UNORDERED,
        )
        return

    newer, unreadable = _releases(r.out, series, here, want_ft=want_ft)
    if unreadable:
        yield unrun(
            f"`uv python list` offers {', '.join(sorted(unreadable))} in the {series} "
            f"series, which this cannot order against `{pinned}` — a release it cannot "
            f"compare is not a release it has ruled out",
            skill.at(),
            RELEASE_UNORDERED,
        )

    if newer:
        best = max(newer, key=newer.__getitem__)
        yield fail(
            f"the interpreter pin is `{pinned}` and `{best}` is available — move it in "
            "`lang/python.py` and `assets/ci.yml`, re-verify the PS-MIG table "
            "against the released What's New, and re-run the suite",
            skill.at(),
            INTERPRETER_STALE,
        )


def _releases(
    listing: str, series: str, here: SortKey, *, want_ft: bool
) -> tuple[dict[str, SortKey], set[str]]:
    """Releases in `series` newer than `here`, and any it cannot order.

    Newer ones map to their order, so the best is picked without
    ordering by a key function that is allowed to answer `None`.
    """
    newer: dict[str, SortKey] = {}
    unreadable: set[str] = set()
    for line in listing.split("\n"):
        found = RELEASE.match(line.strip())
        if not found or bool(found["ft"]) != want_ft:
            continue
        version = found["version"]
        if not version.startswith(f"{series}."):
            continue
        # Scoped to the pinned series, so this reports what it could not
        # rule out rather than every oddity in a list of every CPython
        # ever built.
        order = _sort_key(version)
        if order is None:
            unreadable.add(version)
        elif order > here:
            newer[version] = order
    return newer, unreadable
