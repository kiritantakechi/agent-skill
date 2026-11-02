# State: Resources, States, Transitions, Scoping

Scope: global data that is not attached to an entity, the state machine that decides which parts of
the game are running, and how things are cleaned up when it moves. `Resource` is a subtrait of
`Component`, which shapes what a resource may be. Components are in the ECS chapter; gating a
system on a state is in the scheduling chapter.

## Contents

- **Resources**
  - BV-STATE-01 [M] Never make one type both a resource and a component
  - BV-STATE-02 [M] Reserve a resource for what is genuinely global
  - BV-STATE-03 [S] Give a resource `FromWorld` when its initial value depends on the world
  - BV-STATE-04 [M] Do not put mutable game state in a resource that a component could hold
  - BV-STATE-05 [S] Make a read-only resource immutable
  - BV-STATE-06 [M] Take `Option<Res<T>>` or `If<Res<T>>` where absence is expected
  - BV-STATE-07 [S] Keep configuration and progress in separate resources
  - BV-STATE-08 [S] Persist a settings resource with `#[derive(SettingsGroup)]`

- **States**
  - BV-STATE-09 [M] Model the phases of the game as a `States` enum
  - BV-STATE-10 [M] Derive a dependent state rather than keeping two in step
  - BV-STATE-11 [S] Use `SubStates` for a phase that only exists inside another
  - BV-STATE-12 [M] Register every state exactly once

- **Transitions**
  - BV-STATE-13 [M] Put setup in `OnEnter` and teardown in `OnExit`
  - BV-STATE-14 [M] Scope an entity to a state with `DespawnOnExit`
  - BV-STATE-15 [M] Write the next state through `NextState`, never `State`
  - BV-STATE-16 [M] Guard a repeated `set` with `set_if_different`
  - BV-STATE-17 [S] Keep a transition's work bounded
  - BV-STATE-18 [M] Do not assume a transition happens in the frame that requested it

---

## Resources

### BV-STATE-01 [M] Never make one type both a resource and a component

`#[derive(Resource)]` implements `Component` as well, so a type that needs to be both is two types,
as Bevy split its own `UiDebugOptions` into `GlobalUiDebugOptions` and `UiDebugOptions`.

The resource itself is a component on an entity of its own, marked `IsResource`, and no default
filter hides that entity. `Query<Entity>`, `Query<EntityRef>` and `Query<EntityMut>` match it, so a
sweep that despawns everything it matches despawns the resources too: Bevy warns, and then the
command its own hook queues fails on the gone entity, which the default error handler turns into a
panic. `Query<EntityMut>` beside any `Res`, or `Query<EntityRef>` beside a `ResMut`, conflicts with
the resource and panics with B0002 when the system is built. Each takes `Without<IsResource>`.

**Why:** uniqueness belongs to the *type*: a resource type spawned on a second entity is stripped
from it with only a warning, and the resource shows up in ordinary `&T` queries, so a global
fallback and a per-entity override cannot share one type.

**Check:** grep for a `derive` naming both `Component` and `Resource`; it does not compile.
Then grep for the `Global*` pattern in reverse — a resource and a component that are conceptually
the same fact need two names, not one. Then read each `Query<Entity>`, `Query<EntityRef>` and
`Query<EntityMut>` whose filter does not already exclude resource entities.

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
health". A collection of things that are really entities is BV-STATE-04's case.

**Why:** a resource is one value for the whole world, and games grow second players, split screens
and preview worlds. Two systems touching the same resource also cannot run in parallel, where the
same data on entities would have been partitioned.

**Check:** ask whether there could ever be two. If the answer is not "no, by construction", it is a
component on an entity.

### BV-STATE-03 [S] Give a resource `FromWorld` when its initial value depends on the world

A resource that needs an `AssetServer`, a registry, or another resource to build implements
`FromWorld`; `init_resource` then uses it.

**Why:** a startup system that inserts the resource is a second place the type is constructed, and
anything that runs before it finds nothing. `FromWorld` runs at registration, so the resource exists
from the first frame.

**Check:** grep for `insert_resource` in a `Startup` system. Each one is a `FromWorld` impl that has
not been written.

### BV-STATE-04 [M] Do not put mutable game state in a resource that a component could hold

A `Vec<Enemy>` in a resource is a set of entities that has not been spawned. The usual sign is a
resource whose fields are all `Vec` or `HashMap` keyed by something entity-like.

