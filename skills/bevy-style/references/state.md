# State: Resources, States, Transitions, Scoping

Scope: global data that is not attached to an entity, the state machine that decides which parts of
the game are running, and how things are cleaned up when it moves. Bevy 0.19 made `Resource` a
subtrait of `Component`, which changes what a resource may be. Components are in the ECS chapter;
gating a system on a state is in the scheduling chapter.

## Contents

- **Resources**
  - BV-STA-01 [M] Never make one type both a resource and a component
  - BV-STA-02 [M] Reserve a resource for what is genuinely global
  - BV-STA-03 [M] Register a resource in the plugin that defines it
  - BV-STA-04 [S] Give a resource `FromWorld` when its initial value depends on the world
  - BV-STA-05 [M] Do not put mutable game state in a resource that a component could hold
  - BV-STA-06 [S] Make a read-only resource immutable
  - BV-STA-07 [M] Read a resource with `Res`, and take `ResMut` only to write
  - BV-STA-08 [M] Reach for `Option<Res<T>>` where absence is expected
  - BV-STA-09 [S] Keep configuration and progress in separate resources

- **States**
  - BV-STA-10 [M] Model the phases of the game as a `States` enum
  - BV-STA-11 [M] Derive a dependent state rather than keeping two in step
  - BV-STA-12 [S] Give loading its own state, not a flag
  - BV-STA-13 [S] Use `SubStates` for a phase that only exists inside another
  - BV-STA-14 [M] Register every state exactly once
  - BV-STA-15 [M] Do not branch on `State<S>` inside a system body (see BV-SCH-20)

- **Transitions**
  - BV-STA-16 [M] Put setup in `OnEnter` and teardown in `OnExit`
  - BV-STA-17 [M] Scope an entity to a state with `DespawnOnExit`
  - BV-STA-18 [M] Write the next state through `NextState`, never `State`
  - BV-STA-19 [M] Guard a repeated `set` with `set_if_neq`
  - BV-STA-20 [S] Keep a transition's work bounded
  - BV-STA-21 [M] Do not assume a transition happens in the frame that requested it

---

## Resources

### BV-STA-01 [M] Never make one type both a resource and a component

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

#[derive(Component, Debug)]
struct Velocity(Vec3);

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

### BV-STA-02 [M] Reserve a resource for what is genuinely global

Score, elapsed round time, the current wave, a settings block, a handle table. Not "the player's
health", and not a `Vec` of things that are really entities.

**Why:** a resource is one value for the whole world, so anything stored in one can never have two
of it — and games grow second players, split screens, and preview worlds. It is also invisible to
the query planner: two systems touching the same resource cannot run in parallel, where the same
data on entities would have been partitioned.

**Check:** ask whether there could ever be two. If the answer is not "no, by construction", it is a
component on an entity.

### BV-STA-03 [M] Register a resource in the plugin that defines it

`app.init_resource::<Score>()` in `score`'s plugin, not in a central setup.

**Why:** it is BV-ARC-14 with the case that bites most often: a resource that is never initialised
does not fail to compile, it fails at first access, in whichever system happened to run first — and
the error names the type but not the plugin that forgot it. Keeping initialisation with definition
makes "did anyone register this?" answerable by reading one file.

**Check:** for each `#[derive(Resource)]`, find the `init_resource` or `insert_resource`. The two
should be in the same module.

### BV-STA-04 [S] Give a resource `FromWorld` when its initial value depends on the world

A resource that needs an `AssetServer`, a registry, or another resource to build implements
`FromWorld`; `init_resource` then uses it.

**Why:** the alternative is a startup system that inserts the resource, which is a second place the
type is constructed and an ordering problem for everything that reads it — anything running before
that system finds nothing. `FromWorld` runs at registration, so the resource exists from the first
frame.

**Check:** grep for `insert_resource` in a `Startup` system. Each one is a `FromWorld` impl that has
not been written.

### BV-STA-05 [M] Do not put mutable game state in a resource that a component could hold

A `Vec<Enemy>` in a resource is a set of entities that has not been spawned.

