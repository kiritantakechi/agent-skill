"""One policy for every toolchain's steps and mutants, in one driver.

A step that did not finish is a failure, with a message; a mutant whose
tests did not finish is inconclusive, never killed; a survivor is a
note; and whatever a tool names a line of, the finding names the
markdown line.
"""

import re
from dataclasses import replace
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from agent_skill.checks.toolchain import mutate, verify
from agent_skill.lang import Extraction, toolchain_for
from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.lang.rust import RUST_STYLE
from agent_skill.lang.zig import ZIG_STYLE
from agent_skill.proc import Ran
from agent_skill.report import Level
from structure_fixture import DEMO, build, reparse
lazy from agent_skill.lang import Config, Toolchain
lazy from agent_skill.report import Finding

PASSED = Ran(0, "", "", timed_out=False)
HUNG = Ran(None, "", "", timed_out=True)


def answers(*ran: Ran) -> Callable[..., Ran]:
    """A `run` answering with each of `ran` in turn, then the last."""
    queue = list(ran)

    def fake(*_: object, **__: object) -> Ran:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return fake


def levels(findings: list[Finding]) -> set[Level]:
    return {f.level for f in findings}


RUST_BLOCK = """// verified
pub fn bump(v: &mut u32) {
    *v += 1;
}

#[cfg(test)]
mod tests {
    #[test]
    fn bumps() {}
}
"""

ZIG_BLOCK = """// verified
const std = @import("std");

fn bump(v: *u32) void {
    v.* += 1;
}

test "bump" {
    var v: u32 = 0;
    bump(&v);
    try std.testing.expect(v == 1);
}
"""

PYTHON_BLOCK = """# verified
def bump(v: int) -> int:
    v = v + 1
    return v


def test_bump() -> None:
    assert bump(0) == 1
"""

#: Each toolchain's settings, its fence, and a block that ships a test
#: with one statement outside it worth deleting, on body line 2 or 3.
KINDS = {
    "python": (PYTHON_STYLE, "python", PYTHON_BLOCK),
    "rust": (RUST_STYLE, "rust", RUST_BLOCK),
    "zig": (ZIG_STYLE, "zig", ZIG_BLOCK),
}


def extraction(tmp_path: Path, kind: str) -> tuple[Toolchain, Extraction]:
    """A demo standard holding one block of `kind`, extracted."""
    config, fence, body = KINDS[kind]
    profile = replace(DEMO, languages=(fence,), toolchain=config)
    demo = build(tmp_path, profile)
    chapter = demo.root / "references" / "errors.md"
    chapter.write_text(f"{chapter.read_text()}\n```{fence}\n{body}```\n")
    tc = _toolchain(config)
    return tc, tc.extract(reparse(demo), tmp_path / "out")


def _toolchain(config: Config) -> Toolchain:
    tc = toolchain_for(config)
    assert tc is not None
    return tc


@pytest.mark.parametrize("kind", KINDS)
def test_a_step_that_times_out_fails_with_its_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    tc, ex = extraction(tmp_path, kind)
    monkeypatch.setattr("agent_skill.lang.run", answers(HUNG))
    found = list(verify(tc, ex))
    assert found
    assert levels(found) == {Level.FAIL}
    assert all(re.fullmatch(r".+ did not finish in \d+s", f.message) for f in found)


def test_every_rust_step_is_named_when_it_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tc, ex = extraction(tmp_path, "rust")
    monkeypatch.setattr("agent_skill.lang.run", answers(HUNG))
    assert [f.message for f in verify(tc, ex)] == [
        f"{step} did not finish in 900s"
        for step in ("compiles", "clippy", "tests", "intra-doc links", "rustfmt")
    ]


