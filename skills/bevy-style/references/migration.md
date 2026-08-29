# Migration: Every API Forbidden Since 0.15, and What Replaces It

Scope: the names that changed between Bevy 0.15 and 0.19, as a table of what to write instead. This
is the chapter to open when porting code, when reviewing something that looks like it came from a
tutorial, and when a name does not resolve.

Every right-hand column is the **0.19** spelling, not the first hop. Several of these renamed twice
— `EventWriter::send` became `EventWriter::write` in 0.16 and then `MessageWriter::write` in 0.17 —
and a table that stops at the first hop sends the reader to a name that is also gone.

The tables are not exhaustive for the engine; they are exhaustive for what a game writes. Rendering
internals, the render graph, pipeline specialisation and the reflection internals changed at least
as much, and the upstream migration guides are the reference for those.

## Contents

- **Using this chapter**
  - BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.17 until checked
  - BV-MIG-02 [M] Treat a deprecated API as removed
  - BV-MIG-03 [M] Follow a rename to its 0.19 spelling, not its first hop

- **0.15: bundles and text**
  - BV-MIG-04 [M] Replace every `*Bundle` with the components it inserted
  - BV-MIG-05 [M] Replace the old text API with the text components
  - BV-MIG-06 [M] Replace the old UI node API

- **0.16: hierarchy, queries, errors**
  - BV-MIG-07 [M] Replace `Parent` and the hierarchy commands with relationships
  - BV-MIG-08 [M] Replace the panicking and deprecated query methods
  - BV-MIG-09 [M] Replace `Handle` used directly as a component (see BV-ECS-14)

- **0.17: the big rename**
  - BV-MIG-10 [M] Replace the buffered-event vocabulary with messages
  - BV-MIG-11 [M] Replace `Trigger` and the `On`-prefixed lifecycle events (see BV-EVT-14)
  - BV-MIG-12 [M] Rename every system set to end in `Systems`
  - BV-MIG-13 [M] Replace the remaining 0.17 renames

- **0.18 and 0.19**
  - BV-MIG-14 [M] Replace the 0.18 renames
  - BV-MIG-15 [M] Split a type that was both a component and a resource (see BV-STA-01)
  - BV-MIG-16 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean
  - BV-MIG-17 [M] Replace the remaining 0.19 renames

- **Changes that do not show up as a compile error**
  - BV-MIG-18 [M] Re-read every `Ref` that is cloned

---

## Using this chapter

### BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.17 until checked

Code from a tutorial, a blog post, an answer, or a language model is 0.15-era until something proves
otherwise. Check it against these tables before adapting it.

**Why:** 0.17 renamed the event system, the observer parameter and every system set, and the
overwhelming majority of Bevy material on the internet was written before it. The failure mode is
not a compile error — it is half an hour spent adapting a pattern that no longer exists, and a
mental model that keeps producing the old names.

**Check:** `rg -n  'Trigger<|EventReader|EventWriter|[A-Za-z0-9]Bundle' src/` over the sample.
Any hit dates it, and so does a system set whose name does not end in `Systems`.

### BV-MIG-02 [M] Treat a deprecated API as removed

A `#[deprecated]` item in Bevy has one release to live. Write the replacement.

**Why:** Bevy deprecates for one minor version and then deletes, so a deprecation warning is a
notice that this code will not compile against the next release — six to twelve weeks away. Leaving
it also means the migration happens later, in a batch, at the same time as everything else that
release changed.

**Check:** build with warnings visible and read every `deprecated` note. There should be none.

### BV-MIG-03 [M] Follow a rename to its 0.19 spelling, not its first hop

When a migration guide gives a new name, check whether that name still exists.

**Why:** several APIs moved twice in three releases. `EventWriter::send` → `EventWriter::write`
(0.16) → `MessageWriter::write` (0.17). `SceneRoot` → `WorldAssetRoot` (0.19), while `bevy_scene`
became a different crate entirely. Applying the 0.16 guide to 0.15 code and stopping leaves a name
that was already renamed again.

**Check:** after applying a rename, grep the vendored source of the version you depend on for the
new name. If it is not there, the chain continued.

## 0.15: bundles and text

