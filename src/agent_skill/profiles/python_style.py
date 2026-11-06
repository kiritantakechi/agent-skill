"""python-style: its own `[M]` rules, applied to examples and prose."""

from agent_skill.lang.python import PYTHON_STYLE
from agent_skill.profiles.record import (
    LineRule,
    Mirror,
    Near,
    NotDecisive,
    Profile,
    Unless,
    keyed,
    rules,
)
from agent_skill.report import Level, declare

# The branches of `conventions` and of `prose` this standard's own rules
# fire through.
FUTURE = declare("conventions", "ps_future", Level.FAIL)
AUGMENTED = declare("conventions", "ps_augmented", Level.FAIL)
META_DOC = declare("conventions", "ps_meta_doc", Level.FAIL)
FUTURE_PROSE = declare("prose", "ps_future", Level.FAIL)

CONVENTIONS = (
    # PS-TYPE — PEP 563 is Superseded, and the future import does not
    # merely fail to help on 3.14+: it silently degrades `annotationlib`
    # `VALUE` and `FORWARDREF` to bare strings, so a library reading
    # annotations gets text it must `eval`.
    LineRule(
        FUTURE,
        r"^\s*from\s+__future__\s+import\s+.*\bannotations\b",
        "`from __future__ import annotations` degrades `annotationlib` "
        "VALUE and FORWARDREF to bare strings; PEP 563 is Superseded",
    ),
    # PS-CONC — the GIL made a read-modify-write on shared state
    # *unlikely* to interleave rather than atomic. Free-threading
    # removes the luck, not a guarantee: eight threads lose roughly
    # three quarters of the updates.
    LineRule(
        AUGMENTED,
        r"^\s*(?:self|cls)\.\w+\s*(?:[+\-*/|&^]|//|\*\*|>>|<<)=",
        "augmented assignment on instance state is a read-modify-write; under "
        "free threading it loses updates (PS-CONC)",
    ),
    # A docstring inside an example documents the API, not the standard.
    LineRule(
        META_DOC,
        r'(?i)^\s*""".*\b(this example|this rule|the snippet|as shipped|'
        r"the block|for the purposes of)\b",
        "docstring discusses the example rather than the API",
        comments=True,
    ),
)

PROSE = (
    # The standard must not recommend a spelling it forbids. `from
    # __future__ import annotations` is banned outright, so prose naming
    # it is either hunting it (inside a `**Check:**`) or is the rule
    # that bans it — which is how three passages survived the same rule
    # being tightened in `zig-style`. A table row is the standard's own
    # dead-API listing, and a line already calling the spelling stale,
    # superseded or forbidden is the rule doing its job. What is left is
    # prose that names it without condemning it.
    LineRule(
        FUTURE_PROSE,
        r"__future__",
        "prose names `__future__` outside a **Check:** without saying it is forbidden",
        unless=Unless(
            near=(
                Near(r"^\s*\|"),
                Near(
                    r"(?i)\b(stale|superseded|forbidden|deprecat|never|no longer|"
                    r"degrade|wrong|dead|remove)"
                ),
            )
        ),
    ),
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
    fires=keyed(
        {
            "PS-API-05": ("from acmewidget._internal import helper",),
            "PS-ASYNC-01": ("loop = asyncio.new_event_loop()",),
            "PS-ASYNC-02": ("loop = asyncio.get_event_loop()",),
            "PS-ASYNC-03": ("task = asyncio.create_task(worker())",),
            # The pattern carried a stray space for as long as it
            # shipped, and matched nothing; this is the line it was
            # written to find.
            "PS-MIG-06": ("if json.__version__ < (2, 0):",),
        }
    ),
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=rules(
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
        "PS-BUILD-13",
        "PS-BUILD-20",
        "PS-CONC-02",
        "PS-CONC-03",
        "PS-CONC-05",
        "PS-CONC-07",
        "PS-CONC-08",
        "PS-CONC-10",
        "PS-CONC-12",
        "PS-CONC-13",
        "PS-CONC-15",
        "PS-CONC-17",
        "PS-CONC-18",
        "PS-CONC-19",
        "PS-CONC-20",
        "PS-CONC-21",
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
        "PS-NAME-10",
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
        "PS-TYPE-10",
        "PS-TYPE-11",
        "PS-TYPE-13",
        "PS-TYPE-19",
    ),
    not_decisive=keyed(
        {
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
            "PS-CONC-17": NotDecisive(
                "any hit whose preceding lines are inside",
                "the pattern finds every ContextVar; the scope it is created in "
                "decides, which a line-oriented pattern cannot see",
            ),
            "PS-CONC-18": NotDecisive(
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
            "PS-NAME-10": NotDecisive(
                "read each hit for what",
                "the pattern finds every indented import; what encloses it decides, "
                "and an `if TYPE_CHECKING:` block is indented too",
            ),
            "PS-CONC-12": NotDecisive(
                "read what the target closes over",
                "the pattern finds every thread start; what the target closes over "
                "decides, and starting a thread is not itself a defect",
            ),
            "PS-CONC-19": NotDecisive(
                "inside any thread target",
                "the pattern finds every `print`; the calling thread decides, and a "
                "module-level print is not a hit",
            ),
            "PS-CONC-21": NotDecisive(
                "applied to a `def` containing `yield`",
                "the pattern finds every `@contextmanager`; what it decorates decides, "
                "and the `with` form the rule recommends matches too",
            ),
        }
    ),
    conventions=CONVENTIONS,
    prose=PROSE,
)