The single exception is a simulation the domain owns — one with its own clock, its own event log,
and a save that has to replay. BV-ARCH-06 forbids its fleets, its star systems and its in-flight
orders from being components, because that would put `bevy_ecs` inside the domain; so they are one
resource wrapping one domain type, and the adapter is what queries it. That is the *whole* of the
exception: a resource holding a `Vec` of things the ECS could have held, on the ECS side of the
boundary, is the defect this rule is about.

**Why:** a collection in a resource gives up per-item queries, change detection, parallel iteration,
relationships, reflection and despawn, and it serialises every system that touches it against every
other.

**Check:** for each collection in a resource, ask what the elements are. If they have identity and a
lifetime, they are entities — unless the collection is the domain's own state, in which case the
resource is a newtype over one domain type and no system reaches inside it.

### BV-STATE-05 [S] Make a read-only resource immutable

A resource written once at startup and only read afterwards can be `#[component(immutable)]`, which
makes `ResMut` unavailable for it.

**Why:** the type then states its own contract, and the compiler enforces it — a system that tries
to write gets an error rather than a review comment. It also removes the scheduling constraint: with
no writer possible, no two readers can conflict.

**Check:** for each resource, count the `ResMut<T>` uses. Zero means the type can say so.

### BV-STATE-06 [M] Take `Option<Res<T>>` or `If<Res<T>>` where absence is expected

A resource that only exists in some states, or is inserted by another plugin that may not be
present, is `Option<Res<T>>` when the body has something to do without it, and `If<Res<T>>` when
the answer is "do not run": `If` skips the system instead of failing. Prefer it to a
`resource_exists::<T>` run condition, which has to name the same `T` as the parameter and can drift
from it.

**Why:** a plain `Res<T>` whose resource is missing fails parameter validation, and the failure goes
to the fallback error handler rather than showing at the call site. Either wrapper says in the
signature that absence is a case: the `Option` lets the body answer it, the `If` skips the run.

**Check:** for each `Res<T>`, ask when `T` is inserted relative to this system. Anything conditional
needs the `Option` or the `If`.

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

/// How much spawning the profiler has budgeted for, across every tick it saw.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Budgeted(pub u32);

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

/// Nothing to do without the budget, so `If` skips the system rather than
/// failing it: the condition is stated once, on the parameter it is about.
fn tally_budget(budget: If<Res<SpawnBudget>>, mut budgeted: ResMut<Budgeted>) {
    budgeted.0 += budget.per_tick;
}

#[derive(Debug, Default)]
pub struct SpawningPlugin;

impl Plugin for SpawningPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<SpawnQueue>()
            .init_resource::<Budgeted>()
            .add_systems(FixedUpdate, (drain_spawn_queue, tally_budget));
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
        // Skipped, not failed: a plain `Res` here would reach the error handler.
        assert_eq!(app.world().resource::<Budgeted>().0, 0);
    }

    #[test]
    fn the_resource_wins_where_the_plugin_supplied_it() {
        let mut app = App::new();
        app.add_plugins((SpawningPlugin, ProfilingPlugin));
        assert_eq!(tick(&mut app), 5);
        assert_eq!(app.world().resource::<SpawnQueue>().pending, 5);
        assert_eq!(app.world().resource::<Budgeted>().0, 5);
    }
}
```

### BV-STATE-07 [S] Keep configuration and progress in separate resources

`CombatSettings` is written by the settings screen and read by the simulation; `CombatProgress` is
written by the simulation every frame. They are not one `Combat` resource.

**Why:** change detection and scheduling both key on the resource, so mixing them means every
progress tick marks the settings changed and every reader of settings is blocked by the simulation's
writer. It is BV-ECS-02 for resources, and the same test applies.

**Check:** for each resource, list the systems that write each field. Fields with disjoint writers
are separate resources.

### BV-STATE-08 [S] Persist a settings resource with `#[derive(SettingsGroup)]`

`bevy_settings`'s `SettingsPlugin` loads a resource from the platform's own preferences
directory at startup, and gives you two commands to write it back. It replaces the load system, the
path constant, and the serialisation between them — but not the decision of *when* to save. Three
things about it are not guessable:

- **Saving is explicit.** The plugin loads; it does not save. `commands.queue(SaveSettingsDeferred(
  Duration::from_secs_f32(0.5)))` debounces a write so a dragged slider does not hammer the disk,
  and `SaveSettingsSync::IfChanged` blocks until the write lands, which is what save-on-quit needs.
- **It is a reflected type.** The derive list is `#[derive(Resource, SettingsGroup, Reflect,
  Default)]`; `SettingsGroup` is bounded by `Resource + Reflect + Default`, so a missing derive is a
  compile error. The attribute is `#[reflect(Resource, SettingsGroup, Default)]`, and a missing
  `#[reflect(Default)]` is a logged error.
