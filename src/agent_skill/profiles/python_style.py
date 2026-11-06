"""python-style: its own `[M]` rules, applied to examples and prose."""

import re
lazy from collections.abc import Iterator

from agent_skill.lang.python import LANGUAGE, PYTHON_STYLE
from agent_skill.profiles.record import Mirror, NotDecisive, Profile
from agent_skill.report import Finding, Level, declare, fail
lazy from agent_skill.model import Skill, prose_lines

# The branches of `conventions` and of `prose` this standard's own rules
# fire through.
FUTURE = declare("conventions", "ps_future", Level.FAIL)
AUGMENTED = declare("conventions", "ps_augmented", Level.FAIL)
META_DOC = declare("conventions", "ps_meta_doc", Level.FAIL)
FUTURE_PROSE = declare("prose", "ps_future", Level.FAIL)

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


def conventions(skill: Skill) -> Iterator[Finding]:
    """python-style's own rules, applied to its own examples."""
    for b in skill.advice(LANGUAGE.fence):
        for j, raw in enumerate(b.lines):
            where = b.where_at(j)
            code = LANGUAGE.uncommented(raw)

            if FUTURE_ANNOTATIONS.match(code):
                yield fail(
                    "`from __future__ import annotations` degrades `annotationlib` "
                    "VALUE and FORWARDREF to bare strings; PEP 563 is Superseded",
                    where,
                    FUTURE,
                )

            if AUGMENTED_ON_SHARED.match(code):
                yield fail(
                    "augmented assignment on instance state is a "
                    "read-modify-write; under free threading it loses updates "
                    "(PS-CONC)",
                    where,
                    AUGMENTED,
                )

            if raw.lstrip().startswith('"""') and META.search(raw):
                yield fail(
                    "docstring discusses the example rather than the API",
                    where,
                    META_DOC,
                )


def prose(skill: Skill) -> Iterator[Finding]:
    """The standard must not recommend a spelling it forbids.

    `from __future__ import annotations` is banned outright, so prose
    naming it is either hunting it (inside a `**Check:**`) or is the
    rule that bans it. Anything else is the standard teaching the thing
    it exists to stop — which is how three passages survived the same
    rule being tightened in `zig-style`. Scoped per rule and per Check
    block, because both wrap.
    """
    span = re.compile(r"__future__")
    # A table row is the standard's own dead-API listing, and a line
    # already calling the spelling stale, superseded or forbidden is the
    # rule doing its job. What is left is prose that names it without
    # condemning it.
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
                    chapter.where(i, rid),
                    FUTURE_PROSE,
                )


PROFILE = Profile(
    name="python-style",
    prefix="PS",
    languages=("python",),
    # `pyproject.toml`, `ruff.toml`, `ty.toml` and `pytest.toml`
    # examples carry markers too, and were invisible to every tool
    # while the marked set was derived from the fence tag alone.
    marked_languages=("toml",),
    tools=("python", "ty", "ruff"),
    language="Python",
    verified_as="runs as written on free-threaded CPython {pin}",
    strict_scope="library and high-reliability",
    toolchain=PYTHON_STYLE,
    # Compared with rust-style for tier, as every standard is.
    mirror=Mirror("rust-style"),
    # Each snippet is the defect its rule forbids, written the way it
    # appears in real code rather than tailored to the pattern — a
    # fixture shaped to match proves the fixture, not the pattern.
    fires={
        "PS-API-05": ("from acmewidget._internal import helper",),
        "PS-ASYNC-01": ("loop = asyncio.new_event_loop()",),
        "PS-ASYNC-02": ("loop = asyncio.get_event_loop()",),
        "PS-ASYNC-03": ("task = asyncio.create_task(worker())",),
        # The pattern carried a stray space for as long as it
        # shipped, and matched nothing; this is the line it was
        # written to find.
        "PS-MIG-06": ("if json.__version__ < (2, 0):",),
    },
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=frozenset(
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
    ),
    not_decisive={
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
            "a presence assertion: the finding is an absence, which no hit can show",
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
    },
    conventions=conventions,
    prose=prose,
)
