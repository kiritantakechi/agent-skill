# UI and Rendering: The Half a Game Writes

Scope: the components a game spawns to put something on the screen — UI nodes, text, buttons,
cameras, visibility, materials and gizmos. The engine's rendering internals are out of scope: the
render graph became a set of systems in 0.19, pipeline specialisation changed with it, and neither
is something a game should be reaching into.

This is the area that changes most between releases, so `references/migration.md` is the companion
chapter: the 0.15 bundle removal, the 0.15 text rework and the 0.19 text-backend change all land
here.

## Contents

- **UI**
  - BV-VIEW-01 [M] Lay out with `Node` and children, not with absolute positions
  - BV-VIEW-02 [S] Choose the `Val` unit for what the value means
  - BV-VIEW-03 [M] Read computed layout from `ComputedNode`, never from `Node`
  - BV-VIEW-04 [M] Give text its components together
  - BV-VIEW-05 [S] Compose a mixed-style run from `TextSpan` children
  - BV-VIEW-06 [M] React to a button with an observer, not by polling `Interaction`
  - BV-VIEW-07 [S] Reach for `bevy_ui_widgets` before writing a widget
  - BV-VIEW-08 [S] Reach for `TextInput` before a text-input crate
  - BV-VIEW-09 [S] Build a nested UI tree with `bsn!`

- **Colour**
  - BV-VIEW-10 [M] Construct a colour by naming its space
  - BV-VIEW-11 [S] Keep the whole game in one colour space until the boundary

- **Cameras and visibility**
  - BV-VIEW-12 [M] Spawn a camera as `Camera2d` or `Camera3d`
  - BV-VIEW-13 [M] Give every camera an explicit `order` once there are two
  - BV-VIEW-14 [S] Put a render target on the camera as its own component
  - BV-VIEW-15 [M] Set `Visibility`, and read `ViewVisibility`
  - BV-VIEW-16 [M] Do not maintain `Aabb` by hand

- **Materials and debugging**
  - BV-VIEW-17 [S] Reach for a custom `Material` before a custom render node
  - BV-VIEW-18 [M] Keep shader paths and material types together
  - BV-VIEW-19 [S] Debug in world space with gizmos
  - BV-VIEW-20 [S] Reach for a post-process component before a full-screen pass
  - BV-VIEW-21 [S] Draw with a retained gizmo before a sprite you have to despawn

---

## UI

### BV-VIEW-01 [M] Lay out with `Node` and children, not with absolute positions

`Node` is a flexbox node. Rows, columns, gaps and alignment do the layout; `PositionType::Absolute`
is for overlays.

**Why:** an absolute position is a layout evaluated once, by hand, at one window size. It breaks at
every other resolution, every UI scale factor and every longer string, and still looks right to
whoever wrote it.

**Check:** count the `Val::Px` values in `left`, `top`, `right` and `bottom`. Each one is a position
that will be wrong at another size.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct HudBar;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Slot;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct DimOverlay;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Hud {
    pub compact: bool,
}

/// Three slots in a row. The gap, the padding and the alignment place them,
/// so the bar is right at every resolution and every UI scale factor.
fn spawn_hud(mut commands: Commands) {
    commands.spawn((
        HudBar,
        Node {
            width: Val::Percent(100.0),
            height: Val::Px(48.0),
            flex_direction: FlexDirection::Row,
            align_items: AlignItems::Center,
            justify_content: JustifyContent::SpaceBetween,
            column_gap: Val::Px(16.0),
            row_gap: Val::Px(8.0),
            padding: UiRect::horizontal(Val::Px(24.0)),
            ..default()
        },
        children![
            (Slot, Node::default()),
            (Slot, Node::default()),
            (Slot, Node::default()),
            // What absolute positioning is actually for: something that
            // leaves the flow. It still names no edge — a full-bleed child
            // is two percentages, not four pixel offsets.
            (
                DimOverlay,
                Node {
                    position_type: PositionType::Absolute,
                    width: Val::Percent(100.0),
                    height: Val::Percent(100.0),
                    ..default()
                },
            ),
        ],
    ));
}

