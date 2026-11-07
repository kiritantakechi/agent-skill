"""Citations into another skill, and the table saying where they depart.

`bevy-style` is a delta on `rust-style`: it states what changes when
Bevy is in the dependency list and defers for everything else. That
makes an `RS-…` id inside `bevy-style` a link across documents with
nothing checking it, and it makes the "where this standard departs"
table a claim about two standards that nothing was checking either — the
exact shape of the defect this apparatus exists to catch, one level up.

A citation into a skill that is not in the tree is not checked, because
it cannot be: the claim is about a document nobody here can read.
"""

from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill import shared
from agent_skill.checks import check
from agent_skill.doc import Paragraph, Table, text_of, walk
from agent_skill.doc.chapter import RELATIONS, departures, departures_header
from agent_skill.ids import Location, RuleId, cited
from agent_skill.model import SKILL_MD
from agent_skill.report import Level, declare, fail, unrun
lazy from agent_skill.checks.corpus import Corpus, corpus_for
lazy from agent_skill.checks.patterns import patterns_of
lazy from agent_skill.checks.search import find, searcher_problem
lazy from agent_skill.doc import Block, Doc
lazy from agent_skill.doc.chapter import Departure, Rule
lazy from agent_skill.model import Skill, Tree
lazy from agent_skill.profiles import PROFILES
lazy from agent_skill.report import Finding

# The branches a finding of this check comes from.
APPARATUS_CITATION = declare("crossref", "apparatus", Level.FAIL)
DELTA_NO_TABLE = declare("crossref", "delta_no_table", Level.FAIL)
FOREIGN_CITATION = declare("crossref", "citation", Level.FAIL)
OVERRIDE_TARGET = declare("crossref", "override_target", Level.FAIL)
ANCHOR_ABSENT = declare("crossref", "anchor_absent", Level.UNRUN)
SEARCHER = declare("crossref", "searcher", Level.UNRUN)
ANCHOR_EMPTY_CORPUS = declare("crossref", "anchor_empty_corpus", Level.FAIL)
ANCHOR_NO_ANSWER = declare("crossref", "anchor_no_answer", Level.FAIL)
ANCHOR_HIT = declare("crossref", "anchor_hit", Level.FAIL)

# The branches of the delta map (`_departures`).
RELATION = declare("crossref", "relation", Level.FAIL)
DEPARTURE_TIER = declare("crossref", "departure_tier", Level.FAIL)
DEPARTS = declare("crossref", "departs", Level.FAIL)
REDEFINES = declare("crossref", "redefines", Level.FAIL)


#: Everything outside the skills that names a rule. `assets.py`
#: validates the ids a skill ships, and nothing validated these — so
#: renumbering a chapter left two comments in `lang/rust.py` pointing at
#: the rules that had moved up.
APPARATUS = ("src", "tests", "README.md")

#: Two files hold ids that are *meant* to be invalid: the negative
#: controls inject an out-of-range number precisely to prove a check
#: fires on it. Scanning those would turn each fixture into a failure.
#: (Naming one here would too — this comment is inside a scanned file.)
FIXTURES = ("checks/controls.py", "tests/test_crossref.py")


def _apparatus_citations(
    known: dict[str, frozenset[RuleId]], root: Path | None = None
) -> Iterator[Finding]:
    """A rule id named in the code or the README still has to resolve.

    `root` is injectable so this has a real test: the control harness
    copies the skills and the README and nothing else, so it cannot
    reach the files this reads.
    """
    root = root or Path(__file__).resolve().parents[3]
    files: list[Path] = []
    for name in APPARATUS:
        target = root / name
        files += sorted(target.rglob("*.py")) if target.is_dir() else [target]
    for path in files:
        rel = path.relative_to(root).as_posix()
        if not path.exists() or any(rel.endswith(f) for f in FIXTURES):
            continue
        for rid in cited(path.read_text()):
            if rid.standard in known and rid not in known[rid.standard]:
                yield fail(
                    f"cites {rid}, which is not a rule",
                    Location(file=rel),
                    APPARATUS_CITATION,
                )


@check(
    "crossref",
    "citations into another skill, and the departures table",
    needs=("rg",),
)
def crossref(tree: Tree) -> Iterator[Finding]:
    """Every citation across skills, and each delta's departures."""
    by_prefix = {s.prefix: s for s in tree}
    by_name = {s.name: s for s in tree}
    known = {p: s.ids for p, s in by_prefix.items()}

    for skill in tree:
        yield from _citations(skill, by_prefix, known)
        # A delta's departures are one typed table (decision 10).
        if skill.profile.anchor:
            yield from _departures(skill, by_name.get(skill.profile.anchor))
        yield from _anchor_patterns(skill, by_name)

    # The harness cites the standards it ships; a fixture's IDs in a
    # test (a demo standard's, made up to be wrong) are not citations.
    shipped = {p: ids for p, ids in known.items() if by_prefix[p].name in PROFILES}
    yield from _apparatus_citations(shipped)


