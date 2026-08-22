# ECS: Components, Required Components, Queries, Change Detection

Scope: what a component is and what belongs in one, how "an X always has a Y" is expressed, how a
query is written and read, how change detection is kept meaningful, and when a structural change
goes through `Commands` rather than `&mut World`. Resources and states are in the state chapter;
when a system runs is in the scheduling chapter; reacting to a component appearing is in the events
chapter.

## Contents

- **Components**
  - BV-ECS-01 [M] Leave component fields public
  - BV-ECS-02 [M] Give a component one fact to hold
  - BV-ECS-03 [M] Derive `Debug` and `Reflect` on every component
  - BV-ECS-04 [S] Wrap a bare primitive in a named component
  - BV-ECS-05 [M] Never mark a component `#[non_exhaustive]`
  - BV-ECS-06 [M] Express "always has" with `#[require]`
  - BV-ECS-07 [M] Give a required component a value that is valid on its own
  - BV-ECS-08 [M] Do not build a "bundle" type by hand
  - BV-ECS-09 [M] Never spawn a unit
  - BV-ECS-10 [S] Give a marker component the derives a marker needs
  - BV-ECS-11 [S] Mark a component immutable when a hook depends on it
  - BV-ECS-12 [M] Model a link between entities as a relationship
  - BV-ECS-13 [M!] Register every reflected type
  - BV-ECS-14 [M] Give an asset handle a component of its own

- **Queries**
  - BV-ECS-15 [M] Query the narrowest data that answers the question
  - BV-ECS-16 [M] Ask for `&mut` only where the system writes
  - BV-ECS-17 [M] Put a zero-sized marker in the filter, never in the data
  - BV-ECS-18 [S] Split a system before reaching for a third `Option<&T>`
  - BV-ECS-19 [M] Treat `single` as fallible, because it is
  - BV-ECS-20 [S] Iterate a query with `for`, not a combinator chain
  - BV-ECS-21 [M] Name a query type once it needs two lines
  - BV-ECS-22 [S] Reach for `iter_many` when the set of entities is already known
  - BV-ECS-23 [M] Never nest a query inside itself
  - BV-ECS-24 [S] Parallelise a query only against a measurement

- **Change detection**
  - BV-ECS-25 [M!] Write with `set_if_neq` wherever a `Changed` filter is watching
  - BV-ECS-26 [M] Put `Changed<T>` in the filter so the system can be skipped
  - BV-ECS-27 [M] Do not use `Changed<T>` to mean `Added<T>`
  - BV-ECS-28 [S] Read a change in the same schedule that wrote it
  - BV-ECS-29 [S] Bypass change detection only where the write is bookkeeping

- **Structural change**
  - BV-ECS-30 [M] Do not read back what a command has not applied yet
  - BV-ECS-31 [M] Reach for an exclusive system last, and say what forced it

---

## Components

### BV-ECS-01 [M] Leave component fields public

Component fields are `pub`. This is the one place a struct in this standard is allowed to expose
its storage.

**Why:** the ECS *is* the accessor — `transform.translation.x += 1.0` is how the engine is used,
and accessor methods on a component add a layer over a layer. Reflection, the scene format, `bsn!`
and the remote protocol all read and write fields by name, so a private field is invisible to the
inspector, unserialisable, and unpatchable from a scene. Bevy's own components are public-field
throughout, so a private one is also surprising.

The single exception is a relationship **target** — the collection side of a
`#[relationship_target]` pair. The engine maintains that vector, so a caller who writes to it is
writing to something that will be overwritten. Bevy draws the same line in its own hierarchy:
`ChildOf(pub Entity)` is public and `Children(Vec<Entity>)` is not.

**Check:** does the component have accessor methods that only forward to a field? Delete them. Does
it have a field that a method is guarding? That is BV-ARC-04's case, and the guard belongs in a
domain type. A private field on anything but a relationship target is one of those two.

### BV-ECS-02 [M] Give a component one fact to hold

