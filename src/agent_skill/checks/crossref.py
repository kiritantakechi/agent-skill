"""Citations into another skill, and the table that says the two disagree.

`bevy-style` is a delta on `rust-style`: it states what changes when Bevy is in
the dependency list and defers for everything else. That makes an `RS-…` id
inside `bevy-style` a link across documents with nothing checking it, and it
makes the "where this standard departs" table a claim about two standards that
nothing was checking either — the exact shape of the defect this apparatus
exists to catch, one level up.

A citation into a skill that is not in the tree is not checked, because it
cannot be: the claim is about a document nobody here can read.
"""

import re
from pathlib import Path

from agent_skill.checks import check
from agent_skill.report import fail, note, unrun
lazy from agent_skill.checks.corpus import corpus_for
lazy from agent_skill.checks.patterns import patterns_of
lazy from agent_skill.checks.search import find, searcher_problem

#: `| `RS-API-23` Keep every struct field private | `BV-ECS-01` — … | … |`
OVERRIDE_ROW = re.compile(
    r"^\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`\s*(.*?)\s*\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`",
    re.MULTILINE,
)

CITATION = re.compile(r"\b([A-Z]{2})-([A-Z]+-\d+[a-z]?)\b")


def _ids(skill) -> set[str]:
    return {r.id for r in skill.rules} | {rid for rid, _, _ in skill.core_rules}


#: Everything outside `skills/` that names a rule. `assets.py` validates the ids
#: a skill ships, and nothing validated these — so renumbering a chapter left
#: two comments in `lang/rust.py` pointing at the rules that had moved up.
APPARATUS = ("src", "tests", "README.md")

#: Two files hold ids that are *meant* to be invalid: the negative controls
#: inject an out-of-range number precisely to prove a check fires on it.
#: Scanning those would turn each fixture into a failure. (Naming one here
#: would too — this comment is inside a scanned file.)
FIXTURES = ("checks/controls.py", "tests/test_crossref.py")


def _apparatus_citations(known: dict[str, set[str]], root: Path | None = None):
    """A rule id named in the code or the README still has to resolve.

    `root` is injectable so this has a real test: the control harness copies
    `skills/` and nothing else, so it cannot reach the files this reads.
    """
    root = root or Path(__file__).resolve().parents[3]
    files = []
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
                    f"{path.relative_to(root)}",
                )


def _plain(s: str) -> str:
    """Titles are quoted with backticks in one place and not the other."""
    return " ".join(s.replace("`", "").split()).lower()


@check(
    "crossref",
    "citations into another skill, and the override table",
    scope="all",
    needs=("rg",),
)
def crossref(skills):
    by_prefix = {s.prefix: s for s in skills}
    known = {p: _ids(s) for p, s in by_prefix.items()}
    titles = {p: {r.id: r.title for r in s.rules} for p, s in by_prefix.items()}

    for skill in skills:
        for path in skill.markdown:
            text = path.read_text()
            where = f"{skill.name}/{path.name}"
            for m in CITATION.finditer(text):
                prefix = m.group(1)
                if prefix == skill.prefix or prefix not in known:
                    continue
                if m.group(0) not in known[prefix]:
                    yield fail(
                        f"cites {m.group(0)}, which is not a rule in {by_prefix[prefix].name}",
                        where,
                    )

        # The override table: each row names a rule of the other standard, the
        # rule that applies instead, and enough of the other's title to prove
        # the row still points where it did when it was written.
        rows = list(OVERRIDE_ROW.finditer(skill.text))
        for m in rows:
            theirs, quoted, ours = m.group(1), m.group(2), m.group(3)
            if theirs.startswith(skill.prefix) or theirs[:2] not in titles:
                continue
            if ours not in _ids(skill):
                yield fail(
                    f"override row names {ours}, which is not a rule here", skill.name
                )
            actual = titles[theirs[:2]].get(theirs)
            if actual is None:
                continue  # the citation check above already reported it
            # The whole title, not a prefix of it. A title's tail is where its
            # scope lives — `RS-BUILD-23` ends "in a library" — so a row that
            # quotes a prefix can invent a divergence by dropping the clause
            # that rules it out. Two rows did exactly that.
            if quoted and _plain(actual) != _plain(quoted):
                yield fail(
                    f"override row quotes {quoted!r} for {theirs}, which is titled {actual!r}",
                    skill.name,
                )

        yield from _anchor_patterns(skill, by_prefix, rows)

        # A skill that cites another standard at all should say where it
        # disagrees with it; one that cites none needs no table.
        cites_other = any(
            p != skill.prefix and p in known
            for path in skill.markdown
            for p, _ in CITATION.findall(path.read_text())
        )
        if cites_other and not rows:
            yield note(
                "cites another standard but states no override table", skill.name
            )

    yield from _apparatus_citations(known)


def _anchor_patterns(skill, by_prefix, rows):
    """The other standard's own patterns, run over this one's examples.

    A delta claims that everything the anchor says still holds except the rows
    of its table. That claim is testable, and it was not being tested: two
    `rust-style` `[M]` rules were firing on nineteen and thirty-five lines of
    `bevy-style`'s examples with nothing saying so.

    Only the anchor's **decisive** patterns are run — the ones it ships as a
    literal `rg` command. Its prose spans are far too broad to travel: `assert_eq!`
    and `.iter()` matched a third of the corpus.

    A hit is allowed when the delta's `SKILL.md` names that rule anywhere: in
    the override table, or in the prose that says why a rule is *not* on it.
    Either way the reader has been told.
    """
    anchors = {
        p
        for p in by_prefix
        if p != skill.prefix and any(m.group(1)[:2] == p for m in rows)
    }
    if not anchors or not skill.profile.languages:
        return
    named = set(re.findall(r"\b[A-Z]{2}-[A-Z]+-\d+[a-z]?\b", skill.text))
    lang = skill.profile.languages[0]
    if problem := searcher_problem():
        yield unrun(problem, skill.name)
        return
    corpus = corpus_for(skill, lang)
    if not corpus.blocks:
        return
    for prefix in sorted(anchors):
        other = by_prefix[prefix]
        for rule in other.rules:
            if not rule.check or rule.id in named:
                continue
            for pattern in patterns_of(rule.check):
                if pattern.kind != "command":
                    continue
                lines, used = find(corpus, pattern)
                # `None` is the absence of an answer and `[]` is an answer of
                # nothing. Both are falsy, so `if not lines` reads a search that
                # never ran as a delta with nothing to account for — which is the
                # same silence this whole capability exists to refuse.
                if lines is None:
                    yield fail(
                        f"{rule.id}: {other.name}'s pattern /{pattern.text}/ gave no answer over "
                        f"{skill.name}'s examples — rejected, timed out, or not installed",
                        skill.name,
                    )
                    continue
                if not lines:
                    continue
                chapter, owner, line, snippet = corpus.origin(lines[0].start)
                yield fail(
                    f"{rule.id} {used} /{pattern.text}/ hits {len(lines)} line(s) and "
                    f"{skill.name}'s SKILL.md never mentions it — {rule.title}\n"
                    f"      {chapter}:{line} [{owner}] {snippet}",
                    skill.name,
                )
