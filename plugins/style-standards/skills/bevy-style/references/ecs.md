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
  - BV-ECS-08 [M] Never spawn a unit
  - BV-ECS-09 [S] Give a marker component the derives a marker needs
  - BV-ECS-10 [S] Mark a component immutable when a hook depends on it
  - BV-ECS-11 [M] Model a link between entities as a relationship
  - BV-ECS-12 [M] Register each instantiation of a generic reflected type
  - BV-ECS-13 [M] Give an asset handle a component of its own

- **Queries**
  - BV-ECS-14 [M] Query the narrowest data that answers the question
  - BV-ECS-15 [M] Ask for `&mut` and `ResMut` only where the system writes
  - BV-ECS-16 [M] Put a zero-sized marker in the filter, never in the data
  - BV-ECS-17 [S] Split a system before reaching for a third `Option<&T>`
  - BV-ECS-18 [S] Iterate a query with `for` where the body writes, not `for_each`
  - BV-ECS-19 [M] Name a query type once it needs two lines
  - BV-ECS-20 [S] Reach for `iter_many` when the set of entities is already known
  - BV-ECS-21 [M] Never nest a query inside itself
  - BV-ECS-22 [M] Parallelise a query only against a measurement
  - BV-ECS-23 [M] Reach for `contiguous_iter` only for a loop a profile names

- **Change detection**
  - BV-ECS-24 [M] Write with `set_if_neq` wherever a `Changed` filter is watching
  - BV-ECS-25 [M] Put `Changed<T>` in the filter so the system can be skipped
  - BV-ECS-26 [M] Do not use `Changed<T>` to mean `Added<T>`
  - BV-ECS-27 [S] Bypass change detection only where the write is bookkeeping

- **Structural change**
  - BV-ECS-28 [M] Do not read back what a command has not applied yet
  - BV-ECS-29 [M] Reach for an exclusive system last, and say what forced it

---

## Components

### BV-ECS-01 [M] Leave component fields public

Departs from RS-API-20. Component fields are `pub`: a component is the one struct in this standard
whose storage is its interface.

The single exception is a relationship **target**, the collection side of a `#[relationship_target]`
pair. The engine maintains that vector and overwrites what a caller writes to it, so Bevy's own
hierarchy has `ChildOf(pub Entity)` public and `Children(Vec<Entity>)` not.

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

Departs from RS-API-35. `#[derive(Component, Debug, Reflect)]`, plus `#[reflect(Component)]`, on
every component, public or not. Add `Clone`, `Copy`, `PartialEq` and `Default` where each of them
means something for the type; `PartialEq` is what `set_if_neq` (BV-ECS-24) needs.

**Why:** every panic, `info!` and test failure prints a component, whoever can name its type.
`Reflect` with `#[reflect(Component)]` is what an inspector, a scene and the remote protocol see,
and being opt-in it is forgotten silently.

**Check:** read each `#[derive(Component` list for `Debug`, and each `Reflect` for the matching
`#[reflect(Component)]` — deriving the trait without the registration attribute leaves the type
reflected but not recognised as a component.

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

Departs from RS-API-51. Components are constructed by struct literal, at every spawn site, in every
crate. Grow one by adding a *new component* plus a `#[require]`, which breaks no existing spawn.

**Why:** `#[non_exhaustive]` forbids literal construction outside the defining crate, and a literal
is the only construction a component has. The attribute that protects a growing struct elsewhere in
this standard here breaks every spawn site in another crate.

**Check:** `rg -n -A1 '#\[non_exhaustive\]' src/` lists each marked type with the line after it; one
whose derive names `Component` is the finding.

### BV-ECS-06 [M] Express "always has" with `#[require]`

If every entity with `Enemy` also needs `Health` and `Transform`, `Enemy` declares that:
`#[require(Health, Transform)]`. The spawn site names only what it is choosing, as a tuple. A struct
or type alias that exists only to be spawned as a group is the removed bundle, reintroduced.

**Why:** the invariant lives once, on the type that owns it, and the engine applies it on every
spawn, so it cannot be half-applied. A group type cannot be queried or inserted in part, and changes
every spawn site silently when it gains a field.

