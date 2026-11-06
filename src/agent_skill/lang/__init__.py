"""Turning a skill's examples back into code a compiler will accept.

The markdown is the source of truth, not a crate kept alongside it. The
previous apparatus inverted that: examples lived in a crate, were
injected into the markdown, and a block deleted from the markdown left
an orphan module the orphan check could not see. Extracting in this
direction makes that state unreachable.

Each toolchain's module is also where everything else the harness knows
about that language lives, so no check outside `lang/` names one: how it
is read, which tools decide its `Decided by tools` rows and at which
levels, how its pins are compared, what it asks of a shipped asset, and
how `fmt` writes a block back. A check asks the toolchain the skill's
profile names, through `toolchain_for`.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol
lazy from collections.abc import Callable, Iterable, Mapping
lazy from pathlib import Path

from agent_skill.ids import Branch, Location
from agent_skill.model import located
from agent_skill.report import fail, note
from agent_skill.text import code_only, strip_comment
lazy from agent_skill.lang import python, rust, zig
lazy from agent_skill.model import Skill
lazy from agent_skill.report import Finding

if TYPE_CHECKING:
    # Not `lazy`: `dataclass` evaluates field annotations as the class
    # is built, and reifying this one then would import `rust`, which
    # imports this package before `Extraction` exists.
    from agent_skill.lang.python import PythonSnippet
    from agent_skill.lang.rust import RustCrate
    from agent_skill.lang.zig import ZigBuild

#: How one skill's examples are built: the toolchain it names, and that
#: toolchain's settings for this skill.
type Config = PythonSnippet | RustCrate | ZigBuild


def no_tests(body: str) -> set[int]:  # noqa: ARG001 — the language marks no test
    """No line: the harness reads no test in this language."""
    return set()


@dataclass(frozen=True, slots=True)
class Language:
    """How the harness reads a fence's language: comments, files, tests.

    Declared beside the toolchain that compiles it, because each is a
    fact about the language. Python's comment is `#`, and `//` is floor
    division there; in Rust `'` opens a lifetime rather than a string;
    a Python test is a `def test_*` by indentation and a Zig test a
    `test` block by its braces. A language no toolchain declares is
    read with the defaults.
    """

    fence: str
    #: what opens a line comment
    comment: str = "//"
    #: what delimits a string
    quotes: str = '"'
    #: what a file of it is named
    suffix: str = ".txt"
    #: body-line indices inside a test, for a rule scoped to test code
    tests: Callable[[str], set[int]] = no_tests

    def uncommented(self, line: str) -> str:
        """`line` without its comment, as this language spells one."""
        return strip_comment(line, self.comment, self.quotes)

    def code(self, body: str) -> str:
        """`body` with every comment removed and the line count kept."""
        return code_only(body, self.comment, self.quotes)


@dataclass(frozen=True, slots=True)
class Unit:
    """One extracted block, and where it came from."""

    path: Path
    chapter: str
    line: int
    rule: str
    skill: str | None = None  #: the skill whose markdown holds the block

    @property
    def where(self) -> Location:
        """The block's first body line, under its rule."""
        return self.where_at(0)

    def where_at(self, offset: int) -> Location:
        """Line `offset` of the extracted file, in its block."""
        return located(self.skill, self.chapter, self.line + offset, self.rule)


@dataclass
class Extraction:
    """A skill's examples, written where a toolchain can build them."""

    root: Path
    units: list[Unit] = field(default_factory=list)
    #: how the extracted crate is built; None for a toolchain that needs
    #: no manifest
    crate: RustCrate | None = None
    skill: str | None = None  #: the skill the examples were extracted from

    def __bool__(self) -> bool:
        """Whether any block was extracted at all."""
        return bool(self.units)

    @property
    def where(self) -> Location:
        """The skill, for a finding about the extraction as a whole."""
        return Location(self.skill)


