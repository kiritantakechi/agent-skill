"""Rule anatomy: what a rule is made of, and that the map still fits."""

import itertools
import re
from collections import Counter, defaultdict
lazy from collections.abc import Iterable, Iterator

from agent_skill import shared
from agent_skill.checks import check, per_skill
from agent_skill.doc import (
    Divider,
    Fence,
    Heading,
    ListBlock,
    Paragraph,
    Quote,
    Table,
    printed,
    text_of,
)
from agent_skill.doc.chapter import LABEL, ORDER, WHY, Element, citing
from agent_skill.doc.normal import qualified, quoted, runs
from agent_skill.ids import (
    DASH,
    FAMILY,
    NUMBER,
    RuleId,
    Tier,
    cited,
    releases,
    rule_id,
    uncited,
)
from agent_skill.model import SKILL_MD, Marker, marker_line
from agent_skill.report import Level, declare, fail, note
lazy from agent_skill.doc import Block
lazy from agent_skill.doc.chapter import Entry, Rule
lazy from agent_skill.ids import Location
lazy from agent_skill.model import Chapter, Skill
lazy from agent_skill.report import Finding

#: Words that carry no signal when comparing two rationales.
STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "it",
        "for",
        "that",
        "this",
        "be",
        "are",
        "as",
        "with",
        "on",
        "not",
        "you",
        "your",
        "which",
        "what",
        "when",
        "its",
        "than",
        "then",
        "so",
        "but",
        "if",
        "by",
        "at",
        "from",
        "can",
        "cannot",
    ]
)

#: Above this overlap with its own statement, a Why says the rule again
#: rather than giving a reason for it.
RESTATES = 0.42

#: A Why or Check this short or shorter is not compared for
#: near-duplicates.
SHORT_SECTION = 60

#: Above this overlap, two Whys or two Checks are one text kept twice.
NEAR_DUPLICATE = 0.45

#: A word this short or shorter carries no signal when matching a
#: summary to the rule it cites.
SHORT_WORD = 2

#: How much closer, absolutely, another rule must match a summary than
#: the rule it cites before the citation reads as off by one.
CLOSER_BY = 0.15

# The branches a finding of this check comes from.
BOLD_DEFINITIONS = declare("anatomy", "bold_definitions", Level.FAIL)
DUPLICATE = declare("anatomy", "duplicate", Level.FAIL)
CONTENTS_MISSING = declare("anatomy", "contents_missing", Level.FAIL)
CONTENTS_TIER = declare("anatomy", "contents_tier", Level.FAIL)
CONTENTS_TITLE = declare("anatomy", "contents_title", Level.FAIL)
NO_RELAXED = declare("anatomy", "no_relaxed", Level.FAIL)
RELAXED_LABEL = declare("anatomy", "relaxed_label", Level.FAIL)
RELAXED_ORDER = declare("anatomy", "relaxed_order", Level.FAIL)
RESTATES_RULE = declare("anatomy", "restates", Level.FAIL)
CONTENTS_ORDER = declare("anatomy", "contents_order", Level.FAIL)
SHARED_TITLE = declare("anatomy", "shared_title", Level.FAIL)
UNSTATED = declare("anatomy", "unstated", Level.FAIL)
MIS_CITED = declare("anatomy", "mis_cited", Level.NOTE)
ABBREVIATED = declare("anatomy", "abbreviated", Level.FAIL)
DANGLING = declare("anatomy", "dangling", Level.FAIL)
MISSING_FILE = declare("anatomy", "missing_file", Level.FAIL)
WRONG_CHAPTER = declare("anatomy", "wrong_chapter", Level.FAIL)
CORE_UNCITED = declare("anatomy", "core_uncited", Level.FAIL)
CORE_NOT_A_RULE = declare("anatomy", "core_not_a_rule", Level.FAIL)
CORE_WRONG_CHAPTER = declare("anatomy", "core_wrong_chapter", Level.FAIL)
MAP_TOTAL = declare("anatomy", "map_total", Level.FAIL)
MAP_FAMILY = declare("anatomy", "map_family", Level.FAIL)
MAP_HERE = declare("anatomy", "map_here", Level.FAIL)
NEAR_DUPLICATE_TEXT = declare("anatomy", "near_duplicate", Level.FAIL)
JUNK = declare("anatomy", "junk", Level.NOTE)
BELOW_TARGET = declare("anatomy", "below_target", Level.FAIL)
WHY_LENGTH = declare("anatomy", "why_length", Level.FAIL)
NUMBERING = declare("anatomy", "numbering", Level.FAIL)

