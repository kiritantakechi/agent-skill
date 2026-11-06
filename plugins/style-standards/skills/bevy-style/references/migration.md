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

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- **Using this chapter**
  - BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.20 until checked
  - BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop

- **0.15: bundles and text**
  - BV-MIG-03 [M] Replace every `*Bundle` with the components it inserted
  - BV-MIG-04 [M] Replace the old text API with the text components
  - BV-MIG-05 [M] Replace the old UI node API

- **0.16: hierarchy, queries, errors**
  - BV-MIG-06 [M] Replace `Parent` and the hierarchy commands with relationships
  - BV-MIG-07 [M] Replace the panicking and deprecated query methods

- **0.17: the big rename**
  - BV-MIG-08 [M] Replace the buffered-event vocabulary with messages
  - BV-MIG-09 [M] Rename every system set to end in `Systems`
  - BV-MIG-10 [M] Replace the remaining 0.17 renames

- **0.18 and 0.19**
  - BV-MIG-11 [M] Replace the 0.18 renames
  - BV-MIG-12 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean
  - BV-MIG-13 [M] Replace the remaining 0.19 renames

- **0.20: observers, pointers, deprecations**
  - BV-MIG-14 [M] Move the bundle off `On` and onto the lifecycle event
  - BV-MIG-15 [M] Flatten the pointer events
  - BV-MIG-16 [M] Replace what 0.20 deprecated
  - BV-MIG-17 [M] Replace the remaining 0.20 renames and removals

- **Changes that do not show up as a compile error**
  - BV-MIG-18 [M] Re-read every `Ref` that is cloned

- Decided by tools

---

## Using this chapter

### BV-MIG-01 [M] Assume unfamiliar Bevy code predates 0.20 until checked

Code from a tutorial, a blog post, an answer, or a language model was written against an older Bevy
until something proves otherwise — often 0.15, and at best 0.19. Check it against these tables
before adapting it.

**Why:** 0.17 renamed the event system, the observer parameter and every system set; 0.20 moved the
observer's bundle and flattened the pointer events. Nearly all Bevy material online predates one or
both, and adapting a pattern that no longer exists costs time and keeps the old names in mind.

**Check:** `rg -n '[a-z_]: Trigger<|\bEvent(Reader|Writer)\b|[A-Za-z0-9]Bundle\b' src/` and
`rg -n '\bOn<[A-Za-z0-9_:]+\s*,|\bPointer<|\.as_mut\(\)\.set_if_neq' src/` over the sample. Any hit
dates it, and so does a system set whose name does not end in `Systems`, or a `set_if_neq` whose
receiver is a `NextState` — which only reading finds, since `Mut::set_if_neq` is live.

### BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop

When a migration guide gives a new name, check whether that name still exists.

**Why:** some APIs move twice: `Pointer<Pressed>` became `Pointer<Press>` in 0.17 and `PointerPress`
in 0.20. Applying one release's guide and stopping leaves a name that was already renamed again.

**Check:** after applying a rename, grep the vendored source of the version you depend on for the
new name. If it is not there, the chain continued.

## 0.15: bundles and text

### BV-MIG-03 [M] Replace every `*Bundle` with the components it inserted

The `*Bundle` types were deprecated in 0.15 and are gone: each is the tuple of components in the
table below, with `#[require]` on the types that always travel together (BV-ECS-06). The `Bundle`
**trait** remains, as what a spawn tuple implements.

**Why:** it is the most visible break between old Bevy material and current Bevy, and the most
mechanical: each `XBundle::default()` becomes one or two components.

**Check:** `rg -n '[A-Za-z0-9]Bundle\b' src/`. Every hit is a removed type or a bundle of your own,
which BV-ECS-06 rules out. The three the engine still spells that way, `SpawnRelatedBundle`,
`ReflectBundle` and `DynamicBundle`, are machinery a game does not name.

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

### BV-MIG-04 [M] Replace the old text API with the text components

Text is a root component plus per-run components, not a struct holding sections and a style.

**Why:** the old `Text { sections: Vec<TextSection> }` could not be queried or styled per section
without rebuilding the vector, and no child entity could contribute a run. The component form makes
each of those an ordinary ECS operation.

