"""A GitHub Actions workflow, read as far as the checks read one.

The harness depends on no YAML parser, and what the checks ask of a
workflow is written in a small part of YAML: each `uses:`, and each
step's `uses:`, `with:` and `run:`. That part is read here, once, for
`pins` and `self-application` both. Nothing else of a workflow is
read, and a step written as a flow mapping (`- { uses: … }`) is not
read as a step.
"""

import re
from dataclasses import dataclass, field
lazy from collections.abc import Iterator
lazy from pathlib import Path

from agent_skill.layout import WORKFLOWS
from agent_skill.text import group, strip_comment

#: What a workflow file is called.
SUFFIXES = (".yml", ".yaml")

#: A `uses:` key and its value, alone on its line or opening a step,
#: commented out or not, and the comment after it. A line of prose that
#: mentions `uses:` is not one: the key opens the line, and nothing but
#: a comment follows the value.
_USES = re.compile(
    r"^ *(?:# *)*(?:- +)?uses: *"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s#]+)"
    r" *(?:# *(?P<comment>.*?))? *$"
)

#: A key and what follows it, after a step's `- ` if there is one.
_KEY = re.compile(r"^ *(?:- +)?(?P<key>[\w-]+):(?: +(?P<value>.*))?$")

#: The key a job's list of steps is under.
_STEPS = re.compile(r"^ *steps: *(?:#.*)?$")

#: A step's `- `, and the indent before it.
_ITEM = re.compile(r"^ *- +")

#: A commit, as `git` names one in full.
_COMMIT = re.compile(r"[0-9a-f]{40}")

#: How a workflow names an action that is no third party's: a path in
#: the repository it runs in, or a container image.
_NOT_THIRD_PARTY = ("./", "docker://")

#: What two steps of one identity must agree on: the action and its
#: ref, the `with:` pairs, and the command run.
type Held = tuple[str, tuple[tuple[str, str], ...], str]


@dataclass(frozen=True, slots=True)
class Uses:
    """One `uses:`: what it names, at which ref, and its comment."""

    #: the line it is on, counted from 1
    line: int
    #: `actions/checkout`, `./tools/lint`, `docker://alpine:3`
    action: str
    #: what follows the `@`; "" when nothing does
    ref: str
    #: the comment after the value, its `#` taken off; "" for none
    comment: str

    @property
    def third_party(self) -> bool:
        """Is this an action named by its repository?

        Not a local action, which is the repository's own code at the
        commit being run, nor a container image.
        """
        return not self.action.startswith(_NOT_THIRD_PARTY)

    @property
    def commit(self) -> bool:
        """Does the ref name a commit, all 40 hexadecimal digits?"""
        return _COMMIT.fullmatch(self.ref) is not None

    @property
    def named(self) -> str:
        """The value as written: `actions/checkout@v7`."""
        return f"{self.action}@{self.ref}" if self.ref else self.action


@dataclass(frozen=True, slots=True)
class Step:
    """One step of a job: the action it uses, with what, or its run."""

    #: the line its `- ` is on, counted from 1
    line: int
    uses: Uses | None = None
    #: the `with:` mapping, each key and value as text, sorted by key
    inputs: tuple[tuple[str, str], ...] = ()
    #: the `run:` text, its words separated by single spaces
    run: str = ""

    @property
    def identity(self) -> str:
        """What makes a step of one workflow the same as another's.

        The action, for a step that uses one. For a step that runs a
        command, the words up to the first that holds a digit, which
        is where a command names what it pins: `uv python install
        cpython-3.15.2+freethreaded` is the interpreter step, at
        whatever release it names. A command that pins nothing is the
        same step only as itself.
        """
        if self.uses is not None:
            return self.uses.action
        words = self.run.split()
        pinned = next((i for i, w in enumerate(words) if _digit(w)), 0)
        return " ".join(words[:pinned] if pinned else words)

    @property
    def held(self) -> Held:
        """What two steps of one identity must agree on."""
        named = self.uses.named if self.uses is not None else ""
        return named, self.inputs, self.run

    @property
    def stated(self) -> str:
        """The step as a finding names it."""
        if self.uses is None:
            return f"`{self.run}`"
        given = ", ".join(f"{key}: {value}" for key, value in self.inputs)
        return f"`{self.uses.named}`" + (f" with `{{{given}}}`" if given else "")


def shipped(assets: list[Path]) -> list[Path]:
    """The workflows among a skill's assets."""
    return [p for p in assets if p.suffix in SUFFIXES]


def run_by(root: Path) -> list[Path]:
    """The workflows the repository at `root` runs, in sorted order."""
    directory = root / WORKFLOWS
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix in SUFFIXES)