A component holds one thing about an entity. Two fields written by different systems, changing at
different rates, or read by different queries are two components.

**Why:** the component is the unit of both querying and change detection, so a field bundled with
an unrelated one cannot be queried without the other and cannot be marked changed without falsely
marking it too. It is also the unit of archetype layout: a system that reads a single `f32` pays
for the whole struct's cache line.

**Check:** for each pair of fields, name a system that reads exactly one of them. If such a system
exists for most pairs, the component is a bag.

```rust
// verified — GOOD: three facts, three components, three independent queries
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Shield(pub f32);

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Speed(pub f32);

/// Only touches the entities that actually have a shield.
fn regenerate_shields(mut shields: Query<&mut Shield>) {
    for mut shield in &mut shields {
        shield.0 = (shield.0 + 1.0).min(100.0);
    }
}
```

```rust
// verified — BAD: one struct, so regenerating a shield marks health changed too
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Stats {
    health: f32,
    shield: f32,
    speed: f32,
}

fn regenerate_shields(mut stats: Query<&mut Stats>) {
    for mut stats in &mut stats {
        stats.shield = (stats.shield + 1.0).min(100.0);
    }
}
```

### BV-ECS-03 [M] Derive `Debug` and `Reflect` on every component

`#[derive(Component, Debug, Reflect)]`, plus `#[reflect(Component)]`. Add `Clone`, `Copy`,
`PartialEq` and `Default` where each of them means something for the type.

**Why:** `Debug` is what every panic message, every `info!`, and every test failure prints; without
it the value is a hole in the output exactly when it is needed. `Reflect` plus
`#[reflect(Component)]` is what makes the type visible to an inspector, writable in a scene, and
readable over the remote protocol — and it is opt-in, so it is forgotten silently. `PartialEq` is a
precondition for `set_if_neq` (BV-ECS-25), which is why so many components want it.

**Check:** grep for `#[derive(Component` and look for one without `Debug`, and for a `Reflect`
without the matching `#[reflect(Component)]` — deriving the trait without the registration attribute
leaves the type reflected but not recognised as a component.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Health {
    pub current: f32,
    pub max: f32,
}
```

### BV-ECS-04 [S] Wrap a bare primitive in a named component

`Speed(pub f32)`, not a component called `Value`, and never a raw `f32` as the component type.

**Why:** the component type is the query key, so a bare primitive can only ever appear once per
entity and collides across every feature that wanted one. The name is also the only place the unit
can live: `Speed` says what the number is, and a query for `&Speed` reads as a sentence where a
query for `&f32` reads as a type puzzle.

**Check:** does any component name fail to say what the value means — `Value`, `Data`, `Amount`,
`Inner`? Rename it after the quantity.

### BV-ECS-05 [M] Never mark a component `#[non_exhaustive]`

Components are constructed by struct literal, at every spawn site, in every crate.

**Why:** `#[non_exhaustive]` forbids literal construction outside the defining crate, which is the
only construction a component has. This standard's general rule is to apply the attribute where a
struct's shape may grow; for components the growth mechanism is a *new component* plus a
`#[require]`, which is additive without breaking any existing spawn.

**Check:** grep for `#[non_exhaustive]` immediately above a `#[derive(…Component…)]`. There should
be none.

### BV-ECS-06 [M] Express "always has" with `#[require]`

If every entity with `Enemy` also needs `Health` and `Transform`, `Enemy` declares that:
`#[require(Health, Transform)]`. The spawn site names only what it is choosing.

**Why:** the invariant lives once, on the type that owns it, instead of at every spawn site where
it can be forgotten. The `*Bundle` types were the old mechanism and were removed for exactly this:
nothing
stopped a caller from spawning half a bundle, and adding a field to a bundle silently changed every
spawn. A `#[require]` cannot be half-applied.

**Check:** look at every `spawn` for the same component appearing beside the same other component
more than twice. That repetition is a `#[require]` that has not been written.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

