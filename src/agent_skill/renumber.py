"""Renumber a standard's rules, rename its chapters, and rewrite every citation.

One operation, because the defect it prevents is the one a hand edit
makes. Dense numbering reuses IDs routinely — the old `-03` is the new
`-02` while a different rule becomes the new `-03` — so a rewrite done
as a chain of replacements turns every overlap into a citation of the
wrong rule, and the result is indistinguishable from a correct one. Here
every citation is rewritten in a single pass from one dictionary built
from the old numbering, and the result is verified by identity: each
rule keeps its title, so every old ID must reach a rule with the same
title after the rewrite. Nothing is written until that holds.

A rename table in the migration chapter states the range each family ran
before the revision, and lists every old ID that changed. Run twice over
one revision, the second run composes onto the first against those
ranges: a row whose new ID moves again is updated in place, and an
original that moves for the first time gains a row, so the table always
maps the IDs a reader had before the revision to the IDs they have now.
"""

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from agent_skill import shared, vocabulary
from agent_skill.model import DASH, RENAMED, Rename, Skill, rename_tables
from agent_skill.text import reflow


class RenumberError(Exception):
    """The renumbering cannot be done as asked, and nothing was written."""


@dataclass
class Plan:
    skill: str
    #: chapter path -> its new path, for the chapters being renamed
    moves: dict[Path, Path]
    #: old rule ID -> new rule ID, for every rule the skill defines
    ids: dict[str, str]
    #: old family code -> new family code
    families: dict[str, str]
    #: path (as it will be after the moves) -> its rewritten text
    writes: dict[Path, str]
    #: things the rewrite could not decide and a person should look at
    leftovers: list[str] = field(default_factory=list)
    #: the profile the skill was read with, for reading it again once
    #: written
    profile: object = None

    @property
    def changed(self) -> int:
        return sum(1 for old, new in self.ids.items() if old != new)


def plan(
    repo: Path, name: str, chapters: dict[str, str] | None = None, profile=None
) -> Plan:
    """Everything the renumbering would do, verified, and nothing done yet."""
    chapters = dict(chapters or {})
    skills_dir = repo / "skills"
    skill = Skill(skills_dir / name, profile)
    prefix = skill.prefix
    stems = {c.path.stem for c in skill.chapters}

    for old, new in chapters.items():
        if old not in stems:
            raise RenumberError(f"{name} has no chapter `{old}.md`")
        if not vocabulary.allowed(new):
            raise RenumberError(
                f"`{new}` is not a chapter name in the shared vocabulary"
            )
    targets = [chapters.get(s, s) for s in stems]
    if len(set(targets)) != len(targets):
        raise RenumberError(f"two chapters would both be called {sorted(targets)}")

    ids: dict[str, str] = {}
    families: dict[str, set[str]] = {}
    for chapter in skill.chapters:
        stem = chapters.get(chapter.path.stem, chapter.path.stem)
        code = vocabulary.code_for(stem)
        if code is None and chapter.rules:
            raise RenumberError(f"`{stem}.md` has no family code, and it holds rules")
        for i, rule in enumerate(chapter.rules, 1):
            ids[rule.id] = f"{prefix}-{code}-{i:02d}"
            families.setdefault(rule.id.split("-")[1], set()).add(code or "")
    family_map = {
        old: next(iter(new)) for old, new in families.items() if len(new) == 1
    }

    moves = {
        c.path: c.path.with_name(f"{chapters[c.path.stem]}.md")
        for c in skill.chapters
        if chapters.get(c.path.stem, c.path.stem) != c.path.stem
    }
    plan = Plan(name, moves, ids, family_map, {}, profile=profile)
    renamed_stems = {old: new for old, new in chapters.items() if old != new}

    profile_file = (
        repo / "src" / "agent_skill" / "profiles" / f"{name.replace('-', '_')}.py"
    )
    for path in _corpus(repo):
        text = path.read_text()
        own = skill.root in path.parents or path == profile_file
        # Another skill naming `references/x.md` means its own chapter;
        # only code and prose outside the skills can name this one's
        # without saying so.
        outside = skills_dir not in path.parents
        new = _rewrite(
            text, prefix, ids, family_map, renamed_stems, name, own, outside, plan, path
        )
        target = moves.get(path, path)
        if new != text or target != path:
            plan.writes[target] = new

    _counts(skill, chapters, plan)
    _compose(skill, plan)
    _verify(repo, skill, plan)
    return plan


