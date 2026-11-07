---
name: zig-style
description: >-
  Use when writing, reviewing, refactoring, scaffolding, porting or debugging any Zig code, auditing
  a Zig codebase, checking how a std symbol is spelled now, or bringing code written for an older Zig
  up to date, even when no one asks for "style" or "standards". Applies to a `.zig` file, a
  function, an error set, an allocator choice, a test or fuzz target, a `build.zig` and a
  `build.zig.zon`. Targets Zig 0.17.
---

# Zig Style — 0.17

A single standard formed from three sources: the **official Zig style guide** (naming, formatting),
the **empirical conventions of the 0.17 standard library** (API shape, ownership, decl literals),
and **TigerStyle** (assertions, bounded limits, control-flow discipline). Where they disagree, this
standard picks a side and says why.

**Target: Zig 0.17.0.** Zig changed enormously in 0.15 and 0.16, and again in 0.17. Most Zig you
have seen — including most of what is on the public internet — is stale. Section 2 below is the
single highest-value part of this skill; read it before writing any line of Zig.

## How to use this standard

1. **Read section 2** before emitting Zig code. It is the Zig 0.17 reality check, and some of its
   entries change behaviour without producing an error, so nothing else will catch them.
2. **Apply section 4.** Those core rules bind on their own and reach nearly every file.
3. **Load one chapter** from the reference map in section 6 — the one that matches the task. Each
   opens with a table of contents listing every rule it owns, so you can jump straight to the rule.
   Load a second chapter only when the task genuinely spans two; never load all of them.
4. **Walk section 5** before handing back a diff.

Rules are cited by ID: `ZS-`, then the family of the chapter that owns the rule, then its number.
Section 6 maps each family to its chapter, so cite the ID when justifying a change and the reader
can find the full rule and its rationale. When a rule in a chapter and a rule here appear to
conflict, the chapter is the detailed statement and wins; sections 1 and 3 govern how to break a
genuine tie.

A chapter ends with **Decided by tools** when a tool settles part of its subject on its own: each
lint or compiler error, the level it fails a build at, and what it forbids. Those are not rules —
the tool enforces them, so they carry no Why and no Check. When rules are renumbered, the migration
chapter names the file that maps every old ID to its new one.

Every fenced example carries a marker on its first line. `// verified` — the block compiles as
written against Zig 0.17.0, and any test it ships passes. `// fragment` — shown in context rather
than run as a unit, usually because it uses names the chapter declares around it.
`// rejected — <tool>: …` — the rejection is the point, and the marker names the tool that rejects
it: `zig`. A trailing `— GOOD` or `— BAD` names which side of the rule the block illustrates. A
block in another language carries its marker in that language's comment syntax.

## 1. Tiers

Every rule carries a tier. Apply it literally.

| Tag | Meaning |
|---|---|
| `[M]` | **Mandatory** in all Zig code. No exceptions without an explicit instruction from the user. |
| `[M!]` | **Mandatory in high-reliability code**; strongly recommended elsewhere. Each `[M!]` rule states its relaxed form. |
| `[S]` | **Should.** The default. Deviating is allowed but must be justified in a comment on the line that deviates. |

**A codebase is "high-reliability" — `[M!]` applies as `[M]` — if any of these hold:** it stores
data others cannot reconstruct (databases, filesystems, ledgers); a crash or wrong answer is
unrecoverable or unobservable (embedded, firmware, medical, avionics, consensus); it is a security
boundary (cryptography, parsers on untrusted input, sandboxes, allocators); or it runs unattended
where nobody will read the stack trace. **Otherwise** — CLI tools, build scripts, games, application
code, most libraries — `[M!]` rules are recommendations, and the relaxed form given with each rule
is acceptable.

When you cannot tell which category the code is in, ask, or state your assumption in one line and
proceed with the stricter reading.

## 2. Zig 0.17 reality check

### 2.1 Compiles, and behaves differently

