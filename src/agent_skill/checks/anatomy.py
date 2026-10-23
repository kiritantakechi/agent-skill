"""Rule anatomy: what a rule is made of, and that the map still fits."""

import itertools
import re
from collections import Counter, defaultdict
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.model import DASH, without_renames
from agent_skill.report import fail, note
lazy from agent_skill.model import Chapter, Rule, Skill
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


def shingles(s: str, n: int = 4) -> set[tuple[str, ...]]:
    """Every run of `n` consecutive words in `s`, minus stop words."""
    words = [w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP]
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def overlap[T](a: set[T], b: set[T]) -> float:
    """The Jaccard index of `a` and `b`; 0.0 when either is empty."""
    return len(a & b) / len(a | b) if a and b else 0.0


@check("anatomy", "rule anatomy, ToC agreement, cross-references")
def anatomy(skill: Skill) -> Iterator[Finding]:
    """Each rule's shape, and every map and citation of the rules."""
    seen: dict[str, str] = {}
    titles: dict[str, list[str]] = defaultdict(list)
    blocks: dict[tuple[str, str], str] = {}

    for chapter in skill.chapters:
        if re.search(
            rf"^\*\*{skill.prefix}-[A-Z]+-\d+\*\*", chapter.text, re.MULTILINE
        ):
            yield fail("bold-inline rule definitions", f"{skill.name}/{chapter.name}")
        for rule in chapter.rules:
            where = f"{skill.name}/{chapter.name}"
            if rule.id in seen:
                yield fail(f"duplicate {rule.id}, also in {seen[rule.id]}", where)
            seen[rule.id] = chapter.name
            titles[rule.title].append(rule.id)
            yield from _rule(chapter, rule, where)
            for label, section in (("Why", rule.why), ("Check", rule.check)):
                if section:
                    blocks[(rule.id, label)] = " ".join(section.split())

    yield from _structure(skill)
    yield from _contents_order(skill)
    yield from _unique_titles(skill, titles)
    yield from _mis_cited(skill)
    yield from _references(skill, seen)
    yield from _abbreviated(skill)
    yield from _counts(skill)
    yield from _near_duplicates(skill, blocks)


#: How a rule states what an `[M!]` relaxes to: one label, in the
#: statement, so a reader meets the relaxed reading before the reason.
RELAXED = "*Relaxed form:*"
_RELAXED = re.compile(r"\*{1,2}Relaxed form:?\*{1,2}:?")


def _rule(chapter: Chapter, rule: Rule, where: str) -> Iterator[Finding]:
    """One rule against its contents line, its tier and its parts."""
    toc = chapter.toc.get(rule.id)
    if toc is None:
        yield fail(f"{rule.id} missing from the chapter contents", where)
    elif toc[0] != rule.tier:
        yield fail(f"{rule.id} contents tier != heading tier", where)
    elif toc[1] != rule.title:
        yield fail(f"{rule.id} contents title != heading title", where)

    relaxed = _RELAXED.search(rule.body)
    if relaxed is None:
        if rule.tier == "M!":
            yield fail(f"{rule.id} is [M!] with no relaxed form", where)
    elif relaxed.group(0) != RELAXED:
        yield fail(
            f"{rule.id} labels its relaxed form `{relaxed.group(0)}`; "
            f"the label is `{RELAXED}`",
            where,
        )
    elif relaxed.start() > rule.body.find("**Why") >= 0:
        yield fail(
            f"{rule.id}'s relaxed form follows its Why; it is part of the "
            "statement, so it comes first",
            where,
        )

    yield from _shape(rule, where)

    if rule.why and rule.check:
        a, c = shingles(rule.statement), shingles(rule.why)
        if overlap(a, c) > RESTATES:
            yield fail(f"{rule.id} Why merely restates the rule", where)


def _structure(skill: Skill) -> Iterator[Finding]:
    """Everything `structural` judges, as findings.

    Dense numbering, a Why that fits, and no older release in a rule's
    prose. Appending a rule in the middle passes every other check — the
    contents list agrees, because it was edited too — and leaves a
    reader scanning 01..08, 25, 09; so these are judged once, there.
    """
    for message, where in structural(skill):
        yield fail(message, where)


