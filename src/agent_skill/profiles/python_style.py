"""python-style: its own `[M]` rules, applied to examples and prose."""

import re
from dataclasses import dataclass, field
from typing import override
lazy from collections.abc import Iterable

from agent_skill.profiles import NotDecisive, Profile, register
from agent_skill.report import Finding, fail
from agent_skill.text import group, strip_comment, syntax_for
lazy from agent_skill.lang.python import INTERPRETER
lazy from agent_skill.model import Skill, prose_lines

#: PS-TYPE — PEP 563 is Superseded, and the future import does not
#: merely fail to help on 3.14+: it silently degrades `annotationlib`
#: `VALUE` and `FORWARDREF` to bare strings, so a library reading
#: annotations gets text it must `eval`.
FUTURE_ANNOTATIONS = re.compile(r"^\s*from\s+__future__\s+import\s+.*\bannotations\b")

#: PS-CONC — the GIL made a read-modify-write on shared state *unlikely*
#: to interleave rather than atomic. Free-threading removes the luck,
#: not a guarantee: eight threads lose roughly three quarters of the
#: updates.
AUGMENTED_ON_SHARED = re.compile(
    r"^\s*(?:self|cls)\.\w+\s*(?:[+\-*/|&^]|//|\*\*|>>|<<)="
)

#: A docstring inside an example documents the API, not the standard.
META = re.compile(
    r"\b(this example|this rule|the snippet|as shipped|the block|"
    r"for the purposes of)\b",
    re.IGNORECASE,
)


def _inside_tests(body: str) -> set[int]:
    """Body-line indices inside a `def test_*` function, by indentation.

    Python has no block delimiter to count, so the end of a test is the
    next line at or below the `def`'s own indentation that is not blank.
    """
    inside: set[int] = set()
    lines = body.split("\n")
    depth: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if depth is not None:
            if stripped and indent <= depth:
                depth = None
            else:
                inside.add(i)
                continue
        if re.match(r"^\s*(?:async\s+)?def\s+test_", line):
            depth, _ = indent, inside.add(i)
    return inside


