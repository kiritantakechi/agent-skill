# Migration: Every API Forbidden Since 0.15, and What Replaces It

Scope: the names that changed between Bevy 0.15 and 0.20, as a table of what to write instead. This
is the chapter to open when porting code, when reviewing something that looks like it came from a
tutorial, and when a name does not resolve.

Every right-hand column is the **0.20** spelling, not the first hop. Several of these renamed twice
— `EventWriter::send` became `EventWriter::write` in 0.16 and then `MessageWriter::write` in 0.17 —
and a table that stops at the first hop sends the reader to a name that is also gone.

The tables are not exhaustive for the engine; they are exhaustive for what a game writes. Rendering
internals, the render graph, pipeline specialisation and the reflection internals changed at least
as much, and the upstream migration guides are the reference for those.

## Contents

- **Using this chapter**
  - BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.17 until checked
  - BV-MIG-03 [M] Follow a rename to its 0.20 spelling, not its first hop

- **0.15: bundles and text**
  - BV-MIG-04 [M] Replace every `*Bundle` with the components it inserted
  - BV-MIG-05 [M] Replace the old text API with the text components
  - BV-MIG-06 [M] Replace the old UI node API

- **0.16: hierarchy, queries, errors**
  - BV-MIG-07 [M] Replace `Parent` and the hierarchy commands with relationships
  - BV-MIG-08 [M] Replace the panicking and deprecated query methods

- **0.17: the big rename**
  - BV-MIG-10 [M] Replace the buffered-event vocabulary with messages
  - BV-MIG-12 [M] Rename every system set to end in `Systems`
  - BV-MIG-13 [M] Replace the remaining 0.17 renames

- **0.18 and 0.19**
  - BV-MIG-14 [M] Replace the 0.18 renames
  - BV-MIG-16 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean
  - BV-MIG-17 [M] Replace the remaining 0.19 renames

- **0.20: observers, pointers, deprecations**
  - BV-MIG-91 [M] Move the bundle off `On` and onto the lifecycle event
  - BV-MIG-92 [M] Flatten the pointer events
  - BV-MIG-93 [M] Replace what 0.20 deprecated
  - BV-MIG-94 [M] Replace the remaining 0.20 renames and removals

- **Changes that do not show up as a compile error**
  - BV-MIG-18 [M] Re-read every `Ref` that is cloned
  - BV-MIG-95 [M] Re-read every `iter_many` and every logging error handler
- Decided by tools

---

## Using this chapter

### BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.17 until checked

Code from a tutorial, a blog post, an answer, or a language model is 0.15-era until something proves
otherwise. Check it against these tables before adapting it.

**Why:** 0.17 renamed the event system, the observer parameter and every system set, and most Bevy
material online predates it. The cost is not a compile error but time spent adapting a pattern that
no longer exists, and a mental model that keeps producing the old names.

**Check:** `rg -n  'Trigger<|EventReader|EventWriter|[A-Za-z0-9]Bundle' src/` over the sample.
Any hit dates it, and so does a system set whose name does not end in `Systems`.

### BV-MIG-03 [M] Follow a rename to its 0.20 spelling, not its first hop

When a migration guide gives a new name, check whether that name still exists.

**Why:** some APIs move twice: `Pointer<Pressed>` became `Pointer<Press>` in 0.17 and `PointerPress`
in 0.20. Applying one release's guide and stopping leaves a name that was already renamed again.

**Check:** after applying a rename, grep the vendored source of the version you depend on for the
new name. If it is not there, the chain continued.

## 0.15: bundles and text

### BV-MIG-04 [M] Replace every `*Bundle` with the components it inserted

The `*Bundle` types were deprecated in 0.15 and are gone. What replaces them is a tuple of
components at the spawn site plus `#[require]` on the types that always travel together. The
`Bundle` **trait** remains — it is what a spawn tuple implements — and so does its derive, which
BV-ECS-08 forbids you from using.

**Why:** it is the most visible break between old Bevy material and current Bevy, and the most
mechanical: each `XBundle::default()` becomes one or two components. It was made because a bundle
could be half-applied and a `#[require]` cannot (BV-ECS-06).

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
| `ButtonBundle::default()` | `bevy::ui_widgets::Button` plus `Node` — the prelude `Button` is deprecated |
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

**Why:** the old `Text { sections: Vec<TextSection> }` could not be queried or styled per section
without rebuilding the vector, and no child entity could contribute a run. The component form makes
each of those an ordinary ECS operation.

