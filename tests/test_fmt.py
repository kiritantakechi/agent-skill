"""Rewriting an example the way `cargo fmt --check` will demand."""

lazy from pathlib import Path

from agent_skill import shared
from agent_skill.doc import canonical
from agent_skill.fmt import INJECTED, _bodies, format_skill
from agent_skill.lang.rust import BEVY_STYLE, RUST_STYLE
from agent_skill.profiles import _REGISTRY, profile_for
from agent_skill.report import Level
from structure_fixture import build, edit, reparse


def test_bodies_dedents_and_drops_the_injected_attribute(tmp_path: Path) -> None:
    src = tmp_path / "chapter.rs"
    src.write_text(
        "//! header\n\n"
        "pub mod bv_ecs_01 {\n"
        f"    {INJECTED}\n"
        "    // verified\n"
        "    fn a() {}\n"
        "}\n\n"
        "pub mod bv_ecs_02 {\n"
        f"    {INJECTED}\n"
        "    // verified\n"
        "    fn b() {}\n"
        "}\n"
    )
    assert _bodies(src, BEVY_STYLE) == [
        "// verified\nfn a() {}\n",
        "// verified\nfn b() {}\n",
    ]


def test_bodies_undoes_the_extractor_rebasing(tmp_path: Path) -> None:
    """`fmt` writes bodies back, so it must not store harness paths.

    `lang.rust._module` rewrites `crate::` and `mycrate::` to reach
    inside the wrapper module. Storing that rewrite is how the apparatus
    leaks its own crate name into an example a reader copies.
    """
    src = tmp_path / "structure.rs"
    src.write_text(
        "//! header\n\n"
        "pub mod rs_str_15 {\n"
        f"    {INJECTED}\n"
        "    // verified\n"
        "    use crate::structure::rs_str_15::util::Interner;\n"
        "    use rust_style_verify::structure::rs_str_15::parse;\n"
        "    macro_rules! m {\n"
        "        () => {\n"
        "            $crate::thing\n"
        "        };\n"
        "    }\n"
        "}\n"
    )
    body = _bodies(src, RUST_STYLE)[0]
    assert "use crate::util::Interner;" in body
    assert "use mycrate::parse;" in body
    assert "$crate::thing" in body
    assert "rs_str_15" not in body


def test_each_skill_compiles_as_its_own_crate() -> None:
    """One shared manifest would leave one of the two unverifiable."""
    assert RUST_STYLE.name != BEVY_STYLE.name
    assert "bevy" in "".join(BEVY_STYLE.dependencies)
    assert "bevy" not in "".join(RUST_STYLE.dependencies)


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


def test_every_rust_profile_names_a_crate() -> None:
    profile_for("rust-style")  # force registration by import
    for profile in _REGISTRY.values():
        if profile.toolchain == "rust":
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
        "differs from the shared template" in m for m, _ in shared.compare(drifted)
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
    assert any("no place for" in m for m, _ in shared.compare(stray))
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
