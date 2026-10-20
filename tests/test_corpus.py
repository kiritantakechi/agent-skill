"""`origin` maps a global line back to where it came from.

Two offset subtractions around a `bisect`, exercised until now only end-to-end.
An off-by-one here does not fail anything: it reports a real hit at the wrong
line, in the wrong rule, and reads exactly like a correct report.
"""

import pytest

from agent_skill.checks.corpus import Corpus, Unit


def corpus_of(*sizes: int) -> Corpus:
    """A corpus of units with the given line counts, each line numbered from 100."""
    built = Corpus()
    for n, size in enumerate(sizes):
        built.starts.append(sum(sizes[:n]))
        built.units.append(
            Unit(
                chapter=f"ch{n}.md",
                rule=f"XX-Y-{n:02d}",
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
def test_a_global_line_resolves_to_its_unit(line, chapter, rule, at):
    found_chapter, found_rule, found_at, _ = corpus_of(3, 2, 4).origin(line)
    assert (found_chapter, found_rule, found_at) == (chapter, rule, at)


def test_every_line_round_trips():
    """No line resolves into a neighbour, which is what an off-by-one looks like."""
    built = corpus_of(3, 2, 4)
    seen = [built.origin(n)[:3] for n in range(1, 10)]
    assert len(set(seen)) == 9, "two global lines resolved to the same origin"
    for (chapter, _, _), unit in zip(seen[:3], ["ch0.md"] * 3, strict=True):
        assert chapter == unit
    assert seen[3][0] == "ch1.md" and seen[4][0] == "ch1.md"
    assert all(c == "ch2.md" for c, _, _ in seen[5:])


def test_a_single_unit_corpus_resolves_from_one():
    assert corpus_of(1).origin(1)[:3] == ("ch0.md", "XX-Y-00", 100)
