"""The harness's own pins: the tools whose version decides a check.

A skill's pins are its profile's, and its toolchain's. These pin the
repository instead: `ruff` decides what a citation of a ruff code means,
`rg` whether a pattern hit. They are declared in `pyproject.toml`
beside the package and read from there, so each version is written
once.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from agent_skill.ids import Location, Pin
from agent_skill.proc import tool_path


@dataclass(frozen=True, slots=True)
class Tool:
    """A binary the harness runs, and the distribution that ships it.

    The two are spelled differently for `rg`, which comes from
    `ripgrep-bin`; neither name derives from the other, and guessing
    produced a pin that found nothing and reported agreement.
    """

    binary: str
    #: "" when the distribution is spelled as the binary is
    distribution: str = ""

    @property
    def package(self) -> str:
        """The distribution's name, as a requirement spells it."""
        return self.distribution or self.binary


@dataclass(frozen=True, slots=True)
class Harness:
    """The tools the harness pins, and the file that pins them."""

    tools: tuple[Tool, ...]
    #: relative to the repository
    declared_in: str

    @property
    def where(self) -> Location:
        """The pins' file: a finding about one lies in no skill."""
        return Location(file=self.declared_in)

    @property
    def binaries(self) -> tuple[str, ...]:
        """Each pinned tool, as a command names it."""
        return tuple(t.binary for t in self.tools)

    def tool(self, binary: str) -> Tool:
        """The pinned tool `binary` runs, or one named as it is."""
        return next((t for t in self.tools if t.binary == binary), Tool(binary))


HARNESS = Harness(
    tools=(Tool("ruff"), Tool("ty"), Tool("pytest"), Tool("rg", "ripgrep-bin")),
    declared_in="pyproject.toml",
)


def declared_pins() -> str | None:
    """The file declaring the tool pins, or None when it cannot be read.

    It sits beside the package in the source tree and nowhere at all
    once the package is installed: `uv build --wheel` does not ship
    `pyproject.toml`. Reading it unguarded raised `FileNotFoundError`
    out of `searcher_problem`, so `agent-skill check` from an installed
    distribution died with a traceback instead of reporting — and
    `[project.scripts]` declares that entry point, so that is a
    supported way to run it.

    Not being able to read the pins is a complaint, not a crash and not
    a pass.
    """
    try:
        return (Path(__file__).resolve().parents[2] / HARNESS.declared_in).read_text()
    except OSError:
        return None


def pinned(binary: str) -> Pin | None:
    """The pin `pyproject.toml` declares for this tool, or None.

    Read rather than repeated, so it is declared once. A constant here
    and a pin there is two declarations that agree until someone edits
    one, which is the shape of every drift this repository has had to
    chase.
    """
    package = HARNESS.tool(binary).package
    text = declared_pins()
    if text is None:
        return None
    m = re.search(rf'"({re.escape(package)}==\d+\.\d+\.\d+)"', text)
    return Pin.parse(m.group(1)) if m else None


#: `ripgrep 15.2.0 (rev e89fff89ac)` -> `15.2.0`
_VERSION = re.compile(r"(\d+\.\d+\.\d+)")


def version_mismatch(binary: str, reported: str) -> str:
    """The complaint, if the binary that will run is not the one pinned.

    "" when it is.

    A standard claiming verification against a version the harness was
    not running is a false statement about work that was done. This is
    the check that makes the claim true rather than aspirational.

    An unfindable pin is itself the complaint. Returning "no mismatch"
    when the pin cannot be read is how the first version of this
    function reported that an unpinned `rg` agreed with a pin that did
    not exist.

    Two ways to be unfindable, told apart because they call for
    different things: a pin missing from a file that is there is
    something to add, and a file that is not there at all is how this
    runs when installed rather than checked out.
    """
    pin = pinned(binary)
    if pin is None:
        if declared_pins() is None:
            return (
                f"`{binary}` decides whether checks fire and no pin could be read: "
                "this is running from an installed distribution, which does not "
                f"carry `{HARNESS.declared_in}`, so nothing confirmed which version "
                "ran"
            )
        return (
            f"`{binary}` decides whether checks fire but `{HARNESS.declared_in}` "
            "pins no version for it"
        )
    want = str(pin.version)
    got = _VERSION.search(reported)
    if got and got.group(1) == want:
        return ""
    saw = got.group(1) if got else repr(reported.strip()[:40])
    return f"`{binary}` is pinned to {want} but {tool_path(binary)} reports {saw}"
