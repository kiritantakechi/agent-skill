# Scheduling: Schedules, Sets, Ordering, Run Conditions, Time

Scope: which schedule a system belongs in, how systems are ordered relative to one another, how a
system is prevented from running, and where the frame's elapsed time comes from. What a system
*reads* is in the ECS chapter; state transitions are in the state chapter; reacting to a single
event is in the events chapter.

## Contents

- **Schedules**
  - BV-SCHED-01 [M] Simulate in `FixedUpdate`, present in `Update`
  - BV-SCHED-02 [S] Pick a schedule deliberately, from the whole list
  - BV-SCHED-03 [S] Keep `Startup` to what must exist before the first frame
  - BV-SCHED-04 [M] Never move a camera from `FixedUpdate`
  - BV-SCHED-05 [S] Derive from this frame's transforms in `PostUpdate`
  - BV-SCHED-06 [M] Take the delta from the schedule's own clock
  - BV-SCHED-07 [M] Never assume `FixedUpdate` ran exactly once this frame
  - BV-SCHED-08 [S] Interpolate between fixed steps rather than raising the rate
  - BV-SCHED-09 [M] Never read per-frame input from a fixed-rate schedule

- **Systems**
  - BV-SCHED-10 [M] Group system parameters once there are more than seven
  - BV-SCHED-11 [S] Make a system a step in the frame, not a container for code
  - BV-SCHED-12 [M!] Express ordering through named sets
  - BV-SCHED-13 [M] Configure a set once and join it at each system
  - BV-SCHED-14 [M] Never order a system against another system's function
  - BV-SCHED-15 [S] Keep `chain` to a short pipeline inside one plugin
  - BV-SCHED-16 [M] Add each system to each schedule exactly once

- **Run conditions**
  - BV-SCHED-17 [M] Express a precondition as a run condition, not an early return
  - BV-SCHED-18 [S] Compose the conditions Bevy ships before writing one
  - BV-SCHED-19 [M] Keep a run condition free of effects
  - BV-SCHED-20 [S] Put a shared condition on the set, not on every member
  - BV-SCHED-21 [M] Gate on state with `in_state`, not by reading `State<S>`

- **Sync points and parallelism**
  - BV-SCHED-22 [M] Let the schedule insert its own sync points
  - BV-SCHED-23 [S] Answer an ambiguity warning by ordering, not by silencing it
  - BV-SCHED-24 [S] Leave the executor alone
  - BV-SCHED-25 [M] Keep `Local<T>` to state no other system needs

- **Time control**
  - BV-SCHED-26 [M] Pause and scale the game through `Time<Virtual>`, not a flag

---

## Schedules

### BV-SCHED-01 [M] Simulate in `FixedUpdate`, present in `Update`

Physics, damage, economy, AI decisions and anything else that changes the game state run in
`FixedUpdate`. Input sampling, animation, camera work, UI and anything a player perceives as smooth
run in `Update`.

**Why:** `FixedUpdate` runs at a fixed rate whatever the frame rate; `Update` runs once per rendered
frame. Simulation in `Update` makes the game a function of the player's hardware: different damage
totals and jump heights on a 30 Hz laptop and a 240 Hz desktop.

**Check:** for each system, ask whether running it twice as often would change what the game does.
If yes it is simulation; if it only changes how smooth something looks it is presentation.

### BV-SCHED-02 [S] Pick a schedule deliberately, from the whole list

`Update` is not the default; it is one entry in a documented order. Each `App::update` runs
`First`, `PreUpdate`, `StateTransition`, `RunFixedMainLoop`, `Update`, `SpawnScene`, `PostUpdate`,
`Last` — and inside the fixed loop, `FixedFirst` … `FixedLast`.

**Why:** most `.before()` and `.after()` calls really mean "this belongs in `PreUpdate`". Input
processed in `PreUpdate` precedes every consumer without naming one, and cleanup in `Last` follows
everything without a list that goes stale.

**Check:** for each `.before()` or `.after()` that names a system in another plugin, ask which
bracket schedule expresses the same thing. Usually one does.

### BV-SCHED-03 [S] Keep `Startup` to what must exist before the first frame

Cameras, the window's initial state, resources whose absence would crash frame one. Asset loading
and world generation are jobs with a duration, and belong to a loading state.

**Why:** `Startup` runs once, synchronously, before the first frame is drawn, so everything in it is
time the player spends looking at nothing. Loading is also fallible and progressive — it wants a
progress bar, a retry and a state transition, none of which a `Startup` system can express.

