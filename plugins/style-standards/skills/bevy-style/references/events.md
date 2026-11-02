# Events: Messages, Events, Entity Events, Observers

Scope: the three ways one part of a game tells another that something happened, which to choose, and
how to write each. Bevy has two traits, `Message` and `Event`, for what used to be one concept, and
most code and most documentation on the internet predates the split. State changes are in the state
chapter; when a reader runs is in the scheduling chapter.

## Contents

- **Choosing the mechanism**
  - BV-EVENT-01 [M] Send a `Message` to fan out, trigger an `Event` to react
  - BV-EVENT-02 [S] Query the state instead, where the state already says it
  - BV-EVENT-03 [M] Do not derive both `Message` and `Event` on one type

- **Messages**
  - BV-EVENT-04 [M] Register a message type with `add_message`
  - BV-EVENT-05 [M] Read messages through a `MessageReader`
  - BV-EVENT-06 [M] Make a message a statement about the past
  - BV-EVENT-07 [M] Read a message in a schedule that runs at least as often as the writer
  - BV-EVENT-08 [S] Give a message the data its readers need, not an entity to look up

- **Entity events**
  - BV-EVENT-09 [M] Give an event about one entity the `EntityEvent` derive and an entity field
  - BV-EVENT-10 [M] Read the target from the named field
  - BV-EVENT-11 [S] Turn propagation on deliberately, and stop it deliberately
  - BV-EVENT-12 [M] Treat an entity event as immutable

- **Observers**
  - BV-EVENT-13 [M] Observe a lifecycle event rather than polling for it
  - BV-EVENT-14 [M] Spell the lifecycle events without their old `On` prefix
  - BV-EVENT-15 [M] Keep an observer short, because it runs inside the flush
  - BV-EVENT-16 [M] Scope an observer to one entity when one entity is the subject
  - BV-EVENT-17 [M] Never depend on the order two observers run in
  - BV-EVENT-18 [M] Do not re-trigger the event an observer is handling
  - BV-EVENT-19 [S] Name the observer's parameter after its event

---

## Choosing the mechanism

### BV-EVENT-01 [M] Send a `Message` to fan out, trigger an `Event` to react

A `Message` is buffered: it is written now and read by whichever systems get to it, in their own
schedule. An `Event` is a trigger: observers run immediately, inside the call that triggered it.

**Why:** "damage happened, and the score and the audio care" is fan-out with no ordering; "this
entity died, despawn its turret before anything sees it" cannot wait. The wrong choice is a
one-frame lag where immediacy was needed, or reentrancy where a queue was wanted.

**Check:** ask whether the reaction may happen next frame. If yes it is a message; if the world
would be inconsistent for that frame, it is an event.

| | `Message` | `Event` / `EntityEvent` |
|---|---|---|
| Written with | `MessageWriter::write` | `Commands::trigger` / `World::trigger` |
| Read by | a system with `MessageReader<M>` | an observer taking `On<E>` |
| Runs | when that system next runs | immediately, inside the trigger |
| Readers | any number, each reads all | any number, unordered |
| Registration | `app.add_message::<M>()` | `app.add_observer(…)` |

