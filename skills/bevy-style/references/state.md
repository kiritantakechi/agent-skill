# State: Resources, States, Transitions, Scoping

Scope: global data that is not attached to an entity, the state machine that decides which parts of
the game are running, and how things are cleaned up when it moves. Bevy 0.19 made `Resource` a
subtrait of `Component`, which changes what a resource may be. Components are in the ECS chapter;
gating a system on a state is in the scheduling chapter.

## Contents

- **Resources**
  - BV-STATE-01 [M] Never make one type both a resource and a component
  - BV-STATE-02 [M] Reserve a resource for what is genuinely global
  - BV-STATE-03 [M] Register a resource in the plugin that defines it
  - BV-STATE-04 [S] Give a resource `FromWorld` when its initial value depends on the world
  - BV-STATE-05 [M] Do not put mutable game state in a resource that a component could hold
  - BV-STATE-06 [S] Make a read-only resource immutable
  - BV-STATE-07 [M] Read a resource with `Res`, and take `ResMut` only to write
  - BV-STATE-08 [M] Reach for `Option<Res<T>>` where absence is expected
  - BV-STATE-09 [S] Keep configuration and progress in separate resources
  - BV-STATE-10 [S] Persist a settings resource with `#[derive(SettingsGroup)]`

- **States**
  - BV-STATE-11 [M] Model the phases of the game as a `States` enum
  - BV-STATE-12 [M] Derive a dependent state rather than keeping two in step
  - BV-STATE-13 [S] Give loading its own state, not a flag
  - BV-STATE-14 [S] Use `SubStates` for a phase that only exists inside another
  - BV-STATE-15 [M] Register every state exactly once
  - BV-STATE-16 [M] Do not branch on `State<S>` inside a system body (see BV-SCHED-21)

- **Transitions**
  - BV-STATE-17 [M] Put setup in `OnEnter` and teardown in `OnExit`
  - BV-STATE-18 [M] Scope an entity to a state with `DespawnOnExit`
  - BV-STATE-19 [M] Write the next state through `NextState`, never `State`
  - BV-STATE-20 [M] Guard a repeated `set` with `set_if_neq`
  - BV-STATE-21 [S] Keep a transition's work bounded
  - BV-STATE-22 [M] Do not assume a transition happens in the frame that requested it

---

## Resources

### BV-STATE-01 [M] Never make one type both a resource and a component

Since 0.19, `#[derive(Resource)]` implements `Component` as well. A type that needs to be both is
two types.

**Why:** the subtrait relationship means uniqueness is a property of the *type*, not of how it is
used. Inserting a `Resource` type as a component on an entity despawns the copy on every other
entity, and a resource shows up in ordinary `&T` queries — so a global fallback stored as a resource
and a per-entity override stored as a component silently become the same storage. Bevy split its own
two cases for this: `UiDebugOptions` became `GlobalUiDebugOptions` and `UiDebugOptions`.

**Check:** grep for a `derive` naming both `Component` and `Resource`; in 0.19 it will not compile.
Then grep for the `Global*` pattern in reverse — a resource and a component that are conceptually
the same fact need two names, not one.

```rust
// verified — GOOD: the global default and the per-entity override are two types
use bevy::prelude::*;

/// The setting a new entity inherits.
#[derive(Resource, Debug, Clone, Copy, Reflect)]
#[reflect(Resource)]
pub struct GlobalGravity(pub f32);

/// The setting one entity overrides it with.
#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Gravity(pub f32);

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Velocity(pub Vec3);

/// The per-entity value wins where it exists; the resource is the fallback.
fn fall(
    mut bodies: Query<(&mut Velocity, Option<&Gravity>)>,
    global: Res<GlobalGravity>,
    time: Res<Time<Fixed>>,
) {
    for (mut velocity, gravity) in &mut bodies {
        velocity.0.y -= gravity.map_or(global.0, |g| g.0) * time.delta_secs();
    }
}
```

### BV-STATE-02 [M] Reserve a resource for what is genuinely global

