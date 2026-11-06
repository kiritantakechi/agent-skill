# Migration: Old Spellings Since 0.15, and What Replaced Them

Scope: every spelling a game writes that Bevy 0.15 through 0.20 removed, renamed, changed or
deprecated, keyed by the old spelling, with the rule that owns it. What changed under existing code
with no spelling to key it is section 2.1's, each item citing its owner. Why a spelling is wrong is
its owning rule's to say; this chapter is the table and the command it generates. The engine's
rendering internals, render graph, pipeline specialisation and reflection internals changed as much
and are not in it: no rule of this standard reaches them, and the upstream migration guides are
their reference.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- Old spellings
- **Reading the table**
  - BV-MIG-01 [M] Check unfamiliar Bevy code against this chapter before adapting it
  - BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop
  - BV-MIG-03 [M] Do not call an API 0.20 deprecated
  - BV-MIG-04 [M] Re-read every `Ref` that is cloned
- Decided by tools

---

## Old spellings

A row's status says what its old spelling does under Bevy 0.20 with the shipped configuration:
`gone` — 0.20 has no such item, so the build fails where it stands; `changed` — it compiles and
means something else, or 0.20 rejects it in a shape no fixed string finds, so its owning rule's
Check finds it; `deprecated` — it builds with a warning, which the shipped CI's
`CARGO_BUILD_WARNINGS: deny` makes a failed build. No row is an `alias`: Bevy keeps no old name
working beside its new one. A row may stand for a family its 0.20 column names. The command after
the table finds every `gone` row.

