---
name: bevy-style
description: >-
  The Bevy 0.19 engineering standard — a 240-rule delta on top of rust-style covering the ECS,
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

# Bevy Style — 0.19

A **delta on top of `rust-style`**. Everything that standard says about naming, errors, ownership,
functional style, modules, documentation and Cargo still holds; this one states what changes when
Bevy is in the dependency list, and nothing else. Section 3 lists every place the two disagree and
which one wins.

**Target: Bevy 0.19 (0.19.1 at the time of writing) on edition 2024.** Bevy's API turns over faster
than any other dependency a game has, and most Bevy code on the public internet — and most of what
a language model has read — is 0.15 or older. Section 2 and `references/migration.md` exist for
that reason.

## How to use this standard

1. **Read section 2** before emitting Bevy code. It is the 0.19 reality check, and three of its
   entries change behaviour without changing whether the code compiles.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second only when the task genuinely spans two.
4. **Load `rust-style` as well** for anything that is a Rust question rather than a Bevy question.
5. **Walk section 5** before handing back a diff.

Rules are cited by ID — `BV-ECS-04`, `BV-SCH-11`. The prefix identifies the owning chapter (section
6 maps prefix to file). Rules from the other standard keep their own prefix, so an `RS-` citation is
always a pointer out of this document.

Every fenced example carries a marker on its first line. `// verified` — the block compiles against
Bevy 0.19.1 on edition 2024, and any test it ships passes. `// fragment` — shown in context rather
than compiled as a unit, usually because it names things the chapter declares around it.
`// does-not-compile` — the compile error is the point. A trailing `— GOOD` or `— BAD` names which
side of the rule the block illustrates. A block in another language carries its marker in that
language's comment syntax.

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

## 2. Bevy 0.19 reality check — read before writing code

### 2.1 The three that change behaviour without changing whether it compiles

1. **Setting the same state now runs the transition.** Since 0.18, `next_state.set(S)` fires
   `OnExit(S)` and `OnEnter(S)` even when the current state is already `S`. Code that called `set`
   every frame used to be free and now re-runs every setup and teardown system in the game.
   `set_if_neq` is the old behaviour (`references/state.md` BV-STA-19).
2. **`Ref<T>` now clones the `Ref`, not the `T`.** 0.19 gave `Ref` its own `Clone` and `Copy`. A
   `value.clone()` that used to produce a `T` now produces another `Ref<T>`, and only fails to
   compile if the surrounding code was explicit about the type. Write `ref.deref().clone()` for the
   old meaning (`references/migration.md` BV-MIG-18).
3. **`Resource` is a `Component`.** In 0.19, `#[derive(Resource)]` also implements `Component`. A
   type used as both is now impossible; worse, inserting one as a component despawns the copy on
   any other entity, and resources appear in `&T` queries. Split the type
   (`references/state.md` BV-STA-01).

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

## 3. Where this standard departs from `rust-style`

Each row is a rule of the other standard that Bevy makes impossible, harmful, or merely noisy.
Nothing else is relaxed: a divergence not listed here is a defect, not a dialect.

| `rust-style` rule | What applies instead | Why Bevy forces it |
|---|---|---|
| `RS-API-24` Keep every struct field private | `BV-ECS-01` — component fields are public | The ECS is the accessor. Reflection, scenes, `bsn!` and the remote protocol all read fields directly, and a component cannot defend an invariant anyway. The exemption is paid for by `BV-ARC-04`. |
| `RS-API-26` Keep tuple-struct fields private too | `BV-ECS-01` — a component newtype is `pub` too | The newtype's `pub` normally spends the freedom to change the representation. For a component the representation *is* the contract: reflection, scenes and the remote protocol all address the field by name, so there is no freedom left to spend. |
| `RS-NAM-33` Never suffix a name with the language construct | `BV-ARC-10` — `*Plugin` and `*Systems` | `add_plugins(X)` and `configure_sets(_, X)` are the same shape with different meanings, so the name is the only signal. Bevy addresses both by type — `is_plugin_added::<T>`, `disable::<T>` — and `bevy_lint` enforces the suffix ecosystem-wide. |
| `RS-ERR-14` Never expose `Box<dyn Error>` or `anyhow::Error` from a library | `BV-ERR-03` — a system returns `BevyError`, the domain does not | `BevyError` is boxed and type-erased, and Bevy's `Result` alias is exactly the aliased form the rule names. Its rationale does not reach here: a system has no caller to match on the error — the schedule hands it to the error handler. Everything a caller could branch on stays a real type on the domain side. |
| `RS-CAR-27` Run `clippy::pedantic` at warn and answer each warning | `BV-CAR-12` — `needless_pass_by_value` is allowed | It fires on every `Res<T>` parameter and its suggestion does not compile: `&Res<'_, T>` is not a `SystemParam`. |
| `RS-CAR-31` Never blanket-allow at crate level | `BV-CAR-11` — `elided_lifetimes_in_paths` is allowed | It fires on every `Query`, `Res`, `ResMut`, `Commands`, `MessageReader` and `Local` parameter. Writing the `'_`s does satisfy it, and buys nothing but noise. |
| `RS-CAR-23` Use caret requirements; never pin exact versions | `BV-CAR-04` — a game binary pins Bevy exactly | A 0.x minor bump renames half the API. Libraries keep the caret; the rule is unchanged for anything published. |
| `RS-CAR-24` Turn off default features on heavy dependencies | `BV-CAR-02` — start from a feature collection | Bevy's feature graph has 172 entries and moves every release; a hand-picked list goes stale silently, as an unmeasured one always does. |
| `RS-FP-04` A `for` loop that only pushes is a `collect` | `BV-ECS-20` — iterate a query with `for` | Query iteration is effect, not transformation: the loop writes through `Mut<T>` and the borrow does not survive a collect. |
| `RS-API-71` Use `#[non_exhaustive]` where the shape may grow | `BV-ECS-05` — components are exhaustive | Struct-literal construction is how components are spawned, and `#[non_exhaustive]` forbids it outside the defining crate. Required components are the growth mechanism instead. |

