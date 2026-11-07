"""The demo standard, built for a test to try a check or a command on.

There is one demo, `checks.demo`: a standard of three rules in normal
form, which the controls break one property at a time. This writes it
under a test's directory, reads it back, and edits it.
"""

lazy from pathlib import Path

from agent_skill import shared
from agent_skill.checks import demo
from agent_skill.layout import SKILLS
from agent_skill.model import Skill, Tree
lazy from agent_skill.profiles import Profile

#: The demo's profile: a standard verified against Demo 1.2.3.
DEMO = demo.PROFILE


def build(root: Path, profile: Profile | None = None) -> Skill:
    """Write the demo under `root/demo-style` and return it parsed.

    Read with `profile` when one is given, and its shared passages
    filled for it, as `fmt` would fill them: a fence's comment, the
    target the title names.
    """
    demo.build(root)
    skill = Skill(root / DEMO.name, profile or DEMO)
    if profile is not None:
        shared.rewrite(skill)
    return reparse(skill)


def reparse(skill: Skill) -> Skill:
    """The same skill read again, after a test edited its files."""
    return Skill(skill.root, skill.profile)


def edit(skill: Skill, rel: str, old: str, new: str) -> Skill:
    """`skill` with the first `old` in `rel` replaced, read again."""
    path = skill.root / rel
    text = path.read_text()
    assert old in text, f"{rel}: {old!r} not found"
    path.write_text(text.replace(old, new, 1))
    return reparse(skill)


def repository(root: Path) -> Tree:
    """The demo, its delta and the demo abstract standard, laid out.

    Laid out as a repository is, under `root`: the skills where a
    plugin keeps them, the abstract standard beside them at the root,
    so a check that reads what sits beside the skills finds it. Each
    standard is read with its own profile.
    """
    skills = root / SKILLS
    skills.mkdir(parents=True)
    demo.build(skills)
    demo.build_delta(skills)
    demo.build_abstract(root)
    return Tree.of(Skill(skills / name, p) for name, p in demo.PROFILES.items())
