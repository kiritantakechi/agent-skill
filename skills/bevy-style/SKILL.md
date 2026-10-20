---
name: bevy-style
description: >-
  The Bevy 0.19 engineering standard — a 249-rule delta on top of rust-style covering the ECS,
  scheduling, observers and messages, states and resources, assets, error handling, Cargo features
  and the Bevy lint divergences, the user-facing half of UI and rendering, testing, and a forbidden
  API table spanning 0.15 through 0.19. Its spine is keeping the rules of the game out of the
  engine's vocabulary, so an engine upgrade rewrites signatures and not arithmetic. Use this
  whenever writing, reviewing, refactoring, scaffolding, porting, or debugging ANY Bevy code — a
  plugin, a system, a component, a query, a schedule, an observer, a Cargo.toml with bevy in it —
  even if the user never mentions "style" or "standards". Also use when migrating a project to a
  newer Bevy, when Bevy code written for an older release must be brought up to date, and when
  deciding whether something belongs in a system or in plain Rust.
---

# Bevy Style — 0.20

A **delta on top of `rust-style`**. Everything that standard says about naming, errors, ownership,
functional style, modules, documentation and Cargo still holds; this one states what changes when
Bevy is in the dependency list, and nothing else. Section 3 lists every place the two disagree and
which one wins.

**Target: Bevy 0.20 on Rust 1.99, edition 2024.** Bevy's API turns over faster
than any other dependency a game has, and most Bevy code on the public internet — and most of what
a language model has read — is 0.15 or older. Section 2 and `references/migration.md` exist for
that reason.

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

Rules from the other standard keep their own prefix, so an `RS-` citation is always a pointer out
of this document.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint, the level the shipped configuration sets it at, and what it forbids. Those are not rules — the
tool enforces them, so they carry no Why and no Check. When rules are renumbered,
`references/migration.md` maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Bevy 0.20.0 on Rust 1.99, edition 2024, and any test it ships passes. `// fragment`
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

### 2.1 The three that change behaviour without changing whether it compiles

1. **Setting the same state now runs the transition.** Since 0.18, `next_state.set(S)` fires
   `OnExit(S)` and `OnEnter(S)` even when the current state is already `S`. Code that called `set`
   every frame used to be free and now re-runs every setup and teardown system in the game.
   `set_if_neq` is the old behaviour (`references/state.md` BV-STATE-20).
2. **`Ref<T>` now clones the `Ref`, not the `T`.** 0.19 gave `Ref` its own `Clone` and `Copy`. A
   `value.clone()` that used to produce a `T` now produces another `Ref<T>`, and only fails to
   compile if the surrounding code was explicit about the type. Write `ref.deref().clone()` for the
   old meaning (`references/migration.md` BV-MIG-18).
3. **`Resource` is a `Component`.** In 0.19, `#[derive(Resource)]` also implements `Component`. A
   type used as both is now impossible; worse, inserting one as a component despawns the copy on
   any other entity, and resources appear in `&T` queries. Split the type
   (`references/state.md` BV-STATE-01).

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
| `EditableText` | a third-party text-input crate | 0.19 |
| `#[derive(SettingsGroup)]` (`bevy_settings`) | hand-rolled settings load and save | 0.19 |
| `Query::contiguous_iter()` | hand-written structure-of-arrays for a hot loop | 0.19 |
| `.run_if(…)` on an observer | an early `return` at the top of the observer | 0.19 |

### 2.3 Names that moved, and are still written the old way everywhere