| Old | Zig 0.17 | Rule |
|---|---|---|
| `@bitCast` | the same call, which on an array or a vector now reinterprets logical bits independent of endianness, so a big-endian target gets another result; a cast to an enum compiles and is safety-checked like `@fromBackingInt`, and one of an `extern struct` or `extern union` is rejected — `@ptrCast` a pointer to it | ZS-DATA-09 |
| `@hasDecl` | `false` for a declaration that is not `pub`, even in the same file, with no diagnostic | ZS-COMPTIME-14 |
| `std.mem.containsAtLeastScalar` | the same name with its last two parameters swapped, `(T, list, element, minimum)`: for an integer `T` a 0.16 call type-checks and asks another question | ZS-MIG-01 |
| `std.mem.eql` | on a float slice holding NaN, `false` for the slice compared with itself: the same slice no longer short-circuits; `findDiff` likewise | ZS-MIG-01 |
| `init.gpa` | a `SafeAllocator` in `debug` and `safe` builds whether or not libc is linked, as `std.testing.allocator` is; a `safe` build that links libc no longer gets `c_allocator`, and its leak report still never changes the exit code | ZS-MEM-01 |
| `std.meta.declarations` | the same name, now returning the declarations' names, a `[]const [:0]const u8`, where it returned `[]const Declaration` | ZS-COMPTIME-14 |
| `addOptionPath` | an option naming a file: a directory is `addOptionPathDirectory`, and `addOptionPathUntracked` opts out of tracking | ZS-BUILD-24 |
| `zig fetch` | without `--save`, a command that fills only the global cache: `zig fetch --save` and `zig build` fill `zig-pkg/` | ZS-BUILD-12 |

A `changed` row of an earlier release is in the migration table, `ZS-MIG` in section 6, with its
Since; its owning rule's Check finds it.

### 2.2 No longer compiles

