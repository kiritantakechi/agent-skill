"""Renumber a standard's rules and rename its chapters.

Every citation of either is rewritten in the same pass. One operation,
because the defect it prevents is the one a hand edit makes. Dense
numbering reuses IDs routinely — the old `-03` is the new `-02` while a
different rule becomes the new `-03` — so a rewrite done as a chain of
replacements turns every overlap into a citation of the wrong rule, and
the result is indistinguishable from a correct one. Here every citation
is rewritten in a single pass from one dictionary built from the old
numbering, and the result is verified by identity: each rule keeps its
title, so every old ID must reach a rule with the same title after the
rewrite. Nothing is written until that holds.

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
lazy from collections.abc import Iterator

from agent_skill import shared, vocabulary
from agent_skill.model import DASH, RENAMED, Rename, Skill, rename_tables
from agent_skill.text import reflow
lazy from agent_skill.profiles import Profile


class RenumberError(Exception):
    """The renumbering cannot be done as asked; nothing was written."""


@dataclass
class Plan:
    """What a renumbering will move, rewrite and report."""

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
    profile: Profile | None = None

    @property
    def changed(self) -> int:
        """How many rule IDs the renumbering changes."""
        return sum(1 for old, new in self.ids.items() if old != new)


def plan(
    repo: Path,
    name: str,
    chapters: dict[str, str] | None = None,
    profile: Profile | None = None,
) -> Plan:
    """Everything the renumbering would do, verified.

    Nothing is done yet.
    """
    chapters = dict(chapters or {})
    skills_dir = repo / "skills"
    skill = Skill(skills_dir / name, profile)
    prefix = skill.prefix
    stems = {c.path.stem for c in skill.chapters}

    for old, new in chapters.items():
        if old not in stems:
            msg = f"{name} has no chapter `{old}.md`"
            raise RenumberError(msg)
        if not vocabulary.allowed(new):
            msg = f"`{new}` is not a chapter name in the shared vocabulary"
            raise RenumberError(msg)
    targets = [chapters.get(s, s) for s in stems]
    if len(set(targets)) != len(targets):
        msg = f"two chapters would both be called {sorted(targets)}"
        raise RenumberError(msg)

    ids: dict[str, str] = {}
    families: dict[str, set[str]] = {}
    for chapter in skill.chapters:
        stem = chapters.get(chapter.path.stem, chapter.path.stem)
        code = vocabulary.code_for(stem)
        if not code and chapter.rules:
            msg = f"`{stem}.md` has no family code, and it holds rules"
            raise RenumberError(msg)
        for i, rule in enumerate(chapter.rules, 1):
            ids[rule.id] = f"{prefix}-{code}-{i:02d}"
            families.setdefault(rule.id.split("-")[1], set()).add(code)
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
    cites = _Citations(name, prefix, ids, family_map, renamed_stems)

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
        new, leftovers = _rewrite(text, path, cites, own=own, outside=outside)
        plan.leftovers += leftovers
        target = moves.get(path, path)
        if new != text or target != path:
            plan.writes[target] = new

    _counts(skill, chapters, plan)
    _compose(skill, plan)
    _verify(repo, skill, plan)
    return plan


def _counts(skill: Skill, chapters: dict[str, str], plan: Plan) -> None:
    """Restate `SKILL.md`'s counts from the rules as they will be.

    The counts are one per family in the reference map, and the total in
    the description. A count is the one thing a renumbering always
    changes and a person always forgets.
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
    """Move the chapters and write every rewritten file.

    `plan` is already verified.

    Then restate the shared passages, which carry a rule count of their
    own: the change that left a gap to close, a demotion, moved it.
    """
    for old, new in plan.moves.items():
        tracked = subprocess.run(  # noqa: S603 — a fixed argv, no shell
            ["git", "ls-files", "--error-unmatch", str(old)],  # noqa: S607 — the git on PATH, as a person runs it
            cwd=repo,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            subprocess.run(["git", "mv", str(old), str(new)], cwd=repo, check=True)  # noqa: S603, S607 — a fixed argv; the git on PATH
        else:
            old.rename(new)
    for path, text in plan.writes.items():
        path.write_text(text)
    shared.rewrite(Skill(repo / "skills" / plan.skill, plan.profile))


# ------------------------------------------------------------------ the
# rewrite


def _corpus(repo: Path) -> list[Path]:
    """Every file a citation can live in.

    The archived OpenSpec changes are history, and keep the IDs they
    were written with.
    """
    out = [p for p in (repo / "skills").rglob("*") if p.is_file() and p.suffix in _TEXT]
    out += sorted((repo / "src").rglob("*.py")) + sorted((repo / "tests").rglob("*.py"))
    readme = repo / "README.md"
    return out + ([readme] if readme.is_file() else [])


_TEXT = {".md", ".toml", ".yml", ".yaml", ".zig", ".zon", ".py", ".rs", ""}


@dataclass(frozen=True, slots=True)
class _Citations:
    """What every citation is rewritten from, in a single pass.

    Built once, from the old numbering. `stems` holds only the chapters
    being renamed.
    """

    name: str
    prefix: str
    ids: dict[str, str]
    families: dict[str, str]
    stems: dict[str, str]

    def ids_in(self, segment: str, unknown: set[str]) -> str:
        """`segment` with every rule ID and family code rewritten.

        A rule ID the skill does not define is left as it was, and added
        to `unknown` unless it is a core rule's.
        """
        pattern = re.compile(rf"\b{self.prefix}-([A-Z]+)(?:-(\d+[a-z]?))?\b")

        def swap(m: re.Match[str]) -> str:
            whole, code, number = m.group(0), m.group(1), m.group(2)
            if number is not None:
                if whole in self.ids:
                    return self.ids[whole]
                if code != "CORE":
                    unknown.add(whole)
                return whole
            if code in self.families:
                return f"{self.prefix}-{self.families[code]}"
            return whole

        return pattern.sub(swap, segment)

    def paths_in(self, segment: str, *, own: bool) -> str:
        """`segment` with every path to a renamed chapter rewritten.

        A bare `references/x.md` is rewritten only in the skill's `own`
        files, where it can mean nothing but this skill's chapter.
        """
        for old, new in self.stems.items():
            segment = segment.replace(
                f"{self.name}/references/{old}.md", f"{self.name}/references/{new}.md"
            )
            if own:
                segment = re.sub(
                    rf"(?<![\w/-])references/{re.escape(old)}\.md",
                    f"references/{new}.md",
                    segment,
                )
        return segment


def _rewrite(
    text: str, path: Path, cites: _Citations, *, own: bool, outside: bool
) -> tuple[str, list[str]]:
    """One pass over `text`, rename tables left as they are.

    Returns the rewritten text, and the lines a person should look at.
    """
    unknown: set[str] = set()
    out: list[str] = []
    for segment, protected in _segments(text):
        if protected:
            out.append(segment)
        else:
            out.append(cites.paths_in(cites.ids_in(segment, unknown), own=own))
    rewritten = "".join(out)
    if path.suffix == ".md" and rewritten != text:
        rewritten = reflow(rewritten)

    leftovers = [
        f"{path}: cites {rid}, which {cites.name} does not define; left as it was"
        for rid in sorted(unknown)
    ]
    if outside and not own:
        leftovers += [
            f"{path}: names `references/{old}.md` without its skill"
            for old in cites.stems
            if re.search(rf"(?<![\w/-])references/{re.escape(old)}\.md", rewritten)
        ]
    return rewritten, leftovers


def _segments(text: str) -> Iterator[tuple[str, bool]]:
    """`text` cut into (segment, protected) pieces.

    Each rename table is a protected piece, and nothing else is.
    """
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
    """Carry `migration.md`'s rename tables through this renumbering."""
    # Named as it will be: the run that renames the migration chapter
    # also writes its table.
    migration = next(
        (
            c
            for c in skill.chapters
            if plan.moves.get(c.path, c.path).stem == "migration"
        ),
        None,
    )
    if migration is None:
        msg = f"{skill.name} has no references/migration.md for its rename table"
        raise RenumberError(msg)
    path = plan.moves.get(migration.path, migration.path)
    text = plan.writes.get(path, migration.text)
    now = {old: f"`{new}`" for old, new in plan.ids.items()}
    plan.writes[path] = carry(text, heading(skill), now)


def heading(skill: Skill) -> str:
    """The rename table's heading for the revision `skill` is at now."""
    return (
        f"## Rule IDs before the {skill.profile.language} "
        f"{skill.profile.pin()} revision"
    )


def carry(text: str, revision: str, now: dict[str, str]) -> str:
    """`text`, its rename tables carried through one change to the IDs.

    The table headed `revision` is started if it is missing and an ID
    changed.

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
    out: list[str] = []
    pos = 0
    for table in rename_tables(text):
        if not table.ranges:
            msg = f"`{table.heading}` states no ranges, so its unlisted IDs are lost"
            raise RenumberError(msg)
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
            msg = (
                f"{row.before} has no row, so the table says it is unchanged, and no "
                "rule carries it — record what it became first"
            )
            raise RenumberError(msg)
        if row.target and row.target not in now:
            msg = (
                f"{row.before} became {row.target}, which no longer exists — record "
                "what it became (a rule ID, lint `tool:name`, or removed — reason) "
                "first"
            )
            raise RenumberError(msg)
        out.append(
            Rename(row.before, now[row.target] if row.target else row.now, row.line)
        )
    return _changed(out)


def _changed(rows: list[Rename]) -> list[Rename]:
    """The rows worth printing.

    A row that maps an ID to itself is what the range already says.
    """
    return [r for r in rows if r.target != r.before]


def _ranges(ids: dict[str, str]) -> tuple[tuple[str, int, int], ...]:
    """The runs of consecutive numbers each family held.

    In the order the families appear. A suffixed ID such as `-03a`
    belongs to no run; dense numbering always gives it a row.
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
        msg = f"`{heading}` would list one old ID twice"
        raise RenumberError(msg)
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
                f"Before the revision the families ran {stated}. The table lists "
                "every ID in those ranges that changed, and what it is now; an ID it "
                "does not list is unchanged."
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
    """Check, on a copy, that every old ID still reaches the same rule.

    The plan is applied to a copy of the skills, not to the skills. A
    title can itself cite a rule, so the title expected afterwards is
    the old one with the same rewrite applied.
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
        msg = f"{len(before)} rules before and {len(after)} after"
        raise RenumberError(msg)
