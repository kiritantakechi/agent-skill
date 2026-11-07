"""The standards held to the abstract standard, and to one another.

A concept two or more standards state is one entry of the abstract
standard, and each base standard answers it in a row: the rule that
realises it, the relation, the tier and why (one-abstract-standard,
decisions 1 to 4). This reads the entries and their rows against the
standards, and the standards against each other where no entry holds
them yet.

It replaces `mirror`, which held title-keyed pairs against rust-style
alone: a pair is derived now, two rules that realise one entry, keyed by
rule ID, which `revise` rewrites in `abstract/` with every other
citation. A pair that looks alike and that no entry holds is noted, for
every pair of base standards and for a delta with its anchor.
"""

import re
from collections import defaultdict
lazy from collections.abc import Iterator, Mapping

from agent_skill import vocabulary
from agent_skill.abstract import Concept, abstract_of
from agent_skill.checks import check
from agent_skill.checks.anatomy import overlap
from agent_skill.checks.skeleton import SCOPE, coded, is_scope
from agent_skill.doc import Table, canonical, walk
from agent_skill.doc.chapter import departures, departures_header
from agent_skill.ids import Breach, Location, Relation, RuleId, breaches, cited_lines
from agent_skill.report import Level, declare, fail, note
lazy from agent_skill.abstract import Abstract, Realisation
lazy from agent_skill.doc.chapter import Rule
lazy from agent_skill.model import Chapter, Skill, Tree
lazy from agent_skill.report import Finding

# The branches of the abstract standard's own form.
UNREAD = declare("concepts", "unread", Level.FAIL)
TEMPLATE = declare("concepts", "template", Level.FAIL)
CANONICAL = declare("concepts", "canonical", Level.FAIL)
NUMBERING = declare("concepts", "numbering", Level.FAIL)
WRONG_FAMILY = declare("concepts", "wrong_family", Level.FAIL)
ENTRY_SHAPE = declare("concepts", "entry_shape", Level.FAIL)
INLINE_CODE = declare("concepts", "inline_code", Level.FAIL)

# The branches of the realisation map.
MISSING_ROW = declare("concepts", "missing_row", Level.FAIL)
DELTA_ROW = declare("concepts", "delta_row", Level.FAIL)
UNKNOWN_STANDARD = declare("concepts", "unknown_standard", Level.FAIL)
TWO_RULES_ONE_ENTRY = declare("concepts", "two_rules_one_entry", Level.FAIL)
TWO_ROWS_ONE_RULE = declare("concepts", "two_rows_one_rule", Level.FAIL)
NOT_A_RULE = declare("concepts", "not_a_rule", Level.FAIL)
RELATION = declare("concepts", "relation", Level.FAIL)
NO_REASON = declare("concepts", "no_reason", Level.FAIL)
WRONG_CHAPTER = declare("concepts", "wrong_chapter", Level.FAIL)

# The branches of what a skill may say about the abstract standard.
ABSTRACT_CITED = declare("concepts", "abstract_cited", Level.FAIL)

# The detector.
LOOK_ALIKE = declare("concepts", "look_alike", Level.NOTE)

#: Above this overlap between two titles' three-word runs, the rules
#: look like one concept: the threshold `mirror` noted pairs at.
LOOKS_ALIKE = 0.5


@check(
    "concepts",
    "every shared concept stated once, and each standard's realisation of it",
)
def concepts(tree: Tree) -> Iterator[Finding]:
    """The abstract standard's form, its rows, and what looks alike."""
    abstract = abstract_of(tree)
    yield from _form(abstract)
    yield from _rows(abstract, tree)
    yield from _cited(abstract, tree)
    yield from _look_alike(abstract, tree)


# ------------------------------------------------------------------
# the abstract standard's form


def _form(abstract: Abstract) -> Iterator[Finding]:
    """Each file as `fmt` prints it, each chapter in its template."""
    for chapter in [*abstract.chapters, *filter(None, (abstract.principles,))]:
        if chapter.text != canonical(chapter.text):
            yield fail(
                f"`{chapter.name}` is not as `agent-skill fmt` prints it",
                abstract.at(chapter.path),
                CANONICAL,
            )
    for chapter in abstract.chapters:
        where = abstract.at(chapter.path)
        code = vocabulary.code_for(chapter.path.stem)
        if not code:
            yield fail(
                f"`{chapter.name}` is no chapter the vocabulary names; an abstract "
                "chapter is a vocabulary word's, as a standard's is",
                where,
                UNREAD,
            )
            continue
        if chapter.refused is not None:
            yield fail(
                f"`{chapter.name}` does not read as a chapter: {chapter.refused}",
                where,
                UNREAD,
            )
            continue
        yield from _template(abstract, chapter)
        for k, rule in enumerate(chapter.typed.rules, 1):
            yield from _entry(abstract, chapter, code, k, rule)