| Old | Zig 0.17 | Rule |
|---|---|---|
| `@cImport` | `b.addTranslateC(…)` in `build.zig` and its `.createModule()`, imported as a module | ZS-INTEROP-15 |
| `**` | `@splat(v)` with a result type: `const a: [n]T = @splat(v);` | ZS-DATA-24 |
| `void{}` | `{}` | ZS-MIG-01 |
| `errdefer \|err\|` | the body in an inner function, and at the call `inner() catch \|err\| { …; return err; }` | ZS-ERR-14 |
| `i0` | `u0` | ZS-MIG-01 |
| `.linkage = .internal` | no `@export`: a symbol that is not exported is internal; `std.lang.GlobalLinkage` is `.strong` and `.weak` | ZS-INTEROP-03 |
| `.link_once` | `.weak` | ZS-INTEROP-03 |
| `@bitSizeOf(…)` | `@sizeOf(T) * 8` for a type that is not `packed`, whose padding `@bitSizeOf` counted: it takes a `packed` type only | ZS-DATA-19 |
| `enum(u8) {}` | `enum(noreturn) {}`: an empty exhaustive enum is backed by `noreturn` | ZS-DATA-26 |
| `.@"struct".fields` | `.field_names[i]`, `.field_types[i]`, and `.field_attrs[i]` for `@"comptime"`, `@"align"` and `defaultValue(T)`; an enum's are `.field_names` and `.field_values`, with `.mode == .exhaustive` for `is_exhaustive`, and a union's add `.backing_integer` | ZS-COMPTIME-14 |
| `.decls` | `.decl_names[i]`, on a struct, enum, union or opaque | ZS-COMPTIME-14 |
| `.@"fn".params` | `.param_types[i]`; `calling_convention` and `is_var_args` are `.attrs.@"callconv"` and `.attrs.varargs` | ZS-COMPTIME-14 |
| `.pointer.is_const` | `.pointer.attrs.@"const"`; `is_volatile`, `alignment`, `address_space` and `is_allowzero` likewise | ZS-COMPTIME-14 |
| `std.builtin.Type.Error` | nothing: `@typeInfo(E).error_set` is a struct whose `error_names`, a `?[]const [:0]const u8`, lists the names, and whose `null` still means `anyerror` | ZS-COMPTIME-14 |
| `std.builtin.Type.StructField` | `std.lang.Type.Struct.FieldAttributes`; `UnionField` and `Fn.Param` are `Union.FieldAttributes` and `Fn.ParamAttributes` | ZS-COMPTIME-14 |
| `std.fmt.bufPrintZ` | `std.mem.printSentinel(buffer, fmt, args, 0)` | ZS-OUT-11 |
| `std.Io.File.OpenFlags` | `std.Io.Dir.OpenFileOptions`; `CreateFlags` is `Io.Dir.CreateFileOptions` and `OpenMode` is `Io.Dir.OpenFileOptions.Mode` | ZS-CONC-18 |
| `std.ascii.indexOfIgnoreCase` | `std.ascii.findIgnoreCase`; the `Pos` and `PosLinear` forms likewise | ZS-DATA-32 |
| `std.mem.containsAtLeastScalar2` | `std.mem.containsAtLeastScalar(T, list, element, minimum)` | ZS-MIG-01 |
| `std.mem.readPackedIntNative` | `std.mem.readPackedInt(T, bytes, bit_offset, .native)`; `readPackedIntForeign` takes `.foreign` | ZS-MIG-01 |
| `std.mem.writePackedIntNative` | `std.mem.writePackedInt(T, bytes, bit_offset, value, .native)`; `writePackedIntForeign` takes `.foreign` | ZS-MIG-01 |
| `std.heap.MemoryPoolAligned` | `std.heap.memory_pool.Aligned`; `MemoryPoolExtra` and `MemoryPoolOptions` are `memory_pool.Extra` and `memory_pool.Options` | ZS-MEM-16 |
| `std.heap.memory_pool.Managed` | `std.heap.memory_pool.Aligned` or `.Extra`, with the allocator per call; `AlignedManaged` and `ExtraManaged` likewise | ZS-MEM-16 |
| `.initEmpty()` | `.empty` on an `EnumSet`, a `bit_set.Integer` or a `bit_set.Array`; `.initFull()` is `.full`; `bit_set.Dynamic.initEmpty(gpa, n)` keeps its name | ZS-DATA-13 |
| `std.heap.stackFallback` | `var bfa: std.heap.BufferFirstAllocator = .init(&buffer, fallback);`, then `bfa.allocator()` as often as you like; `StackFallbackAllocator` likewise | ZS-MEM-03 |
| `std.process.spawnPath` | `std.process.spawn(io, .{ .exe = .{ .path = dir }, … })`; `replacePath` is `replace` with the same `.exe` | ZS-CONC-41 |
| `std.meta.Int` | `@Int(signedness, bits)` | ZS-COMPTIME-14 |
| `std.meta.Tuple` | `@Tuple(types)` | ZS-COMPTIME-14 |
| `std.meta.fields` | `@typeInfo(T)` | ZS-COMPTIME-14 |
| `std.meta.declarationInfo` | `@hasDecl`, and `@typeInfo(T)` | ZS-COMPTIME-14 |
| `b.args` | `run.addPassthruArgs()`, which makes the step uncached and keeps the arguments from the build script | ZS-BUILD-07 |
| `b.build_root` | `b.root`, a `Cache.Path` | ZS-MIG-01 |
| `.paths = &.{…}` | `.paths = b.pathList(&.{…})` in `b.addFmt`, and so for `.exclude_paths` | ZS-BUILD-26 |
| `b.reference_trace` | `zig build -freference-trace=n` | ZS-COMPTIME-20 |
| `std.Build.LazyPath.getPath` | nothing: the configure phase resolves no path, so the `LazyPath` goes to the step that reads it; `getPath2`, `getPath3` and `getPath4` likewise | ZS-MIG-01 |
| `std.Build.GeneratedFile` | nothing: a step's output is a `LazyPath` | ZS-MIG-01 |
| `std.Build.LazyPath.basename` | nothing in std | ZS-MIG-01 |
| `b.findProgram(&…)` | `b.findProgramLazy(.{ .names = names })`, a `LazyPath`; `b.findProgram(.{ .names = names })` is a `?[]const u8` that poisons the configure cache | ZS-MIG-01 |
| `.include_guard_override` | `.include_guard` on a `ConfigHeader` | ZS-MIG-01 |
| `--zig-lib-dir` | `--zig-lib=path` | ZS-MIG-01 |
| `--global-cache-dir` | nothing; `--build-runner` and `--verbose-llvm-bc` likewise | ZS-MIG-01 |
| `--build-runner` | nothing | ZS-MIG-01 |
| `--verbose-llvm-bc` | nothing | ZS-MIG-01 |
| `std.Target.SubSystem` | `std.zig.Subsystem`; `builtin.subsystem` has no replacement | ZS-INTEROP-18 |
| `std.zon.parse.fromSliceAlloc` | `std.zon.parse.fromSlice(T, .{ .gpa = gpa, .arena = arena, .source = source, .diagnostics = &diag })`, which allocates the result into `.arena`; the form that allocates nothing is `fromSliceNoAlloc` | ZS-DATA-35 |
| `std.zon.parse.free` | nothing: the result lives in the arena `fromSlice` was given | ZS-DATA-35 |
| `std.Uri.getHost` | `std.Io.net.HostName.fromUri(uri, &buffer)`, which validates the name | ZS-CONC-38 |
| `std.gpu` | `std.spirv` | ZS-MIG-01 |
| `dupeZ` | `allocator.dupeSentinel(u8, s, 0)` | ZS-INTEROP-10 |

