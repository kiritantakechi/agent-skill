# Errors: Fallible Systems, the Error Handler, Panicking APIs

Scope: what a Bevy system does when something goes wrong, where that failure ends up, and which
half of Bevy's paired APIs to call. The general rules about error *types* — one enum per failure
mode, carry the source, `thiserror` in libraries and not in public APIs — are unchanged and live in
the other standard; this chapter is about the paths Bevy adds.

A system may return `Result`, which removes the last reason for `unwrap` in game code. What it
returns goes to the fallback error handler that `App::set_error_handler` installs. Its default
dispatches on a `Severity` carried by the error (`Severity::Panic` unless annotated), and a panic in
a system, observer or command reaches it too, as an error carrying the panic's payload.

## Contents

- **Fallible systems**
  - BV-ERR-01 [M!] Return `Result` from a system that can fail
  - BV-ERR-02 [M] Use Bevy's `Result` alias in a system signature
  - BV-ERR-03 [M] Keep `BevyError` at the boundary and a real type underneath
  - BV-ERR-04 [S] Annotate a severity where the default reading is wrong
  - BV-ERR-05 [M] Choose the fallback error handler deliberately
  - BV-ERR-06 [S] Override the handler per schedule only where the phase differs

- **The panicking half**
  - BV-ERR-07 [M] Prefer the non-panicking half of every pair
  - BV-ERR-08 [M] Never panic to report bad content

- **Elsewhere**
  - BV-ERR-09 [M] Report through `tracing`, never through `println!`
  - BV-ERR-10 [M] Exit with `AppExit::error` when startup cannot continue
  - BV-ERR-11 [M!] Decide the render error policy, because the default quits
- Decided by tools

---

## Fallible systems

### BV-ERR-01 [M!] Return `Result` from a system that can fail

`fn follow(…) -> Result` and `?` on everything fallible, in a system, an observer or a command. No
`unwrap`, no `expect`, no `panic!` on a path the game reaches. An absence the game expects is not a
failure: a system that needs one entity takes `Single`, which skips it while none matches, and keeps
`?` for what nobody expected. A custom command returns its failure as `type Out = Result`, and a
function-style one is `-> impl Command` with a closure returning `Result`.

*Relaxed form:* a debug tool, an example, or a `#[cfg(test)]` system may `expect` where the
condition is a genuine invariant of the test, and the message states the invariant.

**Why:** the conditions that fail are ordinary — a stale entity id, a missing asset, a malformed
file. A returned error reaches a handler that can log it and carry on; a panic stays fatal under
BV-ERR-05 and takes the player's unsaved progress with it.

**Check:** the `unwrap_used` row (`references/ecs.md`) and this chapter's `expect_used`, `panic`,
`todo` and `unimplemented` rows fail the build on the spellings. Read for what they cannot see: a
system that can fail returning `()`, with the failure dropped in a `let … else { return }`.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
struct Player;

/// The HUD panel, and the player it follows.
#[derive(Component, Debug, Clone, Copy, Reflect)]
#[reflect(Component)]
struct Hud {
    pub follows: Entity,
}

/// No HUD yet is an absence the game expects, so `Single` skips the system
/// until there is one. A HUD following a player who is gone is not, so that
/// is the `?`.
fn update_hud(
    hud: Single<(&Hud, &mut Node)>,
    players: Query<&Transform, With<Player>>,
) -> Result {
    let (hud, mut node) = hud.into_inner();
    let player = players.get(hud.follows)?;
    node.left = px(player.translation.x);
    Ok(())
}
```

```rust
// verified
use bevy::prelude::*;
use core::fmt;

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Gold(pub u32);

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Repairing;

/// The one failure these commands can hit that Bevy does not already name.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NoPurse(pub Entity);

impl fmt::Display for NoPurse {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} has no Gold to charge", self.0)
    }
}

impl core::error::Error for NoPurse {}

/// A command states its output as an associated type, so one that can fail
/// says `type Out = Result`.
#[derive(Debug, Clone, Copy)]
pub struct Charge {
    pub payer: Entity,
    pub amount: u32,
}

impl Command for Charge {
    type Out = Result;

