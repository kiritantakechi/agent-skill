"""Each concept the harness reads is spelled in one module.

A rule ID and a version are read by `ids`; the column limit, a fence
and a heading by `doc`. A second spelling agrees with the first on the
files it was written against and on nothing else: a rule-ID pattern
that left out the inserted letter read an inserted rule as no rule, a
`## ` scanner that knew nothing of fences cut a rule in half at a
heading inside its own example, and two fillers at one width made a
renumbering and its inverse disagree. This reads every module of the
harness as source and fails on a new spelling wherever it is written.

A spelling is found as the literal it is written in: a regex, a prefix
test, an assignment. Docstrings are not read. A pattern composed from
`ids.rule_id()` is not a second spelling, and is allowed only for the
citation grammar `anatomy` reads inside a block's text.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import override
lazy from collections.abc import Iterator

import pytest

#: The harness's source.
SRC = Path(__file__).resolve().parents[1] / "src" / "agent_skill"

#: The module that spells a rule ID and a version.
IDS = "ids.py"

#: The package that spells the column limit, a fence and a heading.
DOC = "doc/"

#: The markdown the negative controls write: each control's defect, and
#: the demo standard the controls of the normal form break. Written,
#: never read, so a fence or a heading in it is text, not a reader.
INJECTED = frozenset({"checks/controls.py", "checks/demo.py"})

#: The patterns composed from `ids.rule_id()` outside `ids`, by module
#: and the name they are built in: a citation near its chapter, and an
#: abbreviated ID. Each reads inline grammar inside one block's text,
#: which the tree keeps whole.
COMPOSED = frozenset(
    {
        ("checks/anatomy.py", "_paths"),
        ("checks/anatomy.py", "_ABBREVIATED"),
    }
)

#: A capital-letter class beside a hyphen, as a rule ID's prefix and
#: family are matched (`[A-Z]{2}-`, `[A-Z]+-`, `-[A-Z]+`), or the number
#: with its inserted letter (`\d+[a-z]?`).
RULE_ID = re.compile(
    r"\[A-Z\](?:\{\d+(?:,\d*)?\}|[+*])?\)?-|-\(?\[A-Z\]|\\d\+\[a-z\]\?"
)

#: Digits, a dot, digits: a release read by hand (`\d+\.\d+`,
#: `(\d+)\.(\d+)`).
VERSION = re.compile(r"\\d(?:[+*]|\{\d+(?:,\d*)?\})?\)?\\\.\(?(?:\\d|\[\d)")

#: Backticks at the start of a line, of a literal, or after a line's
#: indentation: a fence found by its text.
FENCE = re.compile(r"(?:\A|\^|\\n|\n)(?:\[ \\t\][*+]|\\s\*|[ \t]*)(?:`{3}|~{3}|`\{3)")

#: Hashes at the start of a line: a heading found by its text.
HEADING = re.compile(r"(?:\^|\\n|\n)(?:\[ \\t\][*+]|\\s\*)?#(?:[# +]|\{\d)")

#: A heading's opening, as a prefix test spells it: `startswith("## ")`.
HEADING_PREFIX = re.compile(r"#{1,6} ")


@dataclass(frozen=True, slots=True)
class Literal:
    """A string a module writes, where, and inside which name."""

    module: str
    line: int
    text: str
    #: the function or module-level assignment it is written in
    within: str
    #: whether it is what a `startswith` tests a line against
    prefix: bool = False

    @override
    def __str__(self) -> str:
        """`module:line (name) 'text'`, as a failure lists it."""
        return f"{self.module}:{self.line} ({self.within}) {self.text!r}"


def _docstrings(tree: ast.Module) -> set[int]:
    """The ids of every docstring constant in `tree`."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            match node.body:
                case [ast.Expr(value=ast.Constant(value=str()) as doc), *_]:
                    out.add(id(doc))
                case _:
                    pass
    return out


