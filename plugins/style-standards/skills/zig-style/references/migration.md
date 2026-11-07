# Migration: Every Spelling That Changed from 0.13 to 0.17

Scope: every spelling a Zig program writes that 0.13 through 0.17 removed, renamed, changed or
deprecated, keyed by the old spelling, with the rule that owns it, and the command the table
generates. Why a spelling is wrong, and how to use what replaced it, is its owning rule's: the
concurrency, memory, data, output and build chapters teach the new designs.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- Old spellings
- **Reading the table**
  - ZS-MIG-01 [M] Write 0.17 spellings; check an unfamiliar std symbol against the local std
  - ZS-MIG-02 [M] Run the command after the table over code no build analyses
  - ZS-MIG-03 [M!] Fail the build on a spelling the table marks `alias`
- Decided by tools

---

## Old spellings

A row's status says what Zig 0.17 does with its old spelling: `gone` — it rejects it, as a
declaration std does not have, a builtin, field or flag the compiler does not know, or a shape it
does not accept, so the build fails wherever the compiler analyses it; `changed` — it accepts it,
and it means something else, so its owning rule's Check finds it; `alias` — it accepts it, it means
what it did, and std marks it deprecated, so the command after the table finds it; `deprecated` — it
accepts it and it means what it did, but only the release notes deprecate it, or no fixed string
tells it from a live spelling. A spelling with `…` in it is a shape: code left out where the `…`
stands, which no fixed string finds, so its owning rule's Check does. A method that only std's types
ever had is keyed by its bare name, as code calls it; a name std reaches through a namespace, by its
path from `std`. A row may stand for a family its 0.17 column names. Since is the release from which
the row's status holds: for a `gone` row the first without the spelling, for an `alias` the one that
deprecated it, for a `changed` row the one that changed it. Section 2.1 lists the `changed` rows of
0.17 and section 2.2 the `gone` ones. A row only the release notes claim says so.

