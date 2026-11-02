"""A check that could not look must not report success.

`UNRUN` exists because a missing tool and a clean tree produce the same
silence. The guarantee is only worth what it covers, and the coverage
used to be a three-entry list written by hand: it named `assets`,
`citations` and `pins` while `crossref`, `self-application` and
`sensitivity` had all become tool-dependent without anyone adding them,
and `pins` was listed as needing `uv` alone after acquiring four more.

So the list is not written any more. Each check declares what it needs,
and this runs over the declarations. Two cross-checks keep them honest:
one reads what the source visibly asks for, and one runs every check and
records every tool it reaches for — through any module, by any route.

A tool is made absent the way it would be: `tool_path` cannot find it
and a command naming it does not start. Replacing `tool_path` alone left
every `run(["ruff", …])` running the real binary while the test called
`ruff` absent, and answered every present tool with a path that does
not exist.
"""

import inspect
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
lazy from collections.abc import Callable

import pytest

import agent_skill.proc
from agent_skill.checks import all_checks, by_name
from agent_skill.lang import toolchain_for
from agent_skill.model import Tree
from agent_skill.report import Level
lazy from agent_skill.checks import Check
lazy from agent_skill.model import Skill

#: What the audit that motivated this found. The declared set may grow;
#: it may not shrink past this. A derivation that quietly stops finding
#: subjects passes every assertion made about it, which is the failure a
#: derived list introduces and the reason this floor is written down
#: rather than computed.
FLOOR = {
    "assets",
    "citations",
    "crossref",
    "mutation",
    "pins",
    "self-application",
    "sensitivity",
    "toolchain",
}

#: `have("x")`, `tool_path("x")`, and a command that names its binary:
#: `run(["ruff", …])`.
TOOL_CALL = re.compile(
    r'(?:have|tool_path)\("([a-z][a-z-]*)"\)|\brun\(\s*\[\s*"([a-z][a-z-]*)"'
)

#: Checks the recording below does not run, and why.
NOT_RECORDED = {
    "controls": (
        "it runs every other check over a copy of the tree, so what it reaches "
        "for is theirs; a control whose check could not run is UNRUN there"
    ),
}

REAL_POPEN = subprocess.Popen
REAL_TOOL_PATH = agent_skill.proc.tool_path


@dataclass
class Absent:
    """Tools made absent, and every tool asked for while they were."""

    gone: Callable[[str], bool]
    asked: set[str] = field(default_factory=set)

    def tool_path(self, name: str) -> str | None:
        """Where `name` really is, or None when it is gone."""
        self.asked.add(name)
        return None if self.gone(name) else REAL_TOOL_PATH(name)

    def popen(self, cmd: list[str], *args: object, **kwargs: object) -> object:
        """Start `cmd`, unless the binary it names is gone.

        A gone binary fails to start, exactly as a missing one does,
        and `run` reports that as status 127.
        """
        binary = str(cmd[0])
        if "/" not in binary:
            self.asked.add(binary)
        if self.gone(Path(binary).name):
            raise FileNotFoundError(binary)
        return REAL_POPEN(cmd, *args, **kwargs)  # ty: ignore[no-matching-overload] — what `run` passed, passed on


def absent(monkeypatch: pytest.MonkeyPatch, gone: Callable[[str], bool]) -> Absent:
    """Make the tools `gone` names absent, by every route to them."""
    shim = Absent(gone)
    monkeypatch.setattr(agent_skill.proc, "tool_path", shim.tool_path)
    monkeypatch.setattr(subprocess, "Popen", shim.popen)
    return shim


def declaring() -> list[Check]:
    return [c for c in all_checks() if c.needs]


def test_the_declared_set_covers_the_floor() -> None:
    declared = {c.name for c in declaring()}
    assert declared >= FLOOR, (
        "checks known to need a tool are no longer declaring one: "
        f"{sorted(FLOOR - declared)}"
    )


