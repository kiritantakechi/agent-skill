"""The predicates every check shares.

Each of these was once implemented twice and fixed once.
"""

import pytest

from agent_skill.model import Marker, inside_tests, needs_c_object, repr_c_above
from agent_skill.text import code_only, strip_comment, syntax_for


@pytest.mark.parametrize(
    ("raw", "kind", "verdict", "bad"),
    [
        ("// verified", "verified", "", False),
        ("// verified — GOOD", "verified", "GOOD", False),
        ("// fragment — BAD: compiles, never runs", "fragment", "BAD", True),
        ("// does-not-compile — BAD", "does-not-compile", "BAD", True),
        ("# fragment — Cargo.toml", "fragment", "", False),
        ("// fragment — (quoted from std/testing.zig)", "fragment", "", False),
    ],
)
def test_marker_grammar(raw: str, kind: str, verdict: str, *, bad: bool) -> None:
    m = Marker(raw)
    assert m.valid
    assert m.kind == kind
    assert m.verdict == verdict
    assert m.bad is bad


def test_bad_in_a_qualifier_is_not_a_verdict() -> None:
    """`… a BAD frame` in prose does not classify the block."""
    assert not Marker("// verified — GOOD: not a BAD frame in sight").bad


def test_quotation_is_evidence() -> None:
    m = Marker("// fragment — (quoted from std/testing.zig)")
    assert m.quotation
    assert m.evidence


def test_strip_comment_keeps_a_url() -> None:
    assert (
        strip_comment('const u = "https://example.com"; // note')
        == 'const u = "https://example.com"; '
    )


def test_code_only_preserves_line_count() -> None:
    body = "a // x\n// y\nb"
    assert len(code_only(body).split("\n")) == 3


def test_python_floor_division_is_not_a_comment() -> None:
    """`//` is an operator in Python, not the start of a comment.

    Reading it as a comment truncated code: under the default syntax
    this line becomes `q = total `, so any Check a pattern searching for
    something after a floor division could not fire at all.
    """
    line = "q = total // count"
    assert strip_comment(line) == "q = total "
    assert strip_comment(line, *syntax_for("python")) == line


def test_python_hash_comment_is_stripped_but_not_inside_a_string() -> None:
    py = syntax_for("python")
    assert strip_comment("x = a // b  # note", *py) == "x = a // b  "
    assert strip_comment("u = 'http://x'  # n", *py) == "u = 'http://x'  "
    assert strip_comment('d = {"#": 1}  # y', *py) == 'd = {"#": 1}  '


def test_rust_keeps_the_default_and_single_quotes_stay_lifetimes() -> None:
    """A `'` delimiter for Rust would swallow the rest of the line."""
    assert strip_comment("fn f<'a>(s: &'a str) -> &'a str { s } // tail") == (
        "fn f<'a>(s: &'a str) -> &'a str { s } "
    )


def test_repr_c_is_per_item_not_per_block() -> None:
    lines = [
        "#[repr(C)]",
        "pub struct Header {",
        "    pub magic: u32,",
        "}",
        "pub struct Cursor {",
        "    pub offset: usize,",
        "}",
    ]
    assert repr_c_above(lines, 2)
    assert not repr_c_above(lines, 5)


def test_extern_struct_is_not_an_undefined_symbol() -> None:
    assert not needs_c_object("const H = extern struct { a: u8 };")
    assert needs_c_object('extern "c" fn strlen(s: [*:0]const u8) usize;')


def test_inside_tests_finds_only_the_test_body() -> None:
    body = (
        "const log = std.log.scoped(.a);\ntest foo {\n    const x = 1;\n}\nconst y = 2;"
    )
    assert inside_tests(body) == {1, 2, 3}
