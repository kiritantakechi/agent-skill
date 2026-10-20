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
  - BV-ECS-19 [S] Iterate a query with `for`, not a combinator chain
  - BV-ECS-20 [M] Name a query type once it needs two lines
  - BV-ECS-21 [S] Reach for `iter_many` when the set of entities is already known
  - BV-ECS-22 [M] Never nest a query inside itself
  - BV-ECS-23 [S] Parallelise a query only against a measurement
  - BV-ECS-24 [S] Reach for `contiguous_iter` only against a measured hot loop

- **Change detection**
  - BV-ECS-25 [M!] Write with `set_if_neq` wherever a `Changed` filter is watching
  - BV-ECS-26 [M] Put `Changed<T>` in the filter so the system can be skipped
  - BV-ECS-27 [M] Do not use `Changed<T>` to mean `Added<T>`
  - BV-ECS-28 [S] Read a change in the same schedule that wrote it
  - BV-ECS-29 [S] Bypass change detection only where the write is bookkeeping

- **Structural change**
  - BV-ECS-30 [M] Do not read back what a command has not applied yet
  - BV-ECS-31 [M] Reach for an exclusive system last, and say what forced it
- Decided by tools

---

## Components

### BV-ECS-01 [M] Leave component fields public

Component fields are `pub`. This is the one place a struct in this standard is allowed to expose
its storage.

The single exception is a relationship **target**, the collection side of a
`#[relationship_target]` pair. The engine maintains that vector and overwrites what a caller writes
to it, so Bevy's own hierarchy has `ChildOf(pub Entity)` public and `Children(Vec<Entity>)` not.

**Why:** the ECS *is* the accessor: `transform.translation.x += 1.0` is how the engine is used.
Reflection, the scene format, `bsn!` and the remote protocol read and write fields by name, so a
private field is invisible to the inspector, unserialisable and unpatchable from a scene.

**Check:** does the component have accessor methods that only forward to a field? Delete them. Does
it have a field that a method is guarding? That is BV-ARCH-04's case, and the guard belongs in a
domain type. A private field on anything but a relationship target is one of those two.

### BV-ECS-02 [M] Give a component one fact to hold

A component holds one thing about an entity. Two fields written by different systems, changing at
different rates, or read by different queries are two components.

**Why:** the component is the unit of querying, of change detection and of archetype layout, so a
field bundled with an unrelated one cannot be queried or marked changed without the other, and a
system that reads a single `f32` pays for the whole struct's cache line.

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
`PartialEq` and `Default` where each of them means something for the type; `PartialEq` is what
`set_if_neq` (BV-ECS-25) needs.

**Why:** `Debug` is what every panic, `info!` and test failure prints, so without it the value is a
hole in the output exactly when it is needed. `Reflect` with `#[reflect(Component)]` is what an
inspector, a scene and the remote protocol see, and being opt-in it is forgotten silently.

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

**Why:** the component type is the query key, so a bare primitive can appear only once per entity
and collides across every feature that wanted one. The name is also the only place the unit can
live: a query for `&Speed` reads as a sentence, and one for `&f32` as a type puzzle.

**Check:** does any component name fail to say what the value means — `Value`, `Data`, `Amount`,
`Inner`? Rename it after the quantity.

### BV-ECS-05 [M] Never mark a component `#[non_exhaustive]`

Components are constructed by struct literal, at every spawn site, in every crate. Grow one by
adding a *new component* plus a `#[require]`, which breaks no existing spawn.

**Why:** `#[non_exhaustive]` forbids literal construction outside the defining crate, and a literal
is the only construction a component has. The attribute that protects a growing struct elsewhere in
this standard here breaks every spawn site in another crate.

**Check:** grep for `#[non_exhaustive]` immediately above a `#[derive(…Component…)]`. There should
be none.

### BV-ECS-06 [M] Express "always has" with `#[require]`

If every entity with `Enemy` also needs `Health` and `Transform`, `Enemy` declares that:
`#[require(Health, Transform)]`. The spawn site names only what it is choosing.