| Old | Zig 0.17 | Status | Since | Rule |
|---|---|---|---|---|
| `usingnamespace` | an explicit re-export, one `pub const` per name: `pub const encode = helpers.encode;`; a declaration once mixed in conditionally is `pub const x = if (cond) a else b;` | gone | 0.15 | ZS-BUILD-15 |
| `@Type` | `@Int`, `@Tuple`, `@Struct`, `@Union`, `@Enum`, `@Pointer`, `@Fn` or `@EnumLiteral`; a float, array, optional or error set has its own syntax | gone | 0.16 | ZS-COMPTIME-14 |
| `@setCold` | `@branchHint(.cold)`, the branch's first statement | gone | 0.14 | ZS-ERR-29 |
| `@fence` | nothing: strengthen the orderings of the atomic operations it stood between | gone | 0.14 | ZS-MIG-01 |
| `@setAlignStack` | `callconv(.withStackAlign(.c, n))`, evaluated at `comptime` | gone | 0.14 | ZS-INTEROP-04 |
| `callconv(.C)` | `callconv(.c)`; `.Naked` is `.naked`, and an x86 `.Stdcall` is `.winapi` or `.{ .x86_stdcall = .{} }` | gone | 0.15 | ZS-INTEROP-04 |
| `@export(f, …)` | `@export(&f, …)`: the first argument is a pointer | gone | 0.14 | ZS-INTEROP-03 |
| `@typeInfo(…).Struct` | `@typeInfo(T).@"struct"`; every tag is lowercase: `.int`, `.pointer`, `.comptime_int`, and `.one` for `Size.One` | gone | 0.14 | ZS-COMPTIME-14 |
| `asm volatile (… ::: "…")` | a clobber struct: `::: .{ .rcx = true, .r11 = true }` | gone | 0.15 | ZS-MIG-01 |
| `v[…]` | on a runtime `@Vector` with a runtime index, copy to an array (`const a: [n]T = v;`), index it, and store back with `v = a;` | gone | 0.16 | ZS-PERF-16 |
| `pub fn panic` | `pub const panic = std.debug.FullPanic(handler);`, the handler a `fn ([]const u8, ?usize) noreturn` | alias | 0.14 | ZS-INTEROP-17 |
| `@cImport` | `b.addTranslateC(…)` in `build.zig` and its `.createModule()`, imported as a module | gone | 0.17 | ZS-INTEROP-15 |
| `@intFromEnum` | `@backingInt`, which also takes a tagged union or a packed type with an explicit backing integer; `zig fmt` rewrites it | alias | 0.17 | ZS-DATA-09 |
| `@enumFromInt` | `@fromBackingInt`, whose operand already has the backing type, so `@intCast` a wider one first; `zig fmt` rewrites it, wrapping the operand in an `@intCast` that a value of the backing type does not need | alias | 0.17 | ZS-DATA-09 |
| `**` | `@splat(v)` with a result type: `const a: [n]T = @splat(v);` | gone | 0.17 | ZS-DATA-24 |
| `void{}` | `{}` | gone | 0.17 | ZS-MIG-01 |
| `errdefer \|err\|` | the body in an inner function, and at the call `inner() catch \|err\| { …; return err; }` | gone | 0.17 | ZS-ERR-15 |
| `i0` | `u0` | gone | 0.17 | ZS-MIG-01 |
| `.linkage = .internal` | no `@export`: a symbol that is not exported is internal; `std.lang.GlobalLinkage` is `.strong` and `.weak` | gone | 0.17 | ZS-INTEROP-03 |
| `.link_once` | `.weak` | gone | 0.17 | ZS-INTEROP-03 |
| `@bitCast` | the same call, which on an array or a vector now reinterprets logical bits independent of endianness, so a big-endian target gets another result; a cast to an enum compiles and is safety-checked like `@fromBackingInt`, and one of an `extern struct` or `extern union` is rejected — `@ptrCast` a pointer to it | changed | 0.17 | ZS-DATA-09 |
| `@bitSizeOf(…)` | `@sizeOf(T) * 8` for a type that is not `packed`, whose padding `@bitSizeOf` counted: it takes a `packed` type only | gone | 0.17 | ZS-DATA-19 |
| `@hasDecl` | `false` for a declaration that is not `pub`, even in the same file, with no diagnostic | changed | 0.17 | ZS-COMPTIME-14 |
| `enum(u8) {}` | `enum(noreturn) {}`: an empty exhaustive enum is backed by `noreturn` | gone | 0.17 | ZS-DATA-26 |
| `.@"struct".fields` | `.field_names[i]`, `.field_types[i]`, and `.field_attrs[i]` for `@"comptime"`, `@"align"` and `defaultValue(T)`; an enum's are `.field_names` and `.field_values`, with `.mode == .exhaustive` for `is_exhaustive`, and a union's add `.backing_integer` | gone | 0.17 | ZS-COMPTIME-14 |
| `.decls` | `.decl_names[i]`, on a struct, enum, union or opaque | gone | 0.17 | ZS-COMPTIME-14 |
| `.@"fn".params` | `.param_types[i]`; `calling_convention` and `is_var_args` are `.attrs.@"callconv"` and `.attrs.varargs` | gone | 0.17 | ZS-COMPTIME-14 |
| `.pointer.is_const` | `.pointer.attrs.@"const"`; `is_volatile`, `alignment`, `address_space` and `is_allowzero` likewise | gone | 0.17 | ZS-COMPTIME-14 |
| `std.builtin.Type.Error` | nothing: `@typeInfo(E).error_set` is a struct whose `error_names`, a `?[]const [:0]const u8`, lists the names, and whose `null` still means `anyerror` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.builtin.Type.StructField` | `std.lang.Type.Struct.FieldAttributes`; `UnionField` and `Fn.Param` are `Union.FieldAttributes` and `Fn.ParamAttributes` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.io` | `std.Io` | gone | 0.16 | ZS-CONC-06 |
| `std.io.GenericWriter` | `*std.Io.Writer`, one non-generic struct with the buffer you give it; `AnyWriter` and `std.io.Writer` likewise | gone | 0.16 | ZS-CONC-06 |
| `std.io.GenericReader` | `*std.Io.Reader`; `AnyReader` and `std.io.Reader` likewise | gone | 0.16 | ZS-CONC-06 |
| `std.io.bufferedWriter` | a buffer passed to the writer's constructor: `file.writerStreaming(io, &buffer)`, then `flush()` | gone | 0.15 | ZS-CONC-04 |
| `std.io.bufferedReader` | a buffer passed to the reader's constructor: `file.reader(io, &buffer)` | gone | 0.15 | ZS-CONC-10 |
| `std.io.fixedBufferStream` | `std.Io.Writer.fixed(&buffer)` to write, `std.Io.Reader.fixed(bytes)` to read | gone | 0.16 | ZS-CONC-06 |
| `std.io.getStdOut` | `std.Io.File.stdout().writerStreaming(io, &buffer)`, then `&w.interface` | gone | 0.15 | ZS-CONC-05 |
| `std.io.getStdErr` | `io.lockStderr(&buffer, null)`, or `std.Io.File.stderr()` | gone | 0.15 | ZS-CONC-09 |
| `std.io.getStdIn` | `std.Io.File.stdin()` | gone | 0.15 | ZS-CONC-10 |
| `std.io.null_writer` | `var d: std.Io.Writer.Discarding = .init(&scratch);`, then `&d.writer` | gone | 0.16 | ZS-CONC-06 |
| `std.io.countingWriter` | `std.Io.Writer.Discarding`: its `count`, and `fullCount()` with the buffered bytes | gone | 0.15 | ZS-CONC-06 |
| `std.io.CountingReader` | `reader.discard(limit)`, which returns the count | gone | 0.16 | ZS-CONC-06 |
| `std.io.tty.detectConfig` | `std.Io.Terminal.Mode.detect(io, file, NO_COLOR, CLICOLOR_FORCE)`; for stderr, the `.terminal()` of `io.lockStderr(&buffer, null)` | gone | 0.16 | ZS-CONC-43 |
| `std.fifo.LinearFifo` | `std.Io.Reader` and `std.Io.Writer`, or `std.Deque(T)` | gone | 0.15 | ZS-CONC-06 |
| `std.RingBuffer` | `std.Io.Reader` and `std.Io.Writer`, or `std.Deque(T)` | gone | 0.15 | ZS-CONC-06 |
| `std.fmt.format` | `w.print(fmt, args)` | gone | 0.16 | ZS-CONC-06 |
| `std.fmt.FormatOptions` | `std.fmt.Options` | gone | 0.16 | ZS-OUT-11 |
| `std.fmt.Formatter` | `std.fmt.Alt(Data, formatFn)`, built with `std.fmt.alt(ctx, .funcName)` | gone | 0.16 | ZS-OUT-03 |
| `std.fmt.formatType` | `w.printValue(…)` | gone | 0.15 | ZS-OUT-02 |
| `std.fmt.formatIntValue` | `w.printInt(…)` | gone | 0.15 | ZS-OUT-02 |
| `std.fmt.fmtSliceHexLower` | `{x}` on the slice; `fmtSliceHexUpper` is `{X}` | gone | 0.15 | ZS-OUT-04 |
| `std.fmt.fmtDuration` | `{f}` on an `Io.Duration` | gone | 0.15 | ZS-OUT-04 |
| `std.fmt.fmtIntSizeDec` | `{B}`; `fmtIntSizeBin` is `{Bi}` | gone | 0.15 | ZS-OUT-04 |
| `std.fmt.allocPrintZ` | `gpa.printSentinel(fmt, args, 0)` | gone | 0.15 | ZS-OUT-11 |
| `{D}` | `{f}` on an `Io.Duration` | gone | 0.16 | ZS-OUT-04 |
| `pub fn format(…, comptime fmt: []const u8, …)` | `pub fn format(v: @This(), w: *std.Io.Writer) std.Io.Writer.Error!void`: `{}` ignores a method of the old shape and `{f}` rejects it | changed | 0.15 | ZS-OUT-02 |
| `{}` | the default dump, which ignores a type's `format` method: `{f}` calls it, and `{t}` prints an enum, union tag or error name | changed | 0.15 | ZS-OUT-01 |
| `std.fmt.allocPrint` | `gpa.print(fmt, args)`; `allocPrintSentinel` is `gpa.printSentinel(fmt, args, 0)` | alias | 0.17 | ZS-OUT-11 |
| `std.fmt.bufPrint` | `std.mem.print`; `bufPrintSentinel` and `BufPrintError` are `std.mem.printSentinel` and `std.mem.PrintError` | alias | 0.17 | ZS-OUT-11 |
| `std.fmt.bufPrintZ` | `std.mem.printSentinel(buffer, fmt, args, 0)` | gone | 0.17 | ZS-OUT-11 |
| `std.fs.cwd` | `std.Io.Dir.cwd()`; every `Io.Dir` and `Io.File` method takes `io` after the receiver | gone | 0.16 | ZS-CONC-18 |
| `std.fs.Dir` | `std.Io.Dir`, each method taking `io` after the receiver; `chmod` and `chown` are `setPermissions` and `setOwner`, and `setAsCwd` is `std.process.setCurrentDir(io, dir)` | gone | 0.16 | ZS-CONC-18 |
| `std.fs.File` | `std.Io.File`, each method taking `io` after the receiver: `read` and `readv` are `readStreaming`, `pread` and `preadv` `readPositional`, `write`, `writev` and `writeAll` `writeStreaming` and `writeStreamingAll`; its `Mode` is `Io.File.Permissions`, and its `OpenFlags` and `CreateFlags` are `Io.Dir.OpenFileOptions` and `CreateFileOptions` | gone | 0.16 | ZS-CONC-18 |
| `std.Io.File.OpenFlags` | `std.Io.Dir.OpenFileOptions`; `CreateFlags` is `Io.Dir.CreateFileOptions` and `OpenMode` is `Io.Dir.OpenFileOptions.Mode` | gone | 0.17 | ZS-CONC-18 |
| `std.fs.MAX_PATH_BYTES` | `std.Io.Dir.max_path_bytes` | gone | 0.14 | ZS-CONC-18 |
| `std.fs.path` | `std.Io.Dir.path` | alias | 0.16 | ZS-CONC-18 |
| `std.fs.max_path_bytes` | `std.Io.Dir.max_path_bytes` | alias | 0.16 | ZS-CONC-18 |
| `std.fs.max_name_bytes` | `std.Io.Dir.max_name_bytes` | alias | 0.16 | ZS-CONC-18 |
| `std.fs.base64_alphabet` | `std.base64.url_safe_alphabet_chars` | alias | 0.16 | ZS-CONC-18 |
| `std.fs.base64_encoder` | `std.base64.url_safe.Encoder` | alias | 0.16 | ZS-CONC-18 |
| `std.fs.base64_decoder` | `std.base64.url_safe.Decoder` | alias | 0.16 | ZS-CONC-18 |
| `makeDir` | `dir.createDir(io, path, permissions)` | gone | 0.16 | ZS-CONC-18 |
| `makePath` | `dir.createDirPath(io, path)` | gone | 0.16 | ZS-CONC-18 |
| `makeOpenPath` | `dir.createDirPathOpen(io, path, options)` | gone | 0.16 | ZS-CONC-18 |
| `realpathAlloc` | `dir.realPathFileAlloc(io, path, gpa)`, a `[:0]u8`; `dir.realpath` is `dir.realPathFile(io, path, &out)`, which returns a length, not a slice | gone | 0.16 | ZS-CONC-18 |
| `std.fs.realpath` | `std.Io.Dir.realPathFileAbsolute(io, path, &out)`, or its `…Alloc` form | gone | 0.16 | ZS-CONC-18 |
| `getEndPos` | `file.length(io)`; `setEndPos` is `file.setLength(io, n)` | gone | 0.16 | ZS-CONC-18 |
| `setAsCwd` | `std.process.setCurrentDir(io, dir)` | gone | 0.16 | ZS-CONC-18 |
| `std.fs.openSelfExe` | `std.process.openExecutable(io, flags)` | gone | 0.16 | ZS-CONC-18 |
| `std.fs.selfExePath` | `std.process.executablePath(io, buffer)`; `selfExePathAlloc` likewise | gone | 0.16 | ZS-CONC-18 |
| `std.fs.selfExeDirPath` | `std.process.executableDirPath(io, buffer)`; `selfExeDirPathAlloc` likewise | gone | 0.16 | ZS-CONC-18 |
| `std.fs.getAppDataDir` | nothing in std | gone | 0.16 | ZS-CONC-18 |
| `std.net` | `std.Io.net` | gone | 0.16 | ZS-CONC-38 |
| `error.RenameAcrossMountPoints` | `error.CrossDevice`, as is `error.NotSameFileSystem`: std returns neither name, so a comparison with it is never true | changed | 0.16 | ZS-ERR-08 |
| `error.SharingViolation` | `error.FileBusy`: std returns the old name no more, so a comparison with it is never true | changed | 0.16 | ZS-ERR-08 |
| `error.EnvironmentVariableNotFound` | `error.EnvironmentVariableMissing`: std returns the old name no more, so a comparison with it is never true | changed | 0.16 | ZS-ERR-08 |
| `error.PathAlreadyExists` | what `rename` onto a directory that is not empty no longer returns: it returns `error.DirNotEmpty` | changed | 0.16 | ZS-CONC-21 |
| `mem.indexOf` | `mem.find` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfPos` | `mem.findPos` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfPosLinear` | `mem.findPosLinear` | alias | 0.16 | ZS-MIG-01 |
| `mem.lastIndexOf` | `mem.findLast` | alias | 0.16 | ZS-MIG-01 |
| `mem.lastIndexOfLinear` | `mem.findLastLinear` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfScalar` | `mem.findScalar` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfScalarPos` | `mem.findScalarPos` | alias | 0.16 | ZS-MIG-01 |
| `mem.lastIndexOfScalar` | `mem.findScalarLast` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfAny` | `mem.findAny` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfAnyPos` | `mem.findAnyPos` | alias | 0.16 | ZS-MIG-01 |
| `mem.lastIndexOfAny` | `mem.findLastAny` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfNone` | `mem.findNone` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfNonePos` | `mem.findNonePos` | alias | 0.16 | ZS-MIG-01 |
| `mem.lastIndexOfNone` | `mem.findLastNone` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfDiff` | `mem.findDiff` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfSentinel` | `mem.findSentinel` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfMin` | `mem.findMin` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfMax` | `mem.findMax` | alias | 0.16 | ZS-MIG-01 |
| `mem.indexOfMinMax` | `mem.findMinMax` | alias | 0.16 | ZS-MIG-01 |
| `std.ascii.indexOfIgnoreCase` | `std.ascii.findIgnoreCase`; the `Pos` and `PosLinear` forms likewise | gone | 0.17 | ZS-DATA-32 |
| `std.mem.containsAtLeastScalar` | the same name with its last two parameters swapped, `(T, list, element, minimum)`: for an integer `T` a 0.16 call type-checks and asks another question | changed | 0.17 | ZS-MIG-01 |
| `std.mem.containsAtLeastScalar2` | `std.mem.containsAtLeastScalar(T, list, element, minimum)` | gone | 0.17 | ZS-MIG-01 |
| `std.mem.readPackedIntNative` | `std.mem.readPackedInt(T, bytes, bit_offset, .native)`; `readPackedIntForeign` takes `.foreign` | gone | 0.17 | ZS-MIG-01 |
| `std.mem.writePackedIntNative` | `std.mem.writePackedInt(T, bytes, bit_offset, value, .native)`; `writePackedIntForeign` takes `.foreign` | gone | 0.17 | ZS-MIG-01 |
| `std.mem.byteSwapAllFields` | `std.mem.byteSwap`; `byteSwapAllFieldsAligned` is `byteSwapAligned` | alias | 0.17 | ZS-MIG-01 |
| `std.mem.eql` | on a float slice holding NaN, `false` for the slice compared with itself: the same slice no longer short-circuits; `findDiff` likewise | changed | 0.17 | ZS-MIG-01 |
| `std.mem.tokenize` | `tokenizeScalar`, `tokenizeAny` or `tokenizeSequence` | gone | 0.14 | ZS-MIG-01 |
| `std.mem.split` | `splitScalar`, `splitAny` or `splitSequence`; `splitBackwards` likewise | gone | 0.14 | ZS-MIG-01 |
| `std.mem.page_size` | `std.heap.page_size_min`, `page_size_max` or `pageSize()` | gone | 0.14 | ZS-MEM-22 |
| `std.mem.copyForwards` | `@memmove(dest[0..source.len], source)`; `copyBackwards` likewise | alias | 0.15 | ZS-MEM-23 |
| `std.ArrayList(…).init(…)` | `var list: std.ArrayList(T) = .empty;`, the allocator passed to every method that allocates and to `deinit` | gone | 0.15 | ZS-DATA-13 |
| `std.ArrayListUnmanaged` | `std.ArrayList` | alias | 0.15 | ZS-DATA-13 |
| `std.ArrayListAligned` | `std.array_list.Aligned(T, alignment)`; `ArrayListAlignedUnmanaged` likewise | alias | 0.15 | ZS-DATA-13 |
| `std.array_list.Managed` | `std.ArrayList`, with the allocator per call; `array_list.AlignedManaged` likewise | alias | 0.15 | ZS-DATA-13 |
| `std.BoundedArray` | `var list: std.ArrayList(T) = .initBuffer(&buffer);`, then `appendBounded` where `BoundedArray` returned an error, and `appendAssumeCapacity` where the capacity is proved | gone | 0.15 | ZS-DATA-23 |
| `std.ArrayHashMap` | `std.array_hash_map.Custom` | gone | 0.16 | ZS-DATA-13 |
| `std.AutoArrayHashMap` | `std.array_hash_map.Auto` | gone | 0.16 | ZS-DATA-13 |
| `std.StringArrayHashMap` | `std.array_hash_map.String` | gone | 0.16 | ZS-DATA-13 |
| `std.ArrayHashMapUnmanaged` | `std.array_hash_map.Custom` | alias | 0.16 | ZS-DATA-13 |
| `std.AutoArrayHashMapUnmanaged` | `std.array_hash_map.Auto` | alias | 0.16 | ZS-DATA-13 |
| `std.StringArrayHashMapUnmanaged` | `std.array_hash_map.String` | alias | 0.16 | ZS-DATA-13 |
| `std.SegmentedList` | `std.heap.MemoryPool(T)` for stable addresses, or indices into a list | gone | 0.16 | ZS-DATA-23 |
| `std.TailQueue` | `std.DoublyLinkedList`, intrusive: a `Node` field recovered with `@fieldParentPtr` | gone | 0.14 | ZS-MEM-14 |
| `std.ComptimeStringMap` | `std.StaticStringMap` | gone | 0.13 | ZS-MIG-01 |
| `std.heap.MemoryPoolAligned` | `std.heap.memory_pool.Aligned`; `MemoryPoolExtra` and `MemoryPoolOptions` are `memory_pool.Extra` and `memory_pool.Options` | gone | 0.17 | ZS-MEM-14 |
| `std.heap.memory_pool.Managed` | `std.heap.memory_pool.Aligned` or `.Extra`, with the allocator per call; `AlignedManaged` and `ExtraManaged` likewise | gone | 0.17 | ZS-MEM-14 |
| `.initEmpty()` | `.empty` on an `EnumSet`, a `bit_set.Integer` or a `bit_set.Array`; `.initFull()` is `.full`; `bit_set.Dynamic.initEmpty(gpa, n)` keeps its name | gone | 0.17 | ZS-DATA-13 |
| `IntegerBitSet` | `bit_set.Integer` | alias | 0.17 | ZS-DATA-13 |
| `ArrayBitSet` | `bit_set.Array` | alias | 0.17 | ZS-DATA-13 |
| `StaticBitSet` | `bit_set.Static` | alias | 0.17 | ZS-DATA-13 |
| `DynamicBitSetUnmanaged` | `bit_set.Dynamic` | alias | 0.17 | ZS-DATA-13 |
| `DynamicBitSet` | `bit_set.Dynamic`, with the allocator per call; `bit_set.DynamicManaged` likewise | alias | 0.17 | ZS-DATA-13 |
| `getLastOrNull` | `list.last()`, a `?T` copy; the borrow is `list.lastPtr()` | alias | 0.17 | ZS-ERR-28 |
| `getLast` | `list.last()`, which returns `?T` where `getLast` returned `T`, so the call site handles the `null` | alias | 0.17 | ZS-ERR-28 |
| `std.DoublyLinkedList.pop` | `popLast` | deprecated | 0.17 | ZS-MEM-14 |
| `std.heap.GeneralPurposeAllocator` | `init.gpa`, or `var sa: std.heap.SafeAllocator = .init(std.heap.page_allocator, .{});` | gone | 0.16 | ZS-MEM-04 |
| `std.heap.DebugAllocator` | `std.heap.SafeAllocator`, not generic: `.init(backing, .{})`, always thread-safe, its `Options` `stack_trace_frames`, `check_write_after_free`, `canary`, `bucket_size_log2` and `block_size_log2` | alias | 0.17 | ZS-MEM-04 |
| `std.heap.Check` | the leak count `SafeAllocator.deinit()` returns: `const leaks = sa.deinit();`, then `assert(leaks == 0)`, the call kept out of the assert | alias | 0.17 | ZS-MEM-04 |
| `init.gpa` | a `SafeAllocator` in `debug` and `safe` builds whether or not libc is linked, as `std.testing.allocator` is; a `safe` build that links libc no longer gets `c_allocator`, and its leak report still never changes the exit code | changed | 0.17 | ZS-MEM-01 |
| `std.heap.ThreadSafeAllocator` | nothing: `SafeAllocator` is thread-safe, and `std.heap.smp_allocator` is the one for a multithreaded `fast` or `small` build | gone | 0.16 | ZS-MEM-03 |
| `std.heap.stackFallback` | `var bfa: std.heap.BufferFirstAllocator = .init(&buffer, fallback);`, then `bfa.allocator()` as often as you like; `StackFallbackAllocator` likewise | gone | 0.17 | ZS-MEM-03 |
| `std.process.argsAlloc` | `try init.minimal.args.toSlice(arena)`, a `[]const [:0]const u8`; `argsFree` goes with it | gone | 0.16 | ZS-MEM-01 |
| `std.process.getEnvMap` | `init.environ_map` | gone | 0.16 | ZS-MEM-01 |
| `std.process.getEnvVarOwned` | `init.environ_map.get(key)`, a borrowed `?[]const u8`; or `try init.minimal.environ.getAlloc(gpa, key)`, which the caller frees and which fails with `error.EnvironmentVariableMissing` | gone | 0.16 | ZS-MEM-01 |
| `std.posix.getenv` | `init.environ_map.get(key)`; on POSIX, `init.minimal.environ.getPosix(key)`, a `?[:0]const u8` read without allocating | gone | 0.16 | ZS-MEM-01 |
| `std.process.hasEnvVar` | `init.environ_map.contains(key)`, or `try init.minimal.environ.contains(gpa, key)`; `hasEnvVarConstant(key)` is `init.minimal.environ.containsConstant(key)` | gone | 0.16 | ZS-MEM-01 |
| `std.ChildProcess` | `std.process.spawn(io, .{ .argv = …, .stdout = .pipe })` | gone | 0.13 | ZS-CONC-41 |
| `std.process.Child.init` | `std.process.spawn(io, .{ .argv = …, .stdout = .pipe })`, which spawns as well | gone | 0.16 | ZS-CONC-41 |
| `std.process.Child.run` | `std.process.run(gpa, io, options)` | gone | 0.16 | ZS-CONC-41 |
| `std.process.execv` | `std.process.replace(io, .{ .argv = … })` | gone | 0.16 | ZS-CONC-41 |
| `std.process.spawnPath` | `std.process.spawn(io, .{ .exe = .{ .path = dir }, … })`; `replacePath` is `replace` with the same `.exe` | gone | 0.17 | ZS-CONC-41 |
| `std.Thread.Mutex` | `std.Io.Mutex` | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.Condition` | `std.Io.Condition` | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.ResetEvent` | `std.Io.Event` | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.Semaphore` | `std.Io.Semaphore` | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.RwLock` | `std.Io.RwLock` | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.Futex` | `io.futexWait` and `io.futexWake`; there is no `Io.Futex` type | gone | 0.16 | ZS-CONC-29 |
| `std.Thread.WaitGroup` | `std.Io.Group` | gone | 0.16 | ZS-CONC-25 |
| `std.Thread.Pool` | `io.async` and `Io.Group`; `Io.Threaded`'s `async_limit` is the pool size | gone | 0.16 | ZS-CONC-25 |
| `std.once` | nothing in std | gone | 0.16 | ZS-CONC-29 |
| `std.time.Timer` | `std.Io.Timestamp`, read from an `Io.Clock`; `std.time` holds unit constants and `epoch` | gone | 0.16 | ZS-CONC-32 |
| `std.time.Instant` | `std.Io.Timestamp` | gone | 0.16 | ZS-CONC-32 |
| `std.time.timestamp` | `std.Io.Timestamp.now(io, clock)`; `milliTimestamp` and `nanoTimestamp` likewise | gone | 0.16 | ZS-CONC-32 |
| `std.time.sleep` | `io.sleep(duration, clock)`, the duration an `Io.Duration` such as `.fromMilliseconds(10)` | gone | 0.15 | ZS-CONC-32 |
| `std.crypto.random` | `io.random(&buffer)`, or `io.randomSecure(&buffer)` where the entropy must be guaranteed | gone | 0.16 | ZS-TEST-14 |
| `std.posix.getrandom` | `io.random(&buffer)`, or `io.randomSecure(&buffer)` | gone | 0.16 | ZS-TEST-14 |
| `crypto_always_getrandom` | nothing: `io.randomSecure`; `crypto_fork_safety` likewise | gone | 0.16 | ZS-TEST-14 |
| `std.rand` | `std.Random` | gone | 0.14 | ZS-TEST-14 |
| `std.testing.refAllDeclsRecursive` | `std.testing.refAllDecls` in each file, or `comptime { _ = @import(…); }` in the module root | gone | 0.16 | ZS-TEST-23 |
| `std.debug.captureStackTrace` | `std.debug.captureCurrentStackTrace(options, addresses)` | gone | 0.16 | ZS-ERR-32 |
| `std.debug.dumpStackTraceFromBase` | `std.debug.dumpCurrentStackTrace(options)`, which takes a `StackUnwindOptions` where it took a start address | gone | 0.16 | ZS-ERR-32 |
| `std.debug.walkStackWindows` | `std.debug.captureCurrentStackTrace`; `writeStackTraceWindows` is `writeCurrentStackTrace` | gone | 0.16 | ZS-ERR-32 |
| `std.debug.StackIterator` | nothing public: `captureCurrentStackTrace` | gone | 0.16 | ZS-ERR-32 |
| `std.debug.runtime_safety` | `@import("builtin").optimize.runtimeSafety()`: your module's mode, where `runtime_safety` reports std's | alias | 0.14 | ZS-ASSERT-16 |
| `std.meta.Int` | `@Int(signedness, bits)` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.meta.Tuple` | `@Tuple(types)` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.meta.declList` | `@typeInfo(T)`'s `decl_names` | gone | 0.16 | ZS-COMPTIME-14 |
| `std.meta.fields` | `@typeInfo(T)` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.meta.declarationInfo` | `@hasDecl`, and `@typeInfo(T)` | gone | 0.17 | ZS-COMPTIME-14 |
| `std.meta.declarations` | the same name, now returning the declarations' names, a `[]const [:0]const u8`, where it returned `[]const Declaration` | changed | 0.17 | ZS-COMPTIME-14 |
| `std.meta.fieldInfo` | `@typeInfo(T)`; `fieldNames` is its `field_names` | alias | 0.17 | ZS-COMPTIME-14 |
| `std.meta.fieldNames` | `@typeInfo(T)`'s `field_names` | alias | 0.17 | ZS-COMPTIME-14 |
| `std.meta.intToEnum` | `std.enums.fromInt(E, n)`, which returns `?E` | gone | 0.16 | ZS-INTEROP-02 |
| `std.builtin` | `std.lang`: `std.builtin.Type` is `std.lang.Type`, `CallingConvention` `std.lang.CallingConvention`, and so for every member | alias | 0.17 | ZS-MIG-01 |
| `std.builtin.OptimizeMode` | `std.lang.Optimize` | alias | 0.17 | ZS-ASSERT-04 |
| `.Debug` | `.debug`; `.ReleaseSafe`, `.ReleaseFast` and `.ReleaseSmall` are `.safe`, `.fast` and `.small`. A field set to the old name compiles, `==` and `!=` reject it, and `@tagName` and `{t}` print the new name | alias | 0.17 | ZS-ASSERT-04 |
| `.ReleaseSafe` | `.safe` | alias | 0.17 | ZS-ASSERT-04 |
| `.ReleaseFast` | `.fast` | alias | 0.17 | ZS-ASSERT-04 |
| `.ReleaseSmall` | `.small` | alias | 0.17 | ZS-ASSERT-04 |
| `builtin.mode` | `builtin.optimize` | alias | 0.17 | ZS-ASSERT-04 |
| `builtin.cpu` | `builtin.target.cpu`; `os`, `abi` and `object_format` are `target.os`, `target.abi` and `target.ofmt` | alias | 0.17 | ZS-INTEROP-18 |
| `builtin.os` | `builtin.target.os` | alias | 0.17 | ZS-INTEROP-18 |
| `builtin.abi` | `builtin.target.abi` | alias | 0.17 | ZS-INTEROP-18 |
| `builtin.object_format` | `builtin.target.ofmt` | alias | 0.17 | ZS-INTEROP-18 |
| `addExecutable(.{ …, .root_source_file = … })` | `.root_module = b.createModule(.{ .root_source_file = …, .target = …, .optimize = … })`: `root_source_file`, `target` and `optimize` are the module's, on `addLibrary`, `addObject` and `addTest` likewise | gone | 0.15 | ZS-BUILD-02 |
| `addStaticLibrary` | `b.addLibrary(.{ .linkage = .static, … })`; `addSharedLibrary` is `.linkage = .dynamic` | gone | 0.15 | ZS-BUILD-06 |
| `addSharedLibrary` | `b.addLibrary(.{ .linkage = .dynamic, … })` | gone | 0.15 | ZS-BUILD-06 |
| `exe.linkLibC(…)` | the same method on the `*Module`, or `.link_libc = true` in `createModule`; `linkSystemLibrary`, `addIncludePath` and `addCSourceFile` likewise | gone | 0.16 | ZS-BUILD-05 |
| `addRemoveDirTree` | nothing: a scratch directory is `b.addTempFiles()` or `b.tmpPath()`, deleted when the build succeeds | gone | 0.16 | ZS-MIG-01 |
| `b.args` | `run.addPassthruArgs()`, which makes the step uncached and keeps the arguments from the build script | gone | 0.17 | ZS-BUILD-07 |
| `b.build_root` | `b.root`, a `Cache.Path` | gone | 0.17 | ZS-MIG-01 |
| `.paths = &.{…}` | `.paths = b.pathList(&.{…})` in `b.addFmt`, and so for `.exclude_paths` | gone | 0.17 | ZS-BUILD-26 |
| `lazyDependency` | `b.dependency(name, args)`, which fetches a lazy package itself, or `try b.dependencyLazy(name, args)` to fetch several at once | alias | 0.17 | ZS-BUILD-13 |
| `b.reference_trace` | `zig build -freference-trace=n` | gone | 0.17 | ZS-COMPTIME-20 |
| `std.Build.LazyPath.getPath` | nothing: the configure phase resolves no path, so the `LazyPath` goes to the step that reads it; `getPath2`, `getPath3` and `getPath4` likewise | gone | 0.17 | ZS-MIG-01 |
| `std.Build.GeneratedFile` | nothing: a step's output is a `LazyPath` | gone | 0.17 | ZS-MIG-01 |
| `getDisplayName` | `{f}` on the `LazyPath` | alias | 0.17 | ZS-MIG-01 |
| `std.Build.LazyPath.basename` | nothing in std | gone | 0.17 | ZS-MIG-01 |
| `.cwd_relative` | `b.graph.cwdRelativePath(path)` | alias | 0.17 | ZS-MIG-01 |
| `b.dupe` | `b.graph.dupeString(s)`; `b.dupeStrings` and `b.dupePath` are `b.graph.dupeStrings` and `b.graph.dupePath` | alias | 0.17 | ZS-MIG-01 |
| `b.dupeStrings` | `b.graph.dupeStrings` | alias | 0.17 | ZS-MIG-01 |
| `b.dupePath` | `b.graph.dupePath` | alias | 0.17 | ZS-MIG-01 |
| `addArtifactArg` | `addArtifactArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addOutputFileArg` | `addOutputFileArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addFileContentArg` | `addFileContentArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addOutputDirectoryArg` | `addOutputDirectoryArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addDirectoryArg` | `addDirectoryArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addDecoratedDirectoryArg` | `addDecoratedDirectoryArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addDepFileOutputArg` | `addDepFileOutputArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addPrefixedOutputFileArg` | `addOutputFileArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addPrefixedFileContentArg` | `addFileContentArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addPrefixedOutputDirectoryArg` | `addOutputDirectoryArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addPrefixedDirectoryArg` | `addDirectoryArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addPrefixedDepFileOutputArg` | `addDepFileOutputArg2`, which takes `.{ .prefix, .suffix }` and, for a path, `.make_absolute` | alias | 0.17 | ZS-MIG-01 |
| `addFileArg` | `addFileArg2`, with `.prefix` for `addPrefixedFileArg`; the release notes deprecate both, and the source does not mark them | deprecated | 0.17 | ZS-MIG-01 |
| `runAllowFail` | `b.runFallible(…)` | alias | 0.17 | ZS-MIG-01 |
| `enableTestRunnerMode` | `run.enableProtocolMode()` | alias | 0.17 | ZS-MIG-01 |
| `b.findProgram(&…)` | `b.findProgramLazy(.{ .names = names })`, a `LazyPath`; `b.findProgram(.{ .names = names })` is a `?[]const u8` that poisons the configure cache | gone | 0.17 | ZS-MIG-01 |
| `addOptionPath` | an option naming a file: a directory is `addOptionPathDirectory`, and `addOptionPathUntracked` opts out of tracking | changed | 0.17 | ZS-BUILD-24 |
| `.include_guard_override` | `.include_guard` on a `ConfigHeader` | gone | 0.17 | ZS-MIG-01 |
| `addTranslateC` | the translate-c package: `zig fetch --save git+https://codeberg.org/ziglang/translate-c`, then `Translator.init(b.dependency("translate_c", .{}), .{ .c_source_file = … })`; the release notes deprecate it, and the source does not mark it | deprecated | 0.17 | ZS-INTEROP-15 |
| `addWin32ResourceFile` | nothing in std: the release notes move the resource APIs, `.win32_manifest`, `.rc_includes` and `Compile.out_filename` with it, to an external `rc` package | deprecated | 0.17 | ZS-MIG-01 |
| `--zig-lib-dir` | `--zig-lib=path` | gone | 0.17 | ZS-MIG-01 |
| `--global-cache-dir` | nothing; `--build-runner` and `--verbose-llvm-bc` likewise | gone | 0.17 | ZS-MIG-01 |
| `--build-runner` | nothing | gone | 0.17 | ZS-MIG-01 |
| `--verbose-llvm-bc` | nothing | gone | 0.17 | ZS-MIG-01 |
| `-Doptimize=ReleaseSafe` | `-Doptimize=safe`; `ReleaseFast` and `ReleaseSmall`, and `-O` likewise; the old names parse through the deprecated `Optimize.fromString` | alias | 0.17 | ZS-ASSERT-04 |
| `zig fetch` | without `--save`, a command that fills only the global cache: `zig fetch --save` and `zig build` fill `zig-pkg/` | changed | 0.17 | ZS-BUILD-12 |
| `.name = "…"` | `.name = .myproject` in `build.zig.zon`, an enum literal; `build.zig` still takes a string | gone | 0.14 | ZS-BUILD-09 |
| `std.tar.PipeOptions` | `std.tar.ExtractOptions` | alias | 0.16 | ZS-MIG-01 |
| `std.tar.pipeToFileSystem` | `std.tar.extract(io, dir, reader, options)`, which it is an alias of | alias | 0.16 | ZS-MIG-01 |
| `std.unicode.utf8Decode` | `std.unicode.Utf8View` to iterate, or `utf8ByteSequenceLength` and then `utf8Decode2`, `utf8Decode3` or `utf8Decode4` for one codepoint | alias | 0.14 | ZS-DATA-30 |
| `std.unicode.wtf8Decode` | `std.unicode.Wtf8View` to iterate, or `utf8ByteSequenceLength` and then `utf8Decode2`, `utf8Decode3AllowSurrogateHalf` or `utf8Decode4` | alias | 0.14 | ZS-DATA-31 |
| `std.zig.CrossTarget` | `std.Target.Query` | gone | 0.14 | ZS-INTEROP-18 |
| `std.Target.SubSystem` | `std.zig.Subsystem`; `builtin.subsystem` has no replacement | gone | 0.17 | ZS-INTEROP-18 |
| `std.math.sign` | the same name, now returning the narrowest integer that holds `-1`, `0` and `1`, not the argument's type | changed | 0.15 | ZS-DATA-33 |
| `std.zon.parse.fromSliceAlloc` | `std.zon.parse.fromSlice(T, .{ .gpa = gpa, .arena = arena, .source = source, .diagnostics = &diag })`, which allocates the result into `.arena`; the form that allocates nothing is `fromSliceNoAlloc` | gone | 0.17 | ZS-DATA-35 |
| `std.zon.parse.free` | nothing: the result lives in the arena `fromSlice` was given | gone | 0.17 | ZS-DATA-35 |
| `readAlloc` | `reader.readAllocAll` | alias | 0.17 | ZS-CONC-13 |
| `path.resolve` | `path.resolveAlloc` | alias | 0.17 | ZS-MIG-01 |
| `path.relative` | `path.relativeAlloc` | alias | 0.17 | ZS-MIG-01 |
| `path.resolvePosix` | `path.resolveAllocPosix` | alias | 0.17 | ZS-MIG-01 |
| `path.resolveWindows` | `path.resolveAllocWindows` | alias | 0.17 | ZS-MIG-01 |
| `path.relativePosix` | `path.relativeAllocPosix` | alias | 0.17 | ZS-MIG-01 |
| `path.relativeWindows` | `path.relativeAllocWindows` | alias | 0.17 | ZS-MIG-01 |
| `std.Uri.getHost` | `std.Io.net.HostName.fromUri(uri, &buffer)`, which validates the name | gone | 0.17 | ZS-CONC-38 |
| `std.gpu` | `std.spirv` | gone | 0.17 | ZS-MIG-01 |
| `isAARCH64` | `isAarch64` | alias | 0.17 | ZS-INTEROP-18 |
| `isMIPS` | `isMips` | alias | 0.17 | ZS-INTEROP-18 |
| `isMIPS32` | `isMips32` | alias | 0.17 | ZS-INTEROP-18 |
| `isMIPS64` | `isMips64` | alias | 0.17 | ZS-INTEROP-18 |
| `isPowerPC` | `isPowerpc` | alias | 0.17 | ZS-INTEROP-18 |
| `isPowerPC32` | `isPowerpc32` | alias | 0.17 | ZS-INTEROP-18 |
| `isPowerPC64` | `isPowerpc64` | alias | 0.17 | ZS-INTEROP-18 |
| `isRISCV` | `isRiscv` | alias | 0.17 | ZS-INTEROP-18 |
| `isSPARC` | `isSparc` | alias | 0.17 | ZS-INTEROP-18 |
| `isSpirV` | `isSpirv` | alias | 0.17 | ZS-INTEROP-18 |
| `isLoongArch` | `isLoongarch` | alias | 0.17 | ZS-INTEROP-18 |
| `isBSD` | a test of the tags you mean: `os.tag` has no `isBSD` replacement | alias | 0.17 | ZS-INTEROP-18 |
| `dupeZ` | `allocator.dupeSentinel(u8, s, 0)` | gone | 0.17 | ZS-INTEROP-10 |

