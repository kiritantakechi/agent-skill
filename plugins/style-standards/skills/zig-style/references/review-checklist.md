# Review protocol

How to audit existing Zig against this standard. Read this before reviewing; read the domain files
as the code demands them.

## Severity model

Report every finding with one of these labels. The label sets the ordering of the review and tells
the author what must change before merge.

| Severity | Meaning | Examples |
|---|---|---|
| **Unsound** | Corrupts memory or data, or crashes the runtime, from code that looks safe | Use-after-free of an arena-owned slice, aliasing `noalias` parameters, `@intCast` that can truncate, reading `undefined`, a pointer into `list.items` held across an append |
| **Stale** | A spelling the target superseded — fails to build, or worse, builds and means something else | `std.io`, `std.fs.cwd()`, `GeneralPurposeAllocator`, `ArrayList(T).init(gpa)`, `std.mem.indexOf`, `{}` where a `format` method was intended, `std.builtin`, `builtin.mode == .Debug`, `std.heap.DebugAllocator`, `std.fmt.allocPrint` |
| **Incorrect** | Produces wrong results or crashes on reachable input | Swallowed error, `catch unreachable` on an operating error, off-by-one, unbounded loop |
| **Contract** | Breaks or under-specifies the public surface | Undocumented ownership transfer, `anyerror` in a public signature, an allocator stored in a long-lived struct, a missing `deinit` |
| **Design** | Works, but the shape will cost later | Concrete type used across a module boundary, `anytype` where a concrete type fits, unbounded queue, recursion with no proven depth, a branch that exists for one input |
| **Performance** | Measurable, avoidable cost | Allocation per loop iteration, unbuffered writer, byte-at-a-time reads, a hot struct that outgrew a cache line |
| **Style** | Idiom and readability | Naming, declaration order, comment typography, a `zig fmt` diff |

Unsound, Stale and Incorrect findings block a merge. Contract findings block a release. Design and
Performance findings need a decision, not necessarily a change. Style findings are batched — do not
spend a review's attention on them while an Unsound or Incorrect finding sits unaddressed.

## Review order

Do not read the diff top to bottom. Read in this order, because a finding at each stage can
invalidate the work of reading the next.

1. **Stale API.** Before anything else, because a pre-0.17 spelling means the author's model of
   `std` is wrong and every other judgement they made is suspect. Run the stale-API greps below.
   (`ZS-MIG`)
2. **Memory and ownership.** Who allocates, who frees, and what the lifetime is. Every allocation
   has a `defer`/`errdefer` on the next line. No allocator stored in a long-lived struct. No pointer
   retained into a container that can resize. (`ZS-MEM`, ZS-MEM-05, ZS-ERR-11, ZS-MEM-12, ZS-MEM-15)
3. **Illegal behavior.** Every `@intCast`, `@ptrCast`, `@alignCast`, and `@bitCast`: is the
   precondition established? Every `undefined`. Every `noalias`. Every `unreachable` reachable from
   operating input. Ask what `fast` does with each, not what `debug` does. (`ZS-DATA`, `ZS-ASSERT`)
4. **Errors.** Every `catch unreachable` and `catch |_|`: is this a programmer error (assert) or an
   operating error (propagate)? Any `anyerror` in a public signature. Any error swallowed to satisfy
   a signature. (`ZS-ERR`, ZS-ERR-01, ZS-ERR-05)
5. **Assertions and bounds.** Is the assertion density near two per function? Does every loop have a
   provable upper bound, every queue a limit, every recursion a proof or an explicit stack?
   (`ZS-ASSERT`, ZS-ASSERT-08, ZS-ASSERT-19, ZS-ERR-23)
6. **Public API.** What is newly `pub`? Is the ownership documented? Is the error set explicit and
   minimal? Would a caller be able to tell from the signature who frees what? (ZS-API-01, `ZS-ERR`)
7. **Concurrency.** Every `Io.async` without a matching `await`, every `Group`/`Select`,
   cancellation paths, and anything holding a resource across a suspension point. (`ZS-CONC`)
8. **Function bodies.** Now read the code. Compound conditions that want splitting, functions past
   70 lines, control flow that wants a labeled switch. (ZS-ERR-18, ZS-ERR-30)
9. **Tests.** Do they use `std.testing.allocator` so leaks fail? Is the error path covered? Is there
   a `checkAllAllocationFailures` for every allocating API? (`ZS-TEST`)
10. **Build and project.** New dependencies justified? `build.zig.zon` `.paths` correct? Does
    `zig build check` pass? (`ZS-BUILD`)

### At a C boundary

At an `export fn`, a `callconv(.c)` function or an `extern` declaration, ask these as well:

1. Does any exported function return `!T`, or an error smuggled as an integer? (ZS-INTEROP-01)
2. Is every pointer parameter null-checked and every length bounded before use? (ZS-INTEROP-02)
3. Does `[*c]` appear anywhere but an exported parameter list? (ZS-INTEROP-09)
4. Is `std.mem.span` being applied to a fixed-size NUL-padded C array where `sliceTo` belongs?
   (ZS-INTEROP-10)
5. Any `@intCast`/`@truncate` on a `c_int`/`c_long`/`c_char` instead of `std.math.cast`?
   (ZS-INTEROP-11)
6. Does every struct shared with C have fixed-width fields and `comptime` layout assertions?
   (ZS-DATA-02, ZS-ASSERT-18)
7. Does any callback `try`, `catch unreachable`, or `@panic` across the C frame? (ZS-INTEROP-13)
8. For each buffer that crosses: which side frees it, is it written down, and does the allocator
   match? (ZS-INTEROP-14)