def _contents_order(skill: Skill) -> Iterator[Finding]:
    """The contents list keeps the chapter's order, or it is no map."""
    for chapter in skill.chapters:
        if list(chapter.toc) and list(chapter.toc) != [r.id for r in chapter.rules]:
            yield fail(
                "contents order != heading order", f"{skill.name}/{chapter.name}"
            )


def _unique_titles(skill: Skill, titles: dict[str, list[str]]) -> Iterator[Finding]:
    """A title is an anchor, so it has to be unique.

    `titles[title] = rid` silently kept whichever chapter sorted last.
    """
    for title, ids in sorted(titles.items()):
        if len(ids) > 1:
            yield fail(
                f"{len(ids)} rules share the title {title!r} ({', '.join(ids)}); "
                f"a title is an anchor and must be unique",
                skill.name,
            )


def _shape(rule: Rule, where: str) -> Iterator[Finding]:
    """A rule states its own Why and Check.

    A rule that only names the rule owning its topic is a second place
    to read and keep in step: a zig-style rule pointed at the migration
    chapter, then kept a two-row copy of that chapter's table whose rows
    were already in it. Such a rule merges into its owner.
    """
    has = ("**Why" in rule.body, "**Check" in rule.body)
    if not all(has):
        which = "Why" if not has[0] else "Check"
        yield fail(f"{rule.id} states no {which}", where)


#: Words that carry no signal when matching a summary to the rule it
#: cites.
_ID = re.compile(r"`references/[^`]+`|\b[A-Z]{2}-[A-Z]+-\d+[a-z]?\b")


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
    by_file: dict[str, list[Rule]] = {}
    for rule in skill.rules:
        by_file.setdefault(rule.file, []).append(rule)
    pre = skill.prefix
    cite = re.compile(
        rf"`references/([a-z0-9-]+\.md)` ((?:{pre}-[A-Z]+-\d+[a-z]?)"
        rf"(?:,? (?:and )?{pre}-[A-Z]+-\d+[a-z]?)*)"
    )
    for rid, _tier, body in skill.core_rules:
        flat = " ".join(body.split())
        cites = cite.findall(flat)
        named = {
            t for _, ids in cites for t in re.findall(rf"{pre}-[A-Z]+-\d+[a-z]?", ids)
        }
        summary = _words(_ID.sub("", flat))
        for fname, ids in cites:
            for target in re.findall(rf"{pre}-[A-Z]+-\d+[a-z]?", ids):
                rule = skill.by_id.get(target)
                if rule is None:
                    continue
                mine = overlap(summary, _words(f"{rule.title} {rule.statement}"))
                for other in by_file.get(fname, []):
                    if other.id in named:
                        continue
                    theirs = overlap(
                        summary, _words(f"{other.title} {other.statement}")
                    )
                    if theirs > mine * 2 and theirs - mine > CLOSER_BY:
                        yield note(
                            f"{rid} cites {target} ({rule.title!r}) but {other.id} "
                            f"({other.title!r}) is a closer match",
                            skill.name,
                        )


def _references(skill: Skill, seen: dict[str, str]) -> Iterator[Finding]:
    """Every cited id resolves, in the chapter the citation names."""
    yield from _dangling(skill, seen)
    home = dict(seen.items())
    yield from _paths(skill, home)
    yield from _core_citations(skill, home)


#: A rule ID followed by a bare number that leans on it: `ZS-ASSERT-03,
#: -07 and -20`, or the range `ZS-MEM-19..23`. `renumber` rewrites whole
#: IDs only, so the bare ones kept their old numbers and named other
#: rules.
_ABBREVIATED = re.compile(
    r"\b[A-Z]{2}-[A-Z]+-\d+[a-z]?"
    rf"(?:(?:,\s*|\s+(?:and|or)\s+|\s*/\s*)-\d+[a-z]?\b|(?:\.\.|{DASH})\d+[a-z]?\b)+"
)