def _counts(skill: Skill, chapters: dict[str, str], plan: Plan) -> None:
    """Restate the counts `SKILL.md` gives — per family in the reference map, and the total in
    the description — from the rules as they will be. A count is the one thing a renumbering
    always changes and a person always forgets.
    """
    path = skill.skill_md
    text = plan.writes.get(path, skill.text)
    total = len(skill.rules) + len(skill.core_rules)
    new = re.sub(r"\b\d+(-rule \w+)", rf"{total}\1", text, count=1)
    for chapter in skill.chapters:
        code = vocabulary.code_for(chapters.get(chapter.path.stem, chapter.path.stem))
        if code:
            family = f"`{skill.prefix}-{code}`"
            new = re.sub(
                rf"{re.escape(family)} \(\d+\)", f"{family} ({len(chapter.rules)})", new
            )
    if new != text:
        plan.writes[path] = new


def apply(repo: Path, plan: Plan) -> None:
    """Move the chapters and write every rewritten file. `plan` is already verified.

    Then restate the shared passages, which carry a rule count of their
    own: the change that left a gap to close, a demotion, moved it.
    """
    for old, new in plan.moves.items():
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(old)],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            subprocess.run(["git", "mv", str(old), str(new)], cwd=repo, check=True)
        else:
            old.rename(new)
    for path, text in plan.writes.items():
        path.write_text(text)
    skill = Skill(repo / "skills" / plan.skill, plan.profile)
    if skill.profile.exempt_from_structure is None:
        shared.rewrite(skill)


# ------------------------------------------------------------------ the
# rewrite


def _corpus(repo: Path) -> list[Path]:
    """Every file a citation can live in. The archived OpenSpec changes are history and
    keep the IDs they were written with.
    """
    out = [p for p in (repo / "skills").rglob("*") if p.is_file() and p.suffix in _TEXT]
    out += sorted((repo / "src").rglob("*.py")) + sorted((repo / "tests").rglob("*.py"))
    readme = repo / "README.md"
    return out + ([readme] if readme.is_file() else [])


_TEXT = {".md", ".toml", ".yml", ".yaml", ".zig", ".zon", ".py", ".rs", ""}


def _rewrite(
    text: str,
    prefix: str,
    ids: dict[str, str],
    families: dict[str, str],
    stems: dict[str, str],
    name: str,
    own: bool,
    outside: bool,
    plan: Plan,
    path: Path,
) -> str:
    """One pass over `text`, rename tables left as they are."""
    pattern = re.compile(rf"\b{prefix}-([A-Z]+)(?:-(\d+[a-z]?))?\b")
    unknown: set[str] = set()

    def swap(m: re.Match[str]) -> str:
        whole, code, number = m.group(0), m.group(1), m.group(2)
        if number is not None:
            if whole in ids:
                return ids[whole]
            if code != "CORE":
                unknown.add(whole)
            return whole
        return f"{prefix}-{families[code]}" if code in families else whole

    def paths(segment: str) -> str:
        for old, new in stems.items():
            segment = segment.replace(
                f"{name}/references/{old}.md", f"{name}/references/{new}.md"
            )
            if own:
                segment = re.sub(
                    rf"(?<![\w/-])references/{re.escape(old)}\.md",
                    f"references/{new}.md",
                    segment,
                )
        return segment

    out = []
    for segment, protected in _segments(text):
        out.append(segment if protected else paths(pattern.sub(swap, segment)))
    rewritten = "".join(out)
    if path.suffix == ".md" and rewritten != text:
        rewritten = reflow(rewritten)

    for rid in sorted(unknown):
        plan.leftovers.append(
            f"{path}: cites {rid}, which {name} does not define; left as it was"
        )
    if outside and not own:
        for old in stems:
            if re.search(rf"(?<![\w/-])references/{re.escape(old)}\.md", rewritten):
                plan.leftovers.append(
                    f"{path}: names `references/{old}.md` without its skill"
                )
    return rewritten


