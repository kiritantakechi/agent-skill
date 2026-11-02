---
name: bevy-style
description: >-
  The Bevy 0.20 engineering standard — a 218-rule delta on top of rust-style covering the ECS,
  scheduling, observers and messages, states and resources, assets, error handling, Cargo features
  and the Bevy lint divergences, the user-facing half of UI and rendering, testing, and a forbidden
  API table spanning 0.15 through 0.20. Its spine is keeping the rules of the game out of the
  engine's vocabulary, so an engine upgrade rewrites signatures and not arithmetic. Use this
  whenever writing, reviewing, refactoring, scaffolding, porting, or debugging ANY Bevy code — a
  plugin, a system, a component, a query, a schedule, an observer, a Cargo.toml with bevy in it —
  even if the user never mentions "style", "standards", or "quality". Also use when migrating a
  project to a newer Bevy, when Bevy code written for an older release must be brought up to
  date, and when deciding whether something belongs in a system or in plain Rust.
---

# Bevy Style — 0.20

A **delta on top of `rust-style`**. Everything that standard says about naming, errors, ownership,
functional style, modules, documentation and Cargo still holds; this one states what changes when
Bevy is in the dependency list, and nothing else. Section 3 lists every place the two disagree and
which one wins.

**Target: Bevy 0.20 on Rust 1.99, edition 2024.** Bevy's API turns over faster than any other
dependency a game has, and most Bevy code on the public internet — and most of what a language model
has read — is 0.15 or older. Section 2 and `references/migration.md` exist for that reason.

## How to use this standard

1. **Read section 2** before emitting Bevy code. It is the Bevy 0.20 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Load `rust-style` as well** for anything that is a Rust question rather than a Bevy question.
5. **Walk section 5** before handing back a diff.

Rules are cited by ID — `BV-ERR-03`, `BV-TEST-05`. The prefix identifies the owning chapter (section
6 maps prefix to file), so cite the ID when justifying a change and the reader can find the full
rule and its rationale. When a rule in a chapter and a rule here appear to conflict, the chapter is
the detailed statement and wins; sections 1 and 3 govern how to break a genuine tie.

Rules from the other standard keep their own prefix, so an `RS-` citation is always a pointer out of
this document.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered,
`references/migration.md` maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Bevy 0.20.1 on Rust 1.99, edition 2024, and any test it ships passes. `// fragment`
— shown in context rather than run as a unit, usually because it uses names the chapter declares
around it. `// rejected — <tool>: …` — the rejection is the point, and the marker names the tool
that rejects it: `rustc`, `clippy`, `rustdoc`. A trailing `— GOOD` or `— BAD` names which side of
the rule the block illustrates. A block in another language carries its marker in that language's
comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Bevy code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in shipped and long-running code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**Code is "shipped or long-running" — `[M!]` applies as `[M]` — if any of these hold:** players run
it; it is a plugin crate published for others to depend on; a panic ends a session someone cannot
resume (a dedicated server, a long play session, a build step); it writes save data or replays; or
it is the authority in a networked game. **Otherwise** — jam prototypes, editor scratch, example
scenes, throwaway tools — `[M!]` rules are recommendations, and the relaxed form given with each
rule is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Bevy 0.20 reality check

### 2.1 The ones that change behaviour without changing whether it compiles

1. **Setting the same state now runs the transition.** Since 0.18, `next_state.set(S)` fires
   `OnExit(S)` and `OnEnter(S)` even when the current state is already `S`. Code that called `set`
   every frame used to be free and now re-runs every setup and teardown system in the game.
   `set_if_different` is the old behaviour (`references/state.md` BV-STATE-16).
2. **Bevy maintains `Aabb`.** Since 0.18 it adds and updates the `Aabb` of meshes and sprites, so a
   system that removes or recomputes one fights the engine (`references/view.md` BV-VIEW-16).
3. **`Ref<T>` now clones the `Ref`, not the `T`.** 0.19 gave `Ref` its own `Clone` and `Copy`. A
   `value.clone()` that used to produce a `T` now produces another `Ref<T>`, and only fails to
   compile if the surrounding code was explicit about the type. Write `ref.deref().clone()` for the
   old meaning (`references/migration.md` BV-MIG-18).
4. **A resource is an entity.** Since 0.19 each resource is a component on an entity of its own, and
   nothing filters those out: `Query<Entity>`, `Query<EntityRef>` and `Query<EntityMut>` match them.
   A sweep that despawns everything it matches takes the resources with it, which Bevy warns about
   and then panics on under the default error handler; `Query<EntityMut>` beside any `Res` panics
   with B0002; and a resource type spawned on a second entity is stripped from it with only a
   warning. Filter such a query with `Without<IsResource>` (`references/state.md` BV-STATE-01).