    /// A command runs at the next flush, not at the queue call, so the
    /// payer may already be despawned — which is what `Out` is for.
    fn apply(self, world: &mut World) -> Self::Out {
        let mut payer = world.get_entity_mut(self.payer)?;
        let mut gold = payer.get_mut::<Gold>().ok_or(NoPurse(self.payer))?;
        gold.0 = gold.0.saturating_sub(self.amount);
        Ok(())
    }
}

/// The function-style form: `-> impl Command`, with the closure returning
/// `Result`.
#[must_use]
pub fn refund(payee: Entity, amount: u32) -> impl Command {
    move |world: &mut World| -> Result {
        let mut entity = world.get_entity_mut(payee)?;
        let mut gold = entity.get_mut::<Gold>().ok_or(NoPurse(payee))?;
        gold.0 = gold.0.saturating_add(amount);
        Ok(())
    }
}

/// `queue` sends an `Err` from `apply` to the fallback error handler;
/// `queue_handled` picks a different one and `queue_silenced` drops it.
fn charge_for_repairs(mut commands: Commands, repairing: Query<Entity, With<Repairing>>) {
    for payer in &repairing {
        commands.queue(Charge { payer, amount: 10 });
    }
}

#[derive(Debug, Default)]
pub struct RepairPlugin;

impl Plugin for RepairPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Update, charge_for_repairs);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_queued_charge_reaches_the_purse() {
        let mut app = App::new();
        app.add_plugins(RepairPlugin);
        let payer = app.world_mut().spawn((Repairing, Gold(50))).id();

        app.update();

        assert_eq!(
            app.world().get_entity(payer).map(|e| e.get::<Gold>()),
            Ok(Some(&Gold(40)))
        );
    }

    #[test]
    fn the_function_style_command_goes_through_the_same_queue() {
        let mut world = World::new();
        let payee = world.spawn(Gold(5)).id();

        world.commands().queue(refund(payee, 7));
        world.flush();

        assert_eq!(
            world.get_entity(payee).map(|e| e.get::<Gold>()),
            Ok(Some(&Gold(12)))
        );
    }

    #[test]
    fn a_despawned_payer_is_an_err_and_not_a_panic() {
        let mut world = World::new();
        let payer = world.spawn(Gold(50)).id();
        assert!(world.despawn(payer));

        assert!(Charge { payer, amount: 10 }.apply(&mut world).is_err());
    }

    #[test]
    fn a_purseless_payer_names_itself_in_the_error() {
        let mut world = World::new();
        let payer = world.spawn_empty().id();

        let Err(error) = (Charge { payer, amount: 10 }).apply(&mut world) else {
            unreachable!()
        };

        assert_eq!(error.downcast_ref::<NoPurse>(), Some(&NoPurse(payer)));
        assert!(
            NoPurse(payer)
                .to_string()
                .ends_with("has no Gold to charge")
        );
    }
}
```

### BV-ERR-02 [M] Use Bevy's `Result` alias in a system signature

`-> Result` — which is `Result<(), BevyError>`. Not `-> Result<(), MyError>` and not
`-> anyhow::Result<()>`.

**Why:** the schedule accepts `Result<(), BevyError>` and no other error type, so any other type is
converted at the boundary anyway. `BevyError` converts from anything implementing `Error`, so the
alias costs nothing and every fallible system looks the same.

**Check:** grep for `-> Result<` in system signatures. Anything with explicit parameters is either
not a system or is fighting the schedule.

### BV-ERR-03 [M] Keep `BevyError` at the boundary and a real type underneath

Domain code returns its own error enum. The system that calls it converts with `?`, and adds what
it knows with `.context("…")` or `.with_context(|| …)` — `ContextExt`, in the prelude.
On an `Option` the same call builds the error, where `ok_or(…)` needed an error type of its own.

**Why:** `BevyError` is boxed and type-erased: the right shape when the only reader is a log line,
the wrong one for a caller that branches. Domain code returning it cannot be matched on or tested
for one failure, and drags a Bevy type across the boundary BV-ARCH-01 keeps clean.

**Check:** grep the domain crates for `BevyError`. There should be none.

```rust
// verified
use bevy::prelude::*;
use core::fmt;

/// The domain's failure modes, named so a caller can branch on them.
/// `thiserror` is not a dependency here, so both impls are written out.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CombatError {
    /// The attack table has no row for this weapon tier.
    UnknownTier(u8),
    /// Armour was configured past the end of the damage curve.
    ArmorOutOfRange { armor: u32, max: u32 },
}