```rust
// verified — the same frame, two mechanisms, two arrival times
use bevy::prelude::*;

/// A fact about the past, buffered. Two readers want it and neither is urgent,
/// so it can wait for the schedule.
#[derive(Message, Debug, Clone, Copy)]
pub struct DamageDealt {
    pub target: Entity,
    pub amount: u32,
}

/// A demand for immediacy. Nothing may observe a corpse that still counts as
/// alive, so the reaction has to happen inside the call that announced it.
#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Died {
    pub entity: Entity,
}

#[derive(Component, Debug, Clone, Copy, PartialEq, Eq, Reflect)]
#[reflect(Component)]
pub struct Health(pub u32);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Score(pub u32);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Deaths(pub u32);

/// One of two readers. Each holds its own cursor, so each sees every message.
fn apply_damage(mut damage: MessageReader<DamageDealt>, mut healths: Query<&mut Health>) {
    for hit in damage.read() {
        if let Ok(mut health) = healths.get_mut(hit.target) {
            health.0 = health.0.saturating_sub(hit.amount);
        }
    }
}

/// The other reader. It knows nothing about the first, and cannot be ordered
/// against it — that is the whole point of the buffer.
fn add_score(mut damage: MessageReader<DamageDealt>, mut score: ResMut<Score>) {
    for hit in damage.read() {
        score.0 += hit.amount;
    }
}

/// Not a system: an observer, run inside `trigger`, before the caller's next line.
fn count_death(_died: On<Died>, mut deaths: ResMut<Deaths>) {
    deaths.0 += 1;
}

#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<DamageDealt>()
            .init_resource::<Score>()
            .init_resource::<Deaths>()
            .add_systems(Update, (apply_damage, add_score))
            .add_observer(count_death);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_message_waits_for_the_schedule_and_the_event_does_not() {
        let mut app = App::new();
        app.add_plugins(CombatPlugin);
        let target = app.world_mut().spawn(Health(30)).id();

        app.world_mut()
            .write_message(DamageDealt { target, amount: 5 });
        // Written, and nothing has run: the buffer is a promise about later.
        assert_eq!(app.world().resource::<Score>().0, 0);
        assert_eq!(
            app.world().entity(target).get::<Health>(),
            Some(&Health(30))
        );

        app.world_mut().trigger(Died { entity: target });
        // No `update()` in between — the observer already ran.
        assert_eq!(app.world().resource::<Deaths>().0, 1);

        app.update();
        // One message, two independent readers, both of them served.
        assert_eq!(app.world().resource::<Score>().0, 5);
        assert_eq!(
            app.world().entity(target).get::<Health>(),
            Some(&Health(25))
        );
    }
}
```

### BV-EVENT-02 [S] Query the state instead, where the state already says it

Before adding a message, check whether a query answers the same question. "Health reached zero" is a
query; it does not need an announcement. A message earns its place when the fact is *not*
recoverable from the world: a key was pressed, a collision occurred, a value crossed a threshold
between two frames.

**Why:** a message duplicates what the world already holds, and the duplicate can disagree: it says
the entity died, and by the time somebody reads it the entity is alive again. It also adds a frame
of latency and a type nobody can inspect.

**Check:** can a system reconstruct the fact by looking at the world when it runs? If yes, and the
timing does not matter, the message is a cache.

### BV-EVENT-03 [M] Do not derive both `Message` and `Event` on one type

A type is buffered or it is observed. Deriving both is legal and almost always means the decision
was postponed. A fact that genuinely needs both is two types with a converter, which is where the
mapping is written down.

**Why:** the two differ in delivery, registration and failure modes, so the readers of a type that
is both make incompatible assumptions about when it arrives, and no signature says which mechanism a
given call site used.

**Check:** grep for `#[derive(` lines naming both. Each is a choice that has not been made.

## Messages

### BV-EVENT-04 [M] Register a message type with `add_message`

`app.add_message::<DamageDealt>()`. Never `init_resource::<Messages<DamageDealt>>()`.

**Why:** `add_message` also registers the type with the update that drops messages two updates old.
Without it the buffer grows for the life of the process — a leak whose only symptom is memory, and
only after a long session.

**Check:** grep for `Messages<` outside a `MessageReader`/`MessageWriter` type. Each occurrence is
either the registration bug or a good reason that should be written down.

```rust
// verified
use bevy::prelude::*;

#[derive(Message, Debug, Clone, Copy)]
pub struct DamageDealt {
    pub target: Entity,
    pub amount: f32,
}

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Health(pub f32);

fn apply_damage(mut damage: MessageReader<DamageDealt>, mut healths: Query<&mut Health>) {
    for hit in damage.read() {
        if let Ok(mut health) = healths.get_mut(hit.target) {
            health.0 -= hit.amount;
        }
    }
}

#[derive(Debug, Default)]
pub struct DamagePlugin;

impl Plugin for DamagePlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<DamageDealt>()
            .add_systems(FixedUpdate, apply_damage);
    }
}
```

