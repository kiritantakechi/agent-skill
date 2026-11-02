"""bevy-style: its own `[M]` rules, applied to its own examples.

Most of this standard's mechanical rules are already `rg` commands in
their own `**Check:**`, which the self-application check runs —
including the whole forbidden-API table, so an example written against
an older Bevy fails the build. What is here is what a line-oriented
pattern cannot decide: whether a derive list contains a name, and
whether a type's name matches the trait it implements.
"""

import re
from dataclasses import dataclass, field
from typing import override
lazy from collections.abc import Iterable, Iterator

from agent_skill.lang.rust import BEVY_STYLE, Crate
from agent_skill.profiles import NotDecisive, Profile, register
from agent_skill.report import Finding, fail
from agent_skill.text import group
lazy from agent_skill.model import Block, Skill

#: `#[derive(Component, Debug, …)]`, possibly wrapped across lines by
#: rustfmt.
DERIVE = re.compile(r"#\[derive\(([^)]*)\)\]", re.DOTALL)

#: A component declaration, with whatever attributes sit above it.
COMPONENT = re.compile(
    r"(?P<attrs>(?:#\[[^\]]*\]\n)*)(?:pub )?struct (?P<name>\w+)"
    r"(?:\((?P<tuple>[^)]*)\)\s*;|\s*\{(?P<named>[^}]*)\}|\s*;)",
    re.DOTALL,
)

#: An attribute on a field, which `pub` follows rather than precedes.
FIELD_ATTR = re.compile(r"#\[[^\]]*\]\s*")

#: BV-ECS-03 on every component; BV-ECS-09 adds the rest on a marker.
DATA_DERIVES = ("Debug", "Reflect")
MARKER_DERIVES = ("Debug", "Clone", "Copy", "Default", "Reflect")

#: BV-ARCH-10 — the two traits whose implementors carry a suffix.
SUFFIX = {"Plugin": "Plugin", "SystemSet": "Systems"}

IMPL_PLUGIN = re.compile(r"^impl Plugin for (\w+)", re.MULTILINE)