# The branches only a normalised standard is held to (`_normal_form`).
RESTATED_TITLE = declare("anatomy", "restated_title", Level.FAIL)
ELEMENT_ORDER = declare("anatomy", "element_order", Level.FAIL)
STRAY = declare("anatomy", "stray", Level.FAIL)
POLARITY = declare("anatomy", "polarity", Level.FAIL)
RELAXED_TIER = declare("anatomy", "relaxed_tier", Level.FAIL)
QUOTED_CITATION = declare("anatomy", "quoted_citation", Level.FAIL)
PATH_CITATION = declare("anatomy", "path_citation", Level.FAIL)
PROSE_GREP = declare("anatomy", "prose_grep", Level.FAIL)
LOCAL_SCOPE = declare("anatomy", "local_scope", Level.FAIL)
ADVICE_TITLE = declare("anatomy", "advice_title", Level.FAIL)


def shingles(s: str, n: int = 4) -> set[tuple[str, ...]]:
    """Every run of `n` consecutive words in `s`, minus stop words."""
    words = [w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP]
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def overlap[T](a: set[T], b: set[T]) -> float:
    """The Jaccard index of `a` and `b`; 0.0 when either is empty."""
    return len(a & b) / len(a | b) if a and b else 0.0


@check("anatomy", "rule anatomy, ToC agreement, cross-references")
@per_skill
def anatomy(skill: Skill) -> Iterator[Finding]:
    """Each rule's shape, and every map and citation of the rules."""
    seen: dict[RuleId, str] = {}
    titles: dict[str, list[RuleId]] = defaultdict(list)
    parts: dict[tuple[RuleId, str], str] = {}

    for chapter in skill.chapters:
        if _bold_definitions(chapter, skill.prefix):
            yield fail(
                "bold-inline rule definitions", chapter.where(), BOLD_DEFINITIONS
            )
        toc = _toc(chapter)
        for rule in chapter.typed.rules:
            if rule.id in seen:
                yield fail(
                    f"duplicate {rule.id}, also in {seen[rule.id]}",
                    chapter.where(rule.line),
                    DUPLICATE,
                )
            seen[rule.id] = chapter.name
            titles[rule.title].append(rule.id)
            yield from _rule(chapter, rule, toc)
            for label, part in (("Why", rule.why), ("Check", rule.check)):
                if part:
                    parts[(rule.id, label)] = _said(part)

    yield from structural(skill)
    yield from _contents_order(skill)
    yield from _unique_titles(skill, titles)
    yield from _mis_cited(skill)
    yield from _references(skill, seen)
    yield from _abbreviated(skill)
    yield from _counts(skill)
    yield from _near_duplicates(skill, parts)
    if skill.profile.normalized:
        yield from _normal_form(skill)


def _toc(chapter: Chapter) -> dict[RuleId, Entry]:
    """The chapter's contents entries, by the ID each lists."""
    contents = chapter.typed.contents
    return {e.id: e for e in contents.entries} if contents is not None else {}


def _said(part: Iterable[Block]) -> str:
    """What a labelled part says, on one line, its label left out."""
    return " ".join(text_of(part).split()[1:])


def _bold_definitions(chapter: Chapter, prefix: str) -> bool:
    """Does a paragraph open with a bold rule ID, defining a rule there?

    A bold ID inside a paragraph is a citation, wherever filling happens
    to break its line.
    """
    return any(
        isinstance(block, Paragraph) and _opens_bold_id(block.text, prefix)
        for block in chapter.doc.blocks
    )


