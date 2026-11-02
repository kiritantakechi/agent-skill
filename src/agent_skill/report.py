"""What a check produces, and how it is shown.

A check returns findings. It does not print and it does not exit, so the
same function backs a command-line report, a pytest assertion, and a
negative control that asserts the check *can* fail.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import override
lazy from collections.abc import Collection, Iterable

lazy from agent_skill.ids import Branch, Location


class Level(Enum):
    """A finding blocks, informs, or says that the check could not look.

    The third one was added because a check that cannot run looks
    exactly like a check that passes, and the repository has already
    paid for that twice: a zig probe that reported 375 symbols present
    including a fake one, and clippy reported clean because it exits 0
    on a warning. `UNRUN` blocks like `FAIL` but reads differently,
    because "there is a defect here" and "nobody looked" call for
    different actions.
    """

    FAIL = "FAIL"
    UNRUN = "unrun"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing a check found: its level, message, location and branch.

    `branch` is the place in the check that said it, so a negative
    control can assert that its own branch fired rather than any branch
    of the same check. `where` is printed by `Location`'s one printer.
    """

    level: Level
    message: str
    where: Location
    branch: Branch

    @override
    def __str__(self) -> str:
        """The message, led by `where` when it names anything."""
        where = str(self.where)
        return f"{where}: {self.message}" if where else self.message


def fail(message: str, where: Location, branch: Branch) -> Finding:
    """A defect: the finding that blocks the pass."""
    return Finding(Level.FAIL, message, where, branch)


def unrun(message: str, where: Location, branch: Branch) -> Finding:
    """The check could not be performed.

    Not a pass, and not a defect either.
    """
    return Finding(Level.UNRUN, message, where, branch)


def note(message: str, where: Location, branch: Branch) -> Finding:
    """Something worth saying that does not block the pass."""
    return Finding(Level.NOTE, message, where, branch)


@dataclass(slots=True)
class Result:
    """One check's output: its findings and its details.

    The details are what the check wants to say about scale.
    """

    name: str
    findings: list[Finding] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def fails(self) -> list[Finding]:
        """The findings that name a defect."""
        return [f for f in self.findings if f.level is Level.FAIL]

    @property
    def unrun(self) -> list[Finding]:
        """The findings that say the check could not look."""
        return [f for f in self.findings if f.level is Level.UNRUN]

    @property
    def notes(self) -> list[Finding]:
        """The findings that only inform."""
        return [f for f in self.findings if f.level is Level.NOTE]

    @property
    def ok(self) -> bool:
        """Green means every check ran and every one of them passed.

        Work that could not be done is not work that succeeded, so
        `UNRUN` withholds the pass exactly as `FAIL` does.
        """
        return not self.fails and not self.unrun

    def extend(self, findings: Iterable[Finding]) -> Result:
        """Add `findings`, and return this result so calls can chain."""
        self.findings.extend(findings)
        return self

    def within(self, skills: Collection[str]) -> Result:
        """Only the findings in one of `skills`, or in no skill at all.

        A finding in no skill is about the repository or the run, so no
        selection of skills leaves it out.
        """
        kept = [f for f in self.findings if f.where.skill in {None, *skills}]
        return Result(self.name, kept, list(self.details))
