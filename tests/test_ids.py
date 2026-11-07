"""The typed values: each one's printer inverts its parser.

The generators are seeded, so a failure names a value that reproduces.
An ID that names no rule uses the prefix `XS`, which no standard owns,
so `crossref` does not read it as a citation.
"""

import itertools
import random
import re
from pathlib import Path

import pytest

from agent_skill.ids import (
    DASH,
    DEPARTING,
    Answered,
    Branch,
    Breach,
    Location,
    NoAnswer,
    Op,
    Pin,
    Relation,
    RuleId,
    Stage,
    Tier,
    Version,
    breaches,
    cited,
    cited_at,
    cited_lines,
    leading,
    parse_answer,
    print_range,
    ranges,
    releases,
    rule_id,
    uncited,
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
    if rng.random() < 0.1:
        return Version((rng.randint(1000, 9999),))  # an edition
    release = tuple(rng.randint(0, 20) for _ in range(rng.randint(2, 4)))
    stage = rng.choice(list(Stage))
    candidate = 0 if stage is Stage.FINAL else rng.randint(0, 12)
    local = rng.choice(["", "", "", "freethreaded", "debug", "ubuntu.1"])
    return Version(release, stage, candidate, local)


def _pin(rng: random.Random) -> Pin:
    op = rng.choice(list(Op))
    tools = ["cpython", "pypy"] if op is Op.REQUEST else ["ruff", "ripgrep-bin", "zig"]
    return Pin(rng.choice(tools), _version(rng), op)


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
        _word(rng, "abcdefgh_0", 1, 10).lstrip("_0") or "w",
    )


@pytest.mark.parametrize(
    ("make", "parse"),
    [
        (_rule_id, RuleId.parse),
        (lambda rng: rng.choice(list(Tier)), Tier.parse),
        (_location, Location.parse),
        (_version, Version.parse),
        (_pin, Pin.parse),
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
    ["RS-ERR-03", "XS-CORE-01b", "XS-ERR-12a", "PS-DATA-17", "XS-ECS-100"],
)
def test_a_canonical_rule_id_prints_as_it_was_read(text: str) -> None:
    assert str(RuleId.parse(text)) == text


def test_a_rule_id_keeps_its_inserted_letter() -> None:
    rid = RuleId.parse("XS-ERR-12a")
    assert (rid.number, rid.suffix) == (12, "a")


@pytest.mark.parametrize(
    "text",
    ["RS-ERR", "RS-ERR-", "rs-err-03", "RSX-ERR-03", "RS-ERR-03ab", " RS-ERR-03"],
)
def test_what_is_not_a_rule_id_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="not a rule ID"):
        RuleId.parse(text)


def test_rule_ids_order_by_number_and_then_by_inserted_letter() -> None:
    spelled = ["XS-CORE-09", "XS-CORE-10", "XS-CORE-12", "XS-CORE-12a", "XS-CORE-12b"]
    ids = [RuleId.parse(t) for t in spelled]
    assert sorted(shuffled(ids)) == ids
    assert RuleId.parse("XS-ERR-100") > RuleId.parse("XS-ERR-99")


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


def test_an_edition_is_a_year_and_orders_among_editions() -> None:
    """Rust's editions read, print and order as versions do."""
    spelled = ["2015", "2018", "2021", "2024"]
    editions = [Version.parse(t) for t in spelled]
    assert [str(e) for e in editions] == spelled
    assert sorted(shuffled(editions)) == editions
    assert all(e.edition and e.series == e for e in editions)
    assert not Version.parse("1.99").edition
    assert Version.released("2024") is None
    assert Version.search("edition 2024") is None


@pytest.mark.parametrize("parts", [(24,), (99999,)])
def test_one_number_that_is_no_year_is_no_version(parts: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="not the parts of a version"):
        Version(parts)


def test_minor_numbers_order_as_numbers() -> None:
    assert Version.parse("0.9.0") < Version.parse("0.10.0")


@pytest.mark.parametrize(
    "text",
    [
        *("3", "1.2.3.post1", "01.2", "1.2rc", "1..2", "v1.2", "1.2-rc1", ""),
        *("999", "10000", "0999", "2024rc1", "2024+x"),
    ],
)
def test_what_cannot_be_ordered_is_not_a_version(text: str) -> None:
    with pytest.raises(ValueError, match="not a version this can order"):
        Version.parse(text)


