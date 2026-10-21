# Compile errors zig-style relies on, under Zig 0.17.0

Every message quoted below was printed by `zig` 0.17.0 (aarch64-macos), compiling a probe with
`zig build-obj -fno-emit-bin <probe>.zig`. Analysis is forced with `export fn`, or with a private
fn plus `comptime { _ = &f; }`. Build-system probes run `zig build`.

## Findings

- **Clean rows are few.** Only ZS-CT-02 is cleanly a row. ZS-CAPI-02 is one if its replacement
  advice fits a Forbids line. ZS-CT-27 is borderline, because its message is generic.
- **Unowned errors.** Most always-on errors are owned by no rule: an unused local, an unused
  parameter, a pointless discard, shadowing, a never-mutated `var`, unreachable code, an ignored
  error union. They become new rows (A2), and no rule is removed.
- **Error `==` compiles.** Comparing an error with `==` is not a compile error in 0.17 (see C).
- **`std.builtin` is now a deprecated alias of `std.lang`,** so messages print `lang.*`.

## A. Rule rows

All are Level `error`.

| Rule | Probe | Exact error line | Lint | Forbids |
|---|---|---|---|---|
| ZS-CT-02 | file scope `const n = comptime std.math.log2_int(u32, 1024);` | `error: redundant comptime keyword in already comptime scope` (the same for an array length and a type expression) | `redundant comptime keyword in already comptime scope` | `comptime` where the scope is already comptime |
| ZS-CAPI-02 | `export fn zs_f(s: []const u8) usize { return s.len; }` | `error: parameter of type '[]const u8' not allowed in function with calling convention 'aarch64_aapcs_darwin'` | `not allowed in function with calling convention` | a slice, auto-layout aggregate, non-pointer optional, inferred-tag enum, array or error union in a C signature |
| ZS-CT-27 (borderline) | `pub usingnamespace std.mem;` | `error: expected function or variable declaration after pub` | — | (generic; keep as a migration row) |

ZS-CAPI-01's `!u32` C return hits the same phrase as ZS-CAPI-02. It stays a rule, because it
prescribes the status-enum and out-parameter shape.

### A′. Rejected unconditionally, but only through a generic diagnostic

These are better kept as rows of the migration tables, under "gone". A Lint phrase such as `has no
member named` would match any typo.

| Rule | 0.17 diagnostic | What is left of the rule |
|---|---|---|
| ZS-CT-18 | `invalid builtin function: '@Type'`; `std.meta.Int` and `Tuple` gone | reference text |
| ZS-FMT-11 | `std.fmt.Formatter`, `FormatOptions`, `bufPrintZ` gone | the current `std.fmt` API list |
| ZS-BUILD-02 | `no field named 'root_source_file' in struct 'Build.ExecutableOptions'` | nothing |
| ZS-BUILD-06 | `no field or member function named 'linkLibC'` | the `.link_libc` preference |
| ZS-CAPI-05 | `union 'lang.CallingConvention' has no member named 'C'`; `invalid builtin function: '@setAlignStack'` | the `.c` preference |

### A2. Rows that remove no rule

All are verified at Level `error`.

| Lint | Exact line | Rule that may cite it |
|---|---|---|
| `unused local constant` | `error: unused local constant` | — |
| `unused local variable` | `error: unused local variable` | — |
| `unused function parameter` | `error: unused function parameter` | ZS-CT-13, ZS-IO-18 |
| `unused capture` | `error: unused capture` | — |
| `pointless discard of` | `error: pointless discard of local constant` / `… of function parameter` | — |
| `local variable is never mutated` | `error: local variable is never mutated` | ZS-BUILD-31, ZS-ERR-27 |
| `shadows declaration of` | `error: local constant shadows declaration of 'count'` | — |
| `shadows local constant from outer scope` | `error: local constant 'a' shadows local constant from outer scope` | — |
| `name shadows primitive` | `error: name shadows primitive 'u8'` | — |
| `unreachable code` | `error: unreachable code` (match it anchored: `reached unreachable code` contains it) | — |
| `unused block label` / `unused while loop label` | as named | — |
| `is ignored` | `error: error union of type 'error{Oops}!void' is ignored` | ZS-ERR-11, ZS-CORE-19 |
| `error union is discarded` | `error: error union is discarded` | ZS-ERR-11 |
| `value of type … ignored` | `error: value of type 'u32' ignored` | ZS-MEM-05, ZS-IO-24 |
| `expected error union type, found` | `try` or `catch` on a non-error | ZS-ERR-11 |
| `expected optional type, found` | `orelse` on a non-optional | — |
| `operator == not allowed for type` | an error union compared with a value | — |
| `duplicate switch value` | `error: duplicate switch value '1'` | — |
| `'try' not allowed inside defer expression` | as named | ZS-IO-29, ZS-MEM-11 |
| `cannot return from defer expression` | as named | — |
| `returning address of expired local variable` | as named | ZS-MIG-02 |
| `invalid builtin function` | `@setCold`, `@Type`, `@fence`, `@setAlignStack`, `@optimizeFor` | ZS-ERR-31, ZS-CT-18, ZS-MIG-02 |
| `unattached documentation comment` | as named | ZS-NAME-24 |

## B. Rules that stay, with the error their Check can name