@dataclass
class BevyStyle(Profile):
    """What bevy-style's checks need to know about it."""

    name: str = "bevy-style"
    prefix: str = "BV"
    languages: tuple[str, ...] = ("rust",)
    marked_languages: tuple[str, ...] = ("toml", "bash", "yaml")
    toolchain: str = "rust"
    tools: tuple[str, ...] = ("rustc", "clippy", "rustdoc")
    language: str = "Bevy"
    library: str = "bevy"
    verified_as: str = (
        "compiles as written against Bevy {pin} on Rust {rust}, edition 2024"
    )
    strict_scope: str = "shipped and long-running"
    delta_step: str = (
        "**Load `rust-style` as well** for anything that is a Rust question "
        "rather than a Bevy question."
    )
    anchor: str = "rust-style"
    crate: Crate | None = BEVY_STYLE
    #: Each snippet is the defect its rule forbids, written the way it
    #: turns up in real code. A fixture shaped to match proves the
    #: fixture, not the pattern.
    fires: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "BV-EVENT-09": ("commands.trigger_targets(Damage(5), target);",),
            "BV-MIG-14": (
                "fn on_enemy_added(add: On<Add, Enemy>, mut commands: Commands) {",
                (
                    "let observer = Observer::new("
                    '|add: On<Add>| info!("{}", add.entity))'
                    ".with_component(health);"
                ),
            ),
            "BV-MIG-15": (
                (
                    "fn start_game(click: On<Pointer<Click>>, "
                    "mut starts: ResMut<Starts>) {"
                ),
                (
                    'info!("{:?} at {}", press.pointer_id, '
                    "press.pointer_location.position);"
                ),
            ),
            "BV-MIG-16": (
                "next.as_mut().set_if_neq(Screen::Playing);",
                (
                    "fn style_buttons("
                    "mut buttons: Query<(&Interaction, &mut BackgroundColor)>) {"
                ),
                "let mut placeholder: AssetId<Image> = AssetId::invalid();",
            ),
            "BV-MIG-17": (
                "app.add_plugins(EditableTextInputPlugin);",
                "TextFont { font: FontSource::SansSerif, ..default() },",
                "TextFont { font: FontSource::SystemUi, ..default() },",
                "commands.spawn((Mesh3d(mesh), MeshMaterial3d(material), MeshTag(7)));",
                "let default = <ReflectDefault as FromType<Settings>>::from_type();",
                "use bevy_math::primitives::Circle;",
                'let atlas = server.load_with_settings("atlas.png", srgb);',
                "#import bevy_pbr::forward_io::VertexOutput",
            ),
        }
    )
    #: Each of these ships an `rg` pattern that no fixture in `fires`
    #: proves yet. Giving one a fixture means deleting it here, which
    #: `sensitivity` insists on, so the list only shrinks.
    unproven: frozenset[str] = frozenset(
        {
            "BV-ARCH-09",
            "BV-EVENT-14",
            "BV-MIG-01",
            "BV-MIG-03",
            "BV-MIG-04",
            "BV-MIG-05",
            "BV-MIG-06",
            "BV-MIG-07",
            "BV-MIG-08",
            "BV-MIG-09",
            "BV-MIG-10",
            "BV-MIG-11",
            "BV-MIG-12",
            "BV-MIG-13",
        }
    )
    #: Measured, not judged: each of these was promoted to accuse and
    #: hit the standard's own compliant examples. The reason names what
    #: the span finds and what, outside the match, decides whether the
    #: hit is a defect — never how many examples it hit the day someone
    #: measured, which is a number `_render` already prints live two
    #: fields away and nothing re-measures.
    not_decisive: dict[str, NotDecisive] = field(
        default_factory=lambda: {
            "BV-ECS-11": NotDecisive(
                "Vec<Entity>",
                "the span finds every `Vec<Entity>`; whether that link is a "
                "relationship, or carries a written reason it cannot be one, decides",
            ),
            "BV-ECS-13": NotDecisive(
                "Handle<",
                "the span finds every handle; whether it sits bare inside a `spawn` "
                "tuple rather than in a component of its own decides",
            ),
            "BV-MIG-18": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether the receiver is a `Ref<`, "
                "where the call's meaning changed, decides — and the type is not on "
                "the line",
            ),
            "BV-SCHED-08": NotDecisive(
                "just_pressed",
                "the span finds every input read; whether the system runs in "
                "`FixedUpdate` rather than `Update` decides, and the schedule is not "
                "on the line",
            ),
            "BV-SCHED-12": NotDecisive(
                "configure_sets",
                "the span finds every set configuration; whether that set is "
                "configured more than once decides, which is a fact about the whole "
                "file",
            ),
            "BV-SCHED-23": NotDecisive(
                "run_if",
                "the span finds every run condition; whether it gates on a `paused` "
                "flag rather than on `Time<Virtual>` decides",
            ),
            "BV-STATE-03": NotDecisive(
                "insert_resource",
                "the span finds every `insert_resource`; whether it is inside a "
                "`Startup` system, and whether the value depends on the world, decides",
            ),
            "BV-TEST-07": NotDecisive(
                "entities().len()",
                "the span finds every entity count; whether the assert is about a "
                "total rather than about the component the test cares about decides",
            ),
            "BV-VIEW-04": NotDecisive(
                "Text::new",
                "the span finds every text spawn; whether the same tuple also carries "
                "a font and a colour decides, which the matched line does not show",
            ),
        }
    )

    @override
    def pin(self) -> str:
        """The exact `bevy` version the verified crate depends on."""
        for dep in self.crate.dependencies if self.crate else ():
            if m := re.match(r'bevy = \{ version = "=([0-9][^"]*)"', dep):
                return group(m)
        return ""

    @override
    def conventions(self, skill: Skill) -> Iterable[Finding]:
        """bevy-style's own rules, applied to its own examples."""
        for b in skill.advice("rust"):
            yield from _component_shape(b)
            yield from _suffixes(b)


