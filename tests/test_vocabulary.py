"""The shared chapter vocabulary."""

from agent_skill import vocabulary as v


def test_each_code_names_one_chapter() -> None:
    assert len(set(v.CHAPTERS.values())) == len(v.CHAPTERS)


def test_each_chapter_has_its_code() -> None:
    for stem, code in v.CHAPTERS.items():
        assert v.code_for(stem) == code


def test_a_name_joining_two_subjects_is_not_a_chapter() -> None:
    for stem in (
        "errors-and-control-flow",
        "traits-generics",
        "ui-render",
        "free-threading",
    ):
        assert not v.allowed(stem)
        assert not v.code_for(stem)


def test_the_review_protocol_is_allowed_and_owns_no_family() -> None:
    assert v.allowed(v.REVIEW)
    assert not v.code_for(v.REVIEW)


def test_every_required_chapter_is_allowed() -> None:
    assert all(v.allowed(stem) for stem in v.REQUIRED)


def test_core_is_not_a_chapter_code() -> None:
    assert v.CORE not in v.CHAPTERS.values()


def test_every_chapter_name_is_one_word() -> None:
    assert all(stem.isalpha() and stem.islower() for stem in v.CHAPTERS)


def test_the_zig_words_have_their_codes() -> None:
    assert [v.code_for(w) for w in ("assertions", "comptime", "memory", "interop")] == [
        "ASSERT",
        "COMPTIME",
        "MEM",
        "INTEROP",
    ]