def uses(text: str) -> Iterator[Uses]:
    """Every `uses:` in a workflow, a commented-out one included.

    A step kept as a comment, such as a job to enable later, is copied
    back in by whoever enables it, at whatever its ref names by then.
    """
    for number, line in enumerate(text.split("\n"), 1):
        if (found := _uses_on(line, number)) is not None:
            yield found


def steps(text: str) -> list[Step]:
    """Every step of every job, in the order the workflow gives them.

    A step is an item of a `steps:` list. Its `with:` is a flow mapping
    on its line or a block mapping under it; its `run:` a scalar on its
    line or a block under it. A commented-out step is no step.
    """
    lines = text.split("\n")
    found: list[Step] = []
    for start, end in _spans(lines):
        draft = _Draft(start + 1, _width(_ITEM, lines[start]))
        for i in range(start, end):
            draft.take(i + 1, lines[i])
        found.append(draft.done())
    return found


def _spans(lines: list[str]) -> Iterator[tuple[int, int]]:
    """Each step's first line, and the line after its last, as indices.

    A `steps:` list holds every line under its key that is indented
    deeper, or as deep and opening an item; an item runs to the next.
    """
    key: int | None = None
    item: int | None = None
    start: int | None = None
    for i, line in enumerate(lines):
        bare = line.strip()
        if not bare or bare.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        dash = bare.startswith("- ")
        if key is not None and (indent > key or (indent == key and dash)):
            if dash and item in {None, indent}:
                if start is not None:
                    yield start, i
                item, start = indent, i
            continue
        if start is not None:
            yield start, i
        key = indent if _STEPS.match(line) else None
        item = start = None
    if start is not None:
        yield start, len(lines)


@dataclass(slots=True)
class _Draft:
    """A step as its lines are read."""

    line: int
    #: the indent of the step's own keys
    width: int
    uses: Uses | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    run: list[str] = field(default_factory=list)
    #: the key whose value goes on under it: a block mapping or scalar
    open: str = ""

    def take(self, number: int, line: str) -> None:
        """One line: a key of the step's, or what goes on under one."""
        if number == self.line:
            line = " " * self.width + line[self.width :]
        bare = line.strip()
        deeper = len(line) - len(line.lstrip(" ")) > self.width
        if self.open == "run" and (deeper or not bare):
            self.run.append(bare)
        elif not bare or bare.startswith("#"):
            return
        elif deeper:
            if self.open == "with" and (m := _KEY.match(_uncommented(line))):
                self.inputs[m["key"]] = _scalar(group(m, "value"))
        elif (m := _KEY.match(_uncommented(line))) is not None:
            self._key(m["key"], group(m, "value"), number, line)

    def _key(self, key: str, value: str, number: int, line: str) -> None:
        """A key of the step's own, and its value on the same line."""
        self.open = ""
        match key:
            case "uses":
                self.uses = _uses_on(line, number)
            case "with" if value:
                self.inputs.update(_flow(value))
            case "run" if value[:1] not in {"|", ">"}:
                self.run.append(value)
            case "with" | "run":
                self.open = key
            case _:
                pass

    def done(self) -> Step:
        """The step, now that all of its lines are read."""
        run = " ".join(" ".join(self.run).split())
        return Step(self.line, self.uses, tuple(sorted(self.inputs.items())), run)


def _uses_on(line: str, number: int) -> Uses | None:
    """The `uses:` `line` holds, or None when it holds none."""
    m = _USES.match(line)
    if m is None:
        return None
    action, _, ref = _scalar(m["value"]).partition("@")
    return Uses(number, action, ref, group(m, "comment"))


def _digit(word: str) -> bool:
    """Does `word` hold a digit?"""
    return any(c.isdigit() for c in word)


def _width(pattern: re.Pattern[str], line: str) -> int:
    """How much of `line` `pattern` matches at its start."""
    m = pattern.match(line)
    return m.end() if m else 0


def _uncommented(line: str) -> str:
    """`line` without a comment after its content."""
    return strip_comment(line, " #", "\"'").rstrip()


def _scalar(text: str) -> str:
    """A scalar's text: unquoted, and without a comment after it."""
    text = _uncommented(f" {text}").strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _flow(text: str) -> dict[str, str]:
    """The pairs of a one-line flow mapping: `{ version: "0.13.7" }`."""
    inner = _uncommented(f" {text}").strip().removeprefix("{").removesuffix("}")
    pairs: dict[str, str] = {}
    for item in _items(inner):
        key, colon, value = item.partition(":")
        if colon and key.strip():
            pairs[key.strip()] = _scalar(value)
    return pairs


def _items(inner: str) -> Iterator[str]:
    """`inner` split at each comma outside a string or a bracket."""
    depth, opener, start = 0, "", 0
    for i, c in enumerate(inner):
        if opener:
            opener = "" if c == opener else opener
        elif c in "\"'":
            opener = c
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        elif c == "," and not depth:
            yield inner[start:i]
            start = i + 1
    yield inner[start:]
