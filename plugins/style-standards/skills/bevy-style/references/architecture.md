# Architecture: The Boundary, Plugins, Crate Shape

Scope: where Bevy is allowed to appear in a codebase and where it is not, how the simulation is kept
separable from the engine that drives it, and the shape of a plugin. Everything about *what* goes in
a component is in the ECS chapter; *when* a system runs is in the scheduling chapter; the manifest
that expresses a crate split is in the build chapter.

This chapter is the reason the standard exists. Bevy's API turns over faster than any other
dependency a game has — three consecutive releases renamed the event system, the scene system and
the resource system — and an engine upgrade is survivable exactly to the extent that the rules of
the game do not mention the engine.

## Contents

- **The boundary**
  - BV-ARCH-01 [M] Keep the rules of the game out of the engine's vocabulary
  - BV-ARCH-02 [M] Scale the boundary's mechanism to the project; never the rule
  - BV-ARCH-03 [M] Give the boundary exactly one crossing point per direction
  - BV-ARCH-04 [M] Keep the invariant in the domain type, and parse at the crossing
  - BV-ARCH-05 [S] Share `glam` across the boundary unless determinism forbids it
  - BV-ARCH-06 [M] Do not reach for `bevy_ecs` to get the ECS in through the side door
  - BV-ARCH-07 [M] Make the boundary a job, not a paragraph
  - BV-ARCH-08 [S] Name a crate for what it models, not for the engine

- **Plugins**
  - BV-ARCH-09 [M] Write every plugin as a type
  - BV-ARCH-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`
  - BV-ARCH-11 [M] A plugin registers its own things and only its own things
  - BV-ARCH-12 [M] Let a duplicate plugin panic rather than opting out of the check
  - BV-ARCH-13 [S] Reach for `PluginGroup` only when the group is the unit users add
  - BV-ARCH-14 [S] Give each plugin one module, and re-export it from the crate root

- **The app**
  - BV-ARCH-15 [M] Keep `main` to plugins and the two error policies
  - BV-ARCH-16 [M] Return `AppExit` from `main`
  - BV-ARCH-17 [M] Configure `DefaultPlugins` where it is added, not by patching afterwards

---

## The boundary

### BV-ARCH-01 [M] Keep the rules of the game out of the engine's vocabulary

Damage numbers, economy, pathfinding, turn order, save format — the code that decides *what happens*
takes and returns plain Rust data. `Query`, `Commands`, `Res`, `Entity`, `Component` and every other
Bevy name belong to the code that decides *when* it happens.

**Why:** an engine upgrade rewrites signatures, not arithmetic: 0.20's `On<Add<T>>` and
`PointerClick` touched every file that named the old spellings and no file that did not. The same
separation is what lets the rules be unit-tested in microseconds without a `World`.

**Check:** for each function, ask what it would take to call it from a test with no `App`. If the
answer involves building a `World`, and the function computes a game outcome rather than moving data
between the ECS and something else, it is on the wrong side. Then count the tests that build an
`App`: if most of them do, the logic is in the systems.

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

### BV-ARCH-02 [M] Scale the boundary's mechanism to the project; never the rule

The separation is mandatory at every size. How it is enforced is not: a single-binary game draws it
between modules, a workspace draws it between crates, and only the crate form can be enforced by the
compiler.

**Why:** a rule demanding a seven-crate workspace of a game jam prototype is ignored wholesale, and
one satisfied by good intentions erodes one `use bevy::prelude::*` at a time. A constant requirement
with a proportional mechanism survives both.

**Check:** name the mechanism in the repository's own words — a module list, a crate list, a lint.
If nobody can say which files are forbidden to name Bevy, the boundary does not exist yet.

| Project shape | Where the line goes | What holds it |
|---|---|---|
| One binary | `src/sim/` vs `src/game/` | a CI grep over `src/sim/` |
| One library plus a binary | the library is the domain | the binary's dependency list |
| Workspace | domain crates vs one view crate | the domain crates' manifests |

### BV-ARCH-03 [M] Give the boundary exactly one crossing point per direction

Data enters the domain through one function that reads the ECS and builds domain values, and leaves
through one function that writes domain results back into components. Neither direction gets a
second implementation elsewhere.

**Why:** two translation sites drift, and the drift is silent — one converts a `Transform` to metres
and the other forgets, so the simulation is correct and the picture is wrong. One crossing point
also gives the conversion a name and therefore a place to be tested.

**Check:** grep the view layer for constructions of domain types. More than one site building the
same domain type from components means the translation has been copied.

```rust
// verified
use bevy::ecs::system::RunSystemOnce;
use bevy::math::Vec2;
use bevy::prelude::*;

