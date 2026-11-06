---
name: bevy-style
description: >-
  Use when writing, reviewing, refactoring, scaffolding, porting or debugging any Bevy code,
  bringing code written for an older Bevy up to date, or deciding whether something belongs in a
  system or in plain Rust, even when no one asks for "style" or "standards". Applies to a plugin, a
  system, a component, a query, a schedule, an observer, a message, a state, an asset handle, a UI
  tree and a `Cargo.toml` with `bevy` in it. Targets Bevy 0.20.
---

# Bevy Style — 0.20

A **delta on top of `rust-style`**. Everything that standard says about naming, errors, ownership,
functional style, modules, documentation and Cargo still holds; this one states what changes when
Bevy is in the dependency list, and nothing else. Section 3 lists every place the two depart.

Its tiers are `rust-style`'s, and so is the code `[M!]` binds in. Read for a game: a shipped game is
high-reliability code, since a panic takes down a process someone else owns — the player's, or the
server their session lives on — an authoritative server parses what its clients send, and saves and
replays are data others cannot reconstruct. A plugin crate others depend on is library code. A jam
prototype, editor scratch, an example scene and a throwaway tool are none of these, and take each
`[M!]` rule's relaxed form.

**Target: Bevy 0.20 on Rust 1.99, edition 2024.** Bevy's API turns over faster than any other
dependency a game has, and most Bevy code on the public internet — and most of what a language model
has read — is 0.15 or older. Section 2 and the migration chapter exist for that reason.

## How to use this standard

1. **Read section 2** before emitting Bevy code. It is the Bevy 0.20 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Load `rust-style` as well** for anything that is a Rust question rather than a Bevy question.
5. **Walk section 5** before handing back a diff.

Rules are cited by ID: `BV-`, then the family of the chapter that owns the rule, then its number.
Section 6 maps each family to its chapter, so cite the ID when justifying a change and the reader
can find the full rule and its rationale. When two rules appear to conflict, sections 1 and 3 govern
how to break the tie.

Rules from the other standard keep their own prefix, so an `RS-` citation is always a pointer out of
this document.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered, the migration
chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Bevy 0.20.1 on Rust 1.99, edition 2024, and any test it ships passes. `// fragment`
— shown in context rather than run as a unit, usually because it uses names the chapter declares
around it. `// rejected — <tool>: …` — the rejection is the point, and the marker names the tool
that rejects it: `rustc`, `clippy`, `rustdoc`. A trailing `— GOOD` or `— BAD` names which side of
the rule the block illustrates. A block in another language carries its marker in that language's
comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Bevy code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in library and high-reliability code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**Code is "library or high-reliability" — `[M!]` applies as `[M]` — if any of these hold:** it is
published to a registry or consumed by code you do not control; a panic takes down a process that
someone else owns (a server, a plugin, an embedded target); it is a security boundary (parsers on
untrusted input, cryptography, sandboxes, allocators); or it stores data others cannot reconstruct.
**Otherwise** — scripts, internal binaries, prototypes, examples — `[M!]` rules are recommendations,
and the relaxed form given with each rule is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Bevy 0.20 reality check

### 2.1 Compiles, and behaves differently

- `next.set(S)` runs `OnExit(S)` and `OnEnter(S)` when the state is already `S`, so code that sets
  it every frame re-runs every setup and teardown; `set_if_different` is the old behaviour
  (BV-STATE-17).
- A resource is a component on an entity of its own: `Query<Entity>`, `Query<EntityRef>` and
  `Query<EntityMut>` match it, a sweep that despawns all it matches panics under the default error
  handler, and `Query<EntityMut>` beside any `Res` panics with B0002 (BV-STATE-02).
- A panic in a system, observer or command reaches the fallback error handler, so a release handler
  that only logs keeps running past it, overflow traps included (BV-ERR-05).
- `iter_many` yields a `Result` per id, so `.count()` and `for _ in` count ids the query does not
  match; `.matched()` is the old meaning (BV-ECS-20).
- `value.clone()` on a `Ref<T>` is another `Ref<T>`, where it was a `T` (BV-MIG-04).
- Bevy adds and updates the `Aabb` of meshes and sprites, so a system that writes one fights the
  engine (BV-VIEW-16).