**Check:** for each `Startup` system, ask how long it takes on the slowest supported machine. If the
answer is "depends on the disk", it belongs in a loading state
(`references/state.md` BV-STATE-13).

### BV-SCHED-04 [M] Never move a camera from `FixedUpdate`

Camera transforms are written in `Update` (or `PostUpdate`), following the target that `FixedUpdate`
moved.

**Why:** `FixedUpdate` does not run on every rendered frame. A camera moved there holds still on the
frames where it did not run and jumps on those where it ran twice: stutter on precisely the object
the player's eye is locked to.

**Check:** search `FixedUpdate` systems for `With<Camera>`, `Camera2d`, `Camera3d` and any query
that could match the camera entity. Follow the target in `Update` instead.

### BV-SCHED-05 [S] Derive from this frame's transforms in `PostUpdate`

Anything reading `GlobalTransform` — visibility, spatial indexing, a screen-space overlay — runs in
`PostUpdate`, after `TransformSystems::Propagate`.

**Why:** `GlobalTransform` is computed from `Transform` by a propagation system in `PostUpdate`.
Read it earlier and it holds the previous frame's value, which is not an error and not visible in a
screenshot — it is one frame of lag that only shows up when something moves fast.

**Check:** find every `&GlobalTransform` in the codebase and check the schedule. Anything in
`Update` is reading last frame.

### BV-SCHED-06 [M] Take the delta from the schedule's own clock

`Res<Time>` in `Update`, `Res<Time<Fixed>>` in `FixedUpdate`. Never a hard-coded step, and never
`Time<Real>` for gameplay: it ignores pause and time scaling, so gameplay driven by it keeps running
while the game is paused.

Plain `Res<Time>` is the portable form, because the fixed loop swaps the default clock to
`Time<Fixed>` for each step and back to `Time<Virtual>` afterwards. Naming `Time<Fixed>` buys
clarity at the cost of that portability; make the trade deliberately.

`commands.delayed().secs(t)`, since 0.19, replaces a `Timer` whose only job is to postpone, and it
belongs to the frame clock: its queue is checked in `PreUpdate` against `Res<Time>`. Use it for
presentation — a despawn after a hit flash, a delayed sound. Anything a replay or a lockstep peer
has to reproduce keeps a `Timer` ticked by `Time<Fixed>`.

**Why:** `Time<Fixed>::delta` is the fixed step in every schedule, so a system naming it, moved to
`Update`, advances one fixed step per rendered frame. A `delayed` deadline queued in the fixed loop
is stamped from `Time<Fixed>` but checked against `Time<Virtual>`, so it fires up to one step early.

**Check:** grep for `1.0 / 60.0` and similar literals, for `Time<Real>` outside diagnostics, and for
`.delayed(` inside a `FixedUpdate` system — the last is a simulation decision made on the frame
clock.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Velocity(pub Vec3);