/// The simulation works in metres and seconds and knows nothing else. In a
/// workspace this type lives in a crate whose manifest names `glam` and does
/// not name `bevy` (BV-ARCH-05).
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
        app.add_systems(FixedUpdate, read_bodies.pipe(integrate).pipe(write_bodies));
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

### BV-ARCH-04 [M] Keep the invariant in the domain type, and parse at the crossing

A component's fields are public — the ECS is the accessor, and reflection, scenes and the remote
protocol all read fields directly. Data that must satisfy a condition therefore cannot be defended
inside a component. Model the condition as a domain type with a private field and a fallible
constructor, let the component carry the plain value, and construct the domain type at the crossing
point (BV-ARCH-03). Nothing else may read that field. Do not wrap the domain type in the component
instead: a private field cannot be reflected from the ECS side (`#[reflect_remote]` needs field
access), so it would cost the component `Reflect` (BV-ECS-03) or the domain a Bevy dependency
(BV-ARCH-06).

**Why:** a component cannot defend an invariant, so needing to defend one signals that *acting* on
the value belongs on the domain side. The component is then an unparsed input, the same shape as a
config file or a network packet, and the crossing point is where it is parsed.

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

### BV-ARCH-05 [S] Share `glam` across the boundary unless determinism forbids it

`Vec2`, `Vec3`, `Quat` and `Mat4` come from `glam`, which is an ordinary crate that Bevy happens to
re-export. Domain code may name them directly, and should, so a position does not have to be rebuilt
at every crossing. Name the `glam` Bevy uses — 0.33 under Bevy 0.20 — and move it with every engine
bump: a `Vec2` from another `glam` is a different type at the crossing point, with the error
BV-BUILD-05 describes. A game that ships replays or lockstep multiplayer takes its own numeric types
instead, and says so where the dependency is declared.

**Why:** the boundary keeps the *engine* out, and `glam` has no `World`, no schedule and its own
release cadence; a duplicate vector type costs a conversion on every field of every message. The
exception is determinism: `glam`'s float paths are not bit-identical across targets.

**Check:** does the project have a stated determinism requirement — replays, rollback, lockstep,
golden vectors? If not, use `glam`. If so, the domain gets its own numeric types and the manifest
comment says which crates can reach produced bytes.

### BV-ARCH-06 [M] Do not reach for `bevy_ecs` to get the ECS in through the side door

Depending on `bevy_ecs` rather than `bevy` does not put a crate on the domain side of the boundary,
and neither does any other subcrate: 0.20 moved `bevy_math`'s primitives into `bevy_shape` and its
curves into `bevy_curve`, while their `bevy::prelude` path stayed put. The domain uses plain data
structures.

**Why:** `bevy_ecs` is where nearly all of the churn lives — the `Event`/`Message` split, the
observer rewrite, `Resource: Component`. A crate that derives `Component` is on the engine's release
schedule whatever it names, so the pin, the migration and the loss of ECS-free tests arrive anyway.

**Check:** search every domain manifest for `bevy`. Any match, facade or subcrate, is a boundary
violation.

### BV-ARCH-07 [M] Make the boundary a job, not a paragraph