- **Some platforms do not persist at all.** TOML under `~/.config`, `~/Library/Preferences` or
  `%LOCALAPPDATA%`, `localStorage` on wasm — and on anything else `preferences_dir()` is `None` and
  the settings are simply not kept. Code that treats a saved value as certain is wrong there.

Two smaller shapes: a group's TOML section is its own type name in snake_case, and two types sharing
`#[settings_group(group = "…")]` merge into one section; `#[settings_group(key = …)]` is a compile
error on a struct with named fields, where the keys are the field names. The feature is
`bevy/bevy_settings`, which is in no collection, so it is named beside one (BV-BUILD-11).

**Why:** every game writes this code and writes the same bugs into it: the path that is right on one
platform, the save that never fires because nothing watched for the change, and a settings file in
a bespoke format nobody else can read.

**Check:** does anything in the game still build a config path, or serialise settings by hand? Both
are what this replaces. Then find the save: a `SettingsGroup` with no `SaveSettings*` anywhere is a
resource that loads once and never persists a change. BV-STATE-07 still governs what goes in:
settings are configuration, so progress does not belong in the same type.

## States

### BV-STATE-09 [M] Model the phases of the game as a `States` enum

Menu, loading, playing, paused, game over. `#[derive(States)]` with `Default` on the first phase.
Loading is one of them, with somewhere to go when it fails: an entry, a progress condition, an exit
and a failure are a state's shape, not a flag's.

**Why:** run conditions, `OnEnter`/`OnExit` and entity scoping all key on the state, so a `bool`
phase gets no transition hooks, no automatic despawn, and no third phase without touching every
reader. An enum is exhaustive, so a new phase is a compile error everywhere it matters.

**Check:** grep for boolean resources named `paused`, `in_menu`, `loading`, `started`. Each pair of
them is a state enum. A `loaded: bool`, or an `AssetsLoading` collection a system checks, is a
loading state kept as a flag.

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

### BV-STATE-10 [M] Derive a dependent state rather than keeping two in step

If "is the world simulating" is a function of the screen and the pause flag, it is a
`ComputedStates` impl, not a third state somebody has to remember to set.

**Why:** two states that must agree will disagree — some path sets one and returns early, and the
game is left simulating behind a menu. A computed state is recalculated from its sources on every
transition, so the invariant holds by construction.

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

### BV-STATE-11 [S] Use `SubStates` for a phase that only exists inside another

Paused, inventory-open and dialogue-open exist only while playing. `#[derive(SubStates)]` with
`#[source(Screen = Screen::Playing)]` says so.

**Why:** a sub-state exists only while its source does, so "paused in the main menu" cannot be
represented, where two independent enums make it eventually real. Leaving the source runs the
sub-state's `OnExit`, which cleans up the pause overlay without anyone writing that code.

**Check:** for each state, ask whether every variant is meaningful in every variant of every other
state. Where it is not, one is a sub-state of the other.

### BV-STATE-12 [M] Register every state exactly once

`init_state` for a root state, `add_sub_state` for a sub-state, `add_computed_state` for a computed
one — each called once, in the plugin that defines the type.

**Why:** registering twice installs the transition systems twice, so every `OnEnter` runs twice per
transition. Registering with the wrong function is worse: `init_state` on a type meant to be a
sub-state gives it an independent life, and the `#[source]` relationship silently does nothing.

**Check:** grep each state type name. Exactly one registration call, and its kind matches the
derive.

## Transitions

### BV-STATE-13 [M] Put setup in `OnEnter` and teardown in `OnExit`

`app.add_systems(OnEnter(Screen::Playing), spawn_level)` and the matching `OnExit`.

**Why:** the transition schedules run exactly once per transition, between frames, so nothing
observes a half-built level. A system with a run condition runs every frame it holds and needs a
"have I done this" flag, which is a state machine built inside a state machine.

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

### BV-STATE-14 [M] Scope an entity to a state with `DespawnOnExit`

Spawn level entities with `DespawnOnExit(Screen::Playing)` rather than writing a system that queries
and despawns them.

**Why:** the component travels with the entity, so one spawned by a plugin nobody remembers is still
cleaned up. A teardown system enumerates what to despawn and is correct until somebody spawns a kind
it does not list — a leak that survives into the next round.

**Check:** look at each `OnExit` system. If it is a query-and-despawn, the marker belongs on the
entities instead. Teardown that a state cannot express, on a condition rather than a transition, is
`commands.despawn_all::<F>()` or `despawn_all_where`: one batched command, not a loop of despawns.

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