Score, elapsed round time, the current wave, a settings block, a handle table. Not "the player's
health", and not a `Vec` of things that are really entities.

**Why:** a resource is one value for the whole world, so anything stored in one can never have two
of it — and games grow second players, split screens, and preview worlds. It is also invisible to
the query planner: two systems touching the same resource cannot run in parallel, where the same
data on entities would have been partitioned.

**Check:** ask whether there could ever be two. If the answer is not "no, by construction", it is a
component on an entity.

### BV-STATE-03 [M] Register a resource in the plugin that defines it

`app.init_resource::<Score>()` in `score`'s plugin, not in a central setup.

**Why:** it is BV-ARCH-14 with the case that bites most often: a resource that is never initialised
does not fail to compile, it fails at first access, in whichever system happened to run first — and
the error names the type but not the plugin that forgot it. Keeping initialisation with definition
makes "did anyone register this?" answerable by reading one file.

**Check:** for each `#[derive(Resource)]`, find the `init_resource` or `insert_resource`. The two
should be in the same module.

### BV-STATE-04 [S] Give a resource `FromWorld` when its initial value depends on the world

A resource that needs an `AssetServer`, a registry, or another resource to build implements
`FromWorld`; `init_resource` then uses it.

**Why:** the alternative is a startup system that inserts the resource, which is a second place the
type is constructed and an ordering problem for everything that reads it — anything running before
that system finds nothing. `FromWorld` runs at registration, so the resource exists from the first
frame.

**Check:** grep for `insert_resource` in a `Startup` system. Each one is a `FromWorld` impl that has
not been written.

### BV-STATE-05 [M] Do not put mutable game state in a resource that a component could hold

A `Vec<Enemy>` in a resource is a set of entities that has not been spawned.

**Why:** collections in resources give up everything the ECS provides: no queries, no change
detection per item, no parallel iteration, no relationships, no reflection of the individual items,
and no despawn. They also serialise every system that touches the collection against every other.
The usual sign is a resource whose fields are all `Vec` or `HashMap` keyed by something entity-like.

The single exception is a simulation the domain owns — one with its own clock, its own event log,
and a save that has to replay. BV-ARCH-06 forbids its fleets, its star systems and its in-flight
orders from being components, because that would put `bevy_ecs` inside the domain; so they are one
resource wrapping one domain type, and the adapter is what queries it. That is the *whole* of the
exception: a resource holding a `Vec` of things the ECS could have held, on the ECS side of the
boundary, is the defect this rule is about.

**Check:** for each collection in a resource, ask what the elements are. If they have identity and a
lifetime, they are entities — unless the collection is the domain's own state, in which case the
resource is a newtype over one domain type and no system reaches inside it.

### BV-STATE-06 [S] Make a read-only resource immutable

A resource written once at startup and only read afterwards can be `#[component(immutable)]`, which
in 0.19 makes `ResMut` unavailable for it.

**Why:** the type then states its own contract, and the compiler enforces it — a system that tries
to write gets an error rather than a review comment. It also removes the scheduling constraint: with
no writer possible, no two readers can conflict.

**Check:** for each resource, count the `ResMut<T>` uses. Zero means the type can say so.

### BV-STATE-07 [M] Read a resource with `Res`, and take `ResMut` only to write

`Res<Score>` to read. `ResMut<Score>` only in systems that assign.

**Why:** `ResMut` is an exclusive lock for the whole schedule, so a system holding one for reading
blocks every other system that touches that resource for as long as it runs. Dereferencing it
mutably also marks the resource changed, which makes `resource_changed` run conditions fire every
frame — the resource-level version of BV-ECS-26.

**Check:** for each `ResMut`, find the write. If the body only reads, it is a `Res`.

### BV-STATE-08 [M] Reach for `Option<Res<T>>` where absence is expected

A resource that only exists in some states, or is inserted by another plugin that may not be
present, is `Option<Res<T>>`.