def _named(doc: Doc) -> Iterator[RuleId]:
    """Every rule ID `doc` names, of any standard, block by block."""
    for block in doc.blocks:
        yield from cited(text_of((block,)))


def _citations(
    skill: Skill, by_prefix: dict[str, Skill], known: dict[str, frozenset[RuleId]]
) -> Iterator[Finding]:
    """Every id this skill cites in another skill names a rule there."""
    for path, doc in skill.docs.items():
        for rid in _named(doc):
            prefix = rid.standard
            if prefix == skill.prefix or prefix not in known:
                continue
            if rid not in known[prefix]:
                yield fail(
                    f"cites {rid}, which is not a rule in {by_prefix[prefix].name}",
                    skill.at(path),
                    FOREIGN_CITATION,
                )


def _anchor_patterns(skill: Skill, by_name: dict[str, Skill]) -> Iterator[Finding]:
    """The other standard's own patterns, run over this one's examples.

    A delta claims that everything the anchor says still holds except
    the rows of its table. That claim is testable, and it was not being
    tested: two `rust-style` `[M]` rules were firing on nineteen and
    thirty-five lines of `bevy-style`'s examples with nothing saying so.

    Only the anchor's **decisive** patterns are run — the ones it ships
    as a literal `rg` command. Its prose spans are far too broad to
    travel: `assert_eq!` and `.iter()` matched a third of the corpus.

    A hit is allowed when the delta's `SKILL.md` names that rule
    anywhere: in the departures table, or in the prose that says why a
    rule is *not* on it. Either way the reader has been told.

    The anchor is the one the profile declares. It used to be every
    standard the override table cited, so deleting the table emptied
    the set and the sweep returned having run nothing.
    """
    if not skill.profile.anchor:
        return
    other = by_name.get(skill.profile.anchor)
    if other is None:
        yield unrun(
            f"its anchor {skill.profile.anchor} is not among the skills read, so "
            "none of its patterns ran over these examples",
            skill.at(),
            ANCHOR_ABSENT,
        )
        return
    named = set(_named(skill.doc))
    # `tests/test_profiles.py` holds a delta to naming the language its
    # examples are in, which the anchor's patterns run over.
    lang = skill.profile.languages[0]
    if problem := searcher_problem():
        yield unrun(problem, skill.at(), SEARCHER)
        return
    corpus = corpus_for(skill, lang)
    if not corpus.blocks:
        yield fail(
            f"no verified {lang} example to run {other.name}'s patterns over — an "
            "empty corpus passes every one of them",
            skill.at(),
            ANCHOR_EMPTY_CORPUS,
        )
        return
    for rule in other.chapter_rules:
        if not rule.check or rule.id in named:
            continue
        yield from _sweep(skill, corpus, other, rule)


def _sweep(skill: Skill, corpus: Corpus, other: Skill, rule: Rule) -> Iterator[Finding]:
    """The anchor rule's decisive patterns, over the delta's corpus."""
    for pattern in patterns_of(text_of(rule.check)):
        if pattern.kind != "command":
            continue
        lines, used = find(corpus, pattern)
        # `None` is the absence of an answer and `[]` is an
        # answer of nothing. Both are falsy, so `if not lines`
        # reads a search that never ran as a delta with nothing
        # to account for — which is the same silence this whole
        # capability exists to refuse.
        if lines is None:
            yield fail(
                f"{rule.id}: {other.name}'s pattern /{pattern.text}/ gave no "
                f"answer over {skill.name}'s examples — rejected, timed out, or "
                "not installed",
                skill.at(),
                ANCHOR_NO_ANSWER,
            )
            continue
        if not lines:
            continue
        where, snippet = corpus.origin(lines[0].start)
        yield fail(
            f"{rule.id} {used} /{pattern.text}/ hits {len(lines)} line(s) and "
            f"{skill.name}'s SKILL.md never mentions it — {rule.title}\n"
            f"      {where} {snippet}",
            skill.at(),
            ANCHOR_HIT,
        )


# ------------------------------------------------------------------
# the delta map (normalize-the-standards, decision 10)


def _departures(skill: Skill, anchor: Skill | None) -> Iterator[Finding]:
    """The delta's departures are one typed table its rules agree with.

    `| <anchor> rule | Relation | <delta> rule | Tier | Reason |`: each
    row an anchor rule, how the delta rule relates to it — it
    overrides, tightens or extends it — the delta rule, the tier before
    and after (`[M!] → [M]`), and why. A departing rule opens "Departs
    from <ID>." and the table and the rules say one set of pairs; a tier
    the table states is each rule's own; and `[M!]` is the anchor's,
    scope and all.
    """
    name = skill.profile.anchor
    header = departures_header(name, skill.name)
    tables = [b for b in walk(skill.doc.blocks) if isinstance(b, Table)]
    rows = [d for t in tables if t.header == header for d in departures(t)]
    if not rows:
        yield fail(
            f"is a delta on {name} and states no departures table, "
            f"`| {' | '.join(header)} |` — a delta that says where it departs from "
            "nothing has either departed silently or lost its table",
            skill.at(),
            DELTA_NO_TABLE,
        )
    theirs = {r.id: r for r in anchor.chapter_rules} if anchor is not None else {}
    ours = {r.id: r for r in skill.chapter_rules}
    for row in rows:
        yield from _departure(skill, row, theirs, ours)
    yield from _departs(skill, rows)
    if anchor is not None:
        yield from _redefines(skill, anchor)


