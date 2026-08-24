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

```rust
// verified — seven tests, and neither an App nor a World anywhere in them
// Not one Bevy name appears below, and that is the whole point: these tests
// need no `App`, no `World` and no schedule, so they run in microseconds and
// survive an ECS refactor untouched.

/// A purse. The economy is `u32` throughout, so no value here can be `NaN`
/// and every assertion is an exact equality.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Coins(pub u32);

/// The shelf price of one item.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Price(pub u32);

/// What happened when a quote was taken to the till.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Purchase {
    /// Paid in full; the purse now holds this much.
    Bought(Coins),
    /// Nothing changed hands; the purse is this far short.
    TooExpensive(Coins),
}

/// Buy nine, get the tenth free.
pub const FREE_EVERY: u32 = 10;

/// What a stack of `count` items costs at the shelf price.
///
/// The till saturates rather than wrapping: an unpayable quote is a better
/// answer than a quote of three coins.
#[must_use]
pub fn quote(unit: Price, count: u32) -> Coins {
    let free = count / FREE_EVERY;
    Coins(unit.0.saturating_mul(count - free))
}

/// Whether the purse covers the quote, and by how much either way.
#[must_use]
pub fn buy(purse: Coins, cost: Coins) -> Purchase {
    purse.0.checked_sub(cost.0).map_or_else(
        || Purchase::TooExpensive(Coins(cost.0 - purse.0)),
        |left| Purchase::Bought(Coins(left)),
    )
}

// The ECS side is a system that reads two components, calls `buy`, and
// writes the result back; it is tested once, through its plugin
// (BV-TST-02). Had the arithmetic lived inside that system instead, all
// seven tests below would have needed a `World` to reach it — and the
// tenth-free rule would have ended up with one test rather than four,
// because nobody writes four `App` tests for one discount.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nine_items_pay_full_price_and_the_tenth_is_free() {
        assert_eq!(quote(Price(3), 9), Coins(27));
        assert_eq!(quote(Price(3), 10), Coins(27));
        assert_eq!(quote(Price(3), 11), Coins(30));
    }

    #[test]
    fn the_discount_repeats_every_tenth_item() {
        let paid_for = |count| quote(Price(1), count);
        assert_eq!(paid_for(0), Coins(0));
        assert_eq!(paid_for(20), Coins(18));
        assert_eq!(paid_for(100), Coins(90));
    }

    #[test]
    fn an_unpayable_stack_saturates_instead_of_wrapping_to_a_bargain() {
        assert_eq!(quote(Price(u32::MAX), 11), Coins(u32::MAX));
    }

    #[test]
    fn an_exact_purse_buys_and_leaves_nothing() {
        assert_eq!(
            buy(Coins(27), quote(Price(3), 10)),
            Purchase::Bought(Coins(0))
        );
    }

    #[test]
    fn one_coin_short_is_a_refusal_that_says_by_how_much() {
        assert_eq!(
            buy(Coins(26), quote(Price(3), 10)),
            Purchase::TooExpensive(Coins(1))
        );
    }

    #[test]
    fn a_bigger_stack_never_costs_less_than_a_smaller_one() {
        let curve = |count| quote(Price(7), count);
        assert!((0..40).all(|count| curve(count) <= curve(count + 1)));
    }

    /// A hundred purchases in one test, and the suite still finishes
    /// instantly — which is the argument for keeping the rule on this side.
    #[test]
    fn a_purse_spent_one_item_at_a_time_runs_out_exactly_when_it_should() {
        let one = quote(Price(3), 1);
        let purse = (0..100).fold(Coins(300), |held, _| match buy(held, one) {
            Purchase::Bought(left) => left,
            Purchase::TooExpensive(_) => held,
        });

        assert_eq!(purse, Coins(0));
        assert_eq!(buy(purse, one), Purchase::TooExpensive(Coins(3)));
    }
}
```

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

