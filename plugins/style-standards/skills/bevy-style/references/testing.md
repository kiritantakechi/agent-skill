# Testing: Headless Apps, Deterministic Ticks, What to Assert

Scope: how a Bevy project is tested — what can be tested without the engine at all, how to build the
smallest `App` that exercises a plugin, and how to drive it so the test is deterministic. General
test practice is unchanged and lives in the other standard; this chapter is the part Bevy shapes.

The most important rule here is the one about not needing this chapter: the boundary of BV-ARCH-01
exists so that most of a game's logic is tested by ordinary Rust unit tests, in microseconds, with
no `World`.

What a test asserts is behaviour, as RS-TEST-02 says of any test: that the enemy is gone, not that a
`Despawn` observer ran; the score, not that a message was written — and the message itself only
where emitting it is the plugin's interface, as it is for a plugin whose job is to tell others.

## Contents

- **What to test where**
  - BV-TEST-01 [S] Test a plugin through its own type
  - BV-TEST-02 [M] Build the smallest `App` the test needs, with no window and no renderer

- **Driving the app**
  - BV-TEST-03 [M] Advance the app with `update`, never with `run`
  - BV-TEST-04 [M] Run a schedule directly when only that schedule is under test
  - BV-TEST-05 [M] Give a fixed-timestep test a known number of steps

- **What to assert**
  - BV-TEST-06 [M] Assert on the world, not on the log
  - BV-TEST-07 [M] Do not assert by counting entities
  - BV-TEST-08 [M] Watch a test fail before trusting it
  - BV-TEST-09 [S] Trigger the event to test an observer

---

## What to test where

### BV-TEST-01 [S] Test a plugin through its own type

`app.add_plugins(CombatPlugin)`, not `app.add_systems(FixedUpdate, combat::apply_damage)`.

**Why:** the plugin is the published interface, so testing through it also tests the registration:
the resource initialised, the message added, the set joined. Adding the system directly skips that,
and the test passes while the plugin misses an `init_resource` and the game crashes on frame one.

**Check:** does the test name a system function? If so it is not testing what the game runs. Where
one plugin depends on another, `assert!(app.is_plugin_added::<T>())` pins that too — a check the
plugin has to be a type to allow at all (BV-ARCH-09).

### BV-TEST-02 [M] Build the smallest `App` the test needs, with no window and no renderer

`App::new()` plus the plugin under test plus whatever it genuinely requires, and `MinimalPlugins`
when the plugin needs a schedule runner. No `WinitPlugin`, no `RenderPlugin`, no `DefaultPlugins`.

**Why:** each plugin added is systems that run on every `update()`, so a test built on more than it
needs is slow and fails for unrelated reasons. A window and a renderer need a display and a GPU,
which CI and a headless container lack, and seconds of driver start-up.

**Check:** remove each plugin from the test's setup and see whether the test still passes; anything
that can go, should. Then run the suite once with no display attached.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, PartialEq, Reflect)]
#[reflect(Component)]
struct Health(pub f32);

fn decay(mut healths: Query<&mut Health>) {
    for mut health in &mut healths {
        health.0 -= 1.0;
    }
}

#[derive(Debug, Default)]
pub struct HealthPlugin;

impl Plugin for HealthPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(FixedUpdate, decay);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn one_fixed_step_costs_one_health() {
        let mut app = App::new();
        app.add_plugins(HealthPlugin);
        let entity = app.world_mut().spawn(Health(3.0)).id();

        app.world_mut().run_schedule(FixedUpdate);