#[derive(Component, Debug, Clone, Copy, Default, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Shield(pub f32);

/// An enemy always has health and a shield, so the type says so once.
#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
#[require(Health(100.0), Shield(25.0), Transform)]
pub struct Enemy;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spawning_an_enemy_brings_its_requirements() {
        let mut world = World::new();
        let entity = world.spawn(Enemy).id();
        assert_eq!(world.entity(entity).get::<Health>(), Some(&Health(100.0)));
        assert_eq!(world.entity(entity).get::<Shield>(), Some(&Shield(25.0)));
    }

    #[test]
    fn an_explicit_value_wins_over_the_required_default() {
        let mut world = World::new();
        let entity = world.spawn((Enemy, Health(10.0))).id();
        assert_eq!(world.entity(entity).get::<Health>(), Some(&Health(10.0)));
    }
}
```

### BV-ECS-07 [M] Give a required component a value that is valid on its own

`#[require(Health)]` uses `Default`. `#[require(Health(100.0))]` names a value. Whichever it is,
that value must be a state the game can be in for a frame.

**Why:** a required component is inserted before any of your code runs, so its initial value is
live: an entity spawned with `#[require(Health)]` and `Health(0.0)` as the `Default` is dead on the
frame it appears, and a death system running that frame will act on it. The inline-value form exists
precisely so the sensible starting value does not have to be the type's `Default`.

**Check:** for each `#[require(T)]` with no value, read `T::default()` and ask whether an entity in
that state for one frame is harmless. If not, give the requirement a value.

### BV-ECS-08 [M] Do not build a "bundle" type by hand

A struct or type alias whose only purpose is to be spawned as a group is the removed bundle,
reintroduced. Use `#[require]` for what is always true and a tuple at the spawn site for what is
being chosen.

**Why:** the group type reproduces the failure the engine removed it for. It cannot be queried, it
cannot be inserted partially without a second definition, and adding a field to it changes every
call site silently — while `#[require]` puts the same information where the query, the inspector and
the scene format can all see it.

**Check:** search for structs deriving `Bundle`, and for `fn *_bundle() -> impl Bundle`. Each one is
either a `#[require]` or a tuple.

### BV-ECS-09 [M] Never spawn a unit

`commands.spawn(())` and a `()` sitting inside a spawn tuple are mistakes. Use `spawn_empty()` when
an entity really has no components.

**Why:** `()` implements `Bundle` and inserts nothing, so it compiles and does nothing. The usual
cause is a method that returns `()` where a component was expected —
`Transform::from_xyz(…).rotate_z(PI)` returns a unit, so the transform never reaches the entity and
the object silently sits at the origin. `bevy_lint`'s `unit_in_bundle` finds every case.

**Check:** for each component expression in a spawn tuple, check that the last call returns `Self`.
The mutating `Transform` methods (`rotate_z`, `translate_around`) do not; the `with_*` builders do.

### BV-ECS-10 [S] Give a marker component the derives a marker needs

A marker is a unit struct: `#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)] pub struct Player;`

**Why:** `Default` is what lets the marker be named in someone else's `#[require]`, and `Copy` and
`Clone` cost nothing on a zero-sized type while letting it be cloned with an entity or written into
a scene patch. Adding either later is a breaking change to anyone who tried and could not. The set
stops there deliberately: `PartialEq`, `Eq` and `Hash` on a type with no data distinguish nothing,
and `bevy_lint`'s `missing_trait_for_unit_struct` asks for exactly these three.

**Check:** is every unit-struct component `Default`? A marker that is not cannot be required by
another component.

### BV-ECS-11 [S] Mark a component immutable when a hook depends on it

`#[component(immutable)]` makes a component insert-and-remove only. Use it where a lifecycle hook,
an index, or a relationship derives something from the value.

**Why:** an immutable component cannot be changed behind the back of the hook that indexed it, so
the derived structure cannot go stale. It is also a genuine statement about the type: an identity, a
kind, or a spawn-time configuration is not something a system should reach in and edit.

