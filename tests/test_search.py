"""What a match covers, and the difference between "no" and "could not tell".

`find` turns a `--json` event into a span by counting newlines in the
matched text. `matches` answers True, False, or **None** — and the None
is the whole point of the `UNRUN` level: a search that could not run
must not be read as a search that found nothing.
"""

import pytest

from agent_skill.checks.corpus import Corpus, Unit
from agent_skill.checks.patterns import Pattern
from agent_skill.checks.search import Span, find, matches


def corpus_at(tmp_path, *bodies: str) -> Corpus:
    built = Corpus()
    built.raw_dir, built.code_dir = tmp_path / "raw", tmp_path / "code"
    built.raw_dir.mkdir(parents=True)
    built.code_dir.mkdir(parents=True)
    for n, body in enumerate(bodies):
        lines = body.split("\n")
        built.starts.append(sum(len(b.split("\n")) for b in bodies[:n]))
        built.units.append(
            Unit(f"ch{n}.md", f"XX-Y-{n:02d}", lines, lines, list(range(len(lines))))
        )
        (built.raw_dir / f"{n:04d}.txt").write_text(body + "\n")
        (built.code_dir / f"{n:04d}.txt").write_text(body + "\n")
    return built


def test_a_single_line_match_is_a_span_of_one_line(tmp_path):
    built = corpus_at(tmp_path, "alpha\nbeta\ngamma")
    spans, _ = find(built, Pattern("beta", "-E", "command"))
    assert spans == [Span(2, 2)]
    assert len(spans[0]) == 1


def test_a_multi_line_match_covers_exactly_its_lines(tmp_path):
    built = corpus_at(tmp_path, "try:\n    go()\nfinally:\n    stop()")
    spans, _ = find(built, Pattern("try:(?s).*finally:", "-E", "command"))
    assert spans == [Span(1, 3)], "the span must end on the line the match ends on"
    assert len(spans[0]) == 3


def test_a_span_is_numbered_across_units(tmp_path):
    built = corpus_at(tmp_path, "one\ntwo", "three\nfour")
    spans, _ = find(built, Pattern("four", "-E", "command"))
    assert spans == [Span(4, 4)], (
        "the second unit's lines continue the first unit's numbering"
    )


def test_a_pattern_the_searcher_rejects_gives_no_answer(tmp_path):
    """Not zero hits — no answer. The two must never collapse."""
    spans, _ = find(corpus_at(tmp_path, "anything"), Pattern("a(", "-E", "command"))
    assert spans is None


def test_a_pattern_that_matches_nothing_gives_an_empty_list(tmp_path):
    spans, _ = find(corpus_at(tmp_path, "anything"), Pattern("absent", "-E", "command"))
    assert spans == []
    assert spans is not None, "an empty result is an answer; None is the absence of one"


@pytest.mark.parametrize(
    ("snippet", "pattern", "expected"),
    [
        ("x = foo.unwrap()", Pattern(r"\.unwrap\(\)", "-E", "command"), True),
        ("x = 1", Pattern(r"\.unwrap\(\)", "-E", "command"), False),
        ("|x| f(x)", Pattern("|x| f(x)", "-F", "prose"), True),
        ("anything", Pattern("a(", "-E", "command"), None),
    ],
)
def test_matches_is_three_valued(snippet, pattern, expected):
    assert matches(snippet, pattern, "rust") is expected


def test_none_is_distinguishable_from_false_by_a_caller():
    """`if not matches(...)` reads None and False the same; callers must not."""
    unanswerable = matches("anything", Pattern("a(", "-E", "command"), "rust")
    negative = matches("x = 1", Pattern(r"\.unwrap\(\)", "-E", "command"), "rust")
    assert unanswerable is None and negative is False
    assert not unanswerable and not negative, (
        "both are falsy, which is exactly why the caller must test `is None`"
    )


def test_a_fixture_is_stripped_the_way_the_corpus_is():
    """`find` searches the comment-stripped copy; the fixture must be the same text.

    Otherwise a fixture whose match depends on comment content certifies
    a pattern that the corpus path can never fire on — the positive
    control and the specificity check would be answering about two
    different inputs.
    """
    code_only = Pattern(r"let unused", "-E", "command")
    assert code_only.over_comments is False
    assert matches("let unused = total;", code_only, "rust") is True
    assert matches("// let unused = total;", code_only, "rust") is False, (
        "the fixture kept its comment, so it certified a pattern the stripped corpus cannot match"
    )


def test_a_pattern_that_names_a_comment_keeps_its_fixture_whole():
    """The rule is that the two agree, not that either is always stripped."""
    over_comments = Pattern(r"^[ \t]*// (let |if |\})", "-E", "command")
    assert over_comments.over_comments is True
    assert (
        matches("    // let unused = compute_total(&items);", over_comments, "rust")
        is True
    )


def test_stripping_follows_the_language():
    """`//` is a comment in Rust and floor division in Python, and `find` already knows that."""
    after_slashes = Pattern(r"count", "-E", "command")
    assert matches("q = total // count", after_slashes, "python") is True
    assert matches("let q = total // count", after_slashes, "rust") is False
