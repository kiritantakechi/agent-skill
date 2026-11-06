"""What a profile and the harness declare, held where it is declared.

A check reads the tree; these read the records. Each of the first group
was a branch of a check that fired only on a value a profile or the
harness declared, and so had no negative control: no edit of the tree
reaches it. Asked of the records instead, it fails the suite the moment
a declaration is wrong, rather than standing as an exemption nobody can
exercise.
"""

import ast
import re
from pathlib import Path
lazy from collections.abc import Iterator

import pytest

import agent_skill
from agent_skill.checks import all_checks
from agent_skill.checks.pins import _sort_key
from agent_skill.lang import toolchain_for
from agent_skill.lang.python import RELEASE, PythonSnippet
from agent_skill.lang.rust import RustCrate
from agent_skill.lang.zig import ZigBuild
from agent_skill.profiles import PROFILES

PROFILED = list(PROFILES.values())


@pytest.mark.parametrize("profile", PROFILED, ids=lambda p: p.name)
def test_a_delta_is_on_a_standard_the_harness_knows(profile) -> None:  # noqa: ANN001 — a profile, as parametrised
    """Was `crossref.delta_declaration`: an anchor is a standard."""
    if profile.delta is None:
        return
    assert profile.delta.anchor in PROFILES, profile.name
    assert profile.delta.anchor != profile.name
    assert profile.delta.step.strip(), f"{profile.name} has no reading step"


@pytest.mark.parametrize("profile", PROFILED, ids=lambda p: p.name)
def test_a_delta_names_the_language_its_anchor_sweeps(profile) -> None:  # noqa: ANN001 — a profile, as parametrised
    """Was `crossref.anchor_no_language`: what the sweep reads."""
    if profile.delta is not None:
        assert profile.languages, profile.name


@pytest.mark.parametrize("profile", PROFILED, ids=lambda p: p.name)
def test_fixtures_are_prepared_as_a_language(profile) -> None:  # noqa: ANN001 — a profile, as parametrised
    """Was `sensitivity.no_language`: a fixture stands in a corpus."""
    if profile.fires:
        assert profile.languages, profile.name


@pytest.mark.parametrize("profile", PROFILED, ids=lambda p: p.name)
def test_every_rule_with_fixtures_has_one(profile) -> None:  # noqa: ANN001 — a profile, as parametrised
    """Was `sensitivity.no_fixture`: an empty entry proves nothing."""
    empty = sorted(rid for rid, fixtures in profile.fires.items() if not fixtures)
    assert not empty, f"{profile.name} lists {empty} with no fixture"


def _configs[T](kind: type[T]) -> list[tuple[str, T]]:
    return [(p.name, p.toolchain) for p in PROFILED if isinstance(p.toolchain, kind)]


@pytest.mark.parametrize(("name", "snippet"), _configs(PythonSnippet))
def test_an_interpreter_pin_is_a_release_uv_lists(
    name: str, snippet: PythonSnippet
) -> None:
    """Was `pins.interpreter_id` and `pins.interpreter_unordered`.

    The pin is compared with `uv python list`, whose lines it must read
    as, at a release the comparison can order.
    """
    pin = snippet.interpreter
    assert RELEASE.match(f"{pin}-"), f"{name}: `{pin}` is not a release identifier"
    assert _sort_key(str(pin.version.public)) is not None, name


@pytest.mark.parametrize(("name", "crate"), _configs(RustCrate))
def test_a_crate_pins_rust_and_its_library_exactly(name: str, crate: RustCrate) -> None:
    """Was `pins.rust_unreadable` and `pins.library_inexact`."""
    assert crate.rust.exact, name
    assert len(crate.rust.version.release) >= 2, name  # major.minor
    if crate.library is not None:
        assert crate.library.pin.exact, name


@pytest.mark.parametrize(("name", "build"), _configs(ZigBuild))
def test_a_pin_that_follows_this_machine_says_why(name: str, build: ZigBuild) -> None:
    """Was `pins.local_no_reason`."""
    assert build.follows_local.strip(), name


