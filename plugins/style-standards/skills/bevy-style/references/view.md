# UI and Rendering: The Half a Game Writes

Scope: the components a game spawns to put something on the screen — UI nodes, text, buttons,
cameras, visibility, materials and gizmos. The engine's rendering internals are out of scope: the
render graph is a set of systems, pipeline specialisation moves with it, and neither is something a
game should be reaching into.

This is the area that changes most between releases, so `references/migration.md` is the companion
chapter: most of the types it removes and renames are ones this chapter spawns.

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

`Node` is a flexbox node. Rows, columns, gaps and alignment do the layout. What leaves the flow is
placed against its parent with `PositionType::Absolute`, or against the viewport with a `FixedNode`,
which lays a nested node out as a root: a full-screen overlay spawned inside a HUD is a `FixedNode`,
because an absolute child at 100% covers only its parent.

**Why:** an absolute position is a layout evaluated once, by hand, at one window size. It breaks at
every other resolution, every UI scale factor and every longer string, and still looks right to
whoever wrote it.

**Check:** count the `px(…)` values in `left`, `top`, `right` and `bottom`. Each one is a position
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
            width: percent(100),
            height: px(48),
            flex_direction: FlexDirection::Row,
            align_items: AlignItems::Center,
            justify_content: JustifyContent::SpaceBetween,
            column_gap: px(16),
            row_gap: px(8),
            padding: UiRect::horizontal(px(24)),
            ..default()
        },
        children![
            (Slot, Node::default()),
            (Slot, Node::default()),
            (Slot, Node::default()),
            // Leaves the flow to dim the whole screen. A `FixedNode` is laid
            // out against the viewport even inside this bar, and it still
            // names no edge: a full-bleed node is two percentages.
            (
                DimOverlay,
                FixedNode,
                Node {
                    width: percent(100),
                    height: percent(100),
                    ..default()
                },
            ),
        ],
    ));
}

/// A narrow window stacks the bar. Flex makes that one field; with hand-placed
/// edges it is every child. The guard is BV-ECS-24 for a single field —
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
/// `stack_when_narrow`, which stays free to be renamed or split (BV-SCHED-11).
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

`px` for something that should stay the same size, `percent` for something that should scale with
its parent, `vw`/`vh` for something that should scale with the window, `em`/`rem` for something
that should scale with the text size, `auto()` for something the content decides. Each helper
builds the `Val` of its name and takes an integer or a float. `Val::Em` resolves against the
node's `EmSize`, which `Node` requires, and `Val::Rem` against the `RemSize` resource.

**Why:** the unit is the only place the intent is recorded. A `Px` where a `Percent` was meant looks
right until the window changes, then looks broken with nothing to say why.

**Check:** for each `Val`, resize the window and the text in your head. If the value should have
changed and did not, the unit is wrong.

### BV-VIEW-03 [M] Read computed layout from `ComputedNode`, never from `Node`

`Node` is the input to layout. `ComputedNode` is the output.

**Why:** for anything sized by `Auto`, a percentage or a flex-grow, the requested value and the
laid-out one are different numbers, and a read of a size from `Node` compiles and returns the
request.

**Check:** grep for reads of `Node` that are looking for a size or a position. Those fields are on
`ComputedNode`.

### BV-VIEW-04 [M] Give text its components together

`Text::new(s)` plus `TextFont` plus `TextColor`, spawned as one tuple. `Text2d` for world-space
text. `TextFont::default()` sizes text at `FontSize::Rem(1.)`, not `Px(20.)`: it renders the same
until `RemSize` changes, so a size that must stay fixed is
`TextFont::from_font_size(FontSize::Px(…))`.