5. **`AssetEvent::Modified` needs a real mutation.** Since 0.19 a `get_mut` that only reads raises
   none, so a reaction that relied on it stops firing (`references/assets.md` BV-ASSET-09).
6. **Bloom judges luminance in linear.** Since 0.19, a tint tuned against sRGB luminance blooms more
   than it did (`references/view.md` BV-VIEW-11).
7. **A logging error handler now swallows panics.** 0.20 hands every panic in a system, observer or
   command to the `FallbackErrorHandler`, so a release handler that logs keeps the app running past
   it — overflow traps included. Re-panic when the error carries a panic payload
   (`references/errors.md` BV-ERR-05).
8. **`iter_many` yields `Result`.** `.count()` and `for _ in` still compile, and now count ids that
   do not match the query; on the plain and unique forms `.matched()` is the old meaning
   (`references/ecs.md` BV-ECS-20).
9. **`EditableText` on its own is inert.** It spawns and ignores the keyboard. Spawn `TextInput`,
   which requires it, under `TextInputPlugin` (`references/view.md` BV-VIEW-08).
10. **The engine's own set chains are weak.** Inside `PostUpdate`'s `UiSystems` and the render
    schedules, systems with no conflict the ECS can see are no longer ordered, so one relying on
    hidden ordering can race (`references/scheduling.md` BV-SCHED-13).

`references/migration.md` keeps the same list with a search for each, under "Changes that do not
show up as a compile error".

### 2.2 Engine features that replaced what games used to hand-roll

| Reach for this | Not this | Since |
|---|---|---|
| `#[require(…)]` required components | `*Bundle` types, which are gone | 0.15 |
| `ChildOf` / `Children` relationships | `Parent`, `push_children`, `despawn_recursive` | 0.16 |
| a system returning `Result` and `?` | `unwrap()` on `Query::single` | 0.16 |
| observers and `On<E>` | polling a message every frame to react to one thing | 0.14 |
| `Message` for buffered fan-out, `Event` for reactions | calling both of them "events" | 0.17 |
| the `2d` / `3d` / `ui` feature collections | a hand-maintained list of thirty features | 0.18 |
| `bsn!` from `bevy_scene` | nested `with_children` closures | 0.19 |
| `commands.delayed()` | a `Timer` resource whose only job is to postpone a spawn | 0.19 |
| `DiagnosticsOverlayPlugin` | a hand-written FPS `Text` system | 0.19 |
| `Gizmos::text()` / `text_2d()` | spawning a `Text2d` to print a debug value | 0.19 |
| `TextInput` from `bevy_ui_widgets` | a third-party text-input crate | 0.20 |
| `#[derive(SettingsGroup)]` (`bevy_settings`) | hand-rolled settings load and save | 0.19 |
| `Query::contiguous_iter()` | hand-written structure-of-arrays for a hot loop | 0.19 |
| `.run_if(…)` on an observer | an early `return` at the top of the observer | 0.19 |
| `.context(…)` on a `Result` or `Option` | `ok_or(…)` at the system boundary | 0.20 |
| `chain_weak()`, `after_weak()` | strong ordering between systems that never conflict | 0.20 |
| `Val::Em`, `Val::Rem` | scaling a node by hand with the text size | 0.20 |

### 2.3 Names that moved, and are still written the old way everywhere

`Trigger<E>` is `On<E>`, and `On<Add, T>` is `On<Add<T>>`; `Pointer<Click>` is `PointerClick`;
`NextState::set_if_neq` is `set_if_different`; `OnAdd` is `Add`; `EventReader`/`EventWriter` are
`MessageReader`/`MessageWriter`; `Parent` is `ChildOf`; every `*Bundle` is a set of components; the
old `bevy_scene` is `bevy_world_serialization`, and `bevy_scene` is now the new scene system.
`references/migration.md` is the full table, and it is the first thing to check when porting code
written against a tutorial.

## 3. Design principles

The spine of this standard is the boundary: the rules of the game live in plain Rust that never
names Bevy, and the engine is the view and the input around them (`references/architecture.md`
BV-ARCH-01). An engine upgrade then rewrites signatures and not arithmetic. Everything else follows
`rust-style`'s principles; the departures are below, and nothing not listed there is relaxed.

### Where this standard departs from `rust-style`

Each row is a rule of the other standard that Bevy makes impossible, harmful, or merely noisy.
Nothing else is relaxed: a divergence not listed here is a defect, not a dialect.