def test_a_failure_with_no_output_still_says_something(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tc, ex = extraction(tmp_path, "rust")
    monkeypatch.setattr(
        "agent_skill.lang.run", answers(Ran(101, "", "", timed_out=False))
    )
    found = list(verify(tc, ex))
    assert {f.message for f in found} >= {"compiles: exited 101 and said nothing"}


def test_a_formatter_that_times_out_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tc, ex = extraction(tmp_path, "zig")

    def fake(cmd: list[str], **_: object) -> Ran:
        return HUNG if cmd[1] == "fmt" else PASSED

    monkeypatch.setattr("agent_skill.lang.run", fake)
    (finding,) = verify(tc, ex)
    assert finding.level is Level.FAIL
    assert finding.message == "zig fmt did not finish in 180s"


def test_a_unit_stops_at_its_first_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test of a block that does not build only reports that again."""
    tc, ex = extraction(tmp_path, "zig")
    ran: list[str] = []

    def fake(cmd: list[str], **_: object) -> Ran:
        ran.append(cmd[1])
        return Ran(1, "", "error: no", timed_out=False)

    monkeypatch.setattr("agent_skill.lang.run", fake)
    found = list(verify(tc, ex))
    assert ran == ["build-obj", "fmt"]
    assert [f.message for f in found] == ["build-obj: error: no", "zig fmt: error: no"]


@pytest.mark.parametrize("kind", KINDS)
def test_a_diagnostic_lies_on_the_markdown_line_it_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Every language, Rust's module files included."""
    tc, ex = extraction(tmp_path, kind)
    (unit,) = ex.units
    named = unit.path.relative_to(ex.root).as_posix()
    said = Ran(1, "", f"{named}:3:5: error: no such thing", timed_out=False)
    monkeypatch.setattr("agent_skill.lang.run", answers(said))
    # A step whose tool prints no lines says it whole, coordinates and
    # all, at what it ran.
    found = list(verify(tc, ex))
    located = [
        f
        for f in found
        if f.message.endswith("no such thing") and ":3:5:" not in f.message
    ]
    assert located
    assert {f.where.line for f in located} == {unit.block.line + 2}


@pytest.mark.parametrize("kind", KINDS)
def test_a_mutant_that_times_out_is_inconclusive_never_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """The first run is the unmutated one."""
    tc, ex = extraction(tmp_path, kind)
    monkeypatch.setattr("agent_skill.lang.run", answers(PASSED, HUNG))
    found = list(mutate(tc, ex))
    assert found
    assert levels(found) == {Level.NOTE}
    assert all("timed out — inconclusive" in f.message for f in found)


@pytest.mark.parametrize("kind", KINDS)
def test_a_survivor_is_a_note_at_its_markdown_line_in_every_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """One rule, one coordinate system: not, for Rust, the crate's."""
    tc, ex = extraction(tmp_path, kind)
    (unit,) = ex.units
    monkeypatch.setattr("agent_skill.lang.run", answers(PASSED))
    found = list(mutate(tc, ex))
    assert found
    assert levels(found) == {Level.NOTE}
    lines = unit.block.body.split("\n")
    for f in found:
        assert f.where.line is not None
        deleted = lines[f.where.line - unit.block.line].strip()
        assert f.message == f"`{deleted}` can be deleted and every test still passes"


def test_a_survivor_is_asked_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second opinion stands between a transient and a survivor."""
    tc, ex = extraction(tmp_path, "zig")
    monkeypatch.setattr(
        "agent_skill.lang.run", answers(PASSED, PASSED, Ran(1, "", "", timed_out=False))
    )
    assert list(mutate(tc, ex)) == []


def test_unmutated_tests_that_fail_are_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing was mutated, which is not every test pinned."""
    tc, ex = extraction(tmp_path, "python")
    monkeypatch.setattr(
        "agent_skill.lang.run", answers(Ran(1, "", "E  boom", timed_out=False))
    )
    (finding,) = mutate(tc, ex)
    assert finding.level is Level.FAIL
    assert finding.message == "the unmutated tests: E  boom"
