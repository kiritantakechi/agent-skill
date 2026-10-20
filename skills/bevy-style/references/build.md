# Cargo: Features, Version Pinning, Lints, CI

Scope: the manifest of a project that depends on Bevy — which features to turn on, how tightly to
pin the engine, which of the other standard's lints have to be relaxed and why, and what CI runs.
Everything general about manifests, features, semver and CI is unchanged and lives in the other
standard; this chapter is the Bevy delta.

Two lints are relaxed here and no others. Both were measured against a representative plugin rather
than assumed, and the measurement is stated with the rule, because "clippy is too strict for Bevy"
is the usual justification for an allow list forty entries long that hides real defects.

## Contents

- **The dependency**
  - BV-BUILD-01 [M] Depend on the `bevy` facade, not on its subcrates
  - BV-BUILD-02 [M] Start from a feature collection
  - BV-BUILD-03 [M] Hand-pick features only against a recorded measurement
  - BV-BUILD-04 [M] Pin Bevy exactly in a binary and with a caret in a library
  - BV-BUILD-05 [M] Keep every ecosystem crate on one Bevy version
  - BV-BUILD-06 [S] Check a plugin crate's compatibility table before adding it

- **Profiles**
  - BV-BUILD-07 [M] Compile dependencies optimised in the dev profile
  - BV-BUILD-08 [S] Keep `dynamic_linking` off the committed manifest
  - BV-BUILD-09 [M!] Keep `overflow-checks` on in release where release must match debug
  - BV-BUILD-10 [M] Keep tracing and dev tooling behind off-by-default features
  - BV-BUILD-11 [S] Take the overlays from `bevy_dev_tools`, behind the feature BV-BUILD-10 asks for

- **Lints**
  - BV-BUILD-12 [M] Allow `elided_lifetimes_in_paths`, with the reason in the table
  - BV-BUILD-13 [M] Allow `clippy::needless_pass_by_value`, with the reason in the table
  - BV-BUILD-14 [M] Keep `type_complexity` and `too_many_arguments` switched on
  - BV-BUILD-15 [M] Add nothing else to the allow list without measuring it
  - BV-BUILD-16 [M] Put the table in the workspace and inherit it
  - BV-BUILD-17 [S] Run `bevy_lint`, pinned to the Bevy version

- **CI**
  - BV-BUILD-18 [M] Build the feature set you ship
  - BV-BUILD-19 [S] Build the wasm target if the game ships to the web
  - BV-BUILD-20 [M] Keep `assets/` out of a published package
  - BV-BUILD-21 [S] Cache the target directory, because Bevy is most of the build

---

## The dependency

### BV-BUILD-01 [M] Depend on the `bevy` facade, not on its subcrates

`bevy = { version = …, features = […] }`. Not a list of `bevy_ecs`, `bevy_render`, `bevy_ui`. A
crate that needs one subcrate and no engine should not depend on Bevy at all (BV-ARCH-06).

**Why:** the facade's feature graph is what upstream tests and documents, and the subcrate split
moves every release: 0.20 split `bevy_shape` and `bevy_curve` out of `bevy_math` and added
`bevy_extract`. A manifest naming subcrates is rewritten for each such move; the facade's is not.

**Check:** grep the manifests for `bevy_`. Each hit is either a third-party plugin crate or a
subcrate dependency that needs a reason.

### BV-BUILD-02 [M] Start from a feature collection

`default-features = false` plus `features = ["2d"]`, `["3d", "ui"]`, or the mid-level `2d_api` /
`default_app` / `default_platform` where the backends are not wanted. Not thirty individual names —
and not a collection *without* `default-features = false`, which selects nothing: `default` is
already `["2d", "3d", "ui", "audio"]`.

**Why:** hand-maintained lists rot: a feature is renamed (`animation` became `gltf_animation`) or a
new one becomes necessary, and the manifest keeps compiling while enabling something other than
what it says. Bevy 0.20 has 177 features, and nobody re-reads that list every release.

**Check:** is `default-features = false` there? Without it the list is decoration. Then count the
entries: past about six, they are describing a collection that already exists.
`assets/Cargo.toml` is a workspace manifest with the collection already chosen.

### BV-BUILD-03 [M] Hand-pick features only against a recorded measurement

A hand-picked list is allowed when there is a build-time, binary-size or dependency-count target,
the measurement is in the manifest as a comment, and each feature says why it is there.

**Why:** the trade is usually smaller than it feels, and the number is the only thing that tells a
list worth its upkeep — a re-read every release — from one that is not. Without it the list is an
assumption defended forever; with it, the next release can re-measure and decide again.