def _abbreviated(skill: Skill) -> Iterator[Finding]:
    """Every cited ID is written whole, for a renumbering to follow."""
    for path in skill.markdown:
        text = without_renames(path.read_text())
        for m in _ABBREVIATED.finditer(text):
            line = text[: m.start()].count("\n") + 1
            yield fail(
                f"`{m.group(0)}` abbreviates rule IDs, which a renumbering cannot "
                "follow; write each in full",
                f"{skill.name}/{path.name}:{line}",
            )


def _dangling(skill: Skill, seen: dict[str, str]) -> Iterator[Finding]:
    """An id cited anywhere in the skill names a rule it defines."""
    pre = skill.prefix
    defined = set(seen) | {rid for rid, _, _ in skill.core_rules}
    cited: set[str] = set()
    for path in skill.markdown:
        text = without_renames(path.read_text())
        cited |= set(re.findall(rf"\b({pre}-[A-Z]+-\d+[a-z]?)\b", text))
    for rid in sorted(cited - defined):
        yield fail(f"dangling reference {rid}", skill.name)


def _paths(skill: Skill, home: dict[str, str]) -> Iterator[Finding]:
    """A named file exists, and a chapter cited for an id holds it."""
    pre = skill.prefix
    for path in skill.markdown:
        text = path.read_text()
        for ref in re.findall(r"`((?:references|assets)/[A-Za-z0-9._-]+)`", text):
            if not (skill.root / ref).exists():
                yield fail(f"missing file {ref}", f"{skill.name}/{path.name}")
        for i, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(
                rf"`references/([a-z0-9-]+\.md)`[^`\n]{{0,40}}?({pre}-[A-Z]+-\d+[a-z]?)",
                line,
            ):
                actual = home.get(m.group(2))
                if actual is not None and actual != m.group(1):
                    yield fail(
                        f"says {m.group(1)} for {m.group(2)}, which lives in {actual}",
                        f"{skill.name}/{path.name}:{i}",
                    )


def _core_citations(skill: Skill, home: dict[str, str]) -> Iterator[Finding]:
    """A core rule cites the chapter rule that states it in full.

    A core rule is a summary; the reader who wants the full statement
    needs to be told where it lives.
    """
    pre = skill.prefix
    for rid, _tier, body in skill.core_rules:
        flat = " ".join(body.split())
        cites = re.findall(
            rf"`references/([a-z0-9-]+\.md)` ((?:{pre}-[A-Z]+-\d+[a-z]?)"
            rf"(?:,? (?:and )?{pre}-[A-Z]+-\d+[a-z]?)*)",
            flat,
        )
        if not cites:
            yield fail(f"{rid} cites no chapter rule", skill.name)
            continue
        for fname, ids in cites:
            for target in re.findall(rf"{pre}-[A-Z]+-\d+[a-z]?", ids):
                if target not in home:
                    yield fail(f"{rid} cites {target}, which is not a rule", skill.name)
                elif home[target] != fname:
                    yield fail(
                        f"{rid} cites {fname} for {target}, which is in {home[target]}",
                        skill.name,
                    )


def _counts(skill: Skill) -> Iterator[Finding]:
    """The reference map's counts, per family and in total, are true."""
    pre = skill.prefix
    total = len(skill.rules)
    per = [int(n) for n in re.findall(rf"`{pre}-[A-Z]+` \((\d+)\)", skill.text)]
    if sum(per) != total:
        yield fail(
            f"reference-map counts sum to {sum(per)}, actual {total}", skill.name
        )

    stated = dict(re.findall(rf"`{pre}-([A-Z]+)` \((\d+)\)", skill.text))
    actual = Counter(r.id.split("-")[1] for r in skill.rules)
    for family in sorted(set(stated) | set(actual)):
        want = int(stated[family]) if family in stated else None
        got = actual.get(family)
        if want != got:
            yield fail(f"{pre}-{family} stated {want}, actual {got}", skill.name)

    here = re.search(r"the other (\d+) live here", skill.text)
    if here and int(here.group(1)) != total:
        yield fail(f"'other {here.group(1)} live here' != {total}", skill.name)


