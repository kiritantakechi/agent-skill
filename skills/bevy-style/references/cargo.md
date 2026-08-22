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
  - BV-CAR-01 [M] Depend on the `bevy` facade, not on its subcrates
  - BV-CAR-02 [M] Start from a feature collection
  - BV-CAR-03 [M] Hand-pick features only against a recorded measurement
  - BV-CAR-04 [M] Pin Bevy exactly in a binary and with a caret in a library
  - BV-CAR-05 [M] Keep every ecosystem crate on one Bevy version
  - BV-CAR-06 [S] Check a plugin crate's compatibility table before adding it

- **Profiles**
  - BV-CAR-07 [M] Compile dependencies optimised in the dev profile
  - BV-CAR-08 [S] Keep `dynamic_linking` off the committed manifest
  - BV-CAR-09 [M!] Keep `overflow-checks` on in release where release must match debug
  - BV-CAR-10 [M] Keep tracing and dev tooling behind off-by-default features

- **Lints**
  - BV-CAR-11 [M] Allow `elided_lifetimes_in_paths`, with the reason in the table
  - BV-CAR-12 [M] Allow `clippy::needless_pass_by_value`, with the reason in the table
  - BV-CAR-13 [M] Keep `type_complexity` and `too_many_arguments` switched on
  - BV-CAR-14 [M] Add nothing else to the allow list without measuring it
  - BV-CAR-15 [M] Put the table in the workspace and inherit it
  - BV-CAR-16 [S] Run `bevy_lint`, pinned to the Bevy version

- **CI**
  - BV-CAR-17 [M] Build the feature set you ship
  - BV-CAR-18 [S] Build the wasm target if the game ships to the web
  - BV-CAR-19 [M] Keep `assets/` out of a published package
  - BV-CAR-20 [S] Cache the target directory, because Bevy is most of the build

---

## The dependency

### BV-CAR-01 [M] Depend on the `bevy` facade, not on its subcrates

`bevy = { version = …, features = […] }`. Not a list of `bevy_ecs`, `bevy_render`, `bevy_ui`.

**Why:** the facade's feature graph is what upstream tests and documents, and the subcrate split
moves between releases — 0.19 alone inverted the `bevy_gltf`/`bevy_pbr` dependency, moved `Hdr` into
`bevy_camera`, moved transmission into `bevy_pbr` and created `bevy_material`. A manifest naming
subcrates has to be rewritten for each of those; one naming the facade does not. The exception is a
crate that genuinely needs one subcrate and no engine — and by BV-ARC-06 that crate should not be
depending on Bevy at all.

**Check:** grep the manifests for `bevy_`. Each hit is either a third-party plugin crate or a
subcrate dependency that needs a reason.

### BV-CAR-02 [M] Start from a feature collection

`default-features = false` plus `features = ["2d"]`, `["3d", "ui"]`, or the mid-level `2d_api` /
`default_app` / `default_platform` where the backends are not wanted. Not thirty individual names —
and not a collection *without* `default-features = false`, which selects nothing: `default` is
already `["2d", "3d", "ui", "audio"]`.

**Why:** the collections landed in 0.18 precisely because hand-maintained lists rot: a feature gets
renamed (`animation` became `gltf_animation`, `bevy_sprite_picking_backend` became
`sprite_picking`), a new one becomes necessary, and the manifest keeps compiling while quietly
enabling something different from what it says. Bevy has 172 features in 0.19; nobody re-reads that
list every release.

**Check:** is `default-features = false` there? Without it the list is decoration. Then count the
entries: past about six, they are describing a collection that already exists.
`assets/Cargo.toml` is a workspace manifest with the collection already chosen.

### BV-CAR-03 [M] Hand-pick features only against a recorded measurement

A hand-picked list is allowed when there is a build-time, binary-size or dependency-count target,
the measurement is in the manifest as a comment, and each feature says why it is there.

**Why:** the trade is real — a hand-picked 2-D list is meaningfully smaller than the `2d` collection
— and it is only worth its maintenance cost if somebody knows how much smaller. Without the number,
the list is an assumption that gets defended forever; with it, the next release can re-measure and
decide again.

**Check:** does the manifest state the number the list buys, and the date or version it was measured
against? If not, switch to a collection until someone measures.