/// Fixed step: the clock is the fixed one, and the result is frame-rate independent.
fn integrate(mut bodies: Query<(&mut Transform, &Velocity)>, time: Res<Time<Fixed>>) {
    let dt = time.delta_secs();
    for (mut transform, velocity) in &mut bodies {
        transform.translation += velocity.0 * dt;
    }
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Spinner;

/// Presentation: the clock is the frame clock, and the result is as smooth as the display.
fn spin(mut spinners: Query<&mut Transform, With<Spinner>>, time: Res<Time>) {
    for mut transform in &mut spinners {
        transform.rotate_z(time.delta_secs());
    }
}
```

### BV-SCHED-07 [M] Never assume `FixedUpdate` ran exactly once this frame

In one frame the fixed schedule may run zero times, once, or several. A `FixedUpdate` system must be
correct for all three: it accumulates into a resource that `Update` then reads and clears.

**Why:** the fixed loop catches up after a long frame by running repeatedly, and skips a short one
entirely. Code written as "once per frame" breaks both ways: a message written per step arrives in
bursts, and a counter incremented there is not a frame counter.

**Check:** for each `FixedUpdate` system, ask what running it three times in a row would do. If the
answer is wrong, it is assuming a frame.

```rust
// verified
use bevy::prelude::*;
use bevy::time::{TimePlugin, TimeUpdateStrategy};

/// One fixed step's worth. The step is the unit of simulation; the frame is not.
const DAMAGE_PER_STEP: u32 = 1;

/// The accumulator. However many steps ran, each one adds its own share.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct PendingDamage(pub u32);

/// What the frame reads: the damage of every step since the frame last looked.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct DamageThisFrame(pub u32);

/// The shape that assumes a frame, kept so the test can catch it lying.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct LatestStepDamage(pub u32);

/// Correct for zero runs, one run and three: each run adds its own step.
fn accumulate_damage(mut pending: ResMut<PendingDamage>) {
    pending.0 += DAMAGE_PER_STEP;
}

/// Wrong in both directions: three steps still report one, and a frame with no
/// step at all reports whatever the last step left behind.
fn overwrite_damage(mut latest: ResMut<LatestStepDamage>) {
    latest.0 = DAMAGE_PER_STEP;
}

/// Runs once per frame, and leaves the accumulator empty for the next one.
fn drain_damage(mut pending: ResMut<PendingDamage>, mut frame: ResMut<DamageThisFrame>) {
    frame.0 = core::mem::take(&mut pending.0);
}

#[derive(Debug, Default)]
pub struct DamagePlugin;

impl Plugin for DamagePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<PendingDamage>()
            .init_resource::<DamageThisFrame>()
            .init_resource::<LatestStepDamage>()
            .add_systems(FixedUpdate, (accumulate_damage, overwrite_damage))
            .add_systems(Update, drain_damage);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `(accumulated, overwritten)` as the frame sees them.
    fn reported(app: &App) -> (u32, u32) {
        (
            app.world().resource::<DamageThisFrame>().0,
            app.world().resource::<LatestStepDamage>().0,
        )
    }

    #[test]
    fn one_frame_may_hold_zero_steps_one_step_or_three() {
        let step = Time::<Fixed>::default().timestep();
        let mut app = App::new();
        app.add_plugins((TimePlugin, DamagePlugin))
            .insert_resource(TimeUpdateStrategy::ManualDuration(step * 3));

        // No virtual time has elapsed yet, so the fixed schedule does not run.
        app.update();
        assert_eq!(reported(&app), (0, 0));

        // Three steps in one frame: the accumulator has all three, the
        // assignment kept only the last.
        app.update();
        assert_eq!(reported(&app), (3, 1));

        // One step, and the previous frame's three are not counted again.
        app.insert_resource(TimeUpdateStrategy::ManualDuration(step));
        app.update();
        assert_eq!(reported(&app), (1, 1));

        // A frame too short for a step. "Nothing happened" is the truth; the
        // assignment still reports a hit that landed two frames ago.
        app.insert_resource(TimeUpdateStrategy::ManualDuration(step / 2));
        app.update();
        assert_eq!(reported(&app), (0, 1));
    }
}
```

### BV-SCHED-08 [S] Interpolate between fixed steps rather than raising the rate

When fixed-step motion looks choppy, render an interpolated position in `Update` using
`Time<Fixed>::overstep_fraction`. Raising the fixed rate is a last resort.

**Why:** raising the rate multiplies the cost of the entire simulation to fix a presentation
problem, and it does not actually remove the artefact — it makes it smaller and moves it to a higher
frame rate. Interpolation costs one lerp per rendered entity and is exact.

**Check:** has the fixed timestep been raised above 64 Hz? If so, what measurement said the
simulation needed it rather than the picture?

### BV-SCHED-09 [M] Never read per-frame input from a fixed-rate schedule

`ButtonInput::just_pressed` and `just_released` are true for exactly one rendered frame. A
`FixedUpdate` system may not run on that frame, or may run on it twice. Sample input at frame rate
in `RunFixedMainLoopSystems::BeforeFixedMainLoop`, which runs before the fixed loop that reads what
it wrote; accumulate the intent; and let the fixed step consume the accumulation.

Accumulating is also where input stops being input. A `bool` named `jump_requested` is a decision
the domain can take, replay, rebind and test; a `KeyCode` is a keyboard (BV-ARCH-01).

**Why:** input handled in `FixedUpdate`, where BV-SCHED-01 sends simulation, drops jumps on a fast
machine and double-fires them on a slow one, with no error and nothing in a log. The two failures
look nothing alike, so neither points at the cause.

**Check:** grep `FixedUpdate` systems for `ButtonInput`, `just_pressed`, `just_released` and
`AccumulatedMouseMotion`. Each is a press the game will miss.

```rust
// verified
use bevy::prelude::*;

/// What the simulation acts on. No keyboard in sight.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Intent {
    pub jump: bool,
}

/// Frame rate, before the fixed loop: a press on any frame survives to the next step.
fn sample(keys: Res<ButtonInput<KeyCode>>, mut intent: ResMut<Intent>) {
    intent.jump |= keys.just_pressed(KeyCode::Space);
}