**Why:** collections in resources give up everything the ECS provides: no queries, no change
detection per item, no parallel iteration, no relationships, no reflection of the individual items,
and no despawn. They also serialise every system that touches the collection against every other.
The usual sign is a resource whose fields are all `Vec` or `HashMap` keyed by something entity-like.

**Check:** for each collection in a resource, ask what the elements are. If they have identity and a
lifetime, they are entities.

### BV-STA-06 [S] Make a read-only resource immutable

A resource written once at startup and only read afterwards can be `#[component(immutable)]`, which
in 0.19 makes `ResMut` unavailable for it.

**Why:** the type then states its own contract, and the compiler enforces it — a system that tries
to write gets an error rather than a review comment. It also removes the scheduling constraint: with
no writer possible, no two readers can conflict.

**Check:** for each resource, count the `ResMut<T>` uses. Zero means the type can say so.

### BV-STA-07 [M] Read a resource with `Res`, and take `ResMut` only to write

`Res<Score>` to read. `ResMut<Score>` only in systems that assign.

**Why:** `ResMut` is an exclusive lock for the whole schedule, so a system holding one for reading
blocks every other system that touches that resource for as long as it runs. Dereferencing it
mutably also marks the resource changed, which makes `resource_changed` run conditions fire every
frame — the resource-level version of BV-ECS-25.

**Check:** for each `ResMut`, find the write. If the body only reads, it is a `Res`.

### BV-STA-08 [M] Reach for `Option<Res<T>>` where absence is expected

A resource that only exists in some states, or is inserted by another plugin that may not be
present, is `Option<Res<T>>`.

**Why:** a plain `Res<T>` whose resource is missing makes the system fail parameter validation, and
in 0.19 that failure goes to the fallback error handler rather than being visible at the call site.
The `Option` form says in the signature that absence is a case, and lets the body say what happens
then. `resource_exists` as a run condition is the other form and is better when the answer is
"do not run".

**Check:** for each `Res<T>`, ask when `T` is inserted relative to this system. Anything conditional
needs the `Option` or a run condition.

### BV-STA-09 [S] Keep configuration and progress in separate resources

`CombatSettings` is written by the settings screen and read by the simulation; `CombatProgress` is
written by the simulation every frame. They are not one `Combat` resource.

**Why:** change detection and scheduling both key on the resource, so mixing them means every
progress tick marks the settings changed and every reader of settings is blocked by the simulation's
writer. It is BV-ECS-02 for resources, and the same test applies.

**Check:** for each resource, list the systems that write each field. Fields with disjoint writers
are separate resources.

## States

### BV-STA-10 [M] Model the phases of the game as a `States` enum

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

### BV-STA-11 [M] Derive a dependent state rather than keeping two in step

If "is the world simulating" is a function of the screen and the pause flag, it is a
`ComputedStates` impl, not a third state somebody has to remember to set.

**Why:** two states that must agree will disagree — some path sets one and returns early, and the
game is left simulating behind a menu. A computed state is recalculated from its sources on every
transition, so the invariant is maintained by construction rather than by every author of every
transition.

**Check:** for each pair of states, ask whether one is a function of the other. If yes, and both are
set by hand, that is the bug waiting.

### BV-STA-12 [S] Give loading its own state, not a flag

Asset loading is a phase: it has an entry, a progress condition, an exit, and a failure. That is a
state.

**Why:** as a state, everything that must not run during loading is gated by one condition, the
loading screen's entities are despawned by scoping rather than by a bespoke system, and "loading
failed" has somewhere to go. As a `bool`, each of those is hand-written and the failure case usually
is not written at all.

**Check:** does the game have a `loaded: bool` or an `AssetsLoading` collection with a system that
checks it? That check is a run condition on a transition.

### BV-STA-13 [S] Use `SubStates` for a phase that only exists inside another

Paused, inventory-open and dialogue-open exist only while playing. `#[derive(SubStates)]` with
`#[source(Screen = Screen::Playing)]` says so.

**Why:** a sub-state is created on entering its source and removed on leaving, so "paused in the
main menu" is not representable — where two independent enums make it representable and therefore
eventually real. The removal also runs the sub-state's `OnExit`, which is where the pause overlay
gets cleaned up without anyone writing that code.