def _opens_bold_id(text: str, prefix: str) -> bool:
    """Does `text` open with an ID of this standard set in bold?"""
    inner, bold, _ = text.removeprefix("**").partition("**")
    rid = RuleId.try_parse(inner) if text.startswith("**") and bold else None
    return rid is not None and rid.standard == prefix


#: How a rule states what an `[M!]` relaxes to: one label, in the
#: statement, so a reader meets the relaxed reading before the reason.
#: It may open a paragraph or sit inside one, so it is looked for in
#: the text of each block.
RELAXED = "*Relaxed form:*"
_RELAXED = re.compile(r"\*{1,2}Relaxed\s+form:?\*{1,2}:?")


def _rule(chapter: Chapter, rule: Rule, toc: dict[RuleId, Entry]) -> Iterator[Finding]:
    """One rule against its contents line, its tier and its parts."""
    where = chapter.where(rule.line)
    entry = toc.get(rule.id)
    if entry is None:
        yield fail(
            f"{rule.id} missing from the chapter contents", where, CONTENTS_MISSING
        )
    elif entry.tier != rule.tier:
        yield fail(f"{rule.id} contents tier != heading tier", where, CONTENTS_TIER)
    elif entry.title != rule.title:
        yield fail(f"{rule.id} contents title != heading title", where, CONTENTS_TITLE)

    yield from _relaxed(rule, where)
    yield from _shape(rule, where)

    if rule.why and rule.check:
        a, c = shingles(text_of(rule.statement)), shingles(_said(rule.why))
        if overlap(a, c) > RESTATES:
            yield fail(f"{rule.id} Why merely restates the rule", where, RESTATES_RULE)


def _relaxed(rule: Rule, where: Location) -> Iterator[Finding]:
    """An `[M!]` rule's relaxed form: stated, labelled, and first."""
    found = next(
        (
            (i, m)
            for i, block in enumerate(rule.body)
            if (m := _RELAXED.search(text_of((block,))))
        ),
        None,
    )
    why = next(
        (
            i
            for i, b in enumerate(rule.body)
            if isinstance(b, Paragraph) and b.text.startswith(WHY)
        ),
        None,
    )
    if found is None:
        if rule.tier is Tier.M_BANG:
            yield fail(f"{rule.id} is [M!] with no relaxed form", where, NO_RELAXED)
    elif (label := " ".join(found[1].group(0).split())) != RELAXED:
        yield fail(
            f"{rule.id} labels its relaxed form `{label}`; the label is `{RELAXED}`",
            where,
            RELAXED_LABEL,
        )
    elif why is not None and found[0] >= why:
        yield fail(
            f"{rule.id}'s relaxed form follows its Why; it is part of the "
            "statement, so it comes first",
            where,
            RELAXED_ORDER,
        )


def _contents_order(skill: Skill) -> Iterator[Finding]:
    """The contents list keeps the chapter's order, or it is no map."""
    for chapter in skill.chapters:
        listed = list(_toc(chapter))
        if listed and listed != [r.id for r in chapter.typed.rules]:
            yield fail(
                "contents order != heading order", chapter.where(), CONTENTS_ORDER
            )


def _unique_titles(skill: Skill, titles: dict[str, list[RuleId]]) -> Iterator[Finding]:
    """A title is an anchor, so it has to be unique.

    `titles[title] = rid` silently kept whichever chapter sorted last.
    """
    for title, ids in sorted(titles.items()):
        if len(ids) > 1:
            named = ", ".join(str(rid) for rid in ids)
            yield fail(
                f"{len(ids)} rules share the title {title!r} ({named}); "
                f"a title is an anchor and must be unique",
                skill.at(),
                SHARED_TITLE,
            )


def _shape(rule: Rule, where: Location) -> Iterator[Finding]:
    """A rule states its own Why and Check.

    A rule that only names the rule owning its topic is a second place
    to read and keep in step: a zig-style rule pointed at the migration
    chapter, then kept a two-row copy of that chapter's table whose rows
    were already in it. Such a rule merges into its owner.
    """
    if not (rule.why and rule.check):
        which = "Why" if not rule.why else "Check"
        yield fail(f"{rule.id} states no {which}", where, UNSTATED)


