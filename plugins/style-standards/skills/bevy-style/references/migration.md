# Migration: Old Spellings Since 0.15, and What Replaced Them

Scope: every spelling a game writes that Bevy 0.15 through 0.20 removed, renamed, changed or
deprecated, keyed by the old spelling, with the rule that owns it. What changed under existing code
with no spelling to key it is its owning rule's to state. Why a spelling is wrong is its owning
rule's to say; this chapter is the table and the command it generates. The engine's rendering
internals, render graph, pipeline specialisation and reflection internals changed as much and are
not in it: no rule of this standard reaches them, and the upstream migration guides are their
reference.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- Old spellings
- **Reading the table**
  - BV-MIG-01 [M] Check unfamiliar Bevy code against this chapter before adapting it
  - BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop
  - BV-MIG-03 [M] Re-read every `Ref` that is cloned
- Decided by tools

---

## Old spellings

A row's status says what Bevy 0.20 does with its old spelling under the shipped configuration:
`gone` — it rejects it, as an item it does not have or a shape it does not accept, so the build
fails where it stands; `changed` — it accepts it, and it means something else, so its owning rule's
Check finds it; `deprecated` — it accepts it, and it means what it did, with a warning, which the
shipped CI's `CARGO_BUILD_WARNINGS: deny` makes a failed build. No row is an `alias`: Bevy keeps no
old name working beside its new one. A spelling with `…` in it is a shape: code left out where the
`…` stands, which no fixed string finds, so its owning rule's Check does. Its Since is the release
from which it does so: for a `gone` row the first without the item, which for a name deprecated
first is a release after the one that renamed it. Section 2.1 lists the `changed` rows of 0.20 and
section 2.2 the `gone` ones. A row may stand for a family its 0.20 column names. The command after
the table finds every `gone` spelling the code writes out but a shape; a removed method keyed by its
type, `Timer::finished`, is called on a value, `timer.finished()`, which names no type a fixed
string can see, and the compiler rejects it.