### BV-EVENT-05 [M] Read messages through a `MessageReader`

`MessageReader<M>` and `read()`. Not `Res<Messages<M>>` and `iter_current_update_messages()`. A
system with nothing to do when no message came takes `PopulatedMessageReader<M>`, which skips the
system on an empty queue, rather than a `MessageReader<M>` gated by `on_message::<M>`.

**Why:** the reader holds a cursor, so each system sees each message exactly once however often it
runs. Without one, a system that runs twice between updates sees the same messages twice, and one
that misses an update sees nothing — silently, both ways.

**Check:** grep for `iter_current_update_messages`. There should be none. A system that reads `M`
and also runs `.run_if(on_message::<M>)` keeps two cursors where `PopulatedMessageReader` has one.

### BV-EVENT-06 [M] Make a message a statement about the past

`DamageDealt`, `WaveCleared`, `ButtonPressed` — not `ApplyDamage`, `ClearWave`, `SpawnEnemy`. When a
single specific effect is wanted, that is a command or an observed event.

**Why:** a message has any number of readers and no ordering, so it cannot be an instruction: two
readers acting on `SpawnEnemy` spawn two enemies. A past-tense fact is safe to read any number of
times, which is what the mechanism provides.

**Check:** read each message name as a sentence starting "the fact that". If it does not fit, the
type is an instruction.

### BV-EVENT-07 [M] Read a message in a schedule that runs at least as often as the writer

A message crosses between the two schedules without loss, but not one for one. Written in
`FixedUpdate` and read in `Update`, it arrives in bursts: several steps' worth in one frame, none in
a frame where no step ran. Written in `Update` and read in `FixedUpdate`, it waits for the next
step, which may be frames away, and arrives together with every other frame's.

**Why:** `TimePlugin` holds back the update in `First` that ages messages until `FixedPostUpdate`
has run, so nothing expires unread; but steps run zero or several times a frame (BV-SCHED-06), so a
reader that keeps only the last message, or asks only whether one came, silently drops the rest.

**Check:** for each message type, list the writers' schedules and the readers'. A reader in a
slower-running schedule than its writer needs a stated reason bursts are acceptable.

### BV-EVENT-08 [S] Give a message the data its readers need, not an entity to look up

If every reader immediately queries the same three components off the entity, put those values in
the message.

**Why:** the entity may be despawned before a reader runs, so every reader carries a
`let Ok(x) = query.get(e) else { continue }` whose failure cannot be told from "this entity did not
match". Carrying the values makes the message self-contained, and so safe to read late.

**Check:** look at what each reader does first. If they all do the same lookup, the message is
missing a field.

## Entity events

### BV-EVENT-09 [M] Give an event about one entity the `EntityEvent` derive and an entity field

`#[derive(EntityEvent)] struct Died { entity: Entity }`, triggered with
`commands.trigger(Died { entity })`. The target is a field of the event, where its type shows it,
not a second argument: there is no `trigger_targets(E, entity)`.

**Why:** `Event` on its own is global: it has no target, so observers registered against an entity
never see it. `EntityEvent` stores the target on the event, which is what makes
`commands.entity(e).observe(…)` work and what makes propagation possible.

**Check:** `rg -n 'trigger_targets' src/` — each one is an `EntityEvent` that has not been
converted.

```rust
// verified
use bevy::prelude::*;

#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Died {
    pub entity: Entity,
}

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Loot(pub u32);

#[derive(Resource, Debug, Default)]
struct Bank(u32);

/// The observer is named after its event, and reads the target from the field.
fn collect_loot(died: On<Died>, loot: Query<&Loot>, mut bank: ResMut<Bank>) {
    if let Ok(loot) = loot.get(died.entity) {
        bank.0 += loot.0;
    }
}

#[derive(Debug, Default)]
pub struct LootPlugin;

impl Plugin for LootPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Bank>().add_observer(collect_loot);
    }
}
```

### BV-EVENT-10 [M] Read the target from the named field

`died.entity`, not `died.event_target()`, and never `trigger.target()` — which no longer exists for
every event type. `event_target()` is for generic code.