### BV-STATE-15 [M] Write the next state through `NextState`, never `State`

`next.set(Screen::Menu)` on a `ResMut<NextState<Screen>>`. `State<S>` has no setter, but
`State::new` is public, so `*state = State::new(S)` through a `ResMut<State<S>>` compiles — and
changes the state with no `OnExit` and no `OnEnter`.

**Why:** the split makes transitions atomic: the request is recorded, and the transition schedules
run at a defined point with the old and new values both available. Writing the current state
directly changes it mid-frame, so half the frame's systems see one state and half the other.

**Check:** grep for `ResMut<State<`. There should be none.

```rust
// verified — BAD: it compiles, and the state moves without a transition
use bevy::prelude::*;

#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum Screen {
    #[default]
    Menu,
    Playing,
}

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct LevelBuilds(pub u32);

fn build_level(mut builds: ResMut<LevelBuilds>) {
    builds.0 += 1;
}

/// Replaces the current state mid-frame. `OnExit(Screen::Menu)` and
/// `OnEnter(Screen::Playing)` never run, so the level is never built.
fn start_playing(mut screen: ResMut<State<Screen>>) {
    *screen = State::new(Screen::Playing);
}

#[derive(Debug, Default)]
pub struct LevelPlugin;

impl Plugin for LevelPlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<Screen>()
            .init_resource::<LevelBuilds>()
            .add_systems(OnEnter(Screen::Playing), build_level)
            .add_systems(Update, start_playing);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::state::app::StatesPlugin;

    #[test]
    fn writing_the_state_skips_its_hooks() {
        let mut app = App::new();
        app.add_plugins((StatesPlugin, LevelPlugin));
        app.update();
        app.update();
        let screen = app.world().resource::<State<Screen>>();
        assert_eq!(screen.get(), &Screen::Playing);
        assert_eq!(app.world().resource::<LevelBuilds>().0, 0);
    }

    #[test]
    fn the_same_move_through_next_state_runs_them() {
        let mut app = App::new();
        app.add_plugins(StatesPlugin)
            .init_state::<Screen>()
            .init_resource::<LevelBuilds>()
            .add_systems(OnEnter(Screen::Playing), build_level);
        app.update();
        app.world_mut()
            .resource_mut::<NextState<Screen>>()
            .set(Screen::Playing);
        app.update();
        assert_eq!(app.world().resource::<LevelBuilds>().0, 1);
    }
}
```

### BV-STATE-16 [M] Guard a repeated `set` with `set_if_different`

`next.set(S)` runs `OnExit(S)` and `OnEnter(S)` even when the current state is already `S`. A
system that calls `set` every frame must use `set_if_different`. `NextState::set_if_neq` and its
relatives are the old spellings and no longer compile (BV-MIG-16); `Mut::set_if_neq` keeps its name.

**Why:** an unconditional `set` tears down and rebuilds the level every frame, and still compiles.
Re-entering a state is sometimes exactly what is wanted, which is why the guard has to be asked
for.

**Check:** for each `next.set(`, ask whether the surrounding code can run while already in that
state. If it can, it needs `set_if_different`. A `set_if_neq` on a `NextState` is the old
spelling.

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

/// The request goes through `NextState` and is applied in `StateTransition`, not
/// here. A plain `set` re-enters a state it is already in, so a system that asks
/// every frame asks with `set_if_different`, or it rebuilds the level every frame.
fn follow_run(run: Res<RunInProgress>, mut next: ResMut<NextState<Screen>>) {
    if run.0 {
        next.set_if_different(Screen::Playing);
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

### BV-STATE-17 [S] Keep a transition's work bounded

`OnEnter` runs between frames, so everything in it is a frame the player does not get. Spawn what
must exist; stream the rest.

**Why:** the transition is synchronous and uninterruptible, so a level built entirely in `OnEnter`
is a visible hitch that grows with the level. Letting the rest arrive over the following frames, or
behind a loading state's progress bar, keeps the hitch constant.

**Check:** time the transition on the slowest supported machine. Anything over a frame's budget
needs splitting.

### BV-STATE-18 [M] Do not assume a transition happens in the frame that requested it

`next.set(…)` records a request. The state has not changed when the next line runs: the transition
is applied in the `StateTransition` schedule, after `PreUpdate` and before `RunFixedMainLoop` and
`Update`.

**Why:** code that sets the state and then reads `State<S>` reads the old value, and so does
everything else in that schedule. Reading it in a later system instead works by accident, until
somebody changes the schedule.

**Check:** in each system that calls `set`, look for a subsequent read of `State<S>`. Move the
dependent work into `OnEnter`.