/// A narrow window stacks the bar. Flex makes that one field; with hand-placed
/// edges it is every child. The guard is BV-ECS-25 for a single field —
/// `Mut<Node>` marks the whole component, and the engine's layout watches it.
fn stack_when_narrow(hud: Res<Hud>, mut bars: Query<&mut Node, With<HudBar>>) {
    let wanted = if hud.compact {
        FlexDirection::Column
    } else {
        FlexDirection::Row
    };
    for mut bar in &mut bars {
        if bar.flex_direction != wanted {
            bar.flex_direction = wanted;
        }
    }
}

/// The plugin's published ordering surface. Anything that needs to run after the
/// bar has been restacked — another plugin, or the test below — names this, never
/// `stack_when_narrow`, which stays free to be renamed or split (BV-SCHED-14).
#[derive(SystemSet, Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum HudSystems {
    /// Rewrites the bar's `flex_direction` from `Hud::compact`.
    Stack,
}

#[derive(Debug, Default)]
pub struct HudPlugin;

impl Plugin for HudPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Hud>()
            .add_systems(Startup, spawn_hud)
            .add_systems(Update, stack_when_narrow.in_set(HudSystems::Stack));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Resource, Debug, Default, Reflect)]
    #[reflect(Resource)]
    struct Relayouts(usize);

    fn count_relayouts(dirty: Query<(), Changed<Node>>, mut relayouts: ResMut<Relayouts>) {
        relayouts.0 += dirty.iter().count();
    }

    /// The rule's own check, mechanised: no `left`, `right`, `top` or
    /// `bottom` anywhere in the tree is a value someone will have to redo.
    #[test]
    fn nothing_in_the_tree_names_an_edge() {
        let mut app = App::new();
        app.add_plugins(HudPlugin);
        app.update();

        let mut nodes = app.world_mut().query::<&Node>();
        assert_eq!(nodes.iter(app.world()).count(), 5);
        let placed = nodes
            .iter(app.world())
            .filter(|n| {
                [n.left, n.right, n.top, n.bottom]
                    .iter()
                    .any(|v| *v != Val::Auto)
            })
            .count();
        assert_eq!(placed, 0);
    }

    #[test]
    fn going_compact_rewrites_one_field_once() {
        let mut app = App::new();
        app.add_plugins(HudPlugin)
            .init_resource::<Relayouts>()
            .add_systems(Update, count_relayouts.after(HudSystems::Stack));
        app.update();
        app.update();
        let settled = app.world().resource::<Relayouts>().0;

        app.world_mut().resource_mut::<Hud>().compact = true;
        app.update();
        app.update();

        let mut bars = app.world_mut().query_filtered::<&Node, With<HudBar>>();
        let directions: Vec<FlexDirection> =
            bars.iter(app.world()).map(|b| b.flex_direction).collect();
        assert_eq!(directions, [FlexDirection::Column]);
        assert_eq!(app.world().resource::<Relayouts>().0, settled + 1);
    }
}
```

### BV-VIEW-02 [S] Choose the `Val` unit for what the value means

`Px` for something that should stay the same size, `Percent` for something that should scale with
its parent, `Vw`/`Vh` for something that should scale with the window, `Em`/`Rem` (`em()`, `rem()`)
for something that should scale with the text size, `Auto` for something the content decides. Since
0.20 `Val::Em` resolves against the node's `EmSize`, which `Node` requires, and `Val::Rem` against
the `RemSize` resource.

**Why:** the unit is the only place the intent is recorded. A `Px` where a `Percent` was meant looks
right until the window changes, then looks broken with nothing to say why.

**Check:** for each `Val`, resize the window and the text in your head. If the value should have
changed and did not, the unit is wrong.

### BV-VIEW-03 [M] Read computed layout from `ComputedNode`, never from `Node`

`Node` is the input to layout. `ComputedNode` is the output.

**Why:** for anything sized by `Auto`, a percentage or a flex-grow, the requested value and the
laid-out one are different numbers. `Node` was the computed output before 0.15, so an old read of a
size from it still compiles.

**Check:** grep for reads of `Node` that are looking for a size or a position. Those fields are on
`ComputedNode`.

### BV-VIEW-04 [M] Give text its components together

`Text::new(s)` plus `TextFont` plus `TextColor`, spawned as one tuple. `Text2d` for world-space
text. Since 0.20 `TextFont::default()` sizes text at `FontSize::Rem(1.)`, not `Px(20.)`: it renders
the same until `RemSize` changes, so a size that must stay fixed is written as `FontSize::Px`.

**Why:** a missing component arrives as a required-component default: a colour nobody chose, and
since 0.20 a size that follows `RemSize`. One tuple also keeps the lines that describe one piece of
text together.

**Check:** grep for `Text::new` and check the same tuple carries a font and a colour.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct ScoreLabel;

fn spawn_hud(mut commands: Commands) {
    commands.spawn((
        ScoreLabel,
        Text::new("0"),
        TextFont {
            font_size: FontSize::Px(32.0),
            ..default()
        },
        TextColor(Color::srgb(0.9, 0.9, 0.9)),
        Node {
            margin: UiRect::all(Val::Px(12.0)),
            ..default()
        },
    ));
}
```