A `gone` row of an earlier release is in the migration table, `ZS-MIG` in section 6, with its Since;
the `rg` command after that table finds every `gone` and `alias` spelling but a shape, whatever its
release.

### 2.3 What Zig 0.17 gained

- `@backingInt` and `@fromBackingInt`, in place of `@intFromEnum` and `@enumFromInt`, and for a
  tagged union or a packed type with an explicit backing integer as well (ZS-DATA-09).
- `@divCeil(a, b)`, in place of `std.math.divCeil(T, a, b) catch unreachable` (ZS-DATA-06).
- `{q}` and `{qf}`, a double-quoted, escaped string, and what a `format` method writes, escaped
  (ZS-OUT-04).
- `std.heap.BufferFirstAllocator`, a buffer first and an allocator after it, as often as you like
  (ZS-MEM-03).
- `b.dependency`, which fetches a lazy package itself, and `b.dependencyLazy`, which fetches several
  at once (ZS-BUILD-13).

## 3. Design principles

**Safety > Performance > Developer experience.** All three matter; when two conflict, the earlier
one wins. This ordering is TigerStyle's and it is the reason for most of the rules below.

Simplicity is not a fourth goal competing with these — it is how the three are achieved at once.
Simplicity is the hardest revision, not the first attempt.

**Symmetry** is how simplicity survives a second contributor. A simple design that is applied
irregularly stops being simple: operations that come in pairs but are named differently, siblings
that take their parameters in a different order, two mechanisms for one concept, a branch that
exists for a single input. None of those is a bug, and each is locally defensible, which is why a
codebase accretes them one reasonable-looking patch at a time, which is why it needs a standing
question in the same pass as the assertion review, not an occasional cleanup.

**Zero technical debt.** Solve a problem in design, where it is cheap, rather than in production,
where it is not. Code, like steel, is least expensive to change while it is hot. In practice this
means: a known showstopper is fixed before the change lands, not filed; an exponential-complexity
algorithm or an unbounded latency spike on a hot path does not ship with a TODO attached; and a
`TODO` in a diff is either resolved or carries a tracking reference and a stated trigger for when it
must be. The point is not perfectionism — it is that the second pass frequently never happens, so
"we will fix it later" is usually a decision to ship it permanently.

When two rules appear to conflict and their tiers are equal, the goal ordering decides it: safety
first, then performance, then developer experience. Where that does not separate them, use these
five questions, in order:

1. **What can be deleted?** Fewer types, fewer parameters, fewer allocations, fewer dependencies,
   fewer states.