**Why:** the event's author named the field for what the entity *is* in this event — `attacker`,
`victim`, `container` — where the trait method can only say "the target". On an event with several
entities, that distinction is the whole meaning.

**Check:** grep for `.event_target()` in non-generic observers, and for `.target()` anywhere.

### BV-EVENT-11 [S] Turn propagation on deliberately, and stop it deliberately

`#[entity_event(propagate)]` walks `ChildOf` toward the root. An observer that has handled the event
calls `propagate(false)`. The engine's own input propagates too: since 0.20, Escape in a focused
text input clears `InputFocus` and is not consumed, so an ancestor's or the window's Escape observer
runs on the same press.

**Why:** propagation carries a click on a child to the panel that handles it, and carries a click
the child already handled there *as well*. Without an explicit stop, an event consumed at one level
is consumed again above it, which is how a single click closes two menus.

**Check:** for each propagating event, find the observers that act on it. Any that fully handles the
event and does not call `propagate(false)` is letting it continue.

### BV-EVENT-12 [M] Treat an entity event as immutable

The mutating half of `EntityEvent` is a separate trait, `SetEntityEventTarget`. Retargeting an event
in flight is not something game code does.

**Why:** every observer for an event sees the same value, so retargeting it mid-flight changes what
later observers are told happened — and which observers count as later depends on registration
order, which is not defined.

**Check:** grep for `SetEntityEventTarget`. Anything outside propagation machinery needs an
explanation.

## Observers

### BV-EVENT-13 [M] Observe a lifecycle event rather than polling for it

Setup when a component appears is `On<Add<T>>`, not a system with `Query<…, Added<T>>`. The
component is the lifecycle event's parameter, not `On`'s, and an observer of dynamic components
(`.with_component(id)`) is `On<Add<()>>` (`references/migration.md` BV-MIG-14).

**Why:** the observer runs at the moment the component is inserted, so nothing else ever sees the
entity half-initialised. A polling system runs at some later point in the frame, and everything
scheduled in between sees the gap.

**Check:** for each `Added<T>` filter, ask whether the work must happen as the component arrives. A
system skipped that frame still sees the addition when it next runs; work that cannot wait for that
is an observer.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Enemy;

#[derive(Resource, Debug, Default)]
pub struct EnemyCount(pub usize);

fn count_up(_add: On<Add<Enemy>>, mut count: ResMut<EnemyCount>) {
    count.0 += 1;
}

fn count_down(_remove: On<Remove<Enemy>>, mut count: ResMut<EnemyCount>) {
    count.0 = count.0.saturating_sub(1);
}

#[derive(Debug, Default)]
pub struct EnemyCountPlugin;

impl Plugin for EnemyCountPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<EnemyCount>()
            .add_observer(count_up)
            .add_observer(count_down);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_count_follows_the_component() {
        let mut app = App::new();
        app.add_plugins(EnemyCountPlugin);
        let entity = app.world_mut().spawn(Enemy).id();
        assert_eq!(app.world().resource::<EnemyCount>().0, 1);
        app.world_mut().entity_mut(entity).despawn();
        assert_eq!(app.world().resource::<EnemyCount>().0, 0);
    }
}
```

### BV-EVENT-14 [M] Spell the lifecycle events without their old `On` prefix

`Add`, `Insert`, `Discard`, `Remove`, `Despawn`. Not `OnAdd`, `OnInsert`, `OnReplace`, `OnRemove`,
`OnDespawn`, and not `Replace`: the event is `Discard`, and its hook `on_discard`. Where `Add`
collides with `std::ops::Add`, disambiguate the trait as `ops::Add` rather than renaming the event.

**Why:** the prefix is the observer parameter — the type is `On<Add<T>>`, so an old name reads as
`On<OnAdd<T>>`. This is the single most common stale spelling in Bevy code written against a
tutorial.

**Check:**
`rg -n 'OnAdd|OnInsert|OnReplace|OnRemove|OnDespawn|[a-z_]: Trigger<|\bReplace<|on_replace' src/`.
An `OnReplace` is `Discard`, not `Replace`. The search for `Trigger<` reads a parameter's type,
because `Event::Trigger<'a>` and the `Trigger<E>` trait are live.