### BV-VIEW-05 [S] Compose a mixed-style run from `TextSpan` children

A line with two colours or two sizes is a `Text` root with `TextSpan` children, not a formatted
string.

**Why:** each span is an entity, so a styled part is queried, changed and animated alone: a score
inside a sentence is a write to one span, not a rebuild of the string. `TextFont` and `TextColor`
cover a whole entity, so spans are also the only way to get two styles.

**Check:** does the text change one part of a line frequently? If it is being rebuilt with
`format!`, that part is a span.

### BV-VIEW-06 [M] React to a button with an observer, not by polling `Interaction`

`commands.entity(button).observe(on_click)` with a `PointerClick` event, whose fields are flat:
`click.button`, not `click.event.button`. The button is `bevy::ui_widgets::Button`, imported by
name, because 0.20 deprecates the prelude `Button` and `Interaction`; `Hovered` and `Pressed` carry
the state a style needs, and under `UiWidgetsPlugins` the widget `Button` also emits `Activate`.

**Why:** a polling system runs every frame over every button to find the one that changed, and its
handler lives in another file. An entity-scoped observer sits beside the spawn, dies with the
button, and runs only when it is used.

**Check:** grep for `Query<&Interaction`. Each is a set of buttons whose handlers have been gathered
into one system.

```rust
// fragment — `PointerClick` comes from `bevy_picking`
use bevy::prelude::*;
use bevy::ui_widgets::Button;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct StartButton;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Starts(pub u32);

/// The reaction is registered on the entity that owns it, one line below the
/// spawn, and is despawned with it. A polled form runs every frame over every
/// button and puts this body in another file.
fn spawn_start_button(mut commands: Commands) {
    commands
        .spawn((
            StartButton,
            Button,
            Node {
                padding: UiRect::axes(Val::Px(24.0), Val::Px(12.0)),
                ..default()
            },
            children![(
                Text::new("Start"),
                TextFont {
                    font_size: FontSize::Px(24.0),
                    ..default()
                },
                TextColor(Color::srgb(0.95, 0.95, 0.95)),
            )],
        ))
        .observe(start_game);
}

/// Named after its event, and it runs only when this button is clicked.
fn start_game(click: On<PointerClick>, mut starts: ResMut<Starts>) {
    if click.button == PointerButton::Primary {
        starts.0 += 1;
    }
}

#[derive(Debug, Default)]
pub struct StartButtonPlugin;

impl Plugin for StartButtonPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Starts>()
            .add_systems(Startup, spawn_start_button);
    }
}
```

### BV-VIEW-07 [S] Reach for `bevy_ui_widgets` before writing a widget

Buttons, checkboxes, radio buttons, sliders, scrollbars, tabs (`TabList`/`Tab`), list boxes, menus,
dialogs, modals, popovers and text input ship in `bevy_ui_widgets`, which stopped being experimental
in 0.19. `bevy_feathers` is the styled layer above it.

**Why:** a hand-written slider is a week of edge cases — drag capture, keyboard focus,
accessibility, scroll interaction — and the shipped ones have had those weeks spent on them. They
are also where upstream's improvements land, so a hand-written one is a fork.