```rust
// verified
use bevy::prelude::*;

/// Seconds of fuse left before the charge goes off.
#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Fuse(pub f32);

/// Naming `Time<Fixed>` rather than the generic `Time` is what lets a test
/// drive this with `run_schedule`: the generic clock is only swapped to the
/// fixed one by the fixed-main loop, which a direct `run_schedule` skips.
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

    /// One fixed step, decided here: advance the fixed clock by exactly one
    /// timestep, then run the schedule exactly once.
    fn step(app: &mut App) {
        let timestep = app.world().resource::<Time<Fixed>>().timestep();
        app.world_mut()
            .resource_mut::<Time<Fixed>>()
            .advance_by(timestep);
        app.world_mut().run_schedule(FixedUpdate);
    }

    /// The plugin does not own the clock, so the test inserts the one it
    /// wants: 32 Hz, which is an exact 31.25 ms in binary floating point.
    fn app_at_32_hz() -> App {
        let mut app = App::new();
        app.add_plugins(FusePlugin)
            .insert_resource(Time::<Fixed>::from_hz(32.0));
        app
    }

    #[test]
    fn eight_steps_at_32_hz_burn_exactly_a_quarter_of_a_second() {
        let mut app = app_at_32_hz();
        let charge = app.world_mut().spawn(Fuse(1.0)).id();

        for _ in 0..8 {
            step(&mut app);
        }

        // 8 x 31.25 ms. The 8 is written in the test; nothing about the
        // machine the test runs on can change it.
        assert_eq!(app.world().entity(charge).get::<Fuse>(), Some(&Fuse(0.75)));
    }

    #[test]
    fn update_does_not_decide_the_number_of_steps_for_you() {
        let mut app = app_at_32_hz();
        let charge = app.world_mut().spawn(Fuse(1.0)).id();

        app.update();
        app.update();

        // Nothing accumulated any overstep, so `FixedUpdate` ran zero times.
        // With a real clock plugin it would have run however many times the
        // frames happened to be long enough for — the machine's answer to a
        // question that belongs to the test.
        assert_eq!(app.world().entity(charge).get::<Fuse>(), Some(&Fuse(1.0)));
    }
}
```

### BV-TST-08 [M] Flush before asserting on anything a command did

`app.world_mut().flush()` after a command, or run the schedule that applies it. A spawn queued by a
command is not visible until then.

**Why:** it is BV-ECS-30 inside a test, and it is the most common reason a Bevy test fails with "the
entity does not exist" while the game works fine. The test does not have a later system to hide the
deferral, so it sees the queue directly.

**Check:** does the test query for something a system spawned, without a flush or an `update`
between? That is the failure.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Muzzle;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Bullet;

/// A structural change from a parallel system goes through `Commands`, so
/// the spawn is queued here and lands at the schedule's sync point.
fn fire(mut commands: Commands, muzzles: Query<&Transform, With<Muzzle>>) {
    for transform in &muzzles {
        commands.spawn((Bullet, *transform));
    }
}

#[derive(Debug, Default)]
pub struct GunPlugin;

impl Plugin for GunPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, fire);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bullets(world: &mut World) -> usize {
        let mut query = world.query_filtered::<(), With<Bullet>>();
        query.iter(world).count()
    }

    #[test]
    fn a_command_the_test_queued_is_invisible_until_the_flush() {
        let mut world = World::new();
        world.commands().spawn(Bullet);

        // The spawn is in the queue, not in the world. Asserting here is
        // what produces "the entity does not exist" in a test of code the
        // game runs perfectly well.
        assert_eq!(bullets(&mut world), 0);

        world.flush();

        assert_eq!(bullets(&mut world), 1);
    }

    #[test]
    fn running_the_schedule_applies_the_systems_commands() {
        let mut app = App::new();
        app.add_plugins(GunPlugin);
        app.world_mut()
            .spawn((Muzzle, Transform::from_xyz(0.0, 2.0, 0.0)));

        app.world_mut().run_schedule(Update);

        // The schedule flushed at its own sync point, so the bullet and
        // everything spawned with it are visible without a `flush` here.
        let mut query = app.world_mut().query_filtered::<&Transform, With<Bullet>>();
        let spawned: Vec<Vec3> = query.iter(app.world()).map(|t| t.translation).collect();
        assert_eq!(spawned, [Vec3::new(0.0, 2.0, 0.0)]);
    }
}
```

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

fn count_slain(_remove: On<Remove, Enemy>, mut slain: ResMut<Slain>) {
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
        let Some(victim) = query.iter(app.world()).next() else {
            unreachable!("the wave spawned three")
        };
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