**Why:** the invariant lives once, on the type that owns it, instead of at every spawn site where
it can be forgotten. The engine applies it on every spawn of that type, so unlike a group of
components passed by hand, a `#[require]` cannot be half-applied.

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
live: with `Health(0.0)` as the `Default`, `#[require(Health)]` spawns an entity that is dead on the
frame it appears, and a death system running that frame acts on it.

**Check:** for each `#[require(T)]` with no value, read `T::default()` and ask whether an entity in
that state for one frame is harmless. If not, give the requirement a value.

### BV-ECS-08 [M] Do not build a "bundle" type by hand

A struct or type alias whose only purpose is to be spawned as a group is the removed bundle,
reintroduced. Use `#[require]` for what is always true and a tuple at the spawn site for what is
being chosen.

**Why:** the group type cannot be queried, cannot be inserted in part without a second definition,
and changes every call site silently when it gains a field. A `#[require]` puts the same
information where the query, the inspector and the scene format can see it.

**Check:** search for structs deriving `Bundle`, and for `fn *_bundle() -> impl Bundle`. Each one is
either a `#[require]` or a tuple.

### BV-ECS-09 [M] Never spawn a unit

`commands.spawn(())` and a `()` sitting inside a spawn tuple are mistakes. Use `spawn_empty()` when
an entity really has no components. `bevy_lint`'s `bevy::unit_in_bundle` reports them, but cannot
run on 0.20 yet (BV-BUILD-17), so the Check is the review.

**Why:** `()` implements `Bundle` and inserts nothing, so it compiles and does nothing. The usual
cause is a method returning `()` where a component was expected:
`Transform::from_xyz(…).rotate_z(PI)` is a unit, so the transform never reaches the entity.

**Check:** for each component expression in a spawn tuple, check that the last call returns `Self`.
The mutating `Transform` methods (`rotate_z`, `translate_around`) do not; the `with_*` builders do.

```rust
// verified — one of these two spawns reaches the entity and one silently does not
use bevy::prelude::*;
use core::f32::consts::PI;

/// A barrel always carries a transform, so `#[require]` guarantees one is
/// present — which is precisely what hides the mistake below.
#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
#[require(Transform)]
pub struct Barrel;

/// BAD: `rotate_z` takes `&mut self` and returns `()`, so the bundle is
/// `(Barrel, ())`. `()` is the bundle that inserts nothing, `#[require]`
/// fills the hole with `Transform::default()`, and the barrel sits at the
/// origin unrotated. No line of this function looks wrong.
fn place_wrong(mut commands: Commands) {
    commands.spawn((Barrel, Transform::from_xyz(3.0, 1.0, 0.0).rotate_z(PI)));
}

/// GOOD: every call in the chain returns `Transform`, so the last one *is*
/// the component. `with_rotation` is the builder that `rotate_z` is not.
fn place(mut commands: Commands) {
    commands.spawn((
        Barrel,
        Transform::from_xyz(3.0, 1.0, 0.0).with_rotation(Quat::from_rotation_z(PI)),
    ));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_unit_leaves_the_barrel_at_the_origin() {
        let mut app = App::new();
        app.add_systems(Update, (place_wrong, place));
        app.update();

        let mut barrels = app.world_mut().query_filtered::<&Transform, With<Barrel>>();
        let placed: Vec<Transform> = barrels.iter(app.world()).copied().collect();

        let spin = Quat::from_rotation_z(PI);
        let wanted = Transform::from_xyz(3.0, 1.0, 0.0).with_rotation(spin);
        assert_eq!(placed.len(), 2);
        // One barrel got the rotation. The other got the required default,
        // because `()` inserted nothing and nothing said so.
        assert!(placed.contains(&wanted));
        assert!(placed.contains(&Transform::default()));
    }
}
```

### BV-ECS-10 [S] Give a marker component the derives a marker needs

A marker is a unit struct: `#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)] pub struct Player;`

The set stops there: `PartialEq`, `Eq` and `Hash` on a type with no data distinguish nothing.
`bevy_lint`'s restriction lints `bevy::missing_default`, `bevy::missing_clone` and
`bevy::missing_copy` ask for `Default`, `Clone` and `Copy` on a unit struct, but cannot run on 0.20
yet (BV-BUILD-17), so the Check is the review.

