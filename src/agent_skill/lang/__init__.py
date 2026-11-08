"""Turning a skill's examples back into code a compiler will accept.

The markdown is the source of truth, not a crate kept alongside it. The
previous apparatus inverted that: examples lived in a crate, were
injected into the markdown, and a block deleted from the markdown left
an orphan module the orphan check could not see. Extracting in this
direction makes that state unreachable.

A toolchain is a pair of maps and the commands between them: `extract`
writes each `verified` block to a file of its own, and `restore` reads
every block back, so `restore ∘ extract` is the identity on block
bodies. What runs in between, and with what policy, is the driver's
(`checks.toolchain`), and `fmt` is `restore ∘ format ∘ extract`: no
toolchain verifies, mutates or formats with code of its own.

Each toolchain's module is also where everything else the harness knows
about that language lives, so no check outside `lang/` names one: how it
is read, which tools decide its `Decided by tools` rows and at which
levels, how its pins are compared, and what it asks of a shipped asset.
A check asks the toolchain the skill's profile names, through
`toolchain_for`.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol
lazy from collections.abc import Callable, Iterable, Iterator, Mapping
lazy from pathlib import Path

from agent_skill.model import Block, located
from agent_skill.proc import run
from agent_skill.report import fail
from agent_skill.text import code_only, strip_comment
lazy from agent_skill.ids import Branch, Location, Version
lazy from agent_skill.lang import python, rust, zig
lazy from agent_skill.model import Skill
lazy from agent_skill.proc import Ran
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

    The last three fields are the vocabulary of the one grammar a
    mutant is drawn from (`deletable`).
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
    #: Body-line indices that each hold one whole statement, for a
    #: language whose statements do not end in a terminator; None for
    #: one whose lines are read for `;` (`terminated`).
    statements: Callable[[str], set[int]] | None = None
    #: What opens a statement no mutant deletes: a declaration or a
    #: binding, whose deletion only stops the build; an assertion, which
    #: earns its place on the path the tests do not reach; a brace.
    kept: tuple[str, ...] = ()

    def uncommented(self, line: str) -> str:
        """`line` without its comment, as this language spells one."""
        return strip_comment(line, self.comment, self.quotes)

    def code(self, body: str) -> str:
        """`body` with every comment removed and the line count kept."""
        return code_only(body, self.comment, self.quotes)

    def whole(self, body: str) -> set[int]:
        """Body-line indices that each hold one whole statement."""
        if self.statements is not None:
            return self.statements(body)
        return terminated(self, body)


#: Each bracket that closes, and the one it closes.
_CLOSES = {")": "(", "]": "[", "}": "{"}


def terminated(language: Language, body: str) -> set[int]:
    """Lines whose code ends in `;` and opens no bracket it leaves open.

    A whole statement, in a language that ends one with `;`. A line that
    closes what an earlier one opened (`));`) is the tail of a
    statement, and deleting it can only stop the build.
    """
    whole: set[int] = set()
    for i, line in enumerate(body.split("\n")):
        code = language.uncommented(line).strip()
        if code.endswith(";") and _balanced(unquoted(code, language.quotes)):
            whole.add(i)
    return whole


def unquoted(code: str, quotes: str) -> str:
    """`code` with every string's contents taken out."""
    out: list[str] = []
    i, opener = 0, ""
    while i < len(code):
        c = code[i]
        if opener:
            if c == "\\":
                i += 2
                continue
            if c == opener:
                opener = ""
        elif c in quotes:
            opener = c
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _balanced(code: str) -> bool:
    """Does every bracket `code` opens close in it, in order?"""
    stack: list[str] = []
    for c in code:
        if c in "([{":
            stack.append(c)
        elif c in _CLOSES and (not stack or stack.pop() != _CLOSES[c]):
            return False
    return not stack