**Check:**
`rg -n 'TextStyle|from_section|JustifyText|BreakLineOn|new_with_(justify|linebreak|no_wrap)' src/`
and `rg -n 'TextSection::(new|from_style)|TextSection \{|Vec<TextSection>' src/`. A bare
`TextSection` is not evidence: since 0.19 `bevy::text::TextSection` is a live trait, so only the old
struct's constructors, literal and vector are searched for.

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

### BV-MIG-05 [M] Replace the old UI node API

`Style` is `Node`, and `Node` is what used to be `NodeBundle`.

**Why:** the rename is a trap rather than a chore: `Node` changed meaning instead of disappearing,
so the compiler accepts a read written for the 0.14 meaning and hands back the requested size
(BV-VIEW-03).

**Check:** `rg -n 'UiImage|UiImageSize|stack_index' src/`, and read every use of `Node` that is
asking for a computed size — that value is on `ComputedNode` and no grep can tell them apart.

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

### BV-MIG-06 [M] Replace `Parent` and the hierarchy commands with relationships

The hierarchy became an instance of the general relationship mechanism in 0.16, and the commands
were renamed again in 0.18.

**Why:** the parent link is now an ordinary component any relationship-aware code can see, which
makes `despawn` recursive by default and lets a game define its own one-to-many links (BV-ECS-11).

**Check:**
`rg -n 'despawn_(recursive|descendants)|push_children|set_parent\b|ChildBuilder|clear_(children|related)' src/`.
It does not match `set_parent_in_place`, which is live and keeps the child's `GlobalTransform` by
rewriting its `Transform`; inserting `ChildOf` does not, so leave it alone.

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
| `despawn_recursive()` | `despawn()` |
| `despawn_descendants()` | `despawn_related::<Children>()` |
| `ChildBuilder` | `ChildSpawnerCommands` |
| `builder.parent_entity()` | `spawner.target_entity()` |
| `HierarchyQueryExt::parent()` | `Query::related()` |
| `HierarchyQueryExt::children()` | `Query::relationship_sources()` |

### BV-MIG-07 [M] Replace the panicking and deprecated query methods

0.16 reworked error handling: queries return `Result`, and systems may return one.

**Why:** it is the change that made BV-ERR-01 possible, and it is the reason so much old code has
`get_single().unwrap()` — the fallible method used to be the long-named one, so the short name was
the panicking one and everybody reached for it.

**Check:**
`rg -n '\bget_single(_mut)?\b|\bto_readonly\b|ManualEventReader|\binit_component\b|EntityFetchError\b[^(]' src/`
and `rg -n 'weak_from_u128|weak_handle!' src/`. `Gradient::get_single` is live, so read a hit whose
receiver is a `Gradient`; the `EntityFetchError(…)` variant of `EntityCommandError` is live too, and
the pattern skips it.

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
| `Handle::weak_from_u128(..)`, and the `weak_handle!` macro that replaced it | the `uuid_handle!("…")` macro: `weak_handle!` is deprecated, and `Handle` has only `Strong` and `Uuid` |

## 0.17: the big rename

### BV-MIG-08 [M] Replace the buffered-event vocabulary with messages

What 0.16 called an event, sent with `EventWriter` and read with `EventReader`, is now a message.
"Event" means an observed event only.

**Why:** this is the single largest source of stale Bevy code, because the old names are the obvious
ones and every tutorial uses them. The split is described in BV-EVENT-01; this table is the
mechanical half.

**Check:**
`rg -n '\bEvent(Reader|Writer)\b|\bEvents<|\bsend_event\b|\b(add|on)_event::<|RemovedComponentEvents' src/`.
The turbofish is the search: `AnimationClip::add_event` is live, and so is a tracing layer's
`on_event`.

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

### BV-MIG-09 [M] Rename every system set to end in `Systems`

0.17 renamed all of Bevy's own sets to a `*Systems` suffix and asked the ecosystem to follow.

**Why:** it is the convention BV-ARCH-10 states, and the engine's own sets are the ones a game
orders against — so a `.after(TransformSystem::TransformPropagate)` in old code names a type that no
longer exists. The rename is mechanical but there are a lot of them.

**Check:**
`rg -n '(Transform|Ui|Input|Sprite|Time)System\b|(Render|Pick|Remote)Set\b|StateTransitionSteps' src/`,
and read any remaining set name that ends in `System`, `Set` or `Steps` rather than `Systems`.

