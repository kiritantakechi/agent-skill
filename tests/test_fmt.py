"""Rewriting an example the way `cargo fmt --check` will demand."""

from dataclasses import replace
lazy from pathlib import Path

import pytest

from agent_skill import shared
from agent_skill.doc import canonical
from agent_skill.fmt import format_skill, put_back
from agent_skill.lang import toolchain_for
from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.lang.rust import BEVY_STYLE, RUST_STYLE, rebase, unrebase
from agent_skill.lang.zig import ZIG_STYLE
from agent_skill.profiles import PROFILES
from agent_skill.report import Level
from structure_fixture import DEMO, build, edit, reparse


def test_rebasing_points_a_block_into_its_module_and_back() -> None:
    """`fmt` writes bodies back, so it must not store harness paths.

    `rebase` rewrites `crate::` and `mycrate::` to reach the block's
    module file. Storing that rewrite is how the apparatus leaks its
    own crate name into an example a reader copies.
    """
    body = (
        "// verified\n"
        "use crate::util::Interner;\n"
        "use mycrate::parse;\n"
        "macro_rules! m {\n"
        "    () => {\n"
        "        $crate::thing\n"
        "    };\n"
        "}\n"
    )
    rebased = rebase(body, RUST_STYLE, "structure", "rs_str_15")
    assert "use crate::structure::rs_str_15::util::Interner;" in rebased
    assert "use rust_style_verify::structure::rs_str_15::parse;" in rebased
    assert "$crate::structure::rs_str_15::thing" in rebased
    assert unrebase(rebased, RUST_STYLE, "structure", "rs_str_15") == body


def test_a_block_is_put_back_by_its_line(tmp_path: Path) -> None:
    """Two blocks with one body: the one asked for is the one rewritten.

    Found by its text, a block written twice in a chapter could not be
    told from its twin and was skipped.
    """
    demo = build(tmp_path)
    chapter = demo.root / "references" / "errors.md"
    fence = "```rust\n// verified\nfn a() {}\n```\n"
    chapter.write_text(chapter.read_text() + f"\n{fence}\n{fence}")
    demo = reparse(demo)
    first, second = demo.blocks("rust")
    assert first.body == second.body

    (changed,) = put_back(demo, {second: "// verified\nfn a() -> u8 {\n    0\n}\n"})

    assert changed.level is Level.NOTE
    text = chapter.read_text()
    assert text.count(fence) == 1
    assert text.endswith("```rust\n// verified\nfn a() -> u8 {\n    0\n}\n```\n")


def test_a_block_that_moved_is_skipped(tmp_path: Path) -> None:
    demo = build(tmp_path)
    chapter = demo.root / "references" / "errors.md"
    chapter.write_text(chapter.read_text() + "\n```rust\n// verified\nfn a() {}\n```\n")
    (block,) = reparse(demo).blocks("rust")
    chapter.write_text("\n" + chapter.read_text())

    (skipped,) = put_back(demo, {block: "// verified\nfn b() {}\n"})

    assert skipped.level is Level.FAIL
    assert "fn b" not in chapter.read_text()


def test_each_skill_compiles_as_its_own_crate() -> None:
    """One shared manifest would leave one of the two unverifiable."""
    assert RUST_STYLE.name != BEVY_STYLE.name
    assert BEVY_STYLE.library is not None
    assert "bevy" in BEVY_STYLE.manifest()
    assert RUST_STYLE.library is None
    assert "bevy" not in RUST_STYLE.manifest()


def test_the_two_bevy_relaxations_are_the_only_ones() -> None:
    allowed = {
        f"{section}.{name}"
        for section, table in BEVY_STYLE.lints.items()
        for name, level in table.items()
        if level == '"allow"'
    }
    assert allowed == {
        "rust.elided_lifetimes_in_paths",
        "clippy.needless_pass_by_value",
    }
    for kept in ("type_complexity", "too_many_arguments"):
        assert kept not in BEVY_STYLE.lints["clippy"]


def test_every_profile_that_compiles_rust_names_a_crate() -> None:
    for profile in PROFILES.values():
        if "rust" in profile.languages:
            assert profile.crate is not None, profile.name