| Old | Bevy 0.20 | Status | Since | Rule |
|---|---|---|---|---|
| `SpriteBundle` | `Sprite::from_image(handle)` plus `Transform` | gone | 0.16 | BV-ECS-06 |
| `SpriteSheetBundle` | `Sprite::from_atlas_image(handle, atlas)` | gone | 0.15 | BV-ECS-06 |
| `PbrBundle` | `Mesh3d(mesh)` plus `MeshMaterial3d(material)` | gone | 0.16 | BV-ECS-06 |
| `MaterialMesh2dBundle` | `Mesh2d(mesh)` plus `MeshMaterial2d(material)` | gone | 0.16 | BV-ECS-06 |
| `ImageBundle` | `ImageNode::new(handle)` | gone | 0.16 | BV-ECS-06 |
| `PointLightBundle` | `PointLight::default()` plus `Transform` | gone | 0.16 | BV-ECS-06 |
| `DirectionalLightBundle` | `DirectionalLight::default()` plus `Transform` | gone | 0.16 | BV-ECS-06 |
| `SpatialBundle` | `Transform`; `Visibility` and the rest are required components | gone | 0.16 | BV-ECS-06 |
| `TransformBundle` | `Transform` | gone | 0.16 | BV-ECS-06 |
| `VisibilityBundle` | `Visibility` | gone | 0.16 | BV-ECS-06 |
| `AudioBundle` | `AudioPlayer(handle)` | gone | 0.16 | BV-ECS-06 |
| `NodeBundle` | `Node::default()` | gone | 0.16 | BV-VIEW-01 |
| `ButtonBundle` | `bevy::ui_widgets::Button` plus `Node` | gone | 0.16 | BV-VIEW-06 |
| `Camera2dBundle` | `Camera2d` | gone | 0.16 | BV-VIEW-12 |
| `Camera3dBundle` | `Camera3d::default()` | gone | 0.16 | BV-VIEW-12 |
| `TextBundle` | `Text::new(s)` plus `TextFont` and `TextColor` | gone | 0.16 | BV-VIEW-04 |
| `Text2dBundle` | `Text2d::new(s)` plus `TextFont` and `TextColor` | gone | 0.16 | BV-VIEW-04 |
| `TextStyle` | `TextFont { font, font_size, .. }` plus `TextColor(color)` | gone | 0.15 | BV-VIEW-04 |
| `Text::from_section` | `Text::new(s)`, with `TextFont` and `TextColor` beside it | gone | 0.15 | BV-VIEW-04 |
| `JustifyText` | `Justify` | gone | 0.17 | BV-VIEW-04 |
| `BreakLineOn` | `LineBreak` | gone | 0.15 | BV-VIEW-04 |
| `TextLayout::new_with_justify` | `TextLayout::justify(j)` | gone | 0.19 | BV-VIEW-04 |
| `TextLayout::new_with_linebreak` | `TextLayout::linebreak(b)` | gone | 0.19 | BV-VIEW-04 |
| `TextLayout::new_with_no_wrap` | `TextLayout::no_wrap()` | gone | 0.19 | BV-VIEW-04 |
| `resolve_font_source` | `font.font.resolve_font_family(fonts)` | gone | 0.20 | BV-VIEW-04 |
| `FontSource::SansSerif` | `FontSource::sans_serif()`, or `FontSource::Generic` with a `GenericFontFamily`; every generic family variant likewise | gone | 0.20 | BV-VIEW-04 |
| `Style` | `Node` | gone | 0.15 | BV-VIEW-01 |
| `UiImage` | `ImageNode`, which carries its own colour | gone | 0.15 | BV-VIEW-01 |
| `UiImageSize` | `ImageNodeSize` | gone | 0.15 | BV-VIEW-01 |
| `ComputedNode::stack_index` | `ComputedStackIndex` | gone | 0.19 | BV-VIEW-03 |
| `ComputedNodeTarget` | `ComputedUiTargetCamera` | gone | 0.17 | BV-VIEW-03 |
| `CoreScrollbarThumb` | `ScrollbarThumb`; `CoreScrollbarDragState` and `CoreSliderDragState` lose `Core` likewise | gone | 0.19 | BV-VIEW-07 |
| `button_bundle` | the feathers `FeathersButton` with `FeathersButtonProps`, used from `bsn!`; each `*_bundle` spawn function likewise | gone | 0.20 | BV-VIEW-07 |
| `FeathersPlugin` | `FeathersCorePlugin` | gone | 0.19 | BV-VIEW-07 |
| `EditableTextInputPlugin` | `TextInputPlugin` | gone | 0.20 | BV-VIEW-08 |
| `TextScroll` | `EditableText::viewport` (`TextViewport`) | gone | 0.20 | BV-VIEW-08 |
| `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) | gone | 0.20 | BV-VIEW-08 |
| `Pointer<Click>` | `PointerClick`, its fields one level up and no `.event`; every `Pointer<X>` is `PointerX`, and a generic `On<Pointer<E>>` is `On<E>` with `E: PointerEvent` | gone | 0.20 | BV-MIG-02 |
| `pointer_location` | `ev.pointer.position` (`Vec2`), or `ev.pointer.location()` for the `Location`; `ev.pointer_id` is `ev.pointer.id` | gone | 0.20 | BV-MIG-02 |
| `Parent` | `ChildOf`, read with `child_of.parent()` | gone | 0.16 | BV-ECS-11 |
| `set_parent` | `insert(ChildOf(p))`; `set_parent_in_place`, which keeps the child's `GlobalTransform`, is live | gone | 0.17 | BV-ECS-11 |
| `push_children` | `add_children` | gone | 0.15 | BV-ECS-11 |
| `remove_children` | `detach_children` | gone | 0.20 | BV-ECS-11 |
| `remove_child` | `detach_child` | gone | 0.20 | BV-ECS-11 |
| `clear_children` | `detach_all_children` | gone | 0.20 | BV-ECS-11 |
| `clear_related` | `detach_all_related::<R>()` | gone | 0.18 | BV-ECS-11 |
| `despawn_recursive` | `despawn()`, which is recursive | gone | 0.17 | BV-ECS-11 |
| `despawn_descendants` | `despawn_related::<Children>()` | gone | 0.16 | BV-ECS-11 |
| `ChildBuilder` | `ChildSpawnerCommands`, whose `target_entity()` was `parent_entity()` | gone | 0.16 | BV-ECS-11 |
| `parent_entity` | `target_entity()` | gone | 0.16 | BV-ECS-11 |
| `HierarchyQueryExt` | `Query::related()` for `parent()`, `Query::relationship_sources()` for `children()` | gone | 0.16 | BV-ECS-11 |
| `get_single_mut` | `Query::single_mut()`, which returns `Result` | gone | 0.17 | BV-ERR-01 |
| `to_readonly` | `Query::as_readonly()` | gone | 0.17 | BV-ECS-15 |
| `DefaultErrorHandler` | `FallbackErrorHandler` | gone | 0.20 | BV-ERR-05 |
| `init_non_send_resource` | `App::init_non_send` | gone | 0.20 | BV-ERR-07 |
| `non_send_resource` | `World::non_send` | gone | 0.20 | BV-ERR-07 |
| `non_send_resource_mut` | `World::non_send_mut` | gone | 0.20 | BV-ERR-07 |
| `ExclusiveSystemParam` | `&mut World` as a `SystemParam`; `ExclusiveFunctionSystem` and `ExclusiveMarker` went with it | gone | 0.20 | BV-ECS-29 |
| `EventReader` | `MessageReader<M>` | gone | 0.18 | BV-EVENT-05 |
| `EventWriter` | `MessageWriter<M>`, whose `send`, `send_batch` and `send_default` are `write`, `write_batch` and `write_default` | gone | 0.18 | BV-EVENT-01 |
| `Events` | `Messages<M>` | gone | 0.18 | BV-EVENT-04 |
| `ManualEventReader` | `MessageCursor` | gone | 0.16 | BV-EVENT-05 |
| `send_event` | `write_message`, on `World` and on `Commands` | gone | 0.18 | BV-EVENT-01 |
| `trigger_targets` | an `EntityEvent` carrying its target as a field: `commands.trigger(E { entity })` | gone | 0.18 | BV-EVENT-08 |
| `event_target_mut` | `SetEntityEventTarget`, which game code does not need | gone | 0.18 | BV-EVENT-11 |
| `OnAdd` | `Add` | gone | 0.18 | BV-EVENT-13 |
| `OnInsert` | `Insert` | gone | 0.18 | BV-EVENT-13 |
| `OnReplace` | `Discard`, not `Replace` | gone | 0.18 | BV-EVENT-13 |
| `OnRemove` | `Remove` | gone | 0.18 | BV-EVENT-13 |
| `OnDespawn` | `Despawn` | gone | 0.18 | BV-EVENT-13 |
| `Replace` | `Discard` | gone | 0.19 | BV-EVENT-13 |
| `on_replace` | `on_discard` | gone | 0.19 | BV-EVENT-13 |
| `TransformSystem` | `TransformSystems` | gone | 0.18 | BV-ARCH-10 |
| `UiSystem` | `UiSystems` | gone | 0.18 | BV-ARCH-10 |
| `PickSet` | `PickingSystems` | gone | 0.18 | BV-ARCH-10 |
| `InputSystem` | `InputSystems` | gone | 0.18 | BV-ARCH-10 |
| `InputFocusSet` | `InputFocusSystems` | gone | 0.18 | BV-ARCH-10 |
| `TimeSystem` | `TimeSystems` | gone | 0.18 | BV-ARCH-10 |
| `AccessibilitySystem` | `AccessibilitySystems` | gone | 0.18 | BV-ARCH-10 |
| `RemoteSet` | `RemoteSystems` | gone | 0.18 | BV-ARCH-10 |
| `StateTransitionSteps` | `StateTransitionSystems` | gone | 0.18 | BV-ARCH-10 |
| `bevy::animation::Animation` | `AnimationSystems` | gone | 0.18 | BV-ARCH-10 |
| `AssetEvents` | `AssetEventSystems` | gone | 0.18 | BV-ARCH-10 |
| `TrackAssets` | `AssetTrackingSystems` | gone | 0.18 | BV-ARCH-10 |
| `EventUpdates` | `MessageUpdateSystems` | gone | 0.18 | BV-ARCH-10 |
| `CameraUpdateSystem` | `CameraUpdateSystems` | gone | 0.18 | BV-ARCH-10 |
| `RunFixedMainLoopSystem` | `RunFixedMainLoopSystems` | gone | 0.18 | BV-ARCH-10 |
| `SpriteSystem` | nothing: `SpriteSystems`, its 0.17 name, is gone from `bevy::sprite` and `bevy::sprite_render` too | gone | 0.18 | BV-ARCH-10 |
| `ExecutorKind` | `Schedule::set_executor(SingleThreadedExecutor::new())` and the other executors | gone | 0.19 | BV-SCHED-22 |
| `set_executor_kind` | `set_executor` | gone | 0.19 | BV-SCHED-22 |
| `SimpleExecutor` | `SingleThreadedExecutor` | gone | 0.18 | BV-SCHED-22 |
| `StateScoped` | `DespawnOnExit` | gone | 0.18 | BV-STATE-15 |
| `PendingIfNeq` | `PendingIfDifferent` | gone | 0.20 | BV-STATE-17 |
| `set_state_if_neq` | `set_state_if_different` | gone | 0.20 | BV-STATE-17 |
| `set_next_state_if_neq` | `set_next_state_if_different` | gone | 0.20 | BV-STATE-17 |
| `Timer::finished` | `Timer::is_finished()`; `paused()` is `is_paused()` likewise | gone | 0.18 | BV-MIG-02 |
| `compute_matrix` | `to_matrix`, on `Transform` and `GlobalTransform` | gone | 0.17 | BV-MIG-02 |
| `Handle::weak_from_u128` | the `uuid_handle!("…")` macro; `Handle` has only `Strong` and `Uuid` | gone | 0.17 | BV-ASSET-03 |
| `load_with_settings` | `load_builder().with_settings(…).load(path)` | gone | 0.20 | BV-ASSET-07 |
| `load_override` | `load_builder().override_unapproved()` | gone | 0.20 | BV-ASSET-07 |
| `load_acquire` | `load_builder().with_guard(…)` | gone | 0.20 | BV-ASSET-07 |
| `SceneRoot` | `WorldAssetRoot` | gone | 0.19 | BV-MIG-02 |
| `DynamicScene` | `DynamicWorld`; `from_scene` is `from_world_asset`, and needs a `&TypeRegistry` | gone | 0.19 | BV-MIG-02 |
| `DynamicSceneBuilder` | `DynamicWorldBuilder`, which needs a `&TypeRegistry` | gone | 0.19 | BV-MIG-02 |
| `DynamicSceneRoot` | `DynamicWorldRoot` | gone | 0.19 | BV-MIG-02 |
| `SceneInstanceReady` | `WorldInstanceReady` | gone | 0.19 | BV-MIG-02 |
| `SceneSpawner` | `WorldInstanceSpawner` | gone | 0.19 | BV-MIG-02 |
| `SceneLoader` | `WorldAssetLoader` | gone | 0.19 | BV-MIG-02 |
| `SceneFilter` | `WorldFilter` | gone | 0.19 | BV-MIG-02 |
| `bevy::a11y::Focus` | `bevy::input_focus::InputFocus` | gone | 0.16 | BV-MIG-02 |
| `AnimationTarget` | the separate components that replaced it | gone | 0.18 | BV-MIG-02 |
| `Atmosphere::earthlike` | `Atmosphere::earth` | gone | 0.19 | BV-MIG-02 |
| `Font::try_from_bytes` | `Font::from_bytes`, which returns the `Font` | gone | 0.19 | BV-MIG-02 |
| `bevy_math::curve` | `bevy_curve`, or `bevy::curve` | gone | 0.20 | BV-ARCH-06 |
| `bevy_math::cubic_splines` | `bevy_curve`, or `bevy::curve` | gone | 0.20 | BV-ARCH-06 |
| `bevy_math::primitives` | `bevy_shape`, or `bevy::shape`; `bevy::prelude` names them as it did | gone | 0.20 | BV-ARCH-06 |
| `#import` | a `.wesl` with `import …;` | gone | 0.20 | BV-VIEW-18 |
| `#ifdef` | `@if(…)` in a `.wesl` | gone | 0.20 | BV-VIEW-18 |
| `#define_import_path` | the `.wesl` module's own path | gone | 0.20 | BV-VIEW-18 |
| `#{MATERIAL_BIND_GROUP}` | `constants::MATERIAL_BIND_GROUP` | gone | 0.20 | BV-VIEW-18 |
| `"shader_format_glsl"` | nothing: GLSL is gone | gone | 0.20 | BV-VIEW-18 |
| `"shader_format_wesl"` | nothing: WESL is the only shader language | gone | 0.20 | BV-VIEW-18 |
| `"animation"` | `"gltf_animation"` | gone | 0.18 | BV-BUILD-03 |
| `"bevy_sprite_picking_backend"` | `"sprite_picking"` | gone | 0.18 | BV-BUILD-03 |
| `"bevy_ui_picking_backend"` | `"ui_picking"` | gone | 0.18 | BV-BUILD-03 |
| `"bevy_mesh_picking_backend"` | `"mesh_picking"` | gone | 0.18 | BV-BUILD-03 |
| `"experimental_bevy_feathers"` | `"bevy_feathers"` | gone | 0.19 | BV-BUILD-03 |
| `"experimental_bevy_ui_widgets"` | `"bevy_ui_widgets"` | gone | 0.19 | BV-BUILD-03 |
| `"bevy_math/curve"` | `"bevy/bevy_curve"` | gone | 0.20 | BV-BUILD-03 |
| `Trigger<…>` | `On<E>`, read by the event's own name; `Trigger` is now a trait | gone | 0.18 | BV-EVENT-13 |
| `On<Add, …>` | `On<Add<T>>`, and so for `Insert`, `Discard`, `Remove` and `Despawn`; a custom `On<E, B>` is a `PhantomData` wrapper implementing `EventPattern` | gone | 0.20 | BV-EVENT-13 |
| `On<Add>` | `On<Add<()>>`, for an observer of dynamic components (`.with_component(id)`) | gone | 0.20 | BV-EVENT-13 |
| `App::add_event` | `.add_message::<M>()`; `AnimationClip::add_event` is live | gone | 0.18 | BV-EVENT-04 |
| `on_event::<…>()` | `on_message::<M>()`, or a `PopulatedMessageReader` | gone | 0.18 | BV-EVENT-05 |
| `App::observe` | `App::add_observer`, as `Commands::observe` is `Commands::add_observer`; `EntityCommands::observe` is live | gone | 0.15 | BV-EVENT-15 |
| `NextState::set_if_neq` | `set_if_different`; `Mut::set_if_neq` is live | gone | 0.20 | BV-STATE-17 |
| `Query::get_single` | `Query::single()`, which returns `Result`; `Gradient::get_single` is live | gone | 0.17 | BV-ERR-01 |
| `impl Command<Result>` | `impl Command { type Out = Result; }`; `-> impl Command` with a closure returning `Result` | gone | 0.19 | BV-ERR-01 |
| `Handle<AnimationGraph>` | `AnimationGraphHandle(handle)` as the component; a `Handle` is no component | gone | 0.15 | BV-ECS-13 |
| `Text { sections: … }` | a `Text` root with `TextSpan` children | gone | 0.15 | BV-VIEW-05 |
| `TextFont { line_height: … }` | the `LineHeight` component | gone | 0.18 | BV-VIEW-04 |
| `TextFont { font: handle, … }` | `TextFont { font: FontSource::Handle(handle), .. }` | gone | 0.19 | BV-VIEW-04 |
| `TextFont { font_size: f32, … }` | `TextFont { font_size: FontSize::Px(…), .. }` | gone | 0.19 | BV-VIEW-04 |
| `Camera { hdr: … }` | the separate `Hdr` component | gone | 0.17 | BV-VIEW-12 |
| `Camera { target: … }` | `RenderTarget` as its own component | gone | 0.18 | BV-VIEW-14 |
| `bevy_pbr::mesh_view_bindings` | `bevy_pbr::render::mesh_view_bindings` | gone | 0.20 | BV-VIEW-18 |
| `Condition` | `SystemCondition` | gone | 0.17 | BV-SCHED-17 |
| `Window { cursor_options: … }` | the separate `CursorOptions` component, which `Window` requires | gone | 0.17 | BV-MIG-02 |
| `Sprite { anchor: … }` | the separate `Anchor` component, which `Sprite` requires: a `Vec2` newtype, `Anchor::CENTER` for `Anchor::Center` and `Anchor(v)` for `Anchor::Custom(v)` | gone | 0.17 | BV-MIG-02 |
| `Skybox { image: handle, … }` | `Skybox { image: Some(handle), .. }`: the field is an `Option<Handle<Image>>` | gone | 0.19 | BV-MIG-02 |
| `BorderRadius { top_left: Val::Px(…), … }` | `CornerRadius` fields, such as `px(10.).into()` | gone | 0.20 | BV-MIG-02 |
| `MeshTag(…)` | `MeshTag::new(x)`, read as `tag.value` | gone | 0.20 | BV-MIG-02 |
| `#[derive(Event)]` | `#[derive(Message)]` for a buffered event; `Event` is an observed one | changed | 0.17 | BV-EVENT-01 |
| `NextState::set` | runs `OnExit(S)` and `OnEnter(S)` when the state is already `S`; `set_if_different` is the old meaning | changed | 0.18 | BV-STATE-17 |
| `App::set_error_handler` | receives every panic in a system, observer or command as an error carrying its payload | changed | 0.20 | BV-ERR-05 |
| `Query::iter_many` | yields `Result` per id, so `.count()` and `for _ in` take ids the query does not match; `.matched()` is the old meaning | changed | 0.20 | BV-ECS-20 |
| `Query<Entity>` | matches each resource's entity too, as `Query<EntityRef>` and `Query<EntityMut>` do | changed | 0.19 | BV-STATE-02 |
| `Ref::clone` | another `Ref<T>`, where it produced a `T`; `r.deref().clone()` is the old meaning | changed | 0.19 | BV-MIG-03 |
| `Node` | the layout input, what was `Style`; the laid-out size is `ComputedNode`'s | changed | 0.15 | BV-VIEW-03 |
| `TextSection` | a live trait; the old struct is a `TextSpan` on a child entity | changed | 0.15 | BV-VIEW-05 |
| `TextFont::default` | sizes text at `FontSize::Rem(1.)`, not `Px(20.)`; `TextFont::from_font_size(FontSize::Px(…))` keeps a fixed size | changed | 0.20 | BV-VIEW-04 |
| `EditableText` | spawned alone, inert; spawn `TextInput`, which requires it | changed | 0.20 | BV-VIEW-08 |
| `Camera2d` | brings `Tonemapping::Linear`, and with `Hdr` runs the tonemapping pass | changed | 0.20 | BV-VIEW-12 |
| `Camera3d` | no longer requires `ScreenSpaceTransmission`; a camera drawing transmissive materials adds it | changed | 0.20 | BV-VIEW-12 |
| `Bloom` | judges luminance in linear, so a tint tuned against sRGB blooms more | changed | 0.19 | BV-VIEW-11 |
| `Aabb` | added and kept up to date by Bevy whenever its mesh or sprite changes, so a system that writes or removes one fights the engine; `NoAutoAabb` opts out | changed | 0.18 | BV-VIEW-16 |
| `Tonemapping::None` | a full passthrough: no `ColorGrading`, no `DebandDither`, no clamping; `Tonemapping::Linear` is no curve | changed | 0.20 | BV-VIEW-20 |
| `SpriteMaterial` | a new public type, unrelated to the internal one of the same name, which is `SpriteMeshMaterial` | changed | 0.20 | BV-VIEW-17 |
| `AssetEvent::Modified` | raised only by an actual mutation, so a `get_mut` that only reads raises none | changed | 0.19 | BV-ASSET-09 |
| `UiSystems` | ordered weakly, as the render schedules' sets are: systems the ECS sees no conflict between are unordered | changed | 0.20 | BV-SCHED-14 |
| `bevy_scene` | the `bsn!` scene system; the old scene crate is `bevy_world_serialization` | changed | 0.19 | BV-MIG-02 |
| `Scene` | a trait of the `bsn!` system; the asset is `WorldAsset` | changed | 0.19 | BV-MIG-02 |
| `ScenePlugin` | the `bsn!` system's plugin; the old one is `WorldSerializationPlugin` | changed | 0.19 | BV-MIG-02 |
| `AmbientLight` | a camera component; the resource is `GlobalAmbientLight` | changed | 0.18 | BV-MIG-02 |
| `Atmosphere` | a component of its own entity, not of the camera | changed | 0.19 | BV-MIG-02 |
| `"compressed_image_saver"` | a BCn/ASTC backend; the Basis one is `"compressed_image_saver_universal"` | changed | 0.20 | BV-BUILD-03 |
| `Interaction` | deprecated, with the prelude `Button`; `Hovered` plus `Pressed`, and `On<Activate>` | deprecated | 0.20 | BV-VIEW-06 |
| `bevy::ui::widget::Button` | `bevy::ui_widgets::Button` | deprecated | 0.20 | BV-VIEW-06 |
| `weak_handle!` | the `uuid_handle!("…")` macro | deprecated | 0.17 | BV-ASSET-03 |
| `AssetId::invalid` | `Option<AssetId<_>>`; `AssetId::INVALID_UUID` likewise | deprecated | 0.20 | BV-MIG-02 |
| `template_value` | the value itself, in `bsn!` | deprecated | 0.20 | BV-VIEW-09 |

