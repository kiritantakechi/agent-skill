"""Reading source text the way a compiler would, not the way a regex would."""

from __future__ import annotations


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