| Removed | Write instead |
|---|---|
| `TransformSystem` | `TransformSystems` |
| `RenderSet` | `RenderSystems` |
| `UiSystem` | `UiSystems` |
| `RenderUiSystem` | `RenderUiSystems` |
| `PickSet` | `PickingSystems` |
| `InputSystem` | `InputSystems` |
| `InputFocusSet` | `InputFocusSystems` |
| `SpriteSystem` | nothing: `SpriteSystems`, its 0.17 name, is gone from both `bevy::sprite` and `bevy::sprite_render` in 0.20 |
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

### BV-MIG-10 [M] Replace the remaining 0.17 renames

**Why:** these are the 0.17 changes outside the event and system-set families. They are individually
small and collectively the reason a 0.16 project does not compile.

**Check:**
`rg -n 'compute_matrix|\bStateScoped\b|Gizmos::cuboid|RenderGraphApp|ComputedNodeTarget|SimpleExecutor' src/`
and `rg -n '\.cursor_options\b|\bAnchor::[A-Z][a-z]' src/`, plus `Timer::paused` and
`Timer::finished`. The `Condition` rename is not greppable — the new name contains the old one — so
read the `SystemCondition` bound instead. `Pressed` is not greppable either, and for the opposite
reason: `bevy::ui::Pressed` is live, outside the prelude, a marker for a widget being held down.
Only `Pointer<Pressed>` is the removed one.

| Removed | Write instead |
|---|---|
| `Condition` | `SystemCondition` |
| `Pointer<Pressed>` / `Pointer<Released>` | `PointerPress` / `PointerRelease` — `Pointer<Press>` was the first hop, and is gone too |
| `Timer::paused()` / `Timer::finished()` | `Timer::is_paused()` / `Timer::is_finished()` |
| `StateScoped` | `DespawnOnExit` |
| `commands.trigger_targets(E, entity)` | an `EntityEvent` carrying its target as a field: `commands.trigger(E { entity })` |
| `Camera { hdr, .. }` | the separate `Hdr` component |
| `Window { cursor_options, .. }` | the separate `CursorOptions` component, which `Window` requires |
| `Sprite { anchor, .. }` | the separate `Anchor` component, which `Sprite` requires: a `Vec2` newtype whose old variants are constants, `Anchor::CENTER` for `Anchor::Center`, `Anchor(v)` for `Anchor::Custom(v)` |
| `Gizmos::cuboid` | `Gizmos::cube` |
| `Transform::compute_matrix` | `Transform::to_matrix` |
| `GlobalTransform::compute_matrix` | `GlobalTransform::to_matrix` |
| `RenderGraphApp` / `RenderGraphExt` | gone: a render pass is a system in the `Core2d` / `Core3d` schedule |
| `ComputedNodeTarget` | `ComputedUiTargetCamera` |
| `LightVisibilityClass` | `ClusterVisibilityClass` |
| `SimpleExecutor` | removed; use the single-threaded executor |

## 0.18 and 0.19

### BV-MIG-11 [M] Replace the 0.18 renames

**Why:** 0.18 is the smallest of the four releases for game code, but it renamed four cargo features
— which fail as "unknown feature" rather than as a type error, and are therefore easy to leave
behind in a manifest that still builds.

**Check:**
`rg -n 'bevy_(sprite|ui|mesh)_picking_backend|event_target_mut|FontAtlasSets|\bAnimationTarget\b' src/`,
and the manifest for the renamed feature names.

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

### BV-MIG-12 [M] Replace the old scene vocabulary, and know which `bevy_scene` you mean

0.19 renamed the old scene crate to `bevy_world_serialization` and gave the name `bevy_scene` to the
new `bsn!`-based scene system. The two are unrelated. Everything that was `Scene` is `WorldAsset`;
`Scene` is now a trait in the new system, the `scene` collection enables both, and since 0.20 a
scene reference inside `bsn!` takes `@` (BV-VIEW-09).

**Why:** a `use` naming `bevy_scene` still resolves, and the `bevy_scene` cargo feature still
exists: in 0.18 it enabled the serialization crate and since 0.19 the new scene system, so a
manifest nobody edited turns on a different thing.

**Check:**
`rg -n '\b(SceneRoot|SceneSpawner|SceneFilter|SceneInstanceReady)\b|\bDynamicScene|\bSceneLoader' src/`,
and read every `bevy_scene` against this table rather than assuming — it is the one name that still
resolves and now means something else.

| Removed | Write instead |
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

### BV-MIG-13 [M] Replace the remaining 0.19 renames