**Check:** `rg -n 'TextStyle|from_section|JustifyText|BreakLineOn|new_with_' src/` and
`rg -n 'TextSection::(new|from_style)|TextSection \{|Vec<TextSection>' src/`. A bare `TextSection`
is not evidence: since 0.19 `bevy::text::TextSection` is a live trait, so only the old struct's
constructors, literal and vector are searched for.

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
| `Font::try_from_bytes` | `Font::from_bytes(bytes)`, which no longer takes a family name |
| `FontSource::SansSerif`, `Serif`, `Monospace` and the other generic families | `FontSource::sans_serif()` and so on, or a `GenericFontFamily` |

### BV-MIG-06 [M] Replace the old UI node API

`Style` is `Node`, and `Node` is what used to be `NodeBundle`.

**Why:** the rename is a trap rather than a chore: `Node` changed meaning instead of disappearing,
so the compiler accepts a read written for the 0.14 meaning and hands back the requested size
(`references/view.md` BV-VIEW-03).

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

**Why:** the parent link is now an ordinary component any relationship-aware code can see, which
makes `despawn` recursive by default and lets a game define its own one-to-many links (BV-ECS-12).

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

## 0.17: the big rename

### BV-MIG-10 [M] Replace the buffered-event vocabulary with messages

What 0.16 called an event, sent with `EventWriter` and read with `EventReader`, is now a message.
"Event" means an observed event only.

**Why:** this is the single largest source of stale Bevy code, because the old names are the obvious
ones and every tutorial uses them. The split is described in `references/events.md` BV-EVENT-01;
this table is the mechanical half.

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

### BV-MIG-12 [M] Rename every system set to end in `Systems`

0.17 renamed all of Bevy's own sets to a `*Systems` suffix and asked the ecosystem to follow.

**Why:** it is the convention BV-ARCH-10 states, and the engine's own sets are the ones a game
orders against — so a `.after(TransformSystem::TransformPropagate)` in old code names a type that no
longer exists. The rename is mechanical but there are a lot of them.

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
| `SpriteSystem` | `bevy::sprite_render::SpriteSystems` — `bevy::sprite::SpriteSystems` is gone in 0.20 |
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
either, and for the opposite reason: `bevy::ui::Pressed` is live, outside the prelude, a marker for
a widget being held down. Only `Pointer<Pressed>` is the removed one.

| Removed | Write instead |
|---|---|
| `Condition` | `SystemCondition` |
| `Pointer<Pressed>` / `Pointer<Released>` | `PointerPress` / `PointerRelease` — `Pointer<Press>` was the first hop, and is gone too |
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

### BV-MIG-16 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean

0.19 renamed the old scene crate to `bevy_world_serialization` and gave the name `bevy_scene` to the
new `bsn!`-based scene system. The two are unrelated. Everything that was `Scene` is `WorldAsset`;
`Scene` is now a trait in the new system, the `scene` collection enables both, and since 0.20 a
scene reference inside `bsn!` takes `@` (`references/view.md` BV-VIEW-09).

**Why:** a `use` naming `bevy_scene` still resolves, and the `bevy_scene` cargo feature still
exists: in 0.18 it enabled the serialization crate and since 0.19 the new scene system, so a
manifest nobody edited turns on a different thing.

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
| `ShaderStorageBuffer` | `ShaderBuffer`, which in 0.20 lost `new(Vec<T>)`, `set_data` and `resize_in_place` |
| `PipelineCacheError` | `ShaderCacheError` |
| `Atmosphere` on the camera | `Atmosphere` on its own entity |
| `Atmosphere::earthlike` | `Atmosphere::earth` |
| `WgpuSettingsPriority::Compatibility` | `WgpuSettingsPriority::WebGPU` |
| `Skybox { image: Handle<Image> }` | `Skybox { image: Option<Handle<Image>> }` |
| `Image::pixel_bytes` returning `Option` | it returns `Result` |
| `AssetPath::get_full_extension` returning `Option<String>` | it returns `Option<&str>` |
| `feathers` widget spawn functions, including 0.19's `button_bundle`, `checkbox_bundle`, `radio_bundle`, `slider_bundle`, `toggle_switch_bundle`, `color_*_bundle`, `virtual_keyboard_bundle` and `ButtonBundleProps` | the feathers `SceneComponent`s, used from `bsn!`: `FeathersButton` with `FeathersButtonProps`, and so on |
| `FeathersPlugin` | `FeathersCorePlugin` |
| feature `experimental_bevy_feathers` | feature `bevy_feathers` |
| feature `experimental_ui_widgets` | feature `bevy_ui_widgets` |

## 0.20: observers, pointers, deprecations

### BV-MIG-91 [M] Move the bundle off `On` and onto the lifecycle event

