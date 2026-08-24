"""Citations into another skill, and the override table."""

from __future__ import annotations

from agent_skill.checks.crossref import OVERRIDE_ROW, _plain, crossref
from agent_skill.model import discover


def test_the_override_table_is_parsed(skills):
    bevy = next(s for s in skills if s.name == "bevy-style")
    rows = OVERRIDE_ROW.findall(bevy.text)
    assert rows, "bevy-style states no override rows"
    assert all(theirs.startswith("RS-") and ours.startswith("BV-") for theirs, _, ours in rows)


def test_titles_compare_across_backtick_styles():
    assert _plain("Run `clippy::pedantic` at `warn`") == "run clippy::pedantic at warn"


def test_a_citation_into_a_missing_skill_is_not_checked(scratch):
    """The claim is about a document nobody here can read."""
    import shutil

    shutil.rmtree(scratch / "rust-style")
    assert list(crossref(discover(scratch))) == []


def test_a_dangling_citation_fails(scratch):
    path = scratch / "bevy-style" / "SKILL.md"
    path.write_text(path.read_text().replace("RS-API-24", "RS-API-99", 1))
    assert any("RS-API-99" in str(f) for f in crossref(discover(scratch)))


def test_a_stale_rule_id_in_the_apparatus_is_caught(tmp_path):
    """Renumbering a chapter left two ids in `lang/rust.py` pointing at the
    rules that had moved up, and nothing said so: `assets` validates the ids a
    skill ships, and this reads everything outside `skills/`."""
    from agent_skill.checks.crossref import _apparatus_citations

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "thing.py").write_text("# see BV-CAR-12 and BV-CAR-4242\n")
    known = {"BV": {"BV-CAR-12"}}

    found = [str(f) for f in _apparatus_citations(known, tmp_path)]
    assert len(found) == 1, found
    assert "BV-CAR-4242" in found[0]