**Check:** for each component read by a hook or observer on `Insert`, ask what happens if a system
mutates it afterwards. If the answer is a stale index, the component wants to be immutable.

### BV-ECS-12 [M] Model a link between entities as a relationship

Parent and child are `ChildOf` and `Children`. Any other one-to-many link — a turret's owner, a
squad's members — is a `#[relationship]` / `#[relationship_target]` pair, not a bare `Entity` field
plus a `Vec<Entity>` kept in step by hand.

**Why:** a relationship maintains both sides, so removing the target cannot leave a dangling id on
the other side, and despawning follows the link. Hand-maintained `Entity` fields have neither
property: the classic bug is a `Vec<Entity>` holding ids of entities that were despawned three
frames ago, which produces a `get` returning `None` in a place that never expected one.

**Check:** search for `Vec<Entity>` and for `Entity` fields in components. Each is either a
relationship or needs a written reason it cannot be one.

```rust
// verified
use bevy::prelude::*;

/// The one side. `#[entities]` is what makes the id survive entity remapping.
#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
#[relationship(relationship_target = Crew)]
pub struct CrewOf(#[entities] pub Entity);

/// The many side. Bevy maintains it; nothing writes to it by hand.
#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
#[relationship_target(relationship = CrewOf)]
pub struct Crew(Vec<Entity>);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn both_sides_are_maintained_by_the_engine() {
        let mut world = World::new();
        let ship = world.spawn_empty().id();
        let pilot = world.spawn(CrewOf(ship)).id();
        assert_eq!(
            world.entity(ship).get::<Crew>().map(|c| c.0.as_slice()),
            Some(&[pilot][..])
        );

        world.entity_mut(pilot).despawn();
        assert!(
            world
                .entity(ship)
                .get::<Crew>()
                .is_none_or(|c| c.0.is_empty())
        );
    }
}
```

### BV-ECS-13 [M!] Register every reflected type

`app.register_type::<Health>()` for every component, resource and message that derives `Reflect`.

*Relaxed form:* a project that has enabled `reflect_auto_register` may rely on it, and then the rule
is that the feature is on, not that each call exists.

**Why:** `#[derive(Reflect)]` makes a type reflectable; registration makes it *findable*. The
inspector lists registered types, the scene loader resolves type names against the registry, and
the remote protocol can only see what is in it. An unregistered type does not error — it is simply
absent, which reads as "the tool is broken".

**Check:** count `#[derive(…Reflect…)]` in the crate and `register_type::<` calls in the plugins. If
the second number is smaller and `reflect_auto_register` is off, the difference is invisible types.

### BV-ECS-14 [M] Give an asset handle a component of its own

`Handle<T>` is not a component. Wrap it: `#[derive(Component)] struct Portrait(pub Handle<Image>);`

**Why:** an entity may want two handles of the same asset type — a portrait and an icon are both
`Handle<Image>` — and a bare handle as the component type allows only one, chosen by whichever
system inserted last. The wrapper also gives the handle a name, which is the only place the meaning
of the asset can be recorded. Bevy removed the blanket `Component` impl on `Handle` for this reason.

**Check:** grep for `Handle<` inside a `spawn` tuple with no wrapper around it.

## Queries

### BV-ECS-15 [M] Query the narrowest data that answers the question

Ask for the components the body reads, and no others. `Query<&Transform>` rather than
`Query<(&Transform, &Health, &Sprite)>` when only the transform is used.

**Why:** the components in the query are the system's declared access, and the scheduler uses that
declaration to decide what may run in parallel. An unused `&mut Sprite` does not slow the body down;
it serialises this system against every other system that touches a sprite, for nothing.

**Check:** for each item in the query tuple, find its use in the body. An unused one is a scheduling
constraint with no reader.

### BV-ECS-16 [M] Ask for `&mut` only where the system writes

`&T` for reading. `&mut T` exclusively for components the body assigns to.