### BV-MIG-04 [M] Replace every `*Bundle` with the components it inserted

The `*Bundle` types were deprecated in 0.15 and are gone. What replaces them is a tuple of
components at the spawn site plus `#[require]` on the types that always travel together. The
`Bundle` **trait** remains — it is what a spawn tuple implements — and so does its derive, which
BV-ECS-08 forbids you from using.

**Why:** this is the most visible break between old Bevy material and current Bevy, and the most
mechanical to fix — every `XBundle::default()` becomes one or two components, and the required
components supply the rest. The reason it was done is BV-ECS-06: a bundle could be half-applied and
a `#[require]` cannot.

**Check:** `rg -n  '[A-Za-z0-9]Bundle' src/`. Every hit is either a removed type or one you
wrote yourself, and BV-ECS-08 forbids the second. The two the engine still spells that way,
`SpawnRelatedBundle` and `ReflectBundle`, are machinery a game does not name.

| Removed | Write instead |
|---|---|
| `SpriteBundle { texture, .. }` | `Sprite::from_image(handle)` plus `Transform` |
| `SpriteSheetBundle` | `Sprite::from_atlas_image(handle, atlas)` |
| `Camera2dBundle::default()` | `Camera2d` |
| `Camera3dBundle::default()` | `Camera3d::default()` |
| `PbrBundle { mesh, material, .. }` | `Mesh3d(mesh)` plus `MeshMaterial3d(material)` |
| `MaterialMesh2dBundle { mesh, material, .. }` | `Mesh2d(mesh)` plus `MeshMaterial2d(material)` |
| `NodeBundle::default()` | `Node::default()` |
| `ButtonBundle::default()` | `Button` plus `Node` |
| `ImageBundle { image, .. }` | `ImageNode::new(handle)` |
| `TextBundle::from_section(s, style)` | `Text::new(s)` plus `TextFont` and `TextColor` |
| `Text2dBundle` | `Text2d::new(s)` plus `TextFont` and `TextColor` |
| `PointLightBundle` | `PointLight::default()` plus `Transform` |
| `DirectionalLightBundle` | `DirectionalLight::default()` plus `Transform` |
| `SpatialBundle` | `Transform` — `Visibility` and the rest are required components |
| `TransformBundle` | `Transform` |
| `VisibilityBundle` | `Visibility` |
| `AudioBundle { source, .. }` | `AudioPlayer(handle)` |
| `Handle<AnimationGraph>` as a component | `AnimationGraphHandle(handle)` |

### BV-MIG-05 [M] Replace the old text API with the text components

Text is a root component plus per-run components, not a struct holding sections and a style.

**Why:** the old `Text { sections: Vec<TextSection> }` could not be queried per section, could not
be styled per section without rebuilding the vector, and had no way for a child entity to contribute
a run. The component form makes each of those an ordinary ECS operation — and 0.19 changed the
internals again, moving from `cosmic-text` to `parley`, which the component API absorbed without a
further break for game code.

**Check:** `rg -n  'TextStyle|TextSection|from_section|JustifyText|BreakLineOn|new_with_'
src/`.

| Removed | Write instead |
|---|---|
| `TextStyle { font, font_size, color }` | `TextFont { font, font_size, .. }` plus `TextColor(color)` |
| `Text::from_section(s, style)` | `Text::new(s)`, with `TextFont` and `TextColor` beside it |
| `Text { sections: vec![…] }` | a `Text` root with `TextSpan` children |
| `TextSection` (the struct) | `TextSpan` on a child entity |
| `JustifyText` | `Justify` |
| `BreakLineOn` | `LineBreak` |
| `TextLayout::new_with_justify(j)` | `TextLayout::justify(j)` |
| `TextLayout::new_with_linebreak(b)` | `TextLayout::linebreak(b)` |
| `TextLayout::new_with_no_wrap()` | `TextLayout::no_wrap()` |
| `TextFont { line_height, .. }` | the separate `LineHeight` component |
| `TextFont { font: Handle<Font>, .. }` | `TextFont { font: FontSource, .. }` |
| `TextFont { font_size: f32, .. }` | `TextFont { font_size: FontSize, .. }` |
| `Font::try_from_bytes` | `Font::from_bytes` |