def _component_shape(block: Block) -> Iterator[Finding]:
    """What every component in this standard's examples must look like.

    BV-ECS-01 public fields, BV-ECS-03 `Debug` and `Reflect` with
    `#[reflect(Component)]`, BV-ECS-09 the marker set. None of the three
    is searchable, and all three had drifted: 25 of 33 components
    carried no `Reflect` at all while BV-ECS-03 was `[M]`.
    """
    for m in COMPONENT.finditer(block.body):
        attrs, name = m.group("attrs"), m.group("name")
        derives: set[str] = set()
        for d in DERIVE.finditer(attrs):
            derives |= {t.strip() for t in d.group(1).split(",")}
        if "Component" not in derives:
            continue
        line = block.at(block.body[: m.start()].count(chr(10)))
        where = f"{block.file}:{line} [{block.rule}]"

        fields = (group(m, "tuple") or group(m, "named")).strip()
        want = MARKER_DERIVES if not fields else DATA_DERIVES
        for trait in want:
            if trait not in derives:
                yield fail(
                    f"BV-ECS-03/10: component `{name}` does not derive `{trait}`", where
                )
        if "#[reflect(Component)]" not in attrs:
            yield fail(
                f"BV-ECS-03: component `{name}` has no `#[reflect(Component)]`", where
            )

        # The collection side of a relationship is the one component
        # whose field is private, because the engine maintains it.
        # Bevy's own `Children` is declared exactly this way.
        if "relationship_target" in attrs:
            continue
        for member in (f.strip() for f in fields.split(",") if f.strip()):
            if not FIELD_ATTR.sub("", member).strip().startswith("pub "):
                yield fail(f"BV-ECS-01: `{name}` has a private field — {member}", where)


def _suffixes(block: Block) -> Iterator[Finding]:
    """BV-ARCH-09 and BV-ARCH-10 — a plugin type's name and derives.

    A plugin written as a function is caught by BV-ARCH-09's own
    pattern, which the self-application check runs. What is left for
    here is the type: its name, and that it carries the derives every
    plugin type carries.
    """
    for m in IMPL_PLUGIN.finditer(block.body):
        name = m.group(1)
        line = block.at(block.body[: m.start()].count("\n"))
        where = f"{block.file}:{line} [{block.rule}]"
        if not name.endswith(SUFFIX["Plugin"]):
            yield fail(
                f"BV-ARCH-10: `{name}` implements `Plugin` "
                "and does not end in `Plugin`",
                where,
            )
        declared = re.search(
            rf"((?:#\[[^\]]*\]\s*)*)\bpub struct {re.escape(name)}\b", block.body
        )
        if declared is None:
            continue  # declared elsewhere; the block only shows the impl
        derives = set()
        for d in DERIVE.finditer(declared.group(1)):
            derives |= {t.strip() for t in d.group(1).split(",")}
        for required in ("Debug", "Default"):
            if required not in derives:
                yield fail(
                    f"BV-ARCH-09: plugin type `{name}` does not derive `{required}`",
                    where,
                )

    lines = block.lines
    for i, line in enumerate(lines):
        if "derive(" not in line or "SystemSet" not in line:
            continue
        decl = next(
            (ln for ln in lines[i + 1 : i + 3] if re.search(r"\b(struct|enum)\b", ln)),
            "",
        )
        name = re.search(r"\b(?:struct|enum)\s+(\w+)", decl)
        if name and not name.group(1).endswith(SUFFIX["SystemSet"]):
            yield fail(
                f"BV-ARCH-10: `{name.group(1)}` derives `SystemSet` "
                "and does not end in `Systems`",
                f"{block.file}:{block.at(i)} [{block.rule}]",
            )


register(BevyStyle())