| `rust-style` rule | What applies instead | Why Bevy forces it |
|---|---|---|
| `RS-API-15` Keep every struct field private, including the ones with no invariant | `BV-ECS-01` — component fields are public | The ECS is the accessor. Reflection, scenes, `bsn!` and the remote protocol all read fields directly, and a component cannot defend an invariant anyway. A newtype's field is public for the same reason: for a component the representation *is* the contract, so making it public gives nothing away. The exemption is paid for by `BV-ARCH-04`. |
| `RS-NAME-29` Never suffix a name with the language construct | `BV-ARCH-10` — `*Plugin` and `*Systems` | `add_plugins(X)` and `configure_sets(_, X)` are the same shape with different meanings, so the name is the only signal. Bevy addresses both by type — `is_plugin_added::<T>`, `disable::<T>` — and its own plugins and sets carry the same suffixes. |
| `RS-ERR-13` Never expose `Box<dyn Error>` or `anyhow::Error` from a library | `BV-ERR-03` — a system returns `BevyError`, the domain does not | `BevyError` is boxed and type-erased, and Bevy's `Result` alias is exactly the aliased form the rule names. Its rationale does not reach here: a system has no caller to match on the error — the schedule hands it to the error handler. Everything a caller could branch on stays a real type on the domain side. |
| `RS-BUILD-25` Never blanket-`allow` at crate level to make CI green | `BV-BUILD-12` — `elided_lifetimes_in_paths` is allowed | It fires on every `Query`, `Res`, `ResMut`, `Commands`, `MessageReader` and `Local` parameter. Writing the `'_`s does satisfy it, and buys nothing but noise. |
| `RS-BUILD-22` Turn off default features on heavy dependencies | `BV-BUILD-02` — start from a feature collection | Bevy's feature graph has 177 entries in 0.20 and moves every release; a hand-picked list goes stale silently, as an unmeasured one always does. |
| `RS-FUNC-03` A `for` loop that only pushes is a `collect` | `BV-ECS-18` — a loop that writes through a query is a `for` | Only the loop that writes: a write through `Mut<T>` is effect, not transformation, so there is nothing to collect. A read-only pass over a query that only pushes is a `collect` here too. |
| `RS-API-54` Decide `#[non_exhaustive]` for every public enum and struct | `BV-ECS-05` — components are exhaustive | Struct-literal construction is how components are spawned, and `#[non_exhaustive]` forbids it outside the defining crate. Required components are the growth mechanism instead. |

Two rows that look like they belong here and do not. `RS-BUILD-24` asks for `pedantic` at warn and
allows "individual lints with a comment giving the reason" — which is exactly what `BV-BUILD-13`
does, so allowing `needless_pass_by_value` with its reason obeys that rule rather than overriding
it. And `RS-BUILD-21` is titled "never pin exact versions *in a library*"; `BV-BUILD-04` pins in a
game binary and keeps the caret for anything published, so the two never meet.

`clippy::wildcard_imports` is not on this list either: it exempts preludes, and
`use bevy::prelude::*` is a prelude. It is the first line of nearly every Bevy file, and naming
twenty imports instead would be worse.

`RS-NAME-02` is **not** on this list, and the temptation is real: Bevy's own packages are
`bevy_ecs`, `bevy_render`, spelled with underscores. That is upstream's namespace, not a licence to
name your own crates `mygame_combat` — packages published from this standard use hyphens
(`BV-ARCH-08`).

## 4. Core rules

These 24 `BV-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### The boundary

- **BV-CORE-01 `[M]`** The code that decides what happens takes and returns plain Rust data.
  `Query`, `Commands`, `Res` and `Entity` belong to the code that decides when it happens. An engine
  upgrade should rewrite signatures, not arithmetic (`references/architecture.md` BV-ARCH-01).
- **BV-CORE-02 `[M]`** The separation is mandatory at every project size; only its mechanism scales
  — modules for one binary, crates for a workspace — and whichever it is, a CI job enforces it
  rather than a paragraph (`references/architecture.md` BV-ARCH-02 and BV-ARCH-07).
- **BV-CORE-03 `[M]`** Data that must satisfy a condition cannot be defended inside a component.
  Model the condition as a domain type with a private field and a fallible constructor, let the
  component carry the plain value, and construct the domain type at the one crossing point — which
  is then the only place that field is read (`references/architecture.md` BV-ARCH-04, BV-ARCH-03).
- **BV-CORE-04 `[M]`** Every plugin is a type implementing `Plugin`, named `*Plugin`, and never a
  function or a closure: four of Bevy's own APIs address a plugin by its type, and a function's type
  cannot be written. `main` adds plugins and installs the two error policies, and nothing else
  (`references/architecture.md` BV-ARCH-09, BV-ARCH-10, BV-ARCH-15).

### Components and queries

- **BV-CORE-05 `[M]`** A component is one fact about an entity. Two fields that change at different
  times, are written by different systems, or are read by different queries are two components
  (`references/ecs.md` BV-ECS-02).
- **BV-CORE-06 `[M]`** Express "an X always has a Y" with `#[require(Y)]`, never with a hand-kept
  tuple that callers must remember. The `*Bundle` types are gone, and writing your own is the same
  defect wearing a new name (`references/ecs.md` BV-ECS-06).
