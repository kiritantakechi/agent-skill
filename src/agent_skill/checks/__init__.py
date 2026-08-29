"""The check registry.

Every check is a function of the parsed skills that yields findings. It prints
nothing and exits nothing, so the command line, pytest, and the negative controls
all drive the same code.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..report import Finding, Result


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    label: str
    fn: Callable[..., Iterable[Finding]]
    scope: str = "skill"  #: "skill" — once per skill; "all" — once, over every skill
    slow: bool = False  #: needs cargo or zig
    #: External binaries without which this check cannot look.
    #:
    #: Declared rather than inferred, because inference cannot see an
    #: indirection: `pins` asks `have(tool)` in a loop over a tuple, so reading
    #: the source finds `uv` and misses `ruff`, `ty`, `pytest` and `rg`. The
    #: guarantee that a missing tool withholds the pass runs over what is
    #: declared here; `test_unrun` cross-checks it against what the source does
    #: name, so forgetting to declare one is a failure rather than a gap.
    needs: tuple[str, ...] = ()

    def wants(self, name: str) -> bool:
        """Does this check take that keyword?

        Asked of the function rather than answered by its name. The caller used
        to read `if c.name == "controls"`, which is a second place that has to
        learn about a check — and the wrong place, since the check's own
        signature already says so.
        """
        return name in inspect.signature(self.fn).parameters

    def run(self, skills, **kw) -> Result:
        """`kw` reaches only an "all"-scope check, and only the keywords it takes.

        `controls` needs to know whether this is a `--fast` run, because it
        re-runs the check each control owns and a control on a slow check would
        drag the whole toolchain into a run that asked to skip it.
        """
        result = Result(self.name)
        if self.scope == "all":
            result.extend(self.fn(skills, **{k: v for k, v in kw.items() if self.wants(k)}))
        else:
            for skill in skills:
                result.extend(self.fn(skill))
        return result


REGISTRY: list[Check] = []


def check(
    name: str,
    label: str,
    *,
    scope: str = "skill",
    slow: bool = False,
    needs: tuple[str, ...] = (),
):
    def wrap(fn):
        REGISTRY.append(Check(name, label, fn, scope, slow, needs))
        return fn

    return wrap


def all_checks() -> list[Check]:
    from . import (  # noqa: F401  (registration by import)
        anatomy,
        assets,
        citations,
        controls,
        conventions,
        crossref,
        dialect,
        documented,
        frontmatter,
        layout,
        lints,
        markers,
        mirror,
        pins,
        prose,
        selfapply,
        sensitivity,
        toolchain,
    )

    return REGISTRY


def by_name(name: str) -> Check | None:
    return next((c for c in all_checks() if c.name == name), None)
