# Architecture: The Boundary, Plugins, Crate Shape

Scope: where Bevy is allowed to appear in a codebase and where it is not, how the simulation is
kept separable from the engine that drives it, and the shape of a plugin. Everything about *what*
goes in a component is in the ECS chapter; *when* a system runs is in the scheduling chapter; the
manifest that expresses a crate split is in the Cargo chapter.

This chapter is the reason the standard exists. Bevy's API turns over faster than any other
dependency a game has — three consecutive releases renamed the event system, the scene system and
the resource system — and an engine upgrade is survivable exactly to the extent that the rules of
the game do not mention the engine.

## Contents

- **The boundary**
  - BV-ARC-01 [M] Keep the rules of the game out of the engine's vocabulary
  - BV-ARC-02 [M] Scale the boundary's mechanism to the project; never the rule
  - BV-ARC-03 [M] Give the boundary exactly one crossing point per direction
  - BV-ARC-04 [M] Keep the invariant in the domain type, and parse at the crossing
  - BV-ARC-05 [S] Share `glam` across the boundary unless determinism forbids it
  - BV-ARC-06 [M] Do not reach for `bevy_ecs` to get the ECS in through the side door
  - BV-ARC-07 [M] Make the boundary a job, not a paragraph
  - BV-ARC-08 [S] Name a crate for what it models, not for the engine

- **Plugins**
  - BV-ARC-09 [M] Write every plugin as a type
  - BV-ARC-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`
  - BV-ARC-11 [M] A plugin registers its own things and only its own things
  - BV-ARC-12 [M] Let a duplicate plugin panic rather than opting out of the check
  - BV-ARC-13 [S] Reach for `PluginGroup` only when the group is the unit users add
  - BV-ARC-14 [M] Let the crate that defines a type own its registration
  - BV-ARC-15 [S] Give each plugin one module, and re-export it from the crate root

- **The app**
  - BV-ARC-16 [M] Keep `main` to plugins and nothing else
  - BV-ARC-17 [M] Return `AppExit` from `main`
  - BV-ARC-18 [M!] Configure `DefaultPlugins` where it is added, not by patching afterwards
  - BV-ARC-19 [S] Split the binary from the library so the game is testable without a window

---

## The boundary

### BV-ARC-01 [M] Keep the rules of the game out of the engine's vocabulary

Damage numbers, economy, pathfinding, turn order, save format — the code that decides *what
happens* takes and returns plain Rust data. `Query`, `Commands`, `Res`, `Entity`, `Component` and
every other Bevy name belong to the code that decides *when* it happens.

**Why:** an engine upgrade rewrites signatures, not arithmetic. Bevy 0.17 renamed `Trigger` to
`On`, split `Event` three ways and re-suffixed every system set; 0.19 made `Resource` a subtrait of
`Component` and renamed the whole scene crate. Each of those touched every file that named a Bevy
type and no file that did not. The same separation is what lets the rules be unit-tested in
microseconds without a `World`.

**Check:** for each function, ask what it would take to call it from a test with no `App`. If the
answer involves building a `World`, and the function computes a game outcome rather than moving
data between the ECS and something else, it is on the wrong side.

```rust
// verified — GOOD: the rule is a function of values, so a test needs no World
/// What a hit does. Nothing here knows an ECS exists.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Damage {
    pub amount: f32,
    pub pierces_shield: bool,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Absorbed {
    pub to_shield: f32,
    pub to_health: f32,
}