def _template(abstract: Abstract, chapter: Chapter) -> Iterator[Finding]:
    """A title naming the concept, its scope, and contents that agree.

    The template every standard's chapter is in: a title with no family
    code, a `Scope:` paragraph, then a contents list that lists each
    entry by its ID, tier and title, in order.
    """
    typed = chapter.typed
    where = abstract.at(chapter.path)
    said: list[str] = []
    if not typed.title or coded(typed.title, abstract.prefix):
        said.append("a title naming the concept, with no family code")
    if not (typed.scope and is_scope(typed.scope[0])):
        said.append(f"a `{SCOPE}` paragraph saying what it owns")
    listed = (
        None
        if typed.contents is None
        else [(e.id, e.tier, e.title) for e in typed.contents.entries]
    )
    if listed != [(r.id, r.tier, r.title) for r in typed.rules]:
        said.append("contents listing each entry's ID, tier and title, in order")
    if said:
        yield fail(
            f"`{chapter.name}` is not in the chapter template: it lacks "
            + "; ".join(said),
            where,
            TEMPLATE,
        )


#: A code span: what names a construct of one language.
_CODE = re.compile(r"`[^`]+`")


def _entry(
    abstract: Abstract, chapter: Chapter, code: str, k: int, rule: Rule
) -> Iterator[Finding]:
    """One entry's ID, its shape, and a statement in no one language."""
    where = abstract.at(chapter.path, rule.line, rule.id)
    if rule.id.standard != abstract.prefix or rule.id.family != code:
        yield fail(
            f"{rule.id} stands in `{chapter.name}`, whose entries are "
            f"`{abstract.prefix}-{code}`",
            where,
            WRONG_FAMILY,
        )
    if rule.id.number != k or rule.id.suffix:
        yield fail(
            f"{rule.id} is entry {k} of `{chapter.name}`; an abstract chapter's IDs "
            "are dense, in order",
            where,
            NUMBERING,
        )
    concept = Concept(rule)
    if not concept.shaped:
        yield fail(
            f"{rule.id} is not a statement and then one realisation table; an entry "
            "has no Why, Check or example, which are each realisation's own",
            where,
            ENTRY_SHAPE,
        )
    stated = [rule.title, *(p.text for p in concept.statement)]
    if spans := [m.group() for text in stated for m in _CODE.finditer(text)]:
        yield fail(
            f"{rule.id} states {spans[0]}, a construct of one language; the "
            "construct is a realising rule's, and the concept all of theirs",
            where,
            INLINE_CODE,
        )


# ------------------------------------------------------------------
# the realisation map


def _rows(abstract: Abstract, tree: Tree) -> Iterator[Finding]:
    """Every entry has one row per base standard, and each row holds.

    A delta realises a concept through its anchor, so it has none. A
    rule realises one concept, so no two entries name it.
    """
    base = {s.name: s for s in tree if not s.profile.anchor}
    deltas = {s.name for s in tree if s.profile.anchor}
    holders: dict[tuple[str, str], list[RuleId]] = defaultdict(list)
    for chapter, concept in abstract.concepts:
        found: dict[str, list[Realisation]] = defaultdict(list)
        for row in concept.rows:
            where = abstract.at(chapter.path, row.line, concept.id)
            if row.standard in deltas:
                yield fail(
                    f"{concept.id} has a row for {row.standard}, a delta, which "
                    "realises a concept through its anchor's row",
                    where,
                    DELTA_ROW,
                )
            elif (skill := base.get(row.standard)) is None:
                yield fail(
                    f"{concept.id} has a row for {row.standard!r}, which is no "
                    "standard here",
                    where,
                    UNKNOWN_STANDARD,
                )
            else:
                found[row.standard].append(row)
                yield from _row(abstract, chapter, concept, row, skill)
                if (named := _named(row, skill, chapter)) is not None:
                    holders[row.standard, named].append(concept.id)
        yield from _answered(abstract, chapter, concept, base, found)
    for (standard, named), entries in holders.items():
        if len(set(entries)) > 1:
            listed = ", ".join(str(e) for e in dict.fromkeys(entries))
            yield fail(
                f"{standard}'s {named} is the row of {listed}; a rule realises one "
                "concept, so the entries are one, or the rule states two",
                abstract.at(rule=entries[1]),
                TWO_ROWS_ONE_RULE,
            )