**Check:** look at every `spawn` for the same component appearing beside the same other component
more than twice. That repetition is a `#[require]` that has not been written. Then
`rg -n 'derive\([^)]*\bBundle\b|-> impl Bundle' src/` finds a bundle of the game's own; each is a
`#[require]` or a tuple.

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

### BV-ECS-08 [M] Never spawn a unit

`commands.spawn(())` and a `()` sitting inside a spawn tuple are mistakes. Use `spawn_empty()` when
an entity really has no components.

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

### BV-ECS-09 [S] Give a marker component the derives a marker needs

A marker is a unit struct:
`#[derive(Component, Debug, Clone, Copy, Default, Reflect)] #[reflect(Component)] pub struct Player;`

The set stops there: `PartialEq`, `Eq` and `Hash` on a type with no data distinguish nothing.

**Why:** `Default` is what lets the marker be named in someone else's `#[require]`, and `Clone` and
`Copy` cost nothing on a zero-sized type while letting it be cloned with an entity or written into a
scene patch. A crate downstream cannot add one that is missing.

**Check:** is every unit-struct component `Default`? A marker that is not cannot be required by
another component.

### BV-ECS-10 [S] Mark a component immutable when a hook depends on it

`#[component(immutable)]` makes a component insert-and-remove only. Use it where a lifecycle hook,
an index, or a relationship derives something from the value.

**Why:** an immutable component cannot be changed behind the back of the hook that indexed it, so
the derived structure cannot go stale. It is also a genuine statement about the type: an identity, a
kind, or a spawn-time configuration is not something a system should reach in and edit.

**Check:** for each component read by a hook or observer on `Insert`, ask what happens if a system
mutates it afterwards. If the answer is a stale index, the component wants to be immutable.

### BV-ECS-11 [M] Model a link between entities as a relationship

Parent and child are `ChildOf` and `Children`. Any other one-to-many link — a turret's owner, a
squad's members — is a `#[relationship]` / `#[relationship_target]` pair, not a bare `Entity` field
plus a `Vec<Entity>` kept in step by hand. Where the many side should not outlive the one, the
target says `linked_spawn`, as `Children` does; without it, despawning the one removes only the
link.

**Why:** a relationship maintains both sides, so removing the target cannot leave a dangling id on
the other. A hand-kept `Vec<Entity>` does neither, and holds ids despawned frames ago until a `get`
returns `None` where nothing expected one.

**Check:** read each `Vec<Entity>` and each `Entity` field of a component. Each is either a
relationship or needs a written reason it cannot be one. For each `#[relationship_target]`, ask what
a despawn of its entity should do to the related ones, and look for `linked_spawn` if the answer is
"despawn them too".

```rust
// verified
use bevy::prelude::*;

/// The one side. `#[entities]` is what makes the id survive entity remapping.
#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
#[relationship(relationship_target = Crew)]
pub struct CrewOf(#[entities] pub Entity);

/// The many side. Bevy maintains it; nothing writes to it by hand. A crew does
/// not outlive its ship, so the target is `linked_spawn`.
#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
#[relationship_target(relationship = CrewOf, linked_spawn)]
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

    #[test]
    fn despawning_the_ship_despawns_its_crew() {
        let mut world = World::new();
        let ship = world.spawn_empty().id();
        let pilot = world.spawn(CrewOf(ship)).id();

        world.entity_mut(ship).despawn();
        assert!(world.get_entity(pilot).is_err());
    }
}
```

### BV-ECS-12 [M] Register each instantiation of a generic reflected type

`#[derive(Reflect)]` registers its type: `reflect_auto_register`, part of `default_app` and so of
every collection built on it (BV-BUILD-02), collects each derived type as the `App` is created. A
generic type is the exception, because the derive cannot know its instantiations: each one the game
uses is registered in the plugin that uses it, `app.register_type::<Cooldown<Dash>>()`.

**Why:** registration makes a type *findable*: the inspector, the scene loader and the remote
protocol all look types up in the registry. An unregistered type does not error; it is simply
absent, which reads as "the tool is broken".

