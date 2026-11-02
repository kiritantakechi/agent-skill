"""`agent-skill` itself: what it refuses, and what each check reads."""

lazy from collections.abc import Iterator, Sequence

import pytest

from agent_skill import cli
from agent_skill.checks import Check
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding


def test_an_unknown_check_is_refused_not_passed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check", "--only", "no-such-check"]) == 2
    out, err = capsys.readouterr()
    assert "ALL CHECKS PASSED" not in out
    assert "no-such-check" in err
    assert "anatomy" in err


@pytest.mark.parametrize("command", ["check", "fmt"])
def test_an_unknown_skill_is_refused_with_the_names_there_are(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([command, "--skill", "no-such-style"]) == 2
    err = capsys.readouterr().err
    assert "no-such-style" in err
    assert "python-style" in err


def test_skill_narrows_only_the_checks_that_read_one_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    given: dict[str, list[str]] = {}

    def across(skills: Sequence[Skill]) -> Iterator[Finding]:
        given["across"] = [s.name for s in skills]
        yield from ()

    def each(skill: Skill) -> Iterator[Finding]:
        given.setdefault("each", []).append(skill.name)
        yield from ()

    fakes = [Check("across", "x", across, scope="all"), Check("each", "x", each)]
    monkeypatch.setattr(cli, "all_checks", lambda: fakes)

    assert cli.main(["check", "--skill", "bevy-style"]) == 0
    assert given["each"] == ["bevy-style"]
    assert given["across"] == ["bevy-style", "python-style", "rust-style", "zig-style"]