**Why:** `Default` is what lets the marker be named in someone else's `#[require]`, and `Clone` and
`Copy` cost nothing on a zero-sized type while letting it be cloned with an entity or written into a
scene patch. A crate downstream cannot add one that is missing.

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
the other, and despawning follows the link. A hand-kept `Vec<Entity>` does neither, and holds ids
despawned frames ago until a `get` returns `None` where nothing expected one.

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

**Why:** `#[derive(Reflect)]` makes a type reflectable and registration makes it *findable*: the
inspector, the scene loader and the remote protocol all look types up in the registry. An
unregistered type does not error; it is simply absent, which reads as "the tool is broken".

**Check:** count `#[derive(…Reflect…)]` in the crate and `register_type::<` calls in the plugins. If
the second number is smaller and `reflect_auto_register` is off, the difference is invisible types.

### BV-ECS-14 [M] Give an asset handle a component of its own

`Handle<T>` is not a component. Wrap it: `#[derive(Component)] struct Portrait(pub Handle<Image>);`

**Why:** an entity may want two handles of one asset type, a portrait and an icon both
`Handle<Image>`, and a bare handle as the component type allows only one, whichever was inserted
last. The wrapper's name is also the only place the meaning of the asset can be recorded.

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

**Why:** `&mut` is both an exclusive lock for the scheduler and a change-detection trigger, so
asking for it only to read keeps every system touching that component from running alongside this
one, and lets one stray mutable deref mark every entity changed.

**Check:** for each `&mut` in a query, find the assignment. If the body only reads, the `mut` is two
bugs waiting.

### BV-ECS-17 [M] Put a zero-sized marker in the filter, never in the data

`Query<&Transform, With<Player>>`, not `Query<(&Transform, &Player)>`. `bevy_lint`'s
`bevy::zst_query` reports the data form, but cannot run on 0.20 yet (BV-BUILD-17), so the Check is
the review.

**Why:** a marker has no runtime data, so fetching it retrieves nothing while still adding a column
to the query's access set and a binding the loop discards: the `_` in `for (transform, _) in &query`
is the giveaway. `With` states the same restriction as what it is, a filter.

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

**Why:** each `Option` doubles the shapes the body must handle, most of them combinations no entity
has. Two systems split by `With<A>` and `Without<A>` say which case each is for, visit only the
entities in that case, and can be scheduled independently.

**Check:** count the `Option<&T>` in the query, which is what the rule is about — the branching
they force is just as reachable through `map_or`, `zip` or one `match`, so counting `if let Some`
in the body misses the functional spellings this standard's sibling actively prefers. Three or more
is the signal; split by `With`/`Without` instead.

### BV-ECS-19 [S] Iterate a query with `for`, not a combinator chain

`for item in &query` and `for item in &mut query`. This standard's general preference for `map`,
`filter` and `collect` over loops does not extend to query iteration. A restriction goes in the
query's filter, which skips entities before they are fetched, rather than in a `.filter()`.

**Why:** the loop is doing effects, which is the case the general rule reserves `for` for: the item
is a `Mut<T>` whose borrow of the query cannot outlive the iteration, so there is nothing to collect
and no value to return.

**Check:** a `.for_each(` or a `.filter(` on a query iterator is either a filter that belongs in the
type, or a loop that has been written the long way.

### BV-ECS-20 [M] Name a query type once it needs two lines

A query with several data items and several filters gets a `type` alias with a name from the domain.

**Why:** the alias names a concept, `Combatants` or `VisibleSprites`, which the inline type never
does, and the systems that share the shape reuse it. It also satisfies `clippy::type_complexity`,
which this standard keeps on because the compliant form is better code than a suppression.

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
    (Entity, &'static Health, &'static Transform),
    (With<Enemy>, Without<Invulnerable>, Changed<Health>),
>;

