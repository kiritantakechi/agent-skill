"""Reading the pins, including where there is nothing to read.

`pinned_version` resolves `pyproject.toml` relative to the package,
three directories up. That is where the file is when the harness runs
from its own source tree, and nowhere at all once the package is
installed — `uv build --wheel` does not ship it. Reproduced: installing
the built wheel into a clean 3.14 venv and calling
`pinned_version('rg')` raised `FileNotFoundError`, out of
`searcher_problem`, on the default path of `agent-skill check`.
`[project.scripts]` declares that entry point, so running it installed
is a supported thing to do.

Unreadable pins are a complaint. Not a crash, and — the older bug one
function away — not a pass.
"""

import pytest

from agent_skill.proc import declared_pins, pinned_version, version_mismatch


def test_the_pins_are_readable_from_the_source_tree() -> None:
    assert declared_pins() is not None
    assert pinned_version("rg"), (
        "the `rg` pin is read through PACKAGE's `ripgrep-bin` spelling"
    )


def test_an_unreadable_declaration_is_not_an_exception(monkeypatch) -> None:
    monkeypatch.setattr("agent_skill.proc.declared_pins", lambda: None)
    assert pinned_version("rg") is None


def test_an_unreadable_declaration_is_not_agreement(monkeypatch) -> None:
    """The whole point: silence here used to be a traceback, and before that, a pass."""
    monkeypatch.setattr("agent_skill.proc.declared_pins", lambda: None)
    complaint = version_mismatch("rg", "ripgrep 15.2.0")
    assert complaint is not None, (
        "an unreadable pin read as agreement with the running version"
    )
    assert "installed distribution" in complaint


def test_a_missing_pin_reads_differently_from_a_missing_file(monkeypatch) -> None:
    """One is something to add; the other is how this runs when installed."""
    monkeypatch.setattr(
        "agent_skill.proc.declared_pins", lambda: 'dev = ["ruff==0.16.5"]'
    )
    complaint = version_mismatch("rg", "ripgrep 15.2.0")
    assert complaint is not None
    assert "pins no version for it" in complaint
    assert "installed distribution" not in complaint


@pytest.mark.parametrize(
    ("reported", "mismatched"),
    [("ripgrep 15.2.0 (rev e89fff89ac)", False), ("ripgrep 14.1.1", True), ("", True)],
)
def test_the_running_version_is_still_compared(reported, mismatched) -> None:
    assert (version_mismatch("rg", reported) is not None) is mismatched