**Check:** is the widget on that list? Then the question is what the shipped one does not do.

### BV-VIEW-08 [S] Reach for `TextInput` before a text-input crate

0.19 put a real text field in the engine. Spawn `bevy::ui_widgets::TextInput`, which requires
`bevy_text::EditableText`: `EditableText` holds the content and the cursor, and `TextInputPlugin`,
part of `UiWidgetsPlugins` and called `EditableTextInputPlugin` before 0.20, wires the keyboard, the
pointer, focus and the clipboard to it. Since 0.20 an `EditableText` without `TextInput` compiles,
spawns and ignores the keyboard, and Escape in a focused field releases `InputFocus` and propagates
to its ancestors and the window.

`EditableText` is not in the prelude, so it is imported by name, and it derives neither `Debug` nor
`Reflect`, because it holds a `parley::PlainEditor`. BV-ECS-03 therefore cannot reach it, and a
component that holds one cannot derive `Reflect` either: keep the field's *value* in a component of
your own and let this one stay the editor.

**Why:** text editing is Unicode work wearing a string's clothes. Backspace removes a grapheme
cluster, the cursor moves by cluster, and on wasm a paste lands a frame or more after it is asked
for — every hand-rolled field gets those wrong in about that order.

**Check:** `queue_edit` is the only thing that changes the text. Assigning the string in place
leaves the cursor pointing into content that no longer exists. The queue drains in `PostUpdate`
under `EditableTextSystems`, so a reader in `Update` is looking at last frame's text. A spawn that
names `EditableText` and not `TextInput` is the inert field.

```rust
// verified — GOOD
use bevy::prelude::*;
use bevy::text::{EditableText, TextEdit};
use bevy::ui_widgets::TextInput;

/// The game's own fact about the field, which *can* reflect. `EditableText`
/// next to it owns the cursor and the Unicode; this owns the meaning.
#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct SeedEntry;

/// `TextInput` requires `EditableText`, which requires `TextLayout`,
/// `TextFont`, `TextColor`, `LineHeight` and `FontHinting`, so the spawn names
/// none of them — BV-ECS-06 supplies them. `EditableText` alone would spawn
/// and ignore the keyboard.
fn spawn_seed_entry(mut commands: Commands) {
    commands.spawn((SeedEntry, Node::default(), TextInput));
}

/// An edit is queued, never applied here: the engine applies it in `PostUpdate`
/// where it can move the cursor by the same rules that drew the glyphs.
fn paste_seed(mut fields: Query<&mut EditableText, With<SeedEntry>>) -> Result {
    let mut field = fields.single_mut()?;
    field.queue_edit(TextEdit::Insert("42".into()));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::ecs::system::RunSystemOnce as _;

    /// The required components arrive without being named, which is the half
    /// of this that a reader is most likely to write out by hand.
    #[test]
    fn the_field_brings_its_text_components() {
        let mut app = App::new();
        app.add_systems(Startup, spawn_seed_entry);
        app.update();

        let mut fields = app
            .world_mut()
            .query_filtered::<(&TextFont, &TextColor, &TextLayout), With<SeedEntry>>();
        assert_eq!(fields.iter(app.world()).count(), 1);
    }

    /// Queued, not applied: nothing has drained the queue yet, and that is
    /// exactly why reading the text back in `Update` would be wrong.
    #[test]
    fn an_edit_waits_for_post_update() {
        let mut app = App::new();
        app.add_systems(Startup, spawn_seed_entry);
        app.update();
        // The annotation is load-bearing: a system returning Bevy's `Result`
        // satisfies `IntoResult` two ways — as itself and as `Result<T,
        // BevyError>` — so `Out` is ambiguous without it (E0283). Naming
        // `()` picks the second, which folds a system error into the outer
        // `Err` where `is_ok` can see it.
        let ran: Result<(), _> = app.world_mut().run_system_once(paste_seed);
        assert!(ran.is_ok());

        let mut fields = app.world_mut().query::<&EditableText>();
        let queued = fields
            .single(app.world())
            .ok()
            .map(|f| f.pending_edits.len());
        assert_eq!(queued, Some(1));
    }
}
```

### BV-VIEW-09 [S] Build a nested UI tree with `bsn!`

`bsn!` from `bevy_scene` expresses a tree with its children inline. Reach for it once the UI nests
more than two levels; a two-component spawn stays a plain tuple.

The grammar is not Rust and is worth reading once, in its 0.20 form. Components are juxtaposed with
no separators. A `Component { field: value }` is a partial patch rather than a literal, so the other
fields keep their defaults, but an enum variant names every field. Entities in `Children [ … ]` are
separated by `--`; the commas and parentheses of 0.19 are deprecated. `{expr}` escapes back to Rust,
and a scene reference takes `@`: `@name`, `@make()`, `@{expr}`. `template_value(x)` is now just `x`,
and a bare list of entities is `bsn_list! { … }`. The tree is spawned with `spawn_scene`, from the
`CommandsSceneExt` trait — not `spawn`, because a scene is not a `Bundle` — and an `On<Ready>`
observer on it runs once the whole subtree has spawned.

**Why:** the alternative nests a `with_children` closure per level, so the indentation is the
structure. It is `[S]` because the grammar still moves: 0.20 deprecated the entity separators 0.19
introduced.

**Check:** count the closing braces at the end of the spawn. Past three levels, the tuple form has
stopped being readable.

```rust
// verified
use bevy::prelude::*;
use bevy::scene::{CommandsSceneExt, bsn};

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Menu;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Choice;