- `AssetEvent::Modified` fires only on an actual mutation, so a `get_mut` that only reads raises
  none (BV-ASSET-09).
- Bloom judges luminance in linear, so a tint tuned against sRGB blooms more (BV-VIEW-11).
- `EditableText` spawned alone ignores the keyboard; `TextInput` requires it and drives it
  (BV-VIEW-08).
- Inside `UiSystems` and the render schedules' sets, systems the ECS sees no conflict between are
  unordered, so one relying on hidden ordering races (BV-SCHED-14).
- `Camera2d` brings `Tonemapping::Linear`, and `Camera3d` no longer requires
  `ScreenSpaceTransmission` (BV-VIEW-12); `Tonemapping::None` is a full passthrough (BV-VIEW-20).
- `TextFont::default()` sizes text at `FontSize::Rem(1.)`, which follows `RemSize` (BV-VIEW-04).
- `bevy_scene` names the `bsn!` scene system, the old one being `bevy_world_serialization`
  (BV-MIG-02), and the `compressed_image_saver` feature selects a BCn/ASTC backend (BV-BUILD-03).

### 2.2 No longer compiles

| Old | Bevy 0.20 | Rule |
|---|---|---|
| `SpriteBundle` | `Sprite::from_image(handle)` plus `Transform` | BV-ECS-06 |
| `SpriteSheetBundle` | `Sprite::from_atlas_image(handle, atlas)` | BV-ECS-06 |
| `PbrBundle` | `Mesh3d(mesh)` plus `MeshMaterial3d(material)` | BV-ECS-06 |
| `MaterialMesh2dBundle` | `Mesh2d(mesh)` plus `MeshMaterial2d(material)` | BV-ECS-06 |
| `ImageBundle` | `ImageNode::new(handle)` | BV-ECS-06 |
| `PointLightBundle` | `PointLight::default()` plus `Transform` | BV-ECS-06 |
| `DirectionalLightBundle` | `DirectionalLight::default()` plus `Transform` | BV-ECS-06 |
| `SpatialBundle` | `Transform`; `Visibility` and the rest are required components | BV-ECS-06 |
| `TransformBundle` | `Transform` | BV-ECS-06 |
| `VisibilityBundle` | `Visibility` | BV-ECS-06 |
| `AudioBundle` | `AudioPlayer(handle)` | BV-ECS-06 |
| `NodeBundle` | `Node::default()` | BV-VIEW-01 |
| `ButtonBundle` | `bevy::ui_widgets::Button` plus `Node` | BV-VIEW-06 |
| `Camera2dBundle` | `Camera2d` | BV-VIEW-12 |
| `Camera3dBundle` | `Camera3d::default()` | BV-VIEW-12 |
| `TextBundle` | `Text::new(s)` plus `TextFont` and `TextColor` | BV-VIEW-04 |
| `Text2dBundle` | `Text2d::new(s)` plus `TextFont` and `TextColor` | BV-VIEW-04 |
| `TextStyle` | `TextFont { font, font_size, .. }` plus `TextColor(color)` | BV-VIEW-04 |
| `Text::from_section` | `Text::new(s)`, with `TextFont` and `TextColor` beside it | BV-VIEW-04 |
| `JustifyText` | `Justify` | BV-VIEW-04 |
| `BreakLineOn` | `LineBreak` | BV-VIEW-04 |
| `TextLayout::new_with_justify` | `TextLayout::justify(j)` | BV-VIEW-04 |
| `TextLayout::new_with_linebreak` | `TextLayout::linebreak(b)` | BV-VIEW-04 |
| `TextLayout::new_with_no_wrap` | `TextLayout::no_wrap()` | BV-VIEW-04 |
| `resolve_font_source` | `font.font.resolve_font_family(fonts)` | BV-VIEW-04 |
| `FontSource::SansSerif` | `FontSource::sans_serif()`, or `FontSource::Generic` with a `GenericFontFamily`; every generic family variant likewise | BV-VIEW-04 |
| `Style` | `Node` | BV-VIEW-01 |
| `UiImage` | `ImageNode`, which carries its own colour | BV-VIEW-01 |
| `UiImageSize` | `ImageNodeSize` | BV-VIEW-01 |
| `ComputedNode::stack_index` | `ComputedStackIndex` | BV-VIEW-03 |
| `ComputedNodeTarget` | `ComputedUiTargetCamera` | BV-VIEW-03 |
| `CoreButton` | `bevy::ui_widgets::Button`; every `Core*` widget component is its name without `Core` | BV-VIEW-07 |
| `button_bundle` | the feathers `FeathersButton` with `FeathersButtonProps`, used from `bsn!`; each `*_bundle` spawn function likewise | BV-VIEW-07 |
| `FeathersPlugin` | `FeathersCorePlugin` | BV-VIEW-07 |
| `EditableTextInputPlugin` | `TextInputPlugin` | BV-VIEW-08 |
| `TextScroll` | `EditableText::viewport` (`TextViewport`) | BV-VIEW-08 |
| `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) | BV-VIEW-08 |
| `Pointer<Click>` | `PointerClick`, its fields one level up and no `.event`; every `Pointer<X>` is `PointerX`, and a generic `On<Pointer<E>>` is `On<E>` with `E: PointerEvent` | BV-MIG-02 |
| `pointer_location` | `ev.pointer.position` (`Vec2`), or `ev.pointer.location()` for the `Location`; `ev.pointer_id` is `ev.pointer.id` | BV-MIG-02 |
| `Parent` | `ChildOf`, read with `child_of.parent()` | BV-ECS-11 |
| `set_parent` | `insert(ChildOf(p))`; `set_parent_in_place`, which keeps the child's `GlobalTransform`, is live | BV-ECS-11 |
| `push_children` | `add_children` | BV-ECS-11 |
| `remove_children` | `detach_children` | BV-ECS-11 |
| `remove_child` | `detach_child` | BV-ECS-11 |
| `clear_children` | `detach_all_children` | BV-ECS-11 |
| `clear_related` | `detach_all_related::<R>()` | BV-ECS-11 |
| `despawn_recursive` | `despawn()`, which is recursive | BV-ECS-11 |
| `despawn_descendants` | `despawn_related::<Children>()` | BV-ECS-11 |
| `ChildBuilder` | `ChildSpawnerCommands`, whose `target_entity()` was `parent_entity()` | BV-ECS-11 |
| `parent_entity` | `target_entity()` | BV-ECS-11 |
| `HierarchyQueryExt` | `Query::related()` for `parent()`, `Query::relationship_sources()` for `children()` | BV-ECS-11 |
| `get_single_mut` | `Query::single_mut()`, which returns `Result` | BV-ERR-01 |
| `to_readonly` | `Query::as_readonly()` | BV-ECS-15 |
| `DefaultErrorHandler` | `FallbackErrorHandler` | BV-ERR-05 |
| `init_non_send_resource` | `App::init_non_send` | BV-ERR-07 |
| `non_send_resource` | `World::non_send` | BV-ERR-07 |
| `non_send_resource_mut` | `World::non_send_mut` | BV-ERR-07 |
| `ExclusiveSystemParam` | `&mut World` as a `SystemParam`; `ExclusiveFunctionSystem` and `ExclusiveMarker` went with it | BV-ECS-29 |
| `EventReader` | `MessageReader<M>` | BV-EVENT-05 |
| `EventWriter` | `MessageWriter<M>`, whose `send`, `send_batch` and `send_default` are `write`, `write_batch` and `write_default` | BV-EVENT-01 |
| `Events` | `Messages<M>` | BV-EVENT-04 |
| `ManualEventReader` | `MessageCursor` | BV-EVENT-05 |
| `send_event` | `write_message`, on `World` and on `Commands` | BV-EVENT-01 |
| `trigger_targets` | an `EntityEvent` carrying its target as a field: `commands.trigger(E { entity })` | BV-EVENT-08 |
| `event_target_mut` | `SetEntityEventTarget`, which game code does not need | BV-EVENT-11 |
| `OnAdd` | `Add` | BV-EVENT-13 |
| `OnInsert` | `Insert` | BV-EVENT-13 |
| `OnReplace` | `Discard`, not `Replace` | BV-EVENT-13 |
| `OnRemove` | `Remove` | BV-EVENT-13 |
| `OnDespawn` | `Despawn` | BV-EVENT-13 |
| `Replace` | `Discard` | BV-EVENT-13 |
| `on_replace` | `on_discard` | BV-EVENT-13 |
| `TransformSystem` | `TransformSystems` | BV-ARCH-10 |
| `UiSystem` | `UiSystems` | BV-ARCH-10 |
| `PickSet` | `PickingSystems` | BV-ARCH-10 |
| `InputSystem` | `InputSystems` | BV-ARCH-10 |
| `InputFocusSet` | `InputFocusSystems` | BV-ARCH-10 |
| `TimeSystem` | `TimeSystems` | BV-ARCH-10 |
| `AccessibilitySystem` | `AccessibilitySystems` | BV-ARCH-10 |
| `RemoteSet` | `RemoteSystems` | BV-ARCH-10 |
| `StateTransitionSteps` | `StateTransitionSystems` | BV-ARCH-10 |
| `bevy::animation::Animation` | `AnimationSystems` | BV-ARCH-10 |
| `AssetEvents` | `AssetEventSystems` | BV-ARCH-10 |
| `TrackAssets` | `AssetTrackingSystems` | BV-ARCH-10 |
| `EventUpdates` | `MessageUpdateSystems` | BV-ARCH-10 |
| `CameraUpdateSystem` | `CameraUpdateSystems` | BV-ARCH-10 |
| `RunFixedMainLoopSystem` | `RunFixedMainLoopSystems` | BV-ARCH-10 |
| `SpriteSystem` | nothing: `SpriteSystems`, its 0.17 name, is gone from `bevy::sprite` and `bevy::sprite_render` too | BV-ARCH-10 |
| `ExecutorKind` | `Schedule::set_executor(SingleThreadedExecutor::new())` and the other executors | BV-SCHED-22 |
| `set_executor_kind` | `set_executor` | BV-SCHED-22 |
| `SimpleExecutor` | `SingleThreadedExecutor` | BV-SCHED-22 |
| `StateScoped` | `DespawnOnExit` | BV-STATE-15 |
| `PendingIfNeq` | `PendingIfDifferent` | BV-STATE-17 |
| `set_state_if_neq` | `set_state_if_different` | BV-STATE-17 |
| `set_next_state_if_neq` | `set_next_state_if_different` | BV-STATE-17 |
| `Timer::finished` | `Timer::is_finished()`; `paused()` is `is_paused()` likewise | BV-MIG-02 |
| `compute_matrix` | `to_matrix`, on `Transform` and `GlobalTransform` | BV-MIG-02 |
| `Handle::weak_from_u128` | the `uuid_handle!("…")` macro; `Handle` has only `Strong` and `Uuid` | BV-ASSET-03 |
| `load_with_settings` | `load_builder().with_settings(…).load(path)` | BV-ASSET-07 |
| `load_override` | `load_builder().override_unapproved()` | BV-ASSET-07 |
| `load_acquire` | `load_builder().with_guard(…)` | BV-ASSET-07 |
| `SceneRoot` | `WorldAssetRoot` | BV-MIG-02 |
| `DynamicScene` | `DynamicWorld`; `from_scene` is `from_world_asset`, and needs a `&TypeRegistry` | BV-MIG-02 |
| `DynamicSceneBuilder` | `DynamicWorldBuilder`, which needs a `&TypeRegistry` | BV-MIG-02 |
| `DynamicSceneRoot` | `DynamicWorldRoot` | BV-MIG-02 |
| `SceneInstanceReady` | `WorldInstanceReady` | BV-MIG-02 |
| `SceneSpawner` | `WorldInstanceSpawner` | BV-MIG-02 |
| `SceneLoader` | `WorldAssetLoader` | BV-MIG-02 |
| `SceneFilter` | `WorldFilter` | BV-MIG-02 |
| `bevy::a11y::Focus` | `bevy::input_focus::InputFocus` | BV-MIG-02 |
| `AnimationTarget` | the separate components that replaced it | BV-MIG-02 |
| `Atmosphere::earthlike` | `Atmosphere::earth` | BV-MIG-02 |
| `Font::try_from_bytes` | `Font::from_bytes`, which returns the `Font` | BV-MIG-02 |
| `bevy_math::curve` | `bevy_curve`, or `bevy::curve` | BV-ARCH-06 |
| `bevy_math::cubic_splines` | `bevy_curve`, or `bevy::curve` | BV-ARCH-06 |
| `bevy_math::primitives` | `bevy_shape`, or `bevy::shape`; `bevy::prelude` names them as it did | BV-ARCH-06 |
| `#import` | a `.wesl` with `import …;` | BV-VIEW-18 |
| `#ifdef` | `@if(…)` in a `.wesl` | BV-VIEW-18 |
| `#define_import_path` | the `.wesl` module's own path | BV-VIEW-18 |
| `#{MATERIAL_BIND_GROUP}` | `constants::MATERIAL_BIND_GROUP` | BV-VIEW-18 |
| `"shader_format_glsl"` | nothing: GLSL is gone | BV-VIEW-18 |
| `"shader_format_wesl"` | nothing: WESL is the only shader language | BV-VIEW-18 |
| `"animation"` | `"gltf_animation"` | BV-BUILD-03 |
| `"bevy_sprite_picking_backend"` | `"sprite_picking"` | BV-BUILD-03 |
| `"bevy_ui_picking_backend"` | `"ui_picking"` | BV-BUILD-03 |
| `"bevy_mesh_picking_backend"` | `"mesh_picking"` | BV-BUILD-03 |
| `"experimental_bevy_feathers"` | `"bevy_feathers"` | BV-BUILD-03 |
| `"experimental_ui_widgets"` | `"bevy_ui_widgets"` | BV-BUILD-03 |
| `"bevy_math/curve"` | `"bevy/bevy_curve"` | BV-BUILD-03 |
| `Trigger<E>` | `On<E>`, read by the event's own name; `Trigger` is now a trait | BV-EVENT-13 |
| `On<Add, T>` | `On<Add<T>>`, and so for `Insert`, `Discard`, `Remove` and `Despawn`; a custom `On<E, B>` is a `PhantomData` wrapper implementing `EventPattern` | BV-EVENT-13 |
| `On<Add>` | `On<Add<()>>`, for an observer of dynamic components (`.with_component(id)`) | BV-EVENT-13 |
| `.add_event::<M>()` | `.add_message::<M>()`; `AnimationClip::add_event` is live | BV-EVENT-04 |
| `on_event::<M>()` | `on_message::<M>()`, or a `PopulatedMessageReader` | BV-EVENT-05 |
| `App::observe` | `App::add_observer`, as `Commands::observe` is `Commands::add_observer`; `EntityCommands::observe` is live | BV-EVENT-15 |
| `NextState::set_if_neq` | `set_if_different`; `Mut::set_if_neq` is live, so the name finds both | BV-STATE-17 |
| `.get_single()` | `Query::single()`, which returns `Result`; `Gradient::get_single` is live | BV-ERR-01 |
| `impl Command<Result>` | `impl Command { type Out = Result; }`; `-> impl Command` with a closure returning `Result` | BV-ERR-01 |
| `Handle<AnimationGraph>` | `AnimationGraphHandle(handle)` as the component | BV-ECS-13 |
| `TextSection` | a live trait; the old struct is a `TextSpan` on a child entity | BV-VIEW-05 |
| `Text { sections }` | a `Text` root with `TextSpan` children | BV-VIEW-05 |
| `TextFont { line_height }` | the `LineHeight` component | BV-VIEW-04 |
| `TextFont { font: handle }` | `TextFont { font: FontSource::Handle(handle), .. }` | BV-VIEW-04 |
| `TextFont { font_size: f32 }` | `TextFont { font_size: FontSize::Px(…), .. }` | BV-VIEW-04 |
| `Camera { hdr }` | the separate `Hdr` component | BV-VIEW-12 |
| `Camera { target }` | `RenderTarget` as its own component | BV-VIEW-14 |
| `bevy_pbr::mesh_view_bindings` | `bevy_pbr::render::mesh_view_bindings` | BV-VIEW-18 |
| `Condition` | `SystemCondition`; the new name contains the old, so read each bound | BV-SCHED-17 |
| `Scene` | a trait of the `bsn!` system; the asset is `WorldAsset` | BV-MIG-02 |
| `Window { cursor_options }` | the separate `CursorOptions` component, which `Window` requires | BV-MIG-02 |
| `Sprite { anchor }` | the separate `Anchor` component, which `Sprite` requires: a `Vec2` newtype, `Anchor::CENTER` for `Anchor::Center` and `Anchor(v)` for `Anchor::Custom(v)` | BV-MIG-02 |
| `AmbientLight` | a camera component; the resource is `GlobalAmbientLight` | BV-MIG-02 |
| `Skybox { image }` | `Option<Handle<Image>>` | BV-MIG-02 |
| `BorderRadius { top_left }` | `CornerRadius` fields, such as `px(10.).into()` | BV-MIG-02 |
| `MeshTag(x)` | `MeshTag::new(x)`, read as `tag.value` | BV-MIG-02 |