0.20 moved an observer's component filter off `On` and onto the lifecycle event: `On<Add, Enemy>`
is `On<Add<Enemy>>`. `Add<B>` has no default, so an observer for dynamic components is
`On<Add<()>>`.

**Why:** the bundle sits in every lifecycle observer's signature, so every one in a 0.19 project
changes, and a custom `On<E, B>` has no one-line replacement: it becomes a wrapper type implementing
`EventPattern`.

**Check:** `rg -n '\bOn<[A-Za-z0-9_:]+\s*,|\bOn<(Add|Insert|Discard|Remove|Despawn)>' src/`. It
does not match `On<Add<Enemy>>`, because `<` follows `Add`.

| Removed | Write instead |
|---|---|
| `On<Add, T>`, `On<Insert, T>`, `On<Discard, T>`, `On<Remove, T>`, `On<Despawn, T>` | `On<Add<T>>`, `On<Insert<T>>`, `On<Discard<T>>`, `On<Remove<T>>`, `On<Despawn<T>>` |
| `On<Add>` (dynamic components with `.with_component(id)`) | `On<Add<()>>` |
| a custom `On<E, B>` | a `PhantomData` wrapper implementing `EventPattern { type Event; type Components }` |
| `IntoObserverSystem<E, B, M, Out>` | `IntoObserverSystem<E, M, Out>` |

### BV-MIG-92 [M] Flatten the pointer events

0.20 replaced the generic `Pointer<E>` with one event type per pointer event, and moved its fields
up a level: there is no `.event` and no `Deref`.

**Why:** every picking observer names its event type and reads its fields, so this touches every
click handler in a UI. `Pointer` still exists, non-generic, so a stale import resolves and only the
type argument fails.

**Check:** `rg -n '\bPointer<|pointer_id|pointer_location' src/`. `Pointer` is non-generic in 0.20,
so any `Pointer<` is stale.

| Removed | Write instead |
|---|---|
| `Pointer<X>` for X in Over, Out, Enter, Leave, Press, Release, Click, Move, DragStart, Drag, DragEnd, DragEnter, DragOver, DragLeave, DragDrop, Scroll, Cancel | `PointerX`: `PointerClick`, `PointerPress`, … |
| `ev.event.button` | `ev.button` |
| `ev.pointer_id` | `ev.pointer.id` |
| `ev.pointer_location.position` | `ev.pointer.position` (`Vec2`); `ev.pointer.location()` for the `Location` |
| `fn f<E: …>(e: On<Pointer<E>>)` | `fn f<E: PointerEvent>(e: On<E>)` |

### BV-MIG-93 [M] Replace what 0.20 deprecated

0.20 deprecated these rather than removing them. They compile with a warning, which the shipped CI
denies (the `deprecated` row in Decided by tools), so the searches are for code not yet built
against 0.20.

**Why:** a deprecated name still builds, so a port can look finished while it holds several, and two
of them share a name with a live, correct API, so no search can find them.

**Check:**
`rg -n 'set_state_if_neq|PendingIfNeq|set_next_state_if_neq|\.as_mut\(\)\.set_if_neq' src/`,
`rg -n '\bInteraction\b|template_value|FilteredResources|\bTypeIdMap\b' src/` and
`rg -n 'AssetId::invalid|INVALID_UUID|try_reads_and_writes' src/`. Then read the two that a search
cannot find. `NextState::set_if_neq` reached through `&mut NextState` looks exactly like
`Mut::set_if_neq`, which keeps its name and is correct, so read every `set_if_neq` whose receiver
is a `NextState`. The deprecated `Button` has the same name as `bevy::ui_widgets::Button`, so read
the import.

| Deprecated | Write instead |
|---|---|
| `NextState::set_if_neq` / `PendingIfNeq` / `set_state_if_neq` / `set_next_state_if_neq` | `set_if_different` / `PendingIfDifferent` / `set_state_if_different` / `set_next_state_if_different` |
| `Interaction` | `Hovered` plus `Pressed` |
| the prelude `Button` (`bevy::ui::widget::Button`) | `bevy::ui_widgets::Button` |
| `template_value(x)` in `bsn!` | `x` |
| `FilteredResources` (and its `Mut`, `*Builder` and `*ParamBuilder` forms) | `QueryParamBuilder` plus `Query<FilteredEntityRef>` plus `IsResource` |
| `DeferredWorld::query(&mut state)` | `state.query_mut(world)` |
| `TypeIdMap` / `TypeIdMapEntry` | `TypeIdHashMap` / `TypeIdIndexMap`, and their entry types |
| `AssetId::invalid()` / `AssetId::INVALID_UUID` | `Option<AssetId<_>>` |
| `DynamicEnum::from(_ref)` | `DynamicEnum::try_from(_ref)` |
| `Access::try_reads_and_writes` | `Access::reads()` |
| `,` and `()` between entities in `bsn!` | `--` |