**Check:** does the manifest state the number the list buys, and the date or version it was measured
against? If not, switch to a collection until someone measures.

```toml
# fragment — a hand-picked list that has earned itself, with the number in it
[dependencies]
# N crates here against M with the `2d` collection, resolved against 0.20.0.
# M - N crates is the whole of what this list buys, which is the number the next
# person needs in order to decide whether to keep maintaining it. Each entry says
# why; anything unexplained goes back to the collection.
bevy = { version = "=0.20.0", default-features = false, features = [
    "std",                 # no_std Bevy exists and this game is not it
    "async_executor",      # the task-pool executor; implied by default_app, which we skip
    "multi_threaded",      # parallel executor and pipelined rendering
    "bevy_log",            # without it the engine is silent, including render-init failures
    "bevy_asset",          # bevy_image requires it; not optional in practice
    "bevy_winit",          # window and event loop
    "bevy_sprite_render",  # the load-bearing one: pulls the whole 2-D pipeline
    "bevy_text",           # Text2d, for the on-screen readouts
    "default_font",        # embeds a font so Text2d needs no asset file
    "keyboard",            # 0.19 made bevy_input's device modules opt-in
    "mouse",               # ditto; without these KeyCode does not exist
    "png",                 # the only image format this game ships
    "x11",                 # inert on macOS and Windows, required on Linux
    "wayland",
] }
```

### BV-BUILD-04 [M] Pin Bevy exactly in a binary and with a caret in a library

A game binary writes `bevy = "=0.20.0"`. A crate other people depend on writes `bevy = "0.20"`;
the general rule against exact pins is unchanged for anything published.

**Why:** a Bevy minor bump renames a large fraction of the API, so in a binary an exact pin makes an
upgrade a scheduled migration rather than something `cargo update` does. In a library it forbids
every other patch downstream, and two libraries pinned to different patches cannot be used together.

**Check:** is the crate a `[[bin]]` or a `[lib]` others depend on? Exact pin for the first, caret
for the second, and the reason for the pin as a comment beside it.

### BV-BUILD-05 [M] Keep every ecosystem crate on one Bevy version

`cargo tree --duplicates` shows nothing named `bevy`. Two versions in the tree are two engines.

**Why:** the crates are named the same and the types are not: a `Handle<Image>` from 0.19 does not
satisfy a parameter expecting 0.20's, and the error shows two identical type names and no
explanation. It also doubles the compile time of the largest dependency in the project.

**Check:** run `cargo tree --duplicates | grep bevy` in CI. Any output fails the build.
`bevy_lint`'s `duplicate_bevy_dependencies` sees only the facade, and no release of it runs on
0.20 (BV-BUILD-17).

### BV-BUILD-06 [S] Check a plugin crate's compatibility table before adding it

Most Bevy ecosystem crates publish a table of which of their versions works with which Bevy. Read it
before adding the dependency, not after the type errors.

**Why:** the ecosystem lags the engine by weeks to months, and a crate that has not caught up
resolves, compiles its own half, and fails with BV-BUILD-05's duplicate-version errors. Reading the
table first turns that into a decision about whether to wait.

**Check:** for each Bevy plugin dependency, is the version the one its table names for this engine
version?

## Profiles

### BV-BUILD-07 [M] Compile dependencies optimised in the dev profile

`[profile.dev.package."*"] opt-level = 3`, with the game's own crates left at the dev default.

**Why:** an unoptimised Bevy is slow enough that frame rate stops being a signal about the game, and
the engine is compiled once and cached, so the cost is paid on the first build only. The game's own
crates stay unoptimised so the edit-compile-run loop stays fast, the point of the dev profile.

**Check:** does the workspace manifest have the `[profile.dev.package."*"]` block? Without it,
everything anyone says about the game's performance in development is about the wrong build.

### BV-BUILD-08 [S] Keep `dynamic_linking` off the committed manifest

`bevy/dynamic_linking` cuts link time substantially and produces a binary that will not run on
another machine. Turn it on with `--features bevy/dynamic_linking` on the command line.

**Why:** the feature makes the binary depend on a shared object beside it, so a CI artefact built
with it is broken in a way that shows only when somebody runs it elsewhere. As a command-line flag
it is a developer's local choice; in the manifest it is everybody's.

**Check:** grep the manifest for `dynamic_linking`. It belongs in a shell alias or a
`.cargo/config.toml` that is not committed.

### BV-BUILD-09 [M!] Keep `overflow-checks` on in release where release must match debug