def _within(node: ast.AST, scope: str) -> str:
    """The name `node` introduces for what it holds, or `scope`."""
    match node:
        case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
            return name
        case ast.Assign(targets=[ast.Name(id=name), *_]) if scope == MODULE:
            return name
        case ast.AnnAssign(target=ast.Name(id=name)) if scope == MODULE:
            return name
        case _:
            return scope


def _text(node: ast.AST) -> str | None:
    """The string `node` writes, a formatted value as `{}`."""
    match node:
        case ast.Constant(value=str() as value):
            return value
        case ast.JoinedStr(values=values):
            return "".join(
                str(v.value) if isinstance(v, ast.Constant) else "{}" for v in values
            )
        case _:
            return None


#: The scope of a module's own top level.
MODULE = "<module>"


def _nodes(
    node: ast.AST, scope: str = MODULE, *, prefix: bool = False
) -> Iterator[tuple[ast.AST, str, bool]]:
    """Each node under `node`, the name it is in, and if it is a prefix.

    A prefix is an argument of `startswith`, or an element of a tuple
    that is one. An f-string's text is its own: only the expressions
    it formats are read further.
    """
    scope = _within(node, scope)
    yield node, scope, prefix
    tested: list[ast.expr] = []
    match node:
        case ast.JoinedStr(values=values):
            children: list[ast.AST] = [
                v.value for v in values if isinstance(v, ast.FormattedValue)
            ]
        case ast.Call(func=ast.Attribute(attr="startswith"), args=args):
            children, tested = list(ast.iter_child_nodes(node)), args
        case _:
            children = list(ast.iter_child_nodes(node))
    held = prefix and isinstance(node, ast.Tuple)
    for child in children:
        yield from _nodes(child, scope, prefix=held or child in tested)


def read(source: str, module: str) -> tuple[list[Literal], list[Literal]]:
    """The literals `source` writes, and its calls of `rule_id`.

    A call is reported as a literal whose text is `rule_id(`, in the
    name it is built in.
    """
    tree = ast.parse(source)
    skip = _docstrings(tree)
    literals: list[Literal] = []
    calls: list[Literal] = []
    for node, scope, prefix in _nodes(tree):
        line = getattr(node, "lineno", 0)
        if id(node) not in skip and (text := _text(node)) is not None:
            literals.append(Literal(module, line, text, scope, prefix))
        match node:
            case ast.Call(func=ast.Name(id="rule_id") | ast.Attribute(attr="rule_id")):
                calls.append(Literal(module, line, "rule_id(", scope))
            case _:
                pass
    return literals, calls


def modules() -> Iterator[tuple[str, str]]:
    """Each module of the harness: its path, then its source."""
    for path in sorted(SRC.rglob("*.py")):
        yield path.relative_to(SRC).as_posix(), path.read_text()


def _spelled(lit: Literal) -> Iterator[str]:
    """What concept `lit` spells, if any, wherever it is written."""
    if RULE_ID.search(lit.text):
        yield "a rule-ID pattern"
    if VERSION.search(lit.text):
        yield "a version parser"
    if FENCE.search(lit.text):
        yield "a fence tracker"
    if HEADING.search(lit.text) or (lit.prefix and HEADING_PREFIX.match(lit.text)):
        yield "a heading scanner"


#: Where each concept is spelled, by what `_spelled` calls it.
HOME = {
    "a rule-ID pattern": IDS,
    "a version parser": IDS,
    "a fence tracker": DOC,
    "a heading scanner": DOC,
}


def spellings(module: str, source: str) -> Iterator[tuple[str, Literal]]:
    """Each second spelling `source` writes, and what it spells.

    The markdown a control injects is text, never a reader, so a fence
    or a heading in it is no spelling.
    """
    literals, calls = read(source, module)
    for lit in literals:
        for what in _spelled(lit):
            injected = module in INJECTED and HOME[what] == DOC
            if not module.startswith(HOME[what]) and not injected:
                yield what, lit
    for call in calls:
        if module != IDS and (module, call.within) not in COMPOSED:
            yield "a pattern composed from `rule_id`", call
    if not module.startswith(DOC):
        for node in ast.walk(ast.parse(source)):
            match node:
                case (
                    ast.Assign(targets=[ast.Name(id="WIDTH"), *_])
                    | ast.AnnAssign(target=ast.Name(id="WIDTH"))
                ):
                    yield "a column limit", Literal(module, node.lineno, "WIDTH =", "")
                case _:
                    pass