def deletable(language: Language, body: str) -> Iterator[tuple[int, str]]:
    """Each line of `body` a mutant deletes, and the statement on it.

    One grammar for every language, in that language's vocabulary: a
    line holding one whole statement, outside the block's tests, that
    no word the language keeps opens. There were three: Python mutated
    only a line holding `=`, its tests' lines included; Rust only what
    came before a module's first `#[cfg(test)]`, its assertions
    included; Zig a line ending in `;` unless a comment followed it.
    """
    lines = body.split("\n")
    for i in sorted(language.whole(body) - language.tests(body)):
        code = language.uncommented(lines[i]).strip()
        if code and not code.startswith(language.kept):
            yield i, code


@dataclass(frozen=True, slots=True)
class Unit:
    """One extracted block: the file it is written to, and the block.

    A file in every language, holding one block, whose body line `i` is
    the file's line `i`: a harness line goes after a body, never before
    it. That is what puts a finding about a line of the file — a
    diagnostic, a mutant — on the markdown line it came from.
    """

    path: Path
    block: Block

    @property
    def where(self) -> Location:
        """The block's first body line, under its rule."""
        return self.block.where

    def where_at(self, offset: int) -> Location:
        """Line `offset` of the unit's file, in the markdown.

        A line past the body is the harness's own, which no markdown
        line holds; it is placed at the block.
        """
        inside = 0 <= offset < self.block.body.count("\n")
        return self.block.where_at(offset if inside else 0)