```toml
# fragment — a hand-picked list that has earned itself, with the number in it
[dependencies]
# 272 crates here against 330 with the `2d` collection, measured against 0.19.1.
# Each entry says why; anything unexplained goes back to the collection.
bevy = { version = "=0.19.1", default-features = false, features = [
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

### BV-CAR-04 [M] Pin Bevy exactly in a binary and with a caret in a library

A game binary writes `bevy = "=0.19.1"`. A crate other people depend on writes `bevy = "0.19"`.

**Why:** a Bevy minor bump renames a large fraction of the API, so for a binary an exact pin turns
an upgrade into a scheduled migration rather than something `cargo update` does on a Tuesday. For a
library the same pin is harmful: it forbids downstream from using any other patch release, and two
libraries pinned to different patches cannot be used together. The general rule against exact pins
is unchanged for anything published.

**Check:** is the crate a `[[bin]]` or a `[lib]` others depend on? Exact pin for the first, caret
for the second, and the reason for the pin as a comment beside it.

### BV-CAR-05 [M] Keep every ecosystem crate on one Bevy version

`cargo tree --duplicates` shows nothing named `bevy`. Two versions in the tree are two engines.

**Why:** the crates are named the same and the types are not: a `Handle<Image>` from 0.18 does not
satisfy a parameter expecting 0.19's, and the error message shows two identical type names and no
explanation. It also doubles the compile time of the largest dependency in the project.
`bevy_lint`'s `duplicate_bevy_dependencies` reports it.

**Check:** run `cargo tree --duplicates | grep bevy` in CI. Any output fails the build.

### BV-CAR-06 [S] Check a plugin crate's compatibility table before adding it

Most Bevy ecosystem crates publish a table of which of their versions works with which Bevy. Read it
before adding the dependency, not after the type errors.

**Why:** the ecosystem lags the engine by weeks to months, so at any moment some crates support the
current Bevy and some do not — and a crate that has not caught up will resolve, compile its own
half, and fail with the duplicate-version errors from BV-CAR-05. Reading the table first turns that
into a decision about whether to wait.

**Check:** for each Bevy plugin dependency, is the version the one its table names for this engine
version?

## Profiles

### BV-CAR-07 [M] Compile dependencies optimised in the dev profile

`[profile.dev.package."*"] opt-level = 3`, with the game's own crates left at the dev default.

**Why:** an unoptimised Bevy is slow enough that frame rate stops being a signal about the game at
all, so every performance judgement made in development is about the wrong build. The engine is
compiled once and then cached, so the cost is paid on the first build and never again. The game's
own crates stay unoptimised so that the edit-compile-run loop stays fast, which is the whole point
of the dev profile.

**Check:** does the workspace manifest have the `[profile.dev.package."*"]` block? Without it,
everything anyone says about the game's performance in development is about the wrong build.

### BV-CAR-08 [S] Keep `dynamic_linking` off the committed manifest

`bevy/dynamic_linking` cuts link time substantially and produces a binary that will not run on
another machine. Turn it on with `--features bevy/dynamic_linking` on the command line.

**Why:** the feature makes the build depend on a shared object beside the executable, so a binary
built with it is not distributable and a CI artefact built with it is broken in a way that only
shows up when somebody runs it. As a command-line flag it is a developer's local choice; in the
manifest it is everybody's.

**Check:** grep the manifest for `dynamic_linking`. It belongs in a shell alias or a
`.cargo/config.toml` that is not committed.

### BV-CAR-09 [M!] Keep `overflow-checks` on in release where release must match debug

`[profile.release] overflow-checks = true` for any game with replays, rollback, lockstep networking
or golden test vectors.

*Relaxed form:* a single-player game with no recorded state may take the default, and then the rule
is that nothing compares a release run against a debug one.

**Why:** integer overflow panics in debug and wraps in release, so without this the two builds
genuinely compute different numbers — a replay recorded in development desynchronises when played
back by a player, and the bug is invisible in every test. The cost is a bounds-check-sized slowdown
on integer arithmetic, which for a simulation is far below the cost of the desync.

**Check:** does the game record or transmit anything that another run has to reproduce? If so, the
line is mandatory.

### BV-CAR-10 [M] Keep tracing and dev tooling behind off-by-default features

`bevy/trace`, `bevy/detailed_trace`, the remote protocol, an in-game inspector and a debug overlay
all go behind a feature that is off by default.

**Why:** each of them costs something a player should not pay: `detailed_trace` instruments the hot
loops, and the remote protocol opens a TCP listener on localhost, which has no business in a shipped
build. Off by default also means the shipped configuration is the one that is built by accident,
which is the right way round.

**Check:** grep the default feature list. Anything whose name mentions trace, debug, remote,
inspector or editor is on by default and should not be.

## Lints

### BV-CAR-11 [M] Allow `elided_lifetimes_in_paths`, with the reason in the table

`elided_lifetimes_in_paths = "allow"` in the `[lints.rust]` table, with a comment saying why.

**Why:** it fires on every single system parameter — `Query`, `Res`, `ResMut`, `Commands`,
`MessageReader`, `Local` — because each carries the world and state lifetimes. In one five-system
plugin that is fourteen warnings. The compliant form does exist and does compile:
`Query<'_, '_, &mut Shield>` and `Res<'_, Time>` are valid system parameters. It buys nothing but
two apostrophes on every parameter of every system in the game, so this standard takes the allow —
and says so, rather than letting a reader think it was impossible.

**Check:** is the entry present, and does the comment beside it say that the compliant form exists?
An allow with no reason is the thing this rule exists to prevent.

### BV-CAR-12 [M] Allow `clippy::needless_pass_by_value`, with the reason in the table

`needless_pass_by_value = "allow"` in `[lints.clippy]`, with a comment saying it has no compliant
form.

**Why:** it fires on every `Res<T>` parameter a system does not consume, and its suggestion does not
compile: `&Res<'_, T>` is not a `SystemParam`, so following the lint produces `E0277` at the
`add_systems` call. This is the one entry of the other standard's table that Bevy makes genuinely
impossible rather than merely noisy, and the comment should say which of the two it is.