        assert_eq!(
            app.world().entity(entity).get::<Health>(),
            Some(&Health(2.0))
        );
    }
}
```

## Driving the app

### BV-TEST-03 [M] Advance the app with `update`, never with `run`

`app.update()` runs one frame and returns. `app.run()` runs until the app exits.

**Why:** `run` installs a runner and blocks, so a test that calls it either hangs or depends on
something writing `AppExit` — which makes the test's duration a property of the game rather than of
the test. `update` is one frame, synchronously, which is what an assertion needs.

**Check:** read each test module for `.run()`. There should be none outside a test of `main` itself.

### BV-TEST-04 [M] Run a schedule directly when only that schedule is under test

`app.world_mut().run_schedule(FixedUpdate)` runs exactly that schedule, exactly once. A system that
reads `Res<Time>` is tested through BV-TEST-05 instead: `run_schedule` skips the fixed loop's clock
swap, so `Time` there is the virtual clock.

**Why:** `update()` runs the whole main schedule: a test of one `FixedUpdate` system also runs every
`Update` system in the app, and the elapsed time decides how many fixed steps ran (BV-TEST-05).

**Check:** does the test call `update()` and then assert on a `FixedUpdate` system's effect? The
number of steps is not what the test thinks it is, unless it sets
`TimeUpdateStrategy::FixedTimesteps` (BV-TEST-05).

### BV-TEST-05 [M] Give a fixed-timestep test a known number of steps

Insert `TimeUpdateStrategy::FixedTimesteps(n)` beside `TimePlugin`: each `update()` then advances
the clock by exactly `n` fixed timesteps, and the fixed loop the game runs runs exactly `n` times.
`TimeUpdateStrategy::ManualDuration` sets a frame's delta the same way. Never `thread::sleep`.

**Why:** with the real clock, `update()` runs the fixed schedule however many times fit — zero on a
fast machine, several on a slow one — so the assertion is about the machine and flakes like a race.
A sleep is slow by what it sleeps and still not exact; the strategy states the duration in the test.

**Check:** for each test involving `FixedUpdate`, find where the number of steps is decided: by the
clock, and the test is not deterministic. `rg -n 'thread::sleep|Instant::now' tests/ src/` finds a
test that waits on the real clock.

```rust
// verified
use bevy::prelude::*;

/// Seconds of fuse left before the charge goes off.
#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Fuse(pub f32);

/// The fixed step, read from the fixed clock (BV-SCHED-05).
fn burn(mut fuses: Query<&mut Fuse>, time: Res<Time<Fixed>>) {
    let step = time.delta_secs();
    for mut fuse in &mut fuses {
        let left = (fuse.0 - step).max(0.0);
        fuse.set_if_neq(Fuse(left));
    }
}

#[derive(Debug, Default)]
pub struct FusePlugin;

impl Plugin for FusePlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(FixedUpdate, burn);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::time::{TimePlugin, TimeUpdateStrategy};

    /// The plugin does not own the clock, so the test inserts the one it
    /// wants: 32 Hz, an exact 31.25 ms in binary floating point, and every
    /// `update` advancing it by exactly `steps` of those.
    fn app_stepping(steps: u32) -> App {
        let mut app = App::new();
        app.add_plugins((TimePlugin, FusePlugin))
            .insert_resource(Time::<Fixed>::from_hz(32.0))
            .insert_resource(TimeUpdateStrategy::FixedTimesteps(steps));
        app
    }

    #[test]
    fn eight_steps_at_32_hz_burn_exactly_a_quarter_of_a_second() {
        let mut app = app_stepping(4);
        let charge = app.world_mut().spawn(Fuse(1.0)).id();

        // The first update starts the clock; the next two run four steps
        // each. The 8 is written in the test, and nothing about the machine
        // it runs on can change it.
        app.update();
        app.update();
        app.update();

        assert_eq!(app.world().entity(charge).get::<Fuse>(), Some(&Fuse(0.75)));
    }

    #[test]
    fn the_first_update_starts_the_clock_and_runs_no_step() {
        let mut app = app_stepping(4);
        let charge = app.world_mut().spawn(Fuse(1.0)).id();

        app.update();

        assert_eq!(app.world().entity(charge).get::<Fuse>(), Some(&Fuse(1.0)));
    }

    #[test]
    fn every_update_runs_the_fixed_loop_the_same_number_of_times() {
        let mut app = app_stepping(1);
        let charge = app.world_mut().spawn(Fuse(1.0)).id();

        app.update();
        app.update();
        app.update();
        app.update();

        // Three steps of 31.25 ms after the clock starts, however long the
        // frames really took.
        assert_eq!(
            app.world().entity(charge).get::<Fuse>(),
            Some(&Fuse(0.906_25))
        );
    }
}
```

## What to assert

### BV-TEST-06 [M] Assert on the world, not on the log

`world.entity(e).get::<Health>()`, `world.resource::<Score>()`. Not that a `warn!` was emitted.

**Why:** the log is a report about what happened, and asserting on it pins the wording rather than
the behaviour — so a clearer message breaks the test and a behaviour change does not. The world is
the state the game actually has.

**Check:** does the test capture or inspect log output? Unless the log line *is* the feature, it is
asserting on a description.

### BV-TEST-07 [M] Do not assert by counting entities

`world.query::<&Enemy>().iter(&world).count()` is fine; "the world has 4 entities" is not.

**Why:** the total includes whatever the engine and every added plugin spawned, and observers,
one-shot systems and internal entities have each been in it at different versions. A count-based
assertion therefore breaks on an engine upgrade that changed nothing about the game.

**Check:** read each `entities().len()` and each assert on a total. Query for the component the test
cares about instead.

```rust
// verified — the query survives what the entity total does not
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Enemy;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Weapon;

