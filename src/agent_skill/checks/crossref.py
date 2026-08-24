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

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..report import fail, note
from . import check

#: `| `RS-API-24` Keep every struct field private | `BV-ECS-01` — … | … |`
OVERRIDE_ROW = re.compile(
    r"^\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`\s*(.*?)\s*\|\s*`([A-Z]{2}-[A-Z]+-\d+[a-z]?)`", re.M
)

CITATION = re.compile(r"\b([A-Z]{2})-([A-Z]+-\d+[a-z]?)\b")


def _ids(skill) -> set[str]:
    return {r.id for r in skill.rules} | {rid for rid, _, _ in skill.core_rules}


def _plain(s: str) -> str:
    """Titles are quoted with backticks in one place and not the other."""
    return " ".join(s.replace("`", "").split()).lower()


@check("crossref", "citations into another skill, and the override table", scope="all")
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
                yield fail(f"override row names {ours}, which is not a rule here", skill.name)
            actual = titles[theirs[:2]].get(theirs)
            if actual is None:
                continue  # the citation check above already reported it
            if quoted and not _plain(actual).startswith(_plain(quoted)):
                yield fail(
                    f"override row quotes {quoted!r} for {theirs}, which is titled {actual!r}",
                    skill.name,
                )

        yield from _anchor_greps(skill, by_prefix, rows)

        # A skill that cites another standard at all should say where it
        # disagrees with it; one that cites none needs no table.
        cites_other = any(
            p != skill.prefix and p in known
            for path in skill.markdown
            for p, _ in CITATION.findall(path.read_text())
        )
        if cites_other and not rows:
            yield note("cites another standard but states no override table", skill.name)


def _anchor_greps(skill, by_prefix, rows):
    """The other standard's own greps, run over this one's examples.

    A delta claims that everything the anchor says still holds except the rows
    of its table. That claim is testable, and it was not being tested: two
    `rust-style` `[M]` rules were firing on nineteen and thirty-five lines of
    `bevy-style`'s examples with nothing saying so.

    Only the anchor's **decisive** patterns are run — the ones it ships as a
    literal `grep`. Its prose spans are far too broad to travel: `assert_eq!`
    and `.iter()` matched a third of the corpus.

    A hit is allowed when the delta's `SKILL.md` names that rule anywhere: in
    the override table, or in the prose that says why a rule is *not* on it.
    Either way the reader has been told.
    """
    from .selfapply import Corpus, patterns_of

    anchors = {p for p in by_prefix if p != skill.prefix and any(m.group(1)[:2] == p for m in rows)}
    if not anchors or not skill.profile.languages:
        return
    named = set(re.findall(r"\b[A-Z]{2}-[A-Z]+-\d+[a-z]?\b", skill.text))
    lang = skill.profile.languages[0]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        corpus = Corpus().build(skill, lang, Path(work))
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
                    lines, used = corpus.hits(pattern)
                    if not lines:
                        continue
                    chapter, owner, line, snippet = corpus.index[lines[0] - 1]
                    yield fail(
                        f"{rule.id} {used} /{pattern.text}/ hits {len(lines)} line(s) and "
                        f"{skill.name}'s SKILL.md never mentions it — {rule.title}\n"
                        f"      {chapter}:{line} [{owner}] {snippet}",
                        skill.name,
                    )