/// Every item the alias names is read, and nothing asks for `&mut` it will not
/// write — the alias does not get to opt out of BV-ECS-15 and BV-ECS-16.
fn cull(mut commands: Commands, combatants: Combatants) {
    for (entity, health, transform) in &combatants {
        if health.0 <= 0.0 || transform.translation.y < -100.0 {
            commands.entity(entity).despawn();
        }
    }
}
```

### BV-ECS-21 [S] Reach for `iter_many` when the set of entities is already known

Given a `Children`, a relationship target, or a stored list of ids, `query.iter_many(ids).matched()`
fetches exactly those that match. Iterating the whole query and testing membership does not.

Since 0.20, `iter_many`, `iter_many_mut`, `iter_many_unique(_mut)` and their sorted and `par_`
variants yield `Result<Item, QueryEntityError>`, one per id, and `.matched()` keeps the old
meaning. A bare `.count()`, `.next().is_some()` or `for _ in` still compiles, and now counts ids
that do not match.

**Why:** the cost of the loop should be the number of entities you care about, not the number that
exist. A membership test inside a full iteration is `O(all)` where the direct form is `O(wanted)`,
and it reads as a search where the code already knows the answer.

**Check:** look for `if ids.contains(&entity)` inside a query loop. That is `iter_many` written out.
Then, for each `iter_many`, check that its items go through `.matched()` or are handled as `Result`.

### BV-ECS-22 [M] Never nest a query inside itself

A loop over a query cannot contain another loop over the same query. Use `iter_combinations` for
pairs, or split the data into two queries with disjoint filters.

**Why:** the borrow checker rejects the mutable case outright, and the read-only case is a quadratic
loop that looks linear. `iter_combinations` also visits each unordered pair once rather than twice,
which is usually what collision or attraction code actually wanted.

**Check:** search for a `for` over a query inside another `for` over a query and check the two are
different queries with filters that cannot both match one entity.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Default, Reflect)]
#[reflect(Component)]
pub struct Velocity(pub Vec2);

/// Bodies closer together than this push each other apart.
const PERSONAL_SPACE: f32 = 4.0;

/// A `for` over `bodies` inside another `for` over `bodies` cannot be
/// written: the outer loop borrows the query for the whole of its body.
/// `iter_combinations_mut` is the API that hands out `K` disjoint items at
/// once, and `fetch_next` rather than `for` is what makes that sound — each
/// array must be dropped before the next is produced, so it cannot be an
/// `Iterator`. The read-only twin is `for [a, b] in bodies.iter_combinations()`.
fn separate(mut bodies: Query<(&Transform, &mut Velocity)>) {
    let mut pairs = bodies.iter_combinations_mut::<2>();
    while let Some([(here, mut mine), (there, mut theirs)]) = pairs.fetch_next() {
        let offset = there.translation.truncate() - here.translation.truncate();
        if offset.length_squared() >= PERSONAL_SPACE * PERSONAL_SPACE {
            continue;
        }
        // Each unordered pair is visited once, never twice, so the
        // equal-and-opposite impulses are written here as a pair instead of
        // halved and applied from both ends.
        let push = offset.normalize_or_zero();
        mine.0 -= push;
        theirs.0 += push;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn velocity(app: &App, entity: Entity) -> Option<Vec2> {
        app.world().entity(entity).get::<Velocity>().map(|v| v.0)
    }

    #[test]
    fn only_the_close_pair_is_pushed_apart() {
        let mut app = App::new();
        app.add_systems(Update, separate);
        let body = |x: f32| (Transform::from_xyz(x, 0.0, 0.0), Velocity::default());
        let left = app.world_mut().spawn(body(-1.0)).id();
        let right = app.world_mut().spawn(body(1.0)).id();
        let loner = app.world_mut().spawn(body(100.0)).id();

        app.update();

        // The body is symmetric in the pair, so the result does not depend
        // on which way round `fetch_next` handed the two back.
        assert_eq!(velocity(&app, left), Some(Vec2::new(-1.0, 0.0)));
        assert_eq!(velocity(&app, right), Some(Vec2::new(1.0, 0.0)));
        assert_eq!(velocity(&app, loner), Some(Vec2::ZERO));
    }
}
```

