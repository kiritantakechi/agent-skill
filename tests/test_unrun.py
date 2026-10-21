"""A check that could not look must not report success.

`UNRUN` exists because a missing tool and a clean tree produce the same
silence. The guarantee is only worth what it covers, and the coverage
used to be a three-entry list written by hand: it named `assets`,
`citations` and `pins` while `crossref`, `self-application` and
`sensitivity` had all become tool-dependent without anyone adding them,
and `pins` was listed as needing `uv` alone after acquiring four more.

So the list is not written any more. Each check declares what it needs,
this runs over the declarations, and
`test_a_declaration_is_not_missing_a_tool` compares those declarations
against what the source visibly asks for.
"""

import inspect
import re
from pathlib import Path

import pytest

import agent_skill.proc
from agent_skill.checks import all_checks, by_name
from agent_skill.report import Level
lazy from agent_skill.checks import Check
lazy from agent_skill.model import Skill

#: What the audit that motivated this found. The declared set may grow;
#: it may not shrink past this. A derivation that quietly stops finding
#: subjects passes every assertion made about it, which is the failure a
#: derived list introduces and the reason this floor is written down
#: rather than computed.
FLOOR = {"assets", "citations", "crossref", "pins", "self-application", "sensitivity"}

TOOL_CALL = re.compile(r'have\("([a-z]+)"\)|tool_path\("([a-z]+)"\)')


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
    found = inspect.getsourcefile(check.fn)
    assert found is not None, (
        f"{check.name} has no source file, so nothing can be read from it"
    )
    return Path(found)


def test_a_declaration_is_not_missing_a_tool() -> None:
    """Every tool the source visibly asks for must be declared.

    Inspection is the weaker of the two — `pins` asks `have(tool)` in a
    loop, so reading it finds `uv` and nothing else — which is why it is
    the cross-check and not the source of truth. It catches the one
    thing a declaration cannot: someone adding a `have("x")` and
    forgetting to say so.
    """
    for c in declaring():
        seen = {a or b for a, b in TOOL_CALL.findall(source_of(c).read_text())}
        assert seen <= set(c.needs), (
            f"{c.name} calls {sorted(seen - set(c.needs))} but does not declare it — "
            "the guarantee runs over the declaration, "
            "so an undeclared tool is uncovered"
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


@pytest.mark.parametrize("check", [c.name for c in declaring()], ids=lambda n: n)
def test_a_missing_tool_withholds_the_pass(
    check: str, skills: list[Skill], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every tool a check declares, removed one at a time."""
    target = by_name(check)
    assert target is not None, f"{check} is registered"
    for tool in target.needs:
        monkeypatch.setattr(
            agent_skill.proc,
            "tool_path",
            lambda name, absent=tool: None if name == absent else f"/usr/bin/{name}",
        )
        result = target.run(skills)

        assert any(f.level is Level.UNRUN for f in result.findings), (
            f"{check} reported nothing at UNRUN with `{tool}` absent — "
            f"a NOTE here lets the run report success while nothing looked"
        )
        assert not result.ok, f"{check} kept the pass with `{tool}` absent"
