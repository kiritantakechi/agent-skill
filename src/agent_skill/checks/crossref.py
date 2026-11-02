"""Citations into another skill, and the table saying they disagree.

`bevy-style` is a delta on `rust-style`: it states what changes when
Bevy is in the dependency list and defers for everything else. That
makes an `RS-…` id inside `bevy-style` a link across documents with
nothing checking it, and it makes the "where this standard departs"
table a claim about two standards that nothing was checking either — the
exact shape of the defect this apparatus exists to catch, one level up.

A citation into a skill that is not in the tree is not checked, because
it cannot be: the claim is about a document nobody here can read.
"""

import re
from pathlib import Path
lazy from collections.abc import Iterator

from agent_skill.checks import check
from agent_skill.ids import Branch, Location
from agent_skill.report import fail, note, unrun
lazy from agent_skill.checks.corpus import Corpus, corpus_for
lazy from agent_skill.checks.patterns import patterns_of
lazy from agent_skill.checks.search import find, searcher_problem
lazy from agent_skill.model import Rule, Skill, Tree
lazy from agent_skill.report import Finding

#: `| `RS-API-15` Keep every struct field private | `BV-ECS-01` — … |`
OVERRIDE_ROW = re.compile(
    r"^\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`\s*(.*?)\s*\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`",
    re.MULTILINE,
)

CITATION = re.compile(r"\b([A-Z]{2})-([A-Z]+-\d+[a-z]?)\b")

# The branches a finding of this check comes from.
APPARATUS_CITATION = Branch("crossref", "apparatus")
NO_TABLE = Branch("crossref", "no_table")
DELTA_DECLARATION = Branch("crossref", "delta_declaration")
DELTA_NO_TABLE = Branch("crossref", "delta_no_table")
FOREIGN_CITATION = Branch("crossref", "citation")
OVERRIDE_TARGET = Branch("crossref", "override_target")
OVERRIDE_TITLE = Branch("crossref", "override_title")
ANCHOR_ABSENT = Branch("crossref", "anchor_absent")
ANCHOR_NO_LANGUAGE = Branch("crossref", "anchor_no_language")
SEARCHER = Branch("crossref", "searcher")
ANCHOR_EMPTY_CORPUS = Branch("crossref", "anchor_empty_corpus")
ANCHOR_NO_ANSWER = Branch("crossref", "anchor_no_answer")
ANCHOR_HIT = Branch("crossref", "anchor_hit")


def _ids(skill: Skill) -> set[str]:
    return {r.id for r in skill.rules} | {rid for rid, _, _ in skill.core_rules}


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
    known: dict[str, set[str]], root: Path | None = None
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
        for m in CITATION.finditer(path.read_text()):
            prefix = m.group(1)
            if prefix in known and m.group(0) not in known[prefix]:
                yield fail(
                    f"cites {m.group(0)}, which is not a rule",
                    Location(file=rel),
                    APPARATUS_CITATION,
                )


def _plain(s: str) -> str:
    """A title, comparable however it was quoted.

    Titles are quoted with backticks in one place and not the other.
    """
    return " ".join(s.replace("`", "").split()).lower()


@check(
    "crossref",
    "citations into another skill, and the override table",
    needs=("rg",),
)
def crossref(tree: Tree) -> Iterator[Finding]:
    """Every citation across skills, and each delta's override table."""
    by_prefix = {s.prefix: s for s in tree}
    by_name = {s.name: s for s in tree}
    known = {p: _ids(s) for p, s in by_prefix.items()}
    titles = {p: {r.id: r.title for r in s.rules} for p, s in by_prefix.items()}

    for skill in tree:
        yield from _citations(skill, by_prefix, known)

        # The override table: each row names a rule of the other
        # standard, the rule that applies instead, and enough of the
        # other's title to prove the row still points where it did when
        # it was written.
        rows = list(OVERRIDE_ROW.finditer(skill.text))
        yield from _override_rows(skill, rows, titles)

        yield from _delta(skill, rows)
        yield from _anchor_patterns(skill, by_name)

        # A skill that cites another standard at all should say where it
        # disagrees with it; one that cites none needs no table. A delta
        # is held to that by `_delta`, as a failure.
        cites_other = any(
            p != skill.prefix and p in known
            for path in skill.markdown
            for p, _ in CITATION.findall(path.read_text())
        )
        if cites_other and not rows and not skill.profile.anchor:
            yield note(
                "cites another standard but states no override table",
                skill.at(),
                NO_TABLE,
            )

    yield from _apparatus_citations(known)