### BV-ECS-23 [S] Parallelise a query only against a measurement

`par_iter_mut` is for a loop that has been measured and found hot. Write the serial form first.

**Why:** the parallel form has per-batch overhead and forces the body to be `Send`, and below a few
thousand entities it is reliably slower. It also hides the usual real answer: a query fetching more
than it reads (BV-ECS-15), or work that belongs in `FixedUpdate` at a lower rate.

**Check:** is there a benchmark or a profile naming this system? If not, the serial form is the one
to ship.

### BV-ECS-24 [S] Reach for `contiguous_iter` only against a measured hot loop

`Query::contiguous_iter`, added in 0.19, yields one slice per table rather than one item per entity,
which is what a SIMD kernel or a cache-blocked pass needs. It replaces a structure-of-arrays kept by
hand beside the components.

It is not a drop-in for `for x in &query`:

- The call returns `Result`, because a sparse-set component is not contiguously iterable and
  nothing in the type system knows which. Take the error with `?`, never `.unwrap()` (BV-ERR-01).
- The filter is bound by `F: ArchetypeFilter`, so `Changed<T>` does not compile here at all.
- The mutable form marks every entity in the slice changed unless the write goes through
  `bypass_change_detection` (BV-ECS-29).

**Why:** it is the only way to get contiguous slices without leaving the ECS, so a hand-kept
`Vec<f32>` can go, and with it the bug where it drifts from the entities. The price is a nested loop
and a run-time failure the day a component turns sparse, which only a hot loop repays.

**Check:** for each `contiguous_iter`, find the measurement. Without one it is a nested loop that
reads worse than the flat iteration and starts failing at run time the day a component becomes
sparse.

```rust
// verified — GOOD
use bevy::ecs::query::QueryNotDenseError;
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Decay(pub f32);

/// The outer loop is tables, the inner is entities within one table — that
/// nesting is the whole shape, and it is the price of the slices. The error
/// is the query's own: `Health` or `Decay` stored sparsely makes this fail
/// at run time, having compiled, so it propagates rather than unwrapping.
fn decay_health(mut lives: Query<(&mut Health, &Decay)>) -> Result<(), QueryNotDenseError> {
    for (mut health, decay) in lives.contiguous_iter_mut()? {
        for (health, decay) in health.iter_mut().zip(decay) {
            health.0 *= decay.0;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::ecs::system::RunSystemOnce as _;

    /// Slices, not items: the assertion is that one call covered every entity
    /// in one table, which is the property the flat iterator cannot offer.
    #[test]
    fn one_table_is_one_slice() {
        let mut world = World::new();
        for _ in 0..4 {
            world.spawn((Health(100.0), Decay(0.5)));
        }
        let mut query = world.query::<(&mut Health, &Decay)>();
        let mut slices = 0;
        let mut covered = 0;
        if let Ok(tables) = query.contiguous_iter_mut(&mut world) {
            for (health, _) in tables {
                slices += 1;
                covered += health.len();
            }
        }
        assert_eq!((slices, covered), (1, 4));
    }

    #[test]
    fn decay_multiplies_every_entity() {
        let mut world = World::new();
        world.spawn((Health(100.0), Decay(0.5)));
        world.spawn((Health(40.0), Decay(0.25)));
        // No annotation needed here: `QueryNotDenseError` is not `BevyError`,
        // so only the identity `IntoResult` impl applies and `Out` is the
        // system's own `Result`. Both layers are pinned.
        assert!(matches!(world.run_system_once(decay_health), Ok(Ok(()))));

        let mut query = world.query::<&Health>();
        let mut got: Vec<f32> = query.iter(&world).map(|h| h.0).collect();
        got.sort_by(f32::total_cmp);
        assert_eq!(got, [10.0, 50.0]);
    }
}
```

## Change detection

### BV-ECS-25 [M!] Write with `set_if_neq` wherever a `Changed` filter is watching

`health.set_if_neq(Health(new))` rather than `*health = Health(new)` when the new value is often the
old one.