**Check:** for each state, ask whether every variant is meaningful in every variant of every other
state. Where it is not, one is a sub-state of the other.

### BV-STA-14 [M] Register every state exactly once

`init_state` for a root state, `add_sub_state` for a sub-state, `add_computed_state` for a computed
one — each called once, in the plugin that defines the type.

**Why:** registering twice installs the transition systems twice, so every `OnEnter` runs twice per
transition. Registering with the wrong function is worse: `init_state` on a type meant to be a
sub-state gives it an independent life, and the `#[source]` relationship silently does nothing.

**Check:** grep each state type name. Exactly one registration call, and its kind matches the
derive.

### BV-STA-15 [M] Do not branch on `State<S>` inside a system body (see BV-SCH-20)

Owned by `references/scheduling.md` BV-SCH-20. A comparison against `State<S>` in a body is a
run condition that has been written as an `if`, and the system still pays for every parameter it
declared.

## Transitions

### BV-STA-16 [M] Put setup in `OnEnter` and teardown in `OnExit`

`app.add_systems(OnEnter(Screen::Playing), spawn_level)` and the matching `OnExit`.

**Why:** the transition schedules run exactly once per transition, between the frames, so nothing
observes a half-built level. The alternative — a `Startup`-style system with a run condition — runs
every frame the condition holds and needs its own "have I done this" flag, which is a state machine
built inside a state machine.

**Check:** grep for `run_once` and for `Local<bool>` used as a "did setup" flag. Each is an
`OnEnter` system.

### BV-STA-17 [M] Scope an entity to a state with `DespawnOnExit`

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

#[derive(Component, Debug)]
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

### BV-STA-18 [M] Write the next state through `NextState`, never `State`

`next.set(Screen::Menu)` on a `ResMut<NextState<Screen>>`. `State<S>` is read-only by design.

**Why:** the split is what makes transitions atomic: the request is recorded, and the transition
schedules run at a defined point with the old and new values both available. Writing the current
state directly — where an API allows it — changes it mid-frame, so half the systems in that frame
see one state and half see the other.

**Check:** grep for `ResMut<State<`. There should be none.

### BV-STA-19 [M] Guard a repeated `set` with `set_if_neq`

Since 0.18, `next.set(S)` runs `OnExit(S)` and `OnEnter(S)` even when the current state is already
`S`. A system that calls `set` every frame must use `set_if_neq`.

**Why:** this changed underneath existing code and does not affect whether it compiles. Code that
called `set` unconditionally used to be a no-op when the state matched; now it tears down and
rebuilds the level, every frame. The new behaviour is deliberate — re-entering a state is sometimes
exactly what is wanted — which is why the old behaviour has to be asked for.

**Check:** for each `next.set(`, ask whether the surrounding code can run while already in that
state. If it can, it needs `set_if_neq`.

### BV-STA-20 [S] Keep a transition's work bounded

`OnEnter` runs between frames, so everything in it is a frame the player does not get. Spawn what
must exist; stream the rest.

**Why:** the transition is synchronous and uninterruptible, so a level built entirely in `OnEnter`
is a visible hitch whose length grows with the level. Spawning the essentials there and letting the
rest arrive over the following frames — or during a loading state with a progress bar — keeps the
hitch constant.

**Check:** time the transition on the slowest supported machine. Anything over a frame's budget
needs splitting.

### BV-STA-21 [M] Do not assume a transition happens in the frame that requested it

`next.set(…)` records a request. The state has not changed when the next line runs.

**Why:** the transition is applied by the state transition systems, which run in the
`StateTransition` schedule — after `PreUpdate` and before `RunFixedMainLoop` and `Update`. Code that
sets the state and then reads `State<S>` in the same system reads the old value, and so does
anything else in that schedule. The usual "fix" is to read it in a later system, which works by
accident until somebody changes the schedule.

**Check:** in each system that calls `set`, look for a subsequent read of `State<S>`. Move the
dependent work into `OnEnter`.
