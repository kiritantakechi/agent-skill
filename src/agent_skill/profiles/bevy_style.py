"""bevy-style: its own `[M]` rules, applied to its own examples.

Most of this standard's mechanical rules are already `rg` commands in
their own `**Check:**`, which the self-application check runs —
including the whole forbidden-API table, so an example written against
an older Bevy fails the build. What is here is what a line-oriented
pattern cannot decide: whether a derive list contains a name, and
whether a type's name matches the trait it implements.
"""

import re
from dataclasses import replace
lazy from collections.abc import Iterator

from agent_skill.lang.rust import BEVY, BEVY_STYLE, RUST_STYLE
from agent_skill.profiles.record import (
    Delta,
    NotDecisive,
    Profile,
    keyed,
    rules,
)
from agent_skill.report import Finding, Level, declare, fail
from agent_skill.text import group
lazy from agent_skill.model import Block

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

# The branches of `conventions` this standard's own rules fire through.
COMPONENT_DERIVE = declare("conventions", "bv_component_derive", Level.FAIL)
COMPONENT_REFLECT = declare("conventions", "bv_component_reflect", Level.FAIL)
PRIVATE_FIELD = declare("conventions", "bv_private_field", Level.FAIL)
PLUGIN_SUFFIX = declare("conventions", "bv_plugin_suffix", Level.FAIL)
PLUGIN_DERIVE = declare("conventions", "bv_plugin_derive", Level.FAIL)
SET_SUFFIX = declare("conventions", "bv_set_suffix", Level.FAIL)

#: The verified crate under its anchor's `clippy.toml`: a delta ships
#: only the assets it departs in, and clippy's settings are not one of
#: them, so the configuration is `rust-style`'s itself, not a copy.
CRATE = replace(BEVY_STYLE, clippy=RUST_STYLE.clippy)


def component_shape(block: Block) -> Iterator[Finding]:
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
        where = block.where_at(block.body[: m.start()].count(chr(10)))

        fields = (group(m, "tuple") or group(m, "named")).strip()
        want = MARKER_DERIVES if not fields else DATA_DERIVES
        for trait in want:
            if trait not in derives:
                yield fail(
                    f"BV-ECS-03/10: component `{name}` does not derive `{trait}`",
                    where,
                    COMPONENT_DERIVE,
                )
        if "#[reflect(Component)]" not in attrs:
            yield fail(
                f"BV-ECS-03: component `{name}` has no `#[reflect(Component)]`",
                where,
                COMPONENT_REFLECT,
            )

        # The collection side of a relationship is the one component
        # whose field is private, because the engine maintains it.
        # Bevy's own `Children` is declared exactly this way.
        if "relationship_target" in attrs:
            continue
        for member in (f.strip() for f in fields.split(",") if f.strip()):
            if not FIELD_ATTR.sub("", member).strip().startswith("pub "):
                yield fail(
                    f"BV-ECS-01: `{name}` has a private field — {member}",
                    where,
                    PRIVATE_FIELD,
                )


def suffixes(block: Block) -> Iterator[Finding]:
    """BV-ARCH-09 and BV-ARCH-10 — a plugin type's name and derives.

    A plugin written as a function is caught by BV-ARCH-09's own
    pattern, which the self-application check runs. What is left for
    here is the type: its name, and that it carries the derives every
    plugin type carries.
    """
    for m in IMPL_PLUGIN.finditer(block.body):
        name = m.group(1)
        where = block.where_at(block.body[: m.start()].count("\n"))
        if not name.endswith(SUFFIX["Plugin"]):
            yield fail(
                f"BV-ARCH-10: `{name}` implements `Plugin` "
                "and does not end in `Plugin`",
                where,
                PLUGIN_SUFFIX,
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
                    PLUGIN_DERIVE,
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
                block.where_at(i),
                SET_SUFFIX,
            )


