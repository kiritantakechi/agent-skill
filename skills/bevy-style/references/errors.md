# Errors: Fallible Systems, the Error Handler, Panicking APIs

Scope: what a Bevy system does when something goes wrong, where that failure ends up, and which
half of Bevy's paired APIs to call. The general rules about error *types* — one enum per failure
mode, carry the source, `thiserror` in libraries and not in public APIs — are unchanged and live in
the other standard; this chapter is about the paths Bevy adds.

Since 0.16 a system may return `Result`, which removed the last reason for `unwrap` in game code.
Since 0.19 the handler is `FallbackErrorHandler`, its default dispatches on a `Severity` carried by
the error, and a `Command` declares its output as an associated type.

## Contents

- **Fallible systems**
  - BV-ERR-01 [M!] Return `Result` from a system that can fail
  - BV-ERR-02 [M] Use Bevy's `Result` alias in a system signature
  - BV-ERR-03 [M] Keep `BevyError` at the boundary and a real type underneath
  - BV-ERR-04 [S] Annotate a severity where the default reading is wrong
  - BV-ERR-05 [M] Choose the fallback error handler deliberately
  - BV-ERR-06 [S] Override the handler per schedule only where the phase differs

- **The panicking half**
  - BV-ERR-07 [M] Never unwrap a query
  - BV-ERR-08 [M] Never index a collection an entity count can reach
  - BV-ERR-09 [M] Prefer the non-panicking half of every pair
  - BV-ERR-10 [M] Never panic to report bad content
  - BV-ERR-11 [M] Do not discard a `Result` with `let _ =`

- **Elsewhere**
  - BV-ERR-12 [M] Give a command's output the `Out` associated type
  - BV-ERR-13 [M] Propagate from an observer the same way as from a system
  - BV-ERR-14 [M] Report through `tracing`, never through `println!`
  - BV-ERR-15 [S] Log once, where the error is handled
  - BV-ERR-16 [M] Exit with `AppExit::error` when startup cannot continue

---

## Fallible systems

### BV-ERR-01 [M!] Return `Result` from a system that can fail

`fn follow(…) -> Result` and `?` on everything fallible. No `unwrap`, no `expect`, no `panic!` on a
path the game reaches.

*Relaxed form:* a debug tool, an example, or a `#[cfg(test)]` system may `expect` where the
condition is a genuine invariant of the test, and the message states the invariant.

**Why:** every panic in a Bevy system takes the whole app down, including the player's unsaved
progress, and the conditions that produce one are ordinary: the camera is not spawned yet, the
player just died, an asset is still loading. Returning `Result` costs one character per fallible
call and hands the decision to the error handler, which can log and continue.

**Check:** grep the diff for `unwrap(`, `expect(`, `panic!`, `todo!` and `unimplemented!`. Each one
needs to be either a `?` or a documented invariant in test code.

```rust
// verified
use bevy::prelude::*;

#[derive(Component, Debug)]
struct Player;

#[derive(Component, Debug)]
struct Hud;

/// A frame before the player exists is a skipped frame, not a crash.
fn update_hud(
    players: Query<&Transform, With<Player>>,
    mut huds: Query<&mut Node, With<Hud>>,
) -> Result {
    let player = players.single()?;
    let mut hud = huds.single_mut()?;
    hud.left = Val::Px(player.translation.x);
    Ok(())
}
```

### BV-ERR-02 [M] Use Bevy's `Result` alias in a system signature

`-> Result` — which is `Result<(), BevyError>`. Not `-> Result<(), MyError>` and not
`-> anyhow::Result<()>`.

**Why:** the schedule accepts systems returning `Result<(), BevyError>` and nothing else, so any
other error type has to be converted at the boundary anyway — writing it in the signature just moves
the conversion into every `?`. `BevyError` converts from anything implementing `Error`, so the alias
costs nothing and makes every fallible system look the same.

**Check:** grep for `-> Result<` in system signatures. Anything with explicit parameters is either
not a system or is fighting the schedule.