### 2.3 What Bevy 0.20 gained

- `#[require(…)]` required components, in place of a `*Bundle` type (BV-ECS-06).
- `ChildOf` and `Children`, and relationships of a game's own, in place of a hand-kept `Vec<Entity>`
  (BV-ECS-11).
- A system that returns `Result` and uses `?`, in place of `unwrap()` on `Query::single`
  (BV-ERR-01); `.context(…)` on a `Result` or an `Option`, in place of `ok_or(…)` (BV-ERR-03).
- `Message` for buffered fan-out and `Event` for a reaction, in place of one word for both
  (BV-EVENT-01), and `.run_if(…)` on an observer, in place of an early `return` (BV-SCHED-16).
- The `2d`, `3d` and `ui` feature collections, in place of a hand-kept list of features
  (BV-BUILD-02).
- `bsn!`, in place of nested `with_children` closures (BV-VIEW-09).
- `commands.delayed()`, in place of a `Timer` whose only job is to postpone a spawn (BV-SCHED-05).
- `DiagnosticsOverlayPlugin`, in place of a hand-written FPS `Text` system (BV-BUILD-11).
- `Gizmos::text()` and `text_2d()`, in place of a spawned `Text2d` for a debug value (BV-VIEW-19).
- `TextInput`, in place of a third-party text-input crate (BV-VIEW-08).
- `#[derive(SettingsGroup)]`, in place of hand-rolled settings load and save (BV-STATE-09).
- `Query::contiguous_iter()`, in place of a hand-kept structure of arrays (BV-ECS-23).
- `chain_weak()` and `after_weak()`, in place of strong ordering between systems that never conflict
  (BV-SCHED-14).