| Rule | Beyond the compiler | Phrase |
|---|---|---|
| ZS-CAPI-01 | status enum and out-parameters | `not allowed in function with calling convention` |
| ZS-CAPI-07 | bare `extern` for your own objects | `dependency on libc must be explicitly specified in the build command` (on linux-musl or wasm32-freestanding; Darwin always links libSystem) |
| ZS-CAPI-14 | state travels through `userdata` | `@ptrCast increases pointer alignment` |
| ZS-NAME-24 | the `///` and `//` editorial split | the doc-comment phrases in A2 |
| ZS-TYPE-06 | unsigned `/`, paired remainders | `signed integers must use @divTrunc, @divFloor, @divCeil, or @divExact` |
| ZS-TYPE-19 | choosing a layout | `packed structs cannot contain fields of type`; `field bit width does not match earlier field` |
| ZS-TYPE-28, ZS-ERR-28, ZS-ERR-09, ZS-CT-25, ZS-CORE-17 | no `else` (which the compiler accepts) | `switch must handle all possibilities`; `unreachable else prong; all cases already handled` |
| ZS-ERR-26 | labeled switch | `cannot continue switch without operand` |
| ZS-CT-04 | `comptime var` only as an inline-loop accumulator | `store to comptime variable depends on runtime condition` |
| ZS-CT-06, ZS-ERR-29 | no inline loop over homogeneous data | `unable to resolve comptime value` |
| ZS-MEM-05 | never `_ =` the Check | `value of type 'heap.Check' ignored` |
| ZS-IO-24 | await or cancel every Future | `value of type 'Io.Future(u32)' ignored` |
| ZS-FMT-04, ZS-FMT-06 | choosing a specifier | `invalid format string 'D' for type 'u64'`; `cannot format slice without a specifier` |
| ZS-BUILD-11 | never hand-edit the fingerprint | `missing top-level 'fingerprint' field`; `invalid fingerprint:` |
| ZS-BUILD-28 | preferred_optimize_mode | `error: invalid option: "optimize"` |

## C. Not compiler rules: 0.17 accepts these

Each of these exits 0 under build-obj:

- `_cursor` and `type_` fields (ZS-NAME-03);
- `//no space` comments, and lines of 104 columns, both clean under `zig fmt --check` (ZS-NAME-28,
  ZS-NAME-30, ZS-CORE-05);
- `errdefer` in a `void` fn (ZS-ERR-13);
- an import cycle under `zig test` (ZS-BUILD-25);
- `.minimum_zig_version = "0.99.0"` (ZS-BUILD-13);
- a widening `@truncate` (ZS-TYPE-09);
- `{}` on a type with `format`, whose output is silently wrong (ZS-FMT-01);
- `{:>8}` on an enum, which panics at run time (ZS-FMT-10);
- `else` after partial prongs (ZS-TYPE-28, ZS-ERR-28);
- `f() catch {};`, `.?`, and `anyerror!u8`;
- `_ = da.deinit();` and `_ = io.async(…)`;
- comparing an error with `==`, including against an error not in the set.

## D. Drift and changed premises

**Messages reworded since the rules quoted them:**

- ZS-TYPE-06 now lists `@divCeil`, a new 0.17 builtin that also affects ZS-ASRT-26.
- ZS-TYPE-19: the error line is now `field bit width does not match earlier field`.
- ZS-CT-04: `store to comptime variable depends on runtime condition`.
- ZS-MIG-02: `union 'lang.CallingConvention' has no member named 'C'`, and `no field named 'Int' in
  union 'lang.Type'`. The real `@setAlignStack` diagnostic is `invalid builtin function`.
- ZS-ERR-17: the message names `'*lang.StackTrace'`.
- ZS-TEST-05: `error: not testing`.
- ZS-BUILD-28: `error: invalid option: "optimize"`.

**Line numbers moved:**

- std/debug.zig 420 → 442;
- Io/Writer.zig 1421 → 1545, and the format dispatch 1077 → 1181;
- testing.zig 82 → 56;
- mem/Allocator.zig 445 → 471.

**Aliases now gone (compile errors):**

- `std.meta.Int`, `Tuple`, `intToEnum` and `declList`;
- `std.fmt.bufPrintZ`;
- `EnumSet.initEmpty` and `initFull`;
- `std.heap.MemoryPoolAligned`, `Extra` and `Options`;
- `Io.File.OpenFlags` and `CreateFlags`;
- `LazyPath.getPath2`, `getPath3` and `getPath4`.

These touch SKILL §2.4 and §5, ZS-CT-18, ZS-FMT-11, ZS-FMT-20, ZS-TYPE-13, and ZS-MIG-05, -07, -12,
-13 and -14. Patterns in the ZS-MIG-14 denylist are now dead weight.

**Still aliases in 0.17:**

- `mem.indexOf*`;
- `ArrayListUnmanaged` and `array_list.Managed`;
- `ArrayHashMapUnmanaged`;
- `fs.path`;
- `debug.runtime_safety` (to be removed after 0.18.0);
- `utf8Decode` and `wtf8Decode`;
- `copyForwards`;
- `tar.pipeToFileSystem`;
- `heap.memory_pool.Aligned`;
- the `pub fn panic` form.

**Errors the rules rely on that no longer occur:**

- `Allocator.free` accepts `*[N]T` (ZS-MEM-15, ZS-IO-04, ZS-TEST-09).
- `Io.Evented` `deinit()` compiles.
- `net.Socket.closeMany` compiles (ZS-IO-42).
- `zig test -ffuzz` builds, and `zig reduce` works. The expiry condition of ZS-BUILD-35, ZS-TEST-20
  and ZS-MIG-11 is met.

**Breaks verified examples:**

- `@typeInfo(T).@"struct".fields` became `field_names`, `field_types` and `field_attrs`.
  `defaultValue` moved to `FieldAttributes.defaultValue(attrs, T)`, and `is_comptime` became
  `field_attrs[i].@"comptime"`.
- `Type.Pointer.alignment` and `.is_const` moved to `attrs.@"align"` and `attrs.@"const"`.

These affect ZS-CT-06, ZS-CT-20, ZS-ERR-29 and ZS-TYPE-37, about 25 lines.
