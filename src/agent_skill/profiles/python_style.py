"""python-style: its own `[M]` rules, applied to its own examples and prose."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..report import Finding, fail
from ..text import strip_comment, syntax_for
from . import NotDecisive, Profile, register

#: PS-TYPE — PEP 563 is Superseded, and the future import does not merely fail to
#: help on 3.14+: it silently degrades `annotationlib` `VALUE` and `FORWARDREF`
#: to bare strings, so a library reading annotations gets text it must `eval`.
FUTURE_ANNOTATIONS = re.compile(r"^\s*from\s+__future__\s+import\s+.*\bannotations\b")

#: PS-FT — the GIL made a read-modify-write on shared state *unlikely* to
#: interleave rather than atomic. Free-threading removes the luck, not a
#: guarantee: eight threads lose roughly three quarters of the updates.
AUGMENTED_ON_SHARED = re.compile(r"^\s*(?:self|cls)\.\w+\s*(?:[+\-*/|&^]|//|\*\*|>>|<<)=")

#: A docstring inside an example documents the API, not the standard.
META = re.compile(
    r"\b(this example|this rule|the snippet|as shipped|the block|for the purposes of)\b",
    re.I,
)


def _inside_tests(body: str) -> set[int]:
    """Body-line indices inside a `def test_*` function, by indentation.

    Python has no block delimiter to count, so the end of a test is the next
    line at or below the `def`'s own indentation that is not blank.
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
    name: str = "python-style"
    prefix: str = "PS"
    languages: tuple[str, ...] = ("python",)
    #: `pyproject.toml`, `ruff.toml`, `ty.toml` and `pytest.toml` examples carry
    #: markers too, and were invisible to every tool while the marked set was
    #: derived from the fence tag alone.
    marked_languages: tuple[str, ...] = ("toml",)
    #: Python has three ways to be wrong and `does-not-compile` names none of
    #: them; `# rejected — <tool>: …` says which tool does the rejecting.
    markers: tuple[str, ...] = ("verified", "fragment", "rejected")
    toolchain: str | None = "python"
    exempt: dict = field(default_factory=dict)
    not_decisive: dict = field(
        default_factory=lambda: {
            # Each anchor is a literal fragment of that rule's own **Check:**, so
            # rewriting the rule cannot leave a stale entry quietly suppressing
            # its grep. Every one of these greps finds the shape; something the
            # grep cannot see decides whether the shape is a defect.
            "PS-FT-02": NotDecisive(
                "read each hit",
                "the grep finds every compound assignment; whether the target is "
                "reachable from a second thread decides, and a lock or a local "
                "accumulator makes it compliant",
            ),
            "PS-FT-03": NotDecisive(
                "unless a lock spans both",
                "the grep finds the test; whether a lock spans the test and the write decides",
            ),
            "PS-FT-11": NotDecisive(
                "every decorator without `frozen=True`",
                "the grep finds every dataclass; the `frozen=True` argument decides",
            ),
            "PS-FT-21": NotDecisive(
                "any hit whose preceding lines are inside",
                "the grep finds every ContextVar; the scope it is created in "
                "decides, which a line-oriented grep cannot see",
            ),
            "PS-FT-22": NotDecisive(
                "whose value was set outside it",
                "the grep finds every context read; passing the context explicitly "
                "is the compliant form and matches the same pattern",
            ),
            "PS-MIG-10": NotDecisive(
                "find every decorator derived from one that is",
                "the grep finds every `@contextmanager`; what it decorates decides, "
                "and the `with` form the standard recommends matches too",
            ),
            "PS-MIG-11": NotDecisive(
                "isinstance(.*, dict)",
                "the grep finds every dict test; a narrowing check on parsed JSON "
                "is correct, and so is a test demonstrating that a `frozendict` "
                "fails it",
            ),
            "PS-TEST-19": NotDecisive(
                "sleep(' tests/",
                "scoped to the test suite: `await asyncio.sleep(...)` in ordinary "
                "code is correct, and the grep cannot see which tree it is in",
            ),
            "PS-DOC-08": NotDecisive(
                "a parenthesised type is the",
                "the grep finds any indented name followed by a parenthesis, which "
                "matches ordinary prose as readily as a docstring type",
            ),
            "PS-ASYNC-04": NotDecisive(
                "every hit outside a `TaskGroup`",
                "the grep finds every task start; being inside a `TaskGroup` is "
                "what makes it compliant, and the grep cannot see the block",
            ),
            "PS-ERR-15": NotDecisive(
                "and read each block for a",
                "the grep finds every `finally`; what is inside it decides, and "
                "most blocks contain nothing of the kind",
            ),
            "PS-ERR-16": NotDecisive(
                "each hit that only releases a resource",
                "the grep finds every `finally`; the one inside a `@contextmanager` "
                "is how a context manager is implemented, not a call site that "
                "should have used one",
            ),
            "PS-DATA-10": NotDecisive(
                "inside class bodies",
                "the grep finds every call on the right of an assignment; being "
                "inside a class body is what makes it a default, which the grep "
                "cannot see",
            ),
            # Polarity: this Check asserts the shape is *present*, so its hits are
            # evidence of compliance and reading them as defects inverts the rule.
            "PS-DATA-14": NotDecisive(
                "should be roughly as common as",
                "a presence assertion: the finding is an absence, which no hit can show",
            ),
            "PS-DATA-15": NotDecisive(
                "every hit is a place a `frozendict` would fail",
                "the rule's own example demonstrates the failing test deliberately, "
                "and a hit in application code is a candidate until the value's "
                "type is known",
            ),
            "PS-DATA-01": NotDecisive(
                "needs a reason on the line above it",
                "the grep finds every dataclass; the `frozen=True` argument decides, "
                "and a frozen one matches the same pattern",
            ),
            "PS-DATA-02": NotDecisive(
                "read for `slots=`",
                "the grep finds every dataclass; the `slots=` argument decides",
            ),
            "PS-NAME-15": NotDecisive(
                "read each hit for what",
                "the grep finds every indented import; what encloses it decides, "
                "and an `if TYPE_CHECKING:` block is indented too",
            ),
            "PS-FT-14": NotDecisive(
                "read what the target closes over",
                "the grep finds every thread start; what the target closes over "
                "decides, and starting a thread is not itself a defect",
            ),
            "PS-FT-23": NotDecisive(
                "inside any thread target",
                "the grep finds every `print`; the calling thread decides, and a "
                "module-level print is not a hit",
            ),
            "PS-FT-25": NotDecisive(
                "applied to a `def` containing `yield`",
                "the grep finds every `@contextmanager`; what it decorates decides, "
                "and the `with` form the rule recommends matches too",
            ),
        }
    )

    def conventions(self, skill) -> Iterable[Finding]:
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
                        "augmented assignment on instance state is a read-modify-write; "
                        "under free threading it loses updates (PS-FT)",
                        where,
                    )

                if raw.lstrip().startswith('"""') and META.search(raw):
                    yield fail("docstring discusses the example rather than the API", where)

    def inside_tests(self, body: str) -> set[int]:
        return _inside_tests(body)

    def prose(self, skill) -> Iterable[Finding]:
        """The standard must not recommend a spelling it forbids.

        `from __future__ import annotations` is banned outright, so prose naming
        it is either hunting it (inside a `**Check:**`) or is the rule that bans
        it. Anything else is the standard teaching the thing it exists to stop —
        which is how three passages survived the same rule being tightened in
        `zig-style`. Scoped per rule and per Check block, because both wrap.
        """
        span = re.compile(r"__future__")
        # A table row is the standard's own dead-API listing, and a line already
        # calling the spelling stale, superseded or forbidden is the rule doing
        # its job. What is left is prose that names it without condemning it.
        condemned = re.compile(
            r"\b(stale|superseded|forbidden|deprecat|never|no longer|degrade|"
            r"wrong|dead|remove)",
            re.I,
        )
        for chapter in skill.chapters:
            for i, line, rid, in_check in _prose_lines(chapter.text, skill.prefix):
                if in_check or line.lstrip().startswith("|") or condemned.search(line):
                    continue
                if span.search(line):
                    yield fail(
                        "prose names `__future__` outside a **Check:** without saying it is "
                        "forbidden",
                        f"{chapter.name}:{i} [{rid}]",
                    )


def _prose_lines(text: str, prefix: str):
    """(lineno, line, owning rule, inside-a-Check) for unfenced prose."""
    rid, in_check, fenced = "?", False, False
    head = re.compile(rf"^### ({prefix}-[A-Z]+-\d+[a-z]?) \[")
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("```"):
            fenced = not fenced
            in_check = False
            continue
        if fenced:
            continue
        if m := head.match(line):
            rid, in_check = m.group(1), False
        elif line.startswith("**Check:"):
            in_check = True
        elif line.startswith("**") or not line.strip():
            in_check = False
        yield i, line, rid, in_check


register(PythonStyle())