`RS-STR-46` is not on this list either: it forbids glob imports "outside tests and preludes", and
`use bevy::prelude::*` is a prelude. It is the first line of nearly every Bevy file, and naming
twenty imports instead would be worse.

`RS-NAM-03` is **not** on this list, and the temptation is real: Bevy's own packages are
`bevy_ecs`, `bevy_render`, spelled with underscores. That is upstream's namespace, not a licence to
name your own crates `mygame_combat` — packages published from this standard use hyphens
(`BV-ARC-08`).

## 4. Core rules

These 24 `BV-CORE-*` rules bind on their own. Each names the chapter carrying the full statement.

### The boundary

- **BV-CORE-01 `[M]`** The code that decides what happens takes and returns plain Rust data.
  `Query`, `Commands`, `Res` and `Entity` belong to the code that decides when it happens. An
  engine upgrade should rewrite signatures, not arithmetic
  (`references/architecture.md` BV-ARC-01).
- **BV-CORE-02 `[M]`** The separation is mandatory at every project size; only its mechanism scales
  — modules for one binary, crates for a workspace — and whichever it is, a CI job enforces it
  rather than a paragraph (`references/architecture.md` BV-ARC-02 and BV-ARC-07).
- **BV-CORE-03 `[M]`** Data that must satisfy a condition does not live in a component as bare
  fields. Model it as a domain type with a private field and a fallible constructor, and let the
  component carry that type (`references/architecture.md` BV-ARC-04).
- **BV-CORE-04 `[M]`** Every plugin is a type implementing `Plugin`, named `*Plugin`, and never a
  function or a closure: four of Bevy's own APIs address a plugin by its type, and a function's type
  cannot be written. `main` adds plugins and nothing else
  (`references/architecture.md` BV-ARC-09, BV-ARC-10, BV-ARC-16).

### Components and queries

- **BV-CORE-05 `[M]`** A component is one fact about an entity. Two fields that change at different
  times, are written by different systems, or are read by different queries are two components
  (`references/ecs.md` BV-ECS-02).
- **BV-CORE-06 `[M]`** Express "an X always has a Y" with `#[require(Y)]`, never with a hand-kept
  tuple that callers must remember. Bundles no longer exist
  (`references/ecs.md` BV-ECS-06).
- **BV-CORE-07 `[M]`** A zero-sized marker goes in `With<T>` or `Without<T>`, never in the query's
  data. Querying it fetches nothing and costs a column
  (`references/ecs.md` BV-ECS-17).
- **BV-CORE-08 `[M!]`** Writing through `Mut<T>` marks the component changed whether or not the
  value differs. Anything a `Changed<T>` filter watches is written with `set_if_neq`
  (`references/ecs.md` BV-ECS-25).
- **BV-CORE-09 `[M]`** Give a query type more than one data item and more than one filter and it
  becomes unreadable; name it with a `type` alias. Give a system more than seven parameters and
  group them with `#[derive(SystemParam)]`
  (`references/ecs.md` BV-ECS-21, `references/scheduling.md` BV-SCH-09).
- **BV-CORE-10 `[M!]`** Every component, resource and message derives `Reflect` and is registered
  with `app.register_type::<T>()`. Reflection is what the inspector, the scene format and the
  remote protocol run on (`references/ecs.md` BV-ECS-13).

### Scheduling

- **BV-CORE-11 `[M]`** Simulation runs in `FixedUpdate`; input, animation, camera and anything that
  must be smooth run in `Update`. A camera modified in `FixedUpdate` visibly stutters
  (`references/scheduling.md` BV-SCH-01, BV-SCH-04).