```sh
rg -n -F -w \
  -e 'SpriteBundle' \
  -e 'SpriteSheetBundle' \
  -e 'PbrBundle' \
  -e 'MaterialMesh2dBundle' \
  -e 'ImageBundle' \
  -e 'PointLightBundle' \
  -e 'DirectionalLightBundle' \
  -e 'SpatialBundle' \
  -e 'TransformBundle' \
  -e 'VisibilityBundle' \
  -e 'AudioBundle' \
  -e 'NodeBundle' \
  -e 'ButtonBundle' \
  -e 'Camera2dBundle' \
  -e 'Camera3dBundle' \
  -e 'TextBundle' \
  -e 'Text2dBundle' \
  -e 'TextStyle' \
  -e 'Text::from_section' \
  -e 'JustifyText' \
  -e 'BreakLineOn' \
  -e 'TextLayout::new_with_justify' \
  -e 'TextLayout::new_with_linebreak' \
  -e 'TextLayout::new_with_no_wrap' \
  -e 'resolve_font_source' \
  -e 'FontSource::SansSerif' \
  -e 'Style' \
  -e 'UiImage' \
  -e 'UiImageSize' \
  -e 'ComputedNode::stack_index' \
  -e 'ComputedNodeTarget' \
  -e 'CoreScrollbarThumb' \
  -e 'button_bundle' \
  -e 'FeathersPlugin' \
  -e 'EditableTextInputPlugin' \
  -e 'TextScroll' \
  -e 'scroll_editable_text' \
  -e 'Pointer<Click>' \
  -e 'pointer_location' \
  -e 'Parent' \
  -e 'set_parent' \
  -e 'push_children' \
  -e 'remove_children' \
  -e 'remove_child' \
  -e 'clear_children' \
  -e 'clear_related' \
  -e 'despawn_recursive' \
  -e 'despawn_descendants' \
  -e 'ChildBuilder' \
  -e 'parent_entity' \
  -e 'HierarchyQueryExt' \
  -e 'get_single_mut' \
  -e 'to_readonly' \
  -e 'DefaultErrorHandler' \
  -e 'init_non_send_resource' \
  -e 'non_send_resource' \
  -e 'non_send_resource_mut' \
  -e 'ExclusiveSystemParam' \
  -e 'EventReader' \
  -e 'EventWriter' \
  -e 'Events' \
  -e 'ManualEventReader' \
  -e 'send_event' \
  -e 'trigger_targets' \
  -e 'event_target_mut' \
  -e 'OnAdd' \
  -e 'OnInsert' \
  -e 'OnReplace' \
  -e 'OnRemove' \
  -e 'OnDespawn' \
  -e 'Replace' \
  -e 'on_replace' \
  -e 'TransformSystem' \
  -e 'UiSystem' \
  -e 'PickSet' \
  -e 'InputSystem' \
  -e 'InputFocusSet' \
  -e 'TimeSystem' \
  -e 'AccessibilitySystem' \
  -e 'RemoteSet' \
  -e 'StateTransitionSteps' \
  -e 'bevy::animation::Animation' \
  -e 'AssetEvents' \
  -e 'TrackAssets' \
  -e 'EventUpdates' \
  -e 'CameraUpdateSystem' \
  -e 'RunFixedMainLoopSystem' \
  -e 'SpriteSystem' \
  -e 'ExecutorKind' \
  -e 'set_executor_kind' \
  -e 'SimpleExecutor' \
  -e 'StateScoped' \
  -e 'PendingIfNeq' \
  -e 'set_state_if_neq' \
  -e 'set_next_state_if_neq' \
  -e 'Timer::finished' \
  -e 'compute_matrix' \
  -e 'Handle::weak_from_u128' \
  -e 'load_with_settings' \
  -e 'load_override' \
  -e 'load_acquire' \
  -e 'SceneRoot' \
  -e 'DynamicScene' \
  -e 'DynamicSceneBuilder' \
  -e 'DynamicSceneRoot' \
  -e 'SceneInstanceReady' \
  -e 'SceneSpawner' \
  -e 'SceneLoader' \
  -e 'SceneFilter' \
  -e 'bevy::a11y::Focus' \
  -e 'AnimationTarget' \
  -e 'Atmosphere::earthlike' \
  -e 'Font::try_from_bytes' \
  -e 'bevy_math::curve' \
  -e 'bevy_math::cubic_splines' \
  -e 'bevy_math::primitives' \
  -e '#import' \
  -e '#ifdef' \
  -e '#define_import_path' \
  -e '#{MATERIAL_BIND_GROUP}' \
  -e '"shader_format_glsl"' \
  -e '"shader_format_wesl"' \
  -e '"animation"' \
  -e '"bevy_sprite_picking_backend"' \
  -e '"bevy_ui_picking_backend"' \
  -e '"bevy_mesh_picking_backend"' \
  -e '"experimental_bevy_feathers"' \
  -e '"experimental_bevy_ui_widgets"' \
  -e '"bevy_math/curve"' \
  -e 'On<Add>' \
  -e 'App::add_event' \
  -e 'App::observe' \
  -e 'NextState::set_if_neq' \
  -e 'Query::get_single' \
  -e 'impl Command<Result>' \
  -e 'Handle<AnimationGraph>' \
  -e 'bevy_pbr::mesh_view_bindings' \
  -e 'Condition' \
  .
```