### BV-EVENT-15 [M] Keep an observer short, because it runs inside the flush

An observer runs synchronously, in the middle of applying the command that triggered it. Update a
resource, queue a command, trigger another event — do not run a loop over the world.

**Why:** the work runs while the world is mid-change, parallel with nothing, and delays every
command queued behind it. The cost is invisible at the trigger site: `commands.entity(e).despawn()`
looks like a queue push and is actually whatever four observers decided to do.

**Check:** does the observer iterate a query with no bound, or do work proportional to the number of
entities? Move that to a system and have the observer record what needs doing.

```rust
// verified — the observer records, the system iterates
use bevy::prelude::*;

#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Died {
    pub entity: Entity,
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Ally;

#[derive(Component, Debug, Clone, Copy, PartialEq, Eq, Reflect)]
#[reflect(Component)]
pub struct Morale(pub u32);

/// All the observer is allowed to produce: a note of what needs doing. Drained
/// every `Update`, so it is a work list and not a second copy of the world.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct DeathQueue(pub Vec<Entity>);

/// Runs inside the flush, holding up every command queued behind it — so it
/// does one push and returns. `commands.entity(e).despawn()` at the trigger
/// site should cost roughly what it looks like it costs.
fn record_death(died: On<Died>, mut queue: ResMut<DeathQueue>) {
    queue.0.push(died.entity);
}

/// The unbounded half — work proportional to the number of allies — is a
/// system: scheduled, parallelisable, and skippable when the queue is empty.
fn spread_grief(mut queue: ResMut<DeathQueue>, mut allies: Query<&mut Morale, With<Ally>>) {
    for _dead in queue.0.drain(..) {
        for mut morale in &mut allies {
            morale.0 = morale.0.saturating_sub(1);
        }
    }
}

#[derive(Debug, Default)]
pub struct MoralePlugin;

impl Plugin for MoralePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<DeathQueue>()
            .add_observer(record_death)
            .add_systems(Update, spread_grief);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_observer_records_and_the_system_does_the_work() {
        let mut app = App::new();
        app.add_plugins(MoralePlugin);
        let ally = app.world_mut().spawn((Ally, Morale(10))).id();
        let victim = app.world_mut().spawn_empty().id();

        app.world_mut().trigger(Died { entity: victim });
        // The trigger has returned, and all that happened inside it was the note.
        assert_eq!(app.world().resource::<DeathQueue>().0.as_slice(), &[victim]);
        assert_eq!(app.world().entity(ally).get::<Morale>(), Some(&Morale(10)));

        app.update();
        assert_eq!(app.world().resource::<DeathQueue>().0, Vec::<Entity>::new());
        assert_eq!(app.world().entity(ally).get::<Morale>(), Some(&Morale(9)));
    }

    #[test]
    fn the_queue_is_drained_so_a_death_is_mourned_once() {
        let mut app = App::new();
        app.add_plugins(MoralePlugin);
        let ally = app.world_mut().spawn((Ally, Morale(10))).id();
        let victim = app.world_mut().spawn_empty().id();

        app.world_mut().trigger(Died { entity: victim });
        app.update();
        app.update();
        assert_eq!(app.world().entity(ally).get::<Morale>(), Some(&Morale(9)));
    }
}
```

### BV-EVENT-16 [M] Scope an observer to one entity when one entity is the subject

`commands.entity(e).observe(handler)` for a handler about that entity. `app.add_observer(handler)`
is global and runs for every trigger of that event. An entity nested in a `children![]` takes the
bundle effect `observe(handler)` (`bevy::ui_widgets`, which works for any entity event) in its
tuple, so the observer is attached as it spawns, with no second pass to find the child.

**Why:** the entity-scoped observer is despawned with the entity, so it cannot outlive its subject
or fire for somebody else's. The global form has to open with a guard on the target, and a guard
forgotten is a handler that silently acts on every entity in the game.