- `Val::Em` and `Val::Rem`, in place of scaling a node by hand with the text size (BV-VIEW-02).

## 3. Design principles

The spine of this standard is the boundary: the rules of the game live in plain Rust that never
names Bevy, and the engine is the view and the input around them (BV-ARCH-01). An engine upgrade
then rewrites signatures and not arithmetic. Everything else follows `rust-style`'s principles.

Each row is a `rust-style` rule that Bevy makes impossible, harmful or noisy (`overrides`), raises
(`tightens`) or reaches further (`extends`), the rule here that departs from it, and both tiers.
Nothing else departs: a divergence not listed here is a defect, not a dialect.

| rust-style rule | Relation | bevy-style rule | Tier | Reason |
|---|---|---|---|---|
| RS-API-15 | overrides | BV-ECS-01 | [M] → [M] | The ECS is the accessor: reflection, scenes, `bsn!` and the remote protocol read fields directly, and a component cannot defend an invariant, so BV-ARCH-04 defends it in the domain |
| RS-API-36 | extends | BV-ECS-03 | [M] → [M] | Every component, public or not: every panic, `info!` and failed test prints one |
| RS-API-53 | overrides | BV-ECS-05 | [M] → [M] | A component is spawned by struct literal in every crate, which `#[non_exhaustive]` forbids; it grows by a required component instead |
| RS-NAME-29 | overrides | BV-ARCH-10 | [M] → [M] | `add_plugins(X)` and `configure_sets(_, X)` are one shape with two meanings, so the name is the only signal, as Bevy's own plugins and sets carry it |
| RS-ERR-13 | overrides | BV-ERR-02 | [M!] → [M] | A system has no caller to match on its error — the schedule hands it to the handler — and the schedule takes no other type; what a caller branches on stays a real type in the domain (BV-ERR-03) |
| RS-BUILD-21 | overrides | BV-BUILD-04 | [M] → [M] | In a game binary the exact pin makes every Bevy bump, patch included, a commit of its own; a library keeps the caret |
| RS-BUILD-22 | overrides | BV-BUILD-02 | [M] → [M] | Bevy's 177 features move every release, so a hand-picked list goes stale silently; a collection is upstream's own |
| RS-BUILD-25 | overrides | BV-BUILD-12 | [M] → [M] | Two lints fire on every system parameter, so no handful of items could carry the `allow` |
| RS-BUILD-43 | tightens | BV-BUILD-07 | [S] → [M] | An unoptimised Bevy is too slow for frame rate to say anything about the game |
| RS-TEST-19 | extends | BV-TEST-08 | [M] → [M] | Every test, not only a regression test: a Bevy test passes vacuously when its system was never added or its schedule never ran |

