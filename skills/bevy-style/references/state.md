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

- **Transitions**
  - BV-STATE-17 [M] Put setup in `OnEnter` and teardown in `OnExit`
  - BV-STATE-18 [M] Scope an entity to a state with `DespawnOnExit`
  - BV-STATE-19 [M] Write the next state through `NextState`, never `State`
  - BV-STATE-20 [M] Guard a repeated `set` with `set_if_different`
  - BV-STATE-21 [S] Keep a transition's work bounded
  - BV-STATE-22 [M] Do not assume a transition happens in the frame that requested it

---

## Resources

### BV-STATE-01 [M] Never make one type both a resource and a component

Since 0.19, `#[derive(Resource)]` implements `Component` as well. A type that needs to be both is
two types, as Bevy split its own `UiDebugOptions` into `GlobalUiDebugOptions` and `UiDebugOptions`.

**Why:** uniqueness belongs to the *type*: inserting a `Resource` type on an entity despawns the
copy on every other entity, and a resource shows up in ordinary `&T` queries, so a global fallback
and a per-entity override of one type silently become the same storage.

**Check:** grep for a `derive` naming both `Component` and `Resource`; it does not compile.
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

**Why:** a resource is one value for the whole world, and games grow second players, split screens
and preview worlds. Two systems touching the same resource also cannot run in parallel, where the
same data on entities would have been partitioned.

**Check:** ask whether there could ever be two. If the answer is not "no, by construction", it is a
component on an entity.

### BV-STATE-03 [M] Register a resource in the plugin that defines it

`app.init_resource::<Score>()` in `score`'s plugin, not in a central setup.

**Why:** it is BV-ARCH-14's commonest case: an uninitialised resource fails at first access, in
whichever system ran first, with an error naming the type but not the plugin that forgot it. Kept
with its definition, "did anyone register this?" is answered by reading one file.

**Check:** for each `#[derive(Resource)]`, find the `init_resource` or `insert_resource`. The two
should be in the same module.

### BV-STATE-04 [S] Give a resource `FromWorld` when its initial value depends on the world

A resource that needs an `AssetServer`, a registry, or another resource to build implements
`FromWorld`; `init_resource` then uses it.

**Why:** a startup system that inserts the resource is a second place the type is constructed, and
anything that runs before it finds nothing. `FromWorld` runs at registration, so the resource exists
from the first frame.

**Check:** grep for `insert_resource` in a `Startup` system. Each one is a `FromWorld` impl that has
not been written.

### BV-STATE-05 [M] Do not put mutable game state in a resource that a component could hold

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

### BV-STATE-06 [S] Make a read-only resource immutable

A resource written once at startup and only read afterwards can be `#[component(immutable)]`, which
since 0.19 makes `ResMut` unavailable for it.

**Why:** the type then states its own contract, and the compiler enforces it — a system that tries
to write gets an error rather than a review comment. It also removes the scheduling constraint: with
no writer possible, no two readers can conflict.

**Check:** for each resource, count the `ResMut<T>` uses. Zero means the type can say so.

### BV-STATE-07 [M] Read a resource with `Res`, and take `ResMut` only to write

`Res<Score>` to read. `ResMut<Score>` only in systems that assign.

**Why:** a system holding `ResMut` only to read still blocks every other system that touches the
resource while it runs. A mutable dereference also marks it changed, so `resource_changed` run
conditions fire every frame — BV-ECS-26 for resources.

**Check:** for each `ResMut`, find the write. If the body only reads, it is a `Res`.

### BV-STATE-08 [M] Reach for `Option<Res<T>>` where absence is expected

A resource that only exists in some states, or is inserted by another plugin that may not be
present, is `Option<Res<T>>`. `resource_exists` as a run condition is the other form, and the
better one when the answer is "do not run".

**Why:** a plain `Res<T>` whose resource is missing fails parameter validation, and the failure goes
to the fallback error handler rather than showing at the call site. The `Option` says in the
signature that absence is a case, and lets the body say what happens then.

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

`bevy_settings`'s `SettingsPlugin` (since 0.19) loads a resource from the platform's own preferences
directory at startup, and gives you two commands to write it back. It replaces the load system, the
path constant, and the serialisation between them — but not the decision of *when* to save. Three
things about it are not guessable:

- **Saving is explicit.** The plugin loads; it does not save. `commands.queue(SaveSettingsDeferred(
  Duration::from_secs_f32(0.5)))` debounces a write so a dragged slider does not hammer the disk,
  and `SaveSettingsSync::IfChanged` blocks until the write lands, which is what save-on-quit needs.