/// Fixed rate: consumes the accumulation, so one press is one jump.
fn jump(mut intent: ResMut<Intent>, mut jumps: ResMut<Jumps>) {
    if core::mem::take(&mut intent.jump) {
        jumps.0 += 1;
    }
}

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Jumps(pub u32);

#[derive(Debug, Default)]
pub struct InputPlugin;

impl Plugin for InputPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Intent>()
            .init_resource::<Jumps>()
            .add_systems(
                RunFixedMainLoop,
                sample.in_set(RunFixedMainLoopSystems::BeforeFixedMainLoop),
            )
            .add_systems(FixedUpdate, jump);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_press_at_frame_rate_reaches_the_fixed_step_exactly_once() {
        let mut app = App::new();
        app.add_plugins(InputPlugin)
            .init_resource::<ButtonInput<KeyCode>>();
        app.world_mut()
            .resource_mut::<ButtonInput<KeyCode>>()
            .press(KeyCode::Space);

        app.world_mut().run_schedule(RunFixedMainLoop);
        assert!(
            app.world().resource::<Intent>().jump,
            "sampled at frame rate"
        );

        app.world_mut().run_schedule(FixedUpdate);
        assert_eq!(app.world().resource::<Jumps>().0, 1);

        app.world_mut().run_schedule(FixedUpdate);
        assert_eq!(
            app.world().resource::<Jumps>().0,
            1,
            "a second step is not a second jump"
        );
    }
}
```

## Systems

### BV-SCHED-10 [M] Group system parameters once there are more than seven

Bundle related parameters into a `#[derive(SystemParam)]` struct named for what they are together.
`clippy::too_many_arguments` stays switched on (BV-BUILD-14), and this grouping is its compliant
form, never a suppression.

**Why:** the parameter list is the system's whole interface, and past about seven entries a reader
cannot hold it. The group is also reusable: three systems needing the same four combat parameters
take one `Combat<'w, 's>` instead of repeating the list.

**Check:** count the parameters. Past seven, look for the subset that shares a subject and give it a
name.

```rust
// verified
use bevy::ecs::system::SystemParam;
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Health(pub f32);

#[derive(Resource, Debug, Default)]
struct Score(u32);

/// The four parameters combat systems always take, named once.
#[derive(SystemParam)]
struct Combat<'w, 's> {
    commands: Commands<'w, 's>,
    healths: Query<'w, 's, (Entity, &'static mut Health)>,
    score: ResMut<'w, Score>,
    time: Res<'w, Time>,
}

fn decay(mut combat: Combat) {
    let dt = combat.time.delta_secs();
    for (entity, mut health) in &mut combat.healths {
        health.0 -= dt;
        if health.0 <= 0.0 {
            combat.score.0 += 1;
            combat.commands.entity(entity).despawn();
        }
    }
}
```

### BV-SCHED-11 [S] Make a system a step in the frame, not a container for code

A system is named for the step it performs — `apply_damage`, `spawn_waves` — and does that one
thing. A system doing three things is three systems.

**Why:** the system is the unit of scheduling, so work fused into one system cannot be ordered,
gated or parallelised separately. It is also the unit a profiler reports, so a fused system is a
single opaque bar where three would have told you which part is slow.

**Check:** write the system's name as a sentence. If it needs an "and", split it.

### BV-SCHED-12 [M!] Express ordering through named sets

Systems that must run in a particular order join `SystemSet`s, and the sets are ordered once.

*Relaxed form:* two systems in one plugin, added in one call, may be ordered with `.chain()` — see
BV-SCHED-15 for the boundary.

**Why:** a set names a phase — "input, then decisions, then resolution" — so a new system joins a
phase without anyone editing an ordering graph. Pairwise ordering needs every added system related
to every existing one, and writes the graph in several places at once.

**Check:** count the `.before(` and `.after(` calls. Past a handful, they are describing phases that
have not been named.

```rust
// verified
use bevy::prelude::*;

/// The phases of a combat frame. Named once, ordered once.
#[derive(SystemSet, Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CombatSystems {
    Intent,
    Resolve,
    Cleanup,
}

fn choose_targets() {}
fn apply_damage() {}
fn despawn_dead() {}

#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.configure_sets(
            FixedUpdate,
            (
                CombatSystems::Intent,
                CombatSystems::Resolve,
                CombatSystems::Cleanup,
            )
                .chain(),
        )
        .add_systems(
            FixedUpdate,
            (
                choose_targets.in_set(CombatSystems::Intent),
                apply_damage.in_set(CombatSystems::Resolve),
                despawn_dead.in_set(CombatSystems::Cleanup),
            ),
        );
    }
}
```

