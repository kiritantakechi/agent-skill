"""The check registry.

Every check is a function of the parsed skills that yields findings. It prints
nothing and exits nothing, so the command line, pytest, and the negative controls
all drive the same code.
"""

from __future__ import annotations

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

    def run(self, skills) -> Result:
        result = Result(self.name)
        if self.scope == "all":
            result.extend(self.fn(skills))
        else:
            for skill in skills:
                result.extend(self.fn(skill))
        return result


REGISTRY: list[Check] = []


def check(name: str, label: str, *, scope: str = "skill", slow: bool = False):
    def wrap(fn):
        REGISTRY.append(Check(name, label, fn, scope, slow))
        return fn

    return wrap


def all_checks() -> list[Check]:
    from . import (  # noqa: F401  (registration by import)
        anatomy,
        assets,
        controls,
        conventions,
        frontmatter,
        layout,
        lints,
        markers,
        mirror,
        prose,
        selfapply,
        toolchain,
    )

    return REGISTRY


def by_name(name: str) -> Check | None:
    return next((c for c in all_checks() if c.name == name), None)
