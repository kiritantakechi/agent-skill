"""bevy-style: its own `[M]` rules, applied to its own examples.

Most of this standard's mechanical rules are already `grep` commands in their own
`**Check:**`, which the self-application check runs — including the whole
forbidden-API table, so an example written against an older Bevy fails the build.
What is here is the two that a line-oriented grep cannot decide: whether a derive
list contains a name, and whether a type's name matches the trait it implements.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ..lang.rust import BEVY_STYLE, Crate
from ..report import Finding, fail
from . import Profile, register

#: `#[derive(Component, Debug, …)]`, possibly wrapped across lines by rustfmt.
DERIVE = re.compile(r"#\[derive\(([^)]*)\)\]", re.S)

#: BV-ARC-10 — the two traits whose implementors carry a suffix.
SUFFIX = {"Plugin": "Plugin", "SystemSet": "Systems"}

IMPL_PLUGIN = re.compile(r"^impl Plugin for (\w+)", re.M)


@dataclass
class BevyStyle(Profile):
    name: str = "bevy-style"
    prefix: str = "BV"
    languages: tuple[str, ...] = ("rust",)
    marked_languages: tuple[str, ...] = ("toml", "bash", "yaml")
    toolchain: str | None = "rust"
    crate: Crate | None = BEVY_STYLE

    def conventions(self, skill) -> Iterable[Finding]:
        for b in skill.blocks("rust"):
            # A BAD block and a quotation are evidence rather than advice.
            if b.marker.evidence:
                continue
            yield from _debug_on_components(b)
            yield from _suffixes(b)


def _debug_on_components(block) -> Iterable[Finding]:
    """BV-ECS-03 — every component derives `Debug`."""
    for m in DERIVE.finditer(block.body):
        traits = {t.strip() for t in m.group(1).split(",")}
        if "Component" in traits and "Debug" not in traits:
            line = block.at(block.body[: m.start()].count("\n"))
            yield fail(
                f"BV-ECS-03: a component whose derive list has no `Debug` — {m.group(1).strip()}",
                f"{block.file}:{line} [{block.rule}]",
            )


def _suffixes(block) -> Iterable[Finding]:
    """BV-ARC-10 — a `Plugin` type ends in `Plugin`, a `SystemSet` in `Systems`."""
    for m in IMPL_PLUGIN.finditer(block.body):
        if not m.group(1).endswith(SUFFIX["Plugin"]):
            line = block.at(block.body[: m.start()].count("\n"))
            yield fail(
                f"BV-ARC-10: `{m.group(1)}` implements `Plugin` and does not end in `Plugin`",
                f"{block.file}:{line} [{block.rule}]",
            )

    lines = block.lines
    for i, line in enumerate(lines):
        if "derive(" not in line or "SystemSet" not in line:
            continue
        decl = next((ln for ln in lines[i + 1 : i + 3] if re.search(r"\b(struct|enum)\b", ln)), "")
        name = re.search(r"\b(?:struct|enum)\s+(\w+)", decl)
        if name and not name.group(1).endswith(SUFFIX["SystemSet"]):
            yield fail(
                f"BV-ARC-10: `{name.group(1)}` derives `SystemSet` and does not end in `Systems`",
                f"{block.file}:{block.at(i)} [{block.rule}]",
            )


PROFILE = register(BevyStyle())