def test_a_floor_and_an_exact_pin_differ() -> None:
    assert Pin.parse("ruff==0.17.3").exact
    assert not Pin.parse("rustc>=1.99").exact
    assert Pin.parse("ruff==0.17.3").version == Version.parse("0.17.3")


@pytest.mark.parametrize(
    ("text", "pin"),
    [
        ("ripgrep-bin==15.2.0", Pin("ripgrep-bin", Version((15, 2, 0)))),
        ("bevy=0.20.1", Pin("bevy", Version((0, 20, 1)), Op.CARGO)),
        (
            "cpython-3.15.2+freethreaded",
            Pin("cpython", Version((3, 15, 2), local="freethreaded"), Op.REQUEST),
        ),
        ("rust==1.99", Pin("rust", Version((1, 99)))),
    ],
)
def test_every_spelling_a_pin_is_copied_in_reads_as_one(text: str, pin: Pin) -> None:
    """A requirement, a Cargo dependency, a `uv` request: one type."""
    assert Pin.parse(text) == pin
    assert str(pin) == text
    assert pin.exact


def test_a_request_names_an_interpreter_the_first_dash_divides() -> None:
    """`uv`'s key has a dash for its operator, as a tool may."""
    with pytest.raises(ValueError, match="not a tool name"):
        Pin("python-build", Version((3, 15)), Op.REQUEST)


def test_a_local_label_is_a_build_of_the_same_public_release() -> None:
    built = Version.parse("3.15.2+freethreaded")
    assert built.public == Version.parse("3.15.2")
    assert str(built.public) == "3.15.2"
    assert Version.parse("3.15.2") < built < Version.parse("3.15.3")


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


def test_a_token_that_is_no_rule_id_reads_as_none() -> None:
    assert RuleId.try_parse("XS-ERR-03") == RuleId("XS", "ERR", 3)
    assert RuleId.try_parse("`XS-ERR-03`") is None
    assert RuleId.try_parse("XS-ERR") is None


def test_an_id_is_cited_only_whole() -> None:
    text = "XS-ERR-03, XS-OUT-12a; not XS-ERR-04b2, AXS-ERR-05 or XS-ERR-06_x."
    assert [str(r) for r in cited(text)] == ["XS-ERR-03", "XS-OUT-12a"]
    assert [str(r) for r in cited(f"{text} YS-ERR-01", "YS")] == ["YS-ERR-01"]
    assert uncited("XS-ERR-03 and XS-OUT-01.") == " and ."


def test_a_citation_is_found_on_its_line() -> None:
    """A form feed ends no line here, as it ends none in an editor."""
    text = "XS-ERR-03\n\nsee XS-OUT-12a and\fXS-ERR-04\nYS-ERR-01"
    assert [(str(r), n) for r, n in cited_lines(text)] == [
        ("XS-ERR-03", 1),
        ("XS-OUT-12a", 3),
        ("XS-ERR-04", 3),
        ("YS-ERR-01", 4),
    ]


@pytest.mark.parametrize(
    ("text", "rid"),
    [
        ("XS-ERR-03", RuleId("XS", "ERR", 3)),
        ("XS-ERR-03),", RuleId("XS", "ERR", 3)),
        ("XS-ERR-03's", RuleId("XS", "ERR", 3)),
        ("XS-CORE-12a.", RuleId("XS", "CORE", 12, "a")),
        ("XS-ERR-03ab", None),
        ("XS-ERR-03_", None),
        ("(XS-ERR-03", None),
        ("XS-ERR", None),
    ],
)
def test_a_word_opens_with_the_id_it_cites(text: str, rid: RuleId | None) -> None:
    assert leading(text) == rid


def test_where_a_citation_ends_is_where_what_follows_it_begins() -> None:
    text = "see XS-ERR-03 below"
    ((rid, end),) = cited_at(text)
    assert rid == RuleId("XS", "ERR", 3)
    assert text[end:] == " below"


def test_a_range_reads_back_as_it_was_printed() -> None:
    one, nine = RuleId("XS", "ERR", 1), RuleId("XS", "ERR", 9)
    mig = RuleId("XS", "MIG", 1)
    text = f"ran {print_range(one, nine)} and {print_range(mig, mig)}."
    assert text == f"ran `XS-ERR-01`{DASH}`XS-ERR-09` and `XS-MIG-01`."
    assert list(ranges(text)) == [(one, nine), (mig, mig)]