fn spawn_menu(mut commands: Commands) {
    commands.spawn_scene(bsn! {
        Menu
        Node { width: Val::Percent(100.0), row_gap: Val::Px(8.0) }
        Children [
            Choice Text("Play")
            --
            Choice Text("Quit")
        ]
    });
}

#[derive(Debug, Default)]
pub struct MenuPlugin;

impl Plugin for MenuPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Startup, spawn_menu);
    }
}
```

## Colour

### BV-VIEW-10 [M] Construct a colour by naming its space

`Color::srgb(r, g, b)` for a colour picked in a design tool. `Color::linear_rgb` and
`LinearRgba` for a value that is being computed.

**Why:** the two spaces give different numbers for one colour, and neither constructor warns: a
palette value passed to the linear one is visibly wrong, most of all in the mid-tones. Naming the
space is the only defence.

**Check:** grep for colour construction and check each against where the value came from. Design
tool and hex codes are sRGB; anything a shader or a lerp produced is linear.

### BV-VIEW-11 [S] Keep the whole game in one colour space until the boundary

Pick sRGB for authored values, convert once where they enter the renderer, and do arithmetic in
linear. Bloom's luminance has been computed in linear since 0.19, so a tint that compensated for
the old behaviour now over-blooms.

**Why:** once the spaces mix, every blend, lerp and tint has to be checked for which space it is in,
and the errors are subtle enough to survive review.

**Check:** for each colour arithmetic — a lerp, a multiply, a fade — ask which space the operands
are in. If the answer varies, the conversions are not at a boundary.

## Cameras and visibility

### BV-VIEW-12 [M] Spawn a camera as `Camera2d` or `Camera3d`

`commands.spawn(Camera2d)`. The bundles are gone, and the required components supply `Camera`,
`Transform`, `Projection` and the rest. Two defaults changed in 0.20: `Camera2d` brings
`Tonemapping::Linear` and, with `Hdr`, runs the tonemapping pass; and `Camera3d` no longer requires
`ScreenSpaceTransmission`, so a camera that draws transmissive materials adds it to its tuple.

**Why:** `Camera2dBundle::default()` is the most common single line in old Bevy material, so it is
the one most often reproduced from memory. The component form also overrides one required component
in the spawn tuple without restating the rest.

**Check:** grep for `Camera2dBundle` and `Camera3dBundle`.

### BV-VIEW-13 [M] Give every camera an explicit `order` once there are two

`Camera { order: 1, .. }` on the UI camera, `0` on the world camera.

**Why:** cameras sort by `(order, target)`, so a tie falls back to archetype order, which no game
controls. The result looks like a rendering bug, and the one warning that names it scrolls past in
the log.

**Check:** grep the startup log for "Camera order ambiguities". Failing that, count the camera
entities: more than one sharing an order and a render target is the condition.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct WorldView;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct HudView;

/// `Camera3d` and `Camera2d` bring `Camera`, `Transform`, `Projection` and
/// `RenderTarget` with them, so the tuple names only what it is choosing.
/// Two cameras on one target means both say where they sit in the order:
/// equal orders are left in archetype order, which no game controls.
fn spawn_views(mut commands: Commands) {
    commands.spawn((
        WorldView,
        Camera3d::default(),
        Camera {
            order: 0,
            ..default()
        },
        Transform::from_xyz(0.0, 6.0, 12.0).looking_at(Vec3::ZERO, Vec3::Y),
    ));
    commands.spawn((
        HudView,
        Camera2d,
        Camera {
            order: 1,
            ..default()
        },
    ));
}

#[derive(Debug, Default)]
pub struct ViewsPlugin;

impl Plugin for ViewsPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Startup, spawn_views);
    }
}

#[cfg(test)]
mod tests {
    use bevy::camera::RenderTarget;
    use bevy::platform::collections::HashSet;

    use super::*;

    #[test]
    fn the_component_form_supplies_the_old_bundle() {
        let mut app = App::new();
        app.add_plugins(ViewsPlugin);
        app.update();

        let mut world_views = app.world_mut().query_filtered::<Entity, With<WorldView>>();
        let Some(view) = world_views.iter(app.world()).next() else {
            unreachable!()
        };
        let view = app.world().entity(view);
        assert!(view.contains::<Camera>());
        assert!(view.contains::<Projection>());
        assert!(view.contains::<Transform>());
        assert!(view.contains::<RenderTarget>());
    }

    #[test]
    fn no_two_cameras_share_an_order() {
        let mut app = App::new();
        app.add_plugins(ViewsPlugin);
        app.update();

        let mut cameras = app.world_mut().query::<&Camera>();
        let orders: Vec<isize> = cameras.iter(app.world()).map(|c| c.order).collect();
        let distinct: HashSet<isize> = orders.iter().copied().collect();
        assert_eq!(orders.len(), 2);
        assert_eq!(distinct.len(), orders.len());
    }
}
```