impl fmt::Display for CombatError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            Self::UnknownTier(tier) => write!(f, "no attack row for weapon tier {tier}"),
            Self::ArmorOutOfRange { armor, max } => {
                write!(f, "armor {armor} is past the curve's maximum of {max}")
            }
        }
    }
}

impl core::error::Error for CombatError {}

const ATTACK_BY_TIER: [u32; 3] = [4, 9, 15];
const MAX_ARMOR: u32 = 20;

/// Domain code: no `World`, no `BevyError`, no `App` needed to test it.
///
/// # Errors
///
/// [`CombatError::UnknownTier`] when no row exists for `tier`, and
/// [`CombatError::ArmorOutOfRange`] when `armor` leaves the curve.
pub fn resolve_hit(tier: u8, armor: u32) -> Result<u32, CombatError> {
    let attack = ATTACK_BY_TIER
        .get(usize::from(tier))
        .copied()
        .ok_or(CombatError::UnknownTier(tier))?;
    if armor > MAX_ARMOR {
        return Err(CombatError::ArmorOutOfRange {
            armor,
            max: MAX_ARMOR,
        });
    }
    Ok(attack.saturating_sub(armor))
}

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct PendingHit;

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Armor(pub u32);

#[derive(Component, Debug, Clone, Copy, PartialEq, Reflect)]
#[reflect(Component)]
pub struct Health(pub u32);

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct EquippedWeapon {
    pub tier: u8,
}

/// The boundary, and the only place `CombatError` becomes a `BevyError`:
/// one `.context(..)?`, in the one function the schedule can see.
fn apply_pending_hits(
    mut targets: Query<(&Armor, &mut Health), With<PendingHit>>,
    weapon: Res<EquippedWeapon>,
) -> Result {
    for (armor, mut health) in &mut targets {
        let damage = resolve_hit(weapon.tier, armor.0).context("applying a pending hit")?;
        health.0 = health.0.saturating_sub(damage);
    }
    Ok(())
}

#[derive(Debug, Default)]
pub struct CombatPlugin;

impl Plugin for CombatPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<EquippedWeapon>()
            .add_systems(Update, apply_pending_hits);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bevy::ecs::system::{RunSystemError, RunSystemOnce};

    #[test]
    fn the_domain_answers_without_an_ecs() {
        assert_eq!(resolve_hit(1, 3), Ok(6));
        assert_eq!(resolve_hit(2, 20), Ok(0));
    }

    #[test]
    fn each_failure_is_a_variant_a_caller_can_match_on() {
        assert_eq!(resolve_hit(7, 0), Err(CombatError::UnknownTier(7)));
        assert_eq!(
            resolve_hit(0, 21),
            Err(CombatError::ArmorOutOfRange { armor: 21, max: 20 })
        );
    }

    #[test]
    fn the_message_names_the_offending_value() {
        let Err(error) = resolve_hit(7, 0) else {
            unreachable!()
        };
        assert_eq!(error.to_string(), "no attack row for weapon tier 7");
    }

    #[test]
    fn the_boxed_error_still_carries_the_domain_type() {
        let boxed = BevyError::from(CombatError::UnknownTier(7));
        assert_eq!(
            boxed.downcast_ref::<CombatError>(),
            Some(&CombatError::UnknownTier(7))
        );
    }

    #[test]
    fn a_bad_tier_is_returned_as_the_domain_error() {
        let mut app = App::new();
        app.add_plugins(CombatPlugin);
        let target = app
            .world_mut()
            .spawn((PendingHit, Armor(3), Health(20)))
            .id();

        app.world_mut().insert_resource(EquippedWeapon { tier: 1 });
        app.update();
        assert_eq!(
            app.world().get_entity(target).map(|e| e.get::<Health>()),
            Ok(Some(&Health(14)))
        );

        // The handler also receives panics, so surviving `update` proves
        // nothing. Run once, the system hands back what it returned,
        // and a panic would unwind through the test instead.
        app.world_mut().insert_resource(EquippedWeapon { tier: 9 });
        let ran: Result<(), _> = app.world_mut().run_system_once(apply_pending_hits);
        assert!(matches!(
            &ran,
            Err(RunSystemError::Failed(error))
                if error.downcast_ref::<CombatError>() == Some(&CombatError::UnknownTier(9))
        ));
        assert_eq!(
            app.world().get_entity(target).map(|e| e.get::<Health>()),
            Ok(Some(&Health(14)))
        );
    }
}
```

### BV-ERR-04 [S] Annotate a severity where the default reading is wrong

`result.with_severity(Severity::Warning)?` when a failure is expected and recoverable. Never
annotate `Severity::Panic`: an un-annotated error already carries it, and BV-ERR-05's shipped
handler logs it like any returned error. A failure that must stop even a shipped build writes
`AppExit::error()`, as BV-ERR-10 does.

**Why:** `match_severity` and BV-ERR-05's shipped handler log an error at its own severity, so the
annotation gives one failure its own level without replacing the handler for all of them. It also
records the decision where it is made: this parse may fail on user content, and that is fine.

**Check:** for each `?` in a system, ask what the log would look like if it fired every frame. An
expected failure logged at error level is a severity that needs stating.

### BV-ERR-05 [M] Choose the fallback error handler deliberately

Install it with `App::set_error_handler`, once, in `main`: `panic` in development, and in a
shipped build a handler that logs a returned error and resumes a panic. A panic in a system,
observer or command reaches the handler as an error carrying its payload, so the shipped handler
resumes unwinding whenever `BevyError::take_payload` returns one. It cannot test `Severity::Panic`
instead: that is also what every un-annotated returned error carries. The handler is where an error
is logged, so the system that returns it does not log it too (`rust-style`'s RS-ERR-09).

**Why:** a development build wants a failure to stop the world where it happened, a shipped build
the log line and the next frame. The default, `match_severity`, panics on every un-annotated error
in both, and a handler that only logs, such as `error`, logs each panic and keeps running.

**Check:** grep for `set_error_handler`: one call, in `main`, distinguishing the two builds — a
second call panics. An inserted `FallbackErrorHandler` reaches the main world only, leaving the
render and extract worlds on the default. The shipped handler calls `take_payload` before it logs.

```rust
// fragment — the handler is a build-time decision, so it is made in main
use bevy::ecs::error::{ErrorContext, error, match_severity, panic};
use bevy::prelude::*;

