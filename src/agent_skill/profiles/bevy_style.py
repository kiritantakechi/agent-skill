"""bevy-style: its own `[M]` rules, applied to its own examples.

Most of this standard's mechanical rules are already `grep` commands in their own
`**Check:**`, which the self-application check runs — including the whole
forbidden-API table, so an example written against an older Bevy fails the build.
What is here is what a line-oriented grep cannot decide: whether a derive list
contains a name, and whether a type's name matches the trait it implements.
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

#: A component declaration, with whatever attributes sit above it.
COMPONENT = re.compile(
    r"(?P<attrs>(?:#\[[^\]]*\]\n)*)(?:pub )?struct (?P<name>\w+)"
    r"(?:\((?P<tuple>[^)]*)\)\s*;|\s*\{(?P<named>[^}]*)\}|\s*;)",
    re.S,
)

#: An attribute on a field, which `pub` follows rather than precedes.
FIELD_ATTR = re.compile(r"#\[[^\]]*\]\s*")

#: BV-ECS-03 on every component; BV-ECS-10 adds the rest on a marker.
DATA_DERIVES = ("Debug", "Reflect")
MARKER_DERIVES = ("Debug", "Clone", "Copy", "Default", "Reflect")

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
            yield from _component_shape(b)
            yield from _suffixes(b)


def _component_shape(block) -> Iterable[Finding]:
    """What every component in this standard's own examples must look like.

    BV-ECS-01 public fields, BV-ECS-03 `Debug` and `Reflect` with
    `#[reflect(Component)]`, BV-ECS-10 the marker set. None of the three is
    greppable, and all three had drifted: 25 of 33 components carried no
    `Reflect` at all while BV-ECS-03 was `[M]`.
    """
    for m in COMPONENT.finditer(block.body):
        attrs, name = m.group("attrs"), m.group("name")
        derives: set[str] = set()
        for d in DERIVE.finditer(attrs):
            derives |= {t.strip() for t in d.group(1).split(",")}
        if "Component" not in derives:
            continue
        where = f"{block.file}:{block.at(block.body[: m.start()].count(chr(10)))} [{block.rule}]"

        fields = (m.group("tuple") or m.group("named") or "").strip()
        want = MARKER_DERIVES if not fields else DATA_DERIVES
        for trait in want:
            if trait not in derives:
                yield fail(f"BV-ECS-03/10: component `{name}` does not derive `{trait}`", where)
        if "#[reflect(Component)]" not in attrs:
            yield fail(f"BV-ECS-03: component `{name}` has no `#[reflect(Component)]`", where)

        # The collection side of a relationship is the one component whose field
        # is private, because the engine maintains it. Bevy's own `Children` is
        # declared exactly this way.
        if "relationship_target" in attrs:
            continue
        for field in (f.strip() for f in fields.split(",") if f.strip()):
            if not FIELD_ATTR.sub("", field).strip().startswith("pub "):
                yield fail(f"BV-ECS-01: `{name}` has a private field — {field}", where)


def _suffixes(block) -> Iterable[Finding]:
    """BV-ARC-09 and BV-ARC-10 — what a plugin type is called, and what it derives.

    A plugin written as a function is caught by BV-ARC-09's own `grep`, which the
    self-application check runs. What is left for here is the type: its name, and
    that it carries the derives every plugin type carries.
    """
    for m in IMPL_PLUGIN.finditer(block.body):
        name = m.group(1)
        line = block.at(block.body[: m.start()].count("\n"))
        where = f"{block.file}:{line} [{block.rule}]"
        if not name.endswith(SUFFIX["Plugin"]):
            yield fail(
                f"BV-ARC-10: `{name}` implements `Plugin` and does not end in `Plugin`", where
            )
        declared = re.search(rf"((?:#\[[^\]]*\]\s*)*)\bpub struct {re.escape(name)}\b", block.body)
        if declared is None:
            continue  # declared elsewhere; the block only shows the impl
        derives = set()
        for d in DERIVE.finditer(declared.group(1)):
            derives |= {t.strip() for t in d.group(1).split(",")}
        for required in ("Debug", "Default"):
            if required not in derives:
                yield fail(f"BV-ARC-09: plugin type `{name}` does not derive `{required}`", where)

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


register(BevyStyle())