`[profile.release] overflow-checks = true` for any game with replays, rollback, lockstep networking
or golden test vectors. The trap is a panic, so it needs BV-ERR-05's shipped handler, which resumes
a panic: since 0.20 a handler that only logs catches the trap and runs the next frame.

*Relaxed form:* a single-player game with no recorded state may take the default, and then the rule
is that nothing compares a release run against a debug one.

**Why:** integer overflow panics in debug and wraps in release, so the two builds compute different
numbers — a replay recorded in development desynchronises on a player's machine, invisibly to every
test. The cost, a check on integer arithmetic, is far below the cost of the desync.

**Check:** does the game record or transmit anything that another run has to reproduce? If so, the
line is mandatory.

### BV-BUILD-10 [M] Keep tracing and dev tooling behind off-by-default features

`bevy/trace`, `bevy/detailed_trace`, the remote protocol, an in-game inspector and a debug overlay
all go behind a feature that is off by default.

**Why:** each costs something a player should not pay: `detailed_trace` instruments the hot loops,
and the remote protocol opens a TCP listener on localhost. Off by default also makes the shipped
configuration the one built by accident, which is the right way round.

**Check:** grep the default feature list. Anything whose name mentions trace, debug, remote,
inspector or editor is on by default and should not be.

### BV-BUILD-11 [S] Take the overlays from `bevy_dev_tools`, behind the feature BV-BUILD-10 asks for

`DiagnosticsOverlayPlugin` (0.19), `FpsOverlayPlugin` and `RenderDebugOverlayPlugin` all live in
`bevy_dev_tools`. Name its feature alongside the collection, inside the dev feature — never in the
default list. A feature named *beside* a collection keeps the collection's guarantee and is not the
hand-picked list BV-BUILD-03 governs; the same shape serves any feature outside the collections,
`bevy_settings` among them (BV-STATE-10).

Since 0.20 the `render_dev_tools` feature, which bevy's `dev` collection includes, puts
`RenderDebugOverlayPlugin` into `DefaultPlugins`, disabled at runtime by default and with its keys
in `RenderDebugOverlayKeybindings`. With that feature on, do not add the plugin by hand: it would be
added twice, and `add_plugins` panics (BV-ARCH-12).

**Why:** a hand-written FPS counter is a `Text` entity, a system, a `Diagnostics` lookup and a
format string that goes stale, and the engine ships all four. `bevy_dev_tools` is in none of the
collections a build starts from — `2d`, `3d`, `ui`, any `*_api` — so BV-BUILD-02 does not reach it.

**Check:** read the default feature list, then the dev one. `bevy_dev_tools` in the first is an
overlay shipped to players; a game that renders it in a release build has answered this rule by
accident. Where either list reaches `render_dev_tools`, grep for `RenderDebugOverlayPlugin`: a hand
add is the duplicate.

```toml
# fragment — the manifest shape, not a whole file
[dependencies]
bevy = { version = "=0.20.0", default-features = false, features = ["2d", "ui", "audio"] }

[features]
default = []
# Named beside the collection, never inside it. `cargo run --features dev`
# turns the overlay on; a release build cannot reach it (BV-BUILD-10).
dev = ["bevy/bevy_dev_tools", "bevy/bevy_ui_debug"]
```

## Lints

### BV-BUILD-12 [M] Allow `elided_lifetimes_in_paths`, with the reason in the table

`elided_lifetimes_in_paths = "allow"` in the `[lints.rust]` table, with a comment saying why. The
compliant form exists and compiles — `Query<'_, '_, &mut Shield>` and `Res<'_, Time>` are valid
system parameters — and the comment says so, rather than letting a reader think it impossible.

**Why:** it fires on every system parameter — `Query`, `Res`, `Commands`, `MessageReader`, `Local` —
because each carries the world and state lifetimes: fourteen warnings in one five-system plugin.
The fix buys nothing but two apostrophes on every parameter of every system in the game.

**Check:** is the entry present, and does the comment beside it say that the compliant form exists?
An allow with no reason is the thing this rule exists to prevent.

### BV-BUILD-13 [M] Allow `clippy::needless_pass_by_value`, with the reason in the table

`needless_pass_by_value = "allow"` in `[lints.clippy]`, with a comment saying it has no compliant
form.

**Why:** it fires on every `Res<T>` parameter a system does not consume, and its suggestion does not
compile: `&Res<'_, T>` is not a `SystemParam`, so following it is `E0277` at `add_systems`. Bevy
makes this entry impossible rather than merely noisy, and the comment says which of the two it is.

**Check:** is the entry present? Then check nothing else from `pedantic` has been allowed alongside
it — this is the one.