**Why:** a plain `Res<T>` whose resource is missing makes the system fail parameter validation, and
in 0.19 that failure goes to the fallback error handler rather than being visible at the call site.
The `Option` form says in the signature that absence is a case, and lets the body say what happens
then. `resource_exists` as a run condition is the other form and is better when the answer is
"do not run".

**Check:** for each `Res<T>`, ask when `T` is inserted relative to this system. Anything conditional
needs the `Option` or a run condition.

```rust
// verified
use bevy::prelude::*;

/// Inserted by a plugin the shipping build may leave out.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct SpawnBudget {
    pub per_tick: u32,
}

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct SpawnQueue {
    pub pending: u32,
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Enemy;

/// The `Option` puts "this may be missing" in the signature and lets the body
/// answer it. A plain `Res<SpawnBudget>` would fail parameter validation on
/// every tick of a build without the profiling plugin, and the failure would
/// surface in the fallback error handler rather than here.
fn drain_spawn_queue(
    mut commands: Commands,
    mut queue: ResMut<SpawnQueue>,
    budget: Option<Res<SpawnBudget>>,
) {
    /// What a build without the profiling plugin uses instead.
    const UNGOVERNED: u32 = 2;

    let cap = budget.map_or(UNGOVERNED, |b| b.per_tick).min(queue.pending);
    for _ in 0..cap {
        commands.spawn(Enemy);
    }
    queue.pending -= cap;
}

#[derive(Debug, Default)]
pub struct SpawningPlugin;

impl Plugin for SpawningPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<SpawnQueue>()
            .add_systems(FixedUpdate, drain_spawn_queue);
    }
}

/// Optional. Nothing in `SpawningPlugin` names it.
#[derive(Debug, Default)]
pub struct ProfilingPlugin;

impl Plugin for ProfilingPlugin {
    fn build(&self, app: &mut App) {
        app.insert_resource(SpawnBudget { per_tick: 5 });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tick(app: &mut App) -> usize {
        app.world_mut().resource_mut::<SpawnQueue>().pending = 10;
        app.world_mut().run_schedule(FixedUpdate);
        let world = app.world_mut();
        world.query::<&Enemy>().iter(world).len()
    }

    #[test]
    fn the_body_names_the_fallback() {
        let mut app = App::new();
        app.add_plugins(SpawningPlugin);
        assert_eq!(tick(&mut app), 2);
        assert_eq!(app.world().resource::<SpawnQueue>().pending, 8);
    }

    #[test]
    fn the_resource_wins_where_the_plugin_supplied_it() {
        let mut app = App::new();
        app.add_plugins((SpawningPlugin, ProfilingPlugin));
        assert_eq!(tick(&mut app), 5);
        assert_eq!(app.world().resource::<SpawnQueue>().pending, 5);
    }
}
```

### BV-STATE-09 [S] Keep configuration and progress in separate resources

`CombatSettings` is written by the settings screen and read by the simulation; `CombatProgress` is
written by the simulation every frame. They are not one `Combat` resource.

**Why:** change detection and scheduling both key on the resource, so mixing them means every
progress tick marks the settings changed and every reader of settings is blocked by the simulation's
writer. It is BV-ECS-02 for resources, and the same test applies.

**Check:** for each resource, list the systems that write each field. Fields with disjoint writers
are separate resources.

### BV-STATE-10 [S] Persist a settings resource with `#[derive(SettingsGroup)]`

0.19's `bevy_settings` loads a resource from the platform's own preferences directory at startup and
gives you two commands to write it back. It replaces the load system, the path constant, and the
serialisation between them — but not the decision of *when* to save.

**Why:** every game writes this code and writes the same bugs into it: the path that is right on one
platform, the save that never fires because nothing watched for the change, and the settings file
that is a bespoke format nobody else can read. Four things about it are worth knowing before it is
reached for, and none of them are guessable:

- **Saving is explicit.** The plugin loads; it does not save. `commands.queue(SaveSettingsDeferred(
  Duration::from_secs_f32(0.5)))` debounces a write so a dragged slider does not hammer the disk,
  and `SaveSettingsSync::IfChanged` blocks until the write lands, which is what save-on-quit needs.