def _citation(prefix: str) -> re.Pattern[str]:
    """A core rule's citation: a chapter, then the IDs it holds.

    `` `references/api.md` RS-API-15, RS-API-16 ``. Matched in the
    rule's text, which the document model keeps whole.
    """
    one = rule_id(prefix)
    return re.compile(
        rf"`references/([a-z0-9-]+\.md)` ((?:{one})(?:,? (?:and )?{one})*)"
    )


def _unnamed(text: str) -> str:
    """`text` without the chapters and rules it cites.

    A citation carries no signal when matching a summary to the rule it
    cites.
    """
    return uncited(re.sub(r"`references/[^`]+`", "", text))


def _words(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z_]+", text.lower())
        if w not in STOP and len(w) > SHORT_WORD
    }


def _mis_cited(skill: Skill) -> Iterator[Finding]:
    """A core rule citing a sibling of the rule it is actually about.

    `BV-CORE-16` summarised the `EntityEvent` rule and cited the rule
    above it. Everything mechanical passed: the id existed and lived in
    the cited chapter, which is all `_references` asks.

    The test is **relative**, not a threshold. A well-written summary
    says the same thing in different words, so absolute overlap
    separates nothing — a correct citation here scores 0.000. What does
    separate is another rule in the same chapter scoring much higher,
    which is what an off-by-one looks like. A note rather than a
    failure: the metric is text, and two of its five hits over three
    skills were coincidence.
    """
    by_file = {c.name: c.typed.rules for c in skill.chapters}
    by_id = {r.id: r for r in skill.chapter_rules}
    pre = skill.prefix
    cite = _citation(pre)
    for core in skill.core:
        flat = " ".join(text_of(core.body).split())
        cites = cite.findall(flat)
        named = {t for _, ids in cites for t in cited(ids, pre)}
        summary = _words(_unnamed(flat))
        for fname, ids in cites:
            for target in cited(ids, pre):
                rule = by_id.get(target)
                if rule is None:
                    continue
                mine = overlap(summary, _words(_summary(rule)))
                for other in by_file.get(fname, ()):
                    if other.id in named:
                        continue
                    theirs = overlap(summary, _words(_summary(other)))
                    if theirs > mine * 2 and theirs - mine > CLOSER_BY:
                        yield note(
                            f"{core.id} cites {target} ({rule.title!r}) but "
                            f"{other.id} ({other.title!r}) is a closer match",
                            skill.at(),
                            MIS_CITED,
                        )


def _summary(rule: Rule) -> str:
    """A chapter rule's title and statement: what a summary restates."""
    return f"{rule.title} {text_of(rule.statement)}"


def _references(skill: Skill, seen: dict[RuleId, str]) -> Iterator[Finding]:
    """Every cited id resolves, in the chapter the citation names."""
    yield from _dangling(skill)
    home = dict(seen.items())
    yield from _paths(skill, home)
    yield from _core_citations(skill, home)


#: A rule ID followed by a bare number that leans on it: `ZS-ASSERT-03,
#: -07 and -20`, or the range `ZS-MEM-19..23`. `renumber` rewrites whole
#: IDs only, so the bare ones kept their old numbers and named other
#: rules. Matched in a block's text, which the document model keeps
#: whole.
_ABBREVIATED = re.compile(
    rf"\b{rule_id()}"
    rf"(?:(?:,\s*|\s+(?:and|or)\s+|\s*/\s*)-{NUMBER}\b|(?:\.\.|{DASH}){NUMBER}\b)+"
)


def _abbreviated(skill: Skill) -> Iterator[Finding]:
    """Every cited ID is written whole, for a renumbering to follow.

    A line is counted in its block as printed, which is the file's own
    line in every file `layout` passes.
    """
    for path, doc in skill.docs.items():
        for block in citing(doc):
            text = text_of((block,))
            for m in _ABBREVIATED.finditer(text):
                yield fail(
                    f"`{m.group(0)}` abbreviates rule IDs, which a renumbering "
                    "cannot follow; write each in full",
                    skill.at(path, block.line + text.count("\n", 0, m.start())),
                    ABBREVIATED,
                )