**Check:** for each generic type deriving `Reflect`, find a `register_type::<…>` for every
instantiation the game names. A `register_type` for a non-generic type is noise. A manifest without
`default_app` — a hand-picked list (BV-BUILD-03), or `2d_api`, `3d_api` or `common_api` on their own
— leaves every type unregistered unless it adds `reflect_auto_register`.

```rust
// verified
use bevy::prelude::*;
use core::marker::PhantomData;

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

#[derive(Debug, Clone, Copy, Reflect)]
pub struct Dash;

/// One cooldown per ability. Generic, so its instantiations are the game's
/// to name: the derive registers none of them.
#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
pub struct Cooldown<A: Send + Sync + 'static> {
    pub seconds: f32,
    #[reflect(ignore)]
    ability: PhantomData<A>,
}

#[derive(Debug, Default)]
pub struct AbilityPlugin;

impl Plugin for AbilityPlugin {
    fn build(&self, app: &mut App) {
        // `Health` needs nothing here: its derive registered it.
        app.register_type::<Cooldown<Dash>>();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use core::any::TypeId;

    fn registered<T: 'static>(app: &App) -> bool {
        let registry = app.world().resource::<AppTypeRegistry>().read();
        registry.get(TypeId::of::<T>()).is_some()
    }

    #[test]
    fn the_derive_registers_the_type_and_the_plugin_the_instantiation() {
        let mut app = App::new();
        assert!(registered::<Health>(&app));
        assert!(!registered::<Cooldown<Dash>>(&app));

        app.add_plugins(AbilityPlugin);
        assert!(registered::<Cooldown<Dash>>(&app));
    }
}
```

### BV-ECS-13 [M] Give an asset handle a component of its own

`Handle<T>` is not a component. Wrap it: `#[derive(Component)] struct Portrait(pub Handle<Image>);`

**Why:** an entity may want two handles of one asset type, a portrait and an icon both
`Handle<Image>`, and a bare handle as the component type allows only one, whichever was inserted
last. The wrapper's name is also the only place the meaning of the asset can be recorded.

**Check:** read each `Handle<` inside a `spawn` tuple: one with no component of its own around it is
the finding.

## Queries

### BV-ECS-14 [M] Query the narrowest data that answers the question

Ask for the components the body reads, and no others. `Query<&Transform>` rather than
`Query<(&Transform, &Health, &Sprite)>` when only the transform is used.

**Why:** the components in the query are the system's declared access, and the scheduler uses that
declaration to decide what may run in parallel. An unused `&Sprite` does not slow the body down; it
keeps this system from running beside any system that writes a sprite, for nothing.

**Check:** for each item in the query tuple, find its use in the body. An unused one is a scheduling
constraint with no reader.

### BV-ECS-15 [M] Ask for `&mut` and `ResMut` only where the system writes

`&T` for reading. `&mut T` exclusively for components the body assigns to. The same for resources:
`Res<T>` to read, `ResMut<T>` only to assign, and `Res<Assets<T>>` with `get` unless the system adds
or edits an asset.

**Why:** `&mut` is both an exclusive lock for the scheduler and a change-detection trigger, so
asking for it only to read blocks every system touching that data, and one stray mutable deref marks
it changed: every entity's `Changed`, or a `resource_changed` condition that fires every frame.

**Check:** for each `&mut` in a query and each `ResMut`, find the write. If the body only reads, the
`mut` is two bugs waiting. `ResMut<Assets<Image>>` is the costliest case: render extraction, UI and
every sprite read it, so a system holding it to read serialises against all of them.

### BV-ECS-16 [M] Put a zero-sized marker in the filter, never in the data

`Query<&Transform, With<Player>>`, not `Query<(&Transform, &Player)>`.

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

### BV-ECS-17 [S] Split a system before reaching for a third `Option<&T>`

One or two `Option<&T>` in a query describe a genuinely optional part. Three describe several
different jobs that have been written as one.

**Why:** each `Option` doubles the shapes the body must handle, most of them combinations no entity
has. Two systems split by `With<A>` and `Without<A>` say which case each is for, visit only the
entities in that case, and can be scheduled independently.

**Check:** count the `Option<&T>` in the query, which is what the rule is about — the branching they
force is just as reachable through `map_or`, `zip` or one `match`, so counting `if let Some` in the
body misses the functional spellings this standard's sibling actively prefers. Three or more is the
signal; split by `With`/`Without` instead.

