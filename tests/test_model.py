"""The predicates every check shares.

Each of these was once implemented twice and fixed once.
"""

lazy from pathlib import Path

import pytest

from agent_skill.checks.lines import near
from agent_skill.lang import language
from agent_skill.lang.zig import inside_tests, needs_c_object
from agent_skill.model import Marker, Rename, Skill
from agent_skill.profiles import Profile
from agent_skill.profiles.rust_style import REPR_C


@pytest.mark.parametrize(
    ("raw", "kind", "verdict", "bad"),
    [
        ("// verified", "verified", "", False),
        ("// verified — GOOD", "verified", "GOOD", False),
        ("// fragment — BAD: compiles, never runs", "fragment", "BAD", True),
        ("// rejected — zig: unused local constant", "rejected", "", False),
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


@pytest.mark.parametrize("rid", ["DS-DATA-17", "DS-DATA-17a", "DS-CORE-12b"])
def test_a_rename_row_reads_every_rule_id_as_its_target(rid: str) -> None:
    """Every other rule-ID pattern took the letter; this one did not."""
    assert Rename("DS-DATA-16", f"`{rid}`", 0).target == rid


def test_bad_in_a_qualifier_is_not_a_verdict() -> None:
    """`… a BAD frame` in prose does not classify the block."""
    assert not Marker("// verified — GOOD: not a BAD frame in sight").bad


def test_quotation_is_evidence() -> None:
    m = Marker("// fragment — (quoted from std/testing.zig)")
    assert m.quotation
    assert m.evidence


def test_strip_comment_keeps_a_url() -> None:
    assert (
        language("rust").uncommented('const u = "https://example.com"; // note')
        == 'const u = "https://example.com"; '
    )


def test_code_only_preserves_line_count() -> None:
    body = "a // x\n// y\nb"
    assert len(language("rust").code(body).split("\n")) == 3


def test_python_floor_division_is_not_a_comment() -> None:
    """`//` is an operator in Python, not the start of a comment.

    Reading it as a comment truncated code: under the default syntax
    this line becomes `q = total `, so any Check a pattern searching for
    something after a floor division could not fire at all.
    """
    line = "q = total // count"
    assert language("rust").uncommented(line) == "q = total "
    assert language("python").uncommented(line) == line


def test_python_hash_comment_is_stripped_but_not_inside_a_string() -> None:
    py = language("python")
    assert py.uncommented("x = a // b  # note") == "x = a // b  "
    assert py.uncommented("u = 'http://x'  # n") == "u = 'http://x'  "
    assert py.uncommented('d = {"#": 1}  # y') == 'd = {"#": 1}  '


def test_rust_keeps_the_default_and_single_quotes_stay_lifetimes() -> None:
    """A `'` delimiter for Rust would swallow the rest of the line."""
    assert language("rust").uncommented(
        "fn f<'a>(s: &'a str) -> &'a str { s } // tail"
    ) == ("fn f<'a>(s: &'a str) -> &'a str { s } ")


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
    assert near(REPR_C, lines, 2)
    assert not near(REPR_C, lines, 5)


def test_extern_struct_is_not_an_undefined_symbol() -> None:
    assert not needs_c_object("const H = extern struct { a: u8 };")
    assert needs_c_object('extern "c" fn strlen(s: [*:0]const u8) usize;')


def test_inside_tests_finds_only_the_test_body() -> None:
    body = (
        "const log = std.log.scoped(.a);\ntest foo {\n    const x = 1;\n}\nconst y = 2;"
    )
    assert inside_tests(body) == {1, 2, 3}


def test_a_block_in_skill_md_is_an_example_like_any_other(tmp_path: Path) -> None:
    root = tmp_path / "demo-style"
    (root / "references").mkdir(parents=True)
    fence = "```zig\n// verified\nconst x = 1;\n```\n"
    (root / "SKILL.md").write_text("---\nname: demo-style\n---\n\n# Demo\n\n" + fence)
    skill = Skill(root, Profile(name="demo-style", prefix="DS"))

    (block,) = skill.blocks("zig", verified=True)

    assert block.file == "SKILL.md"
    assert skill.path_of(block.file) == root / "SKILL.md"
    assert skill.path_of("data.md") == root / "references" / "data.md"