def _answered(
    abstract: Abstract,
    chapter: Chapter,
    concept: Concept,
    base: Mapping[str, Skill],
    found: Mapping[str, list[Realisation]],
) -> Iterator[Finding]:
    """Each base standard has exactly one row of the entry."""
    where = abstract.at(chapter.path, concept.rule.line, concept.id)
    for name in base:
        rows = found.get(name, [])
        if not rows:
            yield fail(
                f"{concept.id} has no row for {name}; every base standard realises "
                "a concept, departs from it, or says why its domain has none",
                where,
                MISSING_ROW,
            )
        elif len(rows) > 1:
            yield fail(
                f"{concept.id} has {len(rows)} rows for {name}; two rules stating one "
                "concept are merged with `revise` before either is its row",
                where,
                TWO_RULES_ONE_ENTRY,
            )


def _home(skill: Skill) -> dict[RuleId, tuple[Rule, Chapter]]:
    """Each chapter rule of `skill`, and the chapter that holds it."""
    return {r.id: (r, c) for c in skill.chapters for r in c.typed.rules}


def _named(row: Realisation, skill: Skill, chapter: Chapter) -> str | None:
    """What a row names that no other entry may: a rule, or a lint."""
    relation = row.related
    if relation is None or relation is Relation.ABSENT:
        return None
    if relation.ruled:
        rid = row.rid
        return str(rid) if rid is not None and rid in skill.ids else None
    lint = row.lint
    return f"`{lint}`" if lint in _lints(skill, chapter.path.stem) else None


def _lints(skill: Skill, stem: str) -> set[str]:
    """The lints `skill`'s chapter `stem` lists as decided by tools."""
    return {
        row.lint for c in skill.chapters if c.path.stem == stem for row in c.typed.tools
    }


def _row(
    abstract: Abstract,
    chapter: Chapter,
    concept: Concept,
    row: Realisation,
    skill: Skill,
) -> Iterator[Finding]:
    """One row: what it names, where that stands, and its relation."""
    where = abstract.at(chapter.path, row.line, concept.id)
    relation = row.related
    if relation is None:
        yield fail(
            f"{concept.id}'s row for {row.standard} says `{row.relation}`; a row "
            f"{', '.join(str(r) for r in list(Relation)[:-1])} or "
            f"{list(Relation)[-1]}",
            where,
            RELATION,
        )
        return
    stem = chapter.path.stem
    tier = None
    if relation.ruled:
        found = _home(skill).get(row.rid) if row.rid is not None else None
        if found is None:
            yield fail(
                f"{concept.id}'s row for {row.standard} names {row.rule or 'nothing'}, "
                f"which is no rule of {skill.name}",
                where,
                NOT_A_RULE,
            )
        else:
            rule, home = found
            tier = rule.tier
            if home.path.stem != stem:
                yield fail(
                    f"{rule.id} realises {concept.id} from `{home.name}`; a concept "
                    f"lives in one chapter in every standard, `{stem}.md`, and "
                    "`revise` moves it there",
                    home.where(rule.line, rule.id),
                    WRONG_CHAPTER,
                )
    elif relation is Relation.DECIDED and row.lint not in _lints(skill, stem):
        yield fail(
            f"{concept.id}'s row for {row.standard} is decided by "
            f"{row.rule or 'nothing'}, which no `Decided by tools` row of its "
            f"`{stem}.md` lists",
            where,
            NOT_A_RULE,
        )
    elif relation is Relation.ABSENT and row.rule.strip():
        yield fail(
            f"{concept.id}'s row for {row.standard} is absent and names {row.rule}; "
            "a domain with no instance has no rule",
            where,
            NOT_A_RULE,
        )
    for breach in breaches(relation, concept.tier, tier, row.reason):
        if breach is Breach.TIER:
            yield fail(
                f"{concept.id} is {concept.tier}, and {row.standard} {relation} it by "
                f"{row.rule} at {tier}; a rule that {relation} a concept takes "
                f"{relation.asks}, or departs from it with its reason",
                where,
                RELATION,
            )
        else:
            yield fail(
                f"{concept.id}'s row for {row.standard} says {relation} and gives no "
                "reason; every relation but `realises` says why",
                where,
                NO_REASON,
            )


