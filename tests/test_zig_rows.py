"""A compiler row is proved by a probe, and a probe needs its row."""

lazy from collections.abc import Callable

import pytest

from agent_skill.checks.citations import _compile_zig, phrase, zig_rows
from agent_skill.model import LintRow
from agent_skill.proc import have

UNUSED = "unused local constant"
SHADOW = "local constant … shadows local constant from outer scope"


def row(lint: str) -> LintRow:
    return LintRow("zig", lint, "error", "x", "naming.md", 1)


type Said = dict[str, list[str] | None]


def compiler(said: Said) -> Callable[[str], list[str] | None]:
    """A stand-in compiler: each probe source maps to what it prints."""
    return said.__getitem__


def messages(rows: list[LintRow], probes: dict[str, str], said: Said) -> list[str]:
    return [m for _, m in zig_rows(rows, probes, compiler(said))]


def test_a_phrase_stands_in_for_the_identifiers() -> None:
    line = (
        "p.zig:4:15: error: local constant 'a' shadows local constant from outer scope"
    )

    assert phrase(SHADOW).search(line)


def test_a_phrase_is_anchored_at_the_error() -> None:
    assert not phrase("unreachable code").search(
        "p.zig:3:5: error: reached unreachable code"
    )


def test_a_probe_that_proves_its_row() -> None:
    said: Said = {"probe": ["p.zig:2:11: error: unused local constant"]}

    assert messages([row(UNUSED)], {UNUSED: "probe"}, said) == []


def test_a_probe_that_compiles() -> None:
    found = messages([row(UNUSED)], {UNUSED: "probe"}, {"probe": None})

    assert found == [
        f"`{UNUSED}`: its probe compiles, so the compiler does not report it"
    ]


def test_a_probe_that_fails_for_another_reason() -> None:
    said: Said = {"probe": ["p.zig:1:1: error: expected ';' after declaration"]}

    found = messages([row(UNUSED)], {UNUSED: "probe"}, said)

    printed = "p.zig:1:1: error: expected ';' after declaration"
    assert found == [f"`{UNUSED}`: its probe fails with `{printed}` instead"]


def test_a_row_with_no_probe() -> None:
    found = messages([row(UNUSED)], {}, {})

    assert found == [
        f"`{UNUSED}` has no probe, so nothing shows the compiler reports it"
    ]


def test_a_probe_with_no_row() -> None:
    found = messages([], {UNUSED: "probe"}, {})

    assert found == [f"the probe for `{UNUSED}` has no row in any chapter"]


@pytest.mark.toolchain
@pytest.mark.skipif(not have("zig"), reason="needs zig")
def test_a_real_probe_reports_its_error() -> None:
    errors = _compile_zig("fn f() void {\n    const x = 1;\n}\n")

    assert errors is not None
    assert any(phrase(UNUSED).search(line) for line in errors)