9. Does the code assume `std.process.Init`, `Io`, or a default panic handler on a target that has
   none? (ZS-INTEROP-16, ZS-INTEROP-17)
10. Does any design depend on two tasks overlapping in a build that may be `-fsingle-threaded`?
    (ZS-INTEROP-19)

## Mechanical pass

Run these before reading anything, and report what could not be run rather than implying it passed.

```sh
zig fmt --check --ast-check --exclude zig-pkg --exclude .zig-cache .  # ZS-BUILD-22
zig build check                       # semantic check, no binary emitted
zig build test                        # debug
zig build test -Doptimize=safe        # ZS-TEST-31: the suite must pass in both
zig build test-integration
zig build -Dtarget=x86_64-linux-gnu   # plus every target you ship (ZS-BUILD-24)
```

### Stale-API greps

These are the highest-yield greps in this file, because they find code that still **compiles**. Run
the command after the migration table: it finds every `gone` and `alias` spelling the code writes
out, and it is generated from the table, so there is no second copy to drift from it here. Then read
each call site this one finds — the spelling did not change, and its meaning did:

```sh
rg -n 'containsAtLeastScalar\(|@hasDecl\(' # 0.17: (element, minimum); pub declarations only
```

A spelling 0.17 removed needs no grep wherever a build analyses it: `zig build check` and the
per-target builds of the mechanical pass reject it, and the name in the diagnostic is a row of the
migration table (ZS-MIG-01). Code no build analyses — a function nothing references, a branch for a
target you do not build — keeps one silently; the same command finds those (ZS-MIG-02).

### Discipline greps

```sh
rg -n 'catch unreachable'               # operating error asserted away?
rg -n 'catch \{\}'                      # swallowed error
rg -n '@(intCast|ptrCast|alignCast|bitCast)' # each needs an established precondition
rg -n '\bundefined\b'                   # every one is a proof obligation
rg -n 'anyerror'                        # widening in a public signature
rg -nUP '(alloc|create).*\n(?!\s*(err)?defer\b)'  # candidates: no defer on the next line
rg -n 'const .* = .*\.items\b'          # pointer into a resizable container
rg -c 'assert\(' ; rg -c '^\s*(pub )?fn '          # two counts: aim for ~2:1
rg -n 'while \(true\)'                  # unbounded loop — where is the limit?
rg -n 'std\.debug\.print'               # program output must not go through this
```

The allocation grep lists each line containing `alloc` or `create` whose next line is no `defer` or
`errdefer`, the pairing ZS-ERR-11 requires; each hit is a candidate to read, not a proven leak. Its
look-ahead needs `-P`, so it needs an `rg` whose `rg --version` lists `+pcre2`.

## Output format

Deliver reviews as a table ordered by severity, then a short prose section for the two or three
findings that deserve discussion.

```markdown
## Findings

| Severity | Rule | Location | Finding | Fix |
|---|---|---|---|---|
| Stale | ZS-MIG-01 | `src/scan.zig:41` | `std.mem.indexOf` — compiles, but is the pre-0.16 name | Rename to `std.mem.find`; it is a pure rename |
| Unsound | ZS-MEM-12 | `src/index.zig:88` | Pointer into `list.items` held across an `append` | Re-index after the append, or reserve capacity up front |
| Contract | ZS-ERR-05 | `src/api.zig:12` | Public `parse` returns `anyerror` | Declare the explicit error set |

## Discussion

<the two or three findings where the right answer depends on context the author
has and you do not — with the trade-off stated and a recommendation>
```

Rules for the review itself:

- **Cite the rule ID.** It makes the standard checkable and the review impersonal.
- **Give the fix, not just the complaint.** A finding without a suggested change is a chore assigned
  to someone else.
- **Separate a stale spelling from a design objection.** The first is a mechanical rename with a
  right answer; conflating them makes the review feel like taste when it is fact.
- **Do not deliver a review that is only praise.** If the code is genuinely good, say so in one line
  and spend the rest on the three most valuable improvements. There are always three.
- **Do not pad with style findings.** `zig fmt` already owns most of them — batch the rest at the
  end under one row, or offer to apply them directly.
- **Say what you did not check.** A review that silently skipped the `@ptrCast` in the decoder is
  worse than one that says it did.
- **Check `fast`, not just `debug`.** Most of the Unsound category is invisible in the build mode
  you ran.

## Refactoring a codebase to this standard

Do it in this order, one mechanical step per commit, so that each commit is reviewable and
revertible:

1. Fix stale API spellings, one release's rows of the migration table (ZS-MIG-01) per commit. These
   are pure renames with no behavior change, so they should never share a commit with anything else.
2. Fix ownership: move stored allocators to parameters, pair every allocation with a
   `defer`/`errdefer`, and give every type that owns memory a `deinit`.
3. Narrow error sets: replace `anyerror` with explicit sets, and turn every `catch unreachable` into
   either an assertion (programmer error) or a propagated error (operating error).
4. Add assertions to reach the density in ZS-ASSERT-08, starting with function preconditions and
   postconditions. This is the step that finds existing bugs, so expect it to stall while you fix
   them — that is the step working.
5. Put a bound on everything unbounded: loops, queues, retries, recursion.
6. Add the missing tests, then `checkAllAllocationFailures` for allocating APIs.
7. Turn on the CI matrix and the `zig fmt --check --ast-check` gate.

State up front which of these steps you are doing, and do not mix a behavioral change into any of
them.