/// Kills so far. A fact about the game, so a test may assert on it.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Slain(pub u32);

fn spawn_wave(mut commands: Commands) {
    for _ in 0..3 {
        commands.spawn(Enemy).with_child(Weapon);
    }
}

fn count_slain(_remove: On<Remove<Enemy>>, mut slain: ResMut<Slain>) {
    slain.0 += 1;
}

#[derive(Debug, Default)]
pub struct WavePlugin;

impl Plugin for WavePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Slain>()
            .add_observer(count_slain)
            .add_systems(Startup, spawn_wave);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Ask for the component the assertion is about, whatever it is.
    fn count<C: Component>(world: &mut World) -> usize {
        let mut query = world.query_filtered::<(), With<C>>();
        query.iter(world).count()
    }

    fn wave() -> App {
        let mut app = App::new();
        app.add_plugins(WavePlugin);
        app.update();
        app
    }

    #[test]
    fn the_query_answers_the_question_and_the_total_does_not() {
        let mut app = wave();

        assert_eq!(count::<Enemy>(app.world_mut()), 3);

        // Three enemies, a weapon under each, and the plugin's observer —
        // an observer is an entity too. Nothing in that list is a fact
        // about the game, and all of it is in the total.
        let total = app.world().entities().len();
        assert!(total > 3, "{total} entities, and 3 of them are enemies");
    }

    #[test]
    fn despawning_an_enemy_does_not_move_the_total_at_all() {
        let mut app = wave();
        let before = app.world().entities().len();

        let mut query = app.world_mut().query_filtered::<Entity, With<Enemy>>();
        let victim = query
            .iter(app.world())
            .next()
            .expect("the wave spawned three");
        app.world_mut().entity_mut(victim).despawn();

        // The facts: one fewer enemy, its weapon went with it, one kill.
        assert_eq!(count::<Enemy>(app.world_mut()), 2);
        assert_eq!(count::<Weapon>(app.world_mut()), 2);
        assert_eq!(app.world().resource::<Slain>().0, 1);

        // And the count-based assertion, breaking. `Entities::len` counts
        // allocated indices rather than living entities, so those two
        // despawns move it by nothing at all.
        assert_eq!(app.world().entities().len(), before);
    }
}
```

### BV-TEST-08 [M] Watch a test fail before trusting it

Departs from RS-TEST-19. Break the system, run the test, see red, put it back — for every test, not
only a regression test.

**Why:** a Bevy test has more ways to pass vacuously than an ordinary one: the system was never
added, the schedule was never run, the entity was never spawned, the command was never flushed. Each
of those produces a test that passes and asserts nothing, and none of them looks wrong.

**Check:** for each new test, was it observed failing? If not, comment out the system's body once.

### BV-TEST-09 [S] Trigger the event to test an observer

`world.trigger(Died { entity })` and assert on what changed.

**Why:** it exercises the observer through the same path the game uses, including the registration —
where calling the handler as a function skips both. Triggering is also synchronous, so the assertion
can follow immediately with no flush.

**Check:** does the test call the observer function directly? Then it is testing a function, not an
observer.