Two that look like departures are not. `clippy::wildcard_imports` exempts preludes, and
`use bevy::prelude::*` is one. And RS-NAME-02 holds as it stands: Bevy's packages spell `bevy_ecs`
with an underscore in upstream's namespace, and a package published from this standard uses hyphens
(BV-ARCH-08).

## 4. Core rules

- **Architecture: The Boundary, Plugins, Crate Shape**
  - BV-ARCH-01 [M] Keep the rules of the game out of the engine's vocabulary
  - BV-ARCH-02 [M] Scale the boundary's mechanism to the project; never the rule
  - BV-ARCH-03 [M] Give the boundary exactly one crossing point per direction
  - BV-ARCH-04 [M] Keep the invariant in the domain type, and parse at the crossing
  - BV-ARCH-07 [M] Make the boundary a job, not a paragraph
  - BV-ARCH-09 [M] Write every plugin as a type
  - BV-ARCH-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`
  - BV-ARCH-15 [M] Keep `main` to plugins and the two error policies
  - BV-ARCH-16 [M] Return `AppExit` from `main`
- **ECS: Components, Required Components, Queries, Change Detection**
  - BV-ECS-02 [M] Give a component one fact to hold
  - BV-ECS-03 [M] Derive `Debug` and `Reflect` on every component
  - BV-ECS-06 [M] Express "always has" with `#[require]`
  - BV-ECS-12 [M] Register each instantiation of a generic reflected type
  - BV-ECS-16 [M] Put a zero-sized marker in the filter, never in the data
  - BV-ECS-19 [M] Name a query type once it needs two lines
  - BV-ECS-24 [M] Write with `set_if_neq` wherever a `Changed` filter is watching