/// Logs a returned error and runs the next frame; a panic stays fatal.
fn shipped(mut err: BevyError, ctx: ErrorContext) {
    // A caught panic: an overflow trap, an index out of range, an engine assert.
    if let Some(payload) = err.take_payload() {
        std::panic::resume_unwind(payload);
    }
    // With no payload, `Severity::Panic` is an un-annotated `?`: log it. A lower
    // severity (BV-ERR-04) is logged at its own level.
    match err.severity() {
        Severity::Panic => error(err, ctx),
        _ => match_severity(err, ctx),
    }
}

fn main() -> AppExit {
    let handler = if cfg!(debug_assertions) { panic } else { shipped };
    App::new()
        .set_error_handler(handler)
        .add_plugins(DefaultPlugins)
        .run()
}
```

### BV-ERR-06 [S] Override the handler per schedule only where the phase differs

A schedule can carry its own handler. Use it where one phase genuinely wants different treatment —
a loading schedule that must not panic on a missing optional asset.

**Why:** per-schedule handlers are a real capability and a real way to lose track of what happens to
an error, because the answer is now "depends which schedule". One global handler plus per-error
severity (BV-ERR-04) covers nearly every case and keeps the answer in one place.

**Check:** for each schedule-level handler, name the errors it treats differently and why severity
could not have expressed it.

## The panicking half

### BV-ERR-07 [M] Prefer the non-panicking half of every pair

Bevy ships both halves for most `World` lookups. Take the one that returns `Option` or `Result`.
A query, an asset collection and an `EntityRef` return one already, and unwrapping it is the
`unwrap_used` row. This is about game code: a `#[cfg(test)]` body may take the panicking half,
because a test asserting on the world wants the panic (BV-TEST-06), and routing it through
`get_resource` would only add an unwrap that BV-ERR-01 forbids.

**Why:** the panicking half exists for examples and for code where the invariant is structural, and
game code is neither. The pairs are easy to miss because the panicking name is the shorter one — it
reads as the default when it is the exception.

**Check:** grep for the left column, outside `#[cfg(test)]`.