def test_a_drifted_shared_passage_is_reported_and_rewritten(tmp_path: Path) -> None:
    """The round trip `shared-text` promises.

    Drift is found, `fmt` repairs it, and the text the skill wrote in a
    free region survives the repair.
    """
    demo = build(tmp_path)
    assert list(shared.compare(demo)) == []
    drifted = edit(demo, "SKILL.md", "Apply it literally.", "Apply it with judgement.")
    assert any(
        "differs from the shared template" in f.message for f in shared.compare(drifted)
    )
    assert format_skill(drifted)
    assert list(shared.compare(drifted)) == []
    text = drifted.skill_md.read_text()
    assert "Apply it literally." in text
    assert '**Code is "library"** — if it is published.' in text


def test_text_outside_a_free_region_is_left_for_a_person(tmp_path: Path) -> None:
    demo = build(tmp_path)
    stray = edit(
        demo, "SKILL.md", "Rules are cited by ID", "An aside.\n\nRules are cited by ID"
    )
    assert any("no place for" in f.message for f in shared.compare(stray))
    before = stray.skill_md.read_text()
    (left,) = shared.rewrite(stray)
    assert left.level is Level.FAIL
    assert "not rewritten" in left.message
    assert stray.skill_md.read_text() == before


def test_fmt_brings_a_prose_line_back_under_the_limit(tmp_path: Path) -> None:
    demo = build(tmp_path)
    long_line = "Subtract. " + "word " * 25 + "end."
    drifted = edit(demo, "SKILL.md", "Subtract.", long_line)
    assert format_skill(drifted)
    prose = [
        ln for ln in drifted.skill_md.read_text().split("\n") if not ln.startswith("|")
    ]
    assert all(len(line) <= 100 for line in prose)


def test_fmt_leaves_every_file_canonical_and_then_changes_nothing(
    tmp_path: Path,
) -> None:
    """`fmt` is a projection: what it writes, it would write again."""
    demo = build(tmp_path)
    drifted = edit(demo, "SKILL.md", "Apply it literally.", "Apply it with judgement.")
    drifted = edit(drifted, "SKILL.md", "Subtract.", "Subtract.\n\n\n" + "word " * 30)
    assert format_skill(drifted)
    texts = {p: p.read_text() for p in drifted.markdown}
    assert all(text == canonical(text) for text in texts.values())
    assert format_skill(drifted) == []
    assert {p: p.read_text() for p in drifted.markdown} == texts


def test_how_a_shared_passage_is_filled_is_never_a_finding(tmp_path: Path) -> None:
    """The copy and the template are compared as trees, not as lines."""
    demo = build(tmp_path)
    text = demo.skill_md.read_text()
    at = text.index("\n", text.index("Rules are cited by ID"))
    demo.skill_md.write_text(f"{text[:at]}   {text[at + 1 :]}")
    assert list(shared.compare(reparse(demo))) == []


#: Each toolchain's settings, a block its formatter rewrites, and what
#: it rewrites the block to.
UNFORMATTED = {
    "python": (PYTHON_STYLE, "# verified\nx=1\n", "# verified\nx = 1\n"),
    "rust": (RUST_STYLE, "// verified\nfn  a( ) {}\n", "// verified\nfn a() {}\n"),
    "zig": (ZIG_STYLE, "// verified\nfn a() void{}\n", "// verified\nfn a() void {}\n"),
}


@pytest.mark.toolchain
@pytest.mark.parametrize("kind", UNFORMATTED)
def test_fmt_writes_back_what_each_formatter_prints(tmp_path: Path, kind: str) -> None:
    """`restore ∘ format ∘ extract`; Zig had no write-back before it."""
    config, body, formatted = UNFORMATTED[kind]
    tc = toolchain_for(config)
    assert tc is not None
    if tc.missing():
        pytest.skip(f"needs {tc.name}")
    fence = tc.language.fence
    demo = build(tmp_path, replace(DEMO, languages=(fence,), toolchain=config))
    chapter = demo.root / "references" / "errors.md"
    chapter.write_text(f"{chapter.read_text()}\n```{fence}\n{body}```\n")

    changed = format_skill(reparse(demo))

    assert any(f.message == "1 block(s) reformatted" for f in changed), changed
    (block,) = reparse(demo).blocks(fence)
    assert block.body == formatted
    assert format_skill(reparse(demo)) == []