- **Scheduling: Schedules, Sets, Ordering, Run Conditions, Time**
  - BV-SCHED-01 [M] Simulate in `FixedUpdate`, present in `Update`
  - BV-SCHED-05 [M] Take the delta from the schedule's own clock
  - BV-SCHED-09 [M] Never read per-frame input from a fixed-rate schedule
  - BV-SCHED-10 [M] Group system parameters by what they are together
  - BV-SCHED-12 [M] Express ordering through named sets
  - BV-SCHED-16 [M] Express a precondition as a run condition, not an early return
- **Events: Messages, Events, Entity Events, Observers**
  - BV-EVENT-01 [M] Send a `Message` to fan out, trigger an `Event` to react
  - BV-EVENT-03 [M] Do not derive both `Message` and `Event` on one type
  - BV-EVENT-04 [M] Register a message type with `add_message`
  - BV-EVENT-08 [M] Give an event about one entity the `EntityEvent` derive and an entity field
  - BV-EVENT-09 [M] Read the target from the named field
- **Errors: Fallible Systems, the Error Handler, Panicking APIs**
  - BV-ERR-01 [M!] Return `Result` from a system that can fail
  - BV-ERR-05 [M] Choose the fallback error handler deliberately
  - BV-ERR-07 [M] Call the non-panicking half of every pair outside a test
