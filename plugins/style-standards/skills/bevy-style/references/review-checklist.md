# Review protocol

How to audit existing Bevy code against this standard. Read this before reviewing; read the domain
files as the code demands them, and `rust-style`'s protocol for everything that is a Rust question.

## Severity model

Report every finding with one of these labels. The label sets the ordering of the review and tells
the author what must change before merge.

| Severity | Meaning | Examples |
|---|---|---|
| **Unsound** | Corrupts memory or data, or crashes the runtime, from code that looks safe | A save file written from a half-applied frame, an `unsafe` system param with an aliasing borrow, a release error handler that logs and continues past a panic |
| **Stale** | A spelling the target superseded — fails to build, or worse, builds and means something else | `Trigger`, `EventReader`, `Parent`, `*Bundle`, `Pointer<Click>`, `On<Add, T>`, `set_if_neq` on `NextState`, `EditableText` without `TextInput` |
| **Incorrect** | Produces wrong results or crashes on reachable input | `query.single()` unwrapped, a `Changed<T>` that matches every frame, an `iter_many(..).count()` counting ids that do not match |
| **Contract** | Breaks or under-specifies the public surface | A plugin that is a function, a component without `Reflect`, a system set not exported for ordering |
| **Design** | Works, but the shape will cost later | Game rules written against `Query` and `Res`, ordering against a function instead of a set, one giant `Update` |
| **Performance** | Measurable, avoidable cost | A system running every frame that a run condition would skip, `Changed<T>` on a component written unconditionally |
| **Style** | Idiom and readability | Plugin and set naming, import of individual subcrates, system parameter order |

Unsound, Stale and Incorrect findings block a merge. Contract findings block a release. Design and
Performance findings need a decision, not necessarily a change. Style findings are batched — do not
spend a review's attention on them while an Unsound or Incorrect finding sits unaddressed.

## Review order

Do not read the diff top to bottom. Read in this order, because a finding at each stage can
invalidate the work of reading the next.

1. **The boundary.** Does anything outside the view layer name Bevy? It is the one defect this
   standard exists to prevent, and it stays invisible until the next upgrade. (`BV-ARCH-01`)
2. **Stale APIs.** Is every API a 0.20 API? Check anything that looks like a tutorial against
   `references/migration.md`; `Trigger`, `EventReader`, `Parent`, `*Bundle`, `Pointer<Click>` and
   `On<Add, T>` are the usual ones. (`BV-MIG`)
3. **Errors and panics.** Does every fallible system return `Result`, and does the release error
   handler still end the app on a caught panic? (`BV-ERR`)
4. **Change detection.** Is any `Changed<T>` watching something written unconditionally? Then it
   matches every frame. (`BV-ECS`)
5. **Ordering.** Is ordering expressed in sets, rather than against a system function? (`BV-SCHED`)
6. **Run conditions and state.** Would each new system be skipped when it should be — a run
   condition, a state scope, or neither on purpose? (`BV-SCHED`, `BV-STATE`)
7. **Reflection.** Does each new component derive `Reflect`, and is each generic instantiation
   registered? (`BV-ECS`)
8. **Tests.** Are the rules of the game tested without an `App`, and each plugin with the smallest
   one that exercises it? (`BV-TEST`)
9. **Relaxed forms.** Is anything `[M!]` relying on its relaxed form? If so, which of the
   shipped-code conditions does not hold?

## Mechanical pass

Run these before reading anything, and report what could not be run rather than implying it passed.

```bash
# fragment — the commands, in the order to run them
cargo fmt --check
CARGO_BUILD_WARNINGS=deny cargo clippy --workspace --all-targets
cargo test --workspace
cargo tree --duplicates | rg '^bevy'
rg -n 'bevy' crates/*-sim/src/
```

The last two are the standard's own invariants: one Bevy in the tree, and no engine name in a
simulation crate. Then run every literal `rg` Check in `references/migration.md` over `src/`.

## Output format

Deliver reviews as a table ordered by severity, then a short prose section for the two or three
findings that deserve discussion — the format `rust-style`'s protocol gives, citing `BV-` IDs for
Bevy findings and `RS-` IDs for Rust ones.

## Refactoring a codebase to this standard

Do it in this order, one mechanical step per commit, so that each commit is reviewable and
revertible:

1. Move to the target Bevy, with `references/migration.md` as the checklist, before anything else.
   Nothing below is worth doing against an engine you are about to leave.
2. Draw the boundary: move each rule of the game into a crate that does not depend on Bevy, one rule
   per commit, with its test written against plain Rust.
3. Make every system fallible that can fail, and set the error handler.
4. Replace function-to-function ordering with sets, then add run conditions and state scopes.
5. Derive `Reflect` on components and resources, and register each generic instantiation.

State up front which of these steps you are doing, and do not mix a behavioural change into any of
them.