### BV-MIG-06 [M] Replace the old UI node API

`Style` is `Node`, and `Node` is what used to be `NodeBundle`.

**Why:** the rename is a trap rather than a chore: `Node` existed in 0.14 as the *computed* layout
output, and in 0.15 it became the *input*. Old code that reads a `Node` to get a computed size
compiles against the new type and reads the wrong thing — the computed values are now
`ComputedNode`.

**Check:** `rg -n  'UiImage|UiImageSize|stack_index' src/`, and read every use of `Node` that
is asking for a computed size — that value is on `ComputedNode` and no grep can tell them apart.

| Removed | Write instead |
|---|---|
| `Style { .. }` | `Node { .. }` |
| `Node` used for computed layout | `ComputedNode` |
| `UiImage` | `ImageNode` |
| `UiImageSize` | `ImageNodeSize` |
| `BackgroundColor` on the same entity as `UiImage` | `ImageNode` carries its own colour |
| `ComputedNode::stack_index` | `ComputedStackIndex` |
| `Core`-prefixed widget components | the same names without `Core` |

## 0.16: hierarchy, queries, errors

### BV-MIG-07 [M] Replace `Parent` and the hierarchy commands with relationships

The hierarchy became an instance of the general relationship mechanism in 0.16, and the commands
were renamed again in 0.18.

**Why:** the parent link is now an ordinary component that any relationship-aware code can see,
which is what makes `despawn` recursive by default and what lets a game define its own one-to-many
links (BV-ECS-12). The knock-on renames are extensive because every hierarchy-specific method became
a relationship method.

**Check:** `rg -n
'despawn_(recursive|descendants)|push_children|set_parent|ChildBuilder|clear_(children|related)'
src/`.

| Removed | Write instead |
|---|---|
| `Parent` | `ChildOf` |
| `parent.get()` or `*parent` | `child_of.parent()` |
| `entity.set_parent(p)` | `entity.insert(ChildOf(p))` |
| `push_children(&[..])` | `add_children(&[..])` |
| `remove_children(&[..])` | `detach_children(&[..])` |
| `remove_child(c)` | `detach_child(c)` |
| `clear_children()` | `detach_all_children()` |
| `clear_related::<R>()` | `detach_all_related::<R>()` |
| `replace_children(&[..])` | remove `Children`, then `add_children(&[..])` |
| `despawn_recursive()` | `despawn()` |
| `despawn_descendants()` | `despawn_related::<Children>()` |
| `ChildBuilder` | `ChildSpawnerCommands` |
| `builder.parent_entity()` | `spawner.target_entity()` |
| `HierarchyQueryExt::parent()` | `Query::related()` |
| `HierarchyQueryExt::children()` | `Query::relationship_sources()` |

### BV-MIG-08 [M] Replace the panicking and deprecated query methods

0.16 reworked error handling: queries return `Result`, and systems may return one.

**Why:** it is the change that made BV-ERR-01 possible, and it is the reason so much old code has
`get_single().unwrap()` — the fallible method used to be the long-named one, so the short name was
the panicking one and everybody reached for it.

**Check:** `rg -n
'get_single|to_readonly|ManualEventReader|init_component|weak_from_u128|EntityFetchError' src/`.

| Removed | Write instead |
|---|---|
| `Query::get_single()` | `Query::single()`, which now returns `Result` |
| `Query::get_single_mut()` | `Query::single_mut()` |
| `Query::many(ids)` | `Query::get_many(ids)` |
| `Query::many_mut(ids)` | `Query::get_many_mut(ids)` |
| `Query::to_readonly()` | `Query::as_readonly()` |
| `App::observe` | `App::add_observer` |
| `Commands::observe` | `Commands::add_observer` |
| `ManualEventReader` | `MessageCursor` |
| `Events::get_reader()` | `Messages::get_cursor()` |
| `World::init_component` | `World::register_component` |
| `EntityFetchError` | `EntityMutableFetchError` |
| `bevy::a11y::Focus` | `bevy::input_focus::InputFocus` |
| `Handle::weak_from_u128(..)` | the `weak_handle!("…")` macro |

### BV-MIG-09 [M] Replace `Handle` used directly as a component (see BV-ECS-14)