class Toolchain(Protocol):
    """What a language must provide for its examples to be verified."""

    name: str
    tool: str
    language: Language
    #: what `missing` asks for
    needs: tuple[str, ...]
    #: each `Decided by tools` row's tool, and the levels at which it
    #: fails a run
    rows: Mapping[str, frozenset[str]]
    #: the row tools that are the compiler itself, so no configuration
    #: enables what their rows say
    compilers: frozenset[str]
    #: what `cite`, `pins` and `asset` ask for
    cites_with: tuple[str, ...]
    pins_with: tuple[str, ...]
    assets_with: tuple[str, ...]
    #: the shipped assets `asset` reads, by suffix
    asset_suffixes: tuple[str, ...]

    def missing(self) -> list[str]:
        """What this toolchain needs and cannot find.

        A `shutil.which` on one name answered for Rust and Zig, where
        one binary does everything. It cannot answer for a toolchain
        that needs an exact interpreter build plus two separate tools,
        and it cannot see an interpreter that is deliberately resolved
        through a version manager rather than through PATH.
        """
        ...

    def extract(self, skill: Skill, out: Path) -> Extraction:
        """Write `skill`'s verified blocks under `out`, to be built."""
        ...

    def verify(self, ex: Extraction) -> Iterable[Finding]:
        """Everything the toolchain rejects in the extracted blocks."""
        ...

    def mutate(self, ex: Extraction) -> Iterable[Finding]:
        """Statements the extracted blocks' tests do not pin."""
        ...

    def cite(self, skill: Skill) -> Iterable[Finding]:
        """Each row and citation the shipped assets do not enforce."""
        ...

    def pins(self, skill: Skill) -> Iterable[Finding]:
        """Each of `skill`'s pins that has fallen behind."""
        ...

    def asset(self, path: Path, where: Location) -> Iterable[Finding]:
        """What is wrong with a shipped asset of `asset_suffixes`."""
        ...

    def format(self, skill: Skill) -> list[Finding]:
        """Rewrite `skill`'s verified blocks as its formatter would."""
        ...


def timed_out(step: str, seconds: float, where: Location, branch: Branch) -> Finding:
    """A verification step that did not finish in its time: a failure.

    Nothing was verified, which is not a pass. One wording for every
    toolchain, because they had four: a message, a message, an empty
    `compiles: `, and a `zig fmt --check` that timed out and passed.
    """
    return fail(f"{step} did not finish in {seconds:g}s", where, branch)


def inconclusive(
    statement: str, where: Location, branch: Branch, *, extracted: str = ""
) -> Finding:
    """A mutant whose tests did not finish: neither killed nor survived.

    Deleting a loop increment turns a test into a hang, so a timeout is
    often the tests failing; but a busy machine times out too. Counted
    as killed, the run goes quiet under load and still reports clean,
    so it is said, in the same words, by every toolchain.

    `extracted` names the statement's line in the extracted source, for
    a toolchain that cannot yet trace it back to the markdown.
    """
    said = f"`{statement[:44]}` timed out — inconclusive: hung, or slow"
    return note(f"{extracted}: {said}" if extracted else said, where, branch)


def toolchains() -> tuple[Toolchain, ...]:
    """Every toolchain the harness can verify examples with."""
    return (python.PYTHON_TOOLCHAIN, rust.RUST, zig.ZIG)


def toolchain_for(config: Config | None) -> Toolchain | None:
    """The toolchain `config` sets up, or None for a skill with none."""
    match config:
        case python.PythonSnippet():
            return python.PYTHON_TOOLCHAIN
        case rust.RustCrate():
            return rust.RUST
        case zig.ZigBuild():
            return zig.ZIG
        case None:
            return None


def needs(tools: Callable[[Toolchain], tuple[str, ...]]) -> tuple[str, ...]:
    """What every toolchain asks for, once each, as `tools` reads it."""
    return tuple(dict.fromkeys(t for tc in toolchains() for t in tools(tc)))


def language(fence: str) -> Language:
    """The language a fence tag names, or one read with the defaults."""
    found = (tc.language for tc in toolchains() if tc.language.fence == fence)
    return next(found, Language(fence))


def comments() -> tuple[str, ...]:
    """Every token that opens a line comment in a declared language."""
    return tuple(dict.fromkeys(tc.language.comment for tc in toolchains()))