def test_no_concept_is_spelled_twice() -> None:
    found = [
        f"{what}: {lit}"
        for module, source in modules()
        for what, lit in spellings(module, source)
    ]
    assert found == []


def test_the_composed_citation_patterns_are_the_two_in_anatomy() -> None:
    """The allowance is spent, not merely permitted."""
    built = {
        (module, call.within)
        for module, source in modules()
        if module != IDS
        for call in read(source, module)[1]
    }
    assert built == COMPOSED


#: The spellings this change deleted, each as it was written, and what
#: each spelled. The test above must catch every one of them.
DELETED = [
    (
        "model.py",
        'head = re.compile(rf"^### ({rule_id(self.prefix)}) \\[(M!|M|S)\\] (.+)$")',
        {"a heading scanner", "a pattern composed from `rule_id`"},
    ),
    (
        "model.py",
        '_RANGE = re.compile(rf"`([A-Z]{{2}}-[A-Z]+)-(\\d+)`")',
        {"a rule-ID pattern"},
    ),
    (
        "model.py",
        'FENCE = re.compile(r"^[ \\t]*```", re.MULTILINE)',
        {"a fence tracker"},
    ),
    ("model.py", 'SECTION = re.compile(r"^## ", re.MULTILINE)', {"a heading scanner"}),
    ("model.py", 'fenced = line.lstrip().startswith("```")', {"a fence tracker"}),
    ("model.py", 'stop = line.startswith("## ")', {"a heading scanner"}),
    (
        "checks/layout.py",
        'TOC = re.compile(r"^\\s*- [A-Z]{2}-[A-Z]+-\\d+[a-z]? \\[")',
        {"a rule-ID pattern"},
    ),
    (
        "checks/prose.py",
        'POSITIONAL = r"({pre}-[A-Z]+-\\d+[a-z]?,?\\s+(below|above)\\b"',
        {"a rule-ID pattern"},
    ),
    ("checks/layout.py", "WIDTH = 100", {"a column limit"}),
    ("fmt.py", 'held = lines[first - 1] != f"```{block.lang}"', {"a fence tracker"}),
    (
        "checks/pins.py",
        'm = re.match(r"^(\\d+)\\.(\\d+)\\.(\\d+)(?:(a|b|rc)(\\d+))?$", version)',
        {"a version parser"},
    ),
    (
        "shared/__init__.py",
        'm = re.match(r"\\d+\\.\\d+", version)',
        {"a version parser"},
    ),
    (
        "harness.py",
        '_VERSION = re.compile(r"(\\d+\\.\\d+\\.\\d+)")',
        {"a version parser"},
    ),
]


@pytest.mark.parametrize(("module", "source", "spelled"), DELETED)
def test_a_deleted_spelling_would_be_caught(
    module: str, source: str, spelled: set[str]
) -> None:
    assert {what for what, _ in spellings(module, source)} == spelled


@pytest.mark.parametrize(
    "source",
    [
        'INLINE = re.compile(r"\\S```")',  # three backticks inside text
        'DATED = r"[Vv]erified \\d{4}-\\d{2}-\\d{2}"',  # a date, not a release
        'CODE = re.compile(r"([A-Z]{1,5}[0-9]{3,4})")',  # a ruff code
        'h1 = "# " + title',  # a heading printed, not scanned for
        'm = re.match(r"^\\[lints\\.(\\w+)\\]", line)',  # a TOML table
    ],
)
def test_what_is_not_a_spelling_passes(source: str) -> None:
    assert list(spellings("checks/example.py", source)) == []