def _near_duplicates(
    skill: Skill, blocks: dict[tuple[str, str], str]
) -> Iterator[Finding]:
    """No two rules share a Why or a Check, and no junk is shipped."""
    shingled = {k: shingles(v) for k, v in blocks.items() if len(v) > SHORT_SECTION}
    for (k1, a), (k2, b) in itertools.combinations(shingled.items(), 2):
        if k1[1] == k2[1] and overlap(a, b) > NEAR_DUPLICATE:
            yield fail(f"near-duplicate {k1[1]} in {k1[0]} / {k2[0]}", skill.name)

    for junk in (".git", ".DS_Store", "*.pyc", "__pycache__"):
        if list(skill.root.rglob(junk)):
            yield note(f"{junk} present in the skill tree", skill.name)


#: A Why is a reason, not an essay. Longer than this, and the excess
#: belongs in the rule's statement, in an example, or in a second rule.
WHY_LINES = 3


#: A fenced example, which a version may sit in as content: a manifest's
#: `rust-version`, a reproduction on an older release.
_FENCED = re.compile(r"^[ \t]*```.*?^[ \t]*```[^\n]*$", re.MULTILINE | re.DOTALL)


def _below_target(skill: Skill) -> Iterator[tuple[str, str]]:
    """(message, where) for a rule whose prose names an older release.

    The subject's own versions only, read from the pin: `3.13` in a
    Python 3.15 standard, `0.19` in a Bevy 0.20 one. A minor of two
    digits or more keeps `3.5x faster` out, and one that does not start
    with `0` keeps a decimal such as `0.05` out. The migration chapter
    is where a standard's history lives, so it is not read.
    """
    pin = re.match(r"(\d+)\.(\d+)", skill.profile.pin())
    if pin is None:
        return
    major, target = pin.group(1), int(pin.group(2))
    token = re.compile(rf"(?<![\d.]){major}\.([1-9]\d+)(?!\d)")
    rules = [
        (rule.id, f"{rule.title}\n{rule.body}", f"{skill.name}/{chapter.name}")
        for chapter in skill.chapters
        if chapter.path.stem != "migration"
        for rule in chapter.rules
    ]
    rules += [
        (rid, body, f"{skill.name}/SKILL.md") for rid, _, body in skill.core_rules
    ]
    for rid, body, where in rules:
        older = sorted(
            {
                m.group(0)
                for m in token.finditer(_FENCED.sub("", body))
                if int(m.group(1)) < target
            },
            key=lambda v: int(v.split(".")[1]),
        )
        if older:
            yield (
                (
                    f"{rid} names {', '.join(older)}, below its target "
                    f"{major}.{target}: a rule speaks of its target, and the "
                    "migration chapter keeps the history"
                ),
                where,
            )


def structural(skill: Skill) -> Iterator[tuple[str, str]]:
    """(message, where) for the rule-shape half of standard-structure.

    Dense numbering, a short Why, and no release older than the target
    in a rule's prose.
    """
    yield from _below_target(skill)
    for chapter in skill.chapters:
        where = f"{skill.name}/{chapter.name}"
        numbers: dict[str, list[str]] = defaultdict(list)
        for rule in chapter.rules:
            family, number = rule.id.split("-")[1:]
            numbers[family].append(number)
            lines = [ln for ln in rule.why.strip().split("\n") if ln.strip()]
            if len(lines) > WHY_LINES:
                yield (
                    (
                        f"{rule.id}'s Why runs {len(lines)} lines; "
                        f"the limit is {WHY_LINES}"
                    ),
                    where,
                )
        for family, seen in numbers.items():
            for i, number in enumerate(seen, 1):
                if number != f"{i:02d}":
                    yield (
                        (
                            f"{skill.prefix}-{family}-{number} should be "
                            f"{skill.prefix}-{family}-{i:02d}: numbers run 01, 02, "
                            "… with no gap and no suffix"
                        ),
                        where,
                    )
                    break