**Why:** these are the 0.19 changes a game touches. The non-send and executor entries are the ones
most likely to appear in an existing project's own plugin code.

**Check:**
`rg -n 'DefaultErrorHandler|ExecutorKind|non_send_resource|ShaderStorageBuffer|earthlike' src/` and
`rg -n 'Font::try_from_bytes' src/`, and the manifest for `experimental_bevy_feathers` and
`experimental_ui_widgets` — not every `experimental_` feature: `experimental_pbr_pcss` is live.

| Removed | Write instead |
|---|---|
| `DefaultErrorHandler` | `FallbackErrorHandler` |
| the lifecycle event `Replace`, its hook `on_replace` | `Discard`, `on_discard` |
| `impl Command<Result>` | `impl Command { type Out = Result; }` |
| `fn f() -> impl Command<Result>` | `fn f() -> impl Command`, its closure returning `Result` |
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
| `TextFont { font: Handle<Font>, .. }` | `TextFont { font: FontSource, .. }`; a handle is `FontSource::Handle(h)` |
| `TextFont { font_size: f32, .. }` | `TextFont { font_size: FontSize, .. }` |
| `Font::try_from_bytes(bytes)` | `Font::from_bytes(bytes)`, which returns the `Font` rather than a `Result` |
| `feathers` widget spawn functions, including 0.19's `button_bundle`, `checkbox_bundle`, `radio_bundle`, `slider_bundle`, `toggle_switch_bundle`, `color_*_bundle`, `virtual_keyboard_bundle` and `ButtonBundleProps` | the feathers `SceneComponent`s, used from `bsn!`: `FeathersButton` with `FeathersButtonProps`, and so on |
| `FeathersPlugin` | `FeathersCorePlugin` |
| feature `experimental_bevy_feathers` | feature `bevy_feathers` |
| feature `experimental_ui_widgets` | feature `bevy_ui_widgets` |

## 0.20: observers, pointers, deprecations

### BV-MIG-14 [M] Move the bundle off `On` and onto the lifecycle event

0.20 moved an observer's component filter off `On` and onto the lifecycle event: `On<Add, Enemy>` is
`On<Add<Enemy>>`. `Add<B>` has no default, so an observer for dynamic components is `On<Add<()>>`.

**Why:** the bundle sits in every lifecycle observer's signature, so every one in a 0.19 project
changes, and a custom `On<E, B>` has no one-line replacement: it becomes a wrapper type implementing
`EventPattern`.

**Check:** `rg -n '\bOn<[A-Za-z0-9_:]+\s*,|\bOn<(Add|Insert|Discard|Remove|Despawn)>' src/`. It does
not match `On<Add<Enemy>>`, because `<` follows `Add`.

| Removed | Write instead |
|---|---|
| `On<Add, T>`, `On<Insert, T>`, `On<Discard, T>`, `On<Remove, T>`, `On<Despawn, T>` | `On<Add<T>>`, `On<Insert<T>>`, `On<Discard<T>>`, `On<Remove<T>>`, `On<Despawn<T>>` |
| `On<Add>` (dynamic components with `.with_component(id)`) | `On<Add<()>>` |
| a custom `On<E, B>` | a `PhantomData` wrapper implementing `EventPattern { type Event; type Components }` |
| `IntoObserverSystem<E, B, M, Out>` | `IntoObserverSystem<E, M, Out>` |

### BV-MIG-15 [M] Flatten the pointer events

0.20 replaced the generic `Pointer<E>` with one event type per pointer event, and moved its fields
up a level: there is no `.event` and no `Deref`.

**Why:** every picking observer names its event type and reads its fields, so this touches every
click handler in a UI. `Pointer` still exists, non-generic, so a stale import resolves and only the
type argument fails.

**Check:** `rg -n '\bPointer<|\.pointer_location\b' src/`. `Pointer` is non-generic in 0.20, so any
`Pointer<` is stale. `.pointer_id` is not searchable, because `PointerInput::pointer_id` is live:
read each one whose receiver is a pointer event.

| Removed | Write instead |
|---|---|
| `Pointer<X>` for X in Over, Out, Enter, Leave, Press, Release, Click, Move, DragStart, Drag, DragEnd, DragEnter, DragOver, DragLeave, DragDrop, Scroll, Cancel | `PointerX`: `PointerClick`, `PointerPress`, … |
| `ev.event.button` | `ev.button` |
| `ev.pointer_id` | `ev.pointer.id` |
| `ev.pointer_location.position` | `ev.pointer.position` (`Vec2`); `ev.pointer.location()` for the `Location` |
| `fn f<E: …>(e: On<Pointer<E>>)` | `fn f<E: PointerEvent>(e: On<E>)` |