`Trigger<E>` is `On<E>`; `OnAdd` is `Add`; `EventReader`/`EventWriter` are
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
| `RS-API-24` Keep every struct field private, including the ones with no invariant | `BV-ECS-01` — component fields are public | The ECS is the accessor. Reflection, scenes, `bsn!` and the remote protocol all read fields directly, and a component cannot defend an invariant anyway. The exemption is paid for by `BV-ARCH-04`. |
| `RS-API-26` Keep tuple-struct fields private too | `BV-ECS-01` — a component newtype is `pub` too | The newtype's `pub` normally spends the freedom to change the representation. For a component the representation *is* the contract: reflection, scenes and the remote protocol all address the field by name, so there is no freedom left to spend. |
| `RS-NAME-33` Never suffix a name with the language construct | `BV-ARCH-10` — `*Plugin` and `*Systems` | `add_plugins(X)` and `configure_sets(_, X)` are the same shape with different meanings, so the name is the only signal. Bevy addresses both by type — `is_plugin_added::<T>`, `disable::<T>` — and `bevy_lint` enforces the suffix ecosystem-wide. |
| `RS-ERR-13` Never expose `Box<dyn Error>` or `anyhow::Error` from a library | `BV-ERR-03` — a system returns `BevyError`, the domain does not | `BevyError` is boxed and type-erased, and Bevy's `Result` alias is exactly the aliased form the rule names. Its rationale does not reach here: a system has no caller to match on the error — the schedule hands it to the error handler. Everything a caller could branch on stays a real type on the domain side. |
| `RS-BUILD-27` Never blanket-`allow` at crate level to make CI green | `BV-BUILD-12` — `elided_lifetimes_in_paths` is allowed | It fires on every `Query`, `Res`, `ResMut`, `Commands`, `MessageReader` and `Local` parameter. Writing the `'_`s does satisfy it, and buys nothing but noise. |
| `RS-BUILD-24` Turn off default features on heavy dependencies | `BV-BUILD-02` — start from a feature collection | Bevy's feature graph has 172 entries and moves every release; a hand-picked list goes stale silently, as an unmeasured one always does. |
| `RS-FUNC-03` A `for` loop that only pushes is a `collect` | `BV-ECS-20` — iterate a query with `for` | Query iteration is effect, not transformation: the loop writes through `Mut<T>` and the borrow does not survive a collect. |
| `RS-API-71` Use `#[non_exhaustive]` where the shape may grow | `BV-ECS-05` — components are exhaustive | Struct-literal construction is how components are spawned, and `#[non_exhaustive]` forbids it outside the defining crate. Required components are the growth mechanism instead. |

Two rows that look like they belong here and do not. `RS-BUILD-26` asks for `pedantic` at warn and
allows "individual lints with a comment giving the reason" — which is exactly what `BV-BUILD-13`
does, so allowing `needless_pass_by_value` with its reason obeys that rule rather than overriding
it. And `RS-BUILD-23` is titled "never pin exact versions *in a library*"; `BV-BUILD-04` pins in a
game binary and keeps the caret for anything published, so the two never meet.

`RS-MOD-44` is not on this list either: it forbids glob imports "outside tests and preludes", and
`use bevy::prelude::*` is a prelude. It is the first line of nearly every Bevy file, and naming
twenty imports instead would be worse.

`RS-NAME-03` is **not** on this list, and the temptation is real: Bevy's own packages are
`bevy_ecs`, `bevy_render`, spelled with underscores. That is upstream's namespace, not a licence to
name your own crates `mygame_combat` — packages published from this standard use hyphens
(`BV-ARCH-08`).

## 4. Core rules

