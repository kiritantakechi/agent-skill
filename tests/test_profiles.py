"""What a profile and the harness declare, held where it is declared.

A check reads the tree; these read the records. Each of the first group
was a branch of a check that fired only on a value a profile or the
harness declared, and so had no negative control: no edit of the tree
reaches it. Asked of the records instead, it fails the suite the moment
a declaration is wrong, rather than standing as an exemption nobody can
exercise.
"""

import pytest

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
