"""The check registry.

Every check is a function of the parsed skills that yields findings. It
prints nothing and exits nothing, so the command line, pytest, and the
negative controls all drive the same code.
"""

import importlib
import inspect
from dataclasses import dataclass
lazy from collections.abc import Callable, Iterable

from agent_skill.report import Finding, Result
lazy from agent_skill.model import Skill


@dataclass(frozen=True, slots=True)
class Check:
    """A registered check: its name, its label, and what it runs."""

    name: str
    label: str
    fn: Callable[..., Iterable[Finding]]
    scope: str = "skill"  #: "skill" — once per skill; "all" — once, over every skill
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

    def run(self, skills: list[Skill], **kw: object) -> Result:
        """Run this check over `skills` and collect what it finds.

        `kw` reaches only an "all"-scope check, and only the keywords it
        takes. `controls` needs to know whether this is a `--fast` run,
        because it re-runs the check each control owns and a control on
        a slow check would drag the whole toolchain into a run that
        asked to skip it.
        """
        result = Result(self.name)
        if self.scope == "all":
            result.extend(
                self.fn(skills, **{k: v for k, v in kw.items() if self.wants(k)})
            )
        else:
            for skill in skills:
                result.extend(self.fn(skill))
        return result


REGISTRY: list[Check] = []


def check[F: Callable[..., Iterable[Finding]]](
    name: str,
    label: str,
    *,
    scope: str = "skill",
    slow: bool = False,
    needs: tuple[str, ...] = (),
) -> Callable[[F], F]:
    """Register the decorated function as check `name`, unchanged."""

    def wrap(fn: F) -> F:
        REGISTRY.append(Check(name, label, fn, scope, slow, needs))
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