2. **What can be made unrepresentable?** Encode the bound in the type and give the limit a name, so
   an invalid value cannot be constructed rather than being caught after the fact (ZS-DATA-03,
   ZS-ASSERT-19).
3. **What can be asserted instead of assumed?** An invariant the code depends on is checked at the
   boundary or written down as an assumption — never left implicit (ZS-ERR-01, ZS-ASSERT-07).
4. **What is asymmetric?** If `init` exists, does `deinit`? Do sibling functions take their
   parameters in the same order? Does every operation have its inverse? A missing half is either a
   restriction the documentation must state, or an oversight (ZS-DATA-36, ZS-DATA-37, ZS-NAME-28).
5. **What is special-cased?** A branch that exists for one input is a design that has not absorbed
   that input. Fold it into the general path, or give it its own type (ZS-ERR-32, ZS-NAME-29).

Simplicity outranks all five. A `comptime` construction that makes the reader hold three levels of
type substitution is worse than the duplication it removed (ZS-COMPTIME-12), and a symmetry nobody
can see is not worth the name it costs.

## 4. Core rules

- **Naming, Files, Module Layout, Declaration Order, Comments**
  - ZS-NAME-01 [M] Apply the official casing rules exactly
  - ZS-NAME-02 [M] Capitalize acronyms as ordinary English words
  - ZS-NAME-04 [M] Spell names out; abbreviate only as scope tightens
  - ZS-NAME-06 [M] Put units and qualifiers last, sorted by descending significance
  - ZS-NAME-12 [M] Name the receiver after its type; keep `self` for anonymous generic containers
  - ZS-NAME-13 [M] Name a file `TitleCase.zig` if and only if it has top-level fields
  - ZS-NAME-15 [M] Keep the `@This()` alias and the whole import block in one place
  - ZS-NAME-17 [M] Order a struct body: fields → types → `init`/`deinit` → methods → tests
  - ZS-NAME-18 [S] Put the entry point and the most important declarations first
  - ZS-NAME-22 [M] Say why, not what — including at the top of every test
  - ZS-NAME-23 [S] Comment typography: space after the slashes, capital letter, full stop
  - ZS-NAME-24 [M] Run `zig fmt`; the trailing comma is your only formatting lever
  - ZS-NAME-25 [M] Hard-limit every line to 100 columns
- **Type selection, integers, structs, data layout**
  - ZS-DATA-27 [M] Return the lowest-dimensionality type that can carry the answer
- **Errors, control flow, assertions vs errors vs panics**
  - ZS-ERR-01 [M] Classify a failure as a programmer error or an operating condition first
  - ZS-ERR-05 [M] Never put `anyerror` in a public signature
  - ZS-ERR-10 [M] Every error is handled somewhere; `catch {}` needs a justification comment
  - ZS-ERR-16 [M] Split compound conditions into separate checks
  - ZS-ERR-17 [S] Prefer a `switch` to an `else if` chain; if you flatten chains into trees, say why
  - ZS-ERR-18 [M] State invariants positively when an `if`/`else` splits the input space
  - ZS-ERR-19 [S] An `if` with no `else` over a validated domain carries a comment or an assertion
  - ZS-ERR-21 [M!] No recursion; where recursion is allowed, bound the depth explicitly
  - ZS-ERR-22 [M!] Push `if`s up and `for`s down
  - ZS-ERR-28 [M!] Hard limit of 70 lines per function
- **Memory, allocators, ownership lifetimes**
  - ZS-MEM-05 [M] Pass the allocator per call; do not store it in a field
  - ZS-MEM-06 [M] Name the allocator for its role — `gpa`, `arena`, `scratch` — and place it after the receiver
  - ZS-MEM-10 [M] Put `defer` / `errdefer` on the line immediately after the acquisition
  - ZS-MEM-15 [M] Pointers into container storage die on any capacity change
  - ZS-MEM-16 [M] If you need stable pointers, use `std.heap.MemoryPool(T)` or store indices
  - ZS-MEM-18 [M] Allocate all memory at startup where every bound is known then; otherwise name the rung