The rule that some directory may not mention Bevy is executable in one line. Write it as a step of
the CI RS-BUILD-27 requires of every crate.

**Why:** an architectural boundary written only in a README is re-crossed by the first contributor
who has not read it, and by every agent that has not been shown it. The failure is silent for as
long as it takes someone to notice, by which point the crossing has callers.

**Check:** does CI fail on a `use bevy::` added to a domain file? If nobody has tried, the job is
unverified — add the import locally and watch it fail before trusting it. `assets/ci.yml` carries
the job, alongside the Linux packages a Bevy build needs.

```bash
# fragment — the whole enforcement, as a CI step
if grep -rn --include='*.rs' -e 'bevy' crates/*-sim/src/; then
  echo 'a simulation crate named Bevy; see BV-ARCH-01' >&2
  exit 1
fi
```

### BV-ARCH-08 [S] Name a crate for what it models, not for the engine

`combat`, `economy`, `navigation` — not `bevy_combat`, `game_ecs`, `sim_components`. Bevy's own
`bevy_*` packages are upstream's namespace, not a pattern to copy, and are spelled with underscores
where a package published from this standard uses hyphens.

**Why:** a name that mentions the engine claims a dependency the crate must not have, and one that
mentions the ECS names the mechanism rather than the subject. Both mislead a reader deciding where a
change belongs, which is the one job a crate name has.

**Check:** read the crate list aloud. If a name would still be accurate after the game switched
engines, it is naming the subject.

## Plugins

### BV-ARCH-09 [M] Write every plugin as a type

A plugin is a type that implements `Plugin`: `#[derive(Debug, Default)]`, a unit struct when it has
no settings and named fields when it has. The blanket impl for `Fn(&mut App)` exists; do not reach
for it, and never pass a closure. Bevy addresses a plugin **by its type**:
`App::is_plugin_added::<T>()`, `App::get_added_plugins::<T>()`,
`PluginGroupBuilder::add_before::<T>()` and `PluginGroupBuilder::disable::<T>()`.

**Why:** a function's type is a fn-item type, which Rust source cannot name, so nothing can ask
whether a function plugin was added, read its configuration, order a group around it or switch it
off. A unit struct that later needs a setting gains a field; a function first has to become a type.

**Check:** `rg -n 'add_plugins\(\(?[a-z_|]' src/`. After `add_plugins(` a type starts with a
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

### BV-ARCH-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`

Departs from RS-NAME-29. A type implementing `Plugin` ends in `Plugin`, and one implementing
`SystemSet` ends in `Systems` — `CombatPlugin`, `MovementSystems` — and no other type ends in either
word.

**Why:** `add_plugins` and `configure_sets` take anything convertible, so at the call site the name
is the only thing telling a reader what kind of thing is added — and `add_systems(Update, X)` and
`configure_sets(Update, X)` are the same shape with different meanings.

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

### BV-ARCH-11 [M] A plugin registers its own things and only its own things

Inside `build`, a plugin adds its own systems, resources, messages and observers, and nothing
another module defines. A type's `init_resource`, `add_message` and `add_observer` go in the plugin
of the module that defines it, never in a central `register_everything` that every feature edits. A
reflected type registers itself through its derive; a generic instantiation, the one exception, is
registered beside its definition too (BV-ECS-12).

**Why:** registration is where a reader learns what a feature is made of, and a plugin that
registers a neighbour's things cannot be added without it. A central list lets a type be added and
not registered: the resource then fails at first access, naming the type but not the plugin.

**Check:** read each `build` and list the types it names; every one should be defined in that
plugin's module or below it. Then, for each `#[derive(Message)]` and `#[derive(Resource)]`, find its
registration: it belongs in the module of the definition.

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

/// Registers the message it defines and the system that reads it; the component
/// registers itself through its derive. Nothing that belongs to anyone else.
#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<DamageDealt>()
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
        app.init_resource::<Score>()
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

### BV-ARCH-12 [M] Let a duplicate plugin panic rather than opting out of the check