### BV-MIG-16 [M] Replace what 0.20 deprecated

0.20 deprecated these rather than removing them (`DeferredWorld::query` already in 0.19), all but
the `NextState` family in the first row, which 0.20 renamed outright. The rest compile with a
warning, which the shipped CI denies (the `deprecated` row in Decided by tools), so the searches are
for code not yet built against 0.20.

**Why:** a deprecated name still builds, so a port can look finished while it holds several, and one
of them, the prelude `Button`, shares its name with a live, correct API, so no search can find it.

**Check:**
`rg -n 'set_state_if_neq|PendingIfNeq|set_next_state_if_neq|\.as_mut\(\)\.set_if_neq' src/`,
`rg -n '\bInteraction\b|template_value|FilteredResources|\bTypeIdMap\b' src/` and
`rg -n 'AssetId::invalid|INVALID_UUID|try_reads_and_writes' src/`. Then read the one a search cannot
find: the deprecated `Button` has the same name as `bevy::ui_widgets::Button`, so read the import. A
`set_if_neq` on a `NextState` is spelled like the live `Mut::set_if_neq` too, but it no longer
compiles, so the build finds every one the search misses.

| Deprecated | Write instead |
|---|---|
| `NextState::set_if_neq` / `PendingIfNeq` / `set_state_if_neq` / `set_next_state_if_neq` | `set_if_different` / `PendingIfDifferent` / `set_state_if_different` / `set_next_state_if_different` — renamed, not deprecated: the old names do not compile |
| `Interaction` | `Hovered` plus `Pressed` |
| the prelude `Button` (`bevy::ui::widget::Button`) | `bevy::ui_widgets::Button` |
| `template_value(x)` in `bsn!` | `x` |
| `FilteredResources` (and its `Mut`, `*Builder` and `*ParamBuilder` forms) | `QueryParamBuilder` plus `Query<FilteredEntityRef>` plus `IsResource` |
| `DeferredWorld::query(&mut state)` | `state.query_mut(world)` |
| `TypeIdMap` / `TypeIdMapEntry` | `TypeIdHashMap` / `TypeIdIndexMap`, and their entry types |
| `AssetId::invalid()` / `AssetId::INVALID_UUID` | `Option<AssetId<_>>` |
| `DynamicEnum::from(_ref)` | `DynamicEnum::try_from(_ref)` |
| `Access::try_reads_and_writes` / `try_writes` | `Access::reads().as_finite_set()` / `writes().as_finite_set()` — `reads()` includes the writes |
| `,` and `()` between entities in `bsn!` | `--` |

### BV-MIG-17 [M] Replace the remaining 0.20 renames and removals

The rest of what 0.20 renamed or removed, across the Rust, the shaders and the manifest. Shaders are
WESL now (BV-VIEW-18), and a domain crate that names `glam` moves with Bevy (BV-ARCH-05).

**Why:** two of these keep their name and change meaning, which no build reports: the
`compressed_image_saver` feature now selects a BCn/ASTC backend, and `SpriteMaterial` is a new
public type unrelated to the old internal one.

**Check:** seven searches over the Rust,
`rg -n 'EditableTextInputPlugin|TextScroll|scroll_editable_text|resolve_font_source' src/`,
`rg -n 'FontSource::(Ui)?(Serif|SansSerif|Monospace)\b' src/`,
`rg -n 'FontSource::(Cursive|Fantasy|SystemUi|UiRounded|Emoji|Math|FangSong)\b' src/`,
`rg -n 'MeshTag\(|compute_aabb|with_attribute|Exclusive(SystemParam|Marker|FunctionSystem)' src/`,
`rg -n '\bFromType\b|meta_transform|UnpreparedBindGroup|ExtractedWindows' src/`,
`rg -n 'resolve_single_corner|VariantDefaults|bevy_math::(curve|cubic_splines|primitives)' src/` and
`rg -n '\.load_(override|acquire|with_settings)' src/`; one over the shaders,
`rg -n '--glob=*.wgsl' '#import|#ifdef|#define_import_path|#\{'`; then read the manifest for
`shader_format_(wesl|glsl)`, which is gone, every `compressed_image_saver`, which kept its name, and
a domain crate's `glam = "0.32"`, which moves to `"0.33"` with Bevy 0.20.