```sh
rg -n -F -w \
  -e 'usingnamespace' \
  -e '@Type' \
  -e '@setCold' \
  -e '@fence' \
  -e '@setAlignStack' \
  -e 'callconv(.C)' \
  -e 'pub fn panic' \
  -e '@cImport' \
  -e '@intFromEnum' \
  -e '@enumFromInt' \
  -e '**' \
  -e 'void{}' \
  -e 'errdefer |err|' \
  -e 'i0' \
  -e '.linkage = .internal' \
  -e '.link_once' \
  -e 'enum(u8) {}' \
  -e '.@"struct".fields' \
  -e '.decls' \
  -e '.@"fn".params' \
  -e '.pointer.is_const' \
  -e 'std.builtin.Type.Error' \
  -e 'std.builtin.Type.StructField' \
  -e 'std.io' \
  -e 'std.io.GenericWriter' \
  -e 'std.io.GenericReader' \
  -e 'std.io.bufferedWriter' \
  -e 'std.io.bufferedReader' \
  -e 'std.io.fixedBufferStream' \
  -e 'std.io.getStdOut' \
  -e 'std.io.getStdErr' \
  -e 'std.io.getStdIn' \
  -e 'std.io.null_writer' \
  -e 'std.io.countingWriter' \
  -e 'std.io.CountingReader' \
  -e 'std.io.tty.detectConfig' \
  -e 'std.fifo.LinearFifo' \
  -e 'std.RingBuffer' \
  -e 'std.fmt.format' \
  -e 'std.fmt.FormatOptions' \
  -e 'std.fmt.Formatter' \
  -e 'std.fmt.formatType' \
  -e 'std.fmt.formatIntValue' \
  -e 'std.fmt.fmtSliceHexLower' \
  -e 'std.fmt.fmtDuration' \
  -e 'std.fmt.fmtIntSizeDec' \
  -e 'std.fmt.allocPrintZ' \
  -e '{D}' \
  -e 'std.fmt.allocPrint' \
  -e 'std.fmt.bufPrint' \
  -e 'std.fmt.bufPrintZ' \
  -e 'std.fs.cwd' \
  -e 'std.fs.Dir' \
  -e 'std.fs.File' \
  -e 'std.Io.File.OpenFlags' \
  -e 'std.fs.MAX_PATH_BYTES' \
  -e 'std.fs.path' \
  -e 'std.fs.max_path_bytes' \
  -e 'std.fs.max_name_bytes' \
  -e 'std.fs.base64_alphabet' \
  -e 'std.fs.base64_encoder' \
  -e 'std.fs.base64_decoder' \
  -e 'makeDir' \
  -e 'makePath' \
  -e 'makeOpenPath' \
  -e 'realpathAlloc' \
  -e 'std.fs.realpath' \
  -e 'getEndPos' \
  -e 'setAsCwd' \
  -e 'std.fs.openSelfExe' \
  -e 'std.fs.selfExePath' \
  -e 'std.fs.selfExeDirPath' \
  -e 'std.fs.getAppDataDir' \
  -e 'std.net' \
  -e 'mem.indexOf' \
  -e 'mem.indexOfPos' \
  -e 'mem.indexOfPosLinear' \
  -e 'mem.lastIndexOf' \
  -e 'mem.lastIndexOfLinear' \
  -e 'mem.indexOfScalar' \
  -e 'mem.indexOfScalarPos' \
  -e 'mem.lastIndexOfScalar' \
  -e 'mem.indexOfAny' \
  -e 'mem.indexOfAnyPos' \
  -e 'mem.lastIndexOfAny' \
  -e 'mem.indexOfNone' \
  -e 'mem.indexOfNonePos' \
  -e 'mem.lastIndexOfNone' \
  -e 'mem.indexOfDiff' \
  -e 'mem.indexOfSentinel' \
  -e 'mem.indexOfMin' \
  -e 'mem.indexOfMax' \
  -e 'mem.indexOfMinMax' \
  -e 'std.ascii.indexOfIgnoreCase' \
  -e 'std.mem.containsAtLeastScalar2' \
  -e 'std.mem.readPackedIntNative' \
  -e 'std.mem.writePackedIntNative' \
  -e 'std.mem.byteSwapAllFields' \
  -e 'std.mem.tokenize' \
  -e 'std.mem.split' \
  -e 'std.mem.page_size' \
  -e 'std.mem.copyForwards' \
  -e 'std.ArrayListUnmanaged' \
  -e 'std.ArrayListAligned' \
  -e 'std.array_list.Managed' \
  -e 'std.BoundedArray' \
  -e 'std.ArrayHashMap' \
  -e 'std.AutoArrayHashMap' \
  -e 'std.StringArrayHashMap' \
  -e 'std.ArrayHashMapUnmanaged' \
  -e 'std.AutoArrayHashMapUnmanaged' \
  -e 'std.StringArrayHashMapUnmanaged' \
  -e 'std.SegmentedList' \
  -e 'std.TailQueue' \
  -e 'std.ComptimeStringMap' \
  -e 'std.heap.MemoryPoolAligned' \
  -e 'std.heap.memory_pool.Managed' \
  -e '.initEmpty()' \
  -e 'IntegerBitSet' \
  -e 'ArrayBitSet' \
  -e 'StaticBitSet' \
  -e 'DynamicBitSetUnmanaged' \
  -e 'DynamicBitSet' \
  -e 'getLastOrNull' \
  -e 'getLast' \
  -e 'std.heap.GeneralPurposeAllocator' \
  -e 'std.heap.DebugAllocator' \
  -e 'std.heap.Check' \
  -e 'std.heap.ThreadSafeAllocator' \
  -e 'std.heap.stackFallback' \
  -e 'std.process.argsAlloc' \
  -e 'std.process.getEnvMap' \
  -e 'std.process.getEnvVarOwned' \
  -e 'std.posix.getenv' \
  -e 'std.process.hasEnvVar' \
  -e 'std.ChildProcess' \
  -e 'std.process.Child.init' \
  -e 'std.process.Child.run' \
  -e 'std.process.execv' \
  -e 'std.process.spawnPath' \
  -e 'std.Thread.Mutex' \
  -e 'std.Thread.Condition' \
  -e 'std.Thread.ResetEvent' \
  -e 'std.Thread.Semaphore' \
  -e 'std.Thread.RwLock' \
  -e 'std.Thread.Futex' \
  -e 'std.Thread.WaitGroup' \
  -e 'std.Thread.Pool' \
  -e 'std.once' \
  -e 'std.time.Timer' \
  -e 'std.time.Instant' \
  -e 'std.time.timestamp' \
  -e 'std.time.sleep' \
  -e 'std.crypto.random' \
  -e 'std.posix.getrandom' \
  -e 'crypto_always_getrandom' \
  -e 'std.rand' \
  -e 'std.testing.refAllDeclsRecursive' \
  -e 'std.debug.captureStackTrace' \
  -e 'std.debug.dumpStackTraceFromBase' \
  -e 'std.debug.walkStackWindows' \
  -e 'std.debug.StackIterator' \
  -e 'std.debug.runtime_safety' \
  -e 'std.meta.Int' \
  -e 'std.meta.Tuple' \
  -e 'std.meta.declList' \
  -e 'std.meta.fields' \
  -e 'std.meta.declarationInfo' \
  -e 'std.meta.fieldInfo' \
  -e 'std.meta.fieldNames' \
  -e 'std.meta.intToEnum' \
  -e 'std.builtin' \
  -e 'std.builtin.OptimizeMode' \
  -e '.Debug' \
  -e '.ReleaseSafe' \
  -e '.ReleaseFast' \
  -e '.ReleaseSmall' \
  -e 'builtin.mode' \
  -e 'builtin.cpu' \
  -e 'builtin.os' \
  -e 'builtin.abi' \
  -e 'builtin.object_format' \
  -e 'addStaticLibrary' \
  -e 'addSharedLibrary' \
  -e 'addRemoveDirTree' \
  -e 'b.args' \
  -e 'b.build_root' \
  -e 'lazyDependency' \
  -e 'b.reference_trace' \
  -e 'std.Build.LazyPath.getPath' \
  -e 'std.Build.GeneratedFile' \
  -e 'getDisplayName' \
  -e 'std.Build.LazyPath.basename' \
  -e '.cwd_relative' \
  -e 'b.dupe' \
  -e 'b.dupeStrings' \
  -e 'b.dupePath' \
  -e 'addArtifactArg' \
  -e 'addOutputFileArg' \
  -e 'addFileContentArg' \
  -e 'addOutputDirectoryArg' \
  -e 'addDirectoryArg' \
  -e 'addDecoratedDirectoryArg' \
  -e 'addDepFileOutputArg' \
  -e 'addPrefixedOutputFileArg' \
  -e 'addPrefixedFileContentArg' \
  -e 'addPrefixedOutputDirectoryArg' \
  -e 'addPrefixedDirectoryArg' \
  -e 'addPrefixedDepFileOutputArg' \
  -e 'runAllowFail' \
  -e 'enableTestRunnerMode' \
  -e '.include_guard_override' \
  -e '--zig-lib-dir' \
  -e '--global-cache-dir' \
  -e '--build-runner' \
  -e '--verbose-llvm-bc' \
  -e '-Doptimize=ReleaseSafe' \
  -e 'std.tar.PipeOptions' \
  -e 'std.tar.pipeToFileSystem' \
  -e 'std.unicode.utf8Decode' \
  -e 'std.unicode.wtf8Decode' \
  -e 'std.zig.CrossTarget' \
  -e 'std.Target.SubSystem' \
  -e 'std.zon.parse.fromSliceAlloc' \
  -e 'std.zon.parse.free' \
  -e 'readAlloc' \
  -e 'path.resolve' \
  -e 'path.relative' \
  -e 'path.resolvePosix' \
  -e 'path.resolveWindows' \
  -e 'path.relativePosix' \
  -e 'path.relativeWindows' \
  -e 'std.Uri.getHost' \
  -e 'std.gpu' \
  -e 'isAARCH64' \
  -e 'isMIPS' \
  -e 'isMIPS32' \
  -e 'isMIPS64' \
  -e 'isPowerPC' \
  -e 'isPowerPC32' \
  -e 'isPowerPC64' \
  -e 'isRISCV' \
  -e 'isSPARC' \
  -e 'isSpirV' \
  -e 'isLoongArch' \
  -e 'isBSD' \
  -e 'dupeZ' \
  .
```