### BV-VIEW-14 [S] Put a render target on the camera as its own component

Since 0.18, `RenderTarget` is a component rather than a field on `Camera`.

**Why:** as a component the target is swapped, removed and queried on its own: retargeting is an
insert, and a filter finds every off-screen camera. Code that copies a `Camera` and expects the
target to travel with it still compiles, and loses it.

**Check:** read every `Camera` struct literal in the diff. A `target` field in one is the 0.17
spelling; too many identifiers are called `target` for a grep to answer this.

### BV-VIEW-15 [M] Set `Visibility`, and read `ViewVisibility`

`Visibility::Hidden` to hide something. `InheritedVisibility` and `ViewVisibility` are outputs.

**Why:** the three are a pipeline — authored, inherited, culled per view — and propagation
overwrites a write to either of the last two in the same frame. Reading `Visibility` to learn
whether something is on screen is the mirror mistake: it says what was asked for.

**Check:** grep for writes to `InheritedVisibility` and `ViewVisibility`, and for reads of
`Visibility` that are asking about culling.

```rust
// verified
use bevy::camera::visibility::VisibilitySystems;
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct MapPins;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct MapPin;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct MapOpen(pub bool);

#[derive(Resource, Debug, Default, PartialEq, Eq, Reflect)]
#[reflect(Resource)]
pub struct PinsDrawn(pub usize);

fn spawn_pins(mut commands: Commands) {
    let pin = || Sprite::from_color(Color::srgb(0.9, 0.3, 0.2), Vec2::splat(8.0));
    commands.spawn((
        MapPins,
        Visibility::Hidden,
        Transform::default(),
        children![
            (MapPin, pin(), Transform::from_xyz(10.0, 0.0, 0.0)),
            (MapPin, pin(), Transform::from_xyz(-10.0, 0.0, 0.0)),
        ],
    ));
}

/// One write, to the authored value, on the root. No child is touched:
/// hiding a subtree is what `Visibility` inherits for.
fn toggle_pins(map: Res<MapOpen>, mut roots: Query<&mut Visibility, With<MapPins>>) {
    let wanted = if map.0 {
        Visibility::Inherited
    } else {
        Visibility::Hidden
    };
    for mut visibility in &mut roots {
        visibility.set_if_neq(wanted);
    }
}

/// `ViewVisibility` is the end of the pipeline and the only one that answers
/// "is it on screen". It runs after the propagation, so it is read there.
fn count_drawn(pins: Query<&ViewVisibility, With<MapPin>>, mut drawn: ResMut<PinsDrawn>) {
    drawn.set_if_neq(PinsDrawn(pins.iter().filter(|v| v.get()).count()));
}

#[derive(Debug, Default)]
pub struct MapPinsPlugin;

impl Plugin for MapPinsPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<MapOpen>()
            .init_resource::<PinsDrawn>()
            .add_systems(Startup, spawn_pins)
            .add_systems(Update, toggle_pins)
            .add_systems(
                PostUpdate,
                count_drawn.after(VisibilitySystems::MarkNewlyHiddenEntitiesInvisible),
            );
    }
}

#[cfg(test)]
mod tests {
    use bevy::asset::AssetPlugin;
    use bevy::camera::visibility::VisibilityPlugin;
    use bevy::mesh::MeshPlugin;

    use super::*;

    fn app() -> App {
        let mut app = App::new();
        app.add_plugins((
            TaskPoolPlugin::default(),
            AssetPlugin::default(),
            TransformPlugin,
            MeshPlugin,
            VisibilityPlugin,
            MapPinsPlugin,
        ));
        app.world_mut().spawn(Camera2d);
        app
    }

    fn a_pin(app: &mut App) -> Entity {
        let mut pins = app.world_mut().query_filtered::<Entity, With<MapPin>>();
        let Some(pin) = pins.iter(app.world()).next() else {
            unreachable!()
        };
        pin
    }

    /// The child was never written to, so its `Visibility` still says
    /// `Inherited` while it is off screen. Asking it about culling gets the
    /// wrong answer with no error.
    #[test]
    fn a_hidden_root_leaves_the_child_asking_and_undrawn() {
        let mut app = app();
        app.update();
        let pin = a_pin(&mut app);

        let entity = app.world().entity(pin);
        assert_eq!(entity.get::<Visibility>(), Some(&Visibility::Inherited));
        assert_eq!(
            entity.get::<InheritedVisibility>(),
            Some(&InheritedVisibility::HIDDEN)
        );
        assert_eq!(
            entity.get::<ViewVisibility>(),
            Some(&ViewVisibility::HIDDEN)
        );
        assert_eq!(app.world().resource::<PinsDrawn>(), &PinsDrawn(0));
    }

    #[test]
    fn opening_the_map_reaches_the_children() {
        let mut app = app();
        app.update();
        app.world_mut().resource_mut::<MapOpen>().0 = true;
        app.update();
        let pin = a_pin(&mut app);

        let entity = app.world().entity(pin);
        assert_eq!(entity.get::<Visibility>(), Some(&Visibility::Inherited));
        assert_eq!(
            entity.get::<InheritedVisibility>(),
            Some(&InheritedVisibility::VISIBLE)
        );
        assert_eq!(app.world().resource::<PinsDrawn>(), &PinsDrawn(2));
    }

    /// Hiding a pin by writing the output: it is back the next frame,
    /// because the visibility systems recompute it from `Visibility`.
    #[test]
    fn a_write_to_view_visibility_does_not_survive_the_frame() {
        let mut app = app();
        app.world_mut().resource_mut::<MapOpen>().0 = true;
        app.update();
        let pin = a_pin(&mut app);
        app.world_mut()
            .entity_mut(pin)
            .insert(ViewVisibility::HIDDEN);

        app.update();

        assert_eq!(
            app.world()
                .entity(pin)
                .get::<ViewVisibility>()
                .map(|v| v.get()),
            Some(true)
        );
        assert_eq!(app.world().resource::<PinsDrawn>(), &PinsDrawn(2));
    }
}
```