- **Cargo: Features, Version Pinning, Lints, CI**
  - BV-BUILD-02 [M] Start from a feature collection
  - BV-BUILD-03 [M] Hand-pick features only against a recorded measurement
  - BV-BUILD-04 [M] Pin Bevy exactly in a binary and with a caret in a library
  - BV-BUILD-12 [M] Relax `elided_lifetimes_in_paths` and `needless_pass_by_value`, and nothing else

## 5. Review checklist

When reviewing or self-reviewing a Bevy diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **The boundary.** Does anything outside the view layer name Bevy? (BV-ARCH-01)
2. **Stale APIs.** Is every API a 0.20 API — no `Trigger`, `EventReader`, `Parent`, `*Bundle`,
   `Pointer<Click>` or `On<Add, T>`? (BV-MIG-01)
3. **Errors and panics.** Does every fallible system return `Result`, and does the release error
   handler still end the app on a caught panic? (BV-ERR-01, BV-ERR-05)
4. **Change detection.** Is any `Changed<T>` watching something written unconditionally? (BV-ECS-24)
5. **Ordering.** Is ordering expressed in sets, not against a system function? (BV-SCHED-12)
6. **Run conditions and state.** Would each new system be skipped when it should be? (BV-SCHED-16,
   BV-STATE-15)