## Reading the table

### BV-MIG-01 [M] Check unfamiliar Bevy code against this chapter before adapting it

Code from a tutorial, a blog post, an answer or a language model was written against an older Bevy
until something proves otherwise — often 0.15, and at best 0.19. Run the command after the table
over it before adapting it, then read it for the `changed` rows, the shapes and the removed methods
it calls on a value (`timer.finished()`), which no fixed string finds.

**Why:** 0.17 renamed the event system, the observer parameter and every system set; 0.20 moved the
observer's bundle and flattened the pointer events. Nearly all Bevy material online predates one or
both, and adapting a pattern that no longer exists costs time and keeps the old names in mind.

**Check:** a hit of the command after the table dates the sample, and so does a hit of the Check of
a rule that owns a `changed` row or a shape, or the compiler rejecting a `gone` row's method; a
sample with none of them is read against those rows by hand.

### BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop

Write each old spelling as its row's 0.20 column says, not as the release that first renamed it did.
A row with no topical rule is this rule's.

**Why:** some APIs move twice: `Pointer<Pressed>` became `Pointer<Press>` in 0.17 and `PointerPress`
in 0.20. Applying one release's guide and stopping leaves a name that was already renamed again.

**Check:** look each new name a guide gives up in the pinned release's source, as the toolchain
looks up each `gone` row's; a name that is not there means the chain continued.
`rg -n '\bMeshTag\(|\bAnchor::[A-Z][a-z]|\bcursor_options:' src/` finds three of this rule's shapes
written the old way.

### BV-MIG-03 [M] Re-read every `Ref` that is cloned

Since 0.19 `Ref<T>` implements `Clone` and `Copy` itself. `value.clone()` on a `Ref<T>` now produces
a `Ref<T>`, where it used to produce a `T`.

**Why:** `let owned = r.clone()` infers the new type and carries on, failing only where the
surrounding code was explicit. Downstream code then holds a borrow where it expected a value, which
surfaces much later as a lifetime error in an unrelated function.

**Check:** read each `.clone()` whose receiver is a `Ref<T>`, a type the line does not show; the old
meaning is `r.deref().clone()` or `r.as_ref().clone()`.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| rustc | `deprecated` | warn | a deprecated Bevy API — listed because the shipped CI denies warnings, so a deprecated row fails its build (RS-MIG-02) |