## Reading the table

### ZS-MIG-01 [M] Write 0.17 spellings; check an unfamiliar std symbol against the local std

Never emit a `std.*` symbol from memory of an older Zig: the 0.13 to 0.16 spellings are the single
largest source of wrong Zig, and many of them still compile. Look a signature up in the installed
std source before typing it. A row with no topical rule is this rule's.

**Why:** an `alias` row compiles and a `changed` row compiles and means something else, so
`zig build` passing proves nothing about whether the code is current.

**Check:** the command after the table over the diff; each hit is a row, and its 0.17 column is the
rewrite. `rg -n 'containsAtLeastScalar\(' src/` and `rg -n 'mem\.eql\(f(16|32|64|80|128),' src/`
find the calls two `changed` rows of this rule's say to re-read. Every `std.*` signature new to the
diff must be findable by `rg -n` in the local std tree (`zig env` names it); one that is not is
misremembered, not merely misspelled.

```sh
# GOOD — the only reliable check. Run it, don't recall it.
grep -rn "pub fn takeDelimiter" "$(zig env | grep std_dir)"/Io/Reader.zig
```

### ZS-MIG-02 [M] Run the command after the table over code no build analyses

A `gone` spelling survives a passing build wherever the compiler never analysed it: a function
nothing references, a file the module root does not import, or a `builtin.target.os.tag` branch for
a target the build does not compile. Run the command after the table over the whole tree, not only
over what the build touched. A `gone` method the table keys by its type's path,
`std.Build.LazyPath.getPath`, is called there on a value, `lazy_path.getPath(b)`, which names no
type a fixed string can see: read that code for those rows.

