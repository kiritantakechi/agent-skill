"""The laws `revise` keeps, on throwaway copies of the shipped skills.

A revision is a map over the repository, so what it must preserve is
stated as laws and tested on the real corpus, where the overlaps that
dense numbering makes routine actually occur: a renaming followed by its
inverse restores every byte, an empty plan writes and reports nothing,
every citation names the rule it named, and a citation of an ID that
named no rule is never handed one. Plans are drawn from seeded
generators and sampled, not enumerated: each revision rewrites the
whole repository, so a few draws cover the laws without costing the run
much.
"""

import random
import re
import shutil
from collections import Counter
from pathlib import Path
lazy from collections.abc import Iterator

import pytest

from agent_skill import cli, revise, vocabulary
from agent_skill.doc import Doc, text_of
from agent_skill.doc.chapter import (
    Chapter,
    Contents,
    Demoted,
    Entry,
    Group,
    LintRow,
    Removed,
    RenameTable,
    Section,
    citing,
)
from agent_skill.ids import RuleId, cited, uncited
from agent_skill.layout import SKILLS
from agent_skill.model import Skill, Tree, discover
lazy from agent_skill.doc.chapter import Becomes

ROOT = Path(__file__).resolve().parents[1]

#: The parts of the repository a revision reads and rewrites.
PARTS = ("plugins", "src", "tests")

#: The families the shared passages illustrate citation with, spelled
#: `{prefix}-ERR-03` in a template. Renaming one of those chapters is a
#: change to the template, which a revision of one standard cannot make:
#: `shared.rewrite` puts the old example back, and the inverse renaming
#: then refuses it as a capture, rightly.
ILLUSTRATED = frozenset(
    m
    for template in (ROOT / "src/agent_skill/shared").glob("*.md")
    for m in re.findall(r"\{prefix\}-([A-Z]+)-\d+", template.read_text())
)


def seeded(seed: int) -> random.Random:
    """A generator that draws the same plan every run."""
    return random.Random(seed)  # noqa: S311 — reproducible test cases, not secrets


