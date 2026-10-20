# bevy-style: Bevy 0.19.1 → 0.20.0, and lint-backed rules — research notes

Researched 2026-10-20. Read-only: nothing in the repo was edited, and no cargo build, `agent-skill check` or
pytest was run. Every 0.20 claim cites a source key from the list below. Anything not confirmed is marked
**UNCONFIRMED**.

## Sources

| Key | Source | What it established |
|---|---|---|
| [G] | Migration guide 0.19→0.20: https://bevy.org/learn/migration-guides/0-19-to-0-20/ (source: https://github.com/bevyengine/bevy-website/blob/main/content/learn/migration-guides/0.19-to-0.20.md) | every breaking change listed below unless otherwise keyed; read in full (2116 lines) |
| [R] | Release notes: https://bevy.org/news/bevy-0-20/ (source: https://github.com/bevyengine/bevy-website/blob/main/content/news/2026-10-08-bevy-0.20/index.md) | new features, catching panics, `Ready`, `despawn_all`, `chain_weak`, `shuffle_seed`, `ContextExt`, `summary_tick`, `FixedNode`, Em/Rem, PanOrbitCamera, sprite materials |
| [C] | crates.io: https://crates.io/api/v1/crates/bevy | 0.20.0 published 2026-10-08 22:31 UTC, MSRV `rust-version = 1.97.1`; no 0.20.1 as of 2026-10-20 |
| [S] | Bevy source at tag `v0.20.0` (and `v0.19.1` for diffs): https://github.com/bevyengine/bevy/tree/v0.20.0 | used for facts the guide omits; file named in each row |
| [D] | docs.rs item index: https://docs.rs/bevy/0.20.0/bevy/all.html vs https://docs.rs/bevy/0.19.1/bevy/all.html | item-level diff: 93 simple names removed, 606 added |
| [PR24240] | https://github.com/bevyengine/bevy/pull/24240 "Pass panics to the fallback error handler" (merged 2026-06-01, lands in 0.20) | panic → `FallbackErrorHandler` routing |
| [G18] | Migration guide 0.18→0.19, line 1728: https://github.com/bevyengine/bevy-website/blob/main/content/learn/migration-guides/0.18-to-0.19.md | `Replace` → `Discard` happened in 0.19 (pre-existing error in the skill) |
| [BL] | bevy_cli repo: https://github.com/TheBevyFlock/bevy_cli — releases, `bevy_lint/CHANGELOG.md`, `docs/src/linter/compatibility.md`, lint sources at tag `lint-v0.6.0`, issue #832, PRs #835, #925, #943 | `bevy_lint` support status, lint names and groups |
| [BLC] | https://thebevyflock.github.io/bevy_cli/linter/compatibility.html and `docs/src/linter/usage/toggling-lints-cargo-toml.md` | compatibility table; `[workspace.metadata.bevy_lint]` configuration |
| [CL] | `cargo clippy --explain <lint>` on local rustc/clippy 1.99.0 (2026-09-28), and clippy source at tag `rust-1.99.0` (https://github.com/rust-lang/rust-clippy/tree/rust-1.99.0) for lint groups | clippy lint names exist; groups |
| [RC] | `rustc -W help` (1.99.0) | rustc lint names and default levels |

## Headline numbers

- **38 rule-level impact rows** (table below). **9 of them carry a compile-silent behaviour change**,
  from 7 distinct mechanisms:
  - panics routed to the handler (BV-ERR-05, BV-ERR-04, BV-CAR-09)
  - `iter_many` yielding `Result`
  - `EditableText` no longer interactive on its own
  - weak ordering of the engine's own sets
  - the duplicate `RenderDebugOverlayPlugin` panic
  - `TextFont`'s default size
  - tonemapping and transmission defaults

  There are also SKILL.md-level edits (version literals in 6 places, the §3 feature count, §5 item 2,
  BV-CORE-19), and 6 pre-existing inaccuracies found along the way.
- **4 new forbidden-API rules** proposed for `migration.md`, each with a literal `rg`, plus edits to 9
  existing rows. Also **1 new silent-change rule**, whose `iter_many` Check would need a `not_decisive`
  entry.
- **Feature collections are unchanged.** `2d`, `3d`, `ui`, `audio`, `scene`, `std`, `*_api`, `default_app`
  and `default_platform` have identical definitions in 0.19.1 and 0.20.0 [S `Cargo.toml`]. Feature count
  172 → 177. Two features were removed (`shader_format_glsl`, `shader_format_wesl`) and seven added
  (`bevy_curve`, `bevy_extract`, `complex_script_segmentation`, `compressed_image_saver_universal`,
  `pan_orbit_camera`, `pan_orbit_gizmo`, `render_dev_tools`).
- **`bevy_lint` supports neither 0.19 nor 0.20**: not in any release, and not on `main`.
- **Lint classification: 11 LINT, 14 PARTIAL.** 5 of the LINT rules are fully enabled by the shipped
  `assets/Cargo.toml`, and 1 is half-enabled.

---

## Rule impacts

The tag says what kind of change each row is. **SILENT** compiles and behaves differently. **BREAK** is a
compile error or a deprecation warning, and the shipped CI denies warnings. **STALE** means the prose or a
version literal is now wrong. **NEW** is a new 0.20 facility the rule should name.

| ID | file | what changes | source |
|---|---|---|---|
| BV-ERR-05 | errors.md | **SILENT.** 0.20 hands every panic in a system, observer or command to `FallbackErrorHandler`: "Called both for explicitly returned errors, and when a panic occurs." The example's release handler `error` therefore now **logs and continues** after any panic. That covers `unwrap` inside dependencies, index panics, engine panics, and the overflow traps BV-CAR-09 turns on. The default (`match_severity`) still re-panics, because a caught panic arrives as `Severity::Panic` carrying the payload. Fix: a release handler that resumes unwinding when `err.take_payload()` is `Some`, or that delegates `Severity::Panic` to `bevy::ecs::error::panic` and logs the rest. | [R] "Catching Panics", [PR24240], [S] `crates/bevy_ecs/src/error/handler.rs` L108-158, `bevy_error.rs` L188-195, `schedule/executor/multi_threaded.rs` L661, L711, L803 |
| BV-ERR-01 | errors.md | **STALE.** The Why says "every panic in a Bevy system takes the whole app down". Under a non-panicking fallback handler that is now false. | [R], [PR24240] |
| BV-ERR-13 | errors.md | **STALE.** The Why says an observer panic "unwinds through the ECS's own machinery". Observer panics now reach the handler too. | [R] |
| BV-ERR-04 | errors.md | **STALE/SILENT.** "`Severity::Panic` when continuing would corrupt something" is honoured only by a severity-dispatching handler. BV-ERR-05's `error` handler ignores it, and from 0.20 it ignores real panics the same way. The two rules need reconciling. | [S] `handler.rs` |
| BV-ERR-03 | errors.md | **NEW.** `ContextExt::context` / `with_context` on `Result` and `Option` produce a `BevyError` with stacked context (prelude). This replaces `ok_or(...)` at the system boundary. | [R] "Bevy Error Context Messages"; [D] `prelude::ContextExt` |
| BV-ERR-17 | errors.md | **No example change needed.** `RenderError::source` is now `Option<WgpuErrorSource>` because `WgpuWrapper` was removed. The example reads only `ty` and `description`. The "0.19 default" wording is a version literal. | [G] "WgpuWrapper has been removed"; [S] `crates/bevy_render/src/error_handler.rs` L94-98 |
| BV-CAR-09 | cargo.md | **SILENT interplay.** `overflow-checks = true` exists so that release traps where debug traps. Under a logging release handler (BV-ERR-05's example), the trap is now caught, logged and stepped past. The system has stopped mid-body, so any writes made before the panic remain (reasoning, not sourced). The rule needs a pointer to the BV-ERR-05 fix. | [R], [PR24240] |
| BV-STA-20 | state.md | **BREAK (deprecated).** `NextState::set_if_neq` → `NextState::set_if_different`. Also `PendingIfNeq` → `PendingIfDifferent`, `CommandsStatesExt::set_state_if_neq` → `set_state_if_different`, and `ReflectFreelyMutableState(Fns)::set_next_state_if_neq` → `…_if_different`. Deprecated wrappers still compile with a warning. Title, statement and Check all name `set_if_neq`. | [G] "NextState::set_if_neq renamed to set_if_different" |
| BV-STA-19 | state.md (L696-707) | **BREAK (deprecated).** The example `next.as_mut().set_if_neq(Screen::Playing)` becomes `next.set_if_different(Screen::Playing)`. The "`as_mut` is load-bearing" comment describes exactly the name clash 0.20 removed, so it should be deleted. | [G] |
| BV-STA-10 | state.md | **STALE.** `SettingsGroup` is now bounded by `Resource + Reflect + Default`, so a missing derive is a compile error. A missing `#[reflect(Default)]` is now a logged error, where the rule says "invisible to the loader". The bullet about the 0.19 release notes naming the API wrong is history now. | [G] "bevy_settings errors on useless SettingsGroups"; [S] `crates/bevy_settings/src/lib.rs` L195, L520 |
| BV-ECS-22 | ecs.md | **BREAK + SILENT.** `iter_many`, `iter_many_mut`, `iter_many_unique(_mut)` and the sorted and `par_` variants now yield `Result<Item, QueryEntityError>`. Most uses fail to compile. `.count()`, `.next().is_some()` and `for _ in` keep compiling and now count ids that do not match. "fetches exactly those" becomes `query.iter_many(ids).matched()`. | [G] "Query iterators from 'many' entities…"; [S] `crates/bevy_ecs/src/query/iter.rs` L1620, L2231 |
| BV-ECS-32 | ecs.md | **STALE.** `&mut World` is now itself a `SystemParam`, may appear anywhere in the parameter list, and exclusivity is "tracked at runtime, rather than compile time". `ExclusiveSystemParam`, `ExclusiveFunctionSystem` and `ExclusiveMarker` are gone, and `System::is_exclusive()` moved to `SystemAccess`. The Check ("name what makes `SystemParam`s insufficient") now reads ambiguously. A param conflict that used to be a compile error is now a runtime one. | [G] "Exclusive function systems have been unified…" |
| BV-ECS-27 / BV-ECS-29 | ecs.md | **NEW (optional).** `#[component(summary_tick)]` keeps a per-column change tick, so `Changed<T>` on a rarely-written component can skip whole columns. | [R] "Per-Column Change Ticks" |
| BV-ECS-10 | ecs.md | **Pre-existing wrong lint name.** It cites `bevy_lint`'s `missing_trait_for_unit_struct`. The lints are `bevy::missing_default`, `bevy::missing_clone` and `bevy::missing_copy` (restriction); `missing_trait_for_unit_struct` is only the pass name. | [BL] `bevy_lint/src/lints/restriction/missing_trait_for_unit_struct.rs` and `mod.rs` @ lint-v0.6.0 |
| BV-EVT-13 | events.md (L379, L401, L405) | **BREAK.** The `B: Bundle` moved off `On`: `On<Add, Enemy>` → `On<Add<Enemy>>` and `On<Remove, Enemy>` → `On<Remove<Enemy>>`. `Add<B>` has no default, so a bare `On<Add>` (dynamic components) is now `On<Add<()>>`. | [G] "Moved Observer events B Bundle generic…"; [S] `crates/bevy_ecs/src/lifecycle.rs` L352-463 |
| BV-EVT-14 | events.md | **BREAK + pre-existing error.** "the type is `On<Add, T>`" becomes `On<Add<T>>`. The list `Add, Insert, Replace, Remove, Despawn` is wrong already in 0.19: `Replace` was renamed `Discard` (and `on_replace` → `on_discard`) in 0.19, and neither 0.19.1 nor 0.20.0 has `Replace` [D]. The Check could add `OnReplace` → `Discard`. | [G], [G18] L1728, [D] |
| BV-EVT-17 | events.md | **No break.** Observer `run_if` survives the generic change (`ObserverWithCondition<E: EventPattern, M, S>::run_if`). "in 0.19" is a version literal. | [S] `crates/bevy_ecs/src/observer/condition.rs` L60-97 |
| BV-TST-11 | testing.md (L507) | **BREAK.** The example's `On<Remove, Enemy>` → `On<Remove<Enemy>>`. | [G] |
| BV-TST-15 | testing.md | **NEW.** `ScheduleBuildSettings::shuffle_seed` (requires the `debug` feature, which is in bevy's `dev` collection) randomises the order of ambiguous systems. It is the dynamic check for "ordering assumed, not configured". Anyone constructing `ScheduleBuildSettings` field by field must add the field (BREAK). | [R] "Schedule Randomization", [G] "ScheduleBuildSettings now includes a shuffle_seed field" |
| BV-SCH-23 | scheduling.md | **NEW + wording.** Same `shuffle_seed` tool. The release notes describe unordered conflicting systems as running "deterministically, but arbitrarily", which is not quite the rule's "different output … on a different run". | [R] |
| BV-SCH-15 | scheduling.md | **NEW + SILENT (engine side).** `chain_weak()`, `before_weak()` and `after_weak()` keep an order only between systems that actually conflict. 0.20 converted the engine's own set chains to weak ones: the `Render`, `RenderGraph`, `Core2d`/`Core3d` and `ExtractSchedule` sets, and **`PostUpdate`'s `UiSystems`**. A game system put in one of those sets that relied on hidden ordering (interior mutability, channels, `NonSend`, atomics) is no longer ordered. | [R] "Weak System Ordering", [G] "Several built-in schedules now order their system sets weakly" |
| BV-SCH-24 | scheduling.md | **STALE.** "In 0.19 this is `Schedule::set_executor`" is a version literal; the API is unchanged. | — |
| BV-ARC-05 | architecture.md | **BREAK (version).** Bevy 0.20 moves `glam` 0.32.0 → 0.33.2. A domain crate that names `glam` directly, as this rule tells it to, must move with it or `Vec2` stops unifying at the crossing point. The same type-mismatch failure that BV-CAR-05 describes for Bevy also applies here. | [S] `crates/bevy_math/Cargo.toml` @ v0.19.1 vs v0.20.0 |
| BV-ARC-06 / BV-CAR-01 | architecture.md, cargo.md | **STALE (strengthens).** New subcrates (`bevy_shape` and `bevy_curve`, split from `bevy_math`; `bevy_extract`; `bevy_camera_controller`) are more churn for anyone naming subcrates. `bevy_math::primitives::*`, `Bounded2d`/`3d` etc. are now `bevy_shape`, and `bevy_math::curve` / `cubic_splines` / `Curve` are now `bevy_curve`. The `bevy::prelude` path is unchanged. | [G] "bevy_shape split out…", "bevy_curve split out…"; [R] |
| BV-CAR-02 | cargo.md | **STALE.** "Bevy has 172 features in 0.19" becomes 177 in 0.20.0. Collection definitions are unchanged (see headline), so the asset's `["2d","ui","audio"]` and the harness's `["std","2d_api","3d_api","ui_api","scene"]` stay valid. | [S] `Cargo.toml` `[features]` diff |
| BV-CAR-03 | cargo.md | **STALE (measurement).** "289 crates here against 311 with the `2d` collection, resolved against 0.19.1" must be re-measured against 0.20.0. Every feature in the hand-picked example still exists. **UNCONFIRMED:** the new counts (not measured; no cargo run). The sprite backend now runs through `Mesh2d`/`Material2d`, so the `bevy_sprite_render` closure may differ. | [S], [G] "Migrate Sprite to use Mesh2d + SpriteMaterial" |
| BV-CAR-04 | cargo.md | **STALE.** `bevy = "=0.19.1"` → `"=0.20.0"`, and `"0.19"` → `"0.20"`. | [C] |
| BV-CAR-05 | cargo.md | **STALE.** The Why's example (`Handle<Image>` from 0.18 vs 0.19's) is a version literal. | — |
| BV-CAR-11 | cargo.md | **NEW + SILENT (runtime panic).** `RenderDebugOverlayPlugin` is now in `DefaultPlugins` whenever the new `render_dev_tools` feature is on. That feature is in bevy's `dev` collection. It is disabled at runtime by default, with keybindings in `RenderDebugOverlayKeybindings`. A game that adds the plugin itself (the rule's advice) and also turns on `bevy/dev` or `bevy/render_dev_tools` adds it twice, and the plugin does not override `is_unique`, so `add_plugins` panics. The guide does not state this; it is source-derived. | [G] "RenderDebugOverlay added to default plugins…"; [S] `crates/bevy_internal/src/default_plugins.rs` L94-95, `crates/bevy_dev_tools/src/render_debug.rs` L50-72 |
| BV-CAR-17 | cargo.md | **STALE.** "its version tracks the engine's" cannot be met: no `bevy_lint` release or `main` commit supports Bevy 0.19 or 0.20. See the bevy_lint section. | [BL], [BLC] |
| BV-UI-06 | ui-render.md (L286-340) | **BREAK.** `Pointer<Click>` → `PointerClick`, and `click.event.button` → `click.button`, because the fields are now flat and there is no `Deref`. The prelude `Button` (`bevy::ui::widget::Button`) is `#[deprecated(since = "0.20.0", note = "Use ui_widgets::Button.")]`. `Interaction`, the rule's foil, is deprecated in favour of `picking::hover::Hovered` + `ui::Pressed`. `bevy::ui_widgets::Button` is not in the prelude; it emits `Activate { entity }` via `ButtonPlugin` / `UiWidgetsPlugins`, which is the natural 0.20 form of this rule. | [G] "Flat pointer events", "ui::widgets::Button and ui::Interaction are deprecated"; [S] `crates/bevy_picking/src/events.rs` L316-365, `crates/bevy_ui/src/lib.rs` prelude, `crates/bevy_ui/src/widget/button.rs` L24, `crates/bevy_ui/src/focus.rs` L61, `crates/bevy_ui_widgets/src/button.rs` |
| BV-UI-08 | ui-render.md (L366-445) | **SILENT + BREAK.** `EditableText` on its own no longer works as a widget: it compiles, spawns, and ignores the keyboard. Spawn `bevy::ui_widgets::TextInput`, which `#[require(EditableText, …)]`. `EditableTextInputPlugin` is now `TextInputPlugin` and is part of `UiWidgetsPlugins`; this rename is **not in the guide** (source-confirmed). Also: `TextScroll` → `EditableText::viewport`, `scroll_editable_text` removed, and Escape now clears `InputFocus` and propagates to ancestors and the window. `EditableText` still derives neither `Debug` nor `Reflect`, and `queue_edit`, `pending_edits` and `EditableTextSystems` are unchanged. | [G] "EditableText and TextInput are now separate components", "TextScroll replaced…", "Escape in a text input releases focus…"; [S] `crates/bevy_ui_widgets/src/text_input.rs` L70-73, L763; `crates/bevy_text/src/editing.rs` L99-126; [D] |
| BV-UI-09 | ui-render.md (L452-500) | **BREAK (deprecation warnings).** The `bsn!` example's `Children [ (Choice Text("Play")), (Choice Text("Quit")), ]` triggers the macro's `DEPRECATED_PARENTHESES` / `DEPRECATED_COMMAS` warnings. 0.20 form: `Children [ Choice Text("Play") -- Choice Text("Quit") ]`. The grammar prose is stale in four places: scene references need `@`, `{expr}` → `@{expr}`, `template_value` is deprecated, and enum variants need every field. Prefer `bsn_list! {}`. **NEW:** an `On<Ready>` observer fires once the scene's whole subtree has spawned. "ergonomics not yet settled" softens: the notes say the syntax "should largely be nailed down". | [G] "BSN syntax improvements"; [R]; [S] `crates/bevy_scene/macros/src/bsn/codegen.rs` L230-235, L855-858, L963 |
| BV-UI-07 | ui-render.md | **STALE.** "Buttons, checkboxes, radio buttons, sliders and scrollbars" and the Check "one of the five". 0.20 `bevy_ui_widgets` also has tabs (`TabList`/`Tab`), list box, menu, dialog, modal, popover and text input. | [R] "Headless Tab Widgets"; [S] `crates/bevy_ui_widgets/src/lib.rs` L66-110 |
| BV-UI-02 | ui-render.md | **NEW.** `Val::Em` and `Val::Rem` (`em()`, `rem()`), resolved against the `EmSize` component and the `RemSize` resource. `Node` now requires `EmSize`. This is the unit for "should scale with the text size". | [G] "Val::Em and Val::Rem"; [R] |
| BV-UI-04 | ui-render.md | **SILENT (conditional).** `TextFont::default()` font size is now `FontSize::Rem(1.)` (was `Px(20.)`). It renders the same until `RemSize` changes, then text left at the default scales. | [G] "TextFont::default() font size is now FontSize::Rem(1.)" |
| BV-UI-12 / BV-UI-20 | ui-render.md | **SILENT (visual).** `Tonemapping::None` is now a full passthrough: no `ColorGrading`, no `DebandDither`, negatives not clamped. Use `Tonemapping::Linear` for "no curve". `Camera2d` now defaults to `Tonemapping::Linear`, and a `Camera2d` with `Hdr` now runs the tonemapping pass. `ScreenSpaceTransmission` is no longer required by `Camera3d`, so transmissive materials render differently unless it is added back. | [G] "Tonemapping::None is now a full passthrough", "Opt-in ScreenSpaceTransmission" |
| BV-UI-17 / BV-UI-18 | ui-render.md | **NEW + BREAK (shaders).** A sprite can now take a custom shader (`SpriteMaterial` + `MaterialExtension2d`), and `ExtendedMaterial2d` exists. Shaders are now WESL: preprocessor-dialect `.wgsl` must become `.wesl` with `import …;`, `@if(...)` and `constants::MATERIAL_BIND_GROUP`, and module paths change (`bevy_pbr::mesh_view_bindings` → `bevy_pbr::render::mesh_view_bindings`). The `shader_format_wesl` / `shader_format_glsl` features and GLSL support are gone. BV-UI-18's Why says "WGSL uniform block". | [R] "Sprite Materials", "2D Extended Materials", "WESL Shaders"; [G] "WESL shaders" |

Minor ones that need no rule edit, listed so nobody re-checks them:

- **Sprite draw order** for sprites at equal Z may change (new `Mesh2d` backend) [G].
- **`LinearRgba::with_luminance`** no longer clamps (BV-UI-11 territory) [G].
- **Stacking with mixed `Hdr`**: a camera stack that mixes `Hdr` on one target now composites instead of
  overwriting (BV-UI-13's example has no `Hdr`) [G].
- **Asset processing**: JPEG joins PNG in the default compressed-image processor, and the
  `compressed_image_saver` feature now means a different (BCn/ASTC) backend; the old behaviour is
  `compressed_image_saver_universal` [G].
- **`DespawnOnExit` / `DespawnOnEnter`** now batch through the new `Commands::despawn_all::<F>()`. That is
  free speed for BV-STA-18, with no change [R; S `crates/bevy_ecs/src/system/commands/mod.rs` L483].

SKILL.md edits that are not single rules:

- **Version literals.**
  - The description line (`Bevy 0.19`, "0.15 through 0.19", the rule count).
  - The H1 `Bevy Style — 0.19`.
  - "Target: Bevy 0.19 (0.19.1…)".
  - The `// verified` marker definition ("compiles against Bevy 0.19.1").
  - §2's title.
  - §5 item 2 ("a 0.19 API").
- **§3, row RS-CAR-24.** "Bevy's feature graph has 172 entries" becomes 177.
- **§5 item 2.** "`Trigger`, `EventReader`, `Parent` and `*Bundle` are the usual four". Add `Pointer<…>` and
  `On<Add, T>`, which are now the commonest stale 0.19 spellings.
- **BV-CORE-19.** "make it panic in debug and log in release" is exactly the configuration that swallows
  panics in 0.20 (see BV-ERR-05).
- **BV-CORE-08.** `Mut::set_if_neq` is unchanged. Only `NextState`'s method was renamed [G].

Pre-existing inaccuracies (not 0.20 changes; found while verifying):

1. **BV-EVT-14 `Replace`.** It should be `Discard` since 0.19 [G18 L1728] [D].
2. **`bevy_ui::Pressed` "in the prelude".** migration.md L325-327 says so, but `Pressed` is in `bevy::ui`
   and was in neither the 0.19.1 nor the 0.20.0 prelude [D] [S `crates/bevy_ui/src/lib.rs`].
3. **BV-ECS-10's lint name.** It cites `missing_trait_for_unit_struct`, which is not a lint; see the row
   above.
4. **BV-MIG-05's Check greps `TextSection`.** Since 0.19 `bevy::text::TextSection` is a live trait (0.19
   consolidated `TextRoot`, `TextSpanAccess` and `TextSpanComponent` into it), so a hit is not proof of
   stale code [D] [0.18→0.19 guide L413].
5. **BV-ERR-09 credits `panicking_methods` with the `World` rows.** The v0.6.0 list is written against
   0.18 names (`non_send_resource`, …), so it does not see `World::non_send` (0.19+) [BL
   `panicking_methods.rs` L233-242].
6. **The README's count of literal `rg` Checks.** README.md L163-166 says "fifteen … thirteen over the
   APIs Bevy removed between 0.15 and 0.19". A literal count today finds **16**: 12 in migration.md, 2 in
   events.md, 1 in ecs.md, 1 in architecture.md. The README's version and count both change once 0.20
   rules are added.

---

## §2 changes

### §2.1, "change behaviour without changing whether it compiles"

The existing three are all still true in 0.20.

1. **Same-state `set` re-enters.** Unchanged, but the escape hatch is renamed: "`set_if_neq` is the old
   behaviour" becomes "`set_if_different` is the old behaviour" [G]. `set_if_neq` still compiles in 0.20,
   with a deprecation warning.
2. **`Ref<T>` clone.** Unchanged.
3. **`Resource` is a `Component`.** Unchanged.

Proposed 0.20 additions, most consequential first:

| # | Trap | Why it belongs in §2.1 | Source |
|---|---|---|---|
| A | **The fallback error handler now receives panics.** A handler that logs (the release half of BV-ERR-05 / BV-CORE-19) turns every panic in a system, observer or command into a log line and a running app, with whatever that system had already written. That includes overflow traps (BV-CAR-09), index panics and engine panics. To keep panics fatal, re-panic when the error carries a panic payload (`BevyError::take_payload`) or has `Severity::Panic`. | It compiles and changes crash semantics in every project that followed this standard's own advice | [R], [PR24240], [S] `handler.rs` |
| B | **`EditableText` alone is no longer a text field.** It compiles, spawns, and accepts no input. Spawn `TextInput`, which requires `EditableText`, and add `TextInputPlugin` (formerly `EditableTextInputPlugin`). | The skill's own BV-UI-08 example is exactly this | [G], [S] |
| C | **`iter_many` yields `Result`.** `.count()`, `.next().is_some()` and `for _ in` keep compiling and now include ids that do not match. Use `.matched()` for the old meaning. | It is a counting change that type inference hides | [G] |
| D | **The engine's own set chains are weak.** In `PostUpdate`'s `UiSystems` and the render schedules, systems with no ECS-visible conflict are no longer ordered. A system that joined one of those sets and relied on hidden ordering (channels, atomics, interior mutability, `NonSend`) can now race. | Silent and order-dependent, the way the 0.18 state change was | [G], [R] |
| E | **Rendering defaults.** `Tonemapping::None` is a full passthrough, `Camera2d` defaults to `Linear`, `ScreenSpaceTransmission` is opt-in, and equal-Z sprite order may change. | A candidate for §2.1, or a single line pointing at ui-render.md, because visual regressions are the hardest to bisect | [G] |
| F | **Escape in a focused text field now propagates.** It blurs the field and is no longer consumed, so an ancestor or window `Escape` observer runs on the same press. | Lower priority | [G] |

Also candidates, manifest-level traps in the spirit of BV-MIG-16:

- **`compressed_image_saver`** keeps its name and now selects a different compressor [G].
- **The `bevy/dev` collection** now adds `RenderDebugOverlayPlugin` to `DefaultPlugins`, so a hand-added
  copy panics as a duplicate [S].

### §2.2, engine features that replace hand-rolled code

Existing rows to amend:

| Row | Change | Source |
|---|---|---|
| `EditableText` | becomes "`TextInput` (with `EditableText`)", since 0.20 | [G] |
| `bsn!` | still valid; the `Since` stays 0.19, but the note must use 0.20 syntax | [G] |
| `#[derive(SettingsGroup)]` | now also requires `Reflect + Default` | [G] |

The other existing rows were verified present in 0.20.0: `commands.delayed()` [S `crates/bevy_time/src/delayed_commands.rs`],
`DiagnosticsOverlayPlugin` [D], `Gizmos::text` / `text_2d` [S `crates/bevy_gizmos/src/stroke_text.rs`
L211, L295], `Query::contiguous_iter` [S `query.rs` L1509], and observer `.run_if` [S].

New rows (Since 0.20):

| Reach for this | Not this | Source |
|---|---|---|
| `commands.despawn_all::<F>()` / `despawn_all_where` | a query-and-despawn loop | [R] "Faster Bulk Despawning"; [S] `commands/mod.rs` L483, L505 |
| `.context("…")` / `.with_context(…)` (`ContextExt`, prelude) | `ok_or_else(|| …)` / `map_err` boilerplate at the system boundary | [R] |
| an `On<Ready>` observer on a scene entity | polling for a spawned scene's children | [R] "Ready Event"; [D] `scene::Ready` |
| `ScheduleBuildSettings::shuffle_seed` (`debug` feature) | trusting the order of ambiguous systems | [R] |
| `chain_weak()` / `before_weak()` / `after_weak()` | `chain()` where only data dependencies matter | [R] |
| `#[component(summary_tick)]` | a hand-kept "dirty" resource for a rarely-changing component | [R] |
| `Val::Em` / `Val::Rem` with `RemSize` | multiplying `px` by a scale factor for text-relative UI | [R] |
| `bevy::ui_widgets::Button` + `Activate`, or `Hovered` + `Pressed` | `Interaction` polling (deprecated) | [G] |
| `PanOrbitCamera` (`bevy::camera_controller`, `pan_orbit_camera` feature) | a hand-written editor/CAD camera | [R] |
| `SpriteMaterial` / `ExtendedMaterial2d` | a custom `Mesh2d` quad just to shade a sprite | [R] |
| `TabList` / `Tab` (headless) | hand-built tabs | [R] |
| `FixedNode` | an absolutely-positioned root to escape a parent's layout | [R] |

### §2.3, names that moved

Add:

- `Pointer<Click>` is `PointerClick`, and every `Pointer<X>` is `PointerX`.
- `On<Add, T>` is `On<Add<T>>`.
- `NextState::set_if_neq` is `set_if_different`.
- `EditableTextInputPlugin` is `TextInputPlugin`.
- The prelude `Button` and `Interaction` are deprecated.
- A preprocessor `.wgsl` is a WESL `.wesl`.
- `bevy_math` primitives and curves are `bevy_shape` and `bevy_curve`.

Also fix the pre-existing `Replace` → `Discard`.

---

## Forbidden-API additions (migration.md)

**Conventions to keep.**

- Every right-hand column is the **0.20** spelling. The chapter's intro and BV-MIG-03 say "0.19 spelling"
  and must change.
- `|` for alternation, never `\|`: `checks/dialect.py` rejects `\|`.
- Every pattern runs against the skill's own Rust examples (`checks/selfapply.py`), so it must not match
  compliant 0.20 code, **including comments in examples**. The BV-UI-06 example has a doc comment naming
  `Query<&Interaction, …>`, which the rewrite has to drop.

### Edits to existing rows

| Rule | Row | 0.20 right-hand side | Source |
|---|---|---|---|
| BV-MIG-04 | `ButtonBundle::default()` | `bevy::ui_widgets::Button` plus `Node` (the prelude `Button` is deprecated) | [G] |
| BV-MIG-05 | `Font::try_from_bytes` | `Font::from_bytes(bytes)`, which no longer takes a family name. Add a row: `FontSource::SansSerif` (and `Serif`, `Monospace`, `Cursive`, `Fantasy`, `SystemUi`, `UiSerif`, `UiSansSerif`, `UiMonospace`, `UiRounded`, `Emoji`, `Math`, `FangSong`) → `FontSource::sans_serif()` etc. / `GenericFontFamily` | [G]; [S] `crates/bevy_text/src/text.rs` FontSource @ v0.19.1 vs v0.20.0 |
| BV-MIG-11 | prose | `On<Add, T>` wording → `On<Add<T>>` | [G] |
| BV-MIG-12 | `SpriteSystem` | the name is right, but in 0.20 it lives only at `bevy::sprite_render::SpriteSystems`; `bevy::sprite::SpriteSystems` is gone | [D] |
| BV-MIG-13 | `Pointer<Pressed>` / `Pointer<Released>` | `PointerPress` / `PointerRelease` (`Pointer<Press>` was the first hop and is gone too) | [G] |
| BV-MIG-16 | — | add that `bsn!` scene references take `@` in 0.20 | [G] |
| BV-MIG-17 | `feathers` widget spawn functions | **0.20 removed `button_bundle`, `checkbox_bundle`, `radio_bundle`, `slider_bundle`, `toggle_switch_bundle`, `color_*_bundle`, `virtual_keyboard_bundle` and `ButtonBundleProps`.** This is not in the guide; it comes from the [D] diff. The replacements are `SceneComponent`s (`FeathersButton` + `FeathersButtonProps`, etc.) used from `bsn!` [S `crates/bevy_feathers/src/controls/button.rs` L66-94]. **UNCONFIRMED:** the exact `bsn!` spelling for a props-taking feathers widget. | [D], [S] |
| BV-MIG-17 | `ShaderStorageBuffer` → `ShaderBuffer` | still right, but `ShaderBuffer`'s API changed again in 0.20: `new(Vec<T>)`, `set_data` and `resize_in_place` removed | [G] |
| BV-MIG-18 | trailing paragraph | lists the silent changes; add the 0.20 ones (panics → handler, `iter_many`, `EditableText`) | — |

### New rules, in a new "0.20" section

**BV-MIG-new-1 [M] Move the bundle off `On` and onto the lifecycle event** [G]

| Removed | Write instead |
|---|---|
| `On<Add, T>`, `On<Insert, T>`, `On<Discard, T>`, `On<Remove, T>`, `On<Despawn, T>` | `On<Add<T>>`, `On<Insert<T>>`, … |
| `On<Add>` (dynamic components with `.with_component(id)`) | `On<Add<()>>` |
| a custom `On<E, B>` | a `PhantomData` wrapper implementing `EventPattern { type Event; type Components }` |
| `IntoObserverSystem<E, B, M, Out>` | `IntoObserverSystem<E, M, Out>` |

Check: `` `rg -n '\bOn<[A-Za-z0-9_:]+\s*,|\bOn<(Add|Insert|Discard|Remove|Despawn)>' src/` ``.
This does not match `On<Add<Enemy>>`, because `<` follows `Add`.

**BV-MIG-new-2 [M] Flatten the pointer events** [G; S `crates/bevy_picking/src/events.rs`]

| Removed | Write instead |
|---|---|
| `Pointer<X>` for X in Over, Out, Enter, Leave, Press, Release, Click, Move, DragStart, Drag, DragEnd, DragEnter, DragOver, DragLeave, DragDrop, Scroll, Cancel | `PointerX` |
| `ev.event.button` | `ev.button` |
| `ev.pointer_id` | `ev.pointer.id` |
| `ev.pointer_location.position` | `ev.pointer.position` (`Vec2`); `ev.pointer.location()` for the `Location` |
| `fn f<E: …>(e: On<Pointer<E>>)` | `fn f<E: PointerEvent>(e: On<E>)` |

Check: `` `rg -n '\bPointer<|pointer_id|pointer_location' src/` ``. `Pointer` is non-generic in 0.20, so any
`Pointer<` is stale.

**BV-MIG-new-3 [M] Replace what 0.20 deprecated** (rustc `deprecated` catches all of these; the `rg` is
for unbuilt code) [G]

| Deprecated | Write instead |
|---|---|
| `NextState::set_if_neq` / `PendingIfNeq` / `set_state_if_neq` / `set_next_state_if_neq` | `set_if_different` / `PendingIfDifferent` / `set_state_if_different` / `set_next_state_if_different` |
| `Interaction` | `Hovered` + `Pressed` |
| the prelude `Button` (`bevy::ui::widget::Button`) | `bevy::ui_widgets::Button` |
| `template_value(x)` | `x` |
| `FilteredResources` (+ `Mut`, `*Builder`, `*ParamBuilder`) | `QueryParamBuilder` + `Query<FilteredEntityRef>` + `IsResource` |
| `DeferredWorld::query(&mut state)` | `state.query_mut(world)` |
| `TypeIdMap` / `TypeIdMapEntry` | `TypeIdHashMap` / `TypeIdIndexMap` (and their entry types) |
| `AssetId::invalid()` / `AssetId::INVALID_UUID` | `Option<AssetId<_>>` |
| `DynamicEnum::from(_ref)` | `try_from(_ref)` |
| `Access::try_reads_and_writes` | `reads()` |
| `,` and `()` between entities in `bsn!` | `--` |

Check: `` `rg -n 'set_state_if_neq|PendingIfNeq|set_next_state_if_neq|\.as_mut\(\)\.set_if_neq|\bInteraction\b|template_value|FilteredResources|\bTypeIdMap\b|AssetId::invalid|INVALID_UUID|try_reads_and_writes' src/` ``.

Prose to go with it:

- `NextState::set_if_neq` reached through `&mut NextState` is not greppable: `Mut::set_if_neq` keeps its
  name and is correct. Read every `set_if_neq` whose receiver is a `NextState`.
- The deprecated `Button` is not greppable either, because `ui_widgets::Button` has the same name. Read
  the import.

**BV-MIG-new-4 [M] Replace the remaining 0.20 renames and removals** [G unless marked]

| Removed (0.19) | Write instead (0.20) |
|---|---|
| `EditableTextInputPlugin` | `TextInputPlugin` [S; not in G] |
| `EditableText` as the whole widget | `TextInput` (requires `EditableText`) |
| `TextScroll`, `scroll_editable_text` | `EditableText::viewport` (`TextViewport`) |
| `resolve_font_source(&font, fonts)` | `font.font.resolve_font_family(fonts)` |
| `FontSource::SansSerif` etc. | `FontSource::sans_serif()` etc. |
| `MeshTag(x)`, `tag.0` | `MeshTag::new(x)`, `tag.value` |
| `MeshAabb::compute_aabb` | `get_aabb` |
| `CustomAttributes::default().with_attribute(..)` | `CustomAttributesBuilder::new().attribute(..).build()` |
| `BorderRadius { top_left: Val, .. }` | `CornerRadius` fields (`px(10.).into()`) |
| `BorderRadius::resolve_single_corner` | `CornerRadius::resolve` |
| `Val::resolve(scale, base, target)` | adds `em_size, rem_size` |
| `FontSize::eval(vp, f32)` | `FontSize::eval(vp, RemSize(..))` |
| `CalculatedClip` struct | enum `Rects` / `FullyClipped` |
| `TextReader::text/font/color/…` | `TextReader::get` → `TextLayoutItem` |
| `ExclusiveSystemParam`, `ExclusiveFunctionSystem`, `ExclusiveSystemParamFunction`, `ExclusiveMarker` | removed; `&mut World` is a `SystemParam` |
| `System::is_exclusive()` | `SystemAccess::is_exclusive()` |
| a `WorldId` param in an exclusive system | `Local<WorldId>` or `world.id()` |
| `WorldQuery` default methods | implement `init_nested_access` and `update_archetypes` |
| `FromType<T>` / `from_type()` | `CreateTypeData<T>` / `create_type_data(())` |
| `ReflectFromPtr::as_reflect(_mut)` | `ptr_as_reflect(_mut)` |
| `from_ptr(_mut)` | `raw_pointer_cast` |
| `PartialReflect::to_dynamic` → value | `Result` |
| `UntypedHandle::meta_transform` | deleted |
| `Name::from(&str)` (non-`'static`) | `Name::new(s.to_owned())` |
| `Ptr::as_ptr` → `*mut u8` | `*const u8` |
| `UiCameraMapper::current_camera()` → `Entity::PLACEHOLDER` | `Option<Entity>` |
| `ComponentInfo::id()` | keep the `ComponentId` you looked it up by |
| `define_label!(X, INTERNER)` | `define_label!(X,)` |
| `SyncComponent` | `SyncComponent<RenderApp>` |
| `#[derive(ExtractComponent)]` | plus `#[extract_app(RenderApp)]` |
| `TemporaryRenderEntity` | `TemporaryRenderEntity::default()` |
| `UnpreparedBindGroup` / `unprepared_bind_group` | `BindGroupBuilder` / `build_bind_group` |
| `ExtractedWindows` | `Query<&ExtractedWindow>` |
| `SortedCamera::hdr` | `ExtractedCamera::hdr` |
| `WgpuWrapper` | removed |
| `bevy_sprite_render::SpriteMaterial(Plugin)` (old internal) | `SpriteMeshMaterial(Plugin)`. **Note:** a *new, different* public `SpriteMaterial` exists in 0.20, the same same-name trap as `bevy_scene` |
| `bevy_feathers::cursor` | `bevy_picking::cursor` |
| `UpdateNumberInput` trigger | insert `NumberInputValue` |
| `Tonemapping::None` meaning "no curve" | `Tonemapping::Linear` |
| `bevy_math::{curve, cubic_splines, Curve}` | `bevy_curve` |
| `bevy_math::primitives::*`, `Bounded2d`, … | `bevy_shape` |
| `VariantDefaults` derive | removed; enums need `Default + Clone` |
| feature `shader_format_wesl`, `shader_format_glsl` | gone |
| feature `compressed_image_saver` (Basis) | `compressed_image_saver_universal` |
| `bevy_math/curve` | `bevy/bevy_curve` |

Rust Check: `` `rg -n 'EditableTextInputPlugin|TextScroll|scroll_editable_text|resolve_font_source|FontSource::(Serif|SansSerif|Cursive|Fantasy|Monospace|SystemUi|UiSerif|UiSansSerif|UiMonospace|UiRounded|Emoji|Math|FangSong)\b|MeshTag\(|compute_aabb|with_attribute|Exclusive(SystemParam|Marker|FunctionSystem)|\bFromType\b|meta_transform|UnpreparedBindGroup|ExtractedWindows|resolve_single_corner|VariantDefaults|bevy_math::(curve|cubic_splines|primitives)' src/` ``

Shader Check (the corpus is Rust, so this one reports clean there; its target is the asset tree):
`` `rg -n '#import|#ifdef|#define_import_path|#\{' -g '*.wgsl'` ``

Manifest: `shader_format_(wesl|glsl)`, plus reading every `compressed_image_saver`, which kept its name and
changed meaning.

`bevy_math` domain crates: `glam = "0.32"` → `"0.33"` (BV-ARC-05).

**BV-MIG-new-5 [M] Re-read every `iter_many` and every logging error handler** (the "do not show up as
a compile error" section, beside BV-MIG-18) [G, R]

- `iter_many*` items are `Result`; `.matched()` is the old meaning.
- A fallback handler that does not re-panic now swallows panics.
- `EditableText` without `TextInput` is inert.

Its natural Check (`rg -n 'iter_many'`) finds the call, but whether the call is a count is not on the
line. It therefore needs a `not_decisive` entry in `profiles/bevy_style.py`, as BV-MIG-18's `.clone()` has.

**Probe.** All four patterns were run with `rg` against sample lines. Each matches its stale forms and
none matches its 0.20 replacement: `On<Add<Enemy>>`, `PointerClick`, `pointer.id`, `health.set_if_neq(..)`,
`InteractionDisabled`, `FontSource::sans_serif()`, `MeshTag::new`.

Over today's skill, the code hits are all examples this plan rewrites anyway:

- events.md L401, L405
- testing.md L507
- state.md L706
- ui-render.md L299, L336

The remaining hits are prose (migration.md's tables, ui-render.md L288, L367), which is not in the
self-application corpus.

Fixtures are optional (`profile.fires`). If any are declared for a new rule, `checks/sensitivity.py`
requires every alternation-split pattern to hit a fixture and every fixture to be hit.

---

## Assets & profile pins

| File | Line | Now | Becomes | Note |
|---|---|---|---|---|
| `skills/bevy-style/assets/Cargo.toml` | 1 | "a Bevy 0.19 game" | 0.20 | |
| ″ | 11 | `rust-version = "1.98"` | `"1.99"` | Bevy 0.20's own MSRV is 1.97.1 [C], so 1.99 satisfies it |
| ″ | 15 | caret `"0.19"` | `"0.20"` | |
| ″ | 25 | "since 0.19 `audio` is not implied…" | still true in 0.20 ([S] collections unchanged); reword if version-neutral wording is wanted | |
| ″ | 27 | `version = "=0.19.1"` | `"=0.20.0"` | features `["2d","ui","audio"]` unchanged and valid |
| ″ | — | — | optionally add `[workspace.metadata.bevy_lint]` | this is how `bevy_lint` levels are set in a manifest [BLC]. **Pointless until a `bevy_lint` supports 0.20** |
| `skills/bevy-style/assets/ci.yml` | 1 | "a Bevy 0.19 game" | 0.20 | |
| ″ | 89 | `dtolnay/rust-toolchain@1.98` | `@1.99` | must match `rust-version` |
| ″ | 97-115 | bevy-lint job, `if: false`, `nightly-YYYY-MM-DD` | **leave disabled**; no supported nightly exists | see the bevy_lint section |
| ″ | apt line | `libasound2-dev libudev-dev libwayland-dev libxkbcommon-dev` | unchanged | `docs/linux_dependencies.md` is byte-identical between v0.19.1 and v0.20.0 [S] |
| `skills/bevy-style/assets/rust-toolchain.toml` | 17 | `channel = "1.98.0"` | `"1.99.0"` | the header comment's nightly placeholder stays |
| `src/agent_skill/lang/rust.py` | 36 | `rust_version: str = "1.98"` | `"1.99"` | **shared default**: it also sets `RUST_STYLE`'s manifest. rust-style's own assets pin 1.98 too (`skills/rust-style/assets/Cargo.toml:10`, `ci.yml:49`) |
| ″ | 141-142 | `'bevy = { version = "=0.19.1", default-features = false, features = ["std", "2d_api", "3d_api", "ui_api", "scene"] }'` | `"=0.20.0"` | all five features exist in 0.20 with unchanged definitions; `common_api` gains `bevy_curve` [S] |
| ″ | 132-137 | comment: "`bsn!` is the newest surface in 0.19" | 0.20 wording | |
| `src/agent_skill/profiles/bevy_style.py` | — | **no literal version or pin in this file** | — | it is tied to rule IDs, not versions; see below |
| `README.md` | 163-166 | "fifteen … between 0.15 and 0.19" | update count and version | |
| `.cache/target/bevy-style-verify` | — | — | rebuilds on the pin change | |

The profile is tied to rule IDs (and the planned renumbering moves all of these):

- **`fires`.**
  - `BV-ECS-19` has `query.single().unwrap()`. If BV-ECS-19 becomes a lint-table row and loses its `rg`
    Check, this fixture must be deleted: `checks/sensitivity.py` fails "has a fixture but no **Check:**".
  - `BV-EVT-09` has `trigger_targets`, which is still gone in 0.20.
- **`not_decisive` anchors.** Each entry must keep quoting text its rule's Check still says:
  BV-ECS-12 `Vec<Entity>`, BV-ECS-14 `Handle<`, BV-MIG-18 `.clone()`, BV-SCH-09 `just_pressed`, BV-SCH-13
  `configure_sets`, BV-SCH-26 `run_if`, BV-STA-04 `insert_resource`, BV-TST-11 `entities().len()`,
  BV-UI-04 `Text::new`. None of these Checks needs a 0.20 change. Add one for the proposed `iter_many`
  rule.
- **`conventions()`** cites BV-ECS-01, BV-ECS-03, BV-ECS-10, BV-ARC-09 and BV-ARC-10 in messages. These are
  ID-bound only.
- **`checks/controls.py`** seeds edits by literal example text, e.g. events.md `mut damage:
  MessageReader<DamageDealt>`, scheduling.md `struct Velocity(pub Vec3);`, and `BV-SCH-09 [M] Never read
  per-frame input`. None of these texts changes for 0.20; the renumbering will move the last one.

---

## bevy_lint status (as of 2026-10-20)

`bevy_lint` supports neither Bevy 0.19 nor 0.20, in any release or on `main` [BL], [BLC].

**Releases.** The latest is **v0.6.0** (2026-02-01): Bevy 0.18, toolchain `nightly-2026-01-22` (Rust
1.95.0). Running it on Bevy 0.19 errors on `cfg_select`, stabilised in Rust 1.95 [BL issue #832]. There
has been no `bevy_cli` release since `cli-v0.1.0-alpha.2` (2025-09-24).

**`main`.** Version `0.7.0-dev` pins `nightly-2026-04-16` (1.97.0-nightly), its dev-dependency is still
`bevy = "0.18"`, and the compatibility table says 0.18.

**Open PRs**, none merged:

- **#835** "Support Bevy v0.19", against `main`.
- **#925** "bevy v0.20", based on the `bevy-v0.19` branch.
- **#943** "Bump channel", based on `bevy-v0.20`. It moves to **`nightly-2026-05-28`** (Rust 1.98.0) with
  `clippy_utils = "=0.1.98"`, because the current nightly fails with "rustc 1.97.0-nightly is not
  supported … bevy@0.20.0 requires rustc 1.97.1".
- **The nightly 0.20 will need is therefore `nightly-2026-05-28` — UNCONFIRMED** until #943 merges and a
  release ships.

**Lint names and groups at v0.6.0** [BL source]. A lint runs at its group's default level unless
configured otherwise.

| Group (default) | Lints |
|---|---|
| suspicious (warn) | `bevy::insert_message_resource`, `bevy::iter_current_update_messages`, `bevy::unit_in_bundle` |
| style (warn) | `bevy::unconventional_naming` (`Plugin`/`SystemSet` suffix only) |
| pedantic (allow) | `bevy::borrowed_reborrowable`, `bevy::main_return_without_appexit` |
| restriction (allow) | `bevy::missing_reflect`, `bevy::missing_default`, `bevy::missing_clone`, `bevy::missing_copy`, `bevy::panicking_methods` (`World` methods only, 0.18 names), `bevy::update_schedule`, `bevy::fixed_update_schedule` |
| nursery (allow) | `bevy::camera_modification_in_fixed_update` (only `With<Camera>`), `bevy::duplicate_bevy_dependencies` (facade only; skips version ranges), `bevy::zst_query` (false positives on `Has<T>`/`AnyOf`) |
| correctness, complexity, performance | empty |

**Configuration.** `[workspace.metadata.bevy_lint]` / `[package.metadata.bevy_lint]` in Cargo.toml, or
`#![warn(bevy::…)]` with `register_tool` [BLC].

**Consequences for the skill.**

- BV-CAR-17's "its version tracks the engine's" is unsatisfiable today.
- Every rule below whose lint is `bevy::…` is backed by a tool that cannot run on the target version.
- The ci.yml job must stay `if: false`.
- BV-ARC-10, BV-ARC-17, BV-CAR-05, BV-ECS-09, BV-ECS-10, BV-ECS-17, BV-ERR-09, BV-EVT-04, BV-EVT-05 and
  BV-SCH-04 cite these lints. The citations are accurate as lint *names*, apart from BV-ECS-10's, but none
  of these lints can run against 0.19/0.20 code.

---

## Lint classification

How to read the table:

- The criterion matches the openspec proposal: **LINT** means the rule's whole content is what the lint
  enforces, **PARTIAL** means the rule says materially more, and **NONE** (not listed) means no tool
  enforces it.
- Clippy names were verified with `cargo clippy --explain` on clippy 0.1.99 [CL], groups from clippy
  source at `rust-1.99.0` [CL], and rustc names with `rustc -W help` [RC].
- `bevy::` lints are from **v0.6.0, which supports Bevy 0.18 only**. No version supports 0.19/0.20.
- **"Enabled in assets?"** means active under the shipped `skills/bevy-style/assets/Cargo.toml` plus
  `ci.yml`. No `bevy::` lint is enabled: there is no `[workspace.metadata.bevy_lint]` table and the CI job
  is `if: false`.

| ID | LINT/PARTIAL | lint | enabled in assets? |
|---|---|---|---|
| BV-ECS-09 Never spawn a unit | LINT | `bevy::unit_in_bundle` (suspicious) | No |
| BV-ECS-17 Marker in the filter, not the data | LINT | `bevy::zst_query` (nursery; false positives on `Has<T>`) | No |
| BV-ECS-19 Treat `single` as fallible | LINT | `clippy::unwrap_used` + `clippy::expect_used` (restriction) | **Yes**, both `deny`. The profile's `fires["BV-ECS-19"]` fixture must go if the `rg` Check goes |
| BV-ERR-07 Never unwrap a query (pointer to BV-ECS-19) | LINT | same as BV-ECS-19 | **Yes** |
| BV-ERR-08 Never index a collection an entity count can reach | LINT | `clippy::indexing_slicing` (restriction; stricter than the rule) | **Yes**, `deny`, and the table comment already cites BV-ERR-08 |
| BV-ERR-11 Do not discard a `Result` with `let _ =` | LINT | `clippy::let_underscore_must_use` (restriction). The required "reason" is `#[expect(…, reason = "…")]`, which `clippy::allow_attributes_without_reason` (warn, enabled) forces | **No**; it would need `let_underscore_must_use = "deny"` added |
| BV-ERR-14 Report through `tracing`, never `println!` | LINT | `clippy::print_stdout` + `clippy::print_stderr` + `clippy::dbg_macro` (all restriction) | **Partly**: `dbg_macro` is `deny` (comment cites BV-ERR-14); `print_stdout` and `print_stderr` are absent. The rule's build.rs/CLI exemption becomes `#[expect]` with a reason |
| BV-EVT-04 Register a message with `add_message` | LINT | `bevy::insert_message_resource` (suspicious) | No |
| BV-EVT-05 Read messages through a `MessageReader` | LINT | `bevy::iter_current_update_messages` (suspicious) | No |
| BV-SCH-10 Group system parameters past seven | LINT (borderline: the rule also says to name the group for its subject) | `clippy::too_many_arguments` (complexity; default threshold 7 means it fires at 8, the rule's "more than seven") | **Yes**: on by default, BV-CAR-14 forbids allowing it, CI `-D warnings` |
| BV-MIG-02 Treat a deprecated API as removed | LINT | rustc `deprecated` (warn by default) | **Yes**: on by default and fatal under ci.yml's `-D warnings` / `CARGO_BUILD_WARNINGS: deny`; not listed in the `[lints]` table |
| BV-ARC-10 `*Plugin` / `*Systems` suffix | PARTIAL | `bevy::unconventional_naming` (style). It does not check the reverse ("a type ending in `Plugin` that is not one") | No |
| BV-ARC-17 Return `AppExit` from `main` | PARTIAL (near-LINT) | `bevy::main_return_without_appexit` (pedantic). It skips any non-unit `main`, so returning a fabricated `AppExit` passes | No |
| BV-ECS-03 Derive `Debug` and `Reflect` on every component | PARTIAL | rustc `missing_debug_implementations` (only types reachable from the public API) + `bevy::missing_reflect` (restriction). `#[reflect(Component)]` is not linted (the harness's `conventions()` checks it in examples) | `missing_debug_implementations` **yes** (`deny`); `missing_reflect` no |
| BV-ECS-10 Marker derives | PARTIAL | `bevy::missing_default`, `bevy::missing_clone`, `bevy::missing_copy` (restriction) + `missing_debug_implementations` + `bevy::missing_reflect`. The skill names a non-lint, `missing_trait_for_unit_struct` | rustc one only |
| BV-ECS-20 Iterate a query with `for` | PARTIAL | `clippy::needless_for_each` (pedantic) covers `.for_each(`; `.filter(` on a query iterator is unlinted | **Yes** (`pedantic = warn`) |
| BV-ECS-21 Name a query type | PARTIAL | `clippy::type_complexity` (complexity; threshold 250, not "two lines") | **Yes** (default; kept by BV-CAR-14) |
| BV-ERR-01 Return `Result` from a fallible system | PARTIAL | `clippy::unwrap_used`, `expect_used`, `panic`, `todo`, `unimplemented`. The "return `Result` and `?`" half is unlinted | **Yes**, all `deny` |
| BV-ERR-09 Prefer the non-panicking half | PARTIAL | `bevy::panicking_methods` (restriction; `World` only, 0.18 names) + `unwrap_used`/`expect_used` for the "unwrapped" rows | clippy yes; bevy no |
| BV-ERR-10 Never panic to report bad content | PARTIAL | `clippy::panic` (+ `unwrap_used`, `expect_used`) | **Yes** |
| BV-ERR-13 Propagate from an observer like a system | PARTIAL | `clippy::unwrap_used`, `expect_used` | **Yes** |
| BV-ERR-16 Exit with `AppExit::error` | PARTIAL | `clippy::panic` forbids the `panic!` it replaces; the `AppExit::error()` half is unlinted | **Yes** |
| BV-SCH-01 Simulate in `FixedUpdate`, present in `Update` | PARTIAL | `bevy::update_schedule` / `bevy::fixed_update_schedule` (restriction; per-module opt-in) | No |
| BV-SCH-04 Never move a camera from `FixedUpdate` | PARTIAL | `bevy::camera_modification_in_fixed_update` (nursery; only `With<Camera>`) | No |
| BV-CAR-05 One Bevy version | PARTIAL | `bevy::duplicate_bevy_dependencies` (nursery; `bevy` facade only, skips ranges) + `clippy::multiple_crate_versions` (cargo group; every crate) | No (ci.yml uses a `cargo tree --duplicates` grep instead) |

**Totals.** 11 LINT, 14 PARTIAL.

- **LINT and fully enabled by shipped config:** BV-ECS-19, BV-ERR-07, BV-ERR-08, BV-SCH-10, BV-MIG-02.
- **LINT, half-enabled:** BV-ERR-14.
- **LINT whose lint is not enabled:** BV-ERR-11 needs one clippy entry. BV-ECS-09, BV-ECS-17, BV-EVT-04
  and BV-EVT-05 are `bevy_lint`-only, so they cannot be shipped-config rows until `bevy_lint` supports
  0.20.

**Core-rule mirrors** in SKILL.md §4 follow their owners:

| Core rule | Owner |
|---|---|
| BV-CORE-07 | BV-ECS-17 (LINT) |
| BV-CORE-09 | BV-ECS-21 (PARTIAL) and BV-SCH-10 (LINT) |
| BV-CORE-17 | BV-EVT-04 (LINT) |
| BV-CORE-18 | BV-ERR-01 (PARTIAL) |
| BV-CORE-20 | BV-ERR-09 (PARTIAL) |
| BV-CORE-21 | BV-ARC-17 (PARTIAL) |

**Not lints, but compiler-enforced.** Removed-API rules fail with a type or name error rather than a lint.
These are BV-STA-01 / BV-MIG-15 (0.19 derive conflict), BV-EVT-09, BV-EVT-14, BV-ERR-12, BV-UI-12,
BV-ECS-14, and the BV-MIG-04…17 tables. They are NONE under the proposal's definition.

**Deliberately not listed.** BV-CAR-12, BV-CAR-13, BV-CAR-14, BV-CAR-15 and BV-CAR-16 are rules *about*
the lint table. They are enforced by `checks/lints.py` and `tests/test_fmt.py`, not by a lint.

---

## UNCONFIRMED

- **bevy_lint's nightly for 0.20.** `nightly-2026-05-28` is what PR #943 proposes; it is unmerged and
  unreleased.
- **The `bsn!` spelling for the 0.20 feathers widgets** that replace `button_bundle` etc.
  `FeathersButton` + `FeathersButtonProps` exist as `SceneComponent`s; the call form is not verified.
- **BV-CAR-03's re-measured crate counts for 0.20.0.** Not measured; no cargo run was allowed.
- **Whether Bevy 0.20 changes the BV-CAR-12/13 measurements** ("fourteen warnings in one five-system
  plugin"), and whether clippy 1.99's pedantic group fires anything new on Bevy code. Both need a build.
- **Partial state after a caught panic.** The claim that writes made before the panic persist is
  reasoning from the executor design, not a sourced statement. [PR24240] lists "still apply the remaining
  commands in the buffer?" as future work.
- **Whether `print_stdout` skips `build.rs` automatically.** The skill's exemption assumes it may need an
  `#[expect]`.
