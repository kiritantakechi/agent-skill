# Testing: Headless Apps, Deterministic Ticks, What to Assert

Scope: how a Bevy project is tested — what can be tested without the engine at all, how to build the
smallest `App` that exercises a plugin, and how to drive it so the test is deterministic. General
test practice is unchanged and lives in the other standard; this chapter is the part Bevy shapes.

The most important rule here is the one about not needing this chapter: the boundary of
`references/architecture.md` BV-ARC-01 exists so that most of a game's logic is tested by ordinary
Rust unit tests, in microseconds, with no `World`.

## Contents

- **What to test where**
  - BV-TST-01 [M] Test the rules of the game without an `App`
  - BV-TST-02 [M] Build the smallest `App` that exercises the plugin
  - BV-TST-03 [S] Test a plugin through its own type
  - BV-TST-04 [M] Keep windowing and rendering out of a test

- **Driving the app**
  - BV-TST-05 [M] Advance the app with `update`, never with `run`
  - BV-TST-06 [M] Run a schedule directly when only that schedule is under test
  - BV-TST-07 [M] Give a fixed-timestep test a known number of steps
  - BV-TST-08 [M] Flush before asserting on anything a command did
  - BV-TST-09 [S] Insert the time the test wants, rather than sleeping

- **What to assert**
  - BV-TST-10 [M] Assert on the world, not on the log
  - BV-TST-11 [M] Do not assert by counting entities
  - BV-TST-12 [S] Assert the fact, not the mechanism that produced it
  - BV-TST-13 [M] Watch a test fail before trusting it
  - BV-TST-14 [S] Trigger the event to test an observer
  - BV-TST-15 [M] Configure the ordering the test depends on

---

## What to test where

### BV-TST-01 [M] Test the rules of the game without an `App`

Damage, economy, pathfinding, save formats: plain functions, plain values, plain `#[test]`.

**Why:** a test that needs a `World` is slower by orders of magnitude, harder to read, and couples
the assertion to the ECS layout — so it has to be rewritten when a component is split, even though
the rule it tests did not change. If a rule cannot be tested this way, the boundary has not been
drawn (BV-ARC-01), and the test is telling you so.

**Check:** count the tests that build an `App`. If most of them do, the logic is in the systems.

### BV-TST-02 [M] Build the smallest `App` that exercises the plugin

`App::new()` plus the plugin under test plus whatever it genuinely requires. `MinimalPlugins` when
the plugin needs a schedule runner; `DefaultPlugins` almost never.

**Why:** each plugin added is a set of systems that run on every `update()`, so a test built on
`DefaultPlugins` is slow, needs a display on some platforms, and fails for reasons unrelated to what
it is testing. Starting from nothing also documents the plugin's real dependencies: whatever has to
be added for the test to pass is what the plugin needs.

**Check:** for each plugin in the test's setup, remove it and see whether the test still passes.
Anything that can go, should.

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

### BV-TST-03 [S] Test a plugin through its own type

`app.add_plugins(CombatPlugin)`, not `app.add_systems(FixedUpdate, combat::apply_damage)`.

**Why:** the plugin is the published interface, so testing through it also tests the registration —
the resource that has to be initialised, the message that has to be added, the set the system has to
be in. Adding the system directly skips all of that, so the test passes while the plugin is missing
an `init_resource` and the game crashes on the first frame.

**Check:** does the test name a system function? If so it is not testing what the game runs. Where
one plugin depends on another, `assert!(app.is_plugin_added::<T>())` pins that too — a check the
plugin has to be a type to allow at all (BV-ARC-09).

### BV-TST-04 [M] Keep windowing and rendering out of a test

No `WinitPlugin`, no `RenderPlugin`, no `DefaultPlugins` in a unit test.

**Why:** they need a display and a GPU, which CI often does not have and which a headless container
never has — so the test either fails everywhere or passes only on a developer's machine. They also
make the test's runtime a function of driver initialisation, which is seconds.

**Check:** does the test suite pass with no display attached? That is the question, and it is
answered by running it that way once.

## Driving the app

### BV-TST-05 [M] Advance the app with `update`, never with `run`

`app.update()` runs one frame and returns. `app.run()` runs until the app exits.

**Why:** `run` installs a runner and blocks, so a test that calls it either hangs or depends on
something writing `AppExit` — which makes the test's duration a property of the game rather than of
the test. `update` is one frame, synchronously, which is what an assertion needs.

**Check:** grep the test modules for `.run()`. There should be none outside a test of `main` itself.

### BV-TST-06 [M] Run a schedule directly when only that schedule is under test

`app.world_mut().run_schedule(FixedUpdate)` runs exactly that schedule, exactly once.