| Panicking | Use instead |
|---|---|
| `World::entity` | `World::get_entity` |
| `World::entity_mut` | `World::get_entity_mut` |
| `World::resource` | `World::get_resource` |
| `World::resource_mut` | `World::get_resource_mut` |
| `World::non_send` | `World::get_non_send` |

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug, Clone, Copy, Default, Reflect)]
#[reflect(Component)]
pub struct Player;

#[derive(Resource, Debug, Default, Reflect)]
#[reflect(Resource)]
pub struct CameraRig {
    pub watching: Option<Entity>,
    pub focus: Vec3,
}

/// `Single` skips the system while no player exists, so the frame after the
/// player dies leaves the rig watching the last one rather than failing.
fn aim_rig(player: Single<Entity, With<Player>>, mut rig: ResMut<CameraRig>) {
    rig.watching = Some(*player);
}

/// An exclusive system is where the `World` pairs live. Every lookup below
/// has a shorter-named twin — `resource`, `entity`, `get(..).unwrap()` —
/// and each of those turns a frame the rig is one tick stale into a crash.
fn record_focus(world: &mut World) {
    // A frame before the rig exists is a skipped frame, not a failure.
    let Some(watching) = world
        .get_resource::<CameraRig>()
        .and_then(|rig| rig.watching)
    else {
        return;
    };

    // The watched entity may have been despawned since the rig recorded it.
    let Some(translation) = world
        .get_entity(watching)
        .ok()
        .and_then(|watched| watched.get::<Transform>().map(|t| t.translation))
    else {
        return;
    };

    if let Some(mut rig) = world.get_resource_mut::<CameraRig>() {
        rig.focus = translation;
    }
}

#[derive(Debug, Default)]
pub struct CameraRigPlugin;

impl Plugin for CameraRigPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<CameraRig>()
            .add_systems(Update, (aim_rig, record_focus).chain());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_frame_after_the_player_dies_is_skipped_and_keeps_the_rig() {
        let mut app = App::new();
        app.add_plugins(CameraRigPlugin);
        let player = app
            .world_mut()
            .spawn((Player, Transform::from_xyz(1.0, 2.0, 3.0)))
            .id();

        app.update();

        // `Single` skips `aim_rig`, and `get_entity` finds a despawned id
        // that `record_focus` steps past. The panicking halves would crash
        // this frame; the default handler would crash on a returned error.
        assert!(app.world_mut().despawn(player));
        app.update();

        let Some(rig) = app.world().get_resource::<CameraRig>() else {
            unreachable!()
        };
        assert_eq!(rig.watching, Some(player));
        assert!(
            rig.focus
                .abs_diff_eq(Vec3::new(1.0, 2.0, 3.0), f32::EPSILON)
        );
    }

    #[test]
    fn a_watched_entity_without_a_transform_is_a_skipped_frame() {
        let mut app = App::new();
        app.add_plugins(CameraRigPlugin);
        app.world_mut().spawn(Player);

        // Nothing here can fail, so an `update` that completes is one in
        // which both systems ran past the missing transform.
        app.update();

        let Some(rig) = app.world().get_resource::<CameraRig>() else {
            unreachable!()
        };
        assert!(rig.watching.is_some());
        assert!(rig.focus.abs_diff_eq(Vec3::ZERO, f32::EPSILON));
    }
}
```

### BV-ERR-08 [M] Never panic to report bad content

A malformed level file, a missing texture, a negative value in a config are inputs, and
`rust-style`'s RS-ERR-01 keeps a panic for bugs. In a game the input changes while it runs: content
is edited under hot reload.

**Why:** the people editing it are not looking at a stack trace, and a panic mid-edit takes the
session with it. A logged error naming the file and the field tells them what to fix while
everything else keeps working.

**Check:** for each panic path on content, ask whether an artist could cause it by saving a file
while the game runs. If so it is a `Result` with the path in the message.

## Elsewhere

### BV-ERR-09 [M] Report through `tracing`, never through `println!`

`info!`, `warn!`, `error!`, `debug!`, `trace!`, as `rust-style`'s RS-CLI-25 asks. In Bevy,
`LogPlugin` is the subscriber, and on wasm `println!` never reaches the browser console.

**Why:** `LogPlugin` gives every record a level, a target and a filter, so a shipped build turns the
noisy ones off and a developer turns one module's on. `println!` bypasses all of it, and on wasm it
is lost, information and all.

**Check:** grep for `println!` and `eprintln!` outside `build.rs` and a CLI tool's output. `dbg!` is
the `dbg_macro` row.

### BV-ERR-10 [M] Exit with `AppExit::error` when startup cannot continue

A missing required asset directory, an unusable GPU, a corrupt configuration: write
`AppExit::error()` to the message and let the app shut down.

**Why:** here continuing is worse than stopping, and the exit code reaches the launcher, the test
harness and the crash reporter as a panic's would, minus a stack trace nobody can act on. It is
also the clean stop: plugins shut down, and the window closes rather than vanishing.

**Check:** for each `panic!` outside a test, ask whether `AppExit::error()` says the same thing more
usefully.

### BV-ERR-11 [M!] Decide the render error policy, because the default quits

`bevy::render::error_handler::RenderErrorHandler` decides what happens when the GPU fails. Insert
your own before `DefaultPlugins`, beside the `set_error_handler` call; `RenderPlugin` registers it
with `init_resource`, so yours wins. `RenderErrorPolicy::Recover(RenderCreation)` rebuilds the
device, `StopRendering` keeps the app alive with the image frozen, and `Ignore` keeps drawing, which
can strobe when the fault repeats — so `Ignore` is the one that has to be justified.

*Relaxed form:* a tool or an example may take the default, and then the rule is that nobody reports
its clean exit as a crash.

**Why:** the default logs and writes `AppExit::error()` for **every** `RenderError`, so a
transient GPU fault closes the player's window and BV-ARCH-16 turns it into an exit that reads as a
crash. BV-ERR-10 makes an unusable GPU at startup your decision; this is the same GPU an hour later.

**Check:** grep for `RenderErrorHandler`. Exactly one insertion, and it branches on the error rather
than returning one blanket policy.

```rust
// fragment — `RenderErrorHandler` lives in `bevy_render`, which needs a GPU
use bevy::prelude::*;
use bevy::render::error_handler::{
    ErrorType, RenderError, RenderErrorHandler, RenderErrorPolicy,
};
use bevy::render::settings::{RenderCreation, WgpuSettings};

