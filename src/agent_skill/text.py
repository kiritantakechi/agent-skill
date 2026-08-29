"""Reading source text the way a compiler would, not the way a regex would."""

from __future__ import annotations

#: How a language spells a line comment, and which characters delimit a string.
#: Rust and Zig keep the default on purpose: in Rust `'` opens a lifetime
#: (`&'a str`), not a string, so treating it as a delimiter swallows the rest of
#: the line. Python needs its own entry for the opposite reason — `//` is floor
#: division there, and reading it as a comment truncated every line after one.
_SYNTAX: dict[str, tuple[str, str]] = {
    "python": ("#", "\"'"),
    "py": ("#", "\"'"),
}
_DEFAULT = ("//", '"')


def syntax_for(lang: str) -> tuple[str, str]:
    """The line-comment token and string delimiters `lang` uses."""
    return _SYNTAX.get(lang, _DEFAULT)


def strip_comment(line: str, comment: str = "//", quotes: str = '"') -> str:
    """Everything before the first `comment` token not inside a string literal.

    `const url = "https://example.com";` keeps its value. Splitting on the token
    does not, and a Check searching for a path would miss it.

    The token is a parameter because it is not a property of source text in
    general. `strip_comment("q = total // count")` returns `"q = total "` under
    the default, which is right for Rust and silently wrong for Python.
    """
    i, opener = 0, ""
    width = len(comment)
    while i < len(line):
        c = line[i]
        if opener:
            if c == "\\":
                i += 2
                continue
            if c == opener:
                opener = ""
        elif c in quotes:
            opener = c
        elif line[i : i + width] == comment:
            break
        i += 1
    return line[:i]


def code_only(body: str, comment: str = "//", quotes: str = '"') -> str:
    """`body` with every comment removed and the line count preserved."""
    return "\n".join(strip_comment(line, comment, quotes) for line in body.split("\n"))