@pytest.mark.parametrize(
    ("said", "named"),
    [
        ("ripgrep 15.2.0 (rev e89fff89ac)", "15.2.0"),
        ("rustc 1.100.0-nightly (abc 2026-01-01)", "1.100.0"),
        ("ty 0.0.99 (2c3e 2026-10-01)", "0.0.99"),
        ("cpython 3.15.0rc1+freethreaded", "3.15.0rc1+freethreaded"),
    ],
)
def test_a_version_is_found_among_other_words(said: str, named: str) -> None:
    assert Version.search(said) == Version.parse(named)


@pytest.mark.parametrize("said", ["1.2.3.post1", "v1.2.3", "no version", ""])
def test_a_version_run_into_a_word_is_none(said: str) -> None:
    assert Version.search(said) is None


@pytest.mark.parametrize(
    ("text", "series"),
    [("3.15.0rc1", "3.15"), ("1.99", "1.99"), ("0.20.1", "0.20")],
)
def test_a_release_belongs_to_its_major_minor(text: str, series: str) -> None:
    assert Version.parse(text).series == Version.parse(series)
    assert str(Version.parse(text).series) == series


def test_a_release_prose_names_is_its_major_minor() -> None:
    text = "since 3.9, in 3.13.1, not 3.5x faster, ~3.2 ns, 0.05 or 13.14"
    assert [str(v) for v in releases(text, 3)] == ["3.9", "3.13"]


# ------------------------------------------------------------------
# the relation a rule stands in, and the law it is held to


def test_a_relation_reads_back_as_it_was_printed() -> None:
    for relation in Relation:
        assert Relation.parse(str(relation)) is relation
    assert Relation.try_parse("replaces") is None
    assert Relation.try_parse("Realises") is None


def test_a_tier_binds_more_code_up_the_order() -> None:
    assert Tier.S.binding < Tier.M_BANG.binding < Tier.M.binding


def test_a_delta_departs_by_the_three_relations_that_name_a_rule() -> None:
    assert set(DEPARTING) == {Relation.OVERRIDES, Relation.TIGHTENS, Relation.EXTENDS}
    assert all(r.ruled for r in DEPARTING)


S, MB, M = Tier.S, Tier.M_BANG, Tier.M
TIER, REASON = Breach.TIER, Breach.REASON

#: The law, row by row: the relation, the tier held against, the rule's
#: tier, whether a reason is given, and how the row breaks it.
LAW = [
    (Relation.REALISES, M, M, False, ()),
    (Relation.REALISES, M, M, True, ()),
    (Relation.REALISES, M, S, False, (TIER,)),
    (Relation.REALISES, S, MB, False, (TIER,)),
    (Relation.EXTENDS, MB, MB, True, ()),
    (Relation.EXTENDS, M, MB, True, (TIER,)),
    (Relation.EXTENDS, M, M, False, (REASON,)),
    (Relation.TIGHTENS, S, M, True, ()),
    (Relation.TIGHTENS, MB, M, True, ()),
    (Relation.TIGHTENS, S, MB, True, ()),
    (Relation.TIGHTENS, M, M, True, (TIER,)),
    (Relation.TIGHTENS, M, MB, True, (TIER,)),
    (Relation.TIGHTENS, M, S, False, (TIER, REASON)),
    (Relation.OVERRIDES, M, S, True, ()),
    (Relation.OVERRIDES, S, M, True, ()),
    (Relation.OVERRIDES, M, M, False, (REASON,)),
    (Relation.DECIDED, M, None, True, ()),
    (Relation.DECIDED, M, None, False, (REASON,)),
    (Relation.DECIDED, M, M, True, (TIER,)),
    (Relation.ABSENT, S, None, True, ()),
    (Relation.ABSENT, S, None, False, (REASON,)),
    (Relation.ABSENT, S, S, True, (TIER,)),
    # A tier not known breaks nothing: no rule is another finding.
    (Relation.REALISES, M, None, False, ()),
    (Relation.TIGHTENS, None, M, True, ()),
]


@pytest.mark.parametrize(("relation", "held", "tier", "said", "broken"), LAW)
def test_a_row_is_held_to_its_relations_law(
    relation: Relation,
    held: Tier | None,
    tier: Tier | None,
    said: bool,  # noqa: FBT001 — a column of the table above
    broken: tuple[Breach, ...],
) -> None:
    reason = "the domain's reason" if said else " "
    assert breaches(relation, held, tier, reason) == broken