- **Performance and the discipline of locality**
  - ZS-PERF-13 [S] Shape functions like an inverted hourglass: narrow in, narrow out, wide inside
  - ZS-PERF-17 [M] Spell out the options that decide behavior; never inherit their defaults
- **Assertions, invariants, and putting a limit on everything**
  - ZS-ASSERT-02 [M] Never put a side effect in an `assert`, and never claim it is compiled out
  - ZS-ASSERT-04 [M!] Ship `safe` builds, or define a project-local always-on assert
  - ZS-ASSERT-08 [M!] Average at least two assertions per function
  - ZS-ASSERT-09 [M] Split compound assertions
  - ZS-ASSERT-10 [M] Write an implication as a single-line `if (a) assert(b);`
  - ZS-ASSERT-11 [M] Assert the negative space, and mark deliberate non-invariants with `maybe`
  - ZS-ASSERT-12 [M] State a biconditional as one `==` between two booleans
  - ZS-ASSERT-15 [M] Check every persisted or transmitted structure on its write path and its read path
  - ZS-ASSERT-19 [M] Put a limit on everything, and give the limit a name ending in `_max`
  - ZS-ASSERT-22 [M] Give every loop a provable bound; an unbounded loop must say so and assert it
  - ZS-ASSERT-23 [M] Fail fast: check the bound at the boundary where untrusted input enters
- **comptime, generics, and interfaces**
  - ZS-COMPTIME-10 [M] A `comptime` parameter the body does not depend on is a bug
  - ZS-COMPTIME-15 [M] Pick the interface shape from this table before writing any dispatch code
  - ZS-COMPTIME-16 [M] The runtime vtable is two fields; recover the impl by `@ptrCast(@alignCast(…))`
  - ZS-COMPTIME-17 [M] Embed a stateful interface as field `interface`; recover owner by `@fieldParentPtr`
  - ZS-COMPTIME-19 [M] A closed set of implementations is a tagged union, not an interface

## 5. Review checklist

When reviewing or self-reviewing a Zig diff, walk this list. It is the review order of the full
protocol — severity model, mechanical pass, output format — in `references/review-checklist.md`.

1. **Stale API.** Does the command after the migration table find anything, and does each call a
   `changed` row names still mean what the author meant — `{}` on a type with a `format` method,
   `containsAtLeastScalar`, `@hasDecl` on a declaration that is not `pub`? (ZS-MIG-01, ZS-OUT-01)
2. **Memory and ownership.** Every allocation paired with a `defer`/`errdefer` at the same nesting
   level, and proved by the test allocator? Any pointer held across a container mutation? Allocators
   named for their lifetime?
3. **Illegal behavior.** Any `@intCast`/`@truncate` that can silently lose data, an index used where
   a count belongs, or division whose intent is not shown with `@divExact`, `@divFloor` or
   `@divCeil`?
4. **Errors.** Every error handled and named? Any `catch unreachable` that can really fire? Any
   `errdefer` missing on a multi-step construction? Every buffered writer flushed on every success
   path?
5. **Assertions and bounds.** Are the preconditions this function relies on asserted, and the
   negative space checked? Any assert with a side effect, or relied on in a `fast` build? Any loop,
   queue, or buffer whose maximum is not established?
6. **Public API.** Units last and descending, receivers named after their type rather than `self`,
   no abbreviations? Unpaired operations, siblings disagreeing on parameter order, error-set members
   with uneven detail, two mechanisms for one concept, a branch that exists for one input
   (ZS-DATA-36 … ZS-DATA-38, ZS-ERR-31, ZS-ERR-32, ZS-NAME-28 … ZS-NAME-30)?
7. **Concurrency.** Every `Io.async` awaited or cancelled, every `Group` and `Select` closed, and
   nothing held across a suspension point?
8. **Function bodies.** `zig fmt` clean, ≤100 columns, functions that fit on a screen, control flow
   in the parent? Does every non-obvious decision have a comment explaining the reasoning?
9. **Tests.** Does the change ship with the test that would have caught the bug? Does it exercise
   invalid input, not just valid?