These 24 `BV-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### The boundary

- **BV-CORE-01 `[M]`** The code that decides what happens takes and returns plain Rust data.
  `Query`, `Commands`, `Res` and `Entity` belong to the code that decides when it happens. An
  engine upgrade should rewrite signatures, not arithmetic
  (`references/architecture.md` BV-ARCH-01).
- **BV-CORE-02 `[M]`** The separation is mandatory at every project size; only its mechanism scales
  — modules for one binary, crates for a workspace — and whichever it is, a CI job enforces it
  rather than a paragraph (`references/architecture.md` BV-ARCH-02 and BV-ARCH-07).
- **BV-CORE-03 `[M]`** Data that must satisfy a condition cannot be defended inside a component.
  Model the condition as a domain type with a private field and a fallible constructor, let the
  component carry the plain value, and construct the domain type at the one crossing point — which
  is then the only place that field is read
  (`references/architecture.md` BV-ARCH-04, BV-ARCH-03).
- **BV-CORE-04 `[M]`** Every plugin is a type implementing `Plugin`, named `*Plugin`, and never a
  function or a closure: four of Bevy's own APIs address a plugin by its type, and a function's type
  cannot be written. `main` adds plugins and nothing else
  (`references/architecture.md` BV-ARCH-09, BV-ARCH-10, BV-ARCH-16).

### Components and queries

- **BV-CORE-05 `[M]`** A component is one fact about an entity. Two fields that change at different
  times, are written by different systems, or are read by different queries are two components
  (`references/ecs.md` BV-ECS-02).
- **BV-CORE-06 `[M]`** Express "an X always has a Y" with `#[require(Y)]`, never with a hand-kept
  tuple that callers must remember. The `*Bundle` types are gone, and writing your own is the same
  defect wearing a new name (`references/ecs.md` BV-ECS-06, BV-ECS-08).
- **BV-CORE-07 `[M]`** A zero-sized marker goes in `With<T>` or `Without<T>`, never in the query's
  data. Querying it fetches nothing and costs a column
  (`references/ecs.md` BV-ECS-17).
- **BV-CORE-08 `[M!]`** Writing through `Mut<T>` marks the component changed whether or not the
  value differs. Anything a `Changed<T>` filter watches is written with `set_if_neq`
  (`references/ecs.md` BV-ECS-26).
- **BV-CORE-09 `[M]`** Give a query type more than one data item and more than one filter and it
  becomes unreadable; name it with a `type` alias. Give a system more than seven parameters and
  group them with `#[derive(SystemParam)]`
  (`references/ecs.md` BV-ECS-21, `references/scheduling.md` BV-SCHED-10).
- **BV-CORE-10 `[M]`** Every component derives `Reflect` and carries `#[reflect(Component)]`;
  every reflected type is then registered, unless `reflect_auto_register` is doing it. Reflection is
  what the inspector, the scene format and the remote protocol run on, and it is opt-in, so it is
  forgotten silently (`references/ecs.md` BV-ECS-03, BV-ECS-13).

### Scheduling

- **BV-CORE-11 `[M]`** Simulation runs in `FixedUpdate`; animation, camera and anything that must
  be smooth run in `Update`. A camera moved from `FixedUpdate` visibly stutters, and per-frame input
  read from it is dropped on a fast machine and doubled on a slow one
  (`references/scheduling.md` BV-SCHED-01, BV-SCHED-04, BV-SCHED-09).
- **BV-CORE-12 `[M!]`** Ordering between systems goes through named `SystemSet`s configured once,
  not a chain of `.before()` and `.after()` at each `add_systems` call
  (`references/scheduling.md` BV-SCHED-12).
- **BV-CORE-13 `[M]`** A system that should not always run says so with `.run_if(…)`. An early
  `return` hides the condition from the schedule, which cannot then skip the system or report it
  (`references/scheduling.md` BV-SCHED-17).
- **BV-CORE-14 `[M]`** Take the time from `Time<Fixed>` in `FixedUpdate` and `Time<Virtual>` in
  `Update`, and never hard-code a per-frame delta
  (`references/scheduling.md` BV-SCHED-06).

### Events, messages, observers

- **BV-CORE-15 `[M]`** `Message` is buffered fan-out read next frame; `Event` is a reaction that
  runs now. They are different traits for different jobs, and a type deriving both is almost always
  a design that has not chosen (`references/events.md` BV-EVENT-01).
- **BV-CORE-16 `[M]`** An event that concerns one entity derives `EntityEvent` and carries the
  entity as a field, read by that field's name. `trigger_targets` is gone
  (`references/events.md` BV-EVENT-09, BV-EVENT-10).
- **BV-CORE-17 `[M]`** Register a `Message` type with `app.add_message::<M>()`. Inserting
  `Messages<M>` as a resource yourself leaks, because nothing then drops old messages
  (`references/events.md` BV-EVENT-04).

