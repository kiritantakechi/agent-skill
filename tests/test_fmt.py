"""Rewriting an example the way `cargo fmt --check` will demand."""

from __future__ import annotations

from agent_skill.fmt import INJECTED, _bodies
from agent_skill.lang.rust import BEVY_STYLE, RUST_STYLE


def test_bodies_dedents_and_drops_the_injected_attribute(tmp_path):
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
    assert _bodies(src, BEVY_STYLE) == ["// verified\nfn a() {}\n", "// verified\nfn b() {}\n"]


def test_bodies_undoes_the_extractor_rebasing(tmp_path):
    """`fmt` writes bodies back into the skill, so it must not store harness paths.

    `lang.rust._module` rewrites `crate::` and `mycrate::` to reach inside the
    wrapper module. Storing that rewrite is how the apparatus leaks its own
    crate name into an example a reader copies.
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


def test_each_skill_compiles_as_its_own_crate():
    """One shared manifest would leave one of the two unverifiable."""
    assert RUST_STYLE.name != BEVY_STYLE.name
    assert "bevy" in "".join(BEVY_STYLE.dependencies)
    assert "bevy" not in "".join(RUST_STYLE.dependencies)


def test_the_two_bevy_relaxations_are_the_only_ones():
    allowed = {
        f"{section}.{name}"
        for section, table in BEVY_STYLE.lints.items()
        for name, level in table.items()
        if level == '"allow"'
    }
    assert allowed == {
        "rust.elided_lifetimes_in_paths",
        "clippy.needless_pass_by_value",
        "clippy.module_name_repetitions",
    }
    for kept in ("type_complexity", "too_many_arguments"):
        assert kept not in BEVY_STYLE.lints["clippy"]


def test_every_rust_profile_names_a_crate():
    from agent_skill.profiles import _REGISTRY, profile_for

    profile_for("rust-style")  # force registration by import
    for profile in _REGISTRY.values():
        if profile.toolchain == "rust":
            assert profile.crate is not None, profile.name