| Old | Bevy 0.20 | Status | Rule |
|---|---|---|---|
| `SpriteBundle` | `Sprite::from_image(handle)` plus `Transform` | gone | BV-ECS-06 |
| `SpriteSheetBundle` | `Sprite::from_atlas_image(handle, atlas)` | gone | BV-ECS-06 |
| `PbrBundle` | `Mesh3d(mesh)` plus `MeshMaterial3d(material)` | gone | BV-ECS-06 |
| `MaterialMesh2dBundle` | `Mesh2d(mesh)` plus `MeshMaterial2d(material)` | gone | BV-ECS-06 |
| `ImageBundle` | `ImageNode::new(handle)` | gone | BV-ECS-06 |
| `PointLightBundle` | `PointLight::default()` plus `Transform` | gone | BV-ECS-06 |
| `DirectionalLightBundle` | `DirectionalLight::default()` plus `Transform` | gone | BV-ECS-06 |
| `SpatialBundle` | `Transform`; `Visibility` and the rest are required components | gone | BV-ECS-06 |
| `TransformBundle` | `Transform` | gone | BV-ECS-06 |
| `VisibilityBundle` | `Visibility` | gone | BV-ECS-06 |
| `AudioBundle` | `AudioPlayer(handle)` | gone | BV-ECS-06 |
| `NodeBundle` | `Node::default()` | gone | BV-VIEW-01 |
| `ButtonBundle` | `bevy::ui_widgets::Button` plus `Node` | gone | BV-VIEW-06 |
| `Camera2dBundle` | `Camera2d` | gone | BV-VIEW-12 |
| `Camera3dBundle` | `Camera3d::default()` | gone | BV-VIEW-12 |
| `TextBundle` | `Text::new(s)` plus `TextFont` and `TextColor` | gone | BV-VIEW-04 |
| `Text2dBundle` | `Text2d::new(s)` plus `TextFont` and `TextColor` | gone | BV-VIEW-04 |
| `TextStyle` | `TextFont { font, font_size, .. }` plus `TextColor(color)` | gone | BV-VIEW-04 |
| `Text::from_section` | `Text::new(s)`, with `TextFont` and `TextColor` beside it | gone | BV-VIEW-04 |
| `JustifyText` | `Justify` | gone | BV-VIEW-04 |
| `BreakLineOn` | `LineBreak` | gone | BV-VIEW-04 |
| `TextLayout::new_with_justify` | `TextLayout::justify(j)` | gone | BV-VIEW-04 |
| `TextLayout::new_with_linebreak` | `TextLayout::linebreak(b)` | gone | BV-VIEW-04 |
| `TextLayout::new_with_no_wrap` | `TextLayout::no_wrap()` | gone | BV-VIEW-04 |
| `resolve_font_source` | `font.font.resolve_font_family(fonts)` | gone | BV-VIEW-04 |
| `FontSource::SansSerif` | `FontSource::sans_serif()`, or `FontSource::Generic` with a `GenericFontFamily`; every generic family variant likewise | gone | BV-VIEW-04 |
| `Style` | `Node` | gone | BV-VIEW-01 |
| `UiImage` | `ImageNode`, which carries its own colour | gone | BV-VIEW-01 |
| `UiImageSize` | `ImageNodeSize` | gone | BV-VIEW-01 |
| `ComputedNode::stack_index` | `ComputedStackIndex` | gone | BV-VIEW-03 |
| `ComputedNodeTarget` | `ComputedUiTargetCamera` | gone | BV-VIEW-03 |
| `CoreButton` | `bevy::ui_widgets::Button`; every `Core*` widget component is its name without `Core` | gone | BV-VIEW-07 |
| `button_bundle` | the feathers `FeathersButton` with `FeathersButtonProps`, used from `bsn!`; each `*_bundle` spawn function likewise | gone | BV-VIEW-07 |
| `FeathersPlugin` | `FeathersCorePlugin` | gone | BV-VIEW-07 |
| `EditableTextInputPlugin` | `TextInputPlugin` | gone | BV-VIEW-08 |
| `TextScroll` | `EditableText::viewport` (`TextViewport`) | gone | BV-VIEW-08 |
| `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) | gone | BV-VIEW-08 |
| `Pointer<Click>` | `PointerClick`, its fields one level up and no `.event`; every `Pointer<X>` is `PointerX`, and a generic `On<Pointer<E>>` is `On<E>` with `E: PointerEvent` | gone | BV-MIG-02 |
| `pointer_location` | `ev.pointer.position` (`Vec2`), or `ev.pointer.location()` for the `Location`; `ev.pointer_id` is `ev.pointer.id` | gone | BV-MIG-02 |
| `Parent` | `ChildOf`, read with `child_of.parent()` | gone | BV-ECS-11 |
| `set_parent` | `insert(ChildOf(p))`; `set_parent_in_place`, which keeps the child's `GlobalTransform`, is live | gone | BV-ECS-11 |
| `push_children` | `add_children` | gone | BV-ECS-11 |
| `remove_children` | `detach_children` | gone | BV-ECS-11 |
| `remove_child` | `detach_child` | gone | BV-ECS-11 |
| `clear_children` | `detach_all_children` | gone | BV-ECS-11 |
| `clear_related` | `detach_all_related::<R>()` | gone | BV-ECS-11 |
| `despawn_recursive` | `despawn()`, which is recursive | gone | BV-ECS-11 |
| `despawn_descendants` | `despawn_related::<Children>()` | gone | BV-ECS-11 |
| `ChildBuilder` | `ChildSpawnerCommands`, whose `target_entity()` was `parent_entity()` | gone | BV-ECS-11 |
| `parent_entity` | `target_entity()` | gone | BV-ECS-11 |
| `HierarchyQueryExt` | `Query::related()` for `parent()`, `Query::relationship_sources()` for `children()` | gone | BV-ECS-11 |
| `get_single_mut` | `Query::single_mut()`, which returns `Result` | gone | BV-ERR-01 |
| `to_readonly` | `Query::as_readonly()` | gone | BV-ECS-15 |
| `DefaultErrorHandler` | `FallbackErrorHandler` | gone | BV-ERR-05 |
| `init_non_send_resource` | `App::init_non_send` | gone | BV-ERR-07 |
| `non_send_resource` | `World::non_send` | gone | BV-ERR-07 |
| `non_send_resource_mut` | `World::non_send_mut` | gone | BV-ERR-07 |
| `ExclusiveSystemParam` | `&mut World` as a `SystemParam`; `ExclusiveFunctionSystem` and `ExclusiveMarker` went with it | gone | BV-ECS-29 |
| `EventReader` | `MessageReader<M>` | gone | BV-EVENT-05 |
| `EventWriter` | `MessageWriter<M>`, whose `send`, `send_batch` and `send_default` are `write`, `write_batch` and `write_default` | gone | BV-EVENT-01 |
| `Events` | `Messages<M>` | gone | BV-EVENT-04 |
| `ManualEventReader` | `MessageCursor` | gone | BV-EVENT-05 |
| `send_event` | `write_message`, on `World` and on `Commands` | gone | BV-EVENT-01 |
| `trigger_targets` | an `EntityEvent` carrying its target as a field: `commands.trigger(E { entity })` | gone | BV-EVENT-08 |
| `event_target_mut` | `SetEntityEventTarget`, which game code does not need | gone | BV-EVENT-11 |
| `OnAdd` | `Add` | gone | BV-EVENT-13 |
| `OnInsert` | `Insert` | gone | BV-EVENT-13 |
| `OnReplace` | `Discard`, not `Replace` | gone | BV-EVENT-13 |
| `OnRemove` | `Remove` | gone | BV-EVENT-13 |
| `OnDespawn` | `Despawn` | gone | BV-EVENT-13 |
| `Replace` | `Discard` | gone | BV-EVENT-13 |
| `on_replace` | `on_discard` | gone | BV-EVENT-13 |
| `TransformSystem` | `TransformSystems` | gone | BV-ARCH-10 |
| `UiSystem` | `UiSystems` | gone | BV-ARCH-10 |
| `PickSet` | `PickingSystems` | gone | BV-ARCH-10 |
| `InputSystem` | `InputSystems` | gone | BV-ARCH-10 |
| `InputFocusSet` | `InputFocusSystems` | gone | BV-ARCH-10 |
| `TimeSystem` | `TimeSystems` | gone | BV-ARCH-10 |
| `AccessibilitySystem` | `AccessibilitySystems` | gone | BV-ARCH-10 |
| `RemoteSet` | `RemoteSystems` | gone | BV-ARCH-10 |
| `StateTransitionSteps` | `StateTransitionSystems` | gone | BV-ARCH-10 |
| `bevy::animation::Animation` | `AnimationSystems` | gone | BV-ARCH-10 |
| `AssetEvents` | `AssetEventSystems` | gone | BV-ARCH-10 |
| `TrackAssets` | `AssetTrackingSystems` | gone | BV-ARCH-10 |
| `EventUpdates` | `MessageUpdateSystems` | gone | BV-ARCH-10 |
| `CameraUpdateSystem` | `CameraUpdateSystems` | gone | BV-ARCH-10 |
| `RunFixedMainLoopSystem` | `RunFixedMainLoopSystems` | gone | BV-ARCH-10 |
| `SpriteSystem` | nothing: `SpriteSystems`, its 0.17 name, is gone from `bevy::sprite` and `bevy::sprite_render` too | gone | BV-ARCH-10 |
| `ExecutorKind` | `Schedule::set_executor(SingleThreadedExecutor::new())` and the other executors | gone | BV-SCHED-22 |
| `set_executor_kind` | `set_executor` | gone | BV-SCHED-22 |
| `SimpleExecutor` | `SingleThreadedExecutor` | gone | BV-SCHED-22 |
| `StateScoped` | `DespawnOnExit` | gone | BV-STATE-15 |
| `PendingIfNeq` | `PendingIfDifferent` | gone | BV-STATE-17 |
| `set_state_if_neq` | `set_state_if_different` | gone | BV-STATE-17 |
| `set_next_state_if_neq` | `set_next_state_if_different` | gone | BV-STATE-17 |
| `Timer::finished` | `Timer::is_finished()`; `paused()` is `is_paused()` likewise | gone | BV-MIG-02 |
| `compute_matrix` | `to_matrix`, on `Transform` and `GlobalTransform` | gone | BV-MIG-02 |
| `Handle::weak_from_u128` | the `uuid_handle!("…")` macro; `Handle` has only `Strong` and `Uuid` | gone | BV-ASSET-03 |
| `load_with_settings` | `load_builder().with_settings(…).load(path)` | gone | BV-ASSET-07 |
| `load_override` | `load_builder().override_unapproved()` | gone | BV-ASSET-07 |
| `load_acquire` | `load_builder().with_guard(…)` | gone | BV-ASSET-07 |
| `SceneRoot` | `WorldAssetRoot` | gone | BV-MIG-02 |
| `DynamicScene` | `DynamicWorld`; `from_scene` is `from_world_asset`, and needs a `&TypeRegistry` | gone | BV-MIG-02 |
| `DynamicSceneBuilder` | `DynamicWorldBuilder`, which needs a `&TypeRegistry` | gone | BV-MIG-02 |
| `DynamicSceneRoot` | `DynamicWorldRoot` | gone | BV-MIG-02 |
| `SceneInstanceReady` | `WorldInstanceReady` | gone | BV-MIG-02 |
| `SceneSpawner` | `WorldInstanceSpawner` | gone | BV-MIG-02 |
| `SceneLoader` | `WorldAssetLoader` | gone | BV-MIG-02 |
| `SceneFilter` | `WorldFilter` | gone | BV-MIG-02 |
| `bevy::a11y::Focus` | `bevy::input_focus::InputFocus` | gone | BV-MIG-02 |
| `AnimationTarget` | the separate components that replaced it | gone | BV-MIG-02 |
| `Atmosphere::earthlike` | `Atmosphere::earth` | gone | BV-MIG-02 |
| `Font::try_from_bytes` | `Font::from_bytes`, which returns the `Font` | gone | BV-MIG-02 |
| `bevy_math::curve` | `bevy_curve`, or `bevy::curve` | gone | BV-ARCH-06 |
| `bevy_math::cubic_splines` | `bevy_curve`, or `bevy::curve` | gone | BV-ARCH-06 |
| `bevy_math::primitives` | `bevy_shape`, or `bevy::shape`; `bevy::prelude` names them as it did | gone | BV-ARCH-06 |
| `#import` | a `.wesl` with `import …;` | gone | BV-VIEW-18 |
| `#ifdef` | `@if(…)` in a `.wesl` | gone | BV-VIEW-18 |
| `#define_import_path` | the `.wesl` module's own path | gone | BV-VIEW-18 |
| `#{MATERIAL_BIND_GROUP}` | `constants::MATERIAL_BIND_GROUP` | gone | BV-VIEW-18 |
| `"shader_format_glsl"` | nothing: GLSL is gone | gone | BV-VIEW-18 |
| `"shader_format_wesl"` | nothing: WESL is the only shader language | gone | BV-VIEW-18 |
| `"animation"` | `"gltf_animation"` | gone | BV-BUILD-03 |
| `"bevy_sprite_picking_backend"` | `"sprite_picking"` | gone | BV-BUILD-03 |
| `"bevy_ui_picking_backend"` | `"ui_picking"` | gone | BV-BUILD-03 |
| `"bevy_mesh_picking_backend"` | `"mesh_picking"` | gone | BV-BUILD-03 |
| `"experimental_bevy_feathers"` | `"bevy_feathers"` | gone | BV-BUILD-03 |
| `"experimental_ui_widgets"` | `"bevy_ui_widgets"` | gone | BV-BUILD-03 |
| `"bevy_math/curve"` | `"bevy/bevy_curve"` | gone | BV-BUILD-03 |
| `Trigger<E>` | `On<E>`, read by the event's own name; `Trigger` is now a trait | changed | BV-EVENT-13 |
| `On<Add, T>` | `On<Add<T>>`, and so for `Insert`, `Discard`, `Remove` and `Despawn`; a custom `On<E, B>` is a `PhantomData` wrapper implementing `EventPattern` | changed | BV-EVENT-13 |
| `On<Add>` | `On<Add<()>>`, for an observer of dynamic components (`.with_component(id)`) | changed | BV-EVENT-13 |
| `#[derive(Event)]` | `#[derive(Message)]` for a buffered event; `Event` is an observed one | changed | BV-EVENT-01 |
| `.add_event::<M>()` | `.add_message::<M>()`; `AnimationClip::add_event` is live | changed | BV-EVENT-04 |
| `on_event::<M>()` | `on_message::<M>()`, or a `PopulatedMessageReader` | changed | BV-EVENT-05 |
| `App::observe` | `App::add_observer`, as `Commands::observe` is `Commands::add_observer`; `EntityCommands::observe` is live | changed | BV-EVENT-15 |
| `NextState::set_if_neq` | `set_if_different`; `Mut::set_if_neq` is live, so the name finds both | changed | BV-STATE-17 |
| `NextState::set` | runs `OnExit(S)` and `OnEnter(S)` when the state is already `S`; `set_if_different` is the old meaning | changed | BV-STATE-17 |
| `.get_single()` | `Query::single()`, which returns `Result`; `Gradient::get_single` is live | changed | BV-ERR-01 |
| `impl Command<Result>` | `impl Command { type Out = Result; }`; `-> impl Command` with a closure returning `Result` | changed | BV-ERR-01 |
| `App::set_error_handler` | receives every panic in a system, observer or command as an error carrying its payload | changed | BV-ERR-05 |
| `Query::iter_many` | yields `Result` per id, so `.count()` and `for _ in` take ids the query does not match; `.matched()` is the old meaning | changed | BV-ECS-20 |
| `Query<Entity>` | matches each resource's entity too, as `Query<EntityRef>` and `Query<EntityMut>` do | changed | BV-STATE-02 |
| `Ref::clone` | another `Ref<T>`, where it produced a `T`; `r.deref().clone()` is the old meaning | changed | BV-MIG-04 |
| `Handle<AnimationGraph>` | `AnimationGraphHandle(handle)` as the component | changed | BV-ECS-13 |
| `Node` | the layout input, what was `Style`; the laid-out size is `ComputedNode`'s | changed | BV-VIEW-03 |
| `TextSection` | a live trait; the old struct is a `TextSpan` on a child entity | changed | BV-VIEW-05 |
| `Text { sections }` | a `Text` root with `TextSpan` children | changed | BV-VIEW-05 |
| `TextFont::default` | sizes text at `FontSize::Rem(1.)`, not `Px(20.)`; `TextFont::from_font_size(FontSize::Px(…))` keeps a fixed size | changed | BV-VIEW-04 |
| `TextFont { line_height }` | the `LineHeight` component | changed | BV-VIEW-04 |
| `TextFont { font: handle }` | `TextFont { font: FontSource::Handle(handle), .. }` | changed | BV-VIEW-04 |
| `TextFont { font_size: f32 }` | `TextFont { font_size: FontSize::Px(…), .. }` | changed | BV-VIEW-04 |
| `EditableText` | spawned alone, inert; spawn `TextInput`, which requires it | changed | BV-VIEW-08 |
| `Camera { hdr }` | the separate `Hdr` component | changed | BV-VIEW-12 |
| `Camera2d` | brings `Tonemapping::Linear`, and with `Hdr` runs the tonemapping pass | changed | BV-VIEW-12 |
| `Camera3d` | no longer requires `ScreenSpaceTransmission`; a camera drawing transmissive materials adds it | changed | BV-VIEW-12 |
| `Camera { target }` | `RenderTarget` as its own component | changed | BV-VIEW-14 |
| `Bloom` | judges luminance in linear, so a tint tuned against sRGB blooms more | changed | BV-VIEW-11 |
| `Tonemapping::None` | a full passthrough: no `ColorGrading`, no `DebandDither`, no clamping; `Tonemapping::Linear` is no curve | changed | BV-VIEW-20 |
| `SpriteMaterial` | a new public type, unrelated to the internal one of the same name, which is `SpriteMeshMaterial` | changed | BV-VIEW-17 |
| `bevy_pbr::mesh_view_bindings` | `bevy_pbr::render::mesh_view_bindings` | changed | BV-VIEW-18 |
| `AssetEvent::Modified` | raised only by an actual mutation, so a `get_mut` that only reads raises none | changed | BV-ASSET-09 |
| `UiSystems` | ordered weakly, as the render schedules' sets are: systems the ECS sees no conflict between are unordered | changed | BV-SCHED-14 |
| `Condition` | `SystemCondition`; the new name contains the old, so read each bound | changed | BV-SCHED-17 |
| `bevy_scene` | the `bsn!` scene system; the old scene crate is `bevy_world_serialization` | changed | BV-MIG-02 |
| `Scene` | a trait of the `bsn!` system; the asset is `WorldAsset` | changed | BV-MIG-02 |
| `ScenePlugin` | the `bsn!` system's plugin; the old one is `WorldSerializationPlugin` | changed | BV-MIG-02 |
| `Window { cursor_options }` | the separate `CursorOptions` component, which `Window` requires | changed | BV-MIG-02 |
| `Sprite { anchor }` | the separate `Anchor` component, which `Sprite` requires: a `Vec2` newtype, `Anchor::CENTER` for `Anchor::Center` and `Anchor(v)` for `Anchor::Custom(v)` | changed | BV-MIG-02 |
| `AmbientLight` | a camera component; the resource is `GlobalAmbientLight` | changed | BV-MIG-02 |
| `Atmosphere` | a component of its own entity, not of the camera | changed | BV-MIG-02 |
| `Skybox { image }` | `Option<Handle<Image>>` | changed | BV-MIG-02 |
| `BorderRadius { top_left }` | `CornerRadius` fields, such as `px(10.).into()` | changed | BV-MIG-02 |
| `MeshTag(x)` | `MeshTag::new(x)`, read as `tag.value` | changed | BV-MIG-02 |
| `"compressed_image_saver"` | a BCn/ASTC backend; the Basis one is `"compressed_image_saver_universal"` | changed | BV-BUILD-03 |
| `Interaction` | deprecated, with the prelude `Button`; `Hovered` plus `Pressed`, and `On<Activate>` | deprecated | BV-VIEW-06 |
| `bevy::ui::widget::Button` | `bevy::ui_widgets::Button` | deprecated | BV-VIEW-06 |
| `weak_handle!` | the `uuid_handle!("…")` macro | deprecated | BV-ASSET-03 |
| `AssetId::invalid` | `Option<AssetId<_>>`; `AssetId::INVALID_UUID` likewise | deprecated | BV-MIG-03 |
| `template_value` | the value itself, in `bsn!` | deprecated | BV-VIEW-09 |

