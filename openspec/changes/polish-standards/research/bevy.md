# bevy-style: duplicate rules and newer APIs

Read: `SKILL.md`, all 11 chapters, the review protocol and `assets/Cargo.toml`, against rust-style's
rules and its "Decided by tools" tables. Each API claim was checked against the 0.20.0 crates, with
0.19.1 to date an arrival, and against the 0.20 release notes and migration guide. `$REG` is
`~/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f`.

## A. Duplicates

### A.1 Within bevy-style

| # | Rules | Owner | Absorb from the other |
|---|---|---|---|
| 1 | BV-MIG-19 ↔ BV-ECS-21 (para 2, Check), BV-ERR-05, BV-VIEW-08, SKILL §2.1 items 4–6. Each MIG-19 bullet repeats a topic rule; ECS-21 copies bullet 1. | The three topic rules | MIG-19's combined grep becomes a "silent changes" list in migration.md, like the paragraph under MIG-18. |
| 2 | BV-ARCH-11 ↔ BV-ARCH-14 ↔ BV-STATE-03 (registration lives with the definition). | ARCH-11, which has the example | ARCH-14: the central `register_everything` anti-pattern, and a forgotten registration shows up as an absence at run time. STATE-03: an uninitialised resource fails at first access, naming the type but not the plugin. |
| 3 | BV-SCHED-17 ↔ BV-SCHED-21 ("the commonest case of SCHED-17") ↔ BV-EVENT-17 ("SCHED-17 applied to observers"), and CORE-13. | SCHED-17, widened to "a system or an observer" | SCHED-21: `in_state` composes with `configure_sets`. EVENT-17: the `add_observer(h.run_if(..))` spelling. |
| 4 | BV-ASSET-02 ↔ BV-ASSET-03 (ASSET-02's example is ASSET-03's pattern), with BV-ASSET-09. | ASSET-02 | ASSET-03: the loading screen's "is everything here" check is a walk over one struct. ASSET-09 stays as the path rule. |
| 5 | BV-ECS-16 ↔ BV-STATE-07 ↔ BV-ASSET-11 (mutable access only where you write). STATE-07's Why mis-cites ECS-25. | ECS-16 | STATE-07: a `resource_changed` condition fires every frame. ASSET-11: `Assets<Image>` is read by extraction, UI and sprites. One line each. |
| 6 | BV-ECS-06 ↔ BV-ECS-08 ↔ BV-MIG-03 (`#[require]` for what is always true, a tuple for what is chosen). | ECS-06 | ECS-08: a group type cannot be queried or partly inserted. MIG-03 keeps its removed-type table and drops the restated statement. |
| 7 | BV-ERR-01 ↔ BV-ERR-11 (ERR-01 for observers). | ERR-01, "system or observer" | Observers may return `Result`. |
| 8 | BV-STATE-02 ↔ BV-STATE-05 (no `Vec` of would-be entities in a resource). | STATE-05 for collections | STATE-02 keeps the "could there ever be two?" test and the parallelism cost, and drops its `Vec` clause. |
| 9 | BV-STATE-18 ↔ BV-STATE-19 ↔ BV-MIG-16 row 1 (STATE-18's example is about `set_if_different`). | STATE-19 owns `set_if_different`; MIG-16 the renames | STATE-18 gets its own example, a `ResMut<State<_>>` attempt. STATE-19 drops its rename paragraph. |
| 10 | BV-SCHED-12 ↔ BV-SCHED-14 (SCHED-14's Check is SCHED-12's statement). | SCHED-12 | SCHED-14: a function is the neighbour's implementation detail, and renaming it silently drops the ordering. |
| 11 | BV-SCHED-01 ↔ BV-SCHED-04 (camera work belongs in `Update`). | SCHED-01 | SCHED-04: the stutter mechanism, the `PostUpdate` allowance, and the grep for camera queries in `FixedUpdate`. |
| 12 | BV-SCHED-10 ↔ BV-BUILD-14 (more than seven parameters is `too_many_arguments`). | BUILD-14 for the lint, SCHED-10 for grouping | SCHED-10: name the group by subject and reuse it. Name the lint as the threshold. |
| 13 | BV-ERR-10 ↔ BV-MIG-13 row `impl Command<Result>` (the rule says the old form does not compile). | MIG-13 | ERR-10's verified example becomes an example in ERR-01 or the commands rule, not a rule. |
| 14 | BV-STATE-11 ↔ BV-STATE-13 (loading is a phase), with SCHED-26's `paused` grep. | STATE-11 | STATE-13: loading needs a failure destination. |
| 15 | BV-EVENT-07 ↔ BV-ECS-28 ↔ BV-SCHED-07 (the fixed loop runs 0..n times a frame). | SCHED-07 owns the fact | Messages (expiry) and change ticks are distinct consequences: keep both, with a shorter Why citing SCHED-07. |
| 16 | BV-ECS-15 ↔ BV-ECS-17 (a marker in the data tuple is an unread item). | ECS-15 | ECS-17 is a core rule: keep it as the `With` idiom and the `_` binding giveaway. |
| 17 | BV-VIEW-12 ↔ MIG-03 camera rows; BV-VIEW-14 ↔ MIG-11 `RenderTarget`; BV-VIEW-03 ↔ MIG-05 `ComputedNode`; BV-EVENT-13's 0.20 sentence ↔ BV-MIG-14. | The migration tables, for the renames | VIEW-12 keeps the 0.20 default changes, VIEW-14 its Why, VIEW-03 the input/output distinction. EVENT-13 cites MIG-14. |
| 18 | BV-TEST-08 ↔ ECS-30; TEST-02 ↔ TEST-04 (`DefaultPlugins`); TEST-09 ↔ TEST-07 (set the clock); TEST-15 ↔ SCHED-23 (`shuffle_seed`); TEST-01 ↔ ARCH-01. | The non-test rule each time | TEST-08: `world.flush()`. TEST-02: the "remove each plugin" Check. TEST-01: "count the tests that build an App". |

Checked and complementary, not duplicates: ASSET-01/13, VIEW-19/21, ARCH-02/07, ARCH-06/BUILD-01,
ECS-01/ARCH-04, ECS-03/10, STATE-09/ECS-02, EVENT-09/10/20.

### A.2 Restating a rust-style rule

| # | Bevy rule | rust-style rule | Bevy content | Recommendation |
|---|---|---|---|---|
| 1 | BV-ERR-09 (no `let _ =` on a `Result`) | RS-ERR-02 | builder methods return `&mut App` | Remove; cite RS-ERR-02 |
| 2 | BV-BUILD-16 (workspace lint table) | RS-MOD-29, RS-BUILD-25 | none | Remove; `assets/Cargo.toml` does it |
| 3 | BV-ARCH-19 (split binary from library) | RS-MOD-24, RS-CLI-01 | "testable without a window" | Fold the window clause into ARCH-16 |
| 4 | BV-ERR-13 (log once) | RS-ERR-09 | the handler is `FallbackErrorHandler` | One line on ERR-05 |
| 5 | BV-ERR-08 (no panic on bad content) | RS-ERR-33 | artists, hot reload | Keep only the hot-reload Check; cite RS-ERR-33 |
| 6 | BV-BUILD-19 (`assets/` out of the package) | RS-BUILD-07, RS-BUILD-36 | `assets/` is large | Remove or a note on RS-BUILD-07 |
| 7 | BV-BUILD-20 (cache `target/`) | RS-BUILD-42 | "Bevy is most of the build" | Remove |
| 8 | BV-BUILD-15 (no other allows unmeasured) | RS-BUILD-26/27, CORE-24 | the "allowed because Bevy" anti-pattern | Merge into BUILD-14 |
| 9 | BV-ERR-12 (`tracing`, not `println!`) | RS-CLI-28 | `LogPlugin` filtering; wasm has no stdout | One-line wasm delta |
| 10 | BV-TEST-12 (assert the fact) | RS-TEST-02 | the message-vs-observer example | Keep the example; cite RS-TEST-02 |
| 11 | BV-TEST-09 (insert the time) | RS-CONC-46 | `Time<Virtual>`, which TEST-07 has | Merge into TEST-07 |
| 12 | BV-BUILD-17 (build what you ship) | RS-TEST-36, RS-BUILD-20 | the shipped list is `default-features = false` | Keep as a short delta |
| 13 | BV-BUILD-07 (optimised dependencies in dev) | RS-BUILD-45 | raises `[S]` to `[M]` for frame rate | Keep; cite RS-BUILD-45 |
| 14 | BV-TEST-13 (watch it fail) | RS-TEST-21 | Bevy's vacuous-pass list | Keep; cite RS-TEST-21 |
| 15 | BV-ECS-03, the `Debug` half | RS-API-50 and `missing_debug_implementations` | `Reflect` is the Bevy half | The `Debug` half becomes a citation |

### A.3 Core rules that misstate their chapter rule

| Core rule | Chapter rule | Problem |
|---|---|---|
| BV-CORE-14 "`Time<Virtual>` in `Update`" | BV-SCHED-06: plain `Res<Time>` is the portable form | Contradicts the chapter |
| BV-CORE-18 "no indexing" | BV-ERR-01, which never mentions indexing | Cites only ERR-01; "no indexing" is the `indexing_slicing` row and RS-ERR-03 |
| BV-CORE-15, second sentence | BV-EVENT-03, not cited | Restates EVENT-03 without naming it |
| BV-CORE-09 "more than one data item and more than one filter" | BV-ECS-20 ("two lines", "several… and several"); BV-BUILD-14 ("two and two") | Three triggers for one rule |

### A.4 Rule content a tool row already decides

- **BV-ERR-11**: its Check is `unwrap_used` + `expect_used`; the rest is ERR-01 and ERR-05
  (A.1 #7). The strongest removal candidate.
- **BV-ERR-10**: a rustc error plus the MIG-13 row (A.1 #13).
- **BV-ERR-01**: its whole Check is five deny rows. Its statement is not.
- **BV-CORE-18**, second sentence: `unwrap_used`, `expect_used`, `indexing_slicing`.
- **BV-ERR-07** table: the "unwrapped" rows are the `unwrap_used` row. The `World::entity`,
  `resource` and `non_send` rows carry content no tool does.
- **BV-ECS-24** bullet 1: `unwrap_used`.
- **BV-MIG-16** and BV-STATE-19's "CI denies the warning": the `rustc deprecated` row.
- **BV-STATE-01** Check, first half: deriving both `Component` and `Resource` does not compile.
- **BV-ERR-12**, the `dbg!` part: `dbg_macro = "deny"`.
- **BV-SCHED-10**: the threshold is `too_many_arguments`, which has no row in build.md. Add one,
  or say the lint sets it.

## B. Newer 0.20 APIs

| # | Where | Old | New (source) | Why |
|---|---|---|---|---|
| 1 | BV-ERR-05 example (errors.md:316–322); BV-CORE-19; BV-ARCH-16; BV-ERR-15 comment | `insert_resource(FallbackErrorHandler(handler))` | `App::set_error_handler(handler)` (`bevy_app-0.20.0/src/app.rs:1471–1505`; sub-apps get it at `:1235–1242`) | Installs the handler in every sub-app, where `insert_resource` leaves render and extract on `match_severity`. Panics on a second call, so ERR-05's "exactly one" becomes mechanical. |
| 2 | BV-ASSET-04 (title, statement, Check); BV-MIG-07 row `weak_from_u128` → `weak_handle!` | `weak_handle!("…")` | `uuid_handle!("…")` → `Handle::Uuid` (`bevy_asset-0.20.0/src/handle.rs:677–681`); `weak_handle!` is `#[deprecated]` (`:683–689`) | The rule teaches a deprecated macro, which the shipped CI denies. |
| 3 | BV-ECS-13 `[M!]`, BV-CORE-10, BV-ARCH-14, review step 7; examples architecture.md:264, 664, 692, assets.md:198, 347 | `register_type::<T>()` for every reflected type | Auto-registration: `default_app` includes `reflect_auto_register`; `App::default` uses `AppTypeRegistry::new_with_derived_types()` (`app.rs:113–120`); only generics need registering (`bevy_reflect-0.20.0/src/lib.rs:516–531`) | The mandated form is dead weight, and the Check flags correct code. Register only generic instantiations. BUILD-03's hand-picked list skips `default_app`, so it adds `reflect_auto_register`. |
| 4 | BV-ERR-01 `update_hud` (errors.md:69–78); BV-ERR-07 `aim_rig` (:380–383); BV-VIEW-08 `paste_seed` (view.md:409–413) | `q.single()?` where absence is expected | `Single<D, F>` / `Option<Single<D, F>>` (`bevy_ecs-0.20.0/src/system/query.rs:2953–2998`), which skips the system | An un-annotated `?` error has `Severity::Panic`, so the example's "a skipped frame, not a crash" is false. Keep `?` for unexpected failures. |
| 5 | BV-VIEW-06 example (view.md:313–339) | `On<PointerClick>` with a manual `PointerButton::Primary` check | `On<Activate>` from `bevy::ui_widgets` (`bevy_ui_widgets-0.20.0/src/lib.rs:111–117`, `button.rs:24–76`) | `PointerClick` fires on a disabled button and never on Enter/Space. |
| 6 | BV-ECS-21 para 2, BV-MIG-19 bullet 1 | "`.matched()` keeps the old meaning" for every `iter_many` variant | `.matched()` exists only on `QueryManyIter` and `QueryManyUniqueIter` (`query/iter.rs:1620`, `:2500`); sorted: `.flat_map(Result::ok)`; `par_`: a closure over `Result` | The advice as written does not compile for the sorted and `par_` cases. |
| 7 | BV-TEST-07 example (testing.md:285–317); BV-SCHED-07 test (scheduling.md:244–265); BV-SCHED-26 test | advancing `Time<Fixed>` by hand and `run_schedule(FixedUpdate)` | `TimePlugin` + `TimeUpdateStrategy::FixedTimesteps(n)` + `app.update()` (`bevy_time-0.20.0/src/lib.rs:126–128`, `:187–189`); the first `update()` only initialises | Runs the real fixed loop n times; systems keep the portable `Res<Time>`. |
| 8 | BV-SCHED-17 example (scheduling.md:667); BV-SCHED-18 list (:675–678) | `.run_if(\|alarm: Res<Alarm>\| alarm.0)` | `resource_exists_and(\|a: &Alarm\| a.0)`, new in 0.20 (`schedule/condition.rs:822–831`). The list also omits `resource_exists_and_equals`, `resource_added`, `resource_removed`, `condition_changed(_to)`, `any_component_removed`. | SCHED-18 asks for a shipped condition; this one is false when the resource is absent. |
| 9 | BV-VIEW-09; BV-VIEW-06, BV-EVENT-16 | spawn, find the nested entity, `commands.entity(e).observe(h)` | `on(handler)` in `bsn!` (`bevy_scene-0.20.0/src/scene.rs:574–584`); `bevy::ui_widgets::observe(handler)` in `children![]` (`observe.rs:81–82`) | Attaches an observer to a nested entity inline. |
| 10 | view.md:87–94, 264, 319, 496; errors.md:76 | `Val::Px(48.0)`, `Val::Percent(100.0)` | `px(48)`, `percent(100)`, `vw`, `em`, `rem`, `auto()` (`bevy_ui-0.20.0/src/geometry.rs:565–639`) | The unit leads, which is VIEW-02's point; MIG-17 already writes `px(10.)`. |
| 11 | BV-ASSET-10 | `AssetEvent<A>` mapped back to entities for a per-entity reaction | `AssetChanged<A>` filter (`bevy_asset-0.20.0/src/asset_changed.rs:92–126`); `Or<(Changed<A>, AssetChanged<A>)>` for a swapped handle | A filter instead of an id-to-entity join. The index example keeps `AssetEvent`. |
| 12 | BV-SCHED-18 (`on_message`); BV-EVENT-05 | `MessageReader<M>` + `.run_if(on_message::<M>)` | `PopulatedMessageReader<M>` (`message/message_reader.rs:134–141`) | One parameter skips and reads, with one cursor. |
| 13 | BV-ECS-12 Why and example (ecs.md:366–369) | `#[relationship_target(relationship = CrewOf)]` | `…, linked_spawn` (`relationship/mod.rs:82–93`, `:278`) | Without it, despawning the ship leaves the crew; the Why is true only with it. |
| 14 | BV-STATE-08 | `Option<Res<T>>`, or `resource_exists::<T>` naming the same `T` | `If<Res<T>>` (`system/system_param.rs:1735–1754`) | "Do not run when absent" is stated once, on the parameter. |
| 15 | BV-STATE-17 Check; despawn loops in the ECS-20 and SCHED-10 examples | `for e in &q { commands.entity(e).despawn() }` | `commands.despawn_all::<F>()`, `despawn_all_where::<D, F>(pred)`, new in 0.20 (`system/commands/mod.rs:483`, `:505`) | Batched, and one line. |
| 16 | BV-VIEW-04, BV-VIEW-06 examples (view.md:258–261, 324–327) | `TextFont { font_size: FontSize::Px(32.0), ..default() }` | `TextFont::from_font_size(FontSize::Px(32.0))` (`bevy_text-0.20.0/src/text.rs:709`) | No struct-update noise; keeps the explicit `Px`. |
| 17 | BV-ASSET-02, BV-ASSET-06 `FromWorld` examples (assets.md:66–73, 147–155) | `world.resource::<AssetServer>().load(..)` | `world.load_asset(path)` (`direct_access_ext.rs:14`, `:33`) | One call per handle. |
| 18 | BV-VIEW-01 (`DimOverlay`) | an absolute child at 100% × 100%, which resolves against its parent | `FixedNode`, new in 0.20 (`bevy_ui-0.20.0/src/ui_node.rs:3532–3535`) | A full-screen overlay inside a HUD subtree covers the screen. |

Not findings: `#[entities]` on `CrewOf` is redundant, but Bevy's own `ChildOf` keeps it.
`DespawnWhen` and `Populated` exist, and no rule teaches a worse alternative to either.
