"""The shared chapter vocabulary."""

from agent_skill import vocabulary as v


def test_each_code_names_one_chapter() -> None:
    assert len(v.FAMILIES) == len(v.CHAPTERS)


def test_lookup_runs_both_ways() -> None:
    for stem, code in v.CHAPTERS.items():
        assert v.code_for(stem) == code
        assert v.chapter_for(code) == stem


def test_a_name_joining_two_subjects_is_not_a_chapter() -> None:
    for stem in (
        "errors-and-control-flow",
        "traits-generics",
        "ui-render",
        "free-threading",
    ):
        assert not v.allowed(stem)
        assert v.code_for(stem) is None


def test_the_review_protocol_is_allowed_and_owns_no_family() -> None:
    assert v.allowed(v.REVIEW)
    assert v.code_for(v.REVIEW) is None


def test_every_required_chapter_is_allowed() -> None:
    assert all(v.allowed(stem) for stem in v.REQUIRED)


def test_core_is_not_a_chapter_code() -> None:
    assert v.chapter_for(v.CORE) is None


def test_every_chapter_name_is_one_word() -> None:
    assert all(stem.isalpha() and stem.islower() for stem in v.CHAPTERS)
