"""A timeout reads the same in every toolchain.

A verification step that did not finish is a failure, with a message;
a mutant whose tests did not finish is inconclusive, never killed.
"""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from agent_skill.lang import Extraction, Unit, python, rust, zig
from agent_skill.lang.rust import RUST, RUST_STYLE
from agent_skill.proc import Ran
from agent_skill.report import Level
lazy from agent_skill.lang import Toolchain
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


def unit(tmp_path: Path, name: str, source: str) -> Extraction:
    path = tmp_path / name
    path.write_text(source)
    return Extraction(tmp_path, [Unit(path, "x.md", 1, "DS-X-01")])


def crate(tmp_path: Path) -> Extraction:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.rs").write_text(
        "pub mod ds_x_01 {\n"
        "    pub fn bump(v: &mut u32) {\n"
        "        *v += 1;\n"
        "    }\n"
        "    #[cfg(test)]\n"
        "    mod tests {}\n"
        "}\n"
    )
    return Extraction(tmp_path, crate=RUST_STYLE)


ZIG_BLOCK = """const std = @import("std");

fn bump(v: *u32) void {
    v.* += 1;
}

test "bump" {
    var v: u32 = 0;
    bump(&v);
    try std.testing.expect(v == 1);
}
"""

PYTHON_BLOCK = """def bump(v: int) -> int:
    v = v + 1
    return v


def test_bump() -> None:
    assert bump(0) == 1
"""


def test_a_rust_step_that_times_out_fails_with_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rust, "run", answers(HUNG))
    found = list(RUST.verify(crate(tmp_path)))
    assert levels(found) == {Level.FAIL}
    assert [f.message for f in found] == [
        f"{step} did not finish in 900s"
        for step in ("compiles", "clippy", "tests", "rustfmt", "intra-doc links")
    ]


def test_a_rust_failure_with_no_output_still_says_something(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rust, "run", answers(Ran(101, "", "", timed_out=False)))
    found = list(RUST.verify(crate(tmp_path)))
    assert {f.message for f in found} >= {"compiles: exited 101 and said nothing"}


def test_zig_fmt_that_times_out_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(zig, "run", answers(HUNG))
    (finding,) = zig.ZIG.verify(Extraction(tmp_path))
    assert finding.level is Level.FAIL
    assert "`zig fmt --check` did not finish" in finding.message


def zig_unit(tmp_path: Path) -> Extraction:
    return unit(tmp_path, "x.zig", ZIG_BLOCK)


def python_unit(tmp_path: Path) -> Extraction:
    return unit(tmp_path, "x.py", PYTHON_BLOCK)


@pytest.mark.parametrize(
    ("toolchain", "make", "runs"),
    [
        (RUST, crate, (PASSED, HUNG)),
        (RUST, crate, (PASSED, PASSED, HUNG)),
        (zig.ZIG, zig_unit, (PASSED, HUNG)),
        (python.PYTHON_TOOLCHAIN, python_unit, (PASSED, HUNG)),
    ],
    ids=["rust", "rust-second-opinion", "zig", "python"],
)
def test_a_mutant_that_times_out_is_inconclusive_never_killed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    toolchain: Toolchain,
    make: Callable[[Path], Extraction],
    runs: tuple[Ran, ...],
) -> None:
    """The first run is the unmutated one; rust's third is a re-run."""
    monkeypatch.setattr(f"{type(toolchain).__module__}.run", answers(*runs))
    found = list(toolchain.mutate(make(tmp_path)))
    assert found
    assert levels(found) == {Level.NOTE}
    assert all("timed out — inconclusive" in f.message for f in found)