### BV-ECS-18 [S] Iterate a query with `for` where the body writes, not `for_each`

`for item in &mut query` when the body writes — through `Mut<T>`, `Commands` or a `MessageWriter` —
rather than `.iter_mut().for_each(…)`. A read-only pass that builds a value is a pipeline here as
anywhere (`rust-style` RS-FUNC-02), the way the crossing point in BV-ARCH-03 collects its query. A
restriction goes in the query's filter, which skips entities before they are fetched, rather than in
a `.filter()`.

**Why:** a write is an effect, the case `rust-style` keeps `for` for (RS-FUNC-05): the write through
`Mut<T>` is the result, so there is nothing to collect, and `for` keeps the `?`, `continue` and
`break` that `for_each` gives up.

**Check:** a `.for_each(` on a query iterator is a loop written the long way. A `.filter(` on one
that only tests whether a component is there belongs in the type, as `With` or `Without`.

### BV-ECS-19 [M] Name a query type once it needs two lines

A query type that wraps onto a second line gets a `type` alias with a name from the domain.

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
/// write — the alias does not get to opt out of BV-ECS-14 and BV-ECS-15.
fn cull(mut commands: Commands, combatants: Combatants) {
    for (entity, health, transform) in &combatants {
        if health.0 <= 0.0 || transform.translation.y < -100.0 {
            commands.entity(entity).despawn();
        }
    }
}
```

### BV-ECS-20 [S] Reach for `iter_many` when the set of entities is already known

Given a `Children`, a relationship target, or a stored list of ids, `query.iter_many(ids).matched()`
fetches exactly those that match. Iterating the whole query and testing membership does not.

Every `iter_many` form yields `Result<Item, QueryEntityError>`, one per id, so a bare `.count()`,
`.next().is_some()` or `for _ in` compiles and counts ids that do not match. `.matched()` skips them
on `iter_many` and `iter_many_unique`, and on their `_mut` forms, read with `fetch_next`. A sorted
form has no `.matched()` and takes `.filter_map(Result::ok)`, and a `par_` form's closure receives
the `Result`.

**Why:** the cost of the loop should be the number of entities you care about, not the number that
exist. A membership test inside a full iteration is `O(all)` where the direct form is `O(wanted)`,
and it reads as a search where the code already knows the answer.

**Check:** look for `if ids.contains(&entity)` inside a query loop. That is `iter_many` written out.
Then, for each `iter_many`, check that its items go through `.matched()` or are handled as `Result`.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Lit;

#[derive(Resource, Debug, Default, PartialEq, Reflect)]
#[reflect(Resource)]
pub struct LitLamps(pub usize);

/// `iter_many` visits a post's children and nothing else; `.matched()` drops
/// the children `lit` does not match.
fn count_lit(posts: Query<&Children>, lit: Query<(), With<Lit>>, mut total: ResMut<LitLamps>) {
    let mut now = 0;
    for children in &posts {
        now += lit.iter_many(children).matched().count();
    }
    total.set_if_neq(LitLamps(now));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matched_counts_the_lit_children_and_a_bare_count_counts_them_all() {
        let mut app = App::new();
        app.init_resource::<LitLamps>()
            .add_systems(Update, count_lit);
        let post = app.world_mut().spawn_empty().id();
        app.world_mut().spawn((Lit, ChildOf(post)));
        app.world_mut().spawn(ChildOf(post));

        app.update();
        assert_eq!(app.world().resource::<LitLamps>().0, 1);

        // The same call without `.matched()` compiles, and counts both.
        let mut posts = app.world_mut().query::<&Children>();
        let mut lit = app.world_mut().query_filtered::<(), With<Lit>>();
        let world = app.world();
        let children = posts.get(world, post).expect("the post has two children");
        assert_eq!(lit.iter_many(world, children).count(), 2);
    }
}
```

### BV-ECS-21 [M] Never nest a query inside itself

A loop over a query cannot contain another loop over the same query. Use `iter_combinations` for
pairs, or split the data into two queries with disjoint filters.