### BV-ERR-03 [M] Keep `BevyError` at the boundary and a real type underneath

Domain code returns its own error enum. The system that calls it converts with `?`.

**Why:** `BevyError` is a boxed, type-erased error — the right shape for something whose only reader
is a log line, and the wrong shape for anything a caller branches on. Domain code that returns
`BevyError` cannot be matched on, cannot be tested for a specific failure, and drags a Bevy type
across the boundary that BV-ARC-01 exists to keep clean.

**Check:** grep the domain crates for `BevyError`. There should be none.

### BV-ERR-04 [S] Annotate a severity where the default reading is wrong

`result.with_severity(Severity::Warning)?` when a failure is expected and recoverable, or
`Severity::Panic` when continuing would corrupt something.

**Why:** 0.19's default handler dispatches on the error's severity, so annotating is how a specific
failure gets a different treatment without replacing the handler for everything. It is also
documentation at the point of the decision: "this parse can fail on user content and that is fine"
is a claim worth writing where the parse is.

**Check:** for each `?` in a system, ask what the log would look like if it fired every frame. An
expected failure logged at error level is a severity that needs stating.

### BV-ERR-05 [M] Choose the fallback error handler deliberately

Set `FallbackErrorHandler` at startup. Loud in development, recoverable in a shipped build.

**Why:** the default in 0.19 dispatches on severity, which is a reasonable default and is still
somebody else's decision about your game. A development build wants a failure to stop the world at
the point it happened; a shipped build wants the log line and the next frame. Leaving it unset means
both builds behave the same, and one of them is wrong.

**Check:** grep for `FallbackErrorHandler`. Exactly one insertion, before `DefaultPlugins`, and it
distinguishes the two builds.

