"""Renumber a standard's rules, rename its chapters, and rewrite every citation.

One operation, because the defect it prevents is the one a hand edit makes. Dense
numbering reuses IDs routinely — the old `-03` is the new `-02` while a different
rule becomes the new `-03` — so a rewrite done as a chain of replacements turns
every overlap into a citation of the wrong rule, and the result is indistinguishable
from a correct one. Here every citation is rewritten in a single pass from one
dictionary built from the old numbering, and the result is verified by identity:
each rule keeps its title, so every old ID must reach a rule with the same title
after the rewrite. Nothing is written until that holds.

A rename table in the migration chapter records what every old ID became. Run
twice over one revision, the second run composes onto the first: a row whose new
ID is renumbered again is updated in place, so the table always maps the IDs a
reader had before the revision to the IDs they have now.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import vocabulary
from .model import RENAMED, Rename, Skill, _rows


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

    @property
    def changed(self) -> int:
        return sum(1 for old, new in self.ids.items() if old != new)


def plan(repo: Path, name: str, chapters: dict[str, str] | None = None, profile=None) -> Plan:
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
            raise RenumberError(f"`{new}` is not a chapter name in the shared vocabulary")
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
    family_map = {old: next(iter(new)) for old, new in families.items() if len(new) == 1}

    moves = {
        c.path: c.path.with_name(f"{chapters[c.path.stem]}.md")
        for c in skill.chapters
        if chapters.get(c.path.stem, c.path.stem) != c.path.stem
    }
    plan = Plan(name, moves, ids, family_map, {})
    renamed_stems = {old: new for old, new in chapters.items() if old != new}

    profile = repo / "src" / "agent_skill" / "profiles" / f"{name.replace('-', '_')}.py"
    for path in _corpus(repo):
        text = path.read_text()
        own = skill.root in path.parents or path == profile
        # Another skill naming `references/x.md` means its own chapter; only code
        # and prose outside the skills can name this one's without saying so.
        outside = skills_dir not in path.parents
        new = _rewrite(text, prefix, ids, family_map, renamed_stems, name, own, outside, plan, path)
        target = moves.get(path, path)
        if new != text or target != path:
            plan.writes[target] = new

    _compose(skill, plan)
    _verify(repo, skill, plan)
    return plan


def apply(repo: Path, plan: Plan) -> None:
    """Move the chapters and write every rewritten file. `plan` is already verified."""
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


# ------------------------------------------------------------------ the rewrite


def _corpus(repo: Path) -> list[Path]:
    """Every file a citation can live in. The archived OpenSpec changes are history and
    keep the IDs they were written with."""
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
            segment = segment.replace(f"{name}/references/{old}.md", f"{name}/references/{new}.md")
            if own:
                segment = re.sub(
                    rf"(?<![\w/-])references/{re.escape(old)}\.md", f"references/{new}.md", segment
                )
        return segment

    out = []
    for segment, protected in _segments(text):
        out.append(segment if protected else paths(pattern.sub(swap, segment)))
    rewritten = "".join(out)

    for rid in sorted(unknown):
        plan.leftovers.append(f"{path}: cites {rid}, which {name} does not define; left as it was")
    if outside and not own:
        for old in stems:
            if re.search(rf"(?<![\w/-])references/{re.escape(old)}\.md", rewritten):
                plan.leftovers.append(f"{path}: names `references/{old}.md` without its skill")
    return rewritten


def _segments(text: str):
    """(segment, protected) pieces of `text`, protected for each rename table."""
    pos = 0
    for m in RENAMED.finditer(text):
        nxt = re.compile(r"^## ", re.M).search(text, m.end())
        end = nxt.start() if nxt else len(text)
        yield text[pos : m.start()], False
        yield text[m.start() : end], True
        pos = end
    yield text[pos:], False


# ------------------------------------------------------------------ the table


def _compose(skill: Skill, plan: Plan) -> None:
    """Keep every rename table in the migration chapter current, and start this
    revision's table if it has none yet.

    Each table maps the IDs from before one revision to the IDs now, so every
    renumbering rewrites the new-ID column of every table. A row whose new ID no
    longer exists is a rule deleted without its disposition being recorded, and
    stops the run: nothing else knows what that rule became.
    """
    migration = next((c for c in skill.chapters if c.path.stem == "migration"), None)
    if migration is None:
        raise RenumberError(f"{skill.name} has no references/migration.md for its rename table")
    path = plan.moves.get(migration.path, migration.path)
    text = plan.writes.get(path, migration.text)
    heading = f"## Rule IDs before the {skill.profile.language} {skill.profile.pin()} revision"

    out, pos = [], 0
    for m in RENAMED.finditer(text):
        nxt = re.compile(r"^## ", re.M).search(text, m.end())
        end = nxt.start() if nxt else len(text)
        rows = [Rename(c[0].strip("`"), c[1], line) for line, c in _rows(text, m.start())]
        out.append(text[pos : m.start()])
        out.append(_table(m.group(0), [_forward(r, plan) for r in rows]) + ("\n" if nxt else ""))
        pos = end
    out.append(text[pos:])
    text = "".join(out)

    if not re.search(rf"^{re.escape(heading)}$", text, re.M):
        fresh = [Rename(old, f"`{new}`", 0) for old, new in plan.ids.items()]
        text = text.rstrip("\n") + "\n\n" + _table(heading, fresh)
    plan.writes[path] = text


def _forward(row: Rename, plan: Plan) -> Rename:
    if not row.target:
        return row
    if row.target not in plan.ids:
        raise RenumberError(
            f"{row.before} became {row.target}, which no longer exists — record what it became "
            f"(a rule ID, lint `tool:name`, or removed — reason) before renumbering"
        )
    return Rename(row.before, f"`{plan.ids[row.target]}`", row.line)


def _table(heading: str, rows: list[Rename]) -> str:
    befores = [r.before for r in rows]
    if len(befores) != len(set(befores)):
        raise RenumberError(f"`{heading}` would list one old ID twice")
    return "\n".join(
        [
            heading,
            "",
            "Every rule ID this standard used before the revision, and what it is now.",
            "",
            "| Before | Now |",
            "|---|---|",
            *(f"| `{r.before}` | {r.now} |" for r in rows),
            "",
        ]
    )


# ------------------------------------------------------------------ verification


def _verify(repo: Path, skill: Skill, plan: Plan) -> None:
    """Apply the plan to a copy and check that every old ID reaches the same rule."""
    before = {r.id: r.title for r in skill.rules}
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
        after = {r.id: r.title for r in Skill(root / "skills" / skill.name, skill.profile).rules}

    wrong = [
        f"{old} → {new}: `{before[old]}` became `{after.get(new, 'nothing')}`"
        for old, new in plan.ids.items()
        if after.get(new) != before[old]
    ]
    if wrong:
        raise RenumberError("a citation would change meaning:\n  " + "\n  ".join(wrong[:10]))
    if len(after) != len(before):
        raise RenumberError(f"{len(before)} rules before and {len(after)} after")
