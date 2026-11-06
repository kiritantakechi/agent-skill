"""The one reader of a standard's own line rules.

A profile states its rules as data — a `LineRule` is a pattern, a
message, and what excuses a hit — and this is what reads them, for
`conventions` over the examples and `prose` over the text around them.
What excuses a hit is also what `self-application` asks of a profile's
`exempt` entries, so a rule says what it permits in one vocabulary
wherever its pattern runs.
"""

import re
from dataclasses import dataclass
lazy from collections.abc import Collection, Iterable, Iterator, Sequence

from agent_skill.doc import Doc, Fence, Paragraph, printed
from agent_skill.doc.chapter import CHECK, owned
from agent_skill.lang import language
from agent_skill.report import DECLARED, Finding
lazy from agent_skill.doc import Block
lazy from agent_skill.ids import Branch, Location, RuleId
lazy from agent_skill.model import Skill
lazy from agent_skill.profiles import LineRule, Near, Unless


def near(found: Near, lines: Sequence[str], j: int) -> bool:
    """Is `found`'s pattern on line `j`, or on the lines it names?"""
    if found.own and re.search(found.pattern, lines[j]):
        return True
    for k in range(j - 1, max(-1, j - 1 - found.above), -1):
        if found.stop and re.search(found.stop, lines[k]):
            return False
        if re.search(found.pattern, lines[k]):
            return True
    return any(
        re.search(found.pattern, lines[k])
        for k in range(j + 1, min(len(lines), j + 1 + found.below))
    )


def excused(
    unless: Unless, lines: Sequence[str], j: int, tests: Collection[int]
) -> bool:
    """Is a hit on line `j` the case its rule permits?

    `tests` are the indices of `lines` inside a test.
    """
    if unless.outside_tests and j not in tests:
        return True
    return any(near(n, lines, j) for n in unless.near)


@dataclass(frozen=True, slots=True)
class _Line:
    """One line a rule is held to, and what is around it."""

    #: the line as written, and with its comment taken out
    raw: str
    code: str
    #: every line of what it is in, and its index there
    lines: Sequence[str]
    j: int
    #: the rule the line sits under, if any
    rule: RuleId | None
    #: the indices of `lines` inside a test
    tests: Collection[int]


def _broken(
    rules: Iterable[LineRule], line: _Line, where: Location
) -> Iterator[Finding]:
    """What `line` breaks: each branch once, at its leftmost hit.

    A rule stated as two patterns through one branch — a `catch` with
    no comment, one pattern for `unreachable` and one for `{}` — is one
    rule, and a line breaks it once, as one pattern of alternatives
    would say.
    """
    hits: dict[Branch, tuple[LineRule, re.Match[str]]] = {}
    for rule in rules:
        if rule.unless_own is not None and line.rule == rule.unless_own:
            continue
        m = re.search(rule.pattern, line.raw if rule.comments else line.code)
        if m is None or not all(near(n, line.lines, line.j) for n in rule.needs):
            continue
        if excused(rule.unless, line.lines, line.j, line.tests):
            continue
        if (first := hits.get(rule.branch)) is None or m.start() < first[1].start():
            hits[rule.branch] = (rule, m)
    for rule, m in hits.values():
        message = rule.message.format(m.group(0), *m.groups())
        yield Finding(DECLARED[rule.branch], message, where, rule.branch)


def examples(skill: Skill) -> Iterator[Finding]:
    """Each of the profile's own rules each advice example breaks.

    Line by line, in the order the profile states them, then each rule
    that reads the example's structure.
    """
    profile = skill.profile
    if not profile.conventions and not profile.structural:
        return
    for b in skill.advice():
        read = language(b.lang)
        lines = b.lines
        tests = read.tests(b.body)
        for j, raw in enumerate(lines):
            line = _Line(raw, read.uncommented(raw), lines, j, b.rule, tests)
            yield from _broken(profile.conventions, line, b.where_at(j))
        for structural in profile.structural:
            yield from structural(b)


def prose(skill: Skill) -> Iterator[Finding]:
    """Each of the profile's own rules a line of its prose breaks.

    Outside the paragraph a **Check:** label opens, which hunts the
    spelling a rule forbids, and under the rule each line sits in, since
    a rule's own text names what it forbids. A line is one of the
    chapter as printed: in a file `layout` passes, the file's own.
    """
    rules = skill.profile.prose
    if not rules:
        return
    for chapter in skill.chapters:
        text = str(chapter.doc)
        lines = text.split("\n")
        # A canonical file is its own printed text, and its parse is the
        # one the chapter holds.
        printed_doc = chapter.doc if text == chapter.text else Doc.parse(text)
        for block, rid in owned(printed_doc):
            if isinstance(block, Fence) or _checks(block):
                continue
            for k, line in enumerate(printed(block)):
                held = _Line(line, line, lines, block.line - 1 + k, rid, ())
                yield from _broken(rules, held, chapter.where(block.line + k, rid))


def _checks(block: Block) -> bool:
    """Is `block` the paragraph a **Check:** label opens?"""
    return isinstance(block, Paragraph) and block.text.startswith(CHECK)