### BV-SCHED-13 [M] Configure a set once and join it at each system

`configure_sets` appears once per set per schedule, in the plugin that defines the set. Systems say
`.in_set(…)` and nothing more.

**Why:** a set configured in two plugins has two orderings, and the schedule builder merges them
into a graph nobody wrote. Keeping the configuration with the definition also means a reader wanting
to know what "Resolve" runs after has exactly one place to look.

**Check:** grep for each set name. It should appear in `configure_sets` once, and in `.in_set(…)`
everywhere else.

```rust
// verified
use bevy::prelude::*;

/// The phases of a combat round. `CombatPlugin` defines this enum and orders it
/// once; every other plugin only ever says `.in_set(…)`.
#[derive(SystemSet, Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CombatSystems {
    Resolve,
    Reward,
    Cleanup,
}

/// Each system records that it ran, so the test can read the order back.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct RoundLog(pub Vec<&'static str>);

fn apply_damage(mut log: ResMut<RoundLog>) {
    log.0.push("apply_damage");
}

fn despawn_dead(mut log: ResMut<RoundLog>) {
    log.0.push("despawn_dead");
}

/// Lives in another plugin and knows one thing: the name of a phase.
fn drop_loot(mut log: ResMut<RoundLog>) {
    log.0.push("drop_loot");
}

#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<RoundLog>()
            // The only `configure_sets` for these sets in this schedule.
            .configure_sets(
                FixedUpdate,
                (
                    CombatSystems::Resolve,
                    CombatSystems::Reward,
                    CombatSystems::Cleanup,
                )
                    .chain(),
            )
            .add_systems(
                FixedUpdate,
                (
                    apply_damage.in_set(CombatSystems::Resolve),
                    despawn_dead.in_set(CombatSystems::Cleanup),
                ),
            );
    }
}

/// A separate plugin joining a phase it did not define: no second
/// `configure_sets`, no `.before(…)`, and nothing to revisit when combat grows
/// a fourth phase.
#[derive(Debug, Default)]
pub struct LootPlugin;

impl Plugin for LootPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(FixedUpdate, drop_loot.in_set(CombatSystems::Reward));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_joining_plugin_lands_inside_the_owner_s_order() {
        let mut app = App::new();
        // Deliberately the wrong way round. The ordering lives in one place, so
        // the order the plugins were added in cannot reach it.
        app.add_plugins((LootPlugin, CombatPlugin));

        app.world_mut().run_schedule(FixedUpdate);

        let log = &app.world().resource::<RoundLog>().0;
        let at = |name: &str| log.iter().position(|entry| *entry == name);
        assert_eq!(at("apply_damage"), Some(0), "Resolve is first");
        assert_eq!(at("drop_loot"), Some(1), "the guest sits in Reward");
        assert_eq!(at("despawn_dead"), Some(2), "Cleanup is last");
    }
}
```

### BV-SCHED-14 [M] Never order a system against another system's function

`.after(damage_systems::apply)` names a function. `.after(CombatSystems::Resolve)` names a phase.

**Why:** the function is the other plugin's implementation detail: renaming, splitting or replacing
it breaks the caller, as a compile error at best and a silently dropped ordering at worst. A set is
the published interface; a function name is not.

**Check:** each `.before(` and `.after(` argument should be a `SystemSet` variant. A path to a `fn`
is a dependency on a neighbour's internals.

### BV-SCHED-15 [S] Keep `chain` to a short pipeline inside one plugin

`(a, b, c).chain()` is right when the three are one pipeline, defined together, and nothing outside
needs to slot in between them. Where only data dependencies matter, `chain_weak()`, `before_weak()`
and `after_weak()` keep an order only between systems that actually conflict.

0.20 made the engine's own set chains weak: `PostUpdate`'s `UiSystems`, and the system sets of the
`Render`, `RenderGraph`, `Core2d`, `Core3d` and `ExtractSchedule` schedules. A game system that
joins one of those sets and depends on a neighbour through a channel, an atomic, interior mutability
or `NonSend` states that ordering itself, with `.before(…)` or `.after(…)` on the set it depends on.

**Why:** `chain` is ordering without names, so nothing outside the plugin can slot between `b` and
`c` or name a position in it. A weak edge holds only where the ECS sees a conflict, so ordering that
rested on state it cannot see is gone, and the race that follows compiles and logs nothing.

