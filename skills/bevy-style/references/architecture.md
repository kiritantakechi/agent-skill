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
  - BV-ARC-04 [M] Put invariants behind a constructor, and let the component carry the result
  - BV-ARC-05 [S] Share `glam` across the boundary unless determinism forbids it
  - BV-ARC-06 [M] Do not reach for `bevy_ecs` to get the ECS in through the side door
  - BV-ARC-07 [M] Make the boundary a job, not a paragraph
  - BV-ARC-08 [S] Name a crate for what it models, not for the engine

- **Plugins**
  - BV-ARC-09 [M] Write a plugin as a function until it needs configuration
  - BV-ARC-10 [M] Suffix a `Plugin` type `Plugin` and a `SystemSet` type `Systems`
  - BV-ARC-11 [M] A plugin registers its own things and only its own things
  - BV-ARC-12 [M] Let a duplicate plugin panic rather than opting out of the check
  - BV-ARC-13 [S] Reach for `PluginGroup` only when the group is the unit users add
  - BV-ARC-14 [M] Let the crate that defines a type own its registration
  - BV-ARC-15 [S] Give each plugin one module and each module one plugin

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
struct Health(f32);

#[derive(Component, Debug)]
struct Shield(f32);

fn absorb(mut hits: Query<(&mut Health, &mut Shield)>, amount: f32, pierces: bool) {
    for (mut health, mut shield) in &mut hits {
        if pierces {
            health.0 -= amount;
            continue;
        }
        let to_shield = amount.min(shield.0);
        shield.0 -= to_shield;
        health.0 -= amount - to_shield;
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

### BV-ARC-04 [M] Put invariants behind a constructor, and let the component carry the result

A component's fields are public — the ECS is the accessor, and reflection, scenes and the remote
protocol all read fields directly. Data that must satisfy a condition therefore cannot live in a
component as bare fields: model it as a domain type whose fields are private and whose constructor
is the only way in, and give the component that type.

**Why:** this standard exempts components from the private-field rule, and the exemption has to buy
something. What it buys is a sharper line: because a component cannot defend an invariant, needing
to defend one is now a signal that the type belongs on the domain side. Without the second half,
the exemption would just be permission to scatter unchecked state through the world.

**Check:** for each component field, ask what value would be wrong. If any answer is more specific
than "any value of this type", the invariant is currently unenforced and the type belongs behind a
constructor.

```rust
// verified — GOOD: the component is a wrapper; the constructor is the only way in
use bevy::prelude::*;

/// A fraction in `0.0..=1.0`. The field is private, so it cannot be violated.
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

#[derive(Component, Debug, Clone, Copy)]
pub struct Throttle(pub Ratio);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_ratio_outside_the_unit_interval_does_not_exist() {
        assert!(Ratio::new(1.5).is_none());
        assert_eq!(Ratio::new(0.25).map(Ratio::get), Some(0.25));
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

### BV-ARC-09 [M] Write a plugin as a function until it needs configuration

`Plugin` is implemented for `Fn(&mut App)`, so a plugin with no settings is a **named** function.
Reach for a type when the plugin carries fields the caller sets, and never for an inline closure.

**Why:** a unit struct plus an `impl` block is six lines that carry no information the function did
not. The type also forces the naming question this standard has to answer at all only because types
exist: a function is called `plugin`, needs no suffix, and reads as `add_plugins(combat::plugin)` at
the call site.

**Check:** does the plugin type have fields? If not, it is a function that has been written as a
type. An inline closure is the other failure: BV-ARC-12's duplicate check keys on the plugin's type
name, and every closure renders as `{{closure}}`.

```rust
// verified — GOOD: a plugin with no settings is a function
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Health(f32);

fn decay(mut healths: Query<&mut Health>) {
    for mut health in &mut healths {
        health.0 -= 1.0;
    }
}

pub fn plugin(app: &mut App) {
    app.add_systems(FixedUpdate, decay);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_function_is_a_plugin() {
        let mut app = App::new();
        app.add_plugins(plugin);
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

/// Configuration, which is why this is a type rather than a function.
#[derive(Debug, Clone, Copy)]
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

### BV-ARC-12 [M] Let a duplicate plugin panic rather than opting out of the check

Adding a plugin that is already in the `App` panics at `add_plugins`. Fix the double add; do not
override `is_unique` to make it stop.

**Why:** the refusal is the good outcome — the alternative is a game that applies gravity twice per
step with nothing saying so. Overriding `is_unique` buys exactly that, so it is only correct for a
plugin whose `build` is genuinely idempotent, and then the `build` is what has to be shown to be.

The check is by plugin **name**, which defaults to the type's `type_name`. That catches a plugin
type, a named function, and — because they render identically — two unrelated closures. Two inline
`|app: &mut App| { … }` plugins in one function both print as `{{closure}}`, so the second is
refused with a message naming neither. It is the strongest practical argument for BV-ARC-09's named
function over an inline closure.

**Check:** grep for `fn is_unique`. Each override needs the reason the plugin is meaningfully
instantiable twice, plus a test that adds it twice and asserts the world is what it should be.

```rust
// verified
use bevy::prelude::*;

#[derive(Resource, Debug, Default)]
struct WaveCount(u32);

pub fn plugin(app: &mut App) {
    app.init_resource::<WaveCount>();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adding_the_plugin_twice_is_refused_rather_than_doubled() {
        let mut app = App::new();
        app.add_plugins(plugin);
        assert!(app.world().get_resource::<WaveCount>().is_some());

        // `App` is not `UnwindSafe`, and the panic is the assertion.
        let again = std::panic::AssertUnwindSafe(move || {
            app.add_plugins(plugin);
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

### BV-ARC-15 [S] Give each plugin one module and each module one plugin

`combat.rs` defines `combat::plugin` and the components, systems and sets that plugin registers.

**Why:** it makes the module tree and the plugin tree the same tree, so `add_plugins` reads as a
table of contents for the source. A module with two plugins is two features that have not been
separated; a plugin spanning two modules has no single place a reader can start.

**Check:** does every `pub fn plugin` or `impl Plugin` sit at the root of its own module, and does
every feature module have exactly one?

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
fn main() -> AppExit {
    App::new()
        .add_plugins(DefaultPlugins)
        .add_plugins((combat::plugin, economy::plugin, hud::plugin))
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

`src/lib.rs` holds the plugins; `src/main.rs` is `App::new().add_plugins(mygame::plugin).run()`.

**Why:** integration tests, benchmarks and any second binary can depend on a library and cannot
depend on a binary. Without the split, every test that needs more than one plugin has to be a unit
test inside the binary crate, and `cargo test --lib` stops being the fast loop.

**Check:** is there anything in `main.rs` besides `main`? Is there a `tests/` directory? If the
answer to the first is yes and the second is no, the split has not happened.