def source_of(check: Check) -> Path:
    """The file a check was defined in, asked of the function itself.

    This used to search `checks/*.py` for the literal `@check("<name>"`,
    and skip on a miss. Three of the six checks that declare a tool
    spell the decorator across two lines, so `crossref`, `pins` and
    `sensitivity` were all silently uncovered — `pins` included, which
    is the case the docstring below names as the reason this cross-check
    exists.

    A subject that cannot be located is a failure of the guarantee, not
    an omission from it: a check skipped here is indistinguishable from
    a check that passed.
    """
    found = inspect.getsourcefile(inspect.unwrap(check.fn))
    assert found is not None, (
        f"{check.name} has no source file, so nothing can be read from it"
    )
    return Path(found)


@pytest.mark.parametrize("check", [c.name for c in all_checks()], ids=lambda n: n)
def test_a_declaration_is_not_missing_a_tool(check: str) -> None:
    """Every tool the source visibly asks for must be declared.

    Every check, not only those that already declare something: a check
    that grew its first `have("x")` was exactly the one nobody read.
    Inspection is the weaker of the two cross-checks — `pins` asks
    `have(tool)` in a loop, so reading it finds `uv` and nothing else —
    and the recording below is the stronger one.
    """
    target = by_name(check)
    assert target is not None
    seen = {a or b for a, b in TOOL_CALL.findall(source_of(target).read_text())}
    assert seen <= set(target.needs), (
        f"{check} names {sorted(seen - set(target.needs))} but does not declare it — "
        "the guarantee runs over the declaration, so an undeclared tool is uncovered"
    )


def test_every_declaring_check_is_actually_read() -> None:
    """The cross-check is worth what it covers; it used to cover half.

    Resolution by source text meant a subject's coverage depended on how
    its decorator happened to be formatted. Asserted here rather than
    left implicit in the loop above, because a lookup that silently
    finds nothing makes every assertion over it pass.
    """
    subjects = declaring()
    assert {c.name for c in subjects} >= FLOOR
    for c in subjects:
        text = source_of(c).read_text()
        assert f'"{c.name}"' in text, (
            f"{c.name} was resolved to {source_of(c).name}, which does not name it — "
            f"the cross-check would be reading the wrong file"
        )


@pytest.mark.parametrize(
    "check",
    [c.name for c in all_checks() if c.name not in NOT_RECORDED],
    ids=lambda n: n,
)
def test_every_tool_a_check_reaches_for_is_declared(
    check: str, skills: list[Skill], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recorded, not read: every lookup and every command, by any route.

    A slow check runs with every tool absent, so it stops at the tools
    it asks for before compiling anything; the rest run as they are.
    """
    target = by_name(check)
    assert target is not None
    shim = absent(monkeypatch, lambda _name: target.slow)
    target.run(Tree.of(skills))
    assert shim.asked <= set(target.needs), (
        f"{check} reached for {sorted(shim.asked - set(target.needs))} and does "
        "not declare it — with that tool missing, nothing withholds its pass"
    )


def test_every_recorded_exemption_names_a_check() -> None:
    known = {c.name for c in all_checks()}
    assert set(NOT_RECORDED) <= known


def subjects(target: Check, tool: str, skills: list[Skill]) -> list[Skill]:
    """The skills to run `target` over with `tool` absent.

    All of them, unless the check compiles every example: then only the
    skills whose toolchain names `tool` among what it misses, so the run
    stops there instead of compiling every other skill's examples.
    """
    if not target.slow:
        return skills
    return [
        s
        for s in skills
        if (tc := toolchain_for(s.profile.toolchain))
        and any(f"`{tool}`" in what for what in tc.missing())
    ]


@pytest.mark.parametrize(
    ("check", "tool"),
    [(c.name, tool) for c in declaring() for tool in c.needs],
    ids=lambda v: v,
)
def test_a_missing_tool_withholds_the_pass(
    check: str, tool: str, skills: list[Skill], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tool a check declares, removed one at a time."""
    target = by_name(check)
    assert target is not None, f"{check} is registered"
    absent(monkeypatch, lambda name: name == tool)
    over = subjects(target, tool, skills)
    assert over, f"no skill's toolchain needs `{tool}`, so declaring it covers nothing"

    result = target.run(Tree.of(over))

    assert any(f.level is Level.UNRUN for f in result.findings), (
        f"{check} reported nothing at UNRUN with `{tool}` absent — "
        f"a NOTE here lets the run report success while nothing looked"
    )
    assert not result.ok, f"{check} kept the pass with `{tool}` absent"