- **It is a reflected type, so BV-ECS-13 reaches it.** The derive list is
  `#[derive(Resource, SettingsGroup, Reflect, Default)]`; since 0.20 `SettingsGroup` is bounded by
  `Resource + Reflect + Default`, so a missing derive is a compile error. The attribute is
  `#[reflect(Resource, SettingsGroup, Default)]`, and since 0.20 a missing `#[reflect(Default)]` is
  a logged error.
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
resource that loads once and never persists a change. BV-STATE-09 still governs what goes in:
settings are configuration, so progress does not belong in the same type.

## States

### BV-STATE-11 [M] Model the phases of the game as a `States` enum

Menu, loading, playing, paused, game over. `#[derive(States)]` with `Default` on the first phase.

**Why:** run conditions, `OnEnter`/`OnExit` and entity scoping all key on the state, so a `bool`
phase gets no transition hooks, no automatic despawn, and no third phase without touching every
reader. An enum is exhaustive, so a new phase is a compile error everywhere it matters.

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

### BV-STATE-13 [S] Give loading its own state, not a flag

Asset loading is a phase: it has an entry, a progress condition, an exit, and a failure. That is a
state.

**Why:** as a state, one condition gates everything that must not run while loading, scoping
despawns the loading screen, and "loading failed" has somewhere to go. As a `bool`, each of those is
hand-written, and the failure case usually is not written at all.

**Check:** does the game have a `loaded: bool` or an `AssetsLoading` collection with a system that
checks it? That check is a run condition on a transition.

### BV-STATE-14 [S] Use `SubStates` for a phase that only exists inside another

Paused, inventory-open and dialogue-open exist only while playing. `#[derive(SubStates)]` with
`#[source(Screen = Screen::Playing)]` says so.

**Why:** a sub-state exists only while its source does, so "paused in the main menu" cannot be
represented, where two independent enums make it eventually real. Leaving the source runs the
sub-state's `OnExit`, which cleans up the pause overlay without anyone writing that code.

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

## Transitions

### BV-STATE-17 [M] Put setup in `OnEnter` and teardown in `OnExit`

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

### BV-STATE-18 [M] Scope an entity to a state with `DespawnOnExit`

Spawn level entities with `DespawnOnExit(Screen::Playing)` rather than writing a system that queries
and despawns them.

**Why:** the component travels with the entity, so one spawned by a plugin nobody remembers is still
cleaned up. A teardown system enumerates what to despawn and is correct until somebody spawns a kind
it does not list — a leak that survives into the next round.

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

**Why:** the split makes transitions atomic: the request is recorded, and the transition schedules
run at a defined point with the old and new values both available. Writing the current state
directly changes it mid-frame, so half the frame's systems see one state and half the other.

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
/// `set_if_different`, or it rebuilds the level every frame.
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

### BV-STATE-20 [M] Guard a repeated `set` with `set_if_different`

Since 0.18, `next.set(S)` runs `OnExit(S)` and `OnEnter(S)` even when the current state is already
`S`. A system that calls `set` every frame must use `set_if_different`. 0.20 renamed it from
`NextState::set_if_neq`, along with `PendingIfNeq` → `PendingIfDifferent`,
`CommandsStatesExt::set_state_if_neq` → `set_state_if_different` and
`ReflectFreelyMutableState::set_next_state_if_neq` → `set_next_state_if_different`; the old names
are deprecated, and the shipped CI denies the warning. `Mut::set_if_neq` keeps its name.

**Why:** an unconditional `set` that was a no-op when the state matched now tears down and rebuilds
the level, every frame, and still compiles. Re-entering a state is sometimes exactly what is wanted,
which is why the old behaviour has to be asked for.

**Check:** for each `next.set(`, ask whether the surrounding code can run while already in that
state. If it can, it needs `set_if_different`. A `set_if_neq` on a `NextState` is the deprecated
spelling.

### BV-STATE-21 [S] Keep a transition's work bounded

`OnEnter` runs between frames, so everything in it is a frame the player does not get. Spawn what
must exist; stream the rest.

**Why:** the transition is synchronous and uninterruptible, so a level built entirely in `OnEnter`
is a visible hitch that grows with the level. Letting the rest arrive over the following frames, or
behind a loading state's progress bar, keeps the hitch constant.

**Check:** time the transition on the slowest supported machine. Anything over a frame's budget
needs splitting.

### BV-STATE-22 [M] Do not assume a transition happens in the frame that requested it

`next.set(…)` records a request. The state has not changed when the next line runs: the transition
is applied in the `StateTransition` schedule, after `PreUpdate` and before `RunFixedMainLoop` and
`Update`.

**Why:** code that sets the state and then reads `State<S>` reads the old value, and so does
everything else in that schedule. Reading it in a later system instead works by accident, until
somebody changes the schedule.

**Check:** in each system that calls `set`, look for a subsequent read of `State<S>`. Move the
dependent work into `OnEnter`.