**Why:** the borrow checker rejects the mutable case outright, and the read-only case is a quadratic
loop that looks linear. `iter_combinations` also visits each unordered pair once rather than twice,
which is usually what collision or attraction code actually wanted.

**Check:** read each `for` over a query for another `for` over a query inside it, and check the two
are different queries with filters that cannot both match one entity.

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

### BV-ECS-22 [M] Parallelise a query only against a measurement

`par_iter_mut` is concurrency, which RS-CONC-01 adds only where a profile shows the need: write the
serial loop first, and parallelise the query a profile names.

**Why:** the parallel form has per-batch overhead and forces the body to be `Send`, and below a few
thousand entities it is reliably slower. It also hides the usual real answer: a query fetching more
than it reads (BV-ECS-14), or work that belongs in `FixedUpdate` at a lower rate.

**Check:** is there a benchmark or a profile naming this system? If not, the serial form is the one
to ship.

### BV-ECS-23 [M] Reach for `contiguous_iter` only for a loop a profile names

`Query::contiguous_iter` yields one slice per table rather than one item per entity, which is what a
SIMD kernel or a cache-blocked pass needs. It replaces a structure-of-arrays kept by hand beside the
components, and it is an optimisation, which RS-PERF-01 makes only against a profile.

It is not a drop-in for `for x in &query`:

- The call returns `Result`, because a sparse-set component is not contiguously iterable and nothing
  in the type system knows which. Take the error with `?`, never `.unwrap()` (BV-ERR-01).
- The filter is bound by `F: ArchetypeFilter`, so `Changed<T>` does not compile here at all.
- The mutable form marks every entity in the slice changed unless the write goes through
  `bypass_change_detection` (BV-ECS-27).

**Why:** it is the only way to get contiguous slices without leaving the ECS, so a hand-kept
`Vec<f32>` can go, and with it the bug where it drifts from the entities. The price is a nested loop
and a run-time failure the day a component turns sparse, which only a hot loop repays.

**Check:** for each `contiguous_iter`, find the measurement. Without one, it is the cost above with
nothing to repay it.

```rust
// verified — GOOD
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Health(pub f32);

#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Decay(pub f32);

/// The outer loop is tables, the inner is entities within one table — that
/// nesting is the whole shape, and it is the price of the slices. The error
/// is the query's own `QueryNotDenseError`: `Health` or `Decay` stored
/// sparsely makes this fail at run time, having compiled, so `?` hands it to
/// the error handler as a `BevyError` rather than unwrapping (BV-ERR-02).
fn decay_health(mut lives: Query<(&mut Health, &Decay)>) -> Result {
    for (mut health, decay) in lives.contiguous_iter_mut()? {
        for (health, decay) in health.iter_mut().zip(decay) {
            health.0 *= decay.0;
        }
    }
    Ok(())
}

/// The schedule takes it as it stands: `Result<(), BevyError>` is a system
/// output `add_systems` accepts, where `Result<(), QueryNotDenseError>` is not.
#[derive(Debug, Default)]
pub struct DecayPlugin;

impl Plugin for DecayPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(FixedUpdate, decay_health);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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

    /// Through the plugin, so the test also pins that the plugin schedules
    /// the system; an error would reach the default handler and fail it.
    #[test]
    fn decay_multiplies_every_entity() {
        let mut app = App::new();
        app.add_plugins(DecayPlugin);
        app.world_mut().spawn((Health(100.0), Decay(0.5)));
        app.world_mut().spawn((Health(40.0), Decay(0.25)));
        app.world_mut().run_schedule(FixedUpdate);

        let mut query = app.world_mut().query::<&Health>();
        let mut got: Vec<f32> = query.iter(app.world()).map(|h| h.0).collect();
        got.sort_by(f32::total_cmp);
        assert_eq!(got, [10.0, 50.0]);
    }
}
```

## Change detection

### BV-ECS-24 [M] Write with `set_if_neq` wherever a `Changed` filter is watching

`health.set_if_neq(Health(new))` rather than `*health = Health(new)` when the new value is often the
old one and anything reads the component's changes: a `Changed<T>` filter, an `is_changed`, or a
`Ref<T>`.