### BV-MIG-94 [M] Replace the remaining 0.20 renames and removals

The rest of what 0.20 renamed or removed, across the Rust, the shaders and the manifest. Shaders are
WESL now (`references/view.md` BV-VIEW-18), and a domain crate that names `glam` moves with Bevy
(`references/architecture.md` BV-ARCH-05).

**Why:** two of these keep their name and change meaning, which no build reports: the
`compressed_image_saver` feature now selects a BCn/ASTC backend, and `SpriteMaterial` is a new
public type unrelated to the old internal one.

**Check:** six searches over the Rust,
`rg -n 'EditableTextInputPlugin|TextScroll|scroll_editable_text|resolve_font_source' src/`,
`rg -n 'FontSource::(Ui)?(Serif|SansSerif|Monospace)\b' src/`,
`rg -n 'FontSource::(Cursive|Fantasy|SystemUi|UiRounded|Emoji|Math|FangSong)\b' src/`,
`rg -n 'MeshTag\(|compute_aabb|with_attribute|Exclusive(SystemParam|Marker|FunctionSystem)' src/`,
`rg -n '\bFromType\b|meta_transform|UnpreparedBindGroup|ExtractedWindows' src/` and
`rg -n 'resolve_single_corner|VariantDefaults|bevy_math::(curve|cubic_splines|primitives)' src/`;
one over the shaders, `rg -n -t wgsl '#import|#ifdef|#define_import_path|#\{'`; then read the
manifest for `shader_format_(wesl|glsl)`, which is gone, every `compressed_image_saver`, which kept
its name, and a domain crate's `glam = "0.32"`, which moves to `"0.33"` with Bevy 0.20.

| Removed | Write instead |
|---|---|
| `EditableTextInputPlugin` | `TextInputPlugin` |
| `EditableText` as the whole widget | `TextInput`, which requires `EditableText` |
| `TextScroll`, `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) |
| `resolve_font_source(&font, fonts)` | `font.font.resolve_font_family(fonts)` |
| `FontSource::SansSerif` and the other generic families | `FontSource::sans_serif()` and so on |
| `MeshTag(x)`, `tag.0` | `MeshTag::new(x)`, `tag.value` |
| `MeshAabb::compute_aabb` | `MeshAabb::get_aabb` |
| `CustomAttributes::default().with_attribute(..)` | `CustomAttributesBuilder::new().attribute(..).build()` |
| `BorderRadius { top_left: Val, .. }` | `CornerRadius` fields, such as `px(10.).into()` |
| `BorderRadius::resolve_single_corner` | `CornerRadius::resolve` |
| `Val::resolve(scale, base, target)` | the same call with `em_size` and `rem_size` added |
| `FontSize::eval(vp, f32)` | `FontSize::eval(vp, RemSize(..))` |
| `CalculatedClip` as a struct | an enum with `Rects` and `FullyClipped` variants |
| `TextReader::text`, `font`, `color`, … | `TextReader::get`, which returns a `TextLayoutItem` |
| `ExclusiveSystemParam`, `ExclusiveFunctionSystem`, `ExclusiveSystemParamFunction`, `ExclusiveMarker` | removed: `&mut World` is a `SystemParam` |
| `System::is_exclusive()` | `SystemAccess::is_exclusive()` |
| a `WorldId` parameter in an exclusive system | `Local<WorldId>` or `world.id()` |
| `WorldQuery` default methods | an implementation of `init_nested_access` and `update_archetypes` |
| `FromType<T>` / `from_type()` | `CreateTypeData<T>` / `create_type_data(())` |
| `ReflectFromPtr::as_reflect(_mut)` | `ReflectFromPtr::ptr_as_reflect(_mut)` |
| `from_ptr(_mut)` | `raw_pointer_cast` |
| `PartialReflect::to_dynamic` returning a value | it returns `Result` |
| `UntypedHandle::meta_transform` | removed |
| `Name::from(&str)` on a non-`'static` string | `Name::new(s.to_owned())` |
| `Ptr::as_ptr` returning `*mut u8` | it returns `*const u8` |
| `UiCameraMapper::current_camera()` returning `Entity::PLACEHOLDER` | it returns `Option<Entity>` |
| `ComponentInfo::id()` | the `ComponentId` it was looked up by |
| `define_label!(X, INTERNER)` | `define_label!(X,)` |
| `SyncComponent` | `SyncComponent<RenderApp>` |
| `#[derive(ExtractComponent)]` alone | plus `#[extract_app(RenderApp)]` |
| `TemporaryRenderEntity` | `TemporaryRenderEntity::default()` |
| `UnpreparedBindGroup` / `unprepared_bind_group` | `BindGroupBuilder` / `build_bind_group` |
| `ExtractedWindows` | `Query<&ExtractedWindow>` |
| `SortedCamera::hdr` | `ExtractedCamera::hdr` |
| `WgpuWrapper` | removed |
| the old internal `bevy_sprite_render::SpriteMaterial` and `SpriteMaterialPlugin` | `SpriteMeshMaterial` and `SpriteMeshMaterialPlugin`; the public `SpriteMaterial` of 0.20 is a different type, the same trap as `bevy_scene` (BV-MIG-16) |
| `bevy_feathers::cursor` | `bevy_picking::cursor` |
| the `UpdateNumberInput` trigger | inserting `NumberInputValue` |
| `Tonemapping::None` meaning "no curve" | `Tonemapping::Linear` |
| `bevy_math::{curve, cubic_splines, Curve}` | `bevy_curve` |
| `bevy_math::primitives::*`, `Bounded2d`, … | `bevy_shape` |
| the `VariantDefaults` derive | removed; the enum needs `Default` and `Clone` |
| a `.wgsl` using `#import`, `#ifdef` or `#define_import_path` | a `.wesl` using `import …;` and `@if(…)` |
| `#{MATERIAL_BIND_GROUP}` | `constants::MATERIAL_BIND_GROUP` |
| `bevy_pbr::mesh_view_bindings` | `bevy_pbr::render::mesh_view_bindings` |
| feature `shader_format_wesl`, `shader_format_glsl` | gone, and GLSL support with them |
| feature `compressed_image_saver` (Basis) | `compressed_image_saver_universal`; the old name now selects a BCn/ASTC backend |
| feature `bevy_math/curve` | feature `bevy/bevy_curve` |

