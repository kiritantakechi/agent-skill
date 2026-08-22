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
  - BV-UI-01 [M] Lay out with `Node` and children, not with absolute positions
  - BV-UI-02 [S] Choose the `Val` unit for what the value means
  - BV-UI-03 [M] Read computed layout from `ComputedNode`, never from `Node`
  - BV-UI-04 [M] Give text its components together
  - BV-UI-05 [S] Compose a mixed-style run from `TextSpan` children
  - BV-UI-06 [M] React to a button with an observer, not by polling `Interaction`
  - BV-UI-07 [S] Reach for `bevy_ui_widgets` before writing a widget
  - BV-UI-08 [S] Build a nested UI tree with `bsn!`

- **Colour**
  - BV-UI-09 [M] Construct a colour by naming its space
  - BV-UI-10 [S] Keep the whole game in one colour space until the boundary

- **Cameras and visibility**
  - BV-UI-11 [M] Spawn a camera as `Camera2d` or `Camera3d`
  - BV-UI-12 [M] Give every camera an explicit `order` once there are two
  - BV-UI-13 [S] Put a render target on the camera as its own component
  - BV-UI-14 [M] Set `Visibility`, and read `ViewVisibility`
  - BV-UI-15 [M] Do not maintain `Aabb` by hand

- **Materials and debugging**
  - BV-UI-16 [S] Reach for a custom `Material` before a custom render node
  - BV-UI-17 [M] Keep shader paths and material types together
  - BV-UI-18 [S] Debug in world space with gizmos

---

## UI

### BV-UI-01 [M] Lay out with `Node` and children, not with absolute positions

`Node` is a flexbox node. Rows, columns, gaps and alignment do the layout; `PositionType::Absolute`
is for overlays.

**Why:** absolute positions are a layout that has been evaluated once, at one window size, by hand.
They break on every other resolution, on every UI scale factor, and whenever a string gets longer —
and the breakage is a design that looks fine to whoever wrote it. The flex layout is the mechanism
that already solves this and is the reason `Node` exists.

**Check:** count the `Val::Px` values in `left`, `top`, `right` and `bottom`. Each one is a position
that will be wrong at another size.

### BV-UI-02 [S] Choose the `Val` unit for what the value means

`Px` for something that should stay the same size, `Percent` for something that should scale with
its parent, `Vw`/`Vh` for something that should scale with the window, `Auto` for something the
content decides.

**Why:** the unit is the only place the intent is recorded, so a `Px` where a `Percent` was meant
looks correct until the window changes and then looks broken with no clue why. Mixing them
arbitrarily also makes the layout unpredictable to the next person: they cannot tell which values
are load-bearing.

**Check:** for each `Val`, resize the window in your head. If the value should have changed and did
not, the unit is wrong.

### BV-UI-03 [M] Read computed layout from `ComputedNode`, never from `Node`

`Node` is the input to layout. `ComputedNode` is the output.

**Why:** `Node` used to be the computed output — before 0.15 the input was called `Style` — so old
code that reads a size from `Node` compiles against the current type and reads the requested value
rather than the actual one. For anything with `Auto`, a percentage or a flex-grow, those are
different numbers.

**Check:** grep for reads of `Node` that are looking for a size or a position. Those fields are on
`ComputedNode`.

### BV-UI-04 [M] Give text its components together

`Text::new(s)` plus `TextFont` plus `TextColor`, spawned as one tuple. `Text2d` for world-space
text.

**Why:** the components are required components of one another in part, so a missing one gets a
default — which for `TextColor` is a colour the author did not choose and for `TextFont` is a size
they did not choose. Spawning them together also keeps the three lines that describe one piece of
text in one place, which is what the old `TextStyle` struct was doing well.

**Check:** grep for `Text::new` and check the same tuple carries a font and a colour.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug)]
struct ScoreLabel;

