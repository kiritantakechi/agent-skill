"""The check registry.

Every check is a function of the whole tree that yields findings. It
prints nothing and exits nothing, so the command line, pytest, and the
negative controls all drive the same code. A check about one skill at a
time is written as a function of a skill and lifted by `per_skill`.
"""

import importlib
import inspect
from dataclasses import dataclass
lazy from collections.abc import Callable, Collection, Iterable, Iterator

from agent_skill.report import Finding, Result
lazy from agent_skill.model import Skill, Tree


@dataclass(frozen=True, slots=True)
class PerSkill:
    """A check about one skill, as a check of the whole tree.

    `per_skill` makes one; this is the only place the two shapes meet.
    Every finding it makes while reading a skill lies in that skill, so
    reading fewer skills drops only findings no one asked for: that is
    what lets `--skill` and the controls read less.
    """

    each: Callable[[Skill], Iterable[Finding]]

    def __call__(self, tree: Tree) -> Iterator[Finding]:
        """What `each` finds in each skill of `tree`, skill by skill."""
        for skill in tree:
            yield from self.each(skill)

    @property
    def __wrapped__(self) -> Callable[[Skill], Iterable[Finding]]:
        """The function lifted, as `inspect.unwrap` asks for it."""
        return self.each


def per_skill(each: Callable[[Skill], Iterable[Finding]]) -> PerSkill:
    """`each`, a check of one skill, lifted to a check of the tree."""
    return PerSkill(each)


@dataclass(frozen=True, slots=True)
class Check:
    """A registered check: its name, its label, and what it runs."""

    name: str
    label: str
    #: a function of the tree; `controls` also takes the run's `fast`
    fn: Callable[..., Iterable[Finding]]
    slow: bool = False  #: needs cargo or zig
    #: External binaries without which this check cannot look.
    #:
    #: Declared rather than inferred, because inference cannot see an
    #: indirection: `pins` asks `have(tool)` in a loop over a tuple, so
    #: reading the source finds `uv` and misses `ruff`, `ty`, `pytest`
    #: and `rg`. The guarantee that a missing tool withholds the pass
    #: runs over what is declared here; `test_unrun` cross-checks it
    #: against what the source does name, so forgetting to declare one
    #: is a failure rather than a gap.
    needs: tuple[str, ...] = ()

    def wants(self, name: str) -> bool:
        """Does this check take that keyword?

        Asked of the function rather than answered by its name. The
        caller used to read `if c.name == "controls"`, which is a second
        place that has to learn about a check — and the wrong place,
        since the check's own signature already says so.
        """
        return name in inspect.signature(self.fn).parameters

    @property
    def reads_one_skill(self) -> bool:
        """Is this a check of one skill at a time, lifted?"""
        return isinstance(self.fn, PerSkill)

    def run(
        self, tree: Tree, *, about: Collection[str] = (), fast: bool = False
    ) -> Result:
        """Run this check over `tree` and collect what it finds.

        `about` names the skills the caller wants findings in, every one
        when empty. A per-skill check then reads only those of them the
        tree holds; any other check reads the whole tree, since what it
        says about one skill depends on the others. Nothing is filtered
        here: `Result.within` is the filter.

        `fast` reaches only a check that takes it. `controls` needs to
        know whether this is a `--fast` run, because it re-runs the
        check each control owns and a control on a slow check would
        drag the whole toolchain into a run that asked to skip it.
        """
        wanted = {s.name for s in tree} & set(about)
        read = tree.only(wanted) if wanted and self.reads_one_skill else tree
        found = self.fn(read, fast=fast) if self.wants("fast") else self.fn(read)
        return Result(self.name).extend(found)


REGISTRY: list[Check] = []


def check[F: Callable[..., Iterable[Finding]]](
    name: str,
    label: str,
    *,
    slow: bool = False,
    needs: tuple[str, ...] = (),
) -> Callable[[F], F]:
    """Register the decorated check of the tree as `name`, unchanged.

    A check of one skill is lifted first: `@check(...)` above
    `@per_skill`.
    """

    def wrap(fn: F) -> F:
        REGISTRY.append(Check(name, label, fn, slow, needs))
        return fn

    return wrap


#: Every module that defines checks. Importing one is what registers its
#: checks.
MODULES = (
    "anatomy",
    "assets",
    "citations",
    "controls",
    "conventions",
    "crossref",
    "dialect",
    "documented",
    "frontmatter",
    "layout",
    "lints",
    "markers",
    "mirror",
    "pins",
    "plugin",
    "prose",
    "selfapply",
    "sensitivity",
    "shared",
    "skeleton",
    "toolchain",
)


def all_checks() -> list[Check]:
    """Every check, once each module that defines one is imported."""
    for module in MODULES:
        importlib.import_module(f"agent_skill.checks.{module}")
    return REGISTRY


def by_name(name: str) -> Check | None:
    """The registered check called `name`, or None if there is none."""
    return next((c for c in all_checks() if c.name == name), None)