**Check:** does anything outside this plugin need to run between two chained systems? If so, the
chain needs to become sets. For each system placed in `UiSystems` or a render set, look for state it
shares with a neighbour outside the ECS; an order that state needs must be written down.

### BV-SCHED-16 [M] Add each system to each schedule exactly once

A system added twice to the same schedule runs twice.

**Why:** there is no error and no warning; the game just applies damage twice, or moves twice as
fast. The usual cause is a plugin added twice (BV-ARCH-12), or a system added both individually and
as part of a tuple during a refactor.

**Check:** grep for the system's name across the crate. More than one `add_systems` mentioning it,
in the same schedule, is a duplicate.

## Run conditions

### BV-SCHED-17 [M] Express a precondition as a run condition, not an early return

`system.run_if(condition)`, not an `if !ready { return; }` at the top of the body.

**Why:** the scheduler evaluates a run condition, so a system that will not run acquires no
parameters, occupies no worker and shows as skipped. An early return pays for the run, does nothing,
and hides the condition from anyone reading `add_systems` to learn when the system runs.

**Check:** look at the first statement of each system body. A `return` guarded by a resource, a
state, or an empty query is a run condition in the wrong place.

```rust
// verified
use bevy::prelude::*;

#[derive(Resource, Debug, Default)]
struct Alarm(bool);

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Enemy;

fn tick_ai() {}

#[derive(Debug, Default)]
pub struct AiPlugin;

impl Plugin for AiPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Alarm>().add_systems(
            FixedUpdate,
            tick_ai
                .run_if(any_with_component::<Enemy>)
                .run_if(|alarm: Res<Alarm>| alarm.0),
        );
    }
}
```

### BV-SCHED-18 [S] Compose the conditions Bevy ships before writing one

`resource_exists`, `resource_changed`, `resource_equals`, `any_with_component`, `any_match_filter`,
`on_message`, `run_once`, `in_state`, and `not` / `and` / `or` to combine them. Neighbours
differ: `resource_changed` panics if the resource is absent, and `resource_exists_and_changed` does
not.

**Why:** the shipped conditions have already settled such subtleties, and a hand-written closure
re-derives them each time. Composition also keeps the condition readable at the call site, where a
named closure would send the reader elsewhere.

**Check:** for each hand-written condition, look for the shipped one it re-implements.

### BV-SCHED-19 [M] Keep a run condition free of effects

A condition answers a question. It does not write a resource, spawn, queue a command, or consume
something a system needed. `on_message` is the documented exception: it consumes from its own
reader, not the system's.

**Why:** the scheduler evaluates conditions on its own terms — possibly more than once for a set and
its members, possibly not at all if an enclosing set was already false — so anything a condition
changes happens an unpredictable number of times.

**Check:** does the condition take any `&mut` parameter, or call anything on `Commands`? Either is
an effect.

### BV-SCHED-20 [S] Put a shared condition on the set, not on every member

`configure_sets(Update, GameSystems.run_if(in_state(Playing)))`, not the same `run_if` repeated on
each of eleven systems.

**Why:** on the set it is evaluated once per frame and stated once; repeated on members it is
evaluated once per system and has eleven places to fall out of step. The set form is also the one
that keeps working when a twelfth system is added by someone who did not read the other eleven.

**Check:** does the same `run_if` appear on more than two systems in one `add_systems` call? It
belongs on their set.

### BV-SCHED-21 [M] Gate on state with `in_state`, not by reading `State<S>`

`.run_if(in_state(GameState::Playing))`. Not `Res<State<GameState>>` plus a comparison in the body.

**Why:** the body form is the commonest case of BV-SCHED-17: the system runs in every state,
acquires all its parameters, compares and returns. The condition also composes with
`configure_sets`, so a whole phase can be state-scoped at once.

**Check:** grep for `Res<State<` in a system body. Each one is a run condition that was written as a
comparison.

## Sync points and parallelism

### BV-SCHED-22 [M] Let the schedule insert its own sync points

Do not add `ApplyDeferred` by hand. Order the systems and let the schedule work out where commands
must be applied.

**Why:** Bevy inserts a sync point on every dependency edge that needs one, and only there. A
hand-placed one is a barrier the schedule did not ask for — everything before it must finish before
anything after it starts — and it is not removed when the ordering that motivated it changes.

**Check:** grep for `ApplyDeferred` and `apply_deferred`. Each occurrence needs a reason the
automatic pass cannot infer.