*Relaxed form:* a component nothing filters on, and nothing reacts to, may be assigned directly —
but that is a fact about today's readers, and it changes the moment someone adds a `Changed` filter.

**Why:** `DerefMut` on `Mut<T>` marks the component changed, so assigning the same value every frame
marks every entity changed every frame. Every downstream `Changed<T>` filter then matches
everything: it goes on compiling and matching, and no longer means anything.

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
On a component that is written rarely, `#[component(summary_tick)]` (new in 0.20) keeps a
per-column change tick, so the filter can skip whole columns.

**Why:** as a filter it is applied during iteration, so unchanged entities are never fetched; in the
body it is applied after the fetch, so the loop still visits everything. The filter also puts
"reactive" in the system's signature, where the body form hides it behind an early `continue`.

**Check:** grep for `is_changed()` inside a query loop. Unless the body needs both the changed and
the unchanged entities, it is a filter that has escaped into the body.

### BV-ECS-27 [M] Do not use `Changed<T>` to mean `Added<T>`

`Added<T>` matches the frame the component was inserted. `Changed<T>` matches insertion *and* every
subsequent write.

**Why:** `Changed` also matches the insertion frame, so setup code under it appears to work and then
runs again on every later write, spawning a second sound or a second child. The bug surfaces only
when someone starts mutating the component, which may be months later and in another module.

**Check:** for each `Changed<T>` filter, ask whether running twice for one entity is acceptable. If
not, it is `Added<T>` — or, better, an observer on `Add` (`references/events.md` BV-EVENT-13).

```rust
// verified — the same body under both filters, counted
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

/// How many times the pickup jingle was started, under each spelling of the
/// filter. One entity picking one thing up should start exactly one sound.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Jingles {
    /// `Added`: one per entity, for the life of that entity.
    pub on_added: usize,
    /// `Changed`: one per entity, plus one for every later write.
    pub on_changed: usize,
}

/// GOOD. The body below is identical; only the filter differs.
fn jingle_on_added(arrived: Query<(), Added<Health>>, mut jingles: ResMut<Jingles>) {
    jingles.on_added += arrived.iter().count();
}

/// BAD. `Changed` matches the insertion frame as well, so this passes review
/// and passes its first test — until somebody, months later and in another
/// module, subtracts a point of `Health` and the jingle plays again.
fn jingle_on_changed(touched: Query<(), Changed<Health>>, mut jingles: ResMut<Jingles>) {
    jingles.on_changed += touched.iter().count();
}

#[derive(Debug, Default)]
pub struct PickupPlugin;

impl Plugin for PickupPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Jingles>()
            .add_systems(Update, (jingle_on_added, jingle_on_changed));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn changed_fires_a_second_time_and_added_does_not() {
        let mut app = App::new();
        app.add_plugins(PickupPlugin);
        let hero = app.world_mut().spawn(Health(100.0)).id();

        app.update();

        // Both filters match the insertion frame. This is where the bug hides.
        assert_eq!(app.world().resource::<Jingles>().on_added, 1);
        assert_eq!(app.world().resource::<Jingles>().on_changed, 1);

        let Some(mut health) = app.world_mut().get_mut::<Health>(hero) else {
            unreachable!()
        };
        health.0 -= 1.0;

        app.update();

        assert_eq!(app.world().resource::<Jingles>().on_added, 1);
        assert_eq!(app.world().resource::<Jingles>().on_changed, 2);
    }
}
```

### BV-ECS-28 [S] Read a change in the same schedule that wrote it

A `Changed<T>` filter sees writes since the reading system last ran. Keep the writer and the reader
in the same schedule.

**Why:** `FixedUpdate` runs zero or several times a frame, so an `Update` reader sees a fixed-step
write once however often it happened, and a fixed-step reader may miss an `Update` write entirely.
The ticks are consistent, but "since you last ran" across schedules is not "this frame".

**Check:** for each `Changed<T>` reader, find the writers. Any writer in a different schedule needs
a stated reason the count does not matter.

### BV-ECS-29 [S] Bypass change detection only where the write is bookkeeping