```sh
rg -n -F \
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
  -e 'CoreButton' \
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
  -e '"experimental_ui_widgets"' \
  -e '"bevy_math/curve"' \
  .
```

## Reading the table

### BV-MIG-01 [M] Check unfamiliar Bevy code against this chapter before adapting it

Code from a tutorial, a blog post, an answer or a language model was written against an older Bevy
until something proves otherwise — often 0.15, and at best 0.19. Run the command after the table
over it before adapting it, then read it for the `changed` rows, which no fixed string finds.

**Why:** 0.17 renamed the event system, the observer parameter and every system set; 0.20 moved the
observer's bundle and flattened the pointer events. Nearly all Bevy material online predates one or
both, and adapting a pattern that no longer exists costs time and keeps the old names in mind.

**Check:** a hit of the command after the table dates the sample, and so does a hit of a `changed`
row's owning rule's Check; a sample with neither is read against the `changed` rows by hand.

### BV-MIG-02 [M] Follow a rename to its 0.20 spelling, not its first hop

Write each old spelling as its row's 0.20 column says, not as the release that first renamed it did.
A row with no topical rule is this rule's.

**Why:** some APIs move twice: `Pointer<Pressed>` became `Pointer<Press>` in 0.17 and `PointerPress`
in 0.20. Applying one release's guide and stopping leaves a name that was already renamed again.