@dataclass
class PythonStyle(Profile):
    """What python-style's checks need to know about it."""

    name: str = "python-style"
    prefix: str = "PS"
    languages: tuple[str, ...] = ("python",)
    #: `pyproject.toml`, `ruff.toml`, `ty.toml` and `pytest.toml`
    #: examples carry markers too, and were invisible to every tool
    #: while the marked set was derived from the fence tag alone.
    marked_languages: tuple[str, ...] = ("toml",)
    tools: tuple[str, ...] = ("python", "ty", "ruff")
    language: str = "Python"
    verified_as: str = "runs as written on free-threaded CPython {pin}"
    strict_scope: str = "library and high-reliability"
    toolchain: str = "python"
    #: Each snippet is the defect its rule forbids, written the way it
    #: appears in real code rather than tailored to the pattern — a
    #: fixture shaped to match proves the fixture, not the pattern.
    fires: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "PS-API-05": ("from acmewidget._internal import helper",),
            "PS-ASYNC-01": ("loop = asyncio.new_event_loop()",),
            "PS-ASYNC-02": ("loop = asyncio.get_event_loop()",),
            "PS-ASYNC-03": ("task = asyncio.create_task(worker())",),
            # The pattern carried a stray space for as long as it
            # shipped, and matched nothing; this is the line it was
            # written to find.
            "PS-MIG-06": ("if json.__version__ < (2, 0):",),
        }
    )
    #: Each of these ships an `rg` pattern that no fixture in `fires`
    #: proves yet. Giving one a fixture means deleting it here, which
    #: `sensitivity` insists on, so the list only shrinks.
    unproven: frozenset[str] = frozenset(
        {
            "PS-API-16",
            "PS-ASYNC-04",
            "PS-ASYNC-05",
            "PS-ASYNC-13",
            "PS-ASYNC-14",
            "PS-ASYNC-15",
            "PS-ASYNC-18",
            "PS-BUILD-03",
            "PS-BUILD-04",
            "PS-BUILD-09",
            "PS-BUILD-12",
            "PS-BUILD-14",
            "PS-BUILD-21",
            "PS-CONC-02",
            "PS-CONC-03",
            "PS-CONC-05",
            "PS-CONC-07",
            "PS-CONC-08",
            "PS-CONC-10",
            "PS-CONC-12",
            "PS-CONC-13",
            "PS-CONC-15",
            "PS-CONC-16",
            "PS-CONC-18",
            "PS-CONC-19",
            "PS-CONC-20",
            "PS-CONC-21",
            "PS-CONC-22",
            "PS-DATA-01",
            "PS-DATA-02",
            "PS-DATA-03",
            "PS-DATA-09",
            "PS-DATA-12",
            "PS-DATA-13",
            "PS-DATA-17",
            "PS-DOC-04",
            "PS-DOC-08",
            "PS-DOC-12",
            "PS-ERR-14",
            "PS-MIG-04",
            "PS-MIG-05",
            "PS-NAME-02",
            "PS-NAME-03",
            "PS-NAME-11",
            "PS-OUT-02",
            "PS-OUT-03",
            "PS-OUT-07",
            "PS-OUT-10",
            "PS-OUT-12",
            "PS-OUT-13",
            "PS-OUT-15",
            "PS-OUT-18",
            "PS-PERF-02",
            "PS-PERF-06",
            "PS-PERF-07",
            "PS-TEST-01",
            "PS-TEST-08",
            "PS-TEST-15",
            "PS-TEST-16",
            "PS-TEST-18",
            "PS-TEST-19",
            "PS-TYPE-04",
            "PS-TYPE-05",
            "PS-TYPE-11",
            "PS-TYPE-12",
            "PS-TYPE-14",
            "PS-TYPE-20",
        }
    )
    not_decisive: dict[str, NotDecisive] = field(
        default_factory=lambda: {
            # Each anchor is a literal fragment of that rule's own
            # **Check:**, so rewriting the rule cannot leave a stale
            # entry quietly suppressing its pattern. Every one of these
            # finds the shape; something the pattern cannot see decides
            # whether the shape is a defect.
            "PS-CONC-02": NotDecisive(
                "read each hit",
                "the pattern finds every compound assignment; whether the target is "
                "reachable from a second thread decides, and a lock or a local "
                "accumulator makes it compliant",
            ),
            "PS-CONC-03": NotDecisive(
                "unless a lock spans both",
                "the pattern finds the test; whether a lock spans the test and the "
                "write decides",
            ),
            "PS-CONC-18": NotDecisive(
                "any hit whose preceding lines are inside",
                "the pattern finds every ContextVar; the scope it is created in "
                "decides, which a line-oriented pattern cannot see",
            ),
            "PS-CONC-19": NotDecisive(
                "whose value was set outside it",
                "the pattern finds every context read; passing the context explicitly "
                "is the compliant form and matches the same pattern",
            ),
            "PS-TEST-18": NotDecisive(
                "sleep\\(' tests/",
                "scoped to the test suite: `await asyncio.sleep(...)` in ordinary "
                "code is correct, and the pattern cannot see which tree it is in",
            ),
            "PS-DOC-04": NotDecisive(
                "a parenthesised type is the",
                "the pattern finds any indented name followed by a parenthesis, which "
                "matches ordinary prose as readily as a docstring type",
            ),
            "PS-ASYNC-03": NotDecisive(
                "every hit outside a `TaskGroup`",
                "the pattern finds every task start; being inside a `TaskGroup` is "
                "what makes it compliant, and the pattern cannot see the block",
            ),
            "PS-ERR-14": NotDecisive(
                "each hit that only releases a resource",
                "the pattern finds every `finally`; the one inside a `@contextmanager` "
                "is how a context manager is implemented, not a call site that "
                "should have used one",
            ),
            "PS-DATA-09": NotDecisive(
                "inside class bodies",
                "the pattern finds every call on the right of an assignment; being "
                "inside a class body is what makes it a default, which the pattern "
                "cannot see",
            ),
            # Polarity: this Check asserts the shape is *present*, so
            # its hits are evidence of compliance and reading them as
            # defects inverts the rule.
            "PS-DATA-12": NotDecisive(
                "should be roughly as common as",
                "a presence assertion: the finding is an absence, which no hit can "
                "show",
            ),
            "PS-DATA-13": NotDecisive(
                "every hit is a place a `frozendict` would fail",
                "the rule's own example demonstrates the failing test deliberately, "
                "and a hit in application code is a candidate until the value's "
                "type is known",
            ),
            "PS-DATA-01": NotDecisive(
                "needs a reason on the line above it",
                "the pattern finds every dataclass; the `frozen=True` argument "
                "decides, and a frozen one matches the same pattern",
            ),
            "PS-DATA-02": NotDecisive(
                "read for `slots=`",
                "the pattern finds every dataclass; the `slots=` argument decides",
            ),
            "PS-NAME-11": NotDecisive(
                "read each hit for what",
                "the pattern finds every indented import; what encloses it decides, "
                "and an `if TYPE_CHECKING:` block is indented too",
            ),
            "PS-CONC-12": NotDecisive(
                "read what the target closes over",
                "the pattern finds every thread start; what the target closes over "
                "decides, and starting a thread is not itself a defect",
            ),
            "PS-CONC-20": NotDecisive(
                "inside any thread target",
                "the pattern finds every `print`; the calling thread decides, and a "
                "module-level print is not a hit",
            ),
            "PS-CONC-22": NotDecisive(
                "applied to a `def` containing `yield`",
                "the pattern finds every `@contextmanager`; what it decorates decides, "
                "and the `with` form the rule recommends matches too",
            ),
        }
    )

    @override
    def pin(self) -> str:
        """The interpreter's version.

        Read from the uv key the harness installs.
        """
        return group(re.match(r"cpython-([0-9][^+]*)", INTERPRETER))

    @override
    def conventions(self, skill: Skill) -> Iterable[Finding]:
        """python-style's own rules, applied to its own examples."""
        comment, quotes = syntax_for("python")
        for b in skill.advice("python"):
            for j, raw in enumerate(b.lines):
                where = f"{b.file}:{b.at(j)} [{b.rule}]"
                code = strip_comment(raw, comment, quotes)

                if FUTURE_ANNOTATIONS.match(code):
                    yield fail(
                        "`from __future__ import annotations` degrades `annotationlib` "
                        "VALUE and FORWARDREF to bare strings; PEP 563 is Superseded",
                        where,
                    )

                if AUGMENTED_ON_SHARED.match(code):
                    yield fail(
                        "augmented assignment on instance state is a "
                        "read-modify-write; under free threading it loses updates "
                        "(PS-CONC)",
                        where,
                    )

                if raw.lstrip().startswith('"""') and META.search(raw):
                    yield fail(
                        "docstring discusses the example rather than the API", where
                    )

    @override
    def inside_tests(self, body: str) -> set[int]:
        """Body-line indices inside a `def test_*`, by indentation."""
        return _inside_tests(body)

    @override
    def prose(self, skill: Skill) -> Iterable[Finding]:
        """The standard must not recommend a spelling it forbids.

        `from __future__ import annotations` is banned outright, so
        prose naming it is either hunting it (inside a `**Check:**`) or
        is the rule that bans it. Anything else is the standard teaching
        the thing it exists to stop — which is how three passages
        survived the same rule being tightened in `zig-style`. Scoped
        per rule and per Check block, because both wrap.
        """
        span = re.compile(r"__future__")
        # A table row is the standard's own dead-API listing, and a line
        # already calling the spelling stale, superseded or forbidden is
        # the rule doing its job. What is left is prose that names it
        # without condemning it.
        condemned = re.compile(
            r"\b(stale|superseded|forbidden|deprecat|never|no longer|degrade|"
            r"wrong|dead|remove)",
            re.IGNORECASE,
        )
        for chapter in skill.chapters:
            for i, line, rid, in_check in prose_lines(chapter.text, skill.prefix):
                if in_check or line.lstrip().startswith("|") or condemned.search(line):
                    continue
                if span.search(line):
                    yield fail(
                        "prose names `__future__` outside a **Check:** without saying "
                        "it is forbidden",
                        f"{chapter.name}:{i} [{rid}]",
                    )


register(PythonStyle())