- **It is a reflected type, so BV-ECS-13 reaches it.** The derive list is
  `#[derive(Resource, SettingsGroup, Reflect, Default)]` with
  `#[reflect(Resource, SettingsGroup, Default)]`; without the `reflect` attribute the group is
  invisible to the loader.
- **Some platforms do not persist at all.** TOML under `~/.config`, `~/Library/Preferences` or
  `%LOCALAPPDATA%`, `localStorage` on wasm — and on anything else `preferences_dir()` is `None` and
  the settings are simply not kept. Code that treats a saved value as certain is wrong there.
- **The 0.19 release notes name the API wrong.** They say `PreferencesPlugin`,
  `SavePreferencesDeferred` and `SavePreferencesSync`; the shipped crate spells them
  `SettingsPlugin`, `SaveSettingsDeferred` and `SaveSettingsSync`. This is BV-MIG-03's hazard on a
  feature that is one release old, so check the name against the crate and not against the prose.

Two smaller shapes: a group's TOML section is its own type name in snake_case, and two types sharing
`#[settings_group(group = "…")]` merge into one section; `#[settings_group(key = …)]` is a compile
error on a struct with named fields, where the keys are the field names. The feature is
`bevy/bevy_settings`, which is in no collection, so it is named beside one (BV-BUILD-11).

**Check:** does anything in the game still build a config path, or serialise settings by hand? Both
are what this replaces. Then find the save: a `SettingsGroup` with no `SaveSettings*` anywhere is a
resource that loads once and never persists a change. BV-STATE-09 still governs what goes in:
settings are configuration, so progress does not belong in the same type.

## States

### BV-STATE-11 [M] Model the phases of the game as a `States` enum

Menu, loading, playing, paused, game over. `#[derive(States)]` with `Default` on the first phase.

**Why:** the state is what run conditions, `OnEnter`/`OnExit` and entity scoping all key on, so a
phase modelled as a `bool` resource gets none of that machinery — no transition hooks, no automatic
despawn, and no way to add a third phase without touching every reader. An enum also makes the
phases exhaustive, so a new one is a compile error everywhere it matters.

**Check:** grep for boolean resources named `paused`, `in_menu`, `loading`, `started`. Each pair of
them is a state enum.

```rust
// verified
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Screen {
    #[default]
    Loading,
    Menu,
    Playing,
}

fn tick_simulation() {}

#[derive(Debug, Default)]
pub struct ScreenPlugin;

impl Plugin for ScreenPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>().add_systems(
            FixedUpdate,
            tick_simulation.run_if(in_state(Screen::Playing)),
        );
    }
}
```

### BV-STATE-12 [M] Derive a dependent state rather than keeping two in step

If "is the world simulating" is a function of the screen and the pause flag, it is a
`ComputedStates` impl, not a third state somebody has to remember to set.

**Why:** two states that must agree will disagree — some path sets one and returns early, and the
game is left simulating behind a menu. A computed state is recalculated from its sources on every
transition, so the invariant is maintained by construction rather than by every author of every
transition.

**Check:** for each pair of states, ask whether one is a function of the other. If yes, and both are
set by hand, that is the bug waiting.