- **BV-CORE-12 `[M!]`** Ordering between systems goes through named `SystemSet`s configured once,
  not a chain of `.before()` and `.after()` at each `add_systems` call
  (`references/scheduling.md` BV-SCH-11).
- **BV-CORE-13 `[M]`** A system that should not always run says so with `.run_if(…)`. An early
  `return` hides the condition from the schedule, which cannot then skip the system or report it
  (`references/scheduling.md` BV-SCH-16).
- **BV-CORE-14 `[M]`** Take the time from `Time<Fixed>` in `FixedUpdate` and `Time<Virtual>` in
  `Update`, and never hard-code a per-frame delta
  (`references/scheduling.md` BV-SCH-06).

### Events, messages, observers

- **BV-CORE-15 `[M]`** `Message` is buffered fan-out read next frame; `Event` is a reaction that
  runs now. They are different traits for different jobs, and a type deriving both is almost always
  a design that has not chosen (`references/events.md` BV-EVT-01).
- **BV-CORE-16 `[M]`** An event that concerns one entity derives `EntityEvent` and carries the
  entity as a field. `trigger_targets` is gone
  (`references/events.md` BV-EVT-08).
- **BV-CORE-17 `[M]`** Register a `Message` type with `app.add_message::<M>()`. Inserting
  `Messages<M>` as a resource yourself leaks, because nothing then drops old messages
  (`references/events.md` BV-EVT-04).

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
  reports a crash as a clean exit (`references/architecture.md` BV-ARC-17).

### Cargo and versions

- **BV-CORE-22 `[M]`** Pin Bevy exactly in a game binary and use a caret in a published crate. A
  minor bump is a scheduled migration, not something `cargo update` does to you
  (`references/cargo.md` BV-CAR-04).
- **BV-CORE-23 `[M]`** Start from a feature collection — `2d`, `3d`, `ui` — and hand-pick features
  only against a measurement recorded in the manifest
  (`references/cargo.md` BV-CAR-02).
- **BV-CORE-24 `[M]`** Two entries of `rust-style`'s lint table are relaxed for Bevy code and no
  others: `elided_lifetimes_in_paths` and `clippy::needless_pass_by_value`. `type_complexity` and
  `too_many_arguments` stay on, because both have a compliant form that is better code
  (`references/cargo.md` BV-CAR-11, BV-CAR-12).

## 5. Before handing back a diff

1. **Does anything outside the view layer name Bevy?** That is the one defect this standard exists
   to prevent, and it is invisible until the next upgrade.
2. **Is every API in the diff a 0.19 API?** Check anything that looks like a tutorial against
   `references/migration.md`. `Trigger`, `EventReader`, `Parent` and `*Bundle` are the usual four.
3. **Is any `Changed<T>` watching something written unconditionally?** If so the filter matches
   every frame and is doing nothing.
4. **Does every fallible system return `Result`?** Search the diff for `unwrap`, `expect` and
   `[` on a query or resource.
5. **Is the ordering expressed in sets?** A `.after(some_system)` naming a function is a
   dependency on an implementation detail.
6. **Would each new system be skipped when it should be?** A run condition, a state scope, or
   neither on purpose.
7. **Does each new component derive `Reflect` and get registered?** An unregistered type is
   invisible to every tool.
8. **Is anything `[M!]` relying on its relaxed form?** If so, say which of the shipped-code
   conditions does not hold.

## 6. Reference map

Load the chapter that matches the task.

| Chapter | Covers | Rules |
|---|---|---|
| `references/architecture.md` | the boundary, plugins, the app | `BV-ARC` (19) |
| `references/ecs.md` | components, required components, queries, change detection, reflection | `BV-ECS` (31) |
| `references/scheduling.md` | schedules, sets, ordering, run conditions, time | `BV-SCH` (24) |
| `references/events.md` | messages, events, entity events, observers | `BV-EVT` (20) |
| `references/state.md` | resources, states, transitions, scoping | `BV-STA` (21) |
| `references/errors.md` | fallible systems, the error handler, panicking APIs | `BV-ERR` (16) |
| `references/assets.md` | handles, loading, hot reload, asset lifetime | `BV-ASS` (14) |
| `references/cargo.md` | features, version pinning, the lint divergences, CI | `BV-CAR` (20) |
| `references/migration.md` | every API forbidden since 0.15, and what replaces it | `BV-MIG` (18) |
| `references/ui-render.md` | UI nodes, text, cameras, materials, gizmos | `BV-UI` (18) |
| `references/testing.md` | headless apps, deterministic ticks, what to assert | `BV-TST` (15) |

The 24 core rules in section 4 are summaries; the full statement is always in the chapter.