7. **Reflection.** Does each new component derive `Reflect`, and is each generic instantiation
   registered? (BV-ECS-03, BV-ECS-12)
8. **Tests.** Is the rule tested without an `App`, and the plugin with the smallest one?
   (BV-ARCH-01, BV-TEST-02)
9. **Relaxed forms.** Is anything `[M!]` relying on its relaxed form, and which of section 1's
   conditions does not hold?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. All
174 rules live here; section 4 lists by ID those that bind on their own.

| File | Rule IDs | Covers |
|---|---|---|
| `references/architecture.md` | `BV-ARCH` (17) | The boundary between the game and the engine, the shape of a plugin and what it registers, and the `App` and its binary |
| `references/ecs.md` | `BV-ECS` (29) | Components and required components, queries and filters, change detection, relationships, and reflection |
| `references/scheduling.md` | `BV-SCHED` (24) | Schedules and the fixed timestep, system sets and ordering, run conditions, time, and input |
| `references/events.md` | `BV-EVENT` (18) | Messages, events and entity events, observers and propagation, and the lifecycle events |
| `references/state.md` | `BV-STATE` (19) | Resources, `States` and their transitions, and what a state scopes |
| `references/errors.md` | `BV-ERR` (10) | Fallible systems, observers and commands, the fallback error handler, and the APIs that panic |
| `references/assets.md` | `BV-ASSET` (10) | Handles and loading, hot reload, asset events, and asset lifetime |
| `references/build.md` | `BV-BUILD` (14) | Feature collections, the exact Bevy pin, the lint divergences from rust-style, and CI |
| `references/migration.md` | `BV-MIG` (4) | Every old spelling Bevy 0.15 through 0.20 left behind, with its status and owning rule, and the command the table generates |
| `references/view.md` | `BV-VIEW` (20) | UI nodes and layout, text, cameras, materials and shaders, post-processing, and gizmos |
| `references/testing.md` | `BV-TEST` (9) | Headless apps, deterministic fixed steps, and what a test asserts |
| `references/review-checklist.md` | — | The audit protocol: the shared seven-level severity model, review order, mechanical pass, output format, and the order in which to refactor an existing game |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/Cargo.toml` | The workspace manifest for a game: an exact Bevy pin with a feature collection, the lint table with its two Bevy relaxations and their reasons, and the profiles that keep debug builds playable |
| `assets/ci.yml` | The workflow: the boundary and one-Bevy checks, clippy and tests under deny-warnings, docs, the weekly advisory audit, the MSRV job and the release build |
| `rust-style`'s `assets/clippy.toml`, `assets/rustfmt.toml` and `assets/rust-toolchain.toml` | Unchanged: a delta ships only the assets it departs in, and these it does not. Its `clippy.toml` already allows `unwrap` and `expect` inside tests, the relaxed form BV-ERR-01 states |