10. **Build and project.** Every new dependency justified, `build.zig.zon` `.paths` correct, and
    `zig build check` passing?

## 6. Reference map

Load the chapter you need; do not load all of them. Every chapter opens with a table of contents
listing each rule it owns, so a cited ID can be resolved without reading the chapter through. The 0
`ZS-CORE-*` rules live in section 4 above; the other 343 live here.

| File | Rule IDs | Covers |
|---|---|---|
| `references/naming.md` | `ZS-NAME` (30) | Naming rules in full, file and module layout, declaration order, doc comments, formatting |
| `references/data.md` | `ZS-DATA` (38) | Integer choice, off-by-one discipline, casts, struct design, decl literals, result location semantics, in-place init, layout, data-oriented design |
| `references/errors.md` | `ZS-ERR` (32) | Error sets, `try`/`catch`/`errdefer`, the error-vs-assert-vs-panic decision table, labeled switch, `@branchHint` |
| `references/memory.md` | `ZS-MEM` (26) | Allocator taxonomy, the allocator vtable, ownership rules, arena patterns, the static-allocation tiering |
| `references/concurrency.md` | `ZS-CONC` (44) | `std.Io` in full: `Reader`/`Writer`, custom streams, `Io.Dir`/`Io.File`, `async`/`concurrent`/`Group`/`Select`, cancellation, timeouts |
| `references/output.md` | `ZS-OUT` (20) | `{}` vs `{f}`, the specifier set, custom `format` methods, `std.fmt`, program output vs logging vs `std.debug.print` |
| `references/performance.md` | `ZS-PERF` (21) | Design-phase performance, back-of-envelope sketches, batching, `@prefetch`/`@Vector`, and the locality discipline (smallest scope, no aliasing, POCPOU, pure leaves) |
| `references/interop.md` | `ZS-INTEROP` (21) | `export`/`extern`/`callconv(.c)`, `[*c]` pointers, C strings and integers, callbacks with `userdata`, plus freestanding/WASM/single-threaded targets |
| `references/assertions.md` | `ZS-ASSERT` (25) | Assertion philosophy and density, pair assertions, comptime assertions, the optimize modes and which one ships, `_max` constants |
| `references/comptime.md` | `ZS-COMPTIME` (20) | comptime rules, `anytype` and its costs, type introspection, the three interface shapes, anti-patterns |
| `references/testing.md` | `ZS-TEST` (27) | `std.testing` in 0.17, `Smith` fuzzing, allocation-failure testing, deterministic simulation |
| `references/build.md` | `ZS-BUILD` (36) | Annotated `build.zig` and `build.zig.zon`, dependencies, project layout, selecting the optimize mode, CI |
| `references/migration.md` | `ZS-MIG` (3) | Every old spelling 0.13 through 0.17 left behind, with its status, Since and owning rule, and the command the table generates |
| `references/review-checklist.md` | — | The audit protocol: seven-level severity model, review order, mechanical greps, output format, and the order in which to refactor an existing codebase |

## 7. Bundled assets

Copy these rather than reconstructing them from memory; they encode decisions the rules only
describe. Each is derived from the chapter that owns it rather than written independently, so the
asset and the rule cannot drift apart.

| File | Contents |
|---|---|
| `assets/build.zig` | The complete library + CLI `build.zig` from ZS-BUILD-01, at 0.17.0: module-level `target`/`optimize`, one test binary per module, a separate `test-integration` step, a host-only codegen tool, and the `fmt` and `check` steps |
| `assets/build.zig.zon` | The annotated manifest from ZS-BUILD-09…12: enum-literal `.name`, the `.fingerprint` warning, what `.minimum_zig_version` does and does not do, and `.paths` as the thing that defines the package hash |
| `assets/ci.yml` | The five CI requirements of ZS-BUILD-29 as a workflow — pinned toolchain, `fmt --check --ast-check`, `debug` and `safe`, the cross-compile matrix of ZS-BUILD-28, and a cache key naming every matrix axis. Only the `run:` lines are rules; verify the action versions yourself |