```rust
// verified
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Screen {
    #[default]
    Menu,
    Playing,
}

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Pause {
    #[default]
    Running,
    Paused,
}

/// Not a state anyone sets: `State<Simulating>` exists exactly while both
/// sources agree, and is removed the moment either stops agreeing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Reflect)]
pub struct Simulating;

impl ComputedStates for Simulating {
    /// A tuple is a `StateSet`; `compute` re-runs when either source moves.
    /// Wrap a source in `Option` to keep computing while it does not exist.
    type SourceStates = (Screen, Pause);

    fn compute((screen, pause): Self::SourceStates) -> Option<Self> {
        matches!((screen, pause), (Screen::Playing, Pause::Running)).then_some(Self)
    }
}

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Ticks(pub u32);

fn advance_world(mut ticks: ResMut<Ticks>) {
    ticks.0 += 1;
}

#[derive(Debug, Default)]
pub struct SimulationPlugin;

impl Plugin for SimulationPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>()
            .init_state::<Pause>()
            .add_computed_state::<Simulating>()
            .init_resource::<Ticks>()
            .add_systems(Update, advance_world.run_if(in_state(Simulating)));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::state::app::StatesPlugin;

    fn app() -> App {
        let mut app = App::new();
        app.add_plugins((StatesPlugin, SimulationPlugin));
        app
    }

    #[test]
    fn simulating_follows_both_sources() {
        let mut app = app();
        app.update();
        assert!(app.world().get_resource::<State<Simulating>>().is_none());
        assert_eq!(app.world().resource::<Ticks>().0, 0);

        app.world_mut()
            .resource_mut::<NextState<Screen>>()
            .set(Screen::Playing);
        app.update();
        assert!(app.world().get_resource::<State<Simulating>>().is_some());
        assert_eq!(app.world().resource::<Ticks>().0, 1);

        // Moving either source alone is enough to end the derived state.
        app.world_mut()
            .resource_mut::<NextState<Pause>>()
            .set(Pause::Paused);
        app.update();
        assert!(app.world().get_resource::<State<Simulating>>().is_none());
        assert_eq!(app.world().resource::<Ticks>().0, 1);
    }
}
```

### BV-STATE-13 [S] Give loading its own state, not a flag

Asset loading is a phase: it has an entry, a progress condition, an exit, and a failure. That is a
state.

**Why:** as a state, everything that must not run during loading is gated by one condition, the
loading screen's entities are despawned by scoping rather than by a bespoke system, and "loading
failed" has somewhere to go. As a `bool`, each of those is hand-written and the failure case usually
is not written at all.

**Check:** does the game have a `loaded: bool` or an `AssetsLoading` collection with a system that
checks it? That check is a run condition on a transition.

### BV-STATE-14 [S] Use `SubStates` for a phase that only exists inside another

Paused, inventory-open and dialogue-open exist only while playing. `#[derive(SubStates)]` with
`#[source(Screen = Screen::Playing)]` says so.

**Why:** a sub-state is created on entering its source and removed on leaving, so "paused in the
main menu" is not representable — where two independent enums make it representable and therefore
eventually real. The removal also runs the sub-state's `OnExit`, which is where the pause overlay
gets cleaned up without anyone writing that code.

**Check:** for each state, ask whether every variant is meaningful in every variant of every other
state. Where it is not, one is a sub-state of the other.

### BV-STATE-15 [M] Register every state exactly once

`init_state` for a root state, `add_sub_state` for a sub-state, `add_computed_state` for a computed
one — each called once, in the plugin that defines the type.

**Why:** registering twice installs the transition systems twice, so every `OnEnter` runs twice per
transition. Registering with the wrong function is worse: `init_state` on a type meant to be a
sub-state gives it an independent life, and the `#[source]` relationship silently does nothing.

**Check:** grep each state type name. Exactly one registration call, and its kind matches the
derive.

### BV-STATE-16 [M] Do not branch on `State<S>` inside a system body (see BV-SCHED-21)

Owned by `references/scheduling.md` BV-SCHED-21. A comparison against `State<S>` in a body is a
run condition that has been written as an `if`, and the system still pays for every parameter it
declared.

## Transitions

### BV-STATE-17 [M] Put setup in `OnEnter` and teardown in `OnExit`

`app.add_systems(OnEnter(Screen::Playing), spawn_level)` and the matching `OnExit`.

**Why:** the transition schedules run exactly once per transition, between the frames, so nothing
observes a half-built level. The alternative — a `Startup`-style system with a run condition — runs
every frame the condition holds and needs its own "have I done this" flag, which is a state machine
built inside a state machine.

**Check:** grep for `run_once` and for `Local<bool>` used as a "did setup" flag. Each is an
`OnEnter` system.