/// One decision per failure kind. The default is a single blanket policy
/// — log, `AppExit::error()`, stop — for all four.
///
/// `RenderErrorPolicy::Ignore` appears nowhere below on purpose: it keeps
/// drawing into a faulted device, which strobes when the fault repeats.
fn on_render_error(
    error: &RenderError,
    main_world: &mut World,
    _render_world: &mut World,
) -> RenderErrorPolicy {
    match error.ty {
        // A driver reset or a laptop waking from sleep: rebuild the device
        // and let `RenderStartup` run again.
        ErrorType::DeviceLost => {
            warn!("render device lost, rebuilding: {}", error.description);
            let settings = Box::new(WgpuSettings::default());
            RenderErrorPolicy::Recover(RenderCreation::Automatic(settings))
        }
        // Out of memory repeats until something is freed, so freeze the image
        // and keep the app alive long enough to autosave.
        ErrorType::OutOfMemory => {
            error!("out of video memory; rendering stopped");
            RenderErrorPolicy::StopRendering
        }
        // A validation or internal fault is a bug in our own render code, so
        // stop with an exit code the launcher can act on (BV-ERR-10).
        ErrorType::Validation | ErrorType::Internal => {
            error!("unrecoverable render error: {}", error.description);
            main_world.write_message(AppExit::error());
            RenderErrorPolicy::StopRendering
        }
    }
}

fn main() -> AppExit {
    App::new()
        // `RenderPlugin` registers this with `init_resource`, so ours wins.
        // It sits beside the `set_error_handler` call of BV-ERR-05: two
        // handlers, two build-time decisions, made in the same place.
        .insert_resource(RenderErrorHandler(on_render_error))
        .add_plugins(DefaultPlugins)
        .run()
}
```

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| clippy | `expect_used` | deny | `.expect("…")` on a path the game reaches — `?` hands the error to the handler |
| clippy | `panic` | deny | `panic!` to report a failure — return the error, or write `AppExit::error()` at startup |
| clippy | `todo` | deny | a `todo!()` on a path the game reaches |
| clippy | `unimplemented` | deny | an `unimplemented!()` on a path the game reaches |
| clippy | `indexing_slicing` | deny | indexing a `Vec` or slice an entity count reaches — `get` returns an `Option` |
| clippy | `dbg_macro` | deny | `dbg!`, which writes to stderr past `LogPlugin` |