def _dangling(skill: Skill) -> Iterator[Finding]:
    """An id cited anywhere in the skill names a rule it defines."""
    named = {
        rid
        for doc in skill.docs.values()
        for block in citing(doc)
        for rid in cited(text_of((block,)), skill.prefix)
    }
    for rid in sorted(named - skill.ids):
        yield fail(f"dangling reference {rid}", skill.at(), DANGLING)


def _paths(skill: Skill, home: dict[RuleId, str]) -> Iterator[Finding]:
    """A named file exists, and a chapter cited for an id holds it.

    A citation may break across lines, as filling breaks any paragraph,
    but never across a blank line, which ends the paragraph. Its line is
    counted as `_abbreviated` counts one.
    """
    near = re.compile(
        rf"`references/([a-z0-9-]+\.md)`(?:[^`\n]|\n(?![ \t]*\n)){{0,40}}?"
        rf"({rule_id(skill.prefix)})"
    )
    for path, doc in skill.docs.items():
        texts = [(block.line, text_of((block,))) for block in doc.blocks]
        for _, text in texts:
            for ref in re.findall(r"`((?:references|assets)/[A-Za-z0-9._-]+)`", text):
                if not skill.asset(ref).exists():
                    yield fail(f"missing file {ref}", skill.at(path), MISSING_FILE)
        for line, text in texts:
            for m in near.finditer(text):
                actual = home.get(RuleId.parse(m.group(2)))
                if actual is not None and actual != m.group(1):
                    yield fail(
                        f"says {m.group(1)} for {m.group(2)}, which lives in {actual}",
                        skill.at(path, line + text.count("\n", 0, m.start())),
                        WRONG_CHAPTER,
                    )


def _core_citations(skill: Skill, home: dict[RuleId, str]) -> Iterator[Finding]:
    """A core rule cites the chapter rule that states it in full.

    A core rule is a summary; the reader who wants the full statement
    needs to be told where it lives.
    """
    pre = skill.prefix
    cite = _citation(pre)
    for core in skill.core:
        cites = cite.findall(" ".join(text_of(core.body).split()))
        if not cites:
            yield fail(f"{core.id} cites no chapter rule", skill.at(), CORE_UNCITED)
            continue
        for fname, ids in cites:
            for target in cited(ids, pre):
                if target not in home:
                    yield fail(
                        f"{core.id} cites {target}, which is not a rule",
                        skill.at(),
                        CORE_NOT_A_RULE,
                    )
                elif home[target] != fname:
                    yield fail(
                        f"{core.id} cites {fname} for {target}, "
                        f"which is in {home[target]}",
                        skill.at(),
                        CORE_WRONG_CHAPTER,
                    )


def _counts(skill: Skill) -> Iterator[Finding]:
    """The reference map's counts, per family and in total, are true.

    A count is written after its family, `` `RS-ERR` (12) ``.
    """
    pre = skill.prefix
    total = len(skill.chapter_rules)
    section = next((s for s in skill.typed.sections if s.title == shared.MAP), None)
    text = "\n".join(_prose(section.lead)) if section is not None else ""
    found = re.findall(rf"`{re.escape(pre)}-({FAMILY})` \((\d+)\)", text)
    per = [int(n) for _, n in found]
    if sum(per) != total:
        yield fail(
            f"reference-map counts sum to {sum(per)}, actual {total}",
            skill.at(),
            MAP_TOTAL,
        )

    stated = dict(found)
    actual = Counter(r.id.family for r in skill.chapter_rules)
    for family in sorted(set(stated) | set(actual)):
        want = int(stated[family]) if family in stated else None
        got = actual.get(family)
        if want != got:
            yield fail(
                f"{pre}-{family} stated {want}, actual {got}", skill.at(), MAP_FAMILY
            )

    here = re.search(r"the other (\d+) live here", text)
    if here and int(here.group(1)) != total:
        yield fail(
            f"'other {here.group(1)} live here' != {total}", skill.at(), MAP_HERE
        )