### BV-VIEW-16 [M] Do not maintain `Aabb` by hand

Since 0.18, Bevy adds and updates an `Aabb` for meshes and sprites, including when the mesh or
sprite changes.

**Why:** the old workarounds — removing the `Aabb` to force a recompute, or recomputing it in a
system — now fight the engine's own updates, costing a duplicate computation every frame or culling
an entity that should be drawn.

**Check:** grep for `Aabb`. In game code there should be reads and no writes.

## Materials and debugging

### BV-VIEW-17 [S] Reach for a custom `Material` before a custom render node

A `Material` (or `Material2d`) with a fragment shader covers most of what a game wants: a shield
effect, a dissolve, a palette swap. Since 0.20 a sprite takes a custom shader too, through
`SpriteMaterial` and `MaterialExtension2d`, rather than a `Mesh2d` quad built to shade it, and
`ExtendedMaterial2d` extends a 2D material.

**Why:** the material API survives releases the render graph does not: 0.19 rewrote every custom
render node in the ecosystem and left materials alone. A node built for a mesh effect pays that
rewrite every release.

**Check:** can the effect be expressed as "this mesh, drawn differently"? Then it is a material.

### BV-VIEW-18 [M] Keep shader paths and material types together

The `Material` impl naming a shader path lives beside the struct, and the shader lives at a path the
struct's module name predicts. Since 0.20 that shader is WESL: a 0.19 `.wgsl` that used `#import`
or `#ifdef` becomes a `.wesl` with `import …;`, `@if(…)` and `constants::MATERIAL_BIND_GROUP`.
GLSL is gone, with the `shader_format_glsl` and `shader_format_wesl` features, and the module paths
that moved are in `references/migration.md` BV-MIG-17.