def test_every_profile_names_a_toolchain_the_harness_has() -> None:
    for profile in PROFILED:
        if profile.toolchain is not None:
            assert toolchain_for(profile.toolchain) is not None, profile.name


@pytest.mark.parametrize("profile", PROFILED, ids=lambda p: p.name)
def test_a_mirror_is_held_against_a_standard_the_harness_knows(profile) -> None:  # noqa: ANN001 — a profile, as parametrised
    if profile.mirror is not None:
        assert profile.mirror.anchor in PROFILES, profile.name
        for rule, _ in profile.mirror.pairs:
            assert rule.startswith(f"{profile.prefix}-"), (profile.name, rule)


#: The package, every module of which is read for literals.
PACKAGE = Path(agent_skill.__file__).resolve().parent

#: Where a fact about one skill or one toolchain may be spelled.
OWNERS = ("profiles", "lang")


def _names() -> tuple[set[str], set[str]]:
    """Every skill's name, and every toolchain's, as the profiles say.

    A toolchain is named by its module and by the fence its examples
    are written in.
    """
    toolchains = {
        tc.name for p in PROFILED if (tc := toolchain_for(p.toolchain)) is not None
    }
    toolchains |= {fence for p in PROFILED for fence in p.languages}
    return set(PROFILES), toolchains


def _literals(path: Path) -> Iterator[tuple[int, str]]:
    """Each string literal in `path` and its line, docstrings left out.

    A comment is not in the tree, and a docstring says why, which may
    need a name; a literal is what the code acts on.
    """
    tree = ast.parse(path.read_text())
    documented = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, documented)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            yield node.lineno, node.value


def _naming(skills: set[str], toolchains: set[str]) -> re.Pattern[str]:
    """A literal that is a toolchain's name, or that names a skill."""
    words = "|".join(re.escape(s) for s in sorted(skills))
    whole = "|".join(re.escape(t) for t in sorted(toolchains))
    return re.compile(rf"(?<![\w-])(?:{words})(?![\w-])|\A(?:{whole})\Z")


def test_the_names_are_read_off_the_profiles() -> None:
    """Derived, so the test below cannot pass over an empty set."""
    skills, toolchains = _names()
    assert len(skills) == len(PROFILED)
    assert toolchains
    naming = _naming(skills, toolchains)
    owned = [
        value
        for owner in OWNERS
        for path in (PACKAGE / owner).rglob("*.py")
        for _, value in _literals(path)
        if naming.search(value)
    ]
    assert owned, "no profile or toolchain spells a name, so nothing is found"


def test_no_generic_module_names_a_skill_or_a_toolchain() -> None:
    """Per-skill facts live in profiles, per-toolchain ones in `lang/`.

    A skill's name in a check is a table keyed by it, or a branch on
    it, and the next standard added is the one it forgets.
    """
    naming = _naming(*_names())
    found = [
        f"{path.relative_to(PACKAGE)}:{line}: {value[:60]!r}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).parts[0] not in OWNERS
        for line, value in _literals(path)
        if naming.search(value)
    ]
    assert not found, "\n".join(found)


def _compared(path: Path) -> Iterator[tuple[int, str]]:
    """Each literal `path` compares with, matches on, or indexes by."""
    for node in ast.walk(ast.parse(path.read_text())):
        match node:
            case ast.Compare(left=left, comparators=rest):
                operands = [left, *rest]
            case ast.Subscript(slice=index):
                operands = [index]
            case ast.MatchValue(value=value):
                operands = [value]
            case _:
                continue
        for operand in operands:
            if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                yield node.lineno, operand.value


def test_no_module_branches_on_a_check_name() -> None:
    """A fact about one check is a field of its registration.

    `documented` asked `if "controls" in rows`: the next check whose
    README row states a scope would have been the one it forgot. A
    check's name is spelled where it is registered and where a branch
    is declared under it; nothing compares against it.
    """
    names = {c.name for c in all_checks()}
    found = [
        f"{path.relative_to(PACKAGE)}:{line}: {value!r}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for line, value in _compared(path)
        if value in names
    ]
    assert not found, "\n".join(found)
