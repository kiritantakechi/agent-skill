"""A structure exemption carries its reason."""

from __future__ import annotations

from agent_skill.model import Marker
from agent_skill.profiles import Profile, exemption_problem, registered


def test_an_exemption_without_a_reason_is_a_problem():
    for reason in ("", "   "):
        profile = Profile(name="x-style", prefix="XS", exempt_from_structure=reason)
        assert exemption_problem(profile)


def test_no_exemption_is_not_a_problem():
    assert exemption_problem(Profile(name="x-style", prefix="XS")) is None


def test_every_registered_exemption_gives_a_reason():
    assert [p.name for p in registered() if exemption_problem(p)] == []


def test_a_rejected_marker_names_its_tool():
    assert Marker("# rejected — ty: invalid-argument-type").tool == "ty"
    assert Marker("// rejected — clippy: unwrap_used").tool == "clippy"
    assert Marker("# rejected — the GIL is off").tool == ""
    assert Marker("# rejected").tool == ""