### Errors

- **BV-CORE-18 `[M!]`** A system that can fail returns `Result` and uses `?`. No `unwrap`, no
  `expect`, no indexing on a path a player can reach
  (`references/errors.md` BV-ERR-01).
- **BV-CORE-19 `[M]`** Set the `FallbackErrorHandler` explicitly at startup, and make it panic in
  debug and log in release. The default is a decision, so make it yours
  (`references/errors.md` BV-ERR-05).
- **BV-CORE-20 `[M]`** Prefer the non-panicking half of every pair: `get_resource` over `resource`,
  `get` over `entity`, `?` over `single().unwrap()`
  (`references/errors.md` BV-ERR-09).
- **BV-CORE-21 `[M]`** `fn main() -> AppExit`, returning what `App::run` returned. Anything else
  reports a crash as a clean exit (`references/architecture.md` BV-ARCH-17).

### Cargo and versions

- **BV-CORE-22 `[M]`** Pin Bevy exactly in a game binary and use a caret in a published crate. A
  minor bump is a scheduled migration, not something `cargo update` does to you
  (`references/build.md` BV-BUILD-04).
- **BV-CORE-23 `[M]`** Start from a feature collection — `2d`, `3d`, `ui` — and hand-pick features
  only against a measurement recorded in the manifest
  (`references/build.md` BV-BUILD-02 and BV-BUILD-03).
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
4. **Change detection.** Is any `Changed<T>` watching something written unconditionally?
   (BV-ECS-26)
5. **Ordering.** Is ordering expressed in sets, not against a system function? (BV-SCHED-12,
   BV-SCHED-14)
6. **Run conditions and state.** Would each new system be skipped when it should be? (BV-SCHED-17,
   BV-STATE-18)
7. **Reflection.** Does each new component derive `Reflect` and get registered? (BV-ECS-03,
   BV-ECS-13)
8. **Tests.** Is the rule tested without an `App`, and the plugin with the smallest one?
   (BV-TEST-01, BV-TEST-02)
9. **Relaxed forms.** Is anything `[M!]` relying on its relaxed form, and which shipped-code
   condition does not hold?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 24
`BV-CORE-*` rules live in section 4 above; the other 225 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/architecture.md` | `BV-ARCH` (19) | the boundary, plugins, the app |
| `references/ecs.md` | `BV-ECS` (32) | components, required components, queries, change detection, reflection |
| `references/scheduling.md` | `BV-SCHED` (26) | schedules, sets, ordering, run conditions, time, input |
| `references/events.md` | `BV-EVENT` (20) | messages, events, entity events, observers |
| `references/state.md` | `BV-STATE` (22) | resources, states, transitions, scoping |
| `references/errors.md` | `BV-ERR` (17) | fallible systems, the error handler, panicking APIs |
| `references/assets.md` | `BV-ASSET` (14) | handles, loading, hot reload, asset lifetime |
| `references/build.md` | `BV-BUILD` (21) | features, version pinning, the lint divergences, CI |
| `references/migration.md` | `BV-MIG` (18) | every API forbidden since 0.15, and what replaces it |
| `references/view.md` | `BV-VIEW` (21) | UI nodes, text, cameras, materials, post-process, gizmos |
| `references/testing.md` | `BV-TEST` (15) | headless apps, deterministic ticks, what to assert |
| `references/review-checklist.md` | — | The audit protocol: the shared severity model, review order, mechanical pass, output format, and the order in which to refactor an existing game |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/Cargo.toml` | The workspace manifest for a game: an exact Bevy pin with a feature collection, the lint table with its two Bevy relaxations and their reasons, and the profiles that keep debug builds playable |
| `assets/ci.yml` | The workflow: the boundary and one-Bevy checks, clippy and tests under deny-warnings, docs, the MSRV job, the release build, and the `bevy_lint` job kept off until a release supports 0.20 |
| `assets/rust-toolchain.toml` | The pinned stable toolchain the game builds with, kept apart from any nightly the linter needs |