fn spawn_hud(mut commands: Commands) {
    commands.spawn((
        ScoreLabel,
        Text::new("0"),
        TextFont {
            font_size: 32.0.into(),
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

### BV-UI-05 [S] Compose a mixed-style run from `TextSpan` children

A line with two colours or two sizes is a `Text` root with `TextSpan` children, not a formatted
string.

**Why:** each span is an entity, so the styled parts can be queried, changed and animated
independently — updating a score inside a sentence is a write to one span rather than a rebuild of
the whole string. It is also the only way to have two styles at all, since `TextFont` and
`TextColor` apply to a whole entity.

**Check:** does the text change one part of a line frequently? If it is being rebuilt with
`format!`, that part is a span.

### BV-UI-06 [M] React to a button with an observer, not by polling `Interaction`

`commands.entity(button).observe(on_click)` with a `Pointer<Click>` event.

**Why:** it is BV-EVT-13's argument in the place it matters most: the polling form is a system
running every frame over every button, testing a component that changed for one of them, and the
handler ends up in a different file from the button. An entity-scoped observer puts the reaction
beside the spawn, dies with the button, and runs only when the button is used.

**Check:** grep for `Query<&Interaction`. Each is a set of buttons whose handlers have been gathered
into one system.

### BV-UI-07 [S] Reach for `bevy_ui_widgets` before writing a widget

Buttons, checkboxes, radio buttons, sliders and scrollbars ship in `bevy_ui_widgets`, which stopped
being experimental in 0.19. `bevy_feathers` is the styled layer above it.

**Why:** a hand-written slider is a week of edge cases — drag capture, keyboard focus,
accessibility, scroll interaction — and the shipped ones have had those weeks spent on them. They
are also where upstream's improvements land, so a hand-written one is a fork.

**Check:** is the widget one of the five? Then the question is what the shipped one does not do.

### BV-UI-08 [S] Build a nested UI tree with `bsn!`

`bsn!` from `bevy_scene` expresses a tree with its children inline. Reach for it once the UI nests
more than two levels.

**Why:** the alternative is `with_children` closures nested to the depth of the tree, where the
indentation is the structure and every level adds a closure. `bsn!` is new in 0.19 and its
ergonomics are not yet settled, which is why this is a `[S]` and why a two-component spawn stays a
plain tuple.

**Check:** count the closing braces at the end of the spawn. Past three levels, the tuple form has
stopped being readable.

## Colour

### BV-UI-09 [M] Construct a colour by naming its space

`Color::srgb(r, g, b)` for a colour picked in a design tool. `Color::linear_rgb` and
`LinearRgba` for a value that is being computed.

**Why:** the two are different numbers for the same colour, and the constructors do not warn — a
value copied from a palette and passed to the linear constructor is a visibly different colour, most
obviously in the mid-tones. Naming the space is the only defence, which is why `Color::rgb` was
renamed to `Color::srgb`.

**Check:** grep for colour construction and check each against where the value came from. Design
tool and hex codes are sRGB; anything a shader or a lerp produced is linear.

### BV-UI-10 [S] Keep the whole game in one colour space until the boundary

Pick sRGB for authored values, convert once where they enter the renderer, and do arithmetic in
linear.

**Why:** mixing the spaces means every blend, lerp and tint has to be checked individually for which
space it is in, and the errors are subtle enough to survive review. It also matters more in 0.19,
which moved bloom's luminance calculation into linear space — a game that was compensating for the
old behaviour now over-blooms.

**Check:** for each colour arithmetic — a lerp, a multiply, a fade — ask which space the operands
are in. If the answer varies, the conversions are not at a boundary.

## Cameras and visibility

### BV-UI-11 [M] Spawn a camera as `Camera2d` or `Camera3d`

`commands.spawn(Camera2d)`. The bundles are gone, and the required components supply `Camera`,
`Transform`, `Projection` and the rest.

**Why:** it is the most common single line in old Bevy material — `Camera2dBundle::default()` — so
it is the one most likely to be reproduced from memory. The component form also lets a game override
exactly one required component in the spawn tuple without restating the others.

**Check:** grep for `Camera2dBundle` and `Camera3dBundle`.

### BV-UI-12 [M] Give every camera an explicit `order` once there are two

`Camera { order: 1, .. }` on the UI camera, `0` on the world camera.

**Why:** cameras with equal order render in an unspecified sequence, so a UI camera and a world
camera with the default order produce a picture that depends on spawn order — which changes when a
plugin is added. The failure is intermittent and looks like a rendering bug rather than a
configuration one.

**Check:** count the camera entities. If there is more than one and any has the default order, the
layering is undefined.

### BV-UI-13 [S] Put a render target on the camera as its own component

Since 0.18, `RenderTarget` is a component rather than a field on `Camera`.

**Why:** as a component it can be added, removed and queried independently — a camera that renders
to a texture this frame and to the window the next is a component swap rather than a struct edit,
and a system can find every off-screen camera with a filter. Old code setting `Camera { target, ..
}` no longer compiles, which is the good case; code copying a `Camera` and expecting the target to
travel with it is the bad one.

**Check:** read every `Camera` struct literal in the diff. A `target` field in one is the 0.17
spelling; too many identifiers are called `target` for a grep to answer this.

### BV-UI-14 [M] Set `Visibility`, and read `ViewVisibility`

`Visibility::Hidden` to hide something. `InheritedVisibility` and `ViewVisibility` are outputs.

**Why:** the three are a pipeline — the authored value, the value after inheriting from the parent,
and the value after culling for a particular view — and writing to either of the last two is
overwritten by the propagation system in the same frame. Reading `Visibility` to find out whether
something is on screen is the mirror mistake: it says what was asked for, not what happened.

**Check:** grep for writes to `InheritedVisibility` and `ViewVisibility`, and for reads of
`Visibility` that are asking about culling.

### BV-UI-15 [M] Do not maintain `Aabb` by hand

Since 0.18, Bevy adds and updates an `Aabb` for meshes and sprites, including when the mesh or
sprite changes.

**Why:** the hand-maintained workarounds this replaced — removing the `Aabb` so it gets recomputed,
or recomputing it in a system — now fight the engine's own updates, and the result is either a
duplicate computation every frame or an entity that is culled when it should not be. The workaround
looks harmless, which is why it survives upgrades.

**Check:** grep for `Aabb`. In game code there should be reads and no writes.

## Materials and debugging

### BV-UI-16 [S] Reach for a custom `Material` before a custom render node

A `Material` (or `Material2d`) with a fragment shader covers most of what a game wants: a shield
effect, a dissolve, a palette swap.

**Why:** the material API is stable across releases in a way the render graph is not — 0.19 turned
every render-graph node into a system, which rewrote every custom node in the ecosystem and left
materials alone. A custom node is for something genuinely outside the mesh pipeline, and the cost of
finding out it was not is a rewrite per release.

**Check:** can the effect be expressed as "this mesh, drawn differently"? Then it is a material.

### BV-UI-17 [M] Keep shader paths and material types together

The `Material` impl naming a shader path lives beside the struct, and the shader lives at a path the
struct's module name predicts.

**Why:** the binding between a Rust struct's fields and a WGSL uniform block is not checked by the
compiler — the shader fails at pipeline compilation, at run time, with an error about a binding
index. Keeping the two next to each other is the only thing that makes a field added on one side
visibly missing on the other.

**Check:** for each `impl Material`, is the shader path within sight of the struct definition, and
does the struct's field order match the shader's?

### BV-UI-18 [S] Debug in world space with gizmos

`Gizmos::line`, `circle`, `cube`, and since 0.19 `Gizmos::text` and `text_2d`. Not a spawned
`Text2d` that has to be despawned.

**Why:** gizmos are immediate-mode: drawn for one frame from the system that wants them, with no
entity to create, position, update or clean up. The spawned alternative outlives its usefulness by
default, which is why debug text has a habit of shipping.

**Check:** grep for spawned entities whose only purpose is debugging. Anything that has to be
despawned to stop showing is a gizmo written the long way.