Owned by `references/ecs.md` BV-ECS-14. `Handle<T>` stopped implementing `Component` in 0.15, and
the replacement is a named wrapper — which is what the engine did to its own: `Mesh3d`,
`MeshMaterial3d`, `AudioPlayer`, `AnimationGraphHandle`.

## 0.17: the big rename

### BV-MIG-10 [M] Replace the buffered-event vocabulary with messages

What 0.16 called an event, sent with `EventWriter` and read with `EventReader`, is now a message.
"Event" means an observed event only.

**Why:** this is the single largest source of stale Bevy code, because the old names are the obvious
ones and every tutorial uses them. The split is described in `references/events.md` BV-EVT-01; this
table is the mechanical half.

**Check:** `rg -n
'EventReader|EventWriter|Events<|send_event|add_event|on_event|RemovedComponentEvents' src/`.

| Removed | Write instead |
|---|---|
| `#[derive(Event)]` for a buffered event | `#[derive(Message)]` |
| `EventReader<E>` | `MessageReader<M>` |
| `EventWriter<E>` | `MessageWriter<M>` |
| `Events<E>` | `Messages<M>` |
| `EventWriter::send(e)` | `MessageWriter::write(m)` |
| `EventWriter::send_batch` | `MessageWriter::write_batch` |
| `EventWriter::send_default` | `MessageWriter::write_default` |
| `App::add_event::<E>()` | `App::add_message::<M>()` |
| `World::send_event` | `World::write_message` |
| `Commands::send_event` | `Commands::write_message` |
| `Events::send` | `Messages::write` |
| `on_event::<E>()` as a run condition | `on_message::<M>()` |
| `RemovedComponents::events` | `RemovedComponents::messages` |
| `RemovedComponentEvents` | `RemovedComponentMessages` |
| `SendBatchIds` | `WriteBatchIds` |

### BV-MIG-11 [M] Replace `Trigger` and the `On`-prefixed lifecycle events (see BV-EVT-14)

Owned by `references/events.md` BV-EVT-14. `Trigger<E>` is `On<E>`, the five lifecycle events lost
their `On` prefix because the prefix moved to the parameter type, and an event with a target is an
`EntityEvent` carrying the entity as a field.

### BV-MIG-12 [M] Rename every system set to end in `Systems`

0.17 renamed all of Bevy's own sets to a `*Systems` suffix and asked the ecosystem to follow.

**Why:** it is the convention BV-ARC-10 states, and the engine's own sets are the ones a game orders
against — so a `.after(TransformSystem::TransformPropagate)` in old code names a type that no longer
exists. The rename is mechanical but there are a lot of them.

**Check:** `rg -n
'(Transform|Ui|Input|Sprite|Time)System\b|(Render|Pick|Remote)Set\b|StateTransitionSteps'
src/`, and read any remaining set name that ends in `System`, `Set` or `Steps` rather than
`Systems`.

| Removed | Write instead |
|---|---|
| `TransformSystem` | `TransformSystems` |
| `RenderSet` | `RenderSystems` |
| `UiSystem` | `UiSystems` |
| `RenderUiSystem` | `RenderUiSystems` |
| `PickSet` | `PickingSystems` |
| `InputSystem` | `InputSystems` |
| `InputFocusSet` | `InputFocusSystems` |
| `SpriteSystem` | `SpriteSystems` |
| `TimeSystem` | `TimeSystems` |
| `AccessibilitySystem` | `AccessibilitySystems` |
| `GizmoRenderSystem` | `GizmoRenderSystems` |
| `RemoteSet` | `RemoteSystems` |
| `StateTransitionSteps` | `StateTransitionSystems` |
| `Animation` | `AnimationSystems` |
| `AssetEvents` | `AssetEventSystems` |
| `TrackAssets` | `AssetTrackingSystems` |
| `EventUpdates` | `MessageUpdateSystems` |
| `CameraUpdateSystem` | `CameraUpdateSystems` |
| `RunFixedMainLoopSystem` | `RunFixedMainLoopSystems` |

### BV-MIG-13 [M] Replace the remaining 0.17 renames

**Why:** these are the 0.17 changes outside the event and system-set families. They are individually
small and collectively the reason a 0.16 project does not compile.