**Check:** is the entry present? Then check nothing else from `pedantic` has been allowed alongside
it — this is the one.

### BV-CAR-13 [M] Keep `type_complexity` and `too_many_arguments` switched on

Both fire on ordinary Bevy code. Both have a compliant form that is better code, so neither is
allowed here.

**Why:** upstream Bevy allows both, and copying that is where most projects' allow lists start.
`type_complexity` fires on a query with two data items and two filters, and the fix is a `type`
alias with a name from the domain (BV-ECS-21). `too_many_arguments` fires at eight parameters, and
the fix is `#[derive(SystemParam)]` (BV-SCH-09). In both cases the lint is pointing at something a
reader would also have complained about.

**Check:** grep the lint table for either name. Their presence is the defect.

### BV-CAR-14 [M] Add nothing else to the allow list without measuring it

A third allow needs the same treatment as the first two: the code that triggers it, the count, and
whether a compliant form exists.

**Why:** an allow list is where a standard goes to die, and it dies one plausible entry at a time —
`redundant_clone`, `float_cmp`, `expect_used` and `unnecessary_wraps` are all things people allow
"because Bevy", and none of them has anything to do with Bevy. Requiring a measurement makes the
question answerable instead of arguable.

**Check:** for each entry beyond the two, name the Bevy API that forces it. If the answer is a
property of the game's own code, it is a defect list rather than a lint table.

### BV-CAR-15 [M] Put the table in the workspace and inherit it

`[workspace.lints]` once, `[lints] workspace = true` in every member.

**Why:** it is the general rule, and it matters more here because the two allows are the sort of
thing that gets copied into a member and then diverges — one crate ends up allowing three lints and
nobody notices which. Inheritance is also all-or-nothing, which is a feature: a member that needs
something different has to say so visibly.

**Check:** grep for `[lints.` in member manifests. Each is a member that has opted out of the shared
table. `assets/Cargo.toml` is the table, with both relaxations and their reasons already in place.

### BV-CAR-16 [S] Run `bevy_lint`, pinned to the Bevy version

`bevy_lint` catches the Bevy-specific defects that `clippy` cannot see. It runs under its own
pinned nightly with the `rustc-dev` component — not the game's toolchain — and its version tracks
the engine's.

**Why:** it is the only mechanical check for a dozen rules in this standard — markers in query data,
`&mut Commands` parameters, `main` without `AppExit`, `Messages` inserted as a resource,
`iter_current_update_messages`, the `*Plugin` and `*Systems` conventions, and duplicate Bevy
versions. Everything it checks is also stated here in prose, so the standard holds without it; with
it, a machine checks a dozen of the rules for free.

**Check:** does CI run `bevy lint`, and is the nightly it installs the one the linter's
compatibility table names for this linter version? `assets/rust-toolchain.toml` is the game's
toolchain and is deliberately not that nightly — a game built on nightly has no stability promise.

## CI

### BV-CAR-17 [M] Build the feature set you ship

If the release build uses `default-features = false` and a list, CI builds that list. Building only
the default feature set proves nothing about the artefact.

**Why:** a feature-gated compile error is invisible until somebody builds that configuration, and
the configuration nobody builds locally is the shipped one. Feature-conditional code also rots
fastest, because the compiler never sees it.

**Check:** compare the feature list in the CI job with the one in the release manifest or workflow.
They should be the same string; `assets/ci.yml` has the job.

### BV-CAR-18 [S] Build the wasm target if the game ships to the web

`cargo build --target wasm32-unknown-unknown` in CI, with the same features as the web build.

**Why:** wasm is where Bevy's platform differences concentrate — no threads unless the feature is
on, different audio and windowing backends, no filesystem, and in 0.19 a dropped `Task` cancels
rather than detaching. None of that appears on a native build, so a green CI on desktop says nothing
about whether the web build works.

**Check:** is the web target in the CI matrix? If the game ships to the web and it is not, the web
build is untested.

### BV-CAR-19 [M] Keep `assets/` out of a published package

A published crate uses `include` to list what ships. A game's asset directory is not part of it.

**Why:** `assets/` in a Bevy project is often hundreds of megabytes and is loaded from the
filesystem at runtime rather than from the crate, so packaging it inflates every download of the
crate for no benefit and can exceed the registry's size limit. The general rule is to use `include`
rather than `exclude`; this is the case where forgetting is expensive.

**Check:** run `cargo package --list` and look for asset paths.

### BV-CAR-20 [S] Cache the target directory, because Bevy is most of the build

CI caches `~/.cargo` and `target/`, keyed on the lockfile.

**Why:** Bevy is by a wide margin the largest thing in the dependency graph, and it changes only
when the pin changes — so the cache hit rate is nearly one and the saving is nearly the whole build.
This is the general advice, and the ratio here is extreme enough that skipping it is the difference
between a two-minute and a fifteen-minute pipeline.

**Check:** is there a cache step keyed on `Cargo.lock`, and does the job log show a hit on a run
that changed only game code?