**Why:** nothing checks a struct's fields against the shader's bindings at compile time: a mismatch
fails at pipeline compilation, at run time, naming a binding index. Side by side, a field added on
one side is visibly missing on the other.

**Check:** for each `impl Material`, is the shader path within sight of the struct definition, and
does the struct's field order match the shader's?

### BV-VIEW-19 [S] Debug in world space with gizmos

`Gizmos::line`, `circle`, `cube`, and since 0.19 `Gizmos::text` and `text_2d`. Not a spawned
`Text2d` that has to be despawned.

**Why:** gizmos are immediate-mode: drawn for one frame from the system that wants them, with no
entity to create, position, update or clean up. The spawned alternative outlives its usefulness by
default, which is why debug text has a habit of shipping.

**Check:** grep for spawned entities whose only purpose is debugging. Anything that has to be
despawned to stop showing is a gizmo written the long way.

### BV-VIEW-20 [S] Reach for a post-process component before a full-screen pass

Bloom, motion blur, depth of field, vignette, lens distortion and chromatic aberration are
components on the camera entity. Spawn them in the camera tuple; animate them by writing a field;
turn one off by removing it. `bevy_post_process` composes them into one pass and sits inside the
`2d` and `3d` collections BV-BUILD-02 mandates, and `Bloom` declares the `Hdr` it requires. For no
tonemapping curve write `Tonemapping::Linear`: since 0.20 `Tonemapping::None` is a full
passthrough, with no `ColorGrading`, no `DebandDither` and no clamping of negative values.

**Why:** BV-VIEW-17 sends a mesh effect to a `Material` and the rest to a render node, but a
full-screen effect has no mesh, so it would land on the node that rule warns against. These
components fill that gap with no dependency the game does not already have.

**Check:** for each custom full-screen pass, name the shipped component it reimplements. If there is
none, that is the case BV-VIEW-17 was talking about.

### BV-VIEW-21 [S] Draw with a retained gizmo before a sprite you have to despawn

`Gizmo` plus a `GizmoAsset` is a line drawing that persists as an entity. Reach for it before
spawning untextured sprites you redraw every frame — for a map, an orbit, a selection ring, or a
debug overlay that has to survive the frame.

**Why:** the default for a drawing that outlives the frame is a despawn loop and a fresh sprite per
element per frame, which allocates, defeats change detection, and leaves nothing to pick or query. A
retained gizmo is built once and edited when its subject changes.

**Check:** find every system that begins by despawning what it is about to respawn. Each is either a
retained gizmo or a set of entities that should have persisted.