**Check:** `rg -n
'compute_matrix|StateScoped|Gizmos::cuboid|RenderGraphApp|ComputedNodeTarget|SimpleExecutor'
src/`, plus `Timer::paused` and `Timer::finished`. The `Condition` rename is not greppable — the new
name contains the old one — so read the `SystemCondition` bound instead. `Pressed` is not greppable
either, and for the opposite reason: 0.19 has a live `bevy_ui::Pressed` in the prelude, a marker for
a widget being held down. Only `Pointer<Pressed>` is the removed one.

| Removed | Write instead |
|---|---|
| `Condition` | `SystemCondition` |
| `Pointer<Pressed>` / `Pointer<Released>` | `Pointer<Press>` / `Pointer<Release>` |
| `Timer::paused()` / `Timer::finished()` | `Timer::is_paused()` / `Timer::is_finished()` |
| `StateScoped` | `DespawnOnExit` |
| `Camera { hdr, .. }` | the separate `Hdr` component |
| `Window` as one component | `Window` split across several components |
| `Gizmos::cuboid` | `Gizmos::cube` |
| `Transform::compute_matrix` | `Transform::to_matrix` |
| `GlobalTransform::compute_matrix` | `GlobalTransform::to_matrix` |
| `RenderGraphApp` / `RenderGraphExt` | gone: a render pass is a system in the `Core2d` / `Core3d` schedule |
| `ComputedNodeTarget` | `ComputedUiTargetCamera` |
| `LightVisibilityClass` | `ClusterVisibilityClass` |
| `SimpleExecutor` | removed; use the single-threaded executor |

## 0.18 and 0.19

### BV-MIG-14 [M] Replace the 0.18 renames

**Why:** 0.18 is the smallest of the four releases for game code, but it renamed four cargo features
— which fail as "unknown feature" rather than as a type error, and are therefore easy to leave
behind in a manifest that still builds.

**Check:** `rg -n
'bevy_(sprite|ui|mesh)_picking_backend|event_target_mut|FontAtlasSets|AnimationTarget'
src/`, and the manifest for the renamed feature names.

| Removed | Write instead |
|---|---|
| feature `animation` | feature `gltf_animation` |
| feature `bevy_sprite_picking_backend` | feature `sprite_picking` |
| feature `bevy_ui_picking_backend` | feature `ui_picking` |
| feature `bevy_mesh_picking_backend` | feature `mesh_picking` |
| the `Internal` component | nothing; these entities are no longer hidden |
| `TextFont { line_height }` | the `LineHeight` component |
| `AmbientLight` as a resource only | a camera component plus `GlobalAmbientLight` |
| `RenderTarget` on the camera | `RenderTarget` as its own component |
| `EntityEvent::event_target_mut` | `SetEntityEventTarget`, which game code should not need |
| `ThinSlicePtr::get()` | `ThinSlicePtr::get_unchecked()` |
| `AnimationTarget` | the separate components that replaced it |
| `FontAtlasSets` | removed |

### BV-MIG-15 [M] Split a type that was both a component and a resource (see BV-STA-01)

Owned by `references/state.md` BV-STA-01. In 0.19 `Resource` is a subtrait of `Component`, so one
type can no longer be both — and `#[reflect(Resource)]` now also reflects `Component`, so reflection
code asks for `ReflectComponent`.

### BV-MIG-16 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean

0.19 renamed the old scene crate to `bevy_world_serialization` and gave the name `bevy_scene` to the
new `bsn!`-based scene system. The two are unrelated.

**Why:** this is the one rename in the whole table that silently means something else. A `use`
naming `bevy_scene` still resolves, and a cargo feature named `bevy_scene` still exists — in 0.18 it
enabled the serialization crate, and in 0.19 it enables the new scene system instead, so a manifest
that was never edited now turns on a different thing. Everything that was `Scene` is `WorldAsset`;
`Scene` is now a trait in the new system, and the `scene` collection enables both.

**Check:** `rg -n
'SceneRoot|DynamicScene|SceneSpawner|SceneFilter|SceneInstanceReady|SceneLoader' src/`, and read
every `bevy_scene` against this table rather than assuming — it is the one name that still resolves
and now means something else.

