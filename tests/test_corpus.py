"""`origin` maps a global line back to where it came from.

Two offset subtractions around a `bisect`, exercised until now only
end-to-end. An off-by-one here does not fail anything: it reports a real
hit at the wrong line, in the wrong rule, and reads exactly like a
correct report.
"""

import pytest

from agent_skill.checks.corpus import Corpus, Unit
from agent_skill.ids import Location, RuleId


def corpus_of(*sizes: int) -> Corpus:
    """A corpus of units with the given line counts.

    Each unit's lines are numbered from 100.
    """
    built = Corpus()
    for n, size in enumerate(sizes):
        built.starts.append(sum(sizes[:n]))
        built.units.append(
            Unit(
                chapter=f"ch{n}.md",
                rule=RuleId("XX", "Y", n),
                raw=[f"line {i} of unit {n}" for i in range(size)],
                code=[f"line {i} of unit {n}" for i in range(size)],
                at=[100 + i for i in range(size)],
            )
        )
    return built


@pytest.mark.parametrize(
    ("line", "chapter", "rule", "at"),
    [
        (1, "ch0.md", "XX-Y-00", 100),  # first line of the corpus
        (3, "ch0.md", "XX-Y-00", 102),  # last line of the first unit
        (4, "ch1.md", "XX-Y-01", 100),  # first line of the second — the boundary
        (5, "ch1.md", "XX-Y-01", 101),
        (9, "ch2.md", "XX-Y-02", 103),  # last line of the corpus — unit2 spans 6..9
    ],
)
def test_a_global_line_resolves_to_its_unit(
    line: int, chapter: str, rule: str, at: int
) -> None:
    where, _ = corpus_of(3, 2, 4).origin(line)
    assert where == Location(None, f"references/{chapter}", at, RuleId.parse(rule))


def test_every_line_round_trips() -> None:
    """No line resolves into a neighbour, as an off-by-one would."""
    built = corpus_of(3, 2, 4)
    seen = [built.origin(n)[0] for n in range(1, 10)]
    assert len(set(seen)) == 9, "two global lines resolved to the same origin"
    files = [where.file for where in seen]
    assert (
        files
        == ["references/ch0.md"] * 3
        + ["references/ch1.md"] * 2
        + ["references/ch2.md"] * 4
    )


def test_a_single_unit_corpus_resolves_from_one() -> None:
    where, _ = corpus_of(1).origin(1)
    assert where == Location(None, "references/ch0.md", 100, RuleId("XX", "Y", 0))


def test_a_hit_is_printed_where_every_finding_is() -> None:
    """One printer for a place, the skill named, `[?]` never."""
    built = corpus_of(1)
    built.units[0] = Unit("SKILL.md", None, ["x"], ["x"], [7], "demo-style")
    assert str(built.origin(1)[0]) == "demo-style/SKILL.md:7"