```rust
// verified
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Screen {
    #[default]
    Menu,
    Playing,
}

/// Exists for exactly one run of the level.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Round {
    pub kills: u32,
}

/// Outlives every run.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Career {
    pub best: u32,
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Enemy;

/// Runs once, between two frames, so no system ever sees half a level.
fn open_round(mut commands: Commands) {
    commands.init_resource::<Round>();
    for lane in 0..4u8 {
        commands.spawn((
            Enemy,
            Transform::from_xyz(f32::from(lane), 0.0, 0.0),
            DespawnOnExit(Screen::Playing),
        ));
    }
}

/// The entities are scoped, so teardown is only what scoping cannot do:
/// keep the one fact that survives the round, drop the rest.
fn close_round(mut commands: Commands, round: Res<Round>, mut career: ResMut<Career>) {
    if round.kills > career.best {
        career.best = round.kills;
    }
    commands.remove_resource::<Round>();
}

#[derive(Debug, Default)]
pub struct RoundPlugin;

impl Plugin for RoundPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>()
            .init_resource::<Career>()
            .add_systems(OnEnter(Screen::Playing), open_round)
            .add_systems(OnExit(Screen::Playing), close_round);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::state::app::StatesPlugin;

    fn enemies(world: &mut World) -> usize {
        world.query::<&Enemy>().iter(world).len()
    }

    #[test]
    fn enter_builds_the_round_and_exit_folds_it_away() {
        let mut app = App::new();
        app.add_plugins((StatesPlugin, RoundPlugin));
        app.update();
        assert!(app.world().get_resource::<Round>().is_none());

        app.world_mut()
            .resource_mut::<NextState<Screen>>()
            .set(Screen::Playing);
        app.update();
        assert_eq!(enemies(app.world_mut()), 4);
        app.world_mut().resource_mut::<Round>().kills = 7;

        app.world_mut()
            .resource_mut::<NextState<Screen>>()
            .set(Screen::Menu);
        app.update();
        assert_eq!(enemies(app.world_mut()), 0);
        assert!(app.world().get_resource::<Round>().is_none());
        assert_eq!(app.world().resource::<Career>().best, 7);
    }
}
```

### BV-STATE-18 [M] Scope an entity to a state with `DespawnOnExit`

Spawn level entities with `DespawnOnExit(Screen::Playing)` rather than writing a system that queries
and despawns them.

**Why:** the component travels with the entity, so an entity spawned by a plugin nobody remembers is
still cleaned up. A hand-written teardown system has to enumerate what to despawn, which means it is
correct only until somebody spawns a kind of entity they did not add to the list — and the failure
is a leak that survives into the next round.

**Check:** look at each `OnExit` system. If it is a query-and-despawn, the marker belongs on the
entities instead.

```rust
// verified
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
enum Screen {
    #[default]
    Menu,
    Playing,
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Enemy;

/// Nothing has to remember to despawn these.
fn spawn_wave(mut commands: Commands) {
    for i in 0..8u8 {
        commands.spawn((
            Enemy,
            Transform::from_xyz(f32::from(i), 0.0, 0.0),
            DespawnOnExit(Screen::Playing),
        ));
    }
}

#[derive(Debug, Default)]
pub struct LevelPlugin;

impl Plugin for LevelPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>()
            .add_systems(OnEnter(Screen::Playing), spawn_wave);
    }
}
```

### BV-STATE-19 [M] Write the next state through `NextState`, never `State`

`next.set(Screen::Menu)` on a `ResMut<NextState<Screen>>`. `State<S>` is read-only by design.

**Why:** the split is what makes transitions atomic: the request is recorded, and the transition
schedules run at a defined point with the old and new values both available. Writing the current
state directly — where an API allows it — changes it mid-frame, so half the systems in that frame
see one state and half see the other.

**Check:** grep for `ResMut<State<`. There should be none.

