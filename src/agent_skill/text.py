"""Reading source text the way a compiler would, not the way a regex would."""

from __future__ import annotations

import re


def strip_comment(line: str) -> str:
    """Everything before the first `//` that is not inside a string literal.

    `const url = "https://example.com";` keeps its value. Splitting on `//` does
    not, and a Check grepping for a path would miss it.
    """
    i, in_str = 0, False
    while i < len(line):
        c = line[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "/" and line[i + 1 : i + 2] == "/":
            break
        i += 1
    return line[:i]


def code_only(body: str) -> str:
    """`body` with every comment removed and the line count preserved."""
    return "\n".join(strip_comment(line) for line in body.split("\n"))


def paragraphs(text: str):
    """(start line, lines) for each blank-line-separated run, 1-based."""
    lines = text.split("\n")
    start, buf = 1, []
    for i, line in enumerate(lines, 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            yield start, buf
            buf = []
    if buf:
        yield start, buf


_FENCE = re.compile(r"^```")


def unfenced(text: str):
    """(lineno, line) for every line outside a fenced code block."""
    fenced = False
    for i, line in enumerate(text.split("\n"), 1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield i, line