| Removed | Write instead |
|---|---|
| `EditableTextInputPlugin` | `TextInputPlugin` |
| `EditableText` as the whole widget | `TextInput`, which requires `EditableText` |
| `TextScroll`, `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) |
| `resolve_font_source(&font, fonts)` | `font.font.resolve_font_family(fonts)` |
| `FontSource::SansSerif`, `Serif`, `Monospace` and the other generic families | `FontSource::sans_serif()` and so on, or `FontSource::Generic` with a `GenericFontFamily` |
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
| `AssetServer::load_with_settings`, `load_override`, `load_acquire` and their combinations | `load_builder()` with `with_settings`, `override_unapproved` or `with_guard` (BV-ASSET-07) |
| `AssetServer::load_untyped`, `load_erased` | the same call on `load_builder()` |
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
| the old internal `bevy_sprite_render::SpriteMaterial` and `SpriteMaterialPlugin` | `SpriteMeshMaterial` and `SpriteMeshMaterialPlugin`; the public `SpriteMaterial` of 0.20 is a different type, the same trap as `bevy_scene` (BV-MIG-12) |
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

Each of these keeps compiling and changes what the code does, so no build flags it. SKILL.md §2.1 is
the same list, to read before writing code; this is the one to grep with.

| Changed | Find it with | Rule |
|---|---|---|
| 0.18: `next.set(S)` runs `OnExit(S)` and `OnEnter(S)` when the state is already `S` | `rg -n 'next.*\.set\(' src/`, then ask whether each can run in that state | BV-STATE-16 |
| 0.18: Bevy adds and updates the `Aabb` of meshes and sprites, so code that writes one fights the engine | `rg -n 'Aabb' src/` for a write | BV-VIEW-16 |
| 0.19: `AssetEvent::Modified` fires only on an actual mutation, so a `get_mut` that only reads no longer raises it | `rg -n 'AssetEvent' src/`, then whether each reaction relied on a read through `get_mut` | BV-ASSET-09 |
| 0.19: bloom computes its luminance in linear, so a tint tuned against sRGB luminance blooms more | `rg -n 'Bloom' src/`, then each tint against a linear judgement | BV-VIEW-11 |
| 0.19: a resource is a component on an entity of its own, and `Query<Entity>`, `Query<EntityRef>` and `Query<EntityMut>` match that entity — a sweep that despawns what it matches panics under the default error handler, `Query<EntityMut>` beside a `Res` panics with B0002, and a resource type spawned on a second entity is stripped from it with a warning | `rg -n 'Query<Entity' src/`, then whether each excludes resource entities | BV-STATE-01 |
| 0.19: `Ref<T>` implements `Clone`, so `.clone()` on one is another `Ref` | `.clone()` on anything of type `Ref<` | BV-MIG-18 |
| 0.20: `iter_many` and its variants yield `Result`, so `.count()` and `for _ in` take ids the query does not match | `rg -n 'iter_many' src/`, then whether each call counts or handles each `Result` | BV-ECS-20 |
| 0.20: a panic in a system, observer or command reaches the fallback error handler | the handler given to `set_error_handler`, for a re-panic on a panic payload | BV-ERR-05 |
| 0.20: `EditableText` without `TextInput` spawns and ignores the keyboard | `rg -n 'EditableText' src/` for a spawn with no `TextInput` | BV-VIEW-08 |
| 0.20: inside `UiSystems` and the render sets, systems the ECS sees no conflict between are unordered | each system placed there, for state shared outside the ECS | BV-SCHED-13 |

### BV-MIG-18 [M] Re-read every `Ref` that is cloned

Since 0.19 `Ref<T>` implements `Clone` and `Copy` itself. `value.clone()` on a `Ref<T>` now produces
a `Ref<T>`, where it used to produce a `T`.

**Why:** `let owned = r.clone()` infers the new type and carries on, failing only where the
surrounding code was explicit. Downstream code then holds a borrow where it expected a value, which
surfaces much later as a lifetime error in an unrelated function.

**Check:** grep for `.clone()` on anything of type `Ref<`. The old meaning is `r.deref().clone()` or
`r.as_ref().clone()`.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `deprecated` | warn | a deprecated Bevy API — CI denies warnings, so treat it as already removed |