```rust
// verified
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Screen {
    #[default]
    Menu,
    Playing,
}

/// Raised while a run is in progress; the driver below re-asserts it every frame.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct RunInProgress(pub bool);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct LevelBuilds(pub u32);

/// `State<Screen>` is read-only: the request goes through `NextState`, and is
/// applied in `StateTransition`, not here. Since 0.18 a plain `set` re-enters a
/// state it is already in — so a system that asks every frame asks with
/// `set_if_neq`, or it rebuilds the level every frame.
fn follow_run(run: Res<RunInProgress>, mut next: ResMut<NextState<Screen>>) {
    if run.0 {
        // `as_mut` is load-bearing: `DetectChangesMut::set_if_neq` is in
        // scope on the `ResMut` itself and would try to compare two whole
        // `NextState`s. The one that takes a state is `NextState`'s own.
        next.as_mut().set_if_neq(Screen::Playing);
    }
}

fn build_level(mut builds: ResMut<LevelBuilds>) {
    builds.0 += 1;
}

#[derive(Debug, Default)]
pub struct RunPlugin;

impl Plugin for RunPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>()
            .init_resource::<RunInProgress>()
            .init_resource::<LevelBuilds>()
            .add_systems(OnEnter(Screen::Playing), build_level)
            .add_systems(Update, follow_run);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::state::app::StatesPlugin;

    fn running_app() -> App {
        let mut app = App::new();
        app.add_plugins((StatesPlugin, RunPlugin));
        app.world_mut().resource_mut::<RunInProgress>().0 = true;
        app
    }

    #[test]
    fn asking_every_frame_enters_once() {
        let mut app = running_app();
        for _ in 0..4 {
            app.update();
        }
        let screen = app.world().resource::<State<Screen>>();
        assert_eq!(screen.get(), &Screen::Playing);
        assert_eq!(app.world().resource::<LevelBuilds>().0, 1);
    }

    #[test]
    fn a_plain_set_re_enters_the_state_it_is_already_in() {
        let mut app = running_app();
        app.update();
        app.update();
        assert_eq!(app.world().resource::<LevelBuilds>().0, 1);

        app.world_mut()
            .resource_mut::<NextState<Screen>>()
            .set(Screen::Playing);
        app.update();
        assert_eq!(app.world().resource::<LevelBuilds>().0, 2);
    }
}
```

### BV-STATE-20 [M] Guard a repeated `set` with `set_if_neq`

Since 0.18, `next.set(S)` runs `OnExit(S)` and `OnEnter(S)` even when the current state is already
`S`. A system that calls `set` every frame must use `set_if_neq`.

**Why:** this changed underneath existing code and does not affect whether it compiles. Code that
called `set` unconditionally used to be a no-op when the state matched; now it tears down and
rebuilds the level, every frame. The new behaviour is deliberate — re-entering a state is sometimes
exactly what is wanted — which is why the old behaviour has to be asked for.

**Check:** for each `next.set(`, ask whether the surrounding code can run while already in that
state. If it can, it needs `set_if_neq`.

### BV-STATE-21 [S] Keep a transition's work bounded

`OnEnter` runs between frames, so everything in it is a frame the player does not get. Spawn what
must exist; stream the rest.

**Why:** the transition is synchronous and uninterruptible, so a level built entirely in `OnEnter`
is a visible hitch whose length grows with the level. Spawning the essentials there and letting the
rest arrive over the following frames — or during a loading state with a progress bar — keeps the
hitch constant.

**Check:** time the transition on the slowest supported machine. Anything over a frame's budget
needs splitting.

### BV-STATE-22 [M] Do not assume a transition happens in the frame that requested it

`next.set(…)` records a request. The state has not changed when the next line runs.

**Why:** the transition is applied by the state transition systems, which run in the
`StateTransition` schedule — after `PreUpdate` and before `RunFixedMainLoop` and `Update`. Code that
sets the state and then reads `State<S>` in the same system reads the old value, and so does
anything else in that schedule. The usual "fix" is to read it in a later system, which works by
accident until somebody changes the schedule.

**Check:** in each system that calls `set`, look for a subsequent read of `State<S>`. Move the
dependent work into `OnEnter`.