### BV-BUILD-14 [M] Keep `type_complexity` and `too_many_arguments` switched on

Both fire on ordinary Bevy code — `type_complexity` on a query with two data items and two filters,
`too_many_arguments` at eight parameters. Both have a compliant form that is better code, so
neither is allowed here.

**Why:** upstream Bevy allows both, and copying that is where most allow lists start. The fixes — a
`type` alias named from the domain (BV-ECS-21) and `#[derive(SystemParam)]` (BV-SCHED-10) — answer
what a reader would also have complained about.

**Check:** grep the lint table for either name. Their presence is the defect.

### BV-BUILD-15 [M] Add nothing else to the allow list without measuring it

A third allow needs the same treatment as the first two: the code that triggers it, the count, and
whether a compliant form exists.

**Why:** an allow list dies one plausible entry at a time — `redundant_clone`, `float_cmp` and
`expect_used` are all allowed "because Bevy", and none has anything to do with Bevy. Requiring a
measurement makes the question answerable instead of arguable.

**Check:** for each entry beyond the two, name the Bevy API that forces it. If the answer is a
property of the game's own code, it is a defect list rather than a lint table.

### BV-BUILD-16 [M] Put the table in the workspace and inherit it

`[workspace.lints]` once, `[lints] workspace = true` in every member.

**Why:** the two allows are the sort of thing copied into a member that then diverges, until one
crate allows three lints and nobody notices which. Inheritance is all-or-nothing, so a member that
needs something different has to say so visibly.

**Check:** grep for `[lints.` in member manifests. Each is a member that has opted out of the shared
table. `assets/Cargo.toml` is the table, with both relaxations and their reasons already in place.

### BV-BUILD-17 [S] Run `bevy_lint`, pinned to the Bevy version

`bevy_lint` catches the Bevy-specific defects that `clippy` cannot see. It runs under its own
pinned nightly with the `rustc-dev` component — not the game's toolchain — and only in a version
whose compatibility table names the engine's. No release supports Bevy 0.19 or 0.20 (v0.6.0, the
latest, targets 0.18), so the job stays in CI, disabled, until one does.

**Why:** it is the only mechanical check for a dozen rules in this standard — markers in query data,
`main` without `AppExit`, `Messages` inserted as a resource, the `*Plugin` and `*Systems`
conventions. Each is also stated here in prose, so the standard holds without it.

**Check:** does CI run `bevy lint`, and is the nightly it installs the one the linter's
compatibility table names for this linter version? While no release supports the pinned Bevy, the
job is present and off (`if: false` in `assets/ci.yml`). `assets/rust-toolchain.toml` is the game's
toolchain and is deliberately not that nightly — a game built on nightly has no stability promise.

## CI

### BV-BUILD-18 [M] Build the feature set you ship

If the release build uses `default-features = false` and a list, CI builds that list. Building only
the default feature set proves nothing about the artefact.

**Why:** a feature-gated compile error is invisible until somebody builds that configuration, and
the configuration nobody builds locally is the shipped one. Feature-conditional code also rots
fastest, because the compiler never sees it.

**Check:** compare the feature list in the CI job with the one in the release manifest or workflow.
They should be the same string; `assets/ci.yml` has the job.

### BV-BUILD-19 [S] Build the wasm target if the game ships to the web

`cargo build --target wasm32-unknown-unknown` in CI, with the same features as the web build.

**Why:** wasm is where Bevy's platform differences concentrate — no threads unless the feature is
on, other audio and windowing backends, no filesystem, and since 0.19 a dropped `Task` cancels
rather than detaching. None of that shows on a native build, so a green desktop CI says nothing.

**Check:** is the web target in the CI matrix? If the game ships to the web and it is not, the web
build is untested.

### BV-BUILD-20 [M] Keep `assets/` out of a published package

A published crate uses `include`, not `exclude`, to list what ships. A game's asset directory is
not part of it.

**Why:** `assets/` in a Bevy project is often hundreds of megabytes and is loaded from the
filesystem at runtime, not from the crate, so packaging it inflates every download for no benefit
and can exceed the registry's size limit.

**Check:** run `cargo package --list` and look for asset paths.

### BV-BUILD-21 [S] Cache the target directory, because Bevy is most of the build

CI caches `~/.cargo` and `target/`, keyed on the lockfile.

**Why:** Bevy is by a wide margin the largest thing in the dependency graph and changes only when
the pin does, so the hit rate is nearly one and the saving nearly the whole build — the difference
between a two-minute and a fifteen-minute pipeline.

**Check:** is there a cache step keyed on `Cargo.lock`, and does the job log show a hit on a run
that changed only game code?
