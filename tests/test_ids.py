"""The typed values: each one's printer inverts its parser.

The generators are seeded, so a failure names a value that reproduces.
"""

import itertools
import random
import re
from pathlib import Path

import pytest

from agent_skill.ids import (
    Answered,
    Branch,
    Location,
    NoAnswer,
    Pin,
    RuleId,
    Stage,
    Tier,
    Version,
    parse_answer,
    rule_id,
)
from agent_skill.layout import SKILLS

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = 400


def seeded(seed: int) -> random.Random:
    """A generator that draws the same cases on every run."""
    return random.Random(seed)  # noqa: S311 — reproducible test cases, not secrets


def shuffled[T](values: list[T]) -> list[T]:
    out = list(values)
    seeded(0).shuffle(out)
    return out


def _word(rng: random.Random, alphabet: str, low: int, high: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(low, high)))


def _rule_id(rng: random.Random) -> RuleId:
    return RuleId(
        _word(rng, "ABRSZP", 2, 2),
        rng.choice(["ERR", "CORE", "DATA", "A", "TEST", _word(rng, "ABCDEFGH", 1, 8)]),
        rng.randint(0, 120),
        rng.choice(["", "", "", "a", "b", "z"]),
    )


def _version(rng: random.Random) -> Version:
    release = tuple(rng.randint(0, 20) for _ in range(rng.randint(2, 4)))
    stage = rng.choice(list(Stage))
    candidate = 0 if stage is Stage.FINAL else rng.randint(0, 12)
    return Version(release, stage, candidate)


def _location(rng: random.Random) -> Location:
    skill = rng.choice([None, "rust-style", "zig-style", _word(rng, "abc-9", 1, 6)])
    if skill is not None and skill.startswith("-"):
        skill = f"x{skill}"
    file = rng.choice(
        [None, "SKILL.md", "references/errors.md", "pyproject.toml", "src/a/b.py"]
    )
    line = rng.choice([None, 1, 42, 1203]) if file is not None else None
    rule = rng.choice([None, _rule_id(rng)])
    return Location(skill, file, line, rule)


def _branch(rng: random.Random) -> Branch:
    return Branch(
        rng.choice(["layout", "shared-text", "self-application"]),
        _word(rng, "abcdefgh-0", 1, 10).lstrip("-0") or "w",
    )


@pytest.mark.parametrize(
    ("make", "parse"),
    [
        (_rule_id, RuleId.parse),
        (lambda rng: rng.choice(list(Tier)), Tier.parse),
        (_location, Location.parse),
        (_version, Version.parse),
        (
            lambda rng: Pin(
                rng.choice(["ruff", "ty", "zig"]),
                _version(rng),
                exact=rng.random() < 0.5,
            ),
            Pin.parse,
        ),
        (_branch, Branch.parse),
    ],
    ids=["RuleId", "Tier", "Location", "Version", "Pin", "Branch"],
)
def test_parsing_what_was_printed_gives_the_value_back(make, parse) -> None:  # noqa: ANN001 — a value type and its parser, of every type above
    rng = seeded(15)
    for _ in range(SAMPLES):
        value = make(rng)
        assert parse(str(value)) == value, str(value)


def test_an_answer_and_no_answer_read_back_as_themselves() -> None:
    rng = seeded(16)
    for _ in range(SAMPLES):
        answer = rng.choice(
            [Answered(_version(rng)), NoAnswer(_word(rng, "abc :-", 0, 30))]
        )
        assert parse_answer(str(answer), Version.parse) == answer


def test_no_answer_is_not_an_answer_of_any_value() -> None:
    nothing = NoAnswer("`rustc --version` timed out")
    assert nothing != Answered("")
    assert nothing != Answered(None)
    assert not isinstance(nothing, Answered)


@pytest.mark.parametrize(
    "text",
    ["RS-ERR-03", "ZS-CORE-01b", "ZS-CORE-12a", "PS-DATA-17", "BV-ECS-100"],
)
def test_a_canonical_rule_id_prints_as_it_was_read(text: str) -> None:
    assert str(RuleId.parse(text)) == text


def test_a_rule_id_keeps_its_inserted_letter() -> None:
    rid = RuleId.parse("ZS-CORE-12a")
    assert (rid.number, rid.suffix) == (12, "a")


@pytest.mark.parametrize(
    "text",
    ["RS-ERR", "RS-ERR-", "rs-err-03", "RSX-ERR-03", "RS-ERR-03ab", " RS-ERR-03"],
)
def test_what_is_not_a_rule_id_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="not a rule ID"):
        RuleId.parse(text)