```rust
// fragment — the handler is a build-time decision, so it is made in main
fn main() -> AppExit {
    let handler = if cfg!(debug_assertions) { panic } else { error };
    App::new()
        .insert_resource(FallbackErrorHandler(handler))
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

### BV-ERR-07 [M] Never unwrap a query

`query.single()?`, `query.get(entity)?`, `let Ok(x) = … else { continue }`. Never `.unwrap()` and
never `.expect(…)` on a query result.

**Why:** "exactly one camera" and "this entity has a Health" are true right up until the frame where
they are not — the entity was despawned by a system that ran earlier, or has not been spawned yet
because loading finished this frame. `single` was made fallible in 0.16 for exactly this reason:
the panicking form was the shorter name, so it read as the default.

**Check:** grep for `single().unwrap`, `single_mut().unwrap`, `get(`…`).unwrap` and `.expect(` on
anything derived from a `Query`.

### BV-ERR-08 [M] Never index a collection an entity count can reach

`slice[i]` where `i` came from a component, a message, or an entity count is a panic waiting for the
frame the counts disagree. Use `get`.

**Why:** the index and the collection are updated by different systems, so they are consistent only
between them — a wave counter incremented in `FixedUpdate` and a `Vec` of wave definitions loaded
from an asset will disagree the first time content is edited. `clippy::indexing_slicing` is at deny
in this standard's lint table for exactly this.

**Check:** grep for `[` applied to a `Vec`, a slice or an array inside a system.

### BV-ERR-09 [M] Prefer the non-panicking half of every pair

Bevy ships both halves for most lookups. Take the one that returns `Option` or `Result`.

**Why:** the panicking half exists for examples and for code where the invariant is structural, and
game code is neither. The pairs are easy to miss because the panicking name is the shorter one — it
reads as the default when it is the exception. `bevy_lint`'s `panicking_methods` reports the `World`
ones.

**Check:** grep for the left column.

| Panicking | Use instead |
|---|---|
| `World::entity` | `World::get_entity` |
| `World::entity_mut` | `World::get_entity_mut` |
| `World::resource` | `World::get_resource` |
| `World::resource_mut` | `World::get_resource_mut` |
| `World::non_send` | `World::get_non_send` |
| `Query::single` unwrapped | `Query::single` with `?` |
| `Assets::get` unwrapped | `Assets::get` with a match on `None` |
| `EntityRef::get::<T>` unwrapped | the same, handling `None` |

### BV-ERR-10 [M] Never panic to report bad content

A malformed level file, a missing texture, a negative value in a config — these are inputs, and an
input is never a bug in the program.

**Why:** content is edited by people who are not looking at a stack trace, often while the game is
running under hot reload. A panic tells them the game is broken; a logged error naming the file and
the field tells them what to fix, and lets everything else keep working. The distinction is exactly
the standard's usual one — a panic means a bug in the code — and content is not code.

**Check:** for each panic path, ask whether an artist could cause it by saving a file. If so it is a
`Result` with the path in the message.

### BV-ERR-11 [M] Do not discard a `Result` with `let _ =`

If a fallible call's outcome genuinely does not matter, say so in a comment on the line that
discards it.

**Why:** `let _ = …` is indistinguishable from an oversight, and Bevy's builder methods return
`&mut App` rather than `Result`, so the ones that *do* return `Result` are exactly the interesting
ones. The comment is what makes a deliberate discard reviewable.

**Check:** grep for `let _ =`. Each occurrence needs a reason on the line above.

## Elsewhere

### BV-ERR-12 [M] Give a command's output the `Out` associated type

In 0.19, `Command` takes its output as an associated type: `impl Command for Foo { type Out =
Result; … }`. The old `impl Command<Result>` no longer exists.

**Why:** this is a compile error rather than a silent change, but it is the shape most existing code
and most examples still use, so it is worth knowing which form is current before writing a custom
command. Function-style commands returning `Result` now say `-> impl Command` with no parameter.

**Check:** grep for `Command<` with a type argument.

### BV-ERR-13 [M] Propagate from an observer the same way as from a system

An observer may return `Result`, and it goes to the same handler.

**Why:** observers run in the middle of a command flush, so a panic there unwinds through the ECS's
own machinery — a strictly worse place to fail than a system. There is no reason to write an
observer differently: the return type, the `?`, and the handler are the same.

**Check:** search observers for `unwrap` and `expect`. They are as unacceptable there as in a
system.

### BV-ERR-14 [M] Report through `tracing`, never through `println!`

`info!`, `warn!`, `error!`, `debug!`, `trace!`. Not `println!`, not `eprintln!`, not `dbg!`.

**Why:** `LogPlugin` gives every record a level, a target and a filter, so a shipped build can turn
the noisy ones off and a developer can turn one module's on. `println!` bypasses all of it, does not
appear in the browser console on a wasm build, and is not filtered — so it either spams the log or
gets deleted, and deleting it loses the information.

**Check:** grep for `println!`, `eprintln!` and `dbg!` outside `build.rs` and a CLI tool's output.

### BV-ERR-15 [S] Log once, where the error is handled

An error logged where it is produced and again where it is handled appears twice, with the same
cause and two different framings.

**Why:** the handler is where the context lives — which entity, which asset, what the game did about
it — so the log line written there is the useful one. A line at the production site has only the
local view, and the two together make the log's volume a function of the call stack's depth rather
than of what happened.

**Check:** follow one error from its source to the handler. If it is logged at more than one level,
delete all but the outermost.

### BV-ERR-16 [M] Exit with `AppExit::error` when startup cannot continue

A missing required asset directory, an unusable GPU, a corrupt configuration: write
`AppExit::error()` to the message and let the app shut down.

**Why:** this is the one case where continuing is worse than stopping, and Bevy already has the
mechanism — the exit code reaches the launcher, the test harness and the crash reporter, which a
panic also does but with a stack trace nobody can act on. It is also the only way to stop cleanly:
plugins get to shut down, and the window closes rather than vanishing.

**Check:** for each `panic!` outside a test, ask whether `AppExit::error()` says the same thing more
usefully.