def _departure(
    skill: Skill,
    row: Departure,
    theirs: dict[RuleId, Rule],
    ours: dict[RuleId, Rule],
) -> Iterator[Finding]:
    """One departure: its relation, its rule here, and its two tiers."""
    where = skill.at(SKILL_MD, row.line)
    if row.relation not in RELATIONS:
        yield fail(
            f"a departure from {row.theirs} is `{row.relation}`; a delta rule "
            f"{', '.join(RELATIONS[:-1])} or {RELATIONS[-1]} its anchor's",
            where,
            RELATION,
        )
    mine = RuleId.try_parse(row.ours)
    if mine is None or mine not in skill.ids:
        yield fail(
            f"departure row names {row.ours}, which is not a rule here",
            where,
            OVERRIDE_TARGET,
        )
    before = theirs.get(other) if (other := RuleId.try_parse(row.theirs)) else None
    after = ours.get(mine) if mine is not None else None
    stated = row.tiers
    if stated is None or (
        before is not None and after is not None and stated != (before.tier, after.tier)
    ):
        actual = f"{before.tier} → {after.tier}" if before and after else "two tiers"
        yield fail(
            f"the departure from {row.theirs} states `{row.tier}`, and the rules "
            f"are {actual}; a tier changes only as its row says",
            where,
            DEPARTURE_TIER,
        )


#: What a departing delta rule's statement opens with, before the ID.
DEPARTS_FROM = ("Departs", "from")


def departs_from(rule: Rule) -> RuleId | None:
    """The anchor rule `rule` opens by departing from, if it does.

    Its statement's first words are `Departs from RS-API-15.`
    """
    first = next(iter(rule.statement), None)
    words = first.words if isinstance(first, Paragraph) else ()
    opening, named = words[: len(DEPARTS_FROM)], words[len(DEPARTS_FROM) : 3]
    if opening != DEPARTS_FROM or not named or not named[0].endswith("."):
        return None
    return RuleId.try_parse(named[0].removesuffix("."))


def _departs(skill: Skill, rows: list[Departure]) -> Iterator[Finding]:
    """The table's pairs and the rules that say they depart agree."""
    listed = {(row.theirs, row.ours): row for row in rows}
    said: dict[tuple[str, str], Location] = {}
    for chapter in skill.chapters:
        for rule in chapter.typed.rules:
            if (other := departs_from(rule)) is not None:
                said[str(other), str(rule.id)] = chapter.where(rule.line, rule.id)
    for (other, mine), row in listed.items():
        if (other, mine) not in said:
            yield fail(
                f"the departures table says {mine} departs from {other}, and {mine} "
                f"does not open `Departs from {other}.`",
                skill.at(SKILL_MD, row.line),
                DEPARTS,
            )
    for (other, mine), where in said.items():
        if (other, mine) not in listed:
            yield fail(
                f"{mine} opens `Departs from {other}.` and no row of the departures "
                "table says so",
                where,
                DEPARTS,
            )


#: The shared passage that says what each tier means, and its scope.
_TIERS = "1. Tiers"


def _scope(skill: Skill) -> tuple[str, tuple[Block, ...]]:
    """How a standard scopes `[M!]`: the code it binds in, its words.

    The words are what section 1 states in its own region, after the
    shared tier table.
    """
    copy = next((c for c in shared.copies(skill) if c.passage.section == _TIERS), None)
    if copy is None:
        return skill.profile.strict_scope, ()
    al = copy.alignment
    return skill.profile.strict_scope, tuple(
        al.actual[a] for _, gap in al.gaps() for a in gap
    )


def _redefines(skill: Skill, anchor: Skill) -> Iterator[Finding]:
    """A delta's `[M!]` is its anchor's: one predicate, not two.

    Its scope (`Profile.strict_scope`) and the words section 1 gives it
    are the anchor's; a delta that binds `[M!]` elsewhere has redefined
    the tier for every rule it defers on.
    """
    if _scope(skill) != _scope(anchor):
        scope = skill.profile.strict_scope
        yield fail(
            f"section 1 scopes `[M!]` to {scope!r} code in words of its own; a delta's "
            f"`[M!]` is {anchor.name}'s, {anchor.profile.strict_scope!r}, as its "
            "section 1 states it",
            skill.at(SKILL_MD),
            REDEFINES,
        )