**Why:** `DerefMut` on `Mut<T>` marks the component changed, so assigning the same value every frame
marks every entity changed every frame. Every downstream `Changed<T>` filter then matches
everything: it goes on compiling and matching, and no longer means anything.

**Check:** for each `*component = …` in a system that runs every frame, ask whether the value can be
unchanged. If so, and anything reads its changes, that is the defect — and a `Changed` filter added
later makes every such write one.

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

### BV-ECS-25 [M] Put `Changed<T>` in the filter so the system can be skipped

`Query<&Health, Changed<Health>>`, not a full query with `if health.is_changed()` inside the loop.
On a component that is written rarely, `#[component(summary_tick)]` (new in 0.20) keeps a per-column
change tick, so the filter can skip whole columns.

**Why:** as a filter it is applied during iteration, so unchanged entities are never fetched; in the
body it is applied after the fetch, so the loop still visits everything. The filter also puts
"reactive" in the system's signature, where the body form hides it behind an early `continue`.

**Check:** read each `is_changed()` inside a query loop. Unless the body needs both the changed and
the unchanged entities, it is a filter that has escaped into the body.

### BV-ECS-26 [M] Do not use `Changed<T>` to mean `Added<T>`

`Added<T>` matches the frame the component was inserted. `Changed<T>` matches insertion *and* every
subsequent write.

**Why:** `Changed` also matches the insertion frame, so setup code under it appears to work and then
runs again on every later write, spawning a second sound or a second child. The bug surfaces only
when someone starts mutating the component, which may be months later and in another module.

**Check:** for each `Changed<T>` filter, ask whether running twice for one entity is acceptable. If
not, it is `Added<T>` — or, better, an observer on `Add` (BV-EVENT-12).

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

        let mut health = app
            .world_mut()
            .get_mut::<Health>(hero)
            .expect("the hero was spawned with Health");
        health.0 -= 1.0;

        app.update();

        assert_eq!(app.world().resource::<Jingles>().on_added, 1);
        assert_eq!(app.world().resource::<Jingles>().on_changed, 2);
    }
}
```

### BV-ECS-27 [S] Bypass change detection only where the write is bookkeeping

`Mut::bypass_change_detection` is for writes that are not changes to the game's state — a cached
value refreshed from its source, a counter nothing reacts to.

**Why:** the bypass is the only way to write without marking, so using it for a real change leaves
everything downstream believing the old value. Used to quiet a noisy filter, it hides that
`set_if_neq` (BV-ECS-24) was the answer.

**Check:** each call needs a comment naming what does *not* need to know about this write. If the
comment cannot be written, the write is a change.

## Structural change

### BV-ECS-28 [M] Do not read back what a command has not applied yet

`Commands` queue work that runs at the next sync point. Within the same system, the entity spawned
two lines ago is not in any query. A test has no later system to wait for, so it applies the queue
itself, with `app.world_mut().flush()` or an `update`, before asserting on what a command did.

**Why:** the deferral is what lets systems run in parallel, and it is invisible: the code reads as
if it were immediate, and a `get` on the id just spawned returns `None` with no error to say why.

**Check:** in each system, is any id from `commands.spawn(…).id()` used to look something up in the
same body? Move the read to a later system: the schedule puts a sync point between the two. In each
test, a query for something a command spawned needs a flush or an `update` before it.

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

### BV-ECS-29 [M] Reach for an exclusive system last, and say what forced it

A system taking `&mut World` cannot run in parallel with anything. Write one only when the work
genuinely needs the whole world at once, and put the reason in a doc comment.

Since 0.20, `&mut World` is itself a `SystemParam` and may appear anywhere in the parameter list.
`ExclusiveSystemParam` is gone, and exclusivity is tracked at run time rather than compile time, so
a parameter that conflicts with `&mut World` is a run-time error, not a compile error.

**Why:** an exclusive system is a global barrier in the schedule: everything before it finishes, it
runs alone, everything after starts. One is usually fine and four is a game that no longer runs its
systems in parallel.

**Check:** for each `&mut World` parameter, name what the system could not do without it. "Needed a
resource and a query" and "needed a command applied now" both have a non-exclusive form; "runs a
scene through the type registry" does not.