- **BV-CORE-07 `[M]`** A zero-sized marker goes in `With<T>` or `Without<T>`, never in the query's
  data. Querying it fetches nothing and costs a column (`references/ecs.md` BV-ECS-16).
- **BV-CORE-08 `[M!]`** Writing through `Mut<T>` marks the component changed whether or not the
  value differs. Anything a `Changed<T>` filter watches is written with `set_if_neq`
  (`references/ecs.md` BV-ECS-24).
- **BV-CORE-09 `[M]`** Name a query type with a `type` alias once it needs two lines, and group a
  system's parameters with `#[derive(SystemParam)]` once `too_many_arguments` fires at eight
  (`references/ecs.md` BV-ECS-19, `references/scheduling.md` BV-SCHED-09).
- **BV-CORE-10 `[M]`** Every component derives `Reflect` and carries `#[reflect(Component)]`. The
  derive registers it — through `reflect_auto_register`, which `default_app` and the `2d`, `3d` and
  `ui` collections enable — so only a generic instantiation needs `register_type`. Reflection is
  what the inspector, the scene format and the remote protocol run on, and it is opt-in per type, so
  it is forgotten silently (`references/ecs.md` BV-ECS-03, BV-ECS-12).

### Scheduling

- **BV-CORE-11 `[M]`** Simulation runs in `FixedUpdate`; animation, camera and anything that must be
  smooth run in `Update`. A camera moved from `FixedUpdate` visibly stutters, and per-frame input
  read from it is dropped on a fast machine and doubled on a slow one (`references/scheduling.md`
  BV-SCHED-01, BV-SCHED-08).
- **BV-CORE-12 `[M!]`** Ordering between systems goes through named `SystemSet`s configured once,
  not a chain of `.before()` and `.after()` at each `add_systems` call (`references/scheduling.md`
  BV-SCHED-11).
- **BV-CORE-13 `[M]`** A system that should not always run says so with `.run_if(…)`. An early
  `return` hides the condition from the schedule, which cannot then skip the system or report it
  (`references/scheduling.md` BV-SCHED-15).
- **BV-CORE-14 `[M]`** Take the delta from `Res<Time>`, which is the frame clock in `Update` and the
  fixed clock inside `FixedUpdate`; naming `Res<Time<Fixed>>` instead trades that portability for
  clarity, deliberately. Never hard-code a per-frame delta (`references/scheduling.md` BV-SCHED-05).

### Events, messages, observers

- **BV-CORE-15 `[M]`** `Message` is buffered fan-out read next frame; `Event` is a reaction that
  runs now. They are different traits for different jobs, and a type deriving both is almost always
  a design that has not chosen (`references/events.md` BV-EVENT-01, BV-EVENT-03).
- **BV-CORE-16 `[M]`** An event that concerns one entity derives `EntityEvent` and carries the
  entity as a field, read by that field's name. `trigger_targets` is gone (`references/events.md`
  BV-EVENT-09, BV-EVENT-10).
- **BV-CORE-17 `[M]`** Register a `Message` type with `app.add_message::<M>()`. Inserting
  `Messages<M>` as a resource yourself leaks, because nothing then drops old messages
  (`references/events.md` BV-EVENT-04).

### Errors

- **BV-CORE-18 `[M!]`** A system that can fail returns `Result` and uses `?`. No `unwrap`, no
  `expect`, no indexing on a path a player can reach (`references/errors.md` BV-ERR-01, and its
  `indexing_slicing` row).
- **BV-CORE-19 `[M]`** Install the fallback error handler explicitly, with `App::set_error_handler`
  in `main`. It also receives panics, so a release handler that logs must re-panic when the error
  carries a panic payload, or every panic becomes a log line (`references/errors.md` BV-ERR-05).
- **BV-CORE-20 `[M]`** Prefer the non-panicking half of every pair: `get_resource` over `resource`,
  `get` over `entity`, `Single` or `single()?` over `single().unwrap()` (`references/errors.md`
  BV-ERR-07).