**Why:** `&mut` is both an exclusive lock for the scheduler and a change-detection trigger.
Requesting it to read means no other system touching that component can run concurrently, and — if
the body ever derefs it mutably — every entity is marked changed every frame, which turns every
downstream `Changed<T>` filter into a no-op.

**Check:** for each `&mut` in a query, find the assignment. If the body only reads, the `mut` is two
bugs waiting.

### BV-ECS-17 [M] Put a zero-sized marker in the filter, never in the data

`Query<&Transform, With<Player>>`, not `Query<(&Transform, &Player)>`.

**Why:** a marker has no runtime data, so fetching it retrieves nothing while still adding a column
to the query's access set and a binding to the loop that is immediately discarded — the `_` in
`for (transform, _) in &query` is the giveaway. `With` expresses the same restriction as a filter,
which is what it is. `bevy_lint`'s `zst_query` reports the data form.

**Check:** for each item in a query's data tuple, is its type a unit struct? If so it belongs in the
filter.

```rust
// verified — GOOD: the marker restricts, the data is what the body reads
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Player;

fn recentre(mut players: Query<&mut Transform, With<Player>>) {
    for mut transform in &mut players {
        transform.translation.x = 0.0;
    }
}
```

### BV-ECS-18 [S] Split a system before reaching for a third `Option<&T>`

One or two `Option<&T>` in a query describe a genuinely optional part. Three describe several
different jobs that have been written as one.

**Why:** each `Option` doubles the number of shapes the body has to handle, and the body then
branches on combinations that no entity actually has. Two systems with `With<A>` and `Without<A>`
say which case each is for, run only over the entities in that case, and can be scheduled
independently.

**Check:** count the `if let Some(…)` in the body. If the combinations exceed the cases the game
actually spawns, split by filter instead.

### BV-ECS-19 [M] Treat `single` as fallible, because it is

`Query::single` and `single_mut` return `Result`. Propagate it with `?` from a system that returns
`Result`.

**Why:** zero or two matches is normal — the camera is not spawned on the first frame, and the
player is despawned on death — so this is a condition to handle, not an invariant. It was made
fallible in 0.16, and the panicking form no longer exists under that name.

**Check:** grep for `single().unwrap()`, `single_mut().unwrap()` and `.expect(` on a query. Each is
a crash where a `?` would have skipped a frame.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Player;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Follower;