**Why:** Zig analyses lazily, so `zig build` reports a removed name only in code it reaches; the
rest waits for the first caller, often on another platform and long after the migration.

**Check:** a hit of the command on a `gone` row in a tree whose build passes is code no build
analysed; rewrite it to the row's 0.17 column, or delete it if nothing calls it.

### ZS-MIG-03 [M!] Fail the build on a spelling the table marks `alias`

Add a CI step that runs the command after the table and fails on a hit, pin the toolchain for real —
`.minimum_zig_version` is documentation only, so use a pinned CI version and the
`comptime builtin.zig_version` guard (ZS-BUILD-29, ZS-BUILD-33) — and treat a toolchain bump as a
migration with its own review. One spelling over-matches: `.Debug` also finds a tag of your own
enum, and the fix is to rename the tag, not to drop the row.

*Relaxed form:* no CI gate; the same command runs by hand before each release, and an `alias` in a
file you are already editing is fixed in that diff.

**Why:** an `alias` never fails a build, so on a long-lived codebase they accumulate until an
upgrade deletes them all at once and the diff is too large to review. A gate turns that big-bang
migration into a per-change cost.

**Check:** the CI workflow runs the command after the table and fails on a hit — its exit status
checked, not swallowed by `|| true`. Run it once by hand when adding it: a hit means the gate is
being added to a tree that already fails it, and those hits are the first commit.

## Decided by tools

The compiler rejects each of these on its own; no setting turns one off.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| zig | `invalid builtin function: …` | error | a builtin 0.17 no longer has: `@setCold`, `@Type`, `@fence`, `@setAlignStack`, `@cImport` |