def _near_duplicates(
    skill: Skill, parts: dict[tuple[RuleId, str], str]
) -> Iterator[Finding]:
    """No two rules share a Why or a Check, and no junk is shipped."""
    shingled = {k: shingles(v) for k, v in parts.items() if len(v) > SHORT_SECTION}
    for (k1, a), (k2, b) in itertools.combinations(shingled.items(), 2):
        if k1[1] == k2[1] and overlap(a, b) > NEAR_DUPLICATE:
            yield fail(
                f"near-duplicate {k1[1]} in {k1[0]} / {k2[0]}",
                skill.at(),
                NEAR_DUPLICATE_TEXT,
            )

    for junk in (".git", ".DS_Store", "*.pyc", "__pycache__"):
        if list(skill.root.rglob(junk)):
            yield note(f"{junk} present in the skill tree", skill.at(), JUNK)


#: A Why is a reason, not an essay. Longer than this, and the excess
#: belongs in the rule's statement, in an example, or in a second rule.
WHY_LINES = 3


#: An inline code span, which is content rather than prose: `"1.2"` as
#: a caret requirement, `from_secs_f32(0.5)` as a literal. Filling keeps
#: a span on one line.
_SPAN = re.compile(r"(`+)[^`\n]*?\1")


def _prose(blocks: Iterable[Block]) -> Iterator[str]:
    """The running text of `blocks`, every example left out.

    A fenced example is content rather than prose, wherever it sits: a
    manifest's `rust-version`, a reproduction on an older release.
    """
    for block in blocks:
        match block:
            case Paragraph() | Heading():
                yield block.text
            case Table(header, _, rows):
                yield from (cell for row in (header, *rows) for cell in row)
            case ListBlock(items):
                yield from (s for item in items for s in _prose(item.blocks))
            case Quote(inner):
                yield from _prose(inner)
            case Fence() | Divider():
                pass


def _below_target(skill: Skill) -> Iterator[Finding]:
    """A rule whose prose names an older release.

    The subject's own versions only, read from the pin: `3.13` in a
    Python 3.15 standard, `0.19` in a Bevy 0.20 one. Code, fenced or
    inline, is content rather than prose. The migration chapter is where
    a standard's history lives, so it is not read.
    """
    pin = skill.profile.pin
    if pin is None:
        return
    target = pin.version.series
    major = target.release[0]
    rules = [
        (rule, chapter.where(rule.line))
        for chapter in skill.chapters
        if chapter.path.stem != "migration"
        for rule in chapter.typed.rules
    ]
    rules += [(core, skill.at(SKILL_MD)) for core in skill.core]
    for rule, where in rules:
        prose = "\n".join([rule.title, *_prose(rule.body)])
        older = sorted(
            {v for v in releases(_SPAN.sub(" ", prose), major) if v < target}
        )
        if older:
            yield fail(
                f"{rule.id} names {', '.join(map(str, older))}, below its target "
                f"{target}: a rule speaks of its target, and the "
                "migration chapter keeps the history",
                where,
                BELOW_TARGET,
            )


def structural(skill: Skill) -> Iterator[Finding]:
    """The rule-shape half of standard-structure.

    Dense numbering, a short Why, and no release older than the target
    in a rule's prose. Appending a rule in the middle passes every other
    check — the contents list agrees, because it was edited too — and
    leaves a reader scanning 01..08, 25, 09; so these are judged once,
    here.
    """
    yield from _below_target(skill)
    for chapter in skill.chapters:
        numbers: dict[str, list[Rule]] = defaultdict(list)
        for rule in chapter.typed.rules:
            numbers[rule.id.family].append(rule)
            lines = [ln for b in rule.why for ln in printed(b) if ln.strip()]
            if len(lines) > WHY_LINES:
                yield fail(
                    f"{rule.id}'s Why runs {len(lines)} lines; "
                    f"the limit is {WHY_LINES}",
                    chapter.where(rule.line),
                    WHY_LENGTH,
                )
        for rules in numbers.values():
            for i, rule in enumerate(rules, 1):
                rid = rule.id
                if (rid.number, rid.suffix) != (i, ""):
                    yield fail(
                        f"{rid} should be {RuleId(rid.standard, rid.family, i)}: "
                        "numbers run 01, 02, … with no gap and no suffix",
                        chapter.where(rule.line),
                        NUMBERING,
                    )
                    break