PROFILE = Profile(
    name="bevy-style",
    prefix="BV",
    languages=("rust",),
    marked_languages=("toml", "bash", "yaml"),
    tools=("rustc", "clippy", "rustdoc"),
    language="Bevy",
    verified_as=(
        "compiles as written against Bevy {pin} on Rust {toolchain}, edition 2024"
    ),
    # rust-style's: a delta's `[M!]` is its anchor's (normalize-the-
    # standards, decision 10), and SKILL.md says how a game reads it.
    strict_scope="library and high-reliability",
    delta=Delta(
        anchor="rust-style",
        step=(
            "**Load `rust-style` as well** for anything that is a Rust question "
            "rather than a Bevy question."
        ),
    ),
    toolchain=CRATE,
    # The engine, not the language: what the H1 names.
    subject=BEVY.pin,
    # Compared with rust-style for tier, as every standard is.
    # Each snippet is the defect its rule forbids, written the way it
    # turns up in real code. A fixture shaped to match proves the
    # fixture, not the pattern.
    fires=keyed(
        {
            "BV-EVENT-08": ("commands.trigger_targets(Damage(5), target);",),
            "BV-ARCH-12": ("    fn is_unique(&self) -> bool {",),
            "BV-ASSET-03": (
                (
                    "const LOGO: Handle<Image> = "
                    'uuid_handle!("1347c9b7-c46a-48e7-b7b8-023a354b7cac");'
                ),
            ),
            "BV-ASSET-10": (
                'let level = std::fs::read_to_string("assets/levels/1.ron")?;',
            ),
            "BV-BUILD-01": ('bevy_ecs = "0.20"',),
            "BV-BUILD-08": (
                'bevy = { version = "=0.20.1", features = ["2d", "dynamic_linking"] }',
            ),
            "BV-BUILD-11": ("app.add_plugins(RenderDebugOverlayPlugin::default());",),
            "BV-ECS-05": ("#[non_exhaustive]",),
            "BV-ECS-06": (
                "#[derive(Bundle, Default)]",
                "fn enemy_bundle() -> impl Bundle {",
            ),
            "BV-EVENT-03": ("#[derive(Message, Event, Debug, Clone)]",),
            "BV-EVENT-04": ("app.init_resource::<Messages<DamageDealt>>();",),
            "BV-EVENT-05": ("for hit in hits.iter_current_update_messages() {",),
            "BV-EVENT-09": ("let victim = trigger.target();",),
            "BV-EVENT-11": ("impl SetEntityEventTarget for Died {",),
            "BV-EVENT-18": (
                "fn on_died(trigger: On<Died>, mut score: ResMut<Score>) {",
            ),
            "BV-SCHED-20": (
                (
                    "app.add_systems("
                    "Update, (spawn_wave, ApplyDeferred, count_wave).chain());"
                ),
            ),
            "BV-SCHED-22": ("schedule.set_executor(SingleThreadedExecutor::new());",),
            "BV-STATE-10": ("pub struct Paused(pub bool);",),
            "BV-STATE-16": ("fn force_menu(mut state: ResMut<State<Screen>>) {",),
            "BV-TEST-05": ("std::thread::sleep(Duration::from_millis(20));",),
            "BV-VIEW-15": (
                "fn hide(mut views: Query<&mut ViewVisibility, With<Ghost>>) {",
            ),
            "BV-VIEW-16": (
                "fn refit(mut boxes: Query<&mut Aabb>) {",
                "commands.entity(ghost).remove::<Aabb>();",
            ),
            "BV-EVENT-13": (
                "fn on_spawn(trigger: Trigger<OnAdd, Enemy>, mut commands: Commands) {",
                "fn on_enemy_added(add: On<Add, Enemy>, mut commands: Commands) {",
                (
                    "let observer = Observer::new("
                    '|add: On<Add>| info!("{}", add.entity))'
                    ".with_component(health);"
                ),
            ),
            "BV-STATE-02": ("fn sweep(all: Query<Entity>, mut commands: Commands) {",),
            "BV-STATE-17": ("next.as_mut().set_if_neq(Screen::Playing);",),
            "BV-VIEW-06": (
                (
                    "fn style_buttons("
                    "mut buttons: Query<(&Interaction, &mut BackgroundColor)>) {"
                ),
            ),
            "BV-VIEW-04": (
                "TextFont { font: FontSource::SansSerif, ..default() },",
                "TextFont { font: FontSource::SystemUi, ..default() },",
            ),
            "BV-VIEW-18": ("#import bevy_pbr::forward_io::VertexOutput",),
            "BV-ASSET-07": (
                'let atlas = server.load_with_settings("atlas.png", srgb);',
            ),
            "BV-MIG-02": (
                "commands.spawn((Mesh3d(mesh), MeshMaterial3d(material), MeshTag(7)));",
                "Sprite { anchor: Anchor::Center, ..default() },",
            ),
            "BV-MIG-03": ("let mut placeholder: AssetId<Image> = AssetId::invalid();",),
        }
    ),
    # Each of these ships an `rg` pattern that no fixture in `fires`
    # proves yet. Giving one a fixture means deleting it here, which
    # `sensitivity` insists on, so the list only shrinks.
    unproven=rules("BV-ARCH-09"),
    # Measured, not judged: each of these was promoted to accuse and
    # hit the standard's own compliant examples. The reason names what
    # the span finds and what, outside the match, decides whether the
    # hit is a defect — never how many examples it hit the day someone
    # measured, which is a number `_render` already prints live two
    # fields away and nothing re-measures.
    not_decisive=keyed(
        {
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
            "BV-MIG-04": NotDecisive(
                ".clone()",
                "the span finds every `.clone()`; whether the receiver is a `Ref<`, "
                "where the call's meaning changed, decides — and the type is not on "
                "the line",
            ),
            "BV-SCHED-09": NotDecisive(
                "just_pressed",
                "the span finds every input read; whether the system runs in "
                "`FixedUpdate` rather than `Update` decides, and the schedule is not "
                "on the line",
            ),
            "BV-SCHED-13": NotDecisive(
                "configure_sets",
                "the span finds every set configuration; whether that set is "
                "configured more than once decides, which is a fact about the whole "
                "file",
            ),
            "BV-SCHED-24": NotDecisive(
                "run_if",
                "the span finds every run condition; whether it gates on a `paused` "
                "flag rather than on `Time<Virtual>` decides",
            ),
            "BV-STATE-04": NotDecisive(
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
    ),
    structural=(component_shape, suffixes),
)