**Check:** does the observer's first statement compare the target against something? That comparison
is `entity(e).observe(…)` written out.

```rust
// verified — the same handler, scoped and global, side by side
use bevy::prelude::*;
use bevy::ui_widgets::observe;

#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Pressed {
    pub entity: Entity,
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Console;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Lever;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Barrel;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct PressLog(pub Vec<Entity>);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct GlobalPressLog(pub Vec<Entity>);

/// Registered against one entity, so its first line is already the work. It
/// cannot be reached by a press on anything else, and it is despawned with its
/// lever.
fn record_press(pressed: On<Pressed>, mut log: ResMut<PressLog>) {
    log.0.push(pressed.entity);
}

/// The same handler registered globally. Its first line has to be the guard
/// that `commands.entity(e).observe(…)` writes for you — forget it and every
/// barrel in the game is a lever.
fn record_press_globally(
    pressed: On<Pressed>,
    levers: Query<(), With<Lever>>,
    mut log: ResMut<GlobalPressLog>,
) {
    if !levers.contains(pressed.entity) {
        return;
    }
    log.0.push(pressed.entity);
}

fn spawn_console(mut commands: Commands) {
    // The lever is a child, and its observer arrives with it. The observer is
    // an entity of its own, linked to the lever by `ObservedBy` and despawned
    // when the last entity it watches is.
    commands.spawn((Console, children![(Lever, observe(record_press))]));
    commands.spawn(Barrel);
}

#[derive(Debug, Default)]
pub struct ConsolePlugin;

impl Plugin for ConsolePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<PressLog>()
            .init_resource::<GlobalPressLog>()
            .add_observer(record_press_globally)
            .add_systems(Startup, spawn_console);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn only<C: Component>(app: &mut App) -> Entity {
        let mut query = app.world_mut().query_filtered::<Entity, With<C>>();
        query
            .single(app.world())
            .expect("the console spawns exactly one of each")
    }

    #[test]
    fn the_scoped_observer_hears_only_its_own_entity() {
        let mut app = App::new();
        app.add_plugins(ConsolePlugin);
        app.update();
        let lever = only::<Lever>(&mut app);
        let barrel = only::<Barrel>(&mut app);

        app.world_mut().trigger(Pressed { entity: barrel });
        app.world_mut().trigger(Pressed { entity: lever });

        // The scoped observer ran once, for the lever, without asking anything.
        assert_eq!(app.world().resource::<PressLog>().0.as_slice(), &[lever]);
        // The global one ran twice and its guard threw the barrel away.
        assert_eq!(
            app.world().resource::<GlobalPressLog>().0.as_slice(),
            &[lever]
        );
    }

    #[test]
    fn the_scoped_observer_is_despawned_with_its_lever() {
        let mut app = App::new();
        app.add_plugins(ConsolePlugin);
        app.update();
        let lever = only::<Lever>(&mut app);

        let mut observers = app.world_mut().query_filtered::<Entity, With<Observer>>();
        // One global, one scoped.
        assert_eq!(observers.iter(app.world()).count(), 2);

        app.world_mut().entity_mut(lever).despawn();
        app.world_mut().flush();
        // The scoped one went with its lever; it cannot outlive its subject.
        assert_eq!(observers.iter(app.world()).count(), 1);
    }
}
```

### BV-EVENT-17 [M] Never depend on the order two observers run in

Several observers for one event run in an unspecified order. If B must follow A, that is not two
observers: it is one observer that does both things in order, or an observer that triggers a second
event which the second observer handles, so the dependency is explicit in the types.

**Why:** the order is an implementation detail of registration and is not part of the API, so code
that works today breaks when a plugin is added earlier.

**Check:** for each event with more than one observer, ask whether swapping them changes the result.
If it does, the ordering needs to be expressed rather than assumed.

### BV-EVENT-18 [M] Do not re-trigger the event an observer is handling

An observer for `Died` must not trigger `Died`. The recursion is unbounded and the stack is the only
thing that stops it.