`Mut::bypass_change_detection` is for writes that are not changes to the game's state — a cached
value refreshed from its source, a counter nothing reacts to.

**Why:** the bypass is the only way to write without marking, so using it for a real change leaves
everything downstream believing the old value. Used to quiet a noisy filter, it hides that
`set_if_neq` (BV-ECS-25) was the answer.

**Check:** each call needs a comment naming what does *not* need to know about this write. If the
comment cannot be written, the write is a change.

## Structural change

### BV-ECS-30 [M] Do not read back what a command has not applied yet

`Commands` queue work that runs at the next sync point. Within the same system, the entity spawned
two lines ago is not in any query.

**Why:** the deferral is what lets systems run in parallel, and it is invisible: the code reads as
if it were immediate, and a `get` on the id just spawned returns `None` with no error to say why.

**Check:** in each system, is any id from `commands.spawn(…).id()` used to look something up in the
same body? Move the read to a later system: the schedule puts a sync point between the two.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
pub struct Shell {
    pub damage: u32,
}

/// What each half of the frame managed to read back about the shell.
#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Sighting {
    /// Filled in by the system that did the spawning, from the id it holds.
    pub from_the_spawner: Option<u32>,
    /// Filled in by a system that runs after the queue was applied.
    pub after_the_sync_point: Option<u32>,
}

/// The trap. `shell` is a real, reserved `Entity` — and the lookup still
/// misses, because `spawn` queued a command rather than changing the world.
/// Nothing errors: the query simply has nothing to hand back, which is
/// indistinguishable from "that entity did not match".
fn fire(mut commands: Commands, shells: Query<&Shell>, mut sighting: ResMut<Sighting>) {
    let shell = commands.spawn(Shell { damage: 12 }).id();
    sighting.from_the_spawner = shells.get(shell).ok().map(|found| found.damage);
}

/// The fix, and the whole of it: read from a system that runs later.
fn confirm(shells: Query<&Shell, Added<Shell>>, mut sighting: ResMut<Sighting>) {
    sighting.after_the_sync_point = shells.iter().next().map(|shell| shell.damage);
}

#[derive(Debug, Default)]
pub struct GunneryPlugin;

impl Plugin for GunneryPlugin {
    fn build(&self, app: &mut App) {
        // `chain` orders the two, and the schedule inserts an
        // `ApplyDeferred` between them because `fire` has a deferred
        // parameter. That barrier is where the entity actually appears.
        app.init_resource::<Sighting>()
            .add_systems(Update, (fire, confirm).chain());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_spawning_system_cannot_see_its_own_spawn() {
        let mut app = App::new();
        app.add_plugins(GunneryPlugin);
        // Seeded, so that "the system looked and found nothing" cannot be
        // read as "the system never looked".
        let unwritten = Some(u32::MAX);
        app.insert_resource(Sighting {
            from_the_spawner: unwritten,
            after_the_sync_point: unwritten,
        });

        app.update();

        let sighting = app.world().resource::<Sighting>();
        assert_eq!(sighting.from_the_spawner, None);
        assert_eq!(sighting.after_the_sync_point, Some(12));
    }
}
```

### BV-ECS-31 [M] Reach for an exclusive system last, and say what forced it

A system taking `&mut World` cannot run in parallel with anything. Write one only when the work
genuinely needs the whole world at once, and put the reason in a doc comment.

Since 0.20, `&mut World` is itself a `SystemParam` and may appear anywhere in the parameter list.
`ExclusiveSystemParam` is gone, and exclusivity is tracked at run time rather than compile time, so
a parameter that conflicts with `&mut World` is a run-time error, not a compile error.

**Why:** an exclusive system is a global barrier in the schedule: everything before it finishes,
it runs alone, everything after starts. One is usually fine and four is a game that no longer runs
its systems in parallel.

**Check:** for each `&mut World` parameter, name what the system could not do without it. "Needed a
resource and a query" and "needed a command applied now" both have a non-exclusive form; "runs a
scene through the type registry" does not.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `unwrap_used` | deny | `query.single().unwrap()` — `single()` returns a `Result`; propagate it with `?` |