## Changes that do not show up as a compile error

### BV-MIG-18 [M] Re-read every `Ref` that is cloned

Since 0.19 `Ref<T>` implements `Clone` and `Copy` itself. `value.clone()` on a `Ref<T>` now produces
a `Ref<T>`, where it used to produce a `T`.

**Why:** `let owned = r.clone()` infers the new type and carries on, failing only where the
surrounding code was explicit. Downstream code then holds a borrow where it expected a value, which
surfaces much later as a lifetime error in an unrelated function.

**Check:** grep for `.clone()` on anything of type `Ref<`. The old meaning is `r.deref().clone()` or
`r.as_ref().clone()`.

The other silent changes are stated where the topic lives: state transitions now fire on a
same-state `set` (`references/state.md` BV-STATE-20), and `Resource` is now a `Component`
(`references/state.md` BV-STATE-01). The three from 0.20 — panics reaching the error handler,
`iter_many` yielding `Result`, and `EditableText` alone being inert — are BV-MIG-95.

### BV-MIG-95 [M] Re-read every `iter_many` and every logging error handler

Three 0.20 changes keep compiling and change what the code does:

- `iter_many` and its `_mut`, `_unique`, sorted and `par_` variants yield
  `Result<Item, QueryEntityError>`. `.count()`, `.next().is_some()` and `for _ in` keep compiling
  and now include ids the query does not match; `.matched()` is the old meaning
  (`references/ecs.md` BV-ECS-22).
- The `FallbackErrorHandler` now receives every panic in a system, observer or command, so a handler
  that logs without re-panicking swallows them (`references/errors.md` BV-ERR-05).
- An `EditableText` without `TextInput` spawns and ignores the keyboard
  (`references/view.md` BV-VIEW-08).

**Why:** each changes behaviour without changing a type the code names: a count over `Result` items
is still a `usize`, a logging handler still compiles, and the inert field still spawns. Only the
call site tells them apart.

**Check:** `rg -n 'iter_many' src/` finds the calls; whether a call counts or tests for presence,
rather than handling each `Result`, decides, and that is often not on the line. Then read the
function given to `FallbackErrorHandler` for a re-panic on a panic payload, and every spawn that
names `EditableText` for a `TextInput`.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `deprecated` | warn | a deprecated Bevy API — CI denies warnings, so treat it as already removed |

## Rule IDs before the Bevy 0.20.0 revision

Every rule ID this standard used before the revision, and what it is now.