Adding a plugin that is already in the `App` panics at `add_plugins`. Fix the double add; do not
override `is_unique` to make it stop, unless the plugin's `build` is genuinely idempotent and is
shown to be. The check is by plugin **name**, the type's `type_name` by default, so two inline
`|app: &mut App| { … }` plugins in one function are both `{{closure}}`, and the refusal names
neither.

**Why:** the refusal is the good outcome — the alternative is a game that applies gravity twice per
step with nothing saying so, which is exactly what overriding `is_unique` buys.

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

### BV-ARCH-13 [S] Reach for `PluginGroup` only when the group is the unit users add

A `PluginGroup` earns its place when callers want to add several plugins at once *and* disable
individual members. Otherwise a function that calls `add_plugins` with a tuple is the same thing
without the machinery.

**Why:** `PluginGroup` exists to give `DefaultPlugins` its `build().disable::<T>()` surface. A group
nobody disables members of pays for a builder, a `PluginGroupBuilder` and a second concept, and
returns a tuple's behaviour.

**Check:** has anyone called `.disable::<_>()` on this group, or asked to? If not, a tuple is the
same feature.

### BV-ARCH-14 [S] Give each plugin one module, and re-export it from the crate root

`combat.rs` defines `CombatPlugin` and the components, systems and sets it registers. The crate root
re-exports the type, so a call site writes `CombatPlugin` rather than `combat::CombatPlugin`.

**Why:** it makes the module tree and the plugin tree the same tree, so `add_plugins` reads as a
table of contents for the source. A module with two plugins is two features that have not been
separated; a plugin spanning two modules has no single place a reader can start.

**Check:** does every `impl Plugin` sit at the root of its own module, does every feature module
have exactly one, and is each plugin type named in the crate root's re-exports?

## The app

### BV-ARCH-15 [M] Keep `main` to plugins and the two error policies

`main` builds the `App`, adds plugins, and runs it, from a `src/main.rs` whose plugins live in the
library beside it. Systems, resources and configuration belong to the plugin that owns them. The
exception is the two error policies, which are the application's to choose and no plugin's:
`set_error_handler` (BV-ERR-05), and the `RenderErrorHandler` that must be in place before
`DefaultPlugins` (BV-ERR-10).

**Why:** `main` is the one file every reader opens first, and a `main` that adds forty systems tells
them nothing about how the game is organised. A headless test, a benchmark and a second binary all
want the plugins without the window, and they can depend on a library but never on a binary.

**Check:** count the statements in `main` that are not `add_plugins`, `App::new`, `run`, or one of
the two error policies above; each is a registration that has escaped its plugin. Then check that
`src/lib.rs` holds the plugins and `main.rs` holds nothing but `main`.

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

### BV-ARCH-16 [M] Return `AppExit` from `main`

`App::run` returns `AppExit`. Return it.

**Why:** `AppExit::Error` sets the process exit code, which is what a launcher, a test harness, a CI
job and a crash reporter read to find out whether the game ended or died. Discarding it makes every
failure look like a clean shutdown to everything outside the process.

**Check:** does `fn main` return `AppExit`, and is the value the one `run` returned? A `main` that
returns a fabricated `AppExit` has the right signature and still discards the real one.

### BV-ARCH-17 [M] Configure `DefaultPlugins` where it is added, not by patching afterwards

Window title, asset path, log filter and render settings known when the plugin group is added are
set with `.set(…)` on it, at that point. A value known only at run time — a window size read from a
settings file — is written afterwards, by code beside the `add_plugins` call.

**Why:** `.set()` replaces the configuration before the plugin builds; mutating the resource
afterwards runs the original first. The window is created at the default size and visibly resized,
and the asset watcher is already running against the wrong directory.

**Check:** search for writes to `WindowPlugin`, `AssetPlugin` or `LogPlugin` state outside the
`add_plugins` call. Each one either belongs in `.set()` or needs the reason it cannot be.