def test_rule_ids_order_by_number_and_then_by_inserted_letter() -> None:
    spelled = ["ZS-CORE-09", "ZS-CORE-10", "ZS-CORE-12", "ZS-CORE-12a", "ZS-CORE-12b"]
    ids = [RuleId.parse(t) for t in spelled]
    assert sorted(shuffled(ids)) == ids
    assert RuleId.parse("RS-ERR-100") > RuleId.parse("RS-ERR-99")


def _assert_total_order[T: (RuleId, Version)](values: list[T]) -> None:
    for a, b in itertools.product(values, repeat=2):
        assert [a < b, a == b, b < a].count(True) == 1, (a, b)
    for a, b, c in itertools.product(values[:24], repeat=3):
        if a < b < c:
            assert a < c, (a, b, c)


def test_rule_ids_are_totally_ordered() -> None:
    rng = seeded(17)
    _assert_total_order([_rule_id(rng) for _ in range(60)])


def test_versions_are_totally_ordered() -> None:
    rng = seeded(18)
    _assert_total_order([_version(rng) for _ in range(60)])


def test_a_final_release_follows_its_candidates() -> None:
    spelled = [
        "1.99",
        "1.99.0",
        "3.14.9",
        "3.15.0a1",
        "3.15.0b2",
        "3.15.0rc1",
        "3.15.0rc2",
        "3.15.0",
        "3.15.1",
        "3.16.0",
    ]
    versions = [Version.parse(t) for t in spelled]
    assert sorted(shuffled(versions)) == versions
    assert [str(v) for v in versions] == spelled


def test_minor_numbers_order_as_numbers() -> None:
    assert Version.parse("0.9.0") < Version.parse("0.10.0")


@pytest.mark.parametrize(
    "text", ["3", "1.2.3.post1", "01.2", "1.2rc", "1..2", "v1.2", "1.2-rc1", ""]
)
def test_what_cannot_be_ordered_is_not_a_version(text: str) -> None:
    with pytest.raises(ValueError, match="not a version this can order"):
        Version.parse(text)


def test_a_floor_and_an_exact_pin_differ() -> None:
    assert Pin.parse("ruff==0.17.3").exact
    assert not Pin.parse("rustc>=1.99").exact
    assert Pin.parse("ruff==0.17.3").version == Version.parse("0.17.3")


@pytest.mark.parametrize("text", ["[M]", "[M!]", "[S]"])
def test_a_tier_prints_as_it_was_read(text: str) -> None:
    assert str(Tier.parse(text)) == text


@pytest.mark.parametrize("text", ["M", "[M]!", "[X]", "`[M]`", "[m]"])
def test_a_tier_is_only_its_bracketed_spelling(text: str) -> None:
    with pytest.raises(ValueError, match="not a tier"):
        Tier.parse(text)


@pytest.mark.parametrize(
    ("location", "printed"),
    [
        (
            Location(
                "rust-style", "references/errors.md", 42, RuleId.parse("RS-ERR-03")
            ),
            "rust-style/references/errors.md:42 [RS-ERR-03]",
        ),
        (Location("zig-style"), "zig-style"),
        (Location(file="src/agent_skill/ids.py", line=7), "./src/agent_skill/ids.py:7"),
        (Location(rule=RuleId.parse("PS-ERR-01")), "[PS-ERR-01]"),
        (Location(), ""),
    ],
)
def test_a_location_prints_only_what_it_knows(location: Location, printed: str) -> None:
    assert str(location) == printed


def test_a_file_outside_any_skill_is_not_read_as_a_skill() -> None:
    assert Location.parse("./src/agent_skill/ids.py") == Location(
        file="src/agent_skill/ids.py"
    )
    assert Location.parse("src/agent_skill/ids.py") == Location(
        "src", "agent_skill/ids.py"
    )


def test_a_line_without_a_file_is_refused() -> None:
    with pytest.raises(ValueError, match="a line is a positive line of a file"):
        Location("rust-style", line=3)


def test_a_branch_reads_as_check_then_name() -> None:
    assert Branch.parse("shared-text.drift") == Branch("shared-text", "drift")
    with pytest.raises(ValueError, match="not a branch"):
        Branch.parse("layout")


def test_every_rule_id_the_skills_spell_is_canonical() -> None:
    spelled = {
        m.group(0)
        for path in sorted((ROOT / SKILLS).rglob("*.md"))
        for m in re.finditer(rf"\b{rule_id()}\b", path.read_text())
    }
    assert len(spelled) > 1000
    assert {t for t in spelled if str(RuleId.parse(t)) != t} == set()