**Why:** `update()` runs the whole main schedule, so a test of one `FixedUpdate` system also runs
every `Update` system in the app — and how many times `FixedUpdate` ran depends on the elapsed time,
which is not something a test should be at the mercy of. Running the schedule directly makes the
number of steps a fact of the test.

**Check:** does the test call `update()` and then assert on a `FixedUpdate` system's effect? The
number of steps is not what the test thinks it is.

### BV-TST-07 [M] Give a fixed-timestep test a known number of steps

Either run the schedule directly N times, or set `Time<Fixed>`'s timestep and advance virtual time
by a known amount.

**Why:** `update()` advances real time, so the fixed schedule runs however many times fit — zero on
a fast machine, several on a slow one. A test asserting "after one frame, health is 2.0" is
asserting something about the machine it ran on, and it will be flaky in CI in a way that looks like
a race.

**Check:** for each test involving `FixedUpdate`, find where the number of steps is decided. If it
is decided by the clock, the test is not deterministic.

### BV-TST-08 [M] Flush before asserting on anything a command did

`app.world_mut().flush()` after a command, or run the schedule that applies it. A spawn queued by a
command is not visible until then.

**Why:** it is BV-ECS-30 inside a test, and it is the most common reason a Bevy test fails with "the
entity does not exist" while the game works fine. The test does not have a later system to hide the
deferral, so it sees the queue directly.

**Check:** does the test query for something a system spawned, without a flush or an `update`
between? That is the failure.

### BV-TST-09 [S] Insert the time the test wants, rather than sleeping

Advance `Time<Virtual>` by inserting a delta, or run the fixed schedule the right number of times.
Never `thread::sleep`.

**Why:** a sleeping test is slow by exactly the amount it sleeps, and it is still not deterministic
— it asserts that at least that much time passed, not that exactly that much did. Setting the clock
is exact, instant, and states the intended duration in the test rather than leaving it implied.

**Check:** grep for `sleep` and `Instant::now` in tests.

## What to assert

### BV-TST-10 [M] Assert on the world, not on the log

`world.entity(e).get::<Health>()`, `world.resource::<Score>()`. Not that a `warn!` was emitted.

**Why:** the log is a report about what happened, and asserting on it pins the wording rather than
the behaviour — so a clearer message breaks the test and a behaviour change does not. The world is
the state the game actually has.

**Check:** does the test capture or inspect log output? Unless the log line *is* the feature, it is
asserting on a description.

### BV-TST-11 [M] Do not assert by counting entities

`world.query::<&Enemy>().iter(&world).count()` is fine; "the world has 4 entities" is not.

**Why:** the total count includes whatever the engine and every added plugin spawned — observers,
one-shot systems and internal entities have all been in that number at different versions, and 0.18
removed the `Internal` marker that used to hide them. A count-based assertion therefore breaks on an
engine upgrade that changed nothing about the game.

**Check:** grep for `entities().len()` and for asserts on a total. Query for the component the test
cares about instead.

### BV-TST-12 [S] Assert the fact, not the mechanism that produced it

Assert that the enemy is gone, not that a `Despawn` observer ran. Assert the score, not that a
message was written.

**Why:** the mechanism is an implementation choice the test should not pin — replacing a message
with an observer is a refactor, and a test that asserts on the message calls it a regression. The
exception is when the mechanism is the interface: a plugin whose job is to emit a message for other
plugins is tested on the message.

**Check:** for each assertion, ask whether it would survive rewriting the system in a different
style. If not, it is testing the shape.

### BV-TST-13 [M] Watch a test fail before trusting it

Break the system, run the test, see red, put it back.

**Why:** a Bevy test has more ways to pass vacuously than an ordinary one: the system was never
added, the schedule was never run, the entity was never spawned, the command was never flushed. Each
of those produces a test that passes and asserts nothing, and none of them looks wrong.

**Check:** for each new test, was it observed failing? If not, comment out the system's body once.

### BV-TST-14 [S] Trigger the event to test an observer

`world.trigger(Died { entity })` and assert on what changed.

**Why:** it exercises the observer through the same path the game uses, including the registration —
where calling the handler as a function skips both. Triggering is also synchronous, so the assertion
can follow immediately with no flush.

**Check:** does the test call the observer function directly? Then it is testing a function, not an
observer.

### BV-TST-15 [M] Configure the ordering the test depends on

If the test needs A before B, the test's app configures that ordering — the same way the game does.

**Why:** systems with no ordering run in an unspecified order, and in a two-system test they will
often happen to run in the right one. That makes the test pass, and it makes it fail later on a
different machine or after an unrelated system is added — as a flake, in CI, weeks from the change
that caused it.

**Check:** for each test with more than one system, is the order configured or assumed? Assumed is a
flake that has not happened yet.