- **BV-CORE-21 `[M]`** `fn main() -> AppExit`, returning what `App::run` returned. Anything else
  reports a crash as a clean exit (`references/architecture.md` BV-ARCH-16).

### Cargo and versions

- **BV-CORE-22 `[M]`** Pin Bevy exactly in a game binary and use a caret in a published crate. A
  minor bump is a scheduled migration, not something `cargo update` does to you
  (`references/build.md` BV-BUILD-04).
- **BV-CORE-23 `[M]`** Start from a feature collection — `2d`, `3d`, `ui` — and hand-pick features
  only against a measurement recorded in the manifest (`references/build.md` BV-BUILD-02 and
  BV-BUILD-03).
- **BV-CORE-24 `[M]`** Two entries of `rust-style`'s lint table are relaxed for Bevy code and no
  others: `elided_lifetimes_in_paths` and `clippy::needless_pass_by_value`. `type_complexity` and
  `too_many_arguments` stay on, because both have a compliant form that is better code
  (`references/build.md` BV-BUILD-12, BV-BUILD-13 and BV-BUILD-14).

## 5. Review checklist

When reviewing or self-reviewing a Bevy diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **The boundary.** Does anything outside the view layer name Bevy? (BV-ARCH-01)
2. **Stale APIs.** Is every API a 0.20 API — no `Trigger`, `EventReader`, `Parent`, `*Bundle`,
   `Pointer<Click>` or `On<Add, T>`? (BV-MIG-01)
3. **Errors and panics.** Does every fallible system return `Result`, and does the release error
   handler still end the app on a caught panic? (BV-ERR-01, BV-ERR-05)
4. **Change detection.** Is any `Changed<T>` watching something written unconditionally? (BV-ECS-24)
5. **Ordering.** Is ordering expressed in sets, not against a system function? (BV-SCHED-11)
6. **Run conditions and state.** Would each new system be skipped when it should be? (BV-SCHED-15,
   BV-STATE-14)
7. **Reflection.** Does each new component derive `Reflect`, and is each generic instantiation
   registered? (BV-ECS-03, BV-ECS-12)
8. **Tests.** Is the rule tested without an `App`, and the plugin with the smallest one?
   (BV-ARCH-01, BV-TEST-02)
9. **Relaxed forms.** Is anything `[M!]` relying on its relaxed form, and which shipped-code
   condition does not hold?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 24
`BV-CORE-*` rules live in section 4 above; the other 194 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/architecture.md` | `BV-ARCH` (17) | The boundary between the game and the engine, the shape of a plugin and what it registers, and the `App` and its binary |
| `references/ecs.md` | `BV-ECS` (30) | Components and required components, queries and filters, change detection, relationships, and reflection |
| `references/scheduling.md` | `BV-SCHED` (23) | Schedules and the fixed timestep, system sets and ordering, run conditions, time, and input |
| `references/events.md` | `BV-EVENT` (19) | Messages, events and entity events, observers and propagation, and the lifecycle events |
| `references/state.md` | `BV-STATE` (18) | Resources, `States` and their transitions, and what a state scopes |
| `references/errors.md` | `BV-ERR` (11) | Fallible systems, observers and commands, the fallback error handler, and the APIs that panic |
| `references/assets.md` | `BV-ASSET` (11) | Handles and loading, hot reload, asset events, and asset lifetime |
| `references/build.md` | `BV-BUILD` (16) | Feature collections, the exact Bevy pin, the lint divergences from rust-style, and CI |
| `references/migration.md` | `BV-MIG` (18) | Every API forbidden since 0.15 and what replaces it, and the changes that still compile |
| `references/view.md` | `BV-VIEW` (21) | UI nodes and layout, text, cameras, materials and shaders, post-processing, and gizmos |
| `references/testing.md` | `BV-TEST` (10) | Headless apps, deterministic fixed steps, and what a test asserts |
| `references/review-checklist.md` | — | The audit protocol: the shared seven-level severity model, review order, mechanical pass, output format, and the order in which to refactor an existing game |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/Cargo.toml` | The workspace manifest for a game: an exact Bevy pin with a feature collection, the lint table with its two Bevy relaxations and their reasons, and the profiles that keep debug builds playable |
| `assets/clippy.toml` | clippy's own settings: `unwrap` and `expect` allowed inside tests, the relaxed form BV-ERR-01 states, as `rust-style`'s are |
| `assets/ci.yml` | The workflow: the boundary and one-Bevy checks, clippy and tests under deny-warnings, docs, the weekly advisory audit, the MSRV job and the release build |
| `assets/rust-toolchain.toml` | The pinned stable toolchain the game builds with |