| 0.18 name | 0.19 name |
|---|---|
| crate `bevy_scene` | crate `bevy_world_serialization` |
| `Scene` (the asset) | `WorldAsset` |
| `SceneRoot` | `WorldAssetRoot` |
| `DynamicScene` | `DynamicWorld` |
| `DynamicSceneBuilder` | `DynamicWorldBuilder`, which now needs a `&TypeRegistry` |
| `DynamicScene::from_scene` | `DynamicWorld::from_world_asset`, which now needs a `&TypeRegistry` |
| `DynamicSceneRoot` | `DynamicWorldRoot` |
| `SceneInstanceReady` | `WorldInstanceReady` |
| `SceneSpawner` | `WorldInstanceSpawner` |
| `SceneLoader` | `WorldAssetLoader` |
| `ScenePlugin` | `WorldSerializationPlugin` — and `ScenePlugin` still exists, as the `bsn!` system's |
| `SceneFilter` | `WorldFilter` |
| `SceneLoaderError` | `WorldAssetLoaderError` |
| `SceneSpawnError` | `WorldInstanceSpawnError` |
| — | `bevy_scene` is now the `bsn!` scene system: `Scene`, `SceneList`, `ScenePatch` |

### BV-MIG-17 [M] Replace the remaining 0.19 renames

**Why:** these are the 0.19 changes a game touches. The non-send and executor entries are the ones
most likely to appear in an existing project's own plugin code.

**Check:** `rg -n
'DefaultErrorHandler|ExecutorKind|non_send_resource|ShaderStorageBuffer|earthlike|experimental_'
src/`.

| Removed | Write instead |
|---|---|
| `DefaultErrorHandler` | `FallbackErrorHandler` |
| `impl Command<Result>` | `impl Command { type Out = Result; }` |
| `ExecutorKind` / `set_executor_kind` | `set_executor(SingleThreadedExecutor::new())` and friends |
| `System::type_id` | `System::system_type` |
| `App::init_non_send_resource` | `App::init_non_send` |
| `World::non_send_resource(_mut)` | `World::non_send(_mut)` |
| `#[reflect(Resource)]` giving `ReflectResource` | ask for `ReflectComponent` |
| `ShaderStorageBuffer` | `ShaderBuffer` |
| `PipelineCacheError` | `ShaderCacheError` |
| `Atmosphere` on the camera | `Atmosphere` on its own entity |
| `Atmosphere::earthlike` | `Atmosphere::earth` |
| `WgpuSettingsPriority::Compatibility` | `WgpuSettingsPriority::WebGPU` |
| `Skybox { image: Handle<Image> }` | `Skybox { image: Option<Handle<Image>> }` |
| `Image::pixel_bytes` returning `Option` | it returns `Result` |
| `AssetPath::get_full_extension` returning `Option<String>` | it returns `Option<&str>` |
| `feathers` widget spawn functions | `button_bundle`, `checkbox_bundle`, `radio_bundle`, or `bsn!` |
| `FeathersPlugin` | `FeathersCorePlugin` |
| feature `experimental_bevy_feathers` | feature `bevy_feathers` |
| feature `experimental_ui_widgets` | feature `bevy_ui_widgets` |

## Changes that do not show up as a compile error

### BV-MIG-18 [M] Re-read every `Ref` that is cloned

In 0.19 `Ref<T>` implements `Clone` and `Copy` itself. `value.clone()` on a `Ref<T>` now produces a
`Ref<T>`, where it used to produce a `T`.

**Why:** this is a change of meaning that mostly does not change whether the code compiles —
`let owned = r.clone()` infers the new type and carries on, and only fails where the surrounding
code was explicit. Everything downstream then holds a borrow where it expected a value, which shows
up much later as a lifetime error in an unrelated function or as a value that tracks its source.

**Check:** grep for `.clone()` on anything of type `Ref<`. The old meaning is `r.deref().clone()` or
`r.as_ref().clone()`.

The other silent changes are stated where the topic lives: state transitions now fire on a
same-state `set` (`references/state.md` BV-STA-20), and `Resource` is now a `Component`
(`references/state.md` BV-STA-01).
