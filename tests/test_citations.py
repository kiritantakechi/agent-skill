"""Which tokens in a rule are ruff codes, as ruff's catalogue says.

A token was classified by stripping its digits and looking the letters
up in a list written by hand, which named four families by their
prefix: `C4`, `C90`, `T10`, `T20`. Stripping the digits of `C408` leaves
`C`, so those families could never be produced, and every citation of
one was dropped as prose — read as enforced while nothing compared it.
"""

import pytest

from agent_skill.lang.python import _catalogue, _codes_in


@pytest.fixture(scope="module")
def catalogue() -> dict[str, str]:
    found = _catalogue()
    assert found is not None, "the pinned ruff did not list its rules"
    return found


@pytest.mark.parametrize("code", ["C408", "C901", "T100", "T201", "COM812"])
def test_a_family_named_by_a_digit_prefix_is_read(
    code: str, catalogue: dict[str, str]
) -> None:
    assert _codes_in(f"`{code}` decides this.", catalogue) == {code}


def test_a_code_ruff_never_had_is_still_a_citation(
    catalogue: dict[str, str],
) -> None:
    """`ASYNC101` was invented, and a finding still has to reach it."""
    assert "ASYNC101" not in catalogue
    assert _codes_in("`ASYNC101` decides this.", catalogue) == {"ASYNC101"}


@pytest.mark.parametrize("prose", ["PS-CONC-02", "3.15", "ISO8601", "PEP 604"])
def test_prose_is_not_a_code(prose: str, catalogue: dict[str, str]) -> None:
    assert _codes_in(prose, catalogue) == set()