**Why:** a missing component arrives as a required-component default: a colour nobody chose, and a
size that follows `RemSize`. One tuple also keeps the lines that describe one piece of text
together.

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
        TextFont::from_font_size(FontSize::Px(32.0)),
        TextColor(Color::srgb(0.9, 0.9, 0.9)),
        Node {
            margin: UiRect::all(px(12)),
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

`commands.entity(button).observe(on_activate)` with an `On<Activate>` event. The button is
`bevy::ui_widgets::Button`, imported by name, because 0.20 deprecates the prelude `Button` and
`Interaction`. Under `UiWidgetsPlugins` it emits `Activate` when a press is released over it while
not `InteractionDisabled`, and on Enter or Space while focused; `PointerClick` fires on a disabled
button too and never from the keyboard. `Hovered` and `Pressed` carry the state a style needs.

**Why:** a polling system runs every frame over every button to find the one that changed, and its
handler lives in another file. An entity-scoped observer sits beside the spawn, dies with the
button, and runs only when it is used.

**Check:** grep for `Query<&Interaction`, and for `On<PointerClick>` on a widget `Button`. The first
is a set of buttons whose handlers were gathered into one system; the second skips the widget's
contract.

```rust
// verified
use bevy::prelude::*;
use bevy::ui_widgets::{Activate, Button};

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
                padding: UiRect::axes(px(24), px(12)),
                ..default()
            },
            children![(
                Text::new("Start"),
                TextFont::from_font_size(FontSize::Px(24.0)),
                TextColor(Color::srgb(0.95, 0.95, 0.95)),
            )],
        ))
        .observe(start_game);
}

/// Named after its event, and it runs only when this button is activated —
/// never while it is disabled, and from the keyboard as well as the pointer.
fn start_game(_activated: On<Activate>, mut starts: ResMut<Starts>) {
    starts.0 += 1;
}

#[derive(Debug, Default)]
pub struct StartButtonPlugin;

impl Plugin for StartButtonPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Starts>()
            .add_systems(Startup, spawn_start_button);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn activating_the_button_runs_the_observer_beside_its_spawn() {
        let mut app = App::new();
        app.add_plugins(StartButtonPlugin);
        app.update();

        let mut buttons = app
            .world_mut()
            .query_filtered::<Entity, With<StartButton>>();
        let button = buttons
            .iter(app.world())
            .next()
            .expect("Startup spawned the button");
        app.world_mut().trigger(Activate { entity: button });
        assert_eq!(app.world().resource::<Starts>().0, 1);
    }
}
```

### BV-VIEW-07 [S] Reach for `bevy_ui_widgets` before writing a widget

Buttons, checkboxes, radio buttons, sliders, scrollbars, tabs (`TabList`/`Tab`), list boxes, menus,
dialogs, modals, popovers and text input ship in `bevy_ui_widgets`. `bevy_feathers` is the styled
layer above it.

**Why:** a hand-written slider is a week of edge cases — drag capture, keyboard focus,
accessibility, scroll interaction — and the shipped ones have had those weeks spent on them. They
are also where upstream's improvements land, so a hand-written one is a fork.

**Check:** is the widget on that list? Then the question is what the shipped one does not do.

### BV-VIEW-08 [S] Reach for `TextInput` before a text-input crate

The engine has a real text field. Spawn `bevy::ui_widgets::TextInput`, which requires
`bevy_text::EditableText`: `EditableText` holds the content and the cursor, and `TextInputPlugin`,
part of `UiWidgetsPlugins`, wires the keyboard, the pointer, focus and the clipboard to it. An
`EditableText` without `TextInput` compiles, spawns and ignores the keyboard, and Escape in a
focused field releases `InputFocus` and propagates to its ancestors and the window.

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
/// where it can move the cursor by the same rules that drew the glyphs. `Single`
/// skips the system while no seed field exists, which is not an error.
fn paste_seed(mut field: Single<&mut EditableText, With<SeedEntry>>) {
    field.queue_edit(TextEdit::Insert("42".into()));
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
        assert!(app.world_mut().run_system_once(paste_seed).is_ok());

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
separated by `--`. `{expr}` escapes back to Rust, and a scene reference takes `@`: `@name`,
`@make()`, `@{expr}`. A bare list of entities is `bsn_list! { … }`. The tree is spawned with
`spawn_scene`, from the `CommandsSceneExt` trait — not `spawn`, because a scene is not a `Bundle` —
and an `On<Ready>` observer on it runs once the whole subtree has spawned. An observer for a nested
entity is attached where that entity is written: `on(handler)` inside `bsn!`, or
`bevy::ui_widgets::observe(handler)` in a `children![]` tuple, never found again after the spawn.

**Why:** the alternative nests a `with_children` closure per level, so the indentation is the
structure. It is `[S]` because the grammar is the newest surface in Bevy, and it still moves
between releases.

**Check:** count the closing braces at the end of the spawn. Past three levels, the tuple form has
stopped being readable.

```rust
// verified
use bevy::prelude::*;
use bevy::scene::{CommandsSceneExt, bsn, on};
use bevy::ui_widgets::Activate;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Menu;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Choice;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Plays(pub u32);

fn play(_activated: On<Activate>, mut plays: ResMut<Plays>) {
    plays.0 += 1;
}

/// The observer is written on the entity it observes, two levels down, rather
/// than attached after the spawn to an entity that has to be found again.
fn spawn_menu(mut commands: Commands) {
    commands.spawn_scene(bsn! {
        Menu
        Node { width: percent(100), row_gap: px(8) }
        Children [
            Choice Text("Play") on(play)
            --
            Choice Text("Quit")
        ]
    });
}

#[derive(Debug, Default)]
pub struct MenuPlugin;

impl Plugin for MenuPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Plays>()
            .add_systems(Startup, spawn_menu);
    }
}

#[cfg(test)]
mod tests {
    use bevy::asset::AssetPlugin;
    use bevy::scene::ScenePlugin;

    use super::*;

    #[test]
    fn the_nested_choice_carries_its_own_observer() {
        let mut app = App::new();
        app.add_plugins((
            TaskPoolPlugin::default(),
            AssetPlugin::default(),
            ScenePlugin,
            MenuPlugin,
        ));
        app.update();

        let mut choices = app
            .world_mut()
            .query_filtered::<(Entity, &Text), With<Choice>>();
        let labelled: Vec<(Entity, String)> = choices
            .iter(app.world())
            .map(|(entity, text)| (entity, text.0.clone()))
            .collect();
        let find = |label: &str| {
            labelled
                .iter()
                .find(|(_, text)| text == label)
                .map(|(entity, _)| *entity)
        };
        let play_choice = find("Play").expect("the menu offers Play");
        let quit_choice = find("Quit").expect("the menu offers Quit");

        app.world_mut().trigger(Activate {
            entity: quit_choice,
        });
        assert_eq!(app.world().resource::<Plays>().0, 0);
        app.world_mut().trigger(Activate {
            entity: play_choice,
        });
        assert_eq!(app.world().resource::<Plays>().0, 1);
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
linear. Bloom computes its luminance in linear too, so judge a bloom tint in linear.

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

**Check:** read each camera spawn: `Camera2d` or `Camera3d`, plus only the components it
overrides. A `Camera2dBundle` or `Camera3dBundle` is BV-MIG-03's table.

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
        let view = world_views
            .iter(app.world())
            .next()
            .expect("the plugin spawned a world view");
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

`RenderTarget` is a component of its own, not a field on `Camera`.

**Why:** as a component the target is swapped, removed and queried on its own: retargeting is an
insert, and a filter finds every off-screen camera. Code that copies a `Camera` and expects the
target to travel with it still compiles, and loses it.

**Check:** read every `Camera` struct literal in the diff. A `target` field in one is the removed
spelling (BV-MIG-11); too many identifiers are called `target` for a grep to answer this.

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
        pins.iter(app.world())
            .next()
            .expect("the plugin spawned two pins")
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

Bevy adds and updates an `Aabb` for meshes and sprites, including when the mesh or sprite changes.

**Why:** removing the `Aabb` to force a recompute, or recomputing it in a system, fights the
engine's own updates, costing a duplicate computation every frame or culling an entity that should
be drawn.

**Check:** grep for `Aabb`. In game code there should be reads and no writes.

## Materials and debugging

### BV-VIEW-17 [S] Reach for a custom `Material` before a custom render node

A `Material` (or `Material2d`) with a fragment shader covers most of what a game wants: a shield
effect, a dissolve, a palette swap. A sprite takes a custom shader too, through
`SpriteMaterial` and `MaterialExtension2d`, rather than a `Mesh2d` quad built to shade it, and
`ExtendedMaterial2d` extends a 2D material.

**Why:** the material API survives releases the render graph does not: a render-graph rewrite
reaches every custom render node in the ecosystem and leaves materials alone. A node built for a
mesh effect pays that rewrite every release.

**Check:** can the effect be expressed as "this mesh, drawn differently"? Then it is a material.

### BV-VIEW-18 [M] Keep shader paths and material types together

The `Material` impl naming a shader path lives beside the struct, and the shader lives at a path the
struct's module name predicts. That shader is WESL, a `.wesl` with `import …;`, `@if(…)` and
`constants::MATERIAL_BIND_GROUP`, where a `.wgsl` used `#import` and `#ifdef`. GLSL is gone, with
the `shader_format_glsl` and `shader_format_wesl` features, and the module paths that moved are in
`references/migration.md` BV-MIG-17.

**Why:** nothing checks a struct's fields against the shader's bindings at compile time: a mismatch
fails at pipeline compilation, at run time, naming a binding index. Side by side, a field added on
one side is visibly missing on the other.

**Check:** for each `impl Material`, is the shader path within sight of the struct definition, and
does the struct's field order match the shader's?

### BV-VIEW-19 [S] Debug in world space with gizmos

`Gizmos::line`, `circle`, `cube`, `text` and `text_2d`. Not a spawned `Text2d` that has to be
despawned.

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
tonemapping curve write `Tonemapping::Linear`: `Tonemapping::None` is a full passthrough, with no
`ColorGrading`, no `DebandDither` and no clamping of negative values.

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
