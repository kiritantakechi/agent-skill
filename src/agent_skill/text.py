"""Reading source text as a compiler would, not as a regex would.

Comments and strings are told apart from code, prose is wrapped to the
house width, and a regex match is narrowed to the text it found.
"""

import re


def group(m: re.Match[str] | None, key: int | str = 1) -> str:
    """What group `key` of `m` matched, or "" when it matched nothing.

    "" both without a match and for a group that took no part in it.
    The stubs type every group as possibly absent, even one the pattern
    cannot leave out; narrowing here says what each caller meant.
    """
    found = m.group(key) if m is not None else None
    return found if isinstance(found, str) else ""


#: How a language spells a line comment, and which characters delimit a
#: string. Rust and Zig keep the default on purpose: in Rust `'` opens a
#: lifetime (`&'a str`), not a string, so treating it as a delimiter
#: swallows the rest of the line. Python needs its own entry for the
#: opposite reason — `//` is floor division there, and reading it as a
#: comment truncated every line after one.
_SYNTAX: dict[str, tuple[str, str]] = {
    "python": ("#", "\"'"),
    "py": ("#", "\"'"),
}
_DEFAULT = ("//", '"')


def syntax_for(lang: str) -> tuple[str, str]:
    """The line-comment token and string delimiters `lang` uses."""
    return _SYNTAX.get(lang, _DEFAULT)


def strip_comment(line: str, comment: str = "//", quotes: str = '"') -> str:
    """Everything before the first `comment` token outside a string.

    `const url = "https://example.com";` keeps its value. Splitting on
    the token does not, and a Check searching for a path would miss it.

    The token is a parameter because it is not a property of source text
    in general. `strip_comment("q = total // count")` returns
    `"q = total "` under the default, which is right for Rust and
    silently wrong for Python.
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
    """`body` with every comment removed and the line count kept."""
    return "\n".join(strip_comment(line, comment, quotes) for line in body.split("\n"))


#: The `layout` check's limit, which `reflow` brings prose back under.
WIDTH = 100

_STARTS_BLOCK = re.compile(r"^\s*(?:[-*] |\d+\. |#|\||```|>|\*\*[A-Z][a-z]+:\*\*)")


def reflow(text: str, width: int = WIDTH) -> str:
    """Push the words of every over-long prose line into the next line.

    The smallest edit that brings a paragraph back under the limit: the
    rest of the paragraph keeps its line breaks, so the diff shows what
    the rename moved and nothing else. Code, tables and headings are
    left alone — `layout` decides those, and a code line is not this
    function's to rewrite.
    """
    lines = text.split("\n")
    fenced = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            fenced = not fenced
        # A contents line is a rule's ID, tier and title by
        # construction, and `layout` exempts it for that reason:
        # wrapping it breaks the contents.
        contents = re.match(r"^\s*- [A-Z]{2}-[A-Z]+-\d+", line)
        if (
            fenced
            or len(line) <= width
            or line.lstrip().startswith(("|", "#"))
            or contents
        ):
            i += 1
            continue
        cut = _cut(line, width)
        head = line[:cut].rstrip() if cut > len(line) - len(line.lstrip()) else ""
        if not head:
            i += 1
            continue
        moved = line[cut + 1 :]
        item = re.match(r"^(\s*)(?:[-*] |\d+\. )", line)
        indent = " " * len(
            item.group(0) if item else line[: len(line) - len(line.lstrip())]
        )
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        lines[i] = head
        if nxt.strip() and not _STARTS_BLOCK.match(nxt):
            lines[i + 1] = f"{indent}{moved} {nxt.lstrip()}"
        else:
            lines.insert(i + 1, f"{indent}{moved}")
        i += 1
    return "\n".join(lines)


def _cut(line: str, width: int) -> int:
    """The last space at or before `width` outside a code span, or -1.

    A break inside `` `rg -n '… *='` `` puts a newline into the command
    a reader copies, and `dialect` rightly fails it.
    """
    best, ticks = -1, 0
    for i, ch in enumerate(line[: width + 1]):
        if ch == "`":
            ticks += 1
        elif ch == " " and ticks % 2 == 0:
            best = i
    return best