def _delta(skill: Skill, rows: list[re.Match[str]]) -> Iterator[Finding]:
    """A delta names its anchor, and states where it departs from it.

    `delta_step` is what marks a delta, so the two declarations have to
    agree. A delta with no override table claims that it relaxes nothing
    — which was the reading when the table was deleted outright, and the
    anchor sweep switched off with it.
    """
    profile = skill.profile
    if bool(profile.delta_step) != bool(profile.anchor):
        yield fail(
            "the profile sets one of `delta_step` and `anchor` without the "
            "other; a delta declares both, a standard that stands alone neither",
            skill.at(),
            DELTA_DECLARATION,
        )
    departures = [m for m in rows if not m.group(1).startswith(f"{skill.prefix}-")]
    if profile.anchor and not departures:
        yield fail(
            f"is a delta on {profile.anchor} and states no override table — "
            "a delta that says where it departs from nothing has either departed "
            "silently or lost its table",
            skill.at(),
            DELTA_NO_TABLE,
        )


def _citations(
    skill: Skill, by_prefix: dict[str, Skill], known: dict[str, set[str]]
) -> Iterator[Finding]:
    """Every id this skill cites in another skill names a rule there."""
    for path in skill.markdown:
        text = path.read_text()
        for m in CITATION.finditer(text):
            prefix = m.group(1)
            if prefix == skill.prefix or prefix not in known:
                continue
            if m.group(0) not in known[prefix]:
                yield fail(
                    f"cites {m.group(0)}, "
                    f"which is not a rule in {by_prefix[prefix].name}",
                    skill.at(path),
                    FOREIGN_CITATION,
                )


def _override_rows(
    skill: Skill, rows: list[re.Match[str]], titles: dict[str, dict[str, str]]
) -> Iterator[Finding]:
    """Each override row names a rule here and quotes a title whole."""
    for m in rows:
        theirs, quoted, ours = m.group(1), m.group(2), m.group(3)
        if theirs.startswith(skill.prefix) or theirs[:2] not in titles:
            continue
        if ours not in _ids(skill):
            yield fail(
                f"override row names {ours}, which is not a rule here",
                skill.at(),
                OVERRIDE_TARGET,
            )
        actual = titles[theirs[:2]].get(theirs)
        if actual is None:
            continue  # the citation check above already reported it
        # The whole title, not a prefix of it. A title's tail is
        # where its scope lives — `RS-BUILD-21` ends "in a library"
        # — so a row that quotes a prefix can invent a divergence by
        # dropping the clause that rules it out. Two rows did
        # exactly that.
        if quoted and _plain(actual) != _plain(quoted):
            yield fail(
                f"override row quotes {quoted!r} for {theirs}, "
                f"which is titled {actual!r}",
                skill.at(),
                OVERRIDE_TITLE,
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
    anywhere: in the override table, or in the prose that says why a
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
    if not skill.profile.languages:
        yield fail(
            f"is a delta on {other.name} and its profile names no language, so the "
            "anchor's patterns have no examples to run over",
            skill.at(),
            ANCHOR_NO_LANGUAGE,
        )
        return
    named = set(re.findall(r"\b[A-Z]{2}-[A-Z]+-\d+[a-z]?\b", skill.text))
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
    for rule in other.rules:
        if not rule.check or rule.id in named:
            continue
        yield from _sweep(skill, corpus, other, rule)


def _sweep(skill: Skill, corpus: Corpus, other: Skill, rule: Rule) -> Iterator[Finding]:
    """The anchor rule's decisive patterns, over the delta's corpus."""
    for pattern in patterns_of(rule.check):
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
        chapter, owner, line, snippet = corpus.origin(lines[0].start)
        yield fail(
            f"{rule.id} {used} /{pattern.text}/ hits {len(lines)} line(s) and "
            f"{skill.name}'s SKILL.md never mentions it — {rule.title}\n"
            f"      {chapter}:{line} [{owner}] {snippet}",
            skill.at(),
            ANCHOR_HIT,
        )