def _segments(text: str):
    """(segment, protected) pieces of `text`, protected for each rename table."""
    pos = 0
    for m in RENAMED.finditer(text):
        nxt = re.compile(r"^## ", re.MULTILINE).search(text, m.end())
        end = nxt.start() if nxt else len(text)
        yield text[pos : m.start()], False
        yield text[m.start() : end], True
        pos = end
    yield text[pos:], False


# ------------------------------------------------------------------ the
# table


def _compose(skill: Skill, plan: Plan) -> None:
    """Carry the migration chapter's rename tables through this renumbering."""
    migration = next((c for c in skill.chapters if c.path.stem == "migration"), None)
    if migration is None:
        raise RenumberError(
            f"{skill.name} has no references/migration.md for its rename table"
        )
    path = plan.moves.get(migration.path, migration.path)
    text = plan.writes.get(path, migration.text)
    now = {old: f"`{new}`" for old, new in plan.ids.items()}
    plan.writes[path] = carry(text, heading(skill), now)


def heading(skill: Skill) -> str:
    """The heading of the rename table for the revision `skill` is at now."""
    return f"## Rule IDs before the {skill.profile.language} {skill.profile.pin()} revision"


def carry(text: str, revision: str, now: dict[str, str]) -> str:
    """`text` with every rename table carried through one change to the rule IDs, and the
    table headed `revision` started if it is missing and an ID changed.

    `now` maps every rule ID there is to what it becomes: a rule ID in
    backticks, a lint `` lint `tool:name` ``, or `removed — reason`.
    Each table maps the IDs from before one revision to the IDs now, so
    every change moves each of its originals forward: an ID with a row
    goes where its row leads, and an ID in range without one is still
    itself. A row is kept only where the result differs from the
    original. An original that no longer exists is a rule deleted
    without its disposition being recorded, and stops the run: nothing
    else knows what that rule became.
    """
    out, pos = [], 0
    for table in rename_tables(text):
        if not table.ranges:
            raise RenumberError(
                f"`{table.heading}` states no ranges, so its unlisted IDs are lost"
            )
        start, end = table.span
        listed, originals = {r.before: r for r in table.rows}, set(table.originals)
        rows = [listed.get(rid, Rename(rid, f"`{rid}`", 0)) for rid in table.originals]
        rows += [r for r in table.rows if r.before not in originals]
        tail = "\n" if end < len(text) else ""
        out += [
            text[pos:start],
            _table(table.heading, table.ranges, _forward(rows, now)) + tail,
        ]
        pos = end
    out.append(text[pos:])
    text = "".join(out)

    rows = [Rename(rid, becomes, 0) for rid, becomes in now.items()]
    if _changed(rows) and not re.search(
        rf"^{re.escape(revision)}$", text, re.MULTILINE
    ):
        text = (
            text.rstrip("\n") + "\n\n" + _table(revision, _ranges(now), _changed(rows))
        )
    return reflow(text)


def _forward(rows: list[Rename], now: dict[str, str]) -> list[Rename]:
    out = []
    for row in rows:
        if row.target == row.before and row.target not in now:
            raise RenumberError(
                f"{row.before} has no row, so the table says it is unchanged, and no rule carries "
                f"it — record what it became first"
            )
        if row.target and row.target not in now:
            raise RenumberError(
                f"{row.before} became {row.target}, which no longer exists — record what it "
                f"became (a rule ID, lint `tool:name`, or removed — reason) first"
            )
        out.append(
            Rename(row.before, now[row.target] if row.target else row.now, row.line)
        )
    return _changed(out)