| Before | Now |
|---|---|
| `BV-ARC-01` | `BV-ARCH-01` |
| `BV-ARC-02` | `BV-ARCH-02` |
| `BV-ARC-03` | `BV-ARCH-03` |
| `BV-ARC-04` | `BV-ARCH-04` |
| `BV-ARC-05` | `BV-ARCH-05` |
| `BV-ARC-06` | `BV-ARCH-06` |
| `BV-ARC-07` | `BV-ARCH-07` |
| `BV-ARC-08` | `BV-ARCH-08` |
| `BV-ARC-09` | `BV-ARCH-09` |
| `BV-ARC-10` | `BV-ARCH-10` |
| `BV-ARC-11` | `BV-ARCH-11` |
| `BV-ARC-12` | `BV-ARCH-12` |
| `BV-ARC-13` | `BV-ARCH-13` |
| `BV-ARC-14` | `BV-ARCH-14` |
| `BV-ARC-15` | `BV-ARCH-15` |
| `BV-ARC-16` | `BV-ARCH-16` |
| `BV-ARC-17` | `BV-ARCH-17` |
| `BV-ARC-18` | `BV-ARCH-18` |
| `BV-ARC-19` | `BV-ARCH-19` |
| `BV-ASS-01` | `BV-ASSET-01` |
| `BV-ASS-02` | `BV-ASSET-02` |
| `BV-ASS-03` | `BV-ASSET-03` |
| `BV-ASS-04` | `BV-ECS-14` |
| `BV-ASS-05` | `BV-ASSET-05` |
| `BV-ASS-06` | `BV-ASSET-06` |
| `BV-ASS-07` | `BV-ASSET-07` |
| `BV-ASS-08` | `BV-ASSET-08` |
| `BV-ASS-09` | `BV-ASSET-09` |
| `BV-ASS-10` | `BV-ASSET-10` |
| `BV-ASS-11` | `BV-ASSET-11` |
| `BV-ASS-12` | `BV-ASSET-12` |
| `BV-ASS-13` | `BV-ASSET-13` |
| `BV-ASS-14` | `BV-ASSET-14` |
| `BV-CAR-01` | `BV-BUILD-01` |
| `BV-CAR-02` | `BV-BUILD-02` |
| `BV-CAR-03` | `BV-BUILD-03` |
| `BV-CAR-04` | `BV-BUILD-04` |
| `BV-CAR-05` | `BV-BUILD-05` |
| `BV-CAR-06` | `BV-BUILD-06` |
| `BV-CAR-07` | `BV-BUILD-07` |
| `BV-CAR-08` | `BV-BUILD-08` |
| `BV-CAR-09` | `BV-BUILD-09` |
| `BV-CAR-10` | `BV-BUILD-10` |
| `BV-CAR-11` | `BV-BUILD-11` |
| `BV-CAR-12` | `BV-BUILD-12` |
| `BV-CAR-13` | `BV-BUILD-13` |
| `BV-CAR-14` | `BV-BUILD-14` |
| `BV-CAR-15` | `BV-BUILD-15` |
| `BV-CAR-16` | `BV-BUILD-16` |
| `BV-CAR-17` | `BV-BUILD-17` |
| `BV-CAR-18` | `BV-BUILD-18` |
| `BV-CAR-19` | `BV-BUILD-19` |
| `BV-CAR-20` | `BV-BUILD-20` |
| `BV-CAR-21` | `BV-BUILD-21` |
| `BV-ECS-01` | `BV-ECS-01` |
| `BV-ECS-02` | `BV-ECS-02` |
| `BV-ECS-03` | `BV-ECS-03` |
| `BV-ECS-04` | `BV-ECS-04` |
| `BV-ECS-05` | `BV-ECS-05` |
| `BV-ECS-06` | `BV-ECS-06` |
| `BV-ECS-07` | `BV-ECS-07` |
| `BV-ECS-08` | `BV-ECS-08` |
| `BV-ECS-09` | `BV-ECS-09` |
| `BV-ECS-10` | `BV-ECS-10` |
| `BV-ECS-11` | `BV-ECS-11` |
| `BV-ECS-12` | `BV-ECS-12` |
| `BV-ECS-13` | `BV-ECS-13` |
| `BV-ECS-14` | `BV-ECS-14` |
| `BV-ECS-15` | `BV-ECS-15` |
| `BV-ECS-16` | `BV-ECS-16` |
| `BV-ECS-17` | `BV-ECS-17` |
| `BV-ECS-18` | `BV-ECS-18` |
| `BV-ECS-19` | lint `clippy:unwrap_used` |
| `BV-ECS-20` | `BV-ECS-20` |
| `BV-ECS-21` | `BV-ECS-21` |
| `BV-ECS-22` | `BV-ECS-22` |
| `BV-ECS-23` | `BV-ECS-23` |
| `BV-ECS-24` | `BV-ECS-24` |
| `BV-ECS-25` | `BV-ECS-25` |
| `BV-ECS-26` | `BV-ECS-26` |
| `BV-ECS-27` | `BV-ECS-27` |
| `BV-ECS-28` | `BV-ECS-28` |
| `BV-ECS-29` | `BV-ECS-29` |
| `BV-ECS-30` | `BV-ECS-30` |
| `BV-ECS-31` | `BV-ECS-31` |
| `BV-ECS-32` | `BV-ECS-32` |
| `BV-ERR-01` | `BV-ERR-01` |
| `BV-ERR-02` | `BV-ERR-02` |
| `BV-ERR-03` | `BV-ERR-03` |
| `BV-ERR-04` | `BV-ERR-04` |
| `BV-ERR-05` | `BV-ERR-05` |
| `BV-ERR-06` | `BV-ERR-06` |
| `BV-ERR-07` | lint `clippy:unwrap_used` |
| `BV-ERR-08` | lint `clippy:indexing_slicing` |
| `BV-ERR-09` | `BV-ERR-09` |
| `BV-ERR-10` | `BV-ERR-10` |
| `BV-ERR-11` | `BV-ERR-11` |
| `BV-ERR-12` | `BV-ERR-12` |
| `BV-ERR-13` | `BV-ERR-13` |
| `BV-ERR-14` | `BV-ERR-14` |
| `BV-ERR-15` | `BV-ERR-15` |
| `BV-ERR-16` | `BV-ERR-16` |
| `BV-ERR-17` | `BV-ERR-17` |
| `BV-EVT-01` | `BV-EVENT-01` |
| `BV-EVT-02` | `BV-EVENT-02` |
| `BV-EVT-03` | `BV-EVENT-03` |
| `BV-EVT-04` | `BV-EVENT-04` |
| `BV-EVT-05` | `BV-EVENT-05` |
| `BV-EVT-06` | `BV-EVENT-06` |
| `BV-EVT-07` | `BV-EVENT-07` |
| `BV-EVT-08` | `BV-EVENT-08` |
| `BV-EVT-09` | `BV-EVENT-09` |
| `BV-EVT-10` | `BV-EVENT-10` |
| `BV-EVT-11` | `BV-EVENT-11` |
| `BV-EVT-12` | `BV-EVENT-12` |
| `BV-EVT-13` | `BV-EVENT-13` |
| `BV-EVT-14` | `BV-EVENT-14` |
| `BV-EVT-15` | `BV-EVENT-15` |
| `BV-EVT-16` | `BV-EVENT-16` |
| `BV-EVT-17` | `BV-EVENT-17` |
| `BV-EVT-18` | `BV-EVENT-18` |
| `BV-EVT-19` | `BV-EVENT-19` |
| `BV-EVT-20` | `BV-EVENT-20` |
| `BV-MIG-01` | `BV-MIG-01` |
| `BV-MIG-02` | lint `rustc:deprecated` |
| `BV-MIG-03` | `BV-MIG-03` |
| `BV-MIG-04` | `BV-MIG-04` |
| `BV-MIG-05` | `BV-MIG-05` |
| `BV-MIG-06` | `BV-MIG-06` |
| `BV-MIG-07` | `BV-MIG-07` |
| `BV-MIG-08` | `BV-MIG-08` |
| `BV-MIG-09` | `BV-ECS-14` |
| `BV-MIG-10` | `BV-MIG-10` |
| `BV-MIG-11` | `BV-EVENT-14` |
| `BV-MIG-12` | `BV-MIG-12` |
| `BV-MIG-13` | `BV-MIG-13` |
| `BV-MIG-14` | `BV-MIG-14` |
| `BV-MIG-15` | `BV-STATE-01` |
| `BV-MIG-16` | `BV-MIG-16` |
| `BV-MIG-17` | `BV-MIG-17` |
| `BV-MIG-18` | `BV-MIG-18` |
| `BV-SCH-01` | `BV-SCHED-01` |
| `BV-SCH-02` | `BV-SCHED-02` |
| `BV-SCH-03` | `BV-SCHED-03` |
| `BV-SCH-04` | `BV-SCHED-04` |
| `BV-SCH-05` | `BV-SCHED-05` |
| `BV-SCH-06` | `BV-SCHED-06` |
| `BV-SCH-07` | `BV-SCHED-07` |
| `BV-SCH-08` | `BV-SCHED-08` |
| `BV-SCH-09` | `BV-SCHED-09` |
| `BV-SCH-10` | `BV-SCHED-10` |
| `BV-SCH-11` | `BV-SCHED-11` |
| `BV-SCH-12` | `BV-SCHED-12` |
| `BV-SCH-13` | `BV-SCHED-13` |
| `BV-SCH-14` | `BV-SCHED-14` |
| `BV-SCH-15` | `BV-SCHED-15` |
| `BV-SCH-16` | `BV-SCHED-16` |
| `BV-SCH-17` | `BV-SCHED-17` |
| `BV-SCH-18` | `BV-SCHED-18` |
| `BV-SCH-19` | `BV-SCHED-19` |
| `BV-SCH-20` | `BV-SCHED-20` |
| `BV-SCH-21` | `BV-SCHED-21` |
| `BV-SCH-22` | `BV-SCHED-22` |
| `BV-SCH-23` | `BV-SCHED-23` |
| `BV-SCH-24` | `BV-SCHED-24` |
| `BV-SCH-25` | `BV-SCHED-25` |
| `BV-SCH-26` | `BV-SCHED-26` |
| `BV-STA-01` | `BV-STATE-01` |
| `BV-STA-02` | `BV-STATE-02` |
| `BV-STA-03` | `BV-STATE-03` |
| `BV-STA-04` | `BV-STATE-04` |
| `BV-STA-05` | `BV-STATE-05` |
| `BV-STA-06` | `BV-STATE-06` |
| `BV-STA-07` | `BV-STATE-07` |
| `BV-STA-08` | `BV-STATE-08` |
| `BV-STA-09` | `BV-STATE-09` |
| `BV-STA-10` | `BV-STATE-10` |
| `BV-STA-11` | `BV-STATE-11` |
| `BV-STA-12` | `BV-STATE-12` |
| `BV-STA-13` | `BV-STATE-13` |
| `BV-STA-14` | `BV-STATE-14` |
| `BV-STA-15` | `BV-STATE-15` |
| `BV-STA-16` | `BV-SCHED-21` |
| `BV-STA-17` | `BV-STATE-17` |
| `BV-STA-18` | `BV-STATE-18` |
| `BV-STA-19` | `BV-STATE-19` |
| `BV-STA-20` | `BV-STATE-20` |
| `BV-STA-21` | `BV-STATE-21` |
| `BV-STA-22` | `BV-STATE-22` |
| `BV-TST-01` | `BV-TEST-01` |
| `BV-TST-02` | `BV-TEST-02` |
| `BV-TST-03` | `BV-TEST-03` |
| `BV-TST-04` | `BV-TEST-04` |
| `BV-TST-05` | `BV-TEST-05` |
| `BV-TST-06` | `BV-TEST-06` |
| `BV-TST-07` | `BV-TEST-07` |
| `BV-TST-08` | `BV-TEST-08` |
| `BV-TST-09` | `BV-TEST-09` |
| `BV-TST-10` | `BV-TEST-10` |
| `BV-TST-11` | `BV-TEST-11` |
| `BV-TST-12` | `BV-TEST-12` |
| `BV-TST-13` | `BV-TEST-13` |
| `BV-TST-14` | `BV-TEST-14` |
| `BV-TST-15` | `BV-TEST-15` |
| `BV-UI-01` | `BV-VIEW-01` |
| `BV-UI-02` | `BV-VIEW-02` |
| `BV-UI-03` | `BV-VIEW-03` |
| `BV-UI-04` | `BV-VIEW-04` |
| `BV-UI-05` | `BV-VIEW-05` |
| `BV-UI-06` | `BV-VIEW-06` |
| `BV-UI-07` | `BV-VIEW-07` |
| `BV-UI-08` | `BV-VIEW-08` |
| `BV-UI-09` | `BV-VIEW-09` |
| `BV-UI-10` | `BV-VIEW-10` |
| `BV-UI-11` | `BV-VIEW-11` |
| `BV-UI-12` | `BV-VIEW-12` |
| `BV-UI-13` | `BV-VIEW-13` |
| `BV-UI-14` | `BV-VIEW-14` |
| `BV-UI-15` | `BV-VIEW-15` |
| `BV-UI-16` | `BV-VIEW-16` |
| `BV-UI-17` | `BV-VIEW-17` |
| `BV-UI-18` | `BV-VIEW-18` |
| `BV-UI-19` | `BV-VIEW-19` |
| `BV-UI-20` | `BV-VIEW-20` |
| `BV-UI-21` | `BV-VIEW-21` |