**Why:** observers run synchronously inside the trigger, so a re-trigger is a direct recursive call
— not a queued item that the next flush would notice. The usual accidental form is indirect: A
triggers B, B's observer triggers A. Neither is diagnosed; the game simply stops.

**Check:** for each `trigger` inside an observer, follow the event to its observers and back. Any
cycle needs a guard, and the guard needs to be a value the observer reads, not a comment.

```rust
// verified — the cycle is real; the guard is the value that ends it
use bevy::prelude::*;

#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Damaged {
    pub entity: Entity,
    pub amount: u32,
}

#[derive(EntityEvent, Debug, Clone, Copy)]
pub struct Died {
    pub entity: Entity,
}

#[derive(Component, Debug, Clone, Copy, PartialEq, Eq, Reflect)]
#[reflect(Component)]
pub struct Health(pub u32);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct DamageMeter(pub u32);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Blasts(pub u32);

/// The guard, and the only reason the cycle below has an end: `Died` fires on
/// the *transition* to zero, never on a hit that lands on a corpse. `before` is
/// a value read out of the world — the thing the observer can actually test.
fn take_damage(
    damaged: On<Damaged>,
    mut healths: Query<&mut Health>,
    mut meter: ResMut<DamageMeter>,
    mut commands: Commands,
) -> Result {
    let mut health = healths.get_mut(damaged.entity)?;
    let before = health.0;
    health.0 = before.saturating_sub(damaged.amount);
    meter.0 += damaged.amount;
    if before > 0 && health.0 == 0 {
        commands.trigger(Died {
            entity: damaged.entity,
        });
    }
    Ok(())
}

/// Handling `Died` by triggering `Died` would never return — observers run
/// inside the trigger, so it is plain recursion with the stack as its only
/// limit. This triggers the *other* event, and the blast still reaches its own
/// corpse: the cycle closes here, and the guard above is what ends it.
fn explode_on_death(died: On<Died>, mut blasts: ResMut<Blasts>, mut commands: Commands) {
    blasts.0 += 1;
    commands.trigger(Damaged {
        entity: died.entity,
        amount: 10,
    });
}

#[derive(Debug, Default)]
pub struct ExplosivePlugin;

impl Plugin for ExplosivePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<DamageMeter>()
            .init_resource::<Blasts>()
            .add_observer(take_damage)
            .add_observer(explode_on_death);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_blast_catches_its_own_corpse_exactly_once() {
        let mut app = App::new();
        app.add_plugins(ExplosivePlugin);
        let charge = app.world_mut().spawn(Health(30)).id();

        app.world_mut().trigger(Damaged {
            entity: charge,
            amount: 30,
        });
        app.update();

        // Damaged(30) -> Died -> Damaged(10) -> guard -> stop. Two hits landed.
        assert_eq!(app.world().resource::<DamageMeter>().0, 40);
        assert_eq!(app.world().resource::<Blasts>().0, 1);
        assert_eq!(app.world().entity(charge).get::<Health>(), Some(&Health(0)));
    }

    #[test]
    fn a_survivable_hit_announces_nothing() {
        let mut app = App::new();
        app.add_plugins(ExplosivePlugin);
        let charge = app.world_mut().spawn(Health(30)).id();

        app.world_mut().trigger(Damaged {
            entity: charge,
            amount: 10,
        });
        app.update();

        assert_eq!(app.world().resource::<DamageMeter>().0, 10);
        assert_eq!(app.world().resource::<Blasts>().0, 0);
        assert_eq!(
            app.world().entity(charge).get::<Health>(),
            Some(&Health(20))
        );
    }
}
```

### BV-EVENT-19 [S] Name the observer's parameter after its event

`fn collect_loot(died: On<Died>, …)`, not `trigger` and not `ev`.

**Why:** the parameter *is* the event, and field access reads as a sentence — `died.entity` rather
than `trigger.entity`. It is also what makes the old and new APIs distinguishable at a glance in a
review: a parameter called `trigger` is usually a `Trigger<E>` that was mechanically renamed.

**Check:** grep for `: On<` preceded by `trigger`, `ev`, `event` or `t`. Rename to the event.