def _changed(rows: list[Rename]) -> list[Rename]:
    """The rows worth printing: a row mapping an ID to itself is what the range already says."""
    return [r for r in rows if r.target != r.before]


def _ranges(ids: dict[str, str]) -> tuple[tuple[str, int, int], ...]:
    """The runs of consecutive numbers each family held, in the order the families appear.
    A suffixed ID such as `-03a` belongs to no run; dense numbering always gives it a row.
    """
    numbers: dict[str, list[int]] = {}
    for rid in ids:
        if m := re.fullmatch(r"([A-Z]{2}-[A-Z]+)-(\d+)", rid):
            numbers.setdefault(m.group(1), []).append(int(m.group(2)))
    out: list[tuple[str, int, int]] = []
    for family, held in numbers.items():
        for n in sorted(held):
            if out and out[-1][0] == family and out[-1][2] == n - 1:
                out[-1] = (family, out[-1][1], n)
            else:
                out.append((family, n, n))
    return tuple(out)


def _table(
    heading: str, ranges: tuple[tuple[str, int, int], ...], rows: list[Rename]
) -> str:
    befores = [r.before for r in rows]
    if len(befores) != len(set(befores)):
        raise RenumberError(f"`{heading}` would list one old ID twice")
    spans = [
        f"`{family}-{lo:02d}`" + (f"{DASH}`{family}-{hi:02d}`" if hi > lo else "")
        for family, lo, hi in ranges
    ]
    stated = (
        ", ".join(spans[:-1]) + f" and {spans[-1]}"
        if len(spans) > 1
        else "".join(spans)
    )
    return "\n".join(
        [
            heading,
            "",
            (
                f"Before the revision the families ran {stated}. The table lists every ID in those "
                "ranges that changed, and what it is now; an ID it does not list is unchanged."
            ),
            "",
            "| Before | Now |",
            "|---|---|",
            *(f"| `{r.before}` | {r.now} |" for r in rows),
            "",
        ]
    )


# ------------------------------------------------------------------
# verification


def _verify(repo: Path, skill: Skill, plan: Plan) -> None:
    """Apply the plan to a copy and check that every old ID reaches the same rule.

    A title can itself cite a rule — a pointer's title names the rule it
    points at — so the title expected afterwards is the old one with the
    same rewrite applied.
    """
    pattern = re.compile(rf"\b{skill.prefix}-([A-Z]+)(?:-(\d+[a-z]?))?\b")

    def retitle(title: str) -> str:
        def swap(m: re.Match[str]) -> str:
            if m.group(2) is not None:
                return plan.ids.get(m.group(0), m.group(0))
            code = m.group(1)
            return (
                f"{skill.prefix}-{plan.families[code]}"
                if code in plan.families
                else m.group(0)
            )

        return pattern.sub(swap, title)

    before = {r.id: retitle(r.title) for r in skill.rules}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        shutil.copytree(repo / "skills", root / "skills", symlinks=True)

        def mirror(p: Path) -> Path:
            return root / p.relative_to(repo)

        for old, new in plan.moves.items():
            mirror(old).rename(mirror(new))
        for path, text in plan.writes.items():
            if (repo / "skills") in path.parents:
                mirror(path).write_text(text)
        after = {
            r.id: r.title
            for r in Skill(root / "skills" / skill.name, skill.profile).rules
        }

    wrong = [
        f"{old} → {new}: `{before[old]}` became `{after.get(new, 'nothing')}`"
        for old, new in plan.ids.items()
        if after.get(new) != before[old]
    ]
    if wrong:
        raise RenumberError(
            "a citation would change meaning:\n  " + "\n  ".join(wrong[:10])
        )
    if len(after) != len(before):
        raise RenumberError(f"{len(before)} rules before and {len(after)} after")