### BV-SCHED-23 [S] Answer an ambiguity warning by ordering, not by silencing it

An ambiguity means two systems touch the same data with no order between them, so they run in an
order that is deterministic but arbitrary. Order them, or split the data.
`ScheduleBuildSettings::shuffle_seed`, which needs the `debug` feature from Bevy's `dev` collection,
randomises the order of ambiguous systems to expose a result that depends on it.

**Why:** no line of code chose that order, so nothing keeps it when the schedule changes. Ignoring a
pair records that someone looked, but it is honest only where the two writes genuinely commute — a
claim worth writing down rather than an annotation worth applying in bulk.

**Check:** turn on ambiguity detection and read the report once. Every pair is either ordered,
split, or ignored with a one-line reason. Then run the tests under a few `shuffle_seed` values; a
result that changes with the seed is an order nobody configured.

### BV-SCHED-24 [S] Leave the executor alone

The multi-threaded executor is the default. Replacing it with `SingleThreadedExecutor` is a
debugging step, not a configuration. In 0.20 that is `Schedule::set_executor`; `ExecutorKind` is
gone.

**Why:** single-threading makes an ordering bug reproducible, which is why it helps while hunting
one and why it must not stay: the bug is still there, now hidden, and the game has given up its
parallelism to hide it.

**Check:** grep for `set_executor`. Anything outside a debugging branch needs a reason.

### BV-SCHED-25 [M] Keep `Local<T>` to state no other system needs

`Local<T>` is private to one system. Anything a second system reads is a resource. What `Local`
exists for is bookkeeping that has no business in the world: a cursor into a message queue, a
scratch `Vec` reused across frames, a "have I logged this yet" flag.

**Why:** a `Local` is not addressable from outside: it cannot be inspected, reset, saved or
reflected. Game state hidden in one is state no tool and no second system can see.

**Check:** for each `Local<T>`, ask what would break if it were reset to `Default` between frames.
If the answer involves game state rather than bookkeeping, it is a resource.

```rust
// verified
use bevy::prelude::*;

/// Above this, a reactor core is in trouble.
const MAX_HEAT: f32 = 90.0;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
pub struct Heat(pub f32);

/// Game state: a second system reads it, the HUD shows it and a save file has
/// to contain it. `Local<u32>` here would compile, would count correctly, and
/// would leave the warning light dark forever.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Alarms(pub u32);

#[derive(Component, Debug, Clone, Copy, Default, PartialEq, Reflect)]
#[reflect(Component)]
pub struct WarningLight(pub bool);

/// `warned` is "have I complained about this yet". No other system can want it,
/// no tool needs to see it, and losing it on a reload costs one duplicate log
/// line — that is the whole job description of `Local`.
fn raise_alarm(mut warned: Local<bool>, cores: Query<&Heat>, mut alarms: ResMut<Alarms>) {
    for heat in &cores {
        if heat.0 > MAX_HEAT && !*warned {
            alarms.0 += 1;
            *warned = true;
        }
    }
}

/// The second reader. It can see the resource; a `Local` would not exist to it.
fn drive_warning_light(alarms: Res<Alarms>, mut lights: Query<&mut WarningLight>) {
    for mut light in &mut lights {
        light.set_if_neq(WarningLight(alarms.0 > 0));
    }
}

#[derive(Debug, Default)]
pub struct AlarmPlugin;

impl Plugin for AlarmPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Alarms>()
            .add_systems(Update, (raise_alarm, drive_warning_light).chain());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_flag_stays_private_and_the_count_stays_shared() {
        let mut app = App::new();
        app.add_plugins(AlarmPlugin);
        app.world_mut().spawn(Heat(120.0));
        app.world_mut().spawn(Heat(150.0));
        let light = app.world_mut().spawn(WarningLight(false)).id();

        app.update();
        app.update();
        app.update();

        // The `Local` survived every run, so two hot cores over three frames
        // raised one alarm rather than six.
        assert_eq!(app.world().resource::<Alarms>().0, 1);
        // And a second system acted on the count, which is why it is not local.
        assert_eq!(
            app.world().entity(light).get::<WarningLight>(),
            Some(&WarningLight(true))
        );
    }
}
```

## Time control

### BV-SCHED-26 [M] Pause and scale the game through `Time<Virtual>`, not a flag