@pytest.fixture(scope="module")
def shipped(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The standards, sources, tests and README, copied once."""
    root = tmp_path_factory.mktemp("shipped")
    for part in PARTS:
        ignore = shutil.ignore_patterns("__pycache__")
        shutil.copytree(ROOT / part, root / part, ignore=ignore)
    shutil.copy(ROOT / "README.md", root / "README.md")
    return root


@pytest.fixture
def repo(shipped: Path, tmp_path: Path) -> Path:
    """A copy of the shipped repository to revise."""
    return shutil.copytree(shipped, tmp_path / "repo")


def snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def skill(repo: Path, name: str) -> Skill:
    return Skill(repo / SKILLS / name)


def apply(
    repo: Path,
    name: str,
    plan: revise.Plan | None = None,
    chapters: dict[str, str] | None = None,
) -> revise.Revision:
    revision = revise.revise(Tree.of([skill(repo, name)]), plan, chapters)
    revision.apply()
    return revision


def renamings(shipped: Path, seed: int) -> tuple[str, dict[str, str]]:
    """A skill, and an injective renaming of some of its chapters.

    Targets are drawn from the chosen chapters and the names no chapter
    of the skill has, so a draw can rename, swap or cycle.
    """
    rng = seeded(seed)
    standard = rng.choice(discover(shipped / SKILLS))
    stems = sorted(c.path.stem for c in standard.chapters)
    movable = [
        c.path.stem
        for c in standard.chapters
        if c.typed.rules and vocabulary.code_for(c.path.stem) not in ILLUSTRATED
    ]
    free = [s for s in vocabulary.CHAPTERS if s not in stems]
    chosen = rng.sample(movable, rng.randint(1, 3))
    targets = rng.sample([*chosen, *free], len(chosen))
    renaming = {
        old: new for old, new in zip(chosen, targets, strict=True) if old != new
    }
    return standard.name, renaming or {chosen[0]: free[0]}


# ------------------------------------------------------------------ a


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_renaming_then_its_inverse_restores_every_byte(
    shipped: Path, repo: Path, seed: int
) -> None:
    name, renaming = renamings(shipped, seed)
    before = snapshot(repo)

    forward = apply(repo, name, chapters=renaming)
    apply(repo, name, chapters={new: old for old, new in renaming.items()})

    assert forward.renamed, renaming
    after = snapshot(repo)
    assert sorted(after.keys() ^ before.keys()) == []
    assert [p for p in before if before[p] != after[p]] == []


def test_a_swap_is_one_permutation_and_its_own_inverse(repo: Path) -> None:
    """`api` and `data` trade names: each old ID is another's new."""
    names = {"api": "data", "data": "api"}
    standard = skill(repo, "python-style")
    title = {
        c.path.stem: c.typed.rules[0].title for c in standard.chapters if c.typed.rules
    }
    before = snapshot(repo)

    apply(repo, "python-style", chapters=names)
    swapped = {str(r.id): r for r in skill(repo, "python-style").chapter_rules}
    apply(repo, "python-style", chapters=names)

    assert swapped["PS-API-01"].title == title["data"]
    assert swapped["PS-DATA-01"].title == title["api"]
    assert snapshot(repo) == before


# ------------------------------------------------------------------ b


def test_an_empty_plan_writes_nothing_and_reports_nothing(repo: Path) -> None:
    before = snapshot(repo)

    revision = revise.revise(Tree.of(discover(repo / SKILLS)), {})
    revision.apply()

    assert revision.empty
    assert revision.renamed == {}
    assert snapshot(repo) == before


def test_renumbering_a_dense_standard_says_so_and_writes_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = snapshot(repo)
    skills = str(repo / SKILLS)

    assert cli.main(["--skills", skills, "renumber", "zig-style"]) == 0

    assert capsys.readouterr().out.startswith("nothing to revise")
    assert snapshot(repo) == before


# ------------------------------------------------------------------ c


def corpus_citations(repo: Path, prefix: str) -> dict[Path, list[RuleId]]:
    """Every ID each file cites under `prefix`, in order.

    A standard's markdown is read through its tree, its rename tables
    left out: they list old IDs on purpose.
    """
    out: dict[Path, list[RuleId]] = {}
    for path in revise.corpus(repo):
        text = path.read_text()
        if path.suffix == ".md" and repo / SKILLS in path.parents:
            doc = Doc.parse(text)
            text = "\n\n".join(
                [doc.frontmatter or "", *(text_of((b,)) for b in citing(doc))]
            )
        out[path.relative_to(repo)] = list(cited(text, prefix))
    return out


def titled(standard: Skill) -> dict[RuleId, str]:
    """Each rule's title, any ID in it taken out; a core rule's ID."""
    titles = {r.id: uncited(r.title) for r in standard.chapter_rules}
    return titles | {r.id: str(r.id) for r in standard.core}


def history(standard: Skill) -> RenameTable:
    """The table for the revision `standard` is at."""
    renames = Chapter.read(Doc.parse(standard.renames_md.read_text())).renames
    heading = revise.heading(standard)
    return next(t for t in renames if t.heading == heading)


def mapped(table: RenameTable) -> dict[RuleId, Becomes]:
    """What `table` says each original is now."""
    listed = {r.before: r.now for r in table.rows}
    return {o: listed.get(o, o) for o in table.originals}


def plans(repo: Path, seed: int) -> tuple[str, revise.Plan]:
    """A skill, and a plan of merges, removals and demotions in it.

    A rule removed or demoted is one nothing cites but its own heading
    and contents entry, since a citation of it stops the revision; a
    merge may be cited anywhere, and its citations follow it, into a
    rule the plan keeps. A demotion becomes a row the standard lists
    already.
    """
    rng = seeded(seed)
    standard = rng.choice(discover(repo / SKILLS))
    cites = Counter(
        rid for ids in corpus_citations(repo, standard.prefix).values() for rid in ids
    )
    rules = [r.id for r in standard.chapter_rules]
    # Cited twice: by its own heading, and by its contents entry.
    quiet = [rid for rid in rules if cites[rid] == 2]
    rows = [row for c in standard.chapters for row in c.typed.tools]
    gone = rng.sample(quiet, 2)
    merged = rng.sample([r for r in rules if r not in gone], 2)
    kept = [r for r in rules if r not in gone and r not in merged]
    out: dict[RuleId, revise.Becomes] = {
        gone[0]: Removed(f"drawn by seed {seed}"),
        gone[1]: rng.choice(rows),
    }
    for rid in merged:
        out[rid] = rng.choice(kept)
    return standard.name, out


def follows(plan: revise.Plan, rid: RuleId) -> RuleId:
    """The rule a citation of `rid` names after the plan, merged."""
    into = plan.get(rid)
    return into if isinstance(into, RuleId) else rid


@pytest.mark.parametrize("seed", [4, 5])
def test_every_citation_names_its_rule_after_or_the_table_says_why(
    repo: Path, seed: int
) -> None:
    name, plan = plans(repo, seed)
    before = skill(repo, name)
    prefix, titles, table = before.prefix, titled(before), mapped(history(before))
    edited = {
        c.path.relative_to(repo)
        for c in before.chapters
        if any(r.id in plan for r in c.typed.rules)
    }
    cites = corpus_citations(repo, prefix)

    apply(repo, name, plan)

    after = skill(repo, name)
    now = titled(after)
    assert {titles[rid] for rid in plan}.isdisjoint(now.values())
    cites_after = corpus_citations(repo, prefix)
    for path, ids in cites.items():
        expected = [titles.get(follows(plan, rid)) for rid in ids]
        found = [now.get(rid) for rid in cites_after[path]]
        if path in edited:
            assert not Counter(found) - Counter(expected), path
        else:
            assert found == expected, path

    # The table: every original goes where the plan sent it.
    for original, was in mapped(history(after)).items():
        prior = table[original]
        if not isinstance(prior, RuleId):
            assert was == prior, original
            continue
        match plan.get(prior):
            case Removed() as gone:
                assert was == gone, original
            case LintRow(tool, lint):
                assert was == Demoted(tool, lint), original
            case _:
                assert isinstance(was, RuleId), original
                assert now[was] == titles[follows(plan, prior)], original


# ------------------------------------------------------------------ d


def deleted(text: str, rid: RuleId) -> str:
    """A chapter's `text`, rule `rid` deleted by hand, entry and all."""
    read = Chapter.read(Doc.parse(text))
    sections = tuple(
        Section(s.title, s.lead, tuple(r for r in s.rules if r.id != rid), s.line)
        for s in read.sections
    )
    assert read.contents is not None
    items = tuple(_listed(read.contents.items, rid))
    contents = Contents(items, read.contents.loose, read.contents.line)
    return str(Chapter(read.title, read.scope, contents, sections).doc())


def _listed(items: tuple[Group | Entry, ...], rid: RuleId) -> Iterator[Group | Entry]:
    """Contents `items` without the entry for `rid`."""
    for item in items:
        if isinstance(item, Group):
            yield Group(item.label, tuple(_listed(item.children, rid)), item.line)
        elif item.id != rid:
            yield item


def capture(repo: Path, seed: int) -> tuple[str, dict[str, str], RuleId, RuleId]:
    """A renaming, an ID it would give a rule, and that rule's ID now.

    Cited before the renaming, the ID names nothing; left as it was, it
    would name a rule nobody chose for it.
    """
    name, renaming = renamings(repo, seed)
    standard = skill(repo, name)
    rng = seeded(seed)
    old = rng.choice(sorted(renaming))
    rules = next(c for c in standard.chapters if c.path.stem == old).typed.rules
    owner = rng.choice(rules).id
    code = vocabulary.code_for(renaming[old])
    return name, renaming, RuleId(standard.prefix, code, owner.number), owner


def refusal(captive: RuleId, owner: RuleId) -> str:
    """The refusal naming `captive`, which the README cites."""
    return (
        rf"{captive}, cited in [^\n]*README\.md[^\n]*, names no rule, and would "
        rf"name the rule that is {owner} now"
    )


@pytest.mark.parametrize("seed", [6, 7])
def test_a_citation_the_renaming_would_capture_stops_it(repo: Path, seed: int) -> None:
    name, renaming, captive, owner = capture(repo, seed)
    readme = repo / "README.md"
    readme.write_text(readme.read_text() + f"\n{captive} is planned.\n")
    before = snapshot(repo)

    with pytest.raises(revise.ReviseError, match=refusal(captive, owner)):
        apply(repo, name, chapters=renaming)

    assert snapshot(repo) == before


def test_a_gap_left_by_hand_will_not_give_its_citation_away(repo: Path) -> None:
    """A rule deleted without a plan, and still cited, closes no gap."""
    gone, next_one = RuleId.parse("PS-ERR-04"), RuleId.parse("PS-ERR-05")
    assert {gone, next_one} <= skill(repo, "python-style").ids
    chapter = repo / SKILLS / "python-style/references/errors.md"
    chapter.write_text(deleted(chapter.read_text(), gone))
    readme = repo / "README.md"
    readme.write_text(readme.read_text() + f"\nSee {gone}.\n")
    before = snapshot(repo)

    # This file is in the copy too, and cites the ID it deletes.
    with pytest.raises(revise.ReviseError, match=refusal(gone, next_one)):
        apply(repo, "python-style")

    assert snapshot(repo) == before
