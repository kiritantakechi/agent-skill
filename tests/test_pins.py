"""Ordering releases, and what happens to one that cannot be ordered.

`_sort_key` used to answer `(0, 0, 0, 0, 0)` for anything it did not
parse, which sorts below every real release. So an index answer of
`1.2.3.post1` compared as *older than the pin*, the staleness check
emitted nothing, and the run reported the pin current — on a comparison
it had not made.

That is the failure `version_mismatch` was already fixed for one
function away: *"an unfindable pin is itself the complaint"*. A value
that could not be read must not be resolved into one that happens to
compare as agreement.
"""

import pytest

from agent_skill.checks import pins as mod
from agent_skill.checks.pins import _sort_key, _tool_pins, library_pin, rust_pin
from agent_skill.proc import Ran
from agent_skill.report import Level, fail, unrun


def _greater(a, b):
    """Untyped on purpose — what this asserts is what happens at run time."""
    return a > b


#: Forms a real index answers with, none of which `_sort_key`
#: understands.
UNORDERABLE = ["1.2.3.post1", "0.16.5.dev0", "2024.1", "15.2", "0.0.75+local", ""]


@pytest.mark.parametrize("version", UNORDERABLE)
def test_a_version_it_cannot_parse_gets_no_answer(version) -> None:
    assert _sort_key(version) is None


@pytest.mark.parametrize("version", UNORDERABLE)
def test_no_unparseable_version_compares_as_older_than_a_pin(version) -> None:
    """The defect stated as its consequence rather than as its cause.

    Comparing `None` against a tuple raises, which is the point: the
    caller has to decide, and cannot fall through to "the pin is
    current" by arithmetic.
    """
    with pytest.raises(TypeError):
        _greater(_sort_key(version), _sort_key("0.16.5"))


@pytest.mark.parametrize(
    ("lower", "higher"),
    [
        ("3.15.0rc1", "3.15.0rc2"),
        ("3.15.0rc2", "3.15.0"),  # a final release sorts after every candidate
        ("3.15.0a1", "3.15.0b1"),
        ("3.14.9", "3.15.0"),
        ("0.16.4", "0.16.5"),
    ],
)
def test_releases_still_order(lower, higher) -> None:
    low, high = _sort_key(lower), _sort_key(higher)
    assert low is not None and high is not None
    assert low < high


def canned(index_answer: str, pinned: str):
    """A `run` that reports the pinned version and then hands back one index line."""

    def fake(cmd, **kw):
        if "--version" in cmd:
            return Ran(0, f"ruff {pinned}", "", False)
        return Ran(0, index_answer, "", False)

    return fake


def test_an_index_answer_it_cannot_order_withholds_the_pass(monkeypatch) -> None:
    pinned = mod.pinned_version("ruff")
    assert pinned, "the source tree declares the ruff pin"
    monkeypatch.setattr(mod, "TOOLS", ("ruff",))
    monkeypatch.setattr(mod, "run", canned(f"ruff=={pinned}.post1\n", pinned))

    findings = list(_tool_pins())

    assert [f.level for f in findings] == [Level.UNRUN], (
        "an unorderable index answer must withhold the pass, not read as the pin being current"
    )
    assert "not a version this can order" in findings[0].message


def test_an_index_answer_it_can_order_still_decides(monkeypatch) -> None:
    """The other half: the check still fires when it genuinely can compare."""
    pinned = mod.pinned_version("ruff")
    assert pinned, "the source tree declares the ruff pin"
    major, minor, micro = (int(n) for n in pinned.split("."))
    monkeypatch.setattr(mod, "TOOLS", ("ruff",))
    monkeypatch.setattr(
        mod, "run", canned(f"ruff=={major}.{minor}.{micro + 1}\n", pinned)
    )

    findings = list(_tool_pins())

    assert [f.level for f in findings] == [Level.FAIL]
    assert "is available" in findings[0].message


def test_a_rust_pin_matching_rustc_and_stable_is_quiet() -> None:
    assert list(rust_pin("1.99", "1.99.0", "1.99.1")) == []


def test_a_rust_pin_behind_stable_fails() -> None:
    found = list(rust_pin("1.98", "1.98.1", "1.99.1"))
    assert [level for level, _ in found] == [fail]
    assert "1.99.1 is stable" in found[0][1]


def test_a_rust_pin_rustc_disagrees_with_fails() -> None:
    assert [level for level, _ in rust_pin("1.98", "1.99.0", "1.98.1")] == [fail]


def test_a_rust_pin_nothing_answered_for_is_unrun() -> None:
    assert [level for level, _ in rust_pin("1.99", None, None)] == [unrun, unrun]


def test_a_library_pin_must_be_exact() -> None:
    assert [level for level, _ in library_pin("bevy", "0.20", "0.20.0")] == [fail]


def test_a_library_pin_behind_the_newest_release_fails() -> None:
    found = list(library_pin("bevy", "=0.19.1", "0.20.0"))
    assert [level for level, _ in found] == [fail]
    assert "0.20.0 is released" in found[0][1]


def test_a_current_library_pin_is_quiet() -> None:
    assert list(library_pin("bevy", "=0.20.0", "0.20.0")) == []


def test_a_library_pin_crates_io_did_not_answer_for_is_unrun() -> None:
    assert [level for level, _ in library_pin("bevy", "=0.20.0", None)] == [unrun]