# ------------------------------------------------------------------
# the normal form: what a normalised standard is held to


def _normal_form(skill: Skill) -> Iterator[Finding]:
    """Each rule in one shape, and every citation a bare ID.

    Only a standard whose profile is `normalized`, until all four are
    (normalize-the-standards, decision 14): each property is a
    consequence of a decision the others have not been brought into.
    """
    for chapter in skill.chapters:
        for rule in chapter.typed.rules:
            where = chapter.where(rule.line)
            yield from _shaped(rule, where)
            yield from _checked(rule, where)
            yield from _one_predicate(rule, where)
    yield from _cited_bare(skill)


def plain(text: str) -> list[str]:
    """The words of `text`, lowercase, code ticks and emphasis left out.

    What a title and a statement are compared as: a statement that
    quotes its title's code, or sets a word of it in bold, still says it
    again.
    """
    return [m.group() for m in re.finditer(r"[a-z0-9]+", text.lower())]


def restates(rule: Rule) -> bool:
    """Does the rule's statement open by saying its title again?

    The title is the statement's first words, however the sentence goes
    on: "Never use features for mutually exclusive choices." after the
    title of that name, or the same words followed by a colon and a
    list. A statement says what the title cannot fit, or is left out.
    """
    first = rule.parts[0] if rule.parts else None
    if first is None or first.element is not Element.STATEMENT:
        return False
    match first.blocks:
        case (Paragraph() as opening, *_):
            title = plain(rule.title)
            return bool(title) and plain(opening.text)[: len(title)] == title
        case _:
            return False


def disorder(rule: Rule) -> tuple[Element, Element] | None:
    """The first element the rule states after one that follows it.

    The element out of place, and the one it comes after. A stray block
    has no place to be out of, and the relaxed form's place beside the
    Why is `relaxed_order`'s to judge, so neither is compared.
    """
    furthest: Element | None = None
    for part in rule.parts:
        if part.element in {Element.STRAY, Element.RELAXED}:
            continue
        if furthest is not None and ORDER.index(part.element) < ORDER.index(furthest):
            return part.element, furthest
        if furthest is None or ORDER.index(part.element) > ORDER.index(furthest):
            furthest = part.element
    return None


def _stray(rule: Rule) -> str | None:
    """The rule's first stray block, said for a reader; or None."""
    part = next((p for p in rule.parts if p.element is Element.STRAY), None)
    if part is None:
        return None
    match part.blocks[0]:
        case Heading(text=text):
            return f"the heading `{text}`"
        case Paragraph(text=text) if (label := LABEL.match(text)) is not None:
            return f"the label `{label.group(0)}`, which the shape has no place for"
        case _:
            return "prose after an example"


def _shaped(rule: Rule, where: Location) -> Iterator[Finding]:
    """Statement, relaxed form, Why, Check, examples: in order, once.

    Out of order is `fmt`'s to fix and reported until it has; a stray
    block, a restated title and a second example of one side are a
    person's (decision 2).
    """
    if restates(rule):
        yield fail(
            f"{rule.id}'s statement opens with its title again; a statement says "
            "what the title cannot, or is left out",
            where,
            RESTATED_TITLE,
        )
    if (found := disorder(rule)) is not None:
        late, early = found
        yield fail(
            f"{rule.id} states its {late.value} after its {early.value}; a rule "
            "states statement, relaxed form, Why, Check, then examples — "
            "`agent-skill fmt` puts them in order",
            where,
            ELEMENT_ORDER,
        )
    if (what := _stray(rule)) is not None:
        yield fail(
            f"{rule.id} holds {what}; no element of a rule holds it, so it "
            "belongs in the statement, in another rule, or nowhere",
            where,
            STRAY,
        )
    sides = Counter(Marker(marker_line(f.body)).verdict for f in rule.examples)
    if over := [side for side in ("GOOD", "BAD") if sides[side] > 1]:
        yield fail(
            f"{rule.id} carries {sides[over[0]]} {over[0]} examples; a second "
            "defect is a second rule or a tool row",
            where,
            POLARITY,
        )
    relaxed = any(
        _RELAXED.search(text_of((b,))) for b in rule.body if not isinstance(b, Fence)
    )
    if relaxed and rule.tier is not Tier.M_BANG:
        yield fail(
            f"{rule.id} is {rule.tier} and states a relaxed form; only an [M!] "
            "rule relaxes, outside section 1's scope",
            where,
            RELAXED_TIER,
        )