@dataclass
class Extraction:
    """A skill's examples, written where a toolchain can build them.

    `root` is the build context every step runs in: the crate a Rust
    module file is compiled in, the directory a Python or Zig file is
    run from.
    """

    root: Path
    skill: Skill
    units: list[Unit] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Whether any block was extracted at all."""
        return bool(self.units)

    @property
    def where(self) -> Location:
        """The skill, for a finding about the extraction as a whole."""
        return located(self.skill.name)

    def unit_at(self, path: Path) -> Unit | None:
        """The unit written to `path`, if any is."""
        resolved = path.resolve()
        return next((u for u in self.units if u.path.resolve() == resolved), None)


def first_error(ran: Ran) -> str:
    """The line of a failed run's output that says what went wrong.

    The first line that names an error or a formatting diff, else the
    start of the output, and the exit status when there was no output
    at all.
    """
    said = (ran.err or ran.out).strip()
    lines = said.split("\n")
    first = next(
        (ln for ln in lines if ln.lstrip().startswith(("error", "Diff"))), said[:120]
    )
    return first.strip() or f"exited {ran.rc} and said nothing"


@dataclass(frozen=True, slots=True)
class Step:
    """One command a toolchain runs over its extraction.

    Data, so the policy of running one is stated once, in the driver:
    a step that times out or fails is a failure naming the step.
    """

    #: what the step is called in a finding: `clippy`, `tests`
    name: str
    cmd: tuple[str, ...]
    cwd: Path
    timeout: float
    env: Mapping[str, str] = field(default_factory=dict)
    #: The unit the step runs, or None for one over the whole
    #: extraction: a failure it cannot place lies there.
    unit: Unit | None = None
    #: whether the tool prints `file:line:col: message`, so a failure
    #: is placed at each line it names
    diagnostics: bool = False
    #: what the tool said, read from a failed run's output
    said: Callable[[Ran], str] = first_error


def execute(step: Step, timeout: float | None = None) -> Ran:
    """Run `step` in its own time, or in `timeout` when one is given."""
    return run(
        list(step.cmd),
        cwd=step.cwd,
        timeout=step.timeout if timeout is None else timeout,
        env=dict(step.env),
    )


#: `path:line:col: message`, as a compiler, a linter or a type checker
#: names the line it means.
DIAGNOSTIC = re.compile(r"^(?P<file>[^:\s][^:]*):(?P<line>\d+):\d+:\s*(?P<rest>.+)$")

#: What opens a diagnostic that points at context rather than a defect:
#: the declaration an error refers to, or a suggested fix.
CONTEXT = ("note:", "help:")


def judged(
    step: Step, ran: Ran, ex: Extraction, *, failed: Branch, timeout: Branch
) -> list[Finding]:
    """What one run of `step` says, by the policy every step is held to.

    A step that did not finish in its time is a failure: nothing was
    verified, which is not a pass. There were four wordings for that —
    a message, a message, an empty `compiles: `, and a `zig fmt
    --check` that timed out and passed. A step that exits 0 in its time
    passed, whatever it printed. One that failed is a failure at each
    line of a unit the tool names, when it names lines, and otherwise
    one at what the step ran, with what the tool said first.
    """
    where = step.unit.where if step.unit is not None else ex.where
    if ran.timed_out:
        return [
            fail(f"{step.name} did not finish in {step.timeout:g}s", where, timeout)
        ]
    if ran.ok:
        return []
    named = list(_named(step, ran, ex, failed)) if step.diagnostics else []
    return named or [fail(f"{step.name}: {step.said(ran)[:120]}", where, failed)]


def _named(step: Step, ran: Ran, ex: Extraction, branch: Branch) -> Iterator[Finding]:
    """Each diagnostic `ran` printed, at the markdown line it names."""
    for line in f"{ran.out}\n{ran.err}".split("\n"):
        m = DIAGNOSTIC.match(line.strip())
        if m is None or m["rest"].startswith(CONTEXT):
            continue
        unit = ex.unit_at(step.cwd / m["file"])
        if unit is not None:
            said = m["rest"].strip()[:120]
            yield fail(
                f"{step.name}: {said}", unit.where_at(int(m["line"]) - 1), branch
            )


class Toolchain(Protocol):
    """What a language must provide for its examples to be verified.

    Data and the maps between markdown and files. Running is the
    driver's: one policy for every step, one grammar for every mutant,
    one composition for `fmt`.
    """

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
    #: how long one mutant's tests may run before it is inconclusive
    mutant_timeout: float
    #: What in a block's code means it reaches outside the directory it
    #: runs in, so it may not be `verified`; None for a toolchain that
    #: asks nothing of the kind.
    outside: re.Pattern[str] | None

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
        """Write each of `skill`'s verified blocks under `out`."""
        ...

    def restore(self, ex: Extraction) -> Mapping[Block, str]:
        """Each extracted block's body, read back from its file."""
        ...

    def steps(self, ex: Extraction) -> Iterable[Step]:
        """What verifies the extraction: compile, lint, test."""
        ...

    def formatter(self, ex: Extraction) -> Step:
        """What rewrites every unit's file as the formatter would."""
        ...

    def tests(self, ex: Extraction, unit: Unit) -> Step | None:
        """What runs `unit`'s tests; None when they cannot run here."""
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

    def probe(
        self, skill: Skill, spelling: str, out: Path, since: Version | None = None
    ) -> Step | None:
        """What looks `spelling` up in the release `skill` is pinned to.

        A step that exits 0 when the release still provides it and 1
        when it does not, any file it needs written under `out` and any
        cache it fills kept there; None for a spelling this toolchain
        cannot look up. `since` is the row's Since: an edition, where
        the language has them, is what made the change, and so what
        the spelling is compiled under. A migration row marked `gone` is
        verified by it (normalize-the-standards, decision 9), and the
        driver runs it.
        """
        ...

    def excused(self, skill: Skill) -> Mapping[str, str]:
        """What `skill`'s examples are excused from of what it ships.

        Each lint code a fenced snippet cannot satisfy, with the reason
        (normalize-the-standards, decision 12); a reason left out fails
        the run, as any exemption without one does.
        """
        ...

    def configured(self, skill: Skill) -> Mapping[tuple[str, str], str]:
        """Each lint `skill`'s shipped configuration sets one by one.

        As a `Decided by tools` row names it — its tool, then the lint —
        and the level it is set to, as a row states one. A group, or a
        selection of everything, sets nothing one by one, and a compiler
        ships no configuration. A row is owed to each set at a level
        that fails a run (normalize-the-standards, decision 8).
        """
        ...


def extracted(skill: Skill, language: Language) -> list[Block]:
    """The blocks a toolchain extracts: every `verified` one, anywhere.

    `SKILL.md` included. Rust used to skip a block above every rule
    heading, which is where `SKILL.md` keeps its examples, while Zig
    compiled one; a `verified` marker is a claim wherever it stands.
    """
    return skill.blocks(language.fence, verified=True)


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