# ------------------------------------------------------------------
# what a skill says


#: The suffixes of a skill's files a citation can be in, and none.
_TEXT = {".md", ".toml", ".yml", ".yaml", ".zig", ".zon", ".py", ".rs", ".json", ""}


def _cited(abstract: Abstract, tree: Tree) -> Iterator[Finding]:
    """No file of a skill cites the abstract standard.

    A skill reads completely when it is installed alone, and the reader
    of an installed skill has no abstract standard to look in.
    """
    for skill in tree:
        for path in sorted(skill.root.rglob("*")):
            if not path.is_file() or path.suffix not in _TEXT:
                continue
            for rid, line in cited_lines(path.read_text(), abstract.prefix):
                yield fail(
                    f"cites {rid}, of the abstract standard, which an installed skill "
                    "does not have; a skill cites only rules it ships or loads",
                    skill.at(path, line),
                    ABSTRACT_CITED,
                )


# ------------------------------------------------------------------
# the detector


def _shingles(title: str, n: int = 3) -> frozenset[tuple[str, ...]]:
    """The runs of `n` words a title holds, lowercased, letters only."""
    words = re.findall(r"[a-z]+", title.lower())
    return frozenset(tuple(words[i : i + n]) for i in range(len(words) - n + 1))


def _held(abstract: Abstract, tree: Tree) -> set[frozenset[RuleId]]:
    """Every pair of rules an entry, or a delta's departure, relates.

    Two rules of one entry's rows realise one concept; a delta rule and
    the anchor rule its departures table names are one departure.
    """
    pairs: set[frozenset[RuleId]] = set()
    for _, concept in abstract.concepts:
        named = [r.rid for r in concept.rows if r.rid is not None]
        pairs |= {frozenset((a, b)) for a in named for b in named if a != b}
    for skill in tree:
        if not skill.profile.anchor:
            continue
        header = departures_header(skill.profile.anchor, skill.name)
        tables = (
            b
            for b in walk(skill.doc.blocks)
            if isinstance(b, Table) and b.header == header
        )
        for row in (d for t in tables for d in departures(t)):
            ours, theirs = RuleId.try_parse(row.ours), RuleId.try_parse(row.theirs)
            if ours is not None and theirs is not None:
                pairs.add(frozenset((ours, theirs)))
    return pairs


def compared(tree: Tree) -> Iterator[tuple[Skill, Skill]]:
    """Each pair of standards the detector compares.

    Every pair of base standards, not only rust-style with each other:
    a concept python-style and zig-style share is as much a pair. And
    each delta with its anchor, which it does not restate.
    """
    skills = list(tree)
    base = [s for s in skills if not s.profile.anchor]
    for i, a in enumerate(base):
        for b in base[i + 1 :]:
            yield a, b
    by_name = {s.name: s for s in skills}
    for skill in skills:
        if (anchor := by_name.get(skill.profile.anchor)) is not None:
            yield skill, anchor


def look_alikes(
    abstract: Abstract, tree: Tree
) -> Iterator[tuple[Skill, Rule, Skill, Rule]]:
    """Each pair of rules whose titles look alike, and no entry holds.

    Two titles look alike when their three-word runs overlap above
    `LOOKS_ALIKE`, which needs a run in common: each rule is compared
    only with the rules it shares one with.
    """
    held = _held(abstract, tree)
    for a, b in compared(tree):
        index: dict[tuple[str, ...], list[Rule]] = defaultdict(list)
        runs = {r.id: _shingles(r.title) for r in b.chapter_rules}
        for rule in b.chapter_rules:
            for run in runs[rule.id]:
                index[run].append(rule)
        for rule in a.chapter_rules:
            mine = _shingles(rule.title)
            near = dict.fromkeys(other for run in mine for other in index[run])
            for other in near:
                if overlap(set(mine), set(runs[other.id])) <= LOOKS_ALIKE:
                    continue
                if frozenset((rule.id, other.id)) not in held:
                    yield a, rule, b, other


def _look_alike(abstract: Abstract, tree: Tree) -> Iterator[Finding]:
    """A note for each pair of rules that look alike, held by none."""
    for a, rule, b, other in look_alikes(abstract, tree):
        yield note(
            f"{rule.id} and {other.id} look alike ({rule.title!r}), and no entry "
            f"holds them; one concept of {a.name} and {b.name}, or two questions",
            Location(a.name, rule=rule.id),
            LOOK_ALIKE,
        )