/// Returns `Result`, so a frame with no player is a skipped frame and not a crash.
fn follow_player(
    players: Query<&Transform, With<Player>>,
    mut followers: Query<&mut Transform, (With<Follower>, Without<Player>)>,
) -> Result {
    let target = players.single()?.translation;
    for mut transform in &mut followers {
        transform.translation = transform.translation.lerp(target, 0.1);
    }
    Ok(())
}
```

### BV-ECS-20 [S] Iterate a query with `for`, not a combinator chain

`for item in &query` and `for item in &mut query`. This standard's general preference for `map`,
`filter` and `collect` over loops does not extend to query iteration.

**Why:** the loop is doing effects, which is the case the general rule reserves `for` for: the item
is a `Mut<T>` whose borrow of the query cannot outlive the iteration, so there is nothing to collect
and no value to return. Restrictions belong in the query's filter rather than in a `.filter()`,
because the filter form skips entities before they are fetched.

**Check:** a `.for_each(` or a `.filter(` on a query iterator is either a filter that belongs in the
type, or a loop that has been written the long way.

### BV-ECS-21 [M] Name a query type once it needs two lines

A query with several data items and several filters gets a `type` alias with a name from the domain.

**Why:** the alias is a name for a concept — `Combatants`, `VisibleSprites` — which the inline type
never is, and it is reusable across the systems that share the shape. It also silences
`clippy::type_complexity`, which this standard keeps switched on for exactly this reason: the lint
is right, and the compliant form is better code rather than a suppression.

**Check:** if the query type wraps onto a second line, name it. The alias needs explicit `'w`, `'s`
and `'static` lifetimes; that is one-time cost paid at the definition rather than at each use.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Health(pub f32);

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Enemy;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Invulnerable;

/// The shape three systems share, named once.
type Combatants<'w, 's> = Query<
    'w,
    's,
    (Entity, &'static mut Transform, &'static mut Health),
    (With<Enemy>, Without<Invulnerable>, Changed<Health>),
>;

fn cull(mut commands: Commands, combatants: Combatants) {
    for (entity, _transform, health) in &combatants {
        if health.0 <= 0.0 {
            commands.entity(entity).despawn();
        }
    }
}
```

### BV-ECS-22 [S] Reach for `iter_many` when the set of entities is already known

Given a `Children`, a relationship target, or a stored list of ids, `query.iter_many(ids)` fetches
exactly those. Iterating the whole query and testing membership does not.

**Why:** the cost of the loop should be the number of entities you care about, not the number that
exist. A membership test inside a full iteration is `O(all)` where the direct form is `O(wanted)`,
and it reads as a search where the code already knows the answer.

**Check:** look for `if ids.contains(&entity)` inside a query loop. That is `iter_many` written out.

### BV-ECS-23 [M] Never nest a query inside itself

A loop over a query cannot contain another loop over the same query. Use `iter_combinations` for
pairs, or split the data into two queries with disjoint filters.

**Why:** the borrow checker rejects the mutable case outright, and the read-only case is a quadratic
loop that looks linear. `iter_combinations` also visits each unordered pair once rather than twice,
which is usually what collision or attraction code actually wanted.

**Check:** search for a `for` over a query inside another `for` over a query and check the two are
different queries with filters that cannot both match one entity.

### BV-ECS-24 [S] Parallelise a query only against a measurement

`par_iter_mut` is for a loop that has been measured and found hot. Write the serial form first.

**Why:** the parallel form has per-batch overhead and forces the body to be `Send`, and below a few
thousand entities it is reliably slower. Reaching for it before measuring also hides the usual real
answer, which is that the query is fetching more components than it reads (BV-ECS-15) or the work
belongs in `FixedUpdate` at a lower rate.

**Check:** is there a benchmark or a profile naming this system? If not, the serial form is the one
to ship.

## Change detection

### BV-ECS-25 [M!] Write with `set_if_neq` wherever a `Changed` filter is watching

`health.set_if_neq(Health(new))` rather than `*health = Health(new)` when the new value is often the
old one.

*Relaxed form:* a component nothing filters on, and nothing reacts to, may be assigned directly —
but that is a fact about today's readers, and it changes the moment someone adds a `Changed` filter.

**Why:** `DerefMut` on `Mut<T>` marks the component changed, so assigning the same value every frame
marks every entity changed every frame. Every downstream `Changed<T>` filter then matches
everything, which is not a slow path — it is a silent loss of the mechanism, because the filter goes
on compiling and matching and no longer means anything.

**Check:** for each `*component = …` in a system that runs every frame, ask whether the value can be
unchanged. If so, and anything filters on it, that is the defect.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
struct Score(pub u32);

/// `set_if_neq` writes only on a difference, so `Changed<Score>` still means something.
fn recompute(mut scores: Query<(&mut Score, &Kills)>) {
    for (mut score, kills) in &mut scores {
        score.set_if_neq(Score(kills.0 * 10));
    }
}

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Kills(pub u32);

#[derive(Resource, Debug, Default)]
struct Bumps(usize);

/// Counts how many entities `Changed<Score>` matched, across every frame.
fn count(changed: Query<(), Changed<Score>>, mut bumps: ResMut<Bumps>) {
    bumps.0 += changed.iter().count();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_score_is_written_once_and_then_stops_changing() {
        let mut app = App::new();
        app.init_resource::<Bumps>()
            .add_systems(Update, (recompute, count).chain());
        let entity = app.world_mut().spawn((Score(0), Kills(3))).id();

        app.update();
        app.update();
        app.update();

        assert_eq!(app.world().entity(entity).get::<Score>(), Some(&Score(30)));
        assert_eq!(app.world().resource::<Bumps>().0, 1);
    }
}
```

### BV-ECS-26 [M] Put `Changed<T>` in the filter so the system can be skipped

`Query<&Health, Changed<Health>>`, not a full query with `if health.is_changed()` inside the loop.

**Why:** as a filter it is applied during iteration, so unchanged entities are never fetched; in the
body it is applied after the fetch, so the loop still visits everything. The filter form is also the
declaration a reader needs — the system's signature says it is reactive, where the body form hides
that behind an early `continue`.

**Check:** grep for `is_changed()` inside a query loop. Unless the body needs both the changed and
the unchanged entities, it is a filter that has escaped into the body.

### BV-ECS-27 [M] Do not use `Changed<T>` to mean `Added<T>`

`Added<T>` matches the frame the component was inserted. `Changed<T>` matches insertion *and* every
subsequent write.

**Why:** `Changed` also matches on the first frame, so setup code written under it appears to work
and then runs again on every later write — spawning a second sound, a second child, a second
subscription. The bug surfaces only when someone starts mutating the component, which may be months
later and in another module.

**Check:** for each `Changed<T>` filter, ask whether running twice for one entity is acceptable. If
not, it is `Added<T>` — or, better, an observer on `Add` (`references/events.md` BV-EVT-12).

### BV-ECS-28 [S] Read a change in the same schedule that wrote it

A `Changed<T>` filter sees writes since the reading system last ran. Keep the writer and the reader
in the same schedule.

**Why:** `FixedUpdate` may run zero times or several times in one frame. A write in `FixedUpdate`
read by an `Update` system is seen once no matter how many times it happened; a write in `Update`
read by a `FixedUpdate` system may be seen by no run at all. Neither is a race — the change ticks
are consistent — but both mean "since you last ran", which across schedules is not "this frame".

**Check:** for each `Changed<T>` reader, find the writers. Any writer in a different schedule needs
a stated reason the count does not matter.

### BV-ECS-29 [S] Bypass change detection only where the write is bookkeeping

`Mut::bypass_change_detection` is for writes that are not changes to the game's state — a cached
value refreshed from its source, a counter nothing reacts to.

**Why:** the bypass is the only way to write without marking, and using it for a real change makes
the component's history a lie: everything downstream carries on believing the old value. Kept for
bookkeeping it is precise; used to quiet a noisy filter it hides the fact that BV-ECS-25 was the
answer.

**Check:** each call needs a comment naming what does *not* need to know about this write. If the
comment cannot be written, the write is a change.

## Structural change

### BV-ECS-30 [M] Do not read back what a command has not applied yet

`Commands` queue work that runs at the next sync point. Within the same system, the entity spawned
two lines ago is not in any query.

**Why:** the deferral is what lets systems run in parallel, and it is invisible: the code reads as
if it were immediate, and the query simply returns nothing. The usual symptom is a spawn followed by
a `get` that returns `None`, "fixed" by moving the read into a second system — which is the correct
fix, arrived at without understanding why.

**Check:** in each system, is any id from `commands.spawn(…).id()` used to look something up in the
same body? Move the read to a later system, or use an exclusive system if it must be immediate.

### BV-ECS-31 [M] Reach for an exclusive system last, and say what forced it

A system taking `&mut World` cannot run in parallel with anything. Write one only when the work
genuinely needs the whole world at once, and put the reason in a doc comment.

**Why:** an exclusive system is a global barrier in the schedule: everything before it finishes,
it runs alone, everything after starts. One is usually fine and four is a game that no longer runs
its systems in parallel. Most reasons for reaching for one — needing a resource and a query
together, needing a command applied now — have a non-exclusive form.

**Check:** for each `&mut World` parameter, name what makes `SystemParam`s insufficient. "Needed a
resource and a query" is not one of them; "runs a scene through the type registry" is.