#[must_use]
pub fn absorb(damage: Damage, shield: f32) -> Absorbed {
    if damage.pierces_shield {
        return Absorbed {
            to_shield: 0.0,
            to_health: damage.amount,
        };
    }
    let to_shield = damage.amount.min(shield);
    Absorbed {
        to_shield,
        to_health: damage.amount - to_shield,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_shield_absorbs_up_to_its_strength() {
        let hit = Damage {
            amount: 30.0,
            pierces_shield: false,
        };
        assert_eq!(
            absorb(hit, 12.0),
            Absorbed {
                to_shield: 12.0,
                to_health: 18.0
            }
        );
    }

    #[test]
    fn piercing_damage_ignores_the_shield() {
        let hit = Damage {
            amount: 30.0,
            pierces_shield: true,
        };
        assert_eq!(
            absorb(hit, 12.0),
            Absorbed {
                to_shield: 0.0,
                to_health: 30.0
            }
        );
    }
}
```

```rust
// verified — BAD: the same arithmetic, now reachable only through a World
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Health(pub f32);

#[derive(Component, Debug)]
struct Shield(pub f32);

#[derive(Message, Debug, Clone, Copy)]
struct Hit {
    target: Entity,
    amount: f32,
    pierces_shield: bool,
}

fn absorb(mut hits: MessageReader<Hit>, mut targets: Query<(&mut Health, &mut Shield)>) {
    for hit in hits.read() {
        let Ok((mut health, mut shield)) = targets.get_mut(hit.target) else {
            continue;
        };
        if hit.pierces_shield {
            health.0 -= hit.amount;
            continue;
        }
        let to_shield = hit.amount.min(shield.0);
        shield.0 -= to_shield;
        health.0 -= hit.amount - to_shield;
    }
}
```

### BV-ARC-02 [M] Scale the boundary's mechanism to the project; never the rule

The separation is mandatory at every size. How it is enforced is not: a single-binary game draws it
between modules, a workspace draws it between crates, and only the crate form can be enforced by
the compiler.

**Why:** a rule that demands a seven-crate workspace from a game jam prototype gets ignored
wholesale, and a rule that is satisfied by good intentions gets eroded one `use bevy::prelude::*`
at a time. Making the requirement constant and the mechanism proportional is what keeps it alive
across both.

**Check:** name the mechanism in the repository's own words — a module list, a crate list, a lint.
If nobody can say which files are forbidden to name Bevy, the boundary does not exist yet.

| Project shape | Where the line goes | What holds it |
|---|---|---|
| One binary | `src/sim/` vs `src/game/` | a CI grep over `src/sim/` |
| One library plus a binary | the library is the domain | the binary's dependency list |
| Workspace | domain crates vs one view crate | the domain crates' manifests |

### BV-ARC-03 [M] Give the boundary exactly one crossing point per direction

Data enters the domain through one function that reads the ECS and builds domain values, and
leaves through one function that writes domain results back into components. Neither direction
gets a second implementation elsewhere.

**Why:** two translation sites drift, and the drift is silent — one converts a `Transform` to
metres and the other forgets, so the simulation is correct and the picture is wrong. One crossing
point also gives the conversion a name and therefore a place to be tested.

**Check:** grep the view layer for constructions of domain types. More than one site building the
same domain type from components means the translation has been copied.

```rust
// verified
use bevy::ecs::system::RunSystemOnce;
use bevy::math::Vec2;
use bevy::prelude::*;

/// The simulation works in metres and seconds and knows nothing else. In a
/// workspace this type lives in a crate whose manifest names `glam` and does
/// not name `bevy` (BV-ARC-05).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Body {
    pub metres: Vec2,
    pub metres_per_second: Vec2,
}

#[must_use]
pub fn fall(body: Body, seconds: f32) -> Body {
    let metres_per_second = body.metres_per_second - Vec2::Y * 9.81 * seconds;
    Body {
        metres: body.metres + metres_per_second * seconds,
        metres_per_second,
    }
}

/// The view works in pixels. The scale is named twice — once per direction —
/// and both times in this file.
const PIXELS_PER_METRE: f32 = 64.0;

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Velocity(pub Vec2);

/// ECS to domain: the only place a `Body` is built from components.
fn read_bodies(movers: Query<(Entity, &Transform, &Velocity)>) -> Vec<(Entity, Body)> {
    movers
        .iter()
        .map(|(entity, transform, velocity)| {
            let body = Body {
                metres: transform.translation.truncate() / PIXELS_PER_METRE,
                metres_per_second: velocity.0 / PIXELS_PER_METRE,
            };
            (entity, body)
        })
        .collect()
}