`time.pause()` on a `ResMut<Time<Virtual>>`, and `set_relative_speed(3.0)` for a speed control. Not
a `Paused(bool)` resource, and not a run condition on every gameplay system; a pause the game models
as a phase is a state (BV-STATE-11) whose `OnEnter` pauses the clock. Diagnostics, the UI and
anything that has to respond while the game is stopped read `Time<Real>`, which keeps running.

**Why:** `pause` sets the virtual clock's speed to zero; `Update`'s `Time` is copied from that clock
and the fixed loop accumulates from it, so one call freezes every `Timer`, delta and fixed step. A
boolean must be remembered by every gameplay system anyone adds, which nothing enforces.

**Check:** grep for a resource named `paused`, a `run_if` mentioning one, and `is_paused` on
anything but `Time<Virtual>`. Then pause the game and confirm a `FixedUpdate` counter stops.

```rust
// verified
use bevy::prelude::*;
use bevy::state::app::StatesPlugin;
use bevy::time::{TimePlugin, TimeUpdateStrategy};
use core::time::Duration;

/// Two phases instead of a `Paused(bool)` nobody remembers to check.
#[derive(States, Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Reflect)]
pub enum GameState {
    #[default]
    Playing,
    Paused,
}

/// Simulation: one increment per fixed step.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Steps(pub u32);

/// Presentation: the frame time the animation layer has consumed.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Presented(pub Duration);

/// Diagnostics: the real clock, which pausing must not touch.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct WallClock(pub Duration);

/// The whole pause feature. No gameplay system below mentions the state.
fn pause_the_clock(mut virtual_time: ResMut<Time<Virtual>>) {
    virtual_time.pause();
}

fn resume_the_clock(mut virtual_time: ResMut<Time<Virtual>>) {
    virtual_time.unpause();
}

fn simulate(mut steps: ResMut<Steps>) {
    steps.0 += 1;
}

/// `Res<Time>` in `Update` is the virtual clock, so this stops when it does.
fn animate(mut presented: ResMut<Presented>, time: Res<Time>) {
    presented.0 += time.delta();
}

/// `Time<Real>` ignores pause, which is what a frame-time readout needs.
fn tick_wall_clock(mut wall: ResMut<WallClock>, time: Res<Time<Real>>) {
    wall.0 += time.delta();
}

#[derive(Debug, Default)]
pub struct GamePlugin;

impl Plugin for GamePlugin {
    fn build(&self, app: &mut App) {
        app.init_state::<GameState>()
            .init_resource::<Steps>()
            .init_resource::<Presented>()
            .init_resource::<WallClock>()
            .add_systems(OnEnter(GameState::Paused), pause_the_clock)
            .add_systems(OnExit(GameState::Paused), resume_the_clock)
            .add_systems(FixedUpdate, simulate)
            .add_systems(Update, (animate, tick_wall_clock));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pausing_the_virtual_clock_stops_both_schedules_at_once() {
        let step = Time::<Fixed>::default().timestep();
        let mut app = App::new();
        app.add_plugins((StatesPlugin, TimePlugin, GamePlugin))
            .insert_resource(TimeUpdateStrategy::ManualDuration(step));

        app.update(); // no virtual time has elapsed yet
        app.update();
        assert_eq!(app.world().resource::<Steps>().0, 1);

        app.world_mut()
            .resource_mut::<NextState<GameState>>()
            .set(GameState::Paused);
        // The clock was read in `First`, before the transition ran, so this
        // frame still steps: a transition is never the frame that asked.
        app.update();
        let frozen_steps = app.world().resource::<Steps>().0;
        let frozen_frame = app.world().resource::<Presented>().0;
        let wall_at_pause = app.world().resource::<WallClock>().0;

        for _ in 0..3 {
            app.update();
        }
        assert_eq!(app.world().resource::<Steps>().0, frozen_steps);
        assert_eq!(app.world().resource::<Presented>().0, frozen_frame);
        assert_eq!(
            app.world().resource::<WallClock>().0,
            wall_at_pause + step * 3,
            "diagnostics and menus keep running"
        );

        // Resuming is the same one call; the speed control is its neighbour.
        app.world_mut()
            .resource_mut::<NextState<GameState>>()
            .set(GameState::Playing);
        app.world_mut()
            .resource_mut::<Time<Virtual>>()
            .set_relative_speed(3.0);
        app.update();
        app.update();
        assert_eq!(app.world().resource::<Steps>().0, frozen_steps + 3);
        assert_eq!(
            app.world().resource::<Presented>().0,
            frozen_frame + step * 3,
            "one clock scaled both schedules"
        );
    }
}
```