#: A Check that names a search in prose: `grep for X`, `search for X`.
#: Read with every code span taken out, so an `rg` command is not one.
_SEARCH = re.compile(
    r"\b(?:grep\w*|rg|ripgrep)\b|\bsearch(?:es|ing)?\s+(?:for|over|through)\b",
    re.IGNORECASE,
)


def _checked(rule: Rule, where: Location) -> Iterator[Finding]:
    """A Check that names a pattern runs it (decision 4).

    A Check is judgement in prose, or `rg` commands and the finding
    each reports. "grep for `X`" is neither: it reads like a command,
    and no one runs it, `self-application` included.
    """
    said = _SPAN.sub(" ", text_of(rule.check))
    if (m := _SEARCH.search(said)) is not None:
        yield fail(
            f"{rule.id}'s Check says `{m.group(0)}` and runs nothing; give the "
            "`rg` command and the finding it reports, or state the judgement",
            where,
            PROSE_GREP,
        )


#: Titles that advise rather than command: a mandatory rule's title in
#: the mood of a suggestion (decision 6).
ADVICE = (
    "Prefer",
    "Consider",
    "Know",
    "Remember",
    "Understand",
    "Treat",
    "Expect",
    "Assume",
    "Budget",
)


def _one_predicate(rule: Rule, where: Location) -> Iterator[Finding]:
    """`[M!]` is section 1's scope, and a mandatory title commands.

    A rule that says where `[M!]` applies redefines the tier for itself;
    a condition on its subject belongs in its statement (decision 6).
    """
    prose = text_of(b for b in rule.body if not isinstance(b, Fence))
    if str(Tier.M_BANG) in prose:
        yield fail(
            f"{rule.id} restates the {Tier.M_BANG} scope; section 1 states it once, "
            "and a condition on the subject belongs in the statement",
            where,
            LOCAL_SCOPE,
        )
    first = rule.title.split(maxsplit=1)[0] if rule.title else ""
    if rule.tier is not Tier.S and first in ADVICE:
        yield fail(
            f"{rule.id} is {rule.tier} and its title opens `{first}`; a mandatory "
            "rule commands or prohibits, and only an [S] rule advises",
            where,
            ADVICE_TITLE,
        )


def _cited_bare(skill: Skill) -> Iterator[Finding]:
    """Every rule is cited by its bare ID (decision 3).

    Never quoted, never behind its chapter's path: section 6 maps each
    family to its file. An example's words are code, and a rename
    table's are history; neither is read.
    """
    for path, doc in skill.docs.items():
        for block in citing(doc):
            text = text_of((block,))
            for _, run in runs(block):
                for word in run:
                    for rid in quoted(word):
                        yield fail(
                            f"`{rid}` is quoted; a rule is cited by its bare ID — "
                            "`agent-skill fmt` unquotes it",
                            skill.at(path, _line(block, text, f"`{rid}`")),
                            QUOTED_CITATION,
                        )
                for _, chapter, rid in qualified(run):
                    yield fail(
                        f"`{chapter}` {rid} names the chapter; a rule is cited by its "
                        "bare ID, and section 6 maps it to its file — "
                        "`agent-skill fmt` drops the path",
                        skill.at(path, _line(block, text, f"`{chapter}`")),
                        PATH_CITATION,
                    )


def _line(block: Block, text: str, said: str) -> int:
    """The line of `block` on which `said` first appears in `text`.

    `text` is the block as printed, which is the file's own in every
    file `layout` passes.
    """
    return block.line + text.count("\n", 0, max(text.find(said), 0))