**Check:** look each new name a guide gives up in the pinned release's source, as the toolchain
looks up each `gone` row's; a name that is not there means the chain continued.
`rg -n '\bMeshTag\(|\bAnchor::[A-Z][a-z]|\bcursor_options:' src/` finds this rule's `changed` rows
written the old way.

### BV-MIG-03 [M] Do not call an API 0.20 deprecated

Every `deprecated` row: the prelude `Button` and `Interaction`, `weak_handle!`, `AssetId::invalid`
and `AssetId::INVALID_UUID`, and `template_value` in `bsn!`. Each still builds, with a warning.

**Why:** the shipped CI denies warnings, so a deprecated name breaks the build the day it is
compiled there, on code that has not changed; and the prelude `Button` shares its name with the live
`bevy::ui_widgets::Button`, so only the compiler tells the two apart.

**Check:** rustc's `deprecated` lint, under the shipped CI's `CARGO_BUILD_WARNINGS: deny`; before a
build, `rg -n 'AssetId::(invalid|INVALID_UUID)|weak_handle!|template_value' src/`.

### BV-MIG-04 [M] Re-read every `Ref` that is cloned

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
| rustc | `deprecated` | warn | a deprecated Bevy API — listed because the shipped CI denies warnings, so BV-MIG-03's rows fail its build |
