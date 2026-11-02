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

lazy from collections.abc import Callable

import pytest

from agent_skill.checks import pins as mod
from agent_skill.checks.pins import _sort_key, _tool_pins, library_pin, rust_pin
from agent_skill.ids import Location
from agent_skill.proc import Ran
from agent_skill.report import Level

#: Where the pins below are said to be.
HERE = Location("rust-style")

FAIL, UNRUN = Level.FAIL, Level.UNRUN


def _greater(a: object, b: object) -> object:
    """Return `a > b`, unchecked on purpose.

    What this asserts is what happens at run time, so the checker's
    objection to comparing `None` with a tuple is suppressed here.
    """
    return a > b  # ty: ignore[unsupported-operator] — the TypeError is the point


#: Forms a real index answers with, none of which `_sort_key`
#: understands.
UNORDERABLE = ["1.2.3.post1", "0.16.5.dev0", "2024.1", "15.2", "0.0.75+local", ""]


@pytest.mark.parametrize("version", UNORDERABLE)
def test_a_version_it_cannot_parse_gets_no_answer(version: str) -> None:
    assert _sort_key(version) is None


@pytest.mark.parametrize("version", UNORDERABLE)
def test_no_unparseable_version_compares_as_older_than_a_pin(version: str) -> None:
    """The defect stated as its consequence rather than as its cause.

    Comparing `None` against a tuple raises, which is the point: the
    caller has to decide, and cannot fall through to "the pin is
    current" by arithmetic.
    """
    with pytest.raises(TypeError, match="between instances of 'NoneType' and 'tuple'"):
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
def test_releases_still_order(lower: str, higher: str) -> None:
    low, high = _sort_key(lower), _sort_key(higher)
    assert low is not None
    assert high is not None
    assert low < high


def canned(index_answer: str, pinned: str) -> Callable[..., Ran]:
    """A `run` that reports the pinned version, then one index line."""

    def fake(cmd: list[str], **_kw: object) -> Ran:
        if "--version" in cmd:
            return Ran(0, f"ruff {pinned}", "", timed_out=False)
        return Ran(0, index_answer, "", timed_out=False)

    return fake


def test_an_index_answer_it_cannot_order_withholds_the_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pinned = mod.pinned_version("ruff")
    assert pinned, "the source tree declares the ruff pin"
    monkeypatch.setattr(mod, "TOOLS", ("ruff",))
    monkeypatch.setattr(mod, "run", canned(f"ruff=={pinned}.post1\n", pinned))

    findings = list(_tool_pins())

    assert [f.level for f in findings] == [Level.UNRUN], (
        "an unorderable index answer must withhold the pass, "
        "not read as the pin being current"
    )
    assert "not a version this can order" in findings[0].message


def test_an_index_answer_it_can_order_still_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half: the check still fires when it can compare."""
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
    assert list(rust_pin("1.99", "1.99.0", "1.99.1", HERE)) == []


def test_a_rust_pin_behind_stable_fails() -> None:
    found = list(rust_pin("1.98", "1.98.1", "1.99.1", HERE))
    assert [f.level for f in found] == [FAIL]
    assert "1.99.1 is stable" in found[0].message
    assert found[0].where == HERE


def test_a_rust_pin_rustc_disagrees_with_fails() -> None:
    assert [f.level for f in rust_pin("1.98", "1.99.0", "1.98.1", HERE)] == [FAIL]


def test_a_rust_pin_nothing_answered_for_is_unrun() -> None:
    assert [f.level for f in rust_pin("1.99", "", "", HERE)] == [UNRUN, UNRUN]


def test_a_library_pin_must_be_exact() -> None:
    assert [f.level for f in library_pin("bevy", "0.20", "0.20.0", HERE)] == [FAIL]


def test_a_library_pin_behind_the_newest_release_fails() -> None:
    found = list(library_pin("bevy", "=0.19.1", "0.20.0", HERE))
    assert [f.level for f in found] == [FAIL]
    assert "0.20.0 is released" in found[0].message


def test_a_current_library_pin_is_quiet() -> None:
    assert list(library_pin("bevy", "=0.20.0", "0.20.0", HERE)) == []


def test_a_library_pin_crates_io_did_not_answer_for_is_unrun() -> None:
    assert [f.level for f in library_pin("bevy", "=0.20.0", "", HERE)] == [UNRUN]


INTERPRETER = "cpython-3.15.2+freethreaded"
HARNESS = {"ty": "0.0.95", "ruff": "0.17.3"}


def test_a_workflow_installing_the_pin_is_quiet() -> None:
    text = f"- run: uv python install {INTERPRETER}\n"
    assert list(mod.workflow_pins(text, INTERPRETER, HERE)) == []


def test_a_workflow_installing_no_interpreter_fails() -> None:
    """The runner's own interpreter is the one build nobody verified."""
    text = "- uses: actions/setup-python@v6\n"
    [found] = mod.workflow_pins(text, INTERPRETER, HERE)
    assert "installs no interpreter" in found.message


def test_a_workflow_installing_another_build_fails() -> None:
    [found] = mod.workflow_pins("- run: uv python install 3.15t\n", INTERPRETER, HERE)
    assert "installs `3.15t`" in found.message


def groups(**lists: list[str]) -> dict[str, object]:
    return {"dependency-groups": lists}


def test_an_exact_pin_is_quiet() -> None:
    project = groups(lint=["ruff==0.17.3"], typecheck=["ty == 0.0.95"])
    assert list(mod.project_pins(project, HARNESS, HERE)) == []


@pytest.mark.parametrize(
    "requirement", ["ty>=0.0.60", "ty", "ty~=0.0.95", "ty==0.0.95,<1", "ty==0.0.60"]
)
def test_anything_but_the_exact_pin_fails(requirement: str) -> None:
    """A floor passed: only a requirement spelled `==` was compared."""
    [found] = mod.project_pins(groups(typecheck=[requirement]), HARNESS, HERE)
    assert f"requires `{requirement}`" in found.message


def test_a_requirement_anywhere_in_the_project_is_read() -> None:
    project = {
        "build-system": {"requires": ["uv_build>=0.13.3,<0.14"]},
        "project": {
            "dependencies": ["ruff>=0.1"],
            "optional-dependencies": {"cli": ["typer>=0.15"]},
        },
        "dependency-groups": {"dev": [{"include-group": "lint"}]},
    }
    [found] = mod.project_pins(project, HARNESS, HERE)
    assert "requires `ruff>=0.1`" in found.message