/// Domain to ECS: the only place a `Body` is spent.
fn write_bodies(
    In(bodies): In<Vec<(Entity, Body)>>,
    mut movers: Query<(&mut Transform, &mut Velocity)>,
) {
    for (entity, body) in bodies {
        let Ok((mut transform, mut velocity)) = movers.get_mut(entity) else {
            continue;
        };
        let pixels = body.metres * PIXELS_PER_METRE;
        transform.translation = pixels.extend(transform.translation.z);
        velocity.set_if_neq(Velocity(body.metres_per_second * PIXELS_PER_METRE));
    }
}

/// Engine-side glue: it decides *when*, and `fall` decides *what*.
fn integrate(In(bodies): In<Vec<(Entity, Body)>>) -> Vec<(Entity, Body)> {
    const STEP_SECONDS: f32 = 1.0 / 64.0;
    bodies
        .into_iter()
        .map(|(entity, body)| (entity, fall(body, STEP_SECONDS)))
        .collect()
}

#[derive(Debug, Default)]
pub struct FlightPlugin;

impl Plugin for FlightPlugin {
    fn build(&self, app: &mut App) {
        app.register_type::<Velocity>()
            .add_systems(FixedUpdate, read_bodies.pipe(integrate).pipe(write_bodies));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_rule_of_the_game_needs_no_world() {
        let start = Body {
            metres: Vec2::ZERO,
            metres_per_second: Vec2::ZERO,
        };
        let after = fall(start, 1.0);
        assert_eq!(after.metres_per_second, Vec2::new(0.0, -9.81));
        assert_eq!(after.metres, Vec2::new(0.0, -9.81));
    }

    #[test]
    fn the_two_crossings_agree_on_the_scale() {
        let mut world = World::new();
        let entity = world
            .spawn((
                Transform::from_xyz(128.0, 64.0, 5.0),
                Velocity(Vec2::new(0.0, 32.0)),
            ))
            .id();

        let crossed = world.run_system_once(read_bodies).unwrap_or_default();
        assert_eq!(
            crossed.first(),
            Some(&(
                entity,
                Body {
                    metres: Vec2::new(2.0, 1.0),
                    metres_per_second: Vec2::new(0.0, 0.5),
                }
            ))
        );

        // Move it by one metre and one metre per second, in the domain's
        // units, and send it back out.
        let moved: Vec<_> = crossed
            .iter()
            .map(|&(entity, body)| {
                let nudged = Body {
                    metres: body.metres + Vec2::X,
                    metres_per_second: body.metres_per_second + Vec2::Y,
                };
                (entity, nudged)
            })
            .collect();
        assert!(
            world
                .run_system_once_with(write_bodies, moved.clone())
                .is_ok()
        );

        // Out and back in is the identity, which a scale dropped on one
        // side only would not survive.
        assert_eq!(world.run_system_once(read_bodies).ok(), Some(moved));

        // And in pixels one metre is sixty-four, with the `z` the domain
        // never saw still where it was.
        let entity_ref = world.entity(entity);
        let translation = entity_ref.get::<Transform>().map(|t| t.translation);
        assert_eq!(translation, Some(Vec3::new(192.0, 64.0, 5.0)));
        assert_eq!(
            entity_ref.get::<Velocity>(),
            Some(&Velocity(Vec2::new(0.0, 96.0)))
        );
    }

    #[test]
    fn one_fixed_step_puts_the_domains_answer_on_the_entity() {
        let mut app = App::new();
        app.add_plugins(FlightPlugin);
        let entity = app
            .world_mut()
            .spawn((Transform::default(), Velocity(Vec2::ZERO)))
            .id();

        app.world_mut().run_schedule(FixedUpdate);

        let rest = Body {
            metres: Vec2::ZERO,
            metres_per_second: Vec2::ZERO,
        };
        let expected = fall(rest, 1.0 / 64.0);
        let world = app.world();
        let translation = world
            .entity(entity)
            .get::<Transform>()
            .map(|t| t.translation);
        assert_eq!(
            translation,
            Some((expected.metres * PIXELS_PER_METRE).extend(0.0))
        );
        assert_eq!(
            world.entity(entity).get::<Velocity>(),
            Some(&Velocity(expected.metres_per_second * PIXELS_PER_METRE))
        );
    }
}
```

### BV-ARC-04 [M] Keep the invariant in the domain type, and parse at the crossing

A component's fields are public — the ECS is the accessor, and reflection, scenes and the remote
protocol all read fields directly. Data that must satisfy a condition therefore cannot be defended
inside a component. Model the condition as a domain type with a private field and a fallible
constructor, let the component carry the plain value, and construct the domain type at the crossing
point (BV-ARC-03). Nothing else may read that field.

**Why:** this standard exempts components from the private-field rule, and the exemption has to buy
something. What it buys is a sharper line: because a component cannot defend an invariant, needing
to defend one is a signal that the *acting* on that value belongs on the domain side. The component
is then an unparsed input — the same shape as a config file or a network packet — and the crossing
point is where it is parsed. Wrapping the domain type in the component instead looks tighter and is
not available: a domain type with a private field cannot be reflected from the ECS side
(`#[reflect_remote]` needs field access), so the component would have to give up `Reflect` or the
domain would have to take a Bevy dependency, and BV-ECS-03 and BV-ARC-06 each forbid one of those.

**Check:** for each component field, ask what value would be wrong. If any answer is more specific
than "any value of this type", find every read of that field: exactly one, at the crossing point,
going through a constructor that can say no. A comparison against that field inside a system is the
defect.

```rust
// verified — GOOD: the invariant is the domain's; the component is an unparsed input
use bevy::ecs::system::RunSystemOnce;
use bevy::prelude::*;

/// The domain's type: private field, fallible constructor, no Bevy in sight.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Ratio(f32);

impl Ratio {
    #[must_use]
    pub fn new(value: f32) -> Option<Self> {
        (0.0..=1.0).contains(&value).then_some(Self(value))
    }

    #[must_use]
    pub fn get(self) -> f32 {
        self.0
    }
}

/// The ECS's type: public field, reflectable, and carrying a number nobody has
/// checked yet.
#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
pub struct Throttle(pub f32);

/// The one crossing point. This is the only place `Throttle.0` is read.
fn throttles(query: Query<(Entity, &Throttle)>) -> Vec<(Entity, Ratio)> {
    query
        .iter()
        .filter_map(|(entity, t)| Ratio::new(t.0).map(|r| (entity, r)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_ratio_outside_the_unit_interval_does_not_exist() {
        assert!(Ratio::new(1.5).is_none());
        assert_eq!(Ratio::new(0.25).map(Ratio::get), Some(0.25));
    }

    #[test]
    fn the_crossing_point_drops_what_the_domain_would_reject() {
        let mut world = World::new();
        world.spawn(Throttle(0.5));
        world.spawn(Throttle(1.5));
        let parsed = world.run_system_once(throttles).unwrap_or_default();
        assert_eq!(parsed.len(), 1);
    }
}
```

### BV-ARC-05 [S] Share `glam` across the boundary unless determinism forbids it

`Vec2`, `Vec3`, `Quat` and `Mat4` come from `glam`, which is an ordinary crate that Bevy happens to
re-export. Domain code may name them directly, and should, so a position does not have to be
rebuilt at every crossing.

**Why:** the boundary exists to keep the *engine* out, and `glam` is not the engine — it has no
`World`, no schedule and its own release cadence. Duplicating a vector type buys nothing and costs a
conversion on every field of every message. The exception is real, though: `glam`'s float paths are
not bit-identical across targets, so a game that ships replays or lockstep multiplayer needs its
own arithmetic and must say so where the dependency is declared.

**Check:** does the project have a stated determinism requirement — replays, rollback, lockstep,
golden vectors? If not, use `glam`. If so, the domain gets its own numeric types and the manifest
comment says which crates can reach produced bytes.

### BV-ARC-06 [M] Do not reach for `bevy_ecs` to get the ECS in through the side door

Depending on `bevy_ecs` rather than `bevy` does not put a crate on the domain side of the boundary.
The domain uses plain data structures.

**Why:** `bevy_ecs` is where nearly all of the churn lives — the `Event`/`Message` split, the
observer rewrite, `Resource: Component`, the `Access` API. A crate that derives `Component` is on
the engine's release schedule whether or not it names the facade, so the version pin, the migration
work and the loss of ECS-free testing all arrive anyway.

**Check:** search every domain manifest for `bevy`. Any match, facade or subcrate, is a boundary
violation.

### BV-ARC-07 [M] Make the boundary a job, not a paragraph

The rule that some directory may not mention Bevy is executable in one line. Write it as a CI step.

**Why:** an architectural boundary written only in a README is re-crossed by the first contributor
who has not read it, and by every agent that has not been shown it. The failure is silent for as
long as it takes someone to notice, by which point the crossing has callers.

**Check:** does CI fail on a `use bevy::` added to a domain file? If nobody has tried, the job is
unverified — add the import locally and watch it fail before trusting it. `assets/ci.yml` carries
the job, alongside the Linux packages a Bevy build needs.

```bash
# fragment — the whole enforcement, as a CI step
if grep -rn --include='*.rs' -e 'bevy' crates/*-sim/src/; then
  echo 'a simulation crate named Bevy; see BV-ARC-01' >&2
  exit 1
fi
```

### BV-ARC-08 [S] Name a crate for what it models, not for the engine

`combat`, `economy`, `navigation` — not `bevy_combat`, `game_ecs`, `sim_components`.

**Why:** a name that mentions the engine claims a dependency the crate is required not to have, and
a name that mentions the ECS describes the mechanism rather than the subject. Both mislead a reader
deciding where a change belongs, which is the one job a crate name has. Bevy's own `bevy_*` packages
are upstream's namespace, not a pattern to copy — and note they are also spelled with underscores,
where a package published from this standard uses hyphens.

**Check:** read the crate list aloud. If a name would still be accurate after the game switched
engines, it is naming the subject.

## Plugins

### BV-ARC-09 [M] Write every plugin as a type

A plugin is a type that implements `Plugin`: `#[derive(Debug, Default)]`, a unit struct when it has
no settings and named fields when it has. The blanket impl for `Fn(&mut App)` exists; do not reach
for it, and never pass a closure.

**Why:** four of Bevy's own APIs address a plugin **by its type** — `App::is_plugin_added::<T>()`,
`App::get_added_plugins::<T>()`, `PluginGroupBuilder::add_before::<T>()` and
`PluginGroupBuilder::disable::<T>()`. A function's type is a fn-item type, which cannot be written
in Rust source at all, so a plugin written as a function is unreachable from every one of them:
nothing can ask whether it was added, read back its configuration, order a group around it, or
switch it off. The type is what the engine addresses; the function impl is a convenience over it.

It is also the form that survives growth. A unit-struct plugin that later needs a setting gains a
field, and its call sites gain `::default()` or a literal; a function that needs one has to become a
type first, which is that edit plus a rewrite of everything that named it.

**Check:** `grep -rn -E 'add_plugins\(\(?[a-z_|]' src/`. After `add_plugins(` a type starts with a
capital, so a lowercase name is a function, a module-qualified function, or a closure — all three of
the forms that cannot be named. The *declaration* has no grep of its own, and deliberately:
`fn f(app: &mut App)` is what a plugin function looks like and also what a test helper that drives
an `App` looks like, so those are read rather than matched.

```rust
// verified — GOOD: no settings, so the type is a unit struct
use bevy::prelude::*;

#[derive(Component, Debug, Reflect)]
#[reflect(Component)]
struct Health(pub f32);

fn decay(mut healths: Query<&mut Health>) {
    for mut health in &mut healths {
        health.0 -= 1.0;
    }
}

/// `Default` so a plugin with settings and one without are constructed alike.
#[derive(Debug, Default)]
pub struct DecayPlugin;

impl Plugin for DecayPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(FixedUpdate, decay);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_plugin_registers_its_system_and_can_be_asked_about() {
        let mut app = App::new();
        app.add_plugins(DecayPlugin);
        assert!(app.is_plugin_added::<DecayPlugin>());

        let entity = app.world_mut().spawn(Health(3.0)).id();
        app.world_mut().run_schedule(FixedUpdate);
        assert_eq!(
            app.world().entity(entity).get::<Health>().map(|h| h.0),
            Some(2.0)
        );
    }
}
```

### BV-ARC-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`

`CombatPlugin`, `MovementSystems`. This standard's general rule is that a name does not end in the
language construct it is; these two types are the exception, and the exception is exactly these two
traits.

**Why:** both suffixes are load-bearing at the call site rather than decorative. `add_plugins` and
`configure_sets` take anything convertible, so the name is the only thing telling a reader which
kind of thing is being added — and `add_systems(Update, X)` versus `configure_sets(Update, X)` are
the same shape with different meanings. The convention is also enforced by `bevy_lint`, so
deviating means a warning in every project that runs it.

**Check:** for each type implementing `Plugin` or `SystemSet`, does the name end in `Plugin` or
`Systems`? Any other type that ends in either word and does not implement the matching trait is a
worse defect than a missing suffix, because it lies.

```rust
// verified
use bevy::prelude::*;

/// Settings, so the type has fields. `Default` means a caller who wants none
/// writes `CombatPlugin::default()` — the same shape as a unit-struct plugin.
#[derive(Debug, Default, Clone, Copy)]
pub struct CombatPlugin {
    pub friendly_fire: bool,
}

#[derive(SystemSet, Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CombatSystems {
    Resolve,
    Report,
}

fn resolve() {}
fn report() {}

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.configure_sets(
            FixedUpdate,
            (CombatSystems::Resolve, CombatSystems::Report).chain(),
        )
        .add_systems(FixedUpdate, resolve.in_set(CombatSystems::Resolve))
        .add_systems(FixedUpdate, report.in_set(CombatSystems::Report));
    }
}
```

### BV-ARC-11 [M] A plugin registers its own things and only its own things

Inside `build`, a plugin adds its own systems, resources, messages, observers and type
registrations. It does not add another module's.

**Why:** registration is where a reader looks to find out what a feature consists of, so a plugin
that registers a neighbour's systems makes that neighbour's plugin an incomplete answer. It also
makes the two impossible to add independently, which is the one thing plugins are for.

**Check:** read each `build` and list the types it names. Every one should be defined in that
plugin's module or below it.

```rust
// verified
use bevy::prelude::*;

#[derive(Message, Debug, Clone, Copy)]
pub struct DamageDealt {
    pub target: Entity,
    pub amount: u32,
}

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Health(pub u32);

fn apply_damage(mut dealt: MessageReader<DamageDealt>, mut healths: Query<&mut Health>) {
    for hit in dealt.read() {
        if let Ok(mut health) = healths.get_mut(hit.target) {
            let remaining = Health(health.0.saturating_sub(hit.amount));
            health.set_if_neq(remaining);
        }
    }
}

/// Registers the message it defines, the component it defines, and the system
/// that reads them. Nothing that belongs to anyone else.
#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.register_type::<Health>()
            .add_message::<DamageDealt>()
            .add_systems(FixedUpdate, apply_damage);
    }
}

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct Score(pub u32);

fn award_points(mut dealt: MessageReader<DamageDealt>, mut score: ResMut<Score>) {
    for hit in dealt.read() {
        score.0 += hit.amount;
    }
}

/// Reads combat's message and registers none of combat's things — no
/// `add_message::<DamageDealt>()` here, because that line is combat's answer
/// to "what is this feature made of". What score *is* responsible for is
/// saying that it cannot run without combat.
#[derive(Debug, Default)]
pub struct ScorePlugin;

impl Plugin for ScorePlugin {
    fn build(&self, app: &mut App) {
        if !app.is_plugin_added::<CombatPlugin>() {
            app.add_plugins(CombatPlugin);
        }
        app.register_type::<Score>()
            .init_resource::<Score>()
            .add_systems(FixedUpdate, award_points);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn score_depends_on_combat_instead_of_re_registering_it() {
        let mut app = App::new();
        app.add_plugins(ScorePlugin);
        assert!(app.is_plugin_added::<CombatPlugin>());

        let entity = app.world_mut().spawn(Health(10)).id();
        let written = app.world_mut().write_message(DamageDealt {
            target: entity,
            amount: 3,
        });
        assert!(written.is_some());
        app.world_mut().run_schedule(FixedUpdate);

        assert_eq!(app.world().entity(entity).get::<Health>(), Some(&Health(7)));
        assert_eq!(app.world().resource::<Score>().0, 3);
    }

    #[test]
    fn adding_both_plugins_is_not_a_duplicate() {
        let mut app = App::new();
        app.add_plugins((CombatPlugin, ScorePlugin));
        assert!(app.is_plugin_added::<ScorePlugin>());
    }
}
```

### BV-ARC-12 [M] Let a duplicate plugin panic rather than opting out of the check

Adding a plugin that is already in the `App` panics at `add_plugins`. Fix the double add; do not
override `is_unique` to make it stop.

**Why:** the refusal is the good outcome — the alternative is a game that applies gravity twice per
step with nothing saying so. Overriding `is_unique` buys exactly that, so it is only correct for a
plugin whose `build` is genuinely idempotent, and then the `build` is what has to be shown to be.

The check is by plugin **name**, which defaults to the type's `type_name`. A type gives that
message something to say. The forms BV-ARC-09 forbids do not: two inline `|app: &mut App| { … }`
plugins written in one function both render as `{{closure}}`, so the second is refused with a
message naming neither of them.

**Check:** grep for `fn is_unique`. Each override needs the reason the plugin is meaningfully
instantiable twice, plus a test that adds it twice and asserts the world is what it should be.

```rust
// verified
use bevy::prelude::*;

#[derive(Resource, Debug, Default)]
struct WaveCount(u32);

#[derive(Debug, Default)]
pub struct WavePlugin;

impl Plugin for WavePlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<WaveCount>();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adding_the_plugin_twice_is_refused_rather_than_doubled() {
        let mut app = App::new();
        app.add_plugins(WavePlugin);
        assert!(app.world().get_resource::<WaveCount>().is_some());

        // `App` is not `UnwindSafe`, and the panic is the assertion.
        let again = std::panic::AssertUnwindSafe(move || {
            app.add_plugins(WavePlugin);
        });
        assert!(std::panic::catch_unwind(again).is_err());
    }
}
```

### BV-ARC-13 [S] Reach for `PluginGroup` only when the group is the unit users add

A `PluginGroup` earns its place when callers want to add several plugins at once *and* disable
individual members. Otherwise a function that calls `add_plugins` with a tuple is the same thing
without the machinery.

**Why:** `PluginGroup` exists to give `DefaultPlugins` its `build().disable::<T>()` surface. A group
nobody disables members of pays for a builder, a `PluginGroupBuilder` and a second concept, and
returns a tuple's behaviour.

**Check:** has anyone called `.disable::<_>()` on this group, or asked to? If not, a tuple is the
same feature.

### BV-ARC-14 [M] Let the crate that defines a type own its registration

`register_type`, `init_resource`, `add_message` and `add_observer` for a type go in the plugin of
the module that defines it.

**Why:** the alternative is a central `register_everything` that grows a line per type and has to be
edited by everyone. Worse, it silently decouples defining from registering: a type gets added, the
central list does not, and reflection or message cleanup is missing in a way that shows up as a
runtime absence rather than a compile error.

**Check:** for each `#[derive(Message)]`, `#[derive(Resource)]` and `#[reflect(Component)]`, find
the registration. If it is in a different module from the definition, move it.

### BV-ARC-15 [S] Give each plugin one module, and re-export it from the crate root

`combat.rs` defines `CombatPlugin` and the components, systems and sets it registers. The crate
root re-exports the type, so a call site writes `CombatPlugin` rather than `combat::CombatPlugin`.

**Why:** it makes the module tree and the plugin tree the same tree, so `add_plugins` reads as a
table of contents for the source. A module with two plugins is two features that have not been
separated; a plugin spanning two modules has no single place a reader can start.

**Check:** does every `impl Plugin` sit at the root of its own module, does every feature module
have exactly one, and is each plugin type named in the crate root's re-exports?

## The app

### BV-ARC-16 [M] Keep `main` to plugins and nothing else

`main` builds the `App`, adds plugins, and runs it. Systems, resources and configuration belong to
the plugin that owns them.

**Why:** `main` is the one file every reader opens first, and a `main` that adds forty systems tells
them nothing about how the game is organised. It is also the one place that cannot be reused: a
headless test, a benchmark and a second binary all want the plugins without the window.

**Check:** count the statements in `main` that are not `add_plugins`, `App::new` or `run`. Each one
is a registration that has escaped its plugin.

```rust
// fragment — GOOD: the shape of a main
use mygame::{CombatPlugin, EconomyPlugin, HudPlugin};

fn main() -> AppExit {
    App::new()
        .add_plugins(DefaultPlugins)
        .add_plugins((CombatPlugin, EconomyPlugin, HudPlugin))
        .run()
}
```

### BV-ARC-17 [M] Return `AppExit` from `main`

`App::run` returns `AppExit`. Return it.

**Why:** `AppExit::Error` sets the process exit code, which is what a launcher, a test harness, a
CI job and a crash reporter read to find out whether the game ended or died. Discarding it makes
every failure look like a clean shutdown to everything outside the process.

**Check:** does `fn main` return `AppExit`, and is the value the one `run` returned? `bevy_lint`'s
`main_return_without_appexit` finds every case.

### BV-ARC-18 [M!] Configure `DefaultPlugins` where it is added, not by patching afterwards

Window title, asset path, log filter and render settings are set with `.set(…)` on the plugin group
at the point it is added.

*Relaxed form:* a value that is genuinely only known at runtime — a window size read from a settings
file — is inserted afterwards, and the code that does so sits next to the `add_plugins` call.

**Why:** `.set()` replaces the plugin's configuration before it builds, whereas mutating the
resource afterwards runs the original configuration first. For a window that means it is created at
the default size and then resized, which users see; for the asset plugin it means a watcher is
already running against the wrong directory.

**Check:** search for writes to `WindowPlugin`, `AssetPlugin` or `LogPlugin` state outside the
`add_plugins` call. Each one either belongs in `.set()` or needs the reason it cannot be.

### BV-ARC-19 [S] Split the binary from the library so the game is testable without a window

`src/lib.rs` holds the plugins and re-exports their types; `src/main.rs` is
`App::new().add_plugins(mygame::GamePlugin).run()`.

**Why:** integration tests, benchmarks and any second binary can depend on a library and cannot
depend on a binary. Without the split, every test that needs more than one plugin has to be a unit
test inside the binary crate, and `cargo test --lib` stops being the fast loop.

**Check:** is there anything in `main.rs` besides `main`? Is there a `tests/` directory? If the
answer to the first is yes and the second is no, the split has not happened.
