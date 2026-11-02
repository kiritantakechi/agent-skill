# build.zig, build.zig.zon, project layout, CI

Everything about how a Zig 0.17.0 project is *assembled*: the build graph (`build.zig`), the package
manifest (`build.zig.zon`), where files go on disk, which optimize mode ships, and what CI must run.

This chapter does not own language-level style (`references/naming.md`, `references/data.md`,
`references/errors.md`), allocator discipline (`references/memory.md`), `std.Io`
(`references/concurrency.md`), what goes *inside* `src/constants.zig` (`references/assertions.md`
ZS-ASSERT-21), or how to write a test or a fuzz target (`references/testing.md`) — only how tests
get *wired into the build*. The rename table for older build spellings is `references/migration.md`
ZS-MIG-11.

Every `zig` block here is `build.zig` code and assumes the file opens with
`const std = @import("std");`; every `zon` block is a `build.zig.zon` fragment.

The single highest-value baseline is the output of `zig init` on 0.17.0. Most of the build-system
advice on the internet predates it and is a hard compile error today. When in doubt, run `zig init`
in a scratch directory and diff.

## Contents

- **Canonical build.zig**
  - ZS-BUILD-01 [M] Every project exposes install, run, test, fmt, and check steps
  - ZS-BUILD-02 [M] Put `target` and `optimize` on the module, never on the artifact
  - ZS-BUILD-03 [M] `b.addModule` for the public API, `b.createModule` for everything else
  - ZS-BUILD-04 [M] Give any module you intend to `addTest` an explicit `.target`
  - ZS-BUILD-05 [M] One `addTest` per module — a lib+exe project needs at least two
  - ZS-BUILD-06 [M] Linking, C sources, and include paths are `Module` methods
  - ZS-BUILD-07 [M] Build libraries with `b.addLibrary(.{ .linkage = ... })`
  - ZS-BUILD-08 [S] Forward the `--` arguments with `addPassthruArgs()` on every runnable step
  - ZS-BUILD-09 [S] `installArtifact` only what ships; use `addInstallArtifact` for on-demand builds
- **build.zig.zon**
  - ZS-BUILD-10 [M] `.name` is an enum literal, not a string
  - ZS-BUILD-11 [M] Never hand-write, copy, or edit `.fingerprint`
  - ZS-BUILD-12 [M] `.paths` lists exactly what ships, because it defines the package hash
  - ZS-BUILD-13 [M] Add dependencies with `zig fetch --save`; never type a hash by hand
  - ZS-BUILD-14 [S] Mark optional dependencies `.lazy = true`; `b.dependency` fetches them
  - ZS-BUILD-15 [M] Consume a dependency as `b.dependency(...).module(...)` and fetch it in CI
- **Project layout**
  - ZS-BUILD-16 [M] `src/root.zig` is the module root and the entire public surface
  - ZS-BUILD-17 [M] Reference every source file from the module root, or its tests never run
  - ZS-BUILD-18 [M!] The limits file is `src/constants.zig`, at the module root, in `.paths`
  - ZS-BUILD-19 [S] Keep `tests/`, `tools/`, `examples/`, and `scripts/` outside `src/`
  - ZS-BUILD-20 [M] Build tools and scripts target `b.graph.host`, never `target`
  - ZS-BUILD-21 [M] Gitignore `.zig-cache/`, `zig-out/`, and `zig-pkg/`
  - ZS-BUILD-22 [M] Count the encapsulation a module boundary costs, not only what it buys
  - ZS-BUILD-23 [M] Keep the module graph directed, because the compiler will not
  - ZS-BUILD-24 [S] Give the directory and the module the same name
- **Build modes**
  - ZS-BUILD-25 [M!] Production builds are `safe` unless a measurement says otherwise
  - ZS-BUILD-26 [S] Know what `.preferred_optimize_mode` takes away before you set it
- **Options and cross-compilation**
  - ZS-BUILD-27 [S] Inject build-time configuration as one generated `build_options` module
  - ZS-BUILD-28 [S] Declare every knob with `b.option`, and whitelist targets when the set is fixed
- **Tooling and CI**
  - ZS-BUILD-29 [M] `zig fmt --check` gates CI, and `--ast-check` rides along
  - ZS-BUILD-30 [S] Add a `check` step whose artifacts are never installed or run
  - ZS-BUILD-31 [M] Cross-compiled test steps set `skip_foreign_checks`
  - ZS-BUILD-32 [M] Pin the Zig version in CI; gate on fmt, two optimize modes, and a cross matrix
  - ZS-BUILD-33 [S] Write automation as `scripts/*.zig`, wired into `build.zig`
  - ZS-BUILD-34 [M!] Justify every dependency; default to none
- **Strictness, toolchain pinning, and backends**
  - ZS-BUILD-35 [M] There is no `-Wall`; the strictest-setting rule translates to six concrete gates
  - ZS-BUILD-36 [S] Hard-error on a toolchain mismatch with a `comptime builtin.zig_version` guard
  - ZS-BUILD-37 [S] Leave the codegen backend and linker alone; know what the three flags cost
- **The program's own interfaces: CLI and config files**
  - ZS-BUILD-38 [M] Hand-roll CLI parsing; std has no argument parser
  - ZS-BUILD-39 [S] `.zon` is a usable project config format, not just `build.zig.zon`

---

## Canonical build.zig

### ZS-BUILD-01 [M] Every project exposes install, run, test, fmt, and check steps

A `build.zig` is the project's user interface. `zig build`, `zig build test`, `zig build fmt`, and
`zig build check` must work in every repository, with no README-only incantations. `check` is the
step ZLS runs for build-on-save diagnostics (ZS-BUILD-30).

**Why:** `zig build --list-steps` is the only discovery mechanism a newcomer or a CI job has. A step
that exists only as a shell command in a README is a step that rots.

**Check:** `zig build --list-steps` lists at least `install`, `run`, `test`, `fmt`, `check`; and no
`b.step(...)` handle is created without something depending on it.

```zig
// verified — GOOD: complete: `zig build`, `zig build test`, `zig build test-integration`
// `zig build fmt`, `zig build check`, `zig build run -- args`,
// `zig build test -Dtarget=x86_64-linux-musl`
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const test_filters = b.option(
        []const []const u8,
        "test-filter",
        "Skip tests that do not match any of these filters",
    ) orelse &.{};

    // Build-time configuration, importable as `@import("build_options")`.
    const options = b.addOptions();
    options.addOption([]const u8, "version", "0.1.0");
    options.addOption(bool, "trace", b.option(bool, "trace", "Emit trace logs") orelse false);

    // Public module: consumers reach this via `dep.module("myproj")`.
    const lib_mod = b.addModule("myproj", .{
        .root_source_file = b.path("src/root.zig"),
        .target = target, // required so `b.addTest` can build it
        .optimize = optimize,
    });
    lib_mod.addOptions("build_options", options);

    // Private module: the CLI. Never exported to consumers.
    const exe_mod = b.createModule(.{
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
        .imports = &.{.{ .name = "myproj", .module = lib_mod }},
    });

    const exe = b.addExecutable(.{ .name = "myproj", .root_module = exe_mod });
    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    run_cmd.addPassthruArgs();
    b.step("run", "Run the CLI").dependOn(&run_cmd.step);

    // ONE test binary per module (ZS-BUILD-05). Unit tests hang off `test`.
    const test_step = b.step("test", "Run unit tests");

    const lib_tests = b.addTest(.{ .root_module = lib_mod, .filters = test_filters });
    const run_lib_tests = b.addRunArtifact(lib_tests);
    run_lib_tests.skip_foreign_checks = true;
    test_step.dependOn(&run_lib_tests.step);

    const exe_tests = b.addTest(.{ .root_module = exe_mod, .filters = test_filters });
    const run_exe_tests = b.addRunArtifact(exe_tests);
    run_exe_tests.skip_foreign_checks = true;
    test_step.dependOn(&run_exe_tests.step);

    // Integration tests get their OWN step, so `zig build test` stays fast
    // (ZS-BUILD-05). CI runs both steps.
    const integration_tests = b.addTest(.{
        .name = "integration",
        .filters = test_filters,
        .root_module = b.createModule(.{
            .root_source_file = b.path("tests/integration.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{.{ .name = "myproj", .module = lib_mod }},
        }),
    });
    const run_integration = b.addRunArtifact(integration_tests);
    run_integration.skip_foreign_checks = true;
    const integration_step = b.step("test-integration", "Run integration tests");
    integration_step.dependOn(&run_integration.step);

    // Host-only build tool: `b.graph.host`, never `target`.
    const codegen = b.addExecutable(.{
        .name = "codegen",
        .root_module = b.createModule(.{
            .root_source_file = b.path("tools/codegen.zig"),
            .target = b.graph.host,
            .optimize = .debug,
        }),
    });
    b.step("codegen", "Regenerate tables").dependOn(&b.addRunArtifact(codegen).step);

    // Formatting gate. Explicit paths, so `zig-pkg/` is never scanned.
    b.step("fmt", "Check source formatting").dependOn(&b.addFmt(.{
        .paths = b.pathList(&.{ "build.zig", "build.zig.zon", "src", "tests", "tools" }),
        .check = true,
    }).step);

    // `check` step for editor build-on-save: these artifacts are never installed
    // and never run, so the build system passes `-fno-emit-bin` and only analyzes.
    const check_step = b.step("check", "Semantic check only, no binary emitted");
    check_step.dependOn(&b.addExecutable(.{
        .name = "myproj-check",
        .root_module = exe_mod,
    }).step);
    check_step.dependOn(&b.addTest(.{ .root_module = lib_mod }).step);
}
```

### ZS-BUILD-02 [M] Put `target` and `optimize` on the module, never on the artifact

`addExecutable`/`addLibrary`/`addObject`/`addTest` take exactly one shape field:
`root_module: *Module`. `root_source_file`, `target`, and `optimize` are fields of
`Module.CreateOptions`.

**Why:** compilation settings are per-module in 0.17 — a single artifact can link modules built at
different optimize levels or with different `link_libc`. Hanging them off the artifact would make
that inexpressible. The artifact-level spelling is a hard compile error, not a deprecation.

**Check:** `.root_source_file`, `.target`, or `.optimize` appearing inside an `addExecutable`,
`addLibrary`, `addObject`, or `addTest` argument literal instead of inside the `createModule` /
`addModule` literal it belongs to.

```zig
// rejected — zig: no field named 'root_source_file' in struct 'Build.ExecutableOptions'
const exe = b.addExecutable(.{
    .name = "myproj",
    .root_source_file = b.path("src/main.zig"), // error: no field named 'root_source_file'
    .target = target,
    .optimize = optimize,
});
```

```zig
// fragment — GOOD
const exe = b.addExecutable(.{
    .name = "myproj",
    .root_module = b.createModule(.{
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
    }),
});
```

### ZS-BUILD-03 [M] `b.addModule` for the public API, `b.createModule` for everything else

`b.addModule(name, opts)` registers a module under `name` so downstream packages can reach it with
`dep.module(name)`. `b.createModule(opts)` produces an anonymous module that never escapes this
package. A library module built with `createModule` makes the package unusable as a dependency:
`dep.module("myproj")` panics with `unable to find module "myproj"` at configure time.

**Why:** the set of names passed to `addModule` *is* your package's published API. Registering the
CLI's private root module there silently commits you to supporting `@import("myproj_cli")` forever.

**Check:** count the `b.addModule(` calls in `build.zig` — each name is one you have committed to
supporting. A CLI, benchmark, or test-only root registered with `addModule`, or the library module
built with `createModule`, is the finding.

```zig
// fragment — GOOD
const lib_mod = b.addModule("myproj", .{ // published: consumers can @import("myproj")
    .root_source_file = b.path("src/root.zig"),
    .target = target,
});
const exe_mod = b.createModule(.{ // private: nobody outside this build.zig sees it
    .root_source_file = b.path("src/main.zig"),
    .target = target,
    .optimize = optimize,
    .imports = &.{.{ .name = "myproj", .module = lib_mod }},
});
```

### ZS-BUILD-04 [M] Give any module you intend to `addTest` an explicit `.target`

`Module.CreateOptions.target` is `?ResolvedTarget = null`. A module created without one cannot be
the root module of a `Step.Compile`.

**Why:** `b.addModule` for a pure library is often written without `.target` because the artifact
was going to supply it — but `b.addTest(.{ .root_module = lib_mod })` makes that module *the root*,
and a root module must know its target.

**Check:** for every `b.addTest(.{ .root_module = m })`, find where `m` was created and confirm the
literal contains `.target =`. A module reached only through `.imports` may omit it; a module that is
ever a root may not.

### ZS-BUILD-05 [M] One `addTest` per module — a lib+exe project needs at least two

A test binary collects `test` blocks from exactly **one** module: the one passed as `.root_module`.
There is no aggregate "test everything" artifact and no way to add a second root to a `Step.Compile`
— the count of `addTest` calls *is* the count of modules under test. Every module that contains
tests needs its own `addTest`, its own `addRunArtifact`, and a `dependOn` from a step you actually
invoke. This is the owning rule for test wiring.

The full checklist for each module that has tests:

1. `b.addTest(.{ .root_module = mod, .filters = test_filters })` — pass `filters` so `-Dtest-filter`
   reaches every binary, not just the first.
2. `b.addRunArtifact(t)` — `addTest` alone only *compiles*; without a run artifact nothing executes.
3. `run.skip_foreign_checks = true` (ZS-BUILD-31), or the cross matrix breaks.
4. `dependOn` from `test` for unit tests, and from a separate step for the slow ones, as
   ZS-BUILD-01's `test-integration` does.

**Why:** this is the most commonly missed trap in 0.17 build scripts. `zig build test` reports
"success" with a subset of your tests silently never compiled, so a broken `src/main.zig` test
passes CI.

**Check:** `zig build test --summary all` prints one `run test` line per test binary. Count them
against the number of modules in `build.zig`; a missing line is a module whose tests never ran.

```zig
// fragment — BAD: main.zig's tests never run, and `zig build test` still says success
const test_step = b.step("test", "Run tests");
test_step.dependOn(&b.addRunArtifact(b.addTest(.{ .root_module = lib_mod })).step);
```

```zig
// fragment — GOOD
const test_step = b.step("test", "Run tests");
test_step.dependOn(&b.addRunArtifact(b.addTest(.{ .root_module = lib_mod })).step);
test_step.dependOn(&b.addRunArtifact(b.addTest(.{ .root_module = exe_mod })).step);
```

A module reached only as an `.imports` entry of another module is **not** covered by that module's
test binary — imports supply declarations, not test blocks. Each imported module still needs its own
`addTest`. So every extra module costs one more test binary, and is worth it where you want an
`@import` boundary: a different compilation setting (target, optimize, `link_libc`,
`single_threaded`) or a separately publishable API. Organizing folders is what files are for.

### ZS-BUILD-06 [M] Linking, C sources, and include paths are `Module` methods

`Step.Compile` has no `linkLibC`, `linkLibrary`, `linkSystemLibrary`, `addIncludePath`,
`addCSourceFile(s)`, `addObjectFile`, `addLibraryPath`, `addRPath`, `addFrameworkPath`, `addCMacro`,
or `addModule`. All of these moved to `Module`. Calling one on the artifact is a hard error:
`error: no field or member function named 'linkLibC' in 'Build.Step.Compile'`.

**Why:** linking is a property of the translation unit that needs the symbols, and the module is
that unit. The artifact spelling fails to compile, so this is a checklist, not a silent hazard.

**Check:** any of those method names called on the result of `addExecutable`/`addLibrary`/`addTest`
(`exe.linkLibC()`, `lib.addIncludePath(...)`) rather than on a `*Module`.

```zig
// fragment — GOOD
const mod = b.createModule(.{
    .root_source_file = b.path("src/main.zig"),
    .target = target,
    .optimize = optimize,
    .link_libc = true, // preferred: set it at creation
});
mod.addIncludePath(b.path("vendor/include"));
mod.addCSourceFile(.{ .file = b.path("vendor/shim.c"), .flags = &.{"-std=c11"} });
mod.addImport("myproj", lib_mod); // post-creation equivalent of `.imports`
```

### ZS-BUILD-07 [M] Build libraries with `b.addLibrary(.{ .linkage = ... })`

`b.addStaticLibrary` and `b.addSharedLibrary` do not exist in 0.17.

**Why:** static vs dynamic is one field, not two entry points; the rest of `LibraryOptions` is
identical either way.

**Check:** any `b.addStaticLibrary(` or `b.addSharedLibrary(` — both are gone. And any
`b.addLibrary` call with no `.linkage`: the field defaults to `.static`, so omitting it hides which
kind of library the project ships.

```zig
// fragment — GOOD
const lib = b.addLibrary(.{
    .name = "myproj",
    .linkage = .static, // or .dynamic
    .root_module = lib_mod,
});
b.installArtifact(lib);
```

### ZS-BUILD-08 [S] Forward the `--` arguments with `addPassthruArgs()` on every runnable step

`run.addPassthruArgs();` on run steps, so `zig build run -- --verbose foo` works. Since 0.17
`build.zig` cannot see the arguments after `--` at all (`b.args` is gone): `addPassthruArgs()`
appends them when the step runs, and marks the step as having side effects, so it is never cached.

**Why:** without it the only way to pass arguments is to build, then find the binary under
`zig-out/`, which defeats the point of having a `run` step and makes scripted invocation
position-dependent.

**Check:** every `b.addRunArtifact` whose step a user invokes by name — `run`, `bench`, `script:*` —
has an `.addPassthruArgs()` call beside it.

### ZS-BUILD-09 [S] `installArtifact` only what ships; use `addInstallArtifact` for on-demand builds

`b.installArtifact(x)` attaches `x` to the default step, so a bare `zig build` produces it.
Examples, benchmarks, and fuzz drivers should hang off their own step via
`b.addInstallArtifact(x, .{})`.

**Why:** every installed artifact is on the critical path of `zig build`, which is what CI and
`zig build run` invoke. A repository with ten examples installed by default takes ten times as long
to smoke-test.

**Check:** count `b.installArtifact(` calls against the artifacts the project actually ships. An
example, benchmark, or fuzz driver among them is the finding — it belongs on
`b.addInstallArtifact(x, .{})` under its own step.

```zig
// fragment — GOOD
const examples_step = b.step("examples", "Build examples");
examples_step.dependOn(&b.addInstallArtifact(example_exe, .{}).step);
```

---

## build.zig.zon

### ZS-BUILD-10 [M] `.name` is an enum literal, not a string

`.name = .myproj`. A string is `error: expected enum literal`.

**Why:** the manifest is ZON and the name is an identifier in the package namespace, not free text.
It also means the name must be a valid Zig identifier — no dashes.

**Check:** the `.name` line in `build.zig.zon` starts with `.` and carries no quotes, no dash, and
no `zig`. A quoted name is `error: expected enum literal`.

```zon
// fragment — GOOD: build.zig.zon — annotated with what each field actually does
.{
    // Enum literal, so it must be a valid Zig identifier: no dashes, no "zig".
    .name = .myproj,
    // Semver. Read by tooling; the compiler does not enforce ordering.
    .version = "0.0.0",
    // Generated once by the compiler; never hand-written (ZS-BUILD-11).
    .fingerprint = 0x53faee2adc55a83f, // Changing this has security and trust implications.
    // DOCUMENTATION ONLY — on 0.17.0, `.minimum_zig_version = "0.99.0"`
    // builds with no error and no warning, in the root package and in
    // dependencies alike. The compiler never reads it; `mlugg/setup-zig` does,
    // resolving the toolchain from it when the workflow omits `version`. Real
    // enforcement is a pinned CI version (ZS-BUILD-32) plus, for a project that
    // pins an exact toolchain, the comptime guard in ZS-BUILD-36.
    .minimum_zig_version = "0.17.0",
    .dependencies = .{},
    // Defines the package hash and is all a consumer receives (ZS-BUILD-12).
    .paths = .{ "build.zig", "build.zig.zon", "src", "LICENSE" },
}
```

Do not include "zig" in the name — it is already inside the Zig package namespace.

### ZS-BUILD-11 [M] Never hand-write, copy, or edit `.fingerprint`

Generate it once by deleting the field and running `zig build`; the compiler prints the value to
use. Keep the `// Changing this has security and trust implications.` comment so a diff to the line
is visible in review. Regenerate it when you fork a still-maintained upstream; leave it alone when
you are shipping a new version of your own package.

Mechanics on 0.17.0:

- Omitting the field: `error: missing top-level 'fingerprint' field; suggested value: 0xee480fa3...`
- A wrong value:
  `error: invalid fingerprint: 0x0; if this is a new or forked package, use this value: ...`
- The **upper 32 bits are derived from `.name`**. Renaming a package therefore invalidates its
  fingerprint: changing `.name = .dep_lib` to `.name = .greet` produces
  `error: invalid fingerprint: 0x865e348439423c53; ... use this value: 0x2df8175b4880850c`. Take the
  compiler's suggestion; never patch the old value back.

**Why:** `(name, fingerprint)` is the globally unique package identity used to decide that package B
is an *updated version of* package A. Copying another project's fingerprint into your fork claims to
*be* that project — the manifest template calls this a **hostile** fork.

**Check:** any diff that touches the `.fingerprint` line at all. The only legitimate ones take the
value the compiler suggested after a fork or a rename and say so in the commit message, and the
`// Changing this has security and trust implications.` comment survives the edit.

### ZS-BUILD-12 [M] `.paths` lists exactly what ships, because it defines the package hash

Only files and directories listed in `.paths` are hashed, and only those remain on disk when a
consumer fetches your package. `.paths` is mandatory.

**Why:** a file you forgot to list is *absent* for consumers, so a `b.path(...)` outside `.paths`
works locally and fails for everyone else. Listing `tests/`, `benchmarks/`, or `assets/` changes the
hash and forces every consumer to re-fetch, for bytes they never compile.

**Check:** every path `build.zig` names with `b.path(...)`, plus every `@import`ed `.zon` or data
file, falls under some entry in `.paths`; and `tests`, `benchmarks`, `examples`, and `assets` appear
under none of them.

```zon
// fragment — GOOD: build.zig.zon — compilation inputs plus the license, nothing else
.paths = .{ "build.zig", "build.zig.zon", "src", "LICENSE" },
```

### ZS-BUILD-13 [M] Add dependencies with `zig fetch --save`; never type a hash by hand

`zig fetch --save git+https://example.com/org/repo.git#v1.2.3` or
`zig fetch --save=<key> <url|path>`. A bare `zig fetch <url>` only fills the global cache: it edits
no manifest and writes nothing under `zig-pkg/`. `zig fetch --save` also validates the fetched
package's own manifest, so a dependency with a bad fingerprint is rejected at add time rather than
at build time.

The hash format, unchanged in 0.17, is `<package-name>-<semver>-<base64url-multihash-digest>` (e.g.
`greet-1.0.0-DIWASNwRAAAiYiTzYBauCrU29xQHKjJV4iCRwITHgElY`), computed over the fetched tree *after
applying that package's own `.paths`*.

When you change a dependency's `url`, **delete its `hash` first**. Leaving the old hash asserts that
the new URL serves the old bytes, and you get a mismatch error instead of an update.

Git refs are selected with `#`: `git+https://github.com/org/repo#tag-or-branch-or-sha`. Prefer a tag
or a full SHA; a branch name makes the fetch non-reproducible until the hash pins it.

**Why:** there is no way to derive the hash by inspection, and the hash — not the URL — is the
source of truth; the manifest comments call the URL "one of many possible mirrors".

**Check:** a `build.zig.zon` diff in which a `.hash` line changed while its neighbouring `.url`
changed too, with the hash not matching the `<name>-<semver>-<digest>` shape `zig fetch --save`
emits — that is a hand-carried hash. Also a `.url` whose `#` ref is a bare branch name.

### ZS-BUILD-14 [S] Mark optional dependencies `.lazy = true`; `b.dependency` fetches them

Mark any dependency behind a feature flag or an optional target `.lazy = true` in `build.zig.zon`,
and reach it with `b.dependency(name, args)` only on the branch that needs it. To require several
lazy packages in one configure run, call `b.dependencyLazy` for each before `try`-ing any of them,
from a `build` that returns `!void`.

`b.dependency` handles a lazy package itself: when it is missing, configure exits, the package is
fetched, and `build.zig` runs again — once per missing package. `dependencyLazy` returns
`error.LazyDependencyNeeded` instead, so one fetch covers every package the run marked.
`b.lazyDependency` (`?*Dependency`) is deprecated in favour of it.

**Why:** a lazy package is downloaded only when a configure run asks for it, so users who never
enable the feature never fetch it.

**Check:** cross-reference `.dependencies` against `build.zig` — a dependency used only behind a
`b.option` or a target condition must be `.lazy = true` and reached inside that branch, not before
it. A remaining `b.lazyDependency(` is the deprecated spelling.

```zig
// fragment — GOOD
// `build` returns `!void`. Both are marked before either is `try`-ed, so one fetch covers them.
const tls = b.dependencyLazy("tls", .{ .target = target, .optimize = optimize });
const zstd = b.dependencyLazy("zstd", .{ .target = target, .optimize = optimize });
exe_mod.addImport("tls", (try tls).module("tls"));
exe_mod.addImport("zstd", (try zstd).module("zstd"));
```

### ZS-BUILD-15 [M] Consume a dependency as `b.dependency(...).module(...)` and fetch it in CI

The anonymous-struct argument to `b.dependency`/`b.dependencyLazy` is that package's own `-D`
options, forwarded to its `build.zig`. `dep.module(name)` looks up a name the dependency registered
with `b.addModule`, and `dep.artifact(name)` a name it passed to `installArtifact`. Both **panic at
configure time** on a typo — `unable to find module "x"` — rather than returning an error.

**Why:** a dependency built at the default target will not link into a cross-compiled artifact, so
`.target` and `.optimize` must be forwarded. A wrong name is a build-script crash, not a link
failure.

**Check:** every string passed to `dep.module(...)`/`dep.artifact(...)` matches a name that
dependency registers with `b.addModule`/`b.installArtifact`, every `b.dependency`/`b.dependencyLazy`
call forwards `.target` and `.optimize`, and CI has a `zig build --fetch` step of its own.

```zig
// fragment — GOOD: end to end
const greet_dep = b.dependency("greet", .{ .target = target, .optimize = optimize });
exe_mod.addImport("greet", greet_dep.module("greet"));
```

`zig build --fetch` resolves the whole tree and exits; `--fetch=all` also pulls lazy dependencies.
Run it as its own CI step so "dependency resolution failed" is distinguishable from "the code
broke". `--fork=<path>` overrides one project in the dependency tree with a local checkout without
editing the manifest — use it for bisecting an upstream bug, never in committed CI.

---

## Project layout

### ZS-BUILD-16 [M] `src/root.zig` is the module root and the entire public surface

Consumers can only reach declarations reachable from the root source file. Re-export everything
public from `root.zig`; anything not re-exported is private by construction.

**Why:** Zig has no `pub(crate)` and no export lists — the reachability graph from the module root
*is* the visibility system. This makes the public API a single reviewable file, and it means adding
a file under `src/` does not silently widen your API.

**Check:** `git ls-files 'src/*.zig'` against the `pub` declaration chain from `root.zig` — a type
the README tells consumers to use that is not reachable from `root.zig` is the finding. And
`src/main.zig` reaches the library as `@import("myproj")`, never as `@import("root.zig")`.

```zig
//! Public API surface of the `myproj` module. Anything a consumer may touch is
//! re-exported here; files not reachable from this file are private.
// fragment — GOOD: src/root.zig
const std = @import("std");

pub const constants = @import("constants.zig");
pub const Parser = @import("parser.zig").Parser;
pub const version = @import("build_options").version;
```

`src/main.zig` is the CLI root module and imports the library by name (`@import("myproj")`), not by
path. Keeping business logic out of `main.zig` is what makes the library independently testable and
embeddable.

### ZS-BUILD-17 [M] Reference every source file from the module root, or its tests never run

Wiring a module into the `test` step (ZS-BUILD-05) is necessary but not sufficient. A `test` block
in a file reached only through a *lazily-analyzed* declaration is **not collected**. End `root.zig`
with a `comptime` block that imports every such file by name. This is the owning rule for
source-file reachability.

On 0.17.0 with `root.zig` (1 test) + `parser.zig` (2 tests), reached only via
`pub const P = @import("parser.zig").P;`:

| Bottom of `root.zig` | Result |
|---|---|
| nothing | `1 pass (1 total)` — both of `parser.zig`'s tests silently skipped |
| `comptime { _ = @import("parser.zig"); }` | `3 pass (3 total)` |
| `test { _ = @import("parser.zig"); }` | `4 pass (4 total)` — the anonymous `test` block is itself a test |
| `test { std.testing.refAllDecls(@This()); }` | `4 pass (4 total)` |

**Why:** Zig analyses container-level declarations lazily, so a re-export in `root.zig` that nothing
uses never resolves its `@import`, and that file's tests do not exist. The failure is silent and
*inverted*: the suite goes green while coverage goes down.

**Check:** every `.zig` file under `src/` appears either in a `pub` declaration chain from
`root.zig` *or* in the root's `comptime` import block. `git ls-files 'src/*.zig'` versus that block
is a one-line diff review.

```zig
// fragment — GOOD: bottom of src/root.zig
comptime {
    // Test blocks in files reachable only through a lazily-analyzed decl are NOT
    // collected. Reference them explicitly. `comptime` rather than `test` so the
    // block does not inflate the test count with an empty test.
    _ = @import("parser.zig");
    _ = @import("constants.zig");
}
```

`std.testing.refAllDecls(@This())` also collects them, but it is a compile smoke test that names no
file (ZS-TEST-22), so it hides which files you meant to cover. Prefer the explicit imports.

### ZS-BUILD-18 [M!] The limits file is `src/constants.zig`, at the module root, in `.paths`

The *placement* half of the centralized-limits rule: one file named `constants.zig`, directly under
`src/`, re-exported from `root.zig` as `pub const constants = @import("constants.zig");`, listed in
`.paths` (ZS-BUILD-12), and referenced from the root's `comptime` import block (ZS-BUILD-17) so its
`comptime` cross-checks are always analysed. What goes *in* the file is `references/assertions.md`
ZS-ASSERT-21.

**`[M!]` trigger:** high-reliability code — a database, consensus layer, allocator, crypto
primitive, parser on untrusted input, or embedded firmware, where an unbounded queue means
corruption rather than a slow request. *Relaxed form:* elsewhere, the file still sits at
`src/constants.zig`, re-exported and in `.paths`; naming it in the `comptime` import block, which is
what guarantees its cross-checks run, becomes optional.

**Why:** omitted from `.paths`, the file is absent for consumers and its import fails only
downstream; unreachable from `root.zig`, its `comptime` cross-checks silently never run
(ZS-BUILD-17); re-exported, the project's bounds become reviewable public surface (ZS-BUILD-16).

**Check:** exactly one `src/constants.zig`, covered by an entry in `.paths`, and named in both
`root.zig`'s re-exports and its `comptime` import block. Whether every limit lives in it is
ZS-ASSERT-21's check.

```zig
// fragment — GOOD: src/root.zig
pub const constants = @import("constants.zig");

comptime {
    _ = @import("constants.zig"); // so its comptime cross-checks are analysed
}
```

The limits in it are named per `references/naming.md` ZS-NAME-06.

### ZS-BUILD-19 [S] Keep `tests/`, `tools/`, `examples/`, and `scripts/` outside `src/`

`src/` is the shipped package. Everything else lives beside it and is excluded from `.paths`.

**Why:** consumers never download your benchmark corpus (ZS-BUILD-12), and integration tests that
`@import("myproj")` by module name exercise the *published* API — the only way to notice that you
forgot to re-export something.

**Check:** `ls src/` shows no `tests`, `tools`, `examples`, `scripts`, or benchmark directory, and
`.paths` names none of them; every file under `tests/` imports the package by module name rather
than with a `../src/` relative path.

```
myproj/
  build.zig
  build.zig.zon
  .gitignore          # .zig-cache/  zig-out/  zig-pkg/
  LICENSE  README.md
  src/
    root.zig          # public module root; re-exports the API
    main.zig          # CLI root module; @import("myproj")
    constants.zig     # every _max limit
    parser.zig …      # internal, reachable only through root.zig
  tests/
    integration.zig   # own test binary; imports "myproj" by name
  tools/
    codegen.zig       # host-only build tool
  scripts/
    release.zig       # automation, in Zig
  examples/
    basic.zig         # built by `zig build examples`, not installed
```

### ZS-BUILD-20 [M] Build tools and scripts target `b.graph.host`, never `target`

Anything the build itself executes — code generators, asset packers, release scripts — must be built
for the host.

**Why:** `zig build -Dtarget=wasm32-wasi` would otherwise try to *run* a WASI binary as part of the
build and fail. `b.graph.host` is a `ResolvedTarget` for the machine running `zig build`, so the
cross-compile matrix in CI keeps working.

**Check:** every artifact that is fed to `b.addRunArtifact` *during the build* — codegen, asset
packers, release scripts — has `.target = b.graph.host` in its module literal. A `.target = target`
on one of them breaks the moment somebody passes `-Dtarget=`.

```zig
// fragment — GOOD
const codegen = b.addExecutable(.{
    .name = "codegen",
    .root_module = b.createModule(.{
        .root_source_file = b.path("tools/codegen.zig"),
        .target = b.graph.host,
        .optimize = .debug,
    }),
});
```

### ZS-BUILD-21 [M] Gitignore `.zig-cache/`, `zig-out/`, and `zig-pkg/`

`zig init` writes no `.gitignore`. All three directories are generated. `zig build` and
`zig fetch --save` unpack dependencies **into the build root** at
`<build-root>/zig-pkg/<name>-<ver>-<hash>/`, not only into the global cache; a bare `zig fetch`
fills only the global cache.

**Why:** a `.gitignore` that names only the first two lets the first `zig build` stage the project's
entire dependency tree for commit.

**Check:** `.gitignore` names all three directories, and
`git ls-files | grep -E 'zig-pkg|zig-out|\.zig-cache'` returns nothing.

```gitignore
.zig-cache/
zig-out/
zig-pkg/
```

### ZS-BUILD-22 [M] Count the encapsulation a module boundary costs, not only what it buys

Everything across the boundary must become `pub`. A seam that exports a handful of declarations is a
seam, and one that exports dozens is the wrong seam, however much an `@import` boundary is wanted
there (ZS-BUILD-05).

**Why:** inside one module a file can keep its helpers unexported; promoting it to a module converts
those internals into public surface — for a separately published module, surface that outside code
may depend on and that you then owe compatibility for.

**Check:** list the declarations the split forces to `pub`. Would each be exported on its own
merits?

### ZS-BUILD-23 [M] Keep the module graph directed, because the compiler will not

`@import` cycles compile. Two modules that import each other are one module wearing two names, and
merging them is the fix.

**Why:** two files that import each other are accepted — Zig resolves the cycle and the test binary
passes — so nothing in the build tells you the boundary is fictional, and the layering has to be
maintained deliberately.

**Check:** draw the `@import` graph across module roots. Any pair pointing both ways is a merge, not
a boundary.

### ZS-BUILD-24 [S] Give the directory and the module the same name

**Why:** the `b.addModule` name, the directory, and the `@import` string then agree, so one grep
finds every mention and a rename is one operation. When they differ, every reader carries the
mapping.

**Check:** does the source tree read as the module list in `build.zig`?

---

## Build modes

### ZS-BUILD-25 [M!] Production builds are `safe` unless a measurement says otherwise

Ship `-Doptimize=safe`. Choosing `fast` or `small` requires a benchmark in the commit message or a
comment naming the constraint.

**`[M!]` trigger:** high-reliability code — databases, storage engines, consensus, allocators,
crypto, parsers on untrusted input, embedded control — where a wrong answer is worse than a crash.
There, `safe` *is* the shipping mode and a release artifact built any other way is a defect.
*Relaxed form:* elsewhere — CLI tools, games, compression kernels, build-time tools, application
code — `fast` or `small` is allowed, but only with the benchmark number or the named constraint
recorded at the `-Doptimize=` site, and only once the assertion question is answered: either the
module does not lean on `std.debug.assert` for anything a user can trigger, or it uses the always-on
helper of `references/assertions.md` ZS-ASSERT-05.

What each mode keeps:

| Mode | Runtime safety checks | Optimization | `std.debug.assert` |
|---|---|---|---|
| `debug` | all (overflow, bounds, `unreachable`, alignment, bad casts) | none; fast builds | live |
| `safe` | all | full | live |
| `fast` | **none** — they become UB | full | **assumed true**; UB if false |
| `small` | **none** | for size | **assumed true**; UB if false |

`std.debug.assert` calls `unreachable`, and `unreachable` is a safety check: it panics in `debug`
and `safe` builds, and is *illegal behavior* in `fast` and `small` builds. TigerBeetle ships `safe`
builds.

Two honest caveats: `safe` costs real throughput on bounds-heavy inner loops, and a *library* does
not choose its consumer's optimize mode — a library should be correct in all four and document which
invariants it asserts rather than dictating a mode.

If you cannot pay the cost of `safe`, the escape hatch is a project-local always-on assert —
`references/assertions.md` ZS-ASSERT-05 owns that helper and its contract. Do not adopt TigerStyle's
assertion density while shipping `fast` builds with no such helper: the code then reads as if it is
checked and none of it is.

**Why:** a `fast` build does not merely disable your assertions — it turns each one into a licence
for the optimizer to assume the condition, so an assertion that would have caught corruption becomes
the mechanism by which corrupt state is optimized into arbitrary behavior.

**Check:** the release command in CI or the release script names an explicit `-Doptimize=`; if it
names `fast` or `small`, the same commit contains a benchmark number or a one-line comment naming
the constraint. `rg -n 'ReleaseFast|ReleaseSmall' .github/ build.zig scripts/` finds the TitleCase
spellings, which 0.17 still parses.

### ZS-BUILD-26 [S] Know what `.preferred_optimize_mode` takes away before you set it

`b.standardOptimizeOption(.{ .preferred_optimize_mode = .safe })` **removes `-Doptimize=` entirely**
and replaces it with a `-Drelease=[bool]` flag: `zig build -Doptimize=safe` then fails with
`error: invalid option: "optimize"`, followed by
`info: available option: "release": optimize for end users`. With a preferred mode set,
`std.Build.standardOptimizeOption` returns `.debug` unless `-Drelease` / `--release` is passed, in
which case it returns the preferred mode — you cannot select `fast` at all, and even
`--release=fast` builds the preferred mode. Default to plain `b.standardOptimizeOption(.{})` and
pass `-Doptimize=safe` explicitly when producing release artifacts.

Bare `--release` against a project with no declared preference exits 1 with
`the project does not declare a preferred optimization mode.` followed by
`choose: --release=fast, --release=safe, or --release=small`.

**Why:** the option is a two-way switch, not a default. That is right for an application whose
release command you control (TigerBeetle uses it), and wrong for a library whose CI wants a
`[debug, safe, fast]` matrix.

**Check:** `rg -n 'preferred_optimize_mode' build.zig`. If it is set, no README line, CI workflow,
or release script in the repository may pass `-Doptimize=` — that flag does not exist in that
project, and every such invocation exits 1.

---

## Options and cross-compilation

### ZS-BUILD-27 [S] Inject build-time configuration as one generated `build_options` module

`b.addOptions()` → `opts.addOption(T, name, value)` → `mod.addOptions("build_options", opts)`, then
`@import("build_options")` in source. `opts.addOptionPath(name, lazy)` records a generated file's
path, which is how you hand a codegen output to source code; since 0.17 a directory takes
`addOptionPathDirectory`, and `addOptionPathUntracked` opts out of dependency tracking.

**Why:** the generated module is real Zig with real types, so a typo is a compile error and the
values are `comptime`-known — `if (build_options.trace)` costs nothing when false. The alternatives
(parsing env vars at runtime, or `-D` macros through C) lose both properties.

**Check:** every `@import("build_options")` in `src/` is matched by a `b.addOptions()` /
`mod.addOptions("build_options", …)` pair in `build.zig`; a value read from an environment variable
at startup that is in fact fixed at build time is the finding.

```zig
// fragment — GOOD: build.zig
const options = b.addOptions();
options.addOption([]const u8, "version", "0.1.0");
options.addOption(bool, "trace", b.option(bool, "trace", "Emit trace logs") orelse false);
lib_mod.addOptions("build_options", options);
```

```zig
// fragment — GOOD: src/log.zig
const std = @import("std");
const build_options = @import("build_options");

pub fn trace(comptime fmt: []const u8, args: anytype) void {
    if (!build_options.trace) return; // comptime-folded away when disabled
    std.log.debug(fmt, args);
}
```

### ZS-BUILD-28 [S] Declare every knob with `b.option`, and whitelist targets when the set is fixed

`b.option(T, name, description) ?T` registers the flag in `zig build --help`. Pass
`.whitelist = &.{...}` to `standardTargetOptions` when you genuinely support only some targets.

`standardTargetOptions` registers `-Dtarget=`, `-Dcpu=`, `-Dofmt=`, and `-Ddynamic-linker=`.
`-Dcpu=` takes a CPU model optionally followed by `+feature`/`-feature` — `-Dcpu=x86_64_v3`,
`-Dcpu=baseline+avx2-sse4a`, `-Dcpu=native`. Use `baseline` for portable release binaries and a
named microarchitecture level only when you also gate on it at runtime; `native` must never appear
in a build that ships.

**Why:** `--help` is the contract. An undeclared knob read from the environment is invisible to
consumers and to CI. And a whitelist turns "we never tested s390x" from a mystery bug report into an
up-front rejection with the list of supported triples.

**Check:** `zig build --help` lists every knob the build reads, each with a description. A value the
build script pulls from an environment variable instead of a `b.option(` call is the finding, as is
a `-Dcpu=native` in a release script.

```zig
// fragment — GOOD
const target = b.standardTargetOptions(.{ .whitelist = &.{
    .{ .cpu_arch = .x86_64, .os_tag = .linux, .abi = .musl },
    .{ .cpu_arch = .aarch64, .os_tag = .linux, .abi = .musl },
    .{ .cpu_arch = .aarch64, .os_tag = .macos },
} });
```

---

## Tooling and CI

### ZS-BUILD-29 [M] `zig fmt --check` gates CI, and `--ast-check` rides along

Non-negotiable. Run `zig fmt --check --ast-check` over your own sources, excluding generated and
fetched directories. A file containing `var x: u8 = 1; _ = x;` passes `zig fmt --check` (exit 0) and
fails `zig ast-check` with `error: local variable is never mutated / note: consider using 'const'`.

Two traps:

- `zig fmt --check .` **descends into `zig-pkg/`** and will fail your build on a *dependency's*
  formatting. Use `--exclude zig-pkg --exclude .zig-cache`, or list paths explicitly.
- `b.addFmt` has **no** `ast-check` option — the command line it runs, built in
  `lib/zig/compiler/Maker/Step/Fmt.zig` since 0.17, only ever appends `--check`, paths, and
  excludes. The `zig build fmt` step and the CI `--ast-check` run are two different checks; do both.

**Why:** `zig fmt` is canonical — there is no style bikeshed to have, so a formatting diff in review
is pure waste. `--ast-check` runs AstGen over each file and catches a real class of defect that
formatting alone does not.

**Check:** the CI formatting step names both `--check` and `--ast-check`, and passes
`--exclude zig-pkg --exclude .zig-cache` or an explicit path list. A bare `zig fmt --check .` is the
finding; so is a workflow whose only formatting gate is `zig build fmt`, which cannot ast-check.

```bash
zig fmt --check --ast-check --exclude zig-pkg --exclude .zig-cache .
```

What `zig fmt` decides, and the trailing comma that is your one lever over it, are
`references/naming.md` ZS-NAME-24; the 100-column limit it cannot enforce is ZS-NAME-25.

### ZS-BUILD-30 [S] Add a `check` step whose artifacts are never installed or run

ZLS auto-detects a top-level step named `check` for build-on-save diagnostics, though the 0.17.0
release notes say ZLS does not yet work with 0.17.0. `Step.Compile` creates `generated_bin` lazily,
and the build system's maker process (`lib/zig/compiler/Maker/Step/Compile.zig` since 0.17) passes
`-fno-emit-bin` when nobody ever asked for the binary. Adding `b.installArtifact(check_exe)` makes
the flag disappear and the speedup with it.

**Why:** it is a real speedup, not a naming convention: a duplicate `addExecutable` that is neither
installed nor run does semantic analysis only — no LLVM, no codegen, no link.

**Check:** the artifacts the `check` step depends on appear in no `b.installArtifact` and no
`b.addRunArtifact` call anywhere in `build.zig`. Either one puts the binary back and takes the
speedup with it.

```zig
// fragment — GOOD
const check_step = b.step("check", "Semantic check only, no binary emitted");
check_step.dependOn(&b.addExecutable(.{ .name = "myproj-check", .root_module = exe_mod }).step);
check_step.dependOn(&b.addTest(.{ .root_module = lib_mod }).step);
```

Use the same Zig and ZLS minor version. For 0.17.0 there is none yet, so build-on-save waits for a
ZLS release that supports it; `zig build check` on the command line works today.

### ZS-BUILD-31 [M] Cross-compiled test steps set `skip_foreign_checks`

`zig build test -Dtarget=<foreign>` fails by default with
`error: the host system ... is unable to execute binaries from the target ...`. Set
`run_step.skip_foreign_checks = true;` on every test run step. With the flag, the compile succeeds
and the run reports `skipped`:
`+- run test skipped / +- compile test debug x86_64-linux-musl success`. For targets you want to
actually execute, enable an emulator at the CLI instead: `-fqemu`, `-fwasmtime`, `-frosetta`,
`-fwine`, `-fdarling`, plus `--libc-runtimes <path>` for dynamic glibc/musl under QEMU.

**Why:** you still want the *compile* half of the cross-compile matrix — that is where
target-specific type errors, missing translated-C symbols, and `usize` width assumptions show up.

**Check:** count `skip_foreign_checks = true;` assignments against the number of `b.addRunArtifact`
calls over `b.addTest` results — the two counts must match. Running
`zig build test -Dtarget=<foreign-triple>` locally is the same check, executed.

### ZS-BUILD-32 [M] Pin the Zig version in CI; gate on fmt, two optimize modes, and a cross matrix

Never `latest` — it will move to 0.18 and break everything at once, in a PR that changed a comment.

The rules, which `assets/ci.yml` applies:

1. **Pin the exact Zig version.** Never `latest`, never `master`, never a range.
2. **Gate on `zig fmt --check --ast-check`** with `zig-pkg` and `.zig-cache` excluded (ZS-BUILD-29).
3. **Run the suite in `debug` and `safe`** (ZS-TEST-25), with `--summary all` so a cached no-op is
   distinguishable from a real pass.
4. **Cross-compile matrix**: build *and* `zig build test` each supported triple. The test binaries
   compile and the runs report `skipped`, which is the whole point (ZS-BUILD-31).
5. **The cache key must include every matrix axis.** With one shared key all matrix legs fight over
   one cache entry and each evicts the others.

**Why:** a Zig minor release is a breaking release. Pinning turns "the toolchain moved" into a
deliberate one-line commit with its own CI run, and `safe` alongside `debug` catches UB that only
manifests under a release memory layout while keeping safety checks armed.

```yaml
# fragment — illustrative only, not a workflow to copy wholesale.
# Verify the action names and versions yourself; only the `run:` lines are rules.
- run: zig fmt --check --ast-check --exclude zig-pkg --exclude .zig-cache .
- run: zig build --fetch                  # dependency resolution as its own step
- run: zig build test -Doptimize=${{ matrix.optimize }} --summary all
- run: zig build test -Dtarget=${{ matrix.target }} --summary all
# cache-key must name every axis, e.g. ${{ matrix.os }}-${{ matrix.optimize }}
```

**Check:** the workflow contains a literal `0.17.0` (or whatever you pin) and no `latest`; the
cache-key expression mentions every `matrix.*` key the job declares.

Locally, `zig build --watch --debounce 100` re-runs the graph on save. `-fincremental` enables
incremental compilation, and the 0.17.0 release notes say `zig build -fincremental --watch` now
works for most `x86_64-linux` projects — read ZS-BUILD-37 before turning it on, because on ELF it
switches to the new linker, which is still off by default.

### ZS-BUILD-33 [S] Write automation as `scripts/*.zig`, wired into `build.zig`

Replace `scripts/release.sh` with `scripts/release.zig` behind a `zig build script:release` step.
Draw the line at *any script CI depends on* — those must be Zig. Genuinely local one-liners can stay
shell: a Zig script needs a compile step, so a three-line `curl | jq` becomes a 40-line program.

**Why:** a Zig script is cross-platform, type-checked, and runs identically on every developer's
machine instead of hitting a Bash/coreutils/OS-version difference. It can also `@import` your own
modules, so release tooling shares the project's constants and parsers.

**Check:** every script a CI workflow invokes is a `.zig` file behind a `b.step`. A `.sh`, a `.py`,
or a multi-line inline `run:` block that CI depends on is the finding.

```zig
// fragment — GOOD: build.zig
const script = b.addExecutable(.{
    .name = "release",
    .root_module = b.createModule(.{
        .root_source_file = b.path("scripts/release.zig"),
        .target = b.graph.host,
        .optimize = .debug,
    }),
});
const run_script = b.addRunArtifact(script);
run_script.addPassthruArgs();
b.step("script:release", "Cut a release").dependOn(&run_script.step);
```

### ZS-BUILD-34 [M!] Justify every dependency; default to none

TigerStyle mandates a **zero-dependency policy** apart from the Zig toolchain itself. Treat that as
the default and require a written justification — in the commit that adds it — for each entry in
`.dependencies`.

**`[M!]` trigger:** a database, consensus layer, allocator, crypto library, or embedded firmware —
anything whose dependency cost is multiplied across everything built on top of it. *Relaxed form:*
elsewhere, dependencies are allowed but each is a reviewed decision — few, small, pinned to a tag or
SHA, optional ones marked `.lazy = true`, and no unaccounted transitive package. The full breakdown
is below.

It is a *policy choice*, not a law of the language, and the countervailing costs are real. Zig's
package manager is content-addressed: the `hash`, not the URL, is the source of truth, `.paths`
constrains what is fetched, and `zig build --fetch` gives reproducible offline builds — which
neutralizes a good part of the classic supply-chain argument. Re-implementing a well-tested TLS
stack or Zstd decoder yourself is usually *worse* for correctness than depending on one.

Recommendation by tier:

- **[M!] high-reliability code** (database, consensus, allocator, crypto, embedded firmware): zero
  runtime dependencies. Vendor with `.path` if you must, so the source sits in your repo and in
  review.
- **[S] everything else**: dependencies are allowed, but each is a reviewed decision. Prefer few,
  small, and pinned to a tag or SHA (ZS-BUILD-13); mark optional ones `.lazy = true` (ZS-BUILD-14);
  and never take a transitive tree you have not read — `zig build --fetch`, then read `zig-pkg/`.
- Build-time and test-only dependencies are cheaper than runtime ones, but they still execute on
  your developers' and CI machines. Hold them to the same bar.

**Why:** each dependency is supply-chain, safety and performance risk you did not audit, and a
slower install; for foundational infrastructure, that cost is multiplied across everything built on
top of you.

**Check:** every entry in `.dependencies` traces to a commit whose message says what it replaces and
why writing it yourself was rejected. After `zig build --fetch`, every directory under `zig-pkg/` is
one somebody named — a transitive package nobody can account for is the finding.

---

## Strictness, toolchain pinning, and backends

### ZS-BUILD-35 [M] There is no `-Wall`; the strictest-setting rule translates to six concrete gates

TigerStyle says to appreciate, from day one, all compiler warnings at the compiler's strictest
setting. Zig has **no warnings and no warning flags** for Zig code — a diagnostic is either a
compile error or it does not exist. Do not go looking for `-Wall`, `-Wextra`, `-Werror`, `#pragma`s,
or a lint level; there is nothing to turn up. What the rule honestly translates to on 0.17.0 is
these six, all of which belong in CI:

| Gate | Command / setting | Catches |
|---|---|---|
| Compile errors are already fatal | `zig build test` | everything the frontend can prove |
| Canonical formatting | `zig fmt --check` (ZS-BUILD-29) | formatting drift; **not** semantics |
| AstGen-level defects | `zig ast-check` (ZS-BUILD-29) | unused/never-mutated locals, unreachable code |
| Runtime safety armed in release | `-Doptimize=safe` (ZS-BUILD-25) | overflow, bounds, bad casts, `unreachable` |
| Comptime failure chains | `zig build -freference-trace=N` | *which* instantiation produced the error |
| Actual C warnings | `-Wall -Wextra -Werror` in `addCSourceFile` flags | everything C's frontend has to say |

The two places where you *do* still have a dial are (a) any C you compile through the Zig build
system, where Clang's full warning machinery is live and off by default, and (b) safety checks,
which `fast` and `small` builds remove.

`--verbose` variants (`--verbose-cc`, `--verbose-link`, `--verbose-llvm-ir`) are diagnostics for the
build, not for your code; they are not part of this.

On 0.17.0:

- `zig build-exe --help` lists no `-W*` flag of any kind. `-Wall`/`-Werror` reach Clang only via
  `zig cc` or a `flags` array on a C source.
- `mod.addCSourceFile(.{ .file = …, .flags = &.{ "-std=c11", "-Wall", "-Wextra", "-Werror" } })`
  turns an unused C local into `error: unused variable 'unused'` and fails `zig build`.
- `-freference-trace` is real and load-bearing: the default output truncates the instantiation chain
  with `5 reference(s) hidden; use '-freference-trace=7' to see all references`, and passing the
  flag prints the whole chain from `main` down. Since 0.17 only the command line sets it for the
  build graph: the `b.reference_trace` field, which TigerBeetle sets to 10, is gone
  (`no field named 'reference_trace' in struct 'Build'`), so pass `zig build -freference-trace=10`.

**Why:** C needs warning levels because its default is to accept nearly anything; Zig moved that
entire category into hard errors, so "strictest setting" is already at maximum for Zig code.
Pretending Zig has a `-Wall` leads people to add imaginary flags instead of the gates that exist.

```zig
// fragment — GOOD: build.zig — the two knobs that actually exist
pub fn build(b: *std.Build) void {
    // Full comptime instantiation chains on every error: `zig build -freference-trace=10`.
    // Since 0.17 the command line is the only place that sets it.

    const mod = b.createModule(.{
        .root_source_file = b.path("src/main.zig"),
        .target = b.standardTargetOptions(.{}),
        .optimize = b.standardOptimizeOption(.{}),
        .link_libc = true,
    });
    // Zig code has no warning flags. C code compiled by this build does.
    mod.addCSourceFile(.{
        .file = b.path("vendor/shim.c"),
        .flags = &.{ "-std=c11", "-Wall", "-Wextra", "-Werror" },
    });
    b.installArtifact(b.addExecutable(.{ .name = "myproj", .root_module = mod }));
}
```

**Check:** every `addCSourceFile`/`addCSourceFiles` call in `build.zig` has `-Werror` in its
`flags`; CI runs `zig ast-check` as well as `zig fmt --check`; and nobody has invented a `-Wall`.

### ZS-BUILD-36 [S] Hard-error on a toolchain mismatch with a `comptime builtin.zig_version` guard

When your project pins one exact Zig version, put the check in `build.zig` where it fires before
anything else. `.minimum_zig_version` cannot do this: it is documentation, not enforcement. The
compiler never reads it, so `"0.99.0"` builds clean on 0.17.0 (ZS-BUILD-10's annotated manifest).
`builtin.zig_version` is a `std.SemanticVersion` and is comptime-known inside `build.zig`, so the
whole check costs nothing.

**Why:** a Zig minor release is a breaking release, so the failure mode without a guard is a wall of
unrelated compile errors deep in std, from which nobody deduces "you are on the wrong toolchain".
The guard converts that into one sentence naming both versions.

**When it is appropriate:** a project that pins an exact toolchain — an application with a
reproducible release process, a high-reliability service, anything with a vendored or Nix-pinned
compiler. TigerBeetle does exactly this. **When `.minimum_zig_version` is enough:** a *library*,
where a hard equality check makes your package unusable in any dependency tree whose root is on a
different patch release. A library should compile across the whole minor version and let the
consumer pin.

```zig
// verified — GOOD: with `.patch = 1` this is
// `error: unsupported zig version: expected 0.17.1, found 0.17.0`
const builtin = @import("builtin");
const std = @import("std");

/// The exact toolchain this project is developed and released against.
const zig_version_required: std.SemanticVersion = .{ .major = 0, .minor = 17, .patch = 0 };

comptime {
    const v = builtin.zig_version;
    if (v.order(zig_version_required) != .eq) @compileError(std.fmt.comptimePrint(
        "unsupported zig version: expected {f}, found {f}",
        .{ zig_version_required, v },
    ));
}
```

Note the `{f}`, not `{}`: `SemanticVersion` has a custom `format` method, and in 0.17 only `{f}`
dispatches to it (`references/output.md`). Use `.order(...) != .eq` for an exact pin; use
`.order(...) == .lt` if you want a floor rather than a pin.

**Check:** `rg -n 'zig_version' build.zig` — a project that claims a pinned toolchain in its README
or CI has this block, and its version literal matches the one CI installs.

### ZS-BUILD-37 [S] Leave the codegen backend and linker alone; know what the three flags cost

Ship the defaults unless you have a measurement, and never turn on `-fincremental` or `-fnew-linker`
in a build whose artifacts you ship.

Read off 0.17.0 (with `@compileLog(@import("builtin").zig_backend)`, `--verbose-link`, and the ELF
section table of the produced binaries):

| Setting | Behavior on 0.17.0 | Do |
|---|---|---|
| `debug` on `x86_64-linux-{gnu,musl}` | `.stage2_x86_64` — the **self-hosted** backend is the default, linked by the legacy self-hosted ELF linker | leave alone; this is the fast-build path |
| `debug` on aarch64-linux / x86_64-macos / aarch64-macos / x86_64-windows / wasm32-wasi | `.stage2_llvm` | leave alone |
| Any `safe`/`fast` build, incl. x86_64-linux | `.stage2_llvm` | leave alone; release codegen is LLVM everywhere |
| `-fllvm` / `exe.use_llvm = true` | forces LLVM (x86_64-linux `debug` flips to `.stage2_llvm`, linked by LLD) | only to bisect a suspected self-hosted-backend bug |
| `-fno-llvm` | forces self-hosted | avoid; on aarch64-macos a hello-world did not finish within 90 seconds |
| `-fnew-linker` / `exe.use_new_linker = true` | emits DWARF and `.eh_frame`; off by default and not yet at feature parity | do not ship |
| `-fincremental` | opt-in, off by default, and **implies the new ELF linker** | local iteration only, never in CI or a release |
| LLVM loop vectorization | **disabled in 0.17.x** (LLVM 22) | do not micro-tune vector loops against these numbers |

Every linker emits full debug information. Building `pub fn main() void {}` for `x86_64-linux-gnu`
on 0.17.0 and dumping the section headers:

```text
default:           .debug_abbrev .debug_aranges .debug_info .debug_line .debug_line_str
                   .debug_loc .debug_loclists .debug_pubnames .debug_pubtypes .debug_ranges
                   .debug_rnglists .debug_str  + .eh_frame .eh_frame_hdr
-fnew-linker:      .debug_abbrev .debug_addr .debug_info .debug_line .debug_line_str .debug_loc
                   .debug_pubnames .debug_pubtypes .debug_ranges .debug_rnglists .debug_str
                   .debug_str_offsets  + .eh_frame .eh_frame_hdr
-fincremental:     (identical to -fnew-linker — it selects that linker on ELF)
```

So `-fincremental` costs no debugging information, but it still selects a linker that is off by
default: a fine trade for a save-recompile loop, and not one to make for a binary you ship.

> [!NOTE] The new ELF linker is off by default, and the default under `-fincremental`. A plain
> `zig build-exe -target x86_64-linux-gnu` uses the self-hosted `.stage2_x86_64` backend and the
> legacy self-hosted ELF linker (`--verbose-link` prints `zig ld`), with full DWARF.

LLVM loop vectorization is off in 0.17 (`references/performance.md` ZS-PERF-15).

All three are `?bool` fields on `Step.Compile` (`use_llvm`, `use_lld`, `use_new_linker`), assigned
after `addExecutable` returns; `use_llvm` and `use_lld` can also be passed in `ExecutableOptions`,
and none of them is a field of `Module`.

**Why:** the self-hosted backends and the new ELF linker are large, fast, and incomplete; the 0.17.0
release notes say the new linker is not yet at feature parity with the legacy one, which is why it
stays off by default.

**Check:** `rg -n 'use_new_linker|use_llvm|use_lld|fincremental|fnew-linker' build.zig .github/`
returns nothing, or every hit has a comment saying why and is confined to a local-only step.

---

## The program's own interfaces: CLI and config files

### ZS-BUILD-38 [M] Hand-roll CLI parsing; std has no argument parser

`std.process.Init` hands you `args`; nothing in std turns them into flags. There is no argument
parser anywhere in `std`, and `std.process.Args` offers only `iterate()`, `iterateAllocator(gpa)`,
and `toSlice(arena)`. Write the loop yourself: a `while` over the slice, `std.mem.eql` for exact
flags, `std.mem.cutPrefix` for `--name=value`, an explicit `--` terminator, and `std.process.fatal`
for usage errors.

Parsed arguments as a **second parameter of `main`** have been discussed upstream
(ziglang/zig#24510) and do not exist in 0.17. **Do not anticipate them**: code written against a
guessed API is not early, it is wrong.

Three details that are easy to get wrong:

- `init.minimal.args.toSlice(arena)` returns `[]const [:0]const u8` — sentinel-terminated elements,
  because they may be handed to a `execve`-shaped API. Match that type in your signatures.
- **`std.process.fatal` has no exit-code and no writer parameter**: it logs an error and exits 1,
  with the signature `references/errors.md` ZS-ERR-01's table gives.
- `argv[0]` is the program name. Start the loop at index 1.

**Why:** the shape of the answer is so obvious that a model will confidently invent
`std.process.argsParse`, `std.cli`, or a second `main` parameter, and none of them exist — the
single highest-risk gap in the 0.17 std for generated code.

```zig
// verified — GOOD
const std = @import("std");

const Cli = struct {
    verbose: bool = false,
    output: ?[]const u8 = null,
    limit: u32 = 16,
    /// Everything after `--`, plus any non-flag operands.
    rest: []const [:0]const u8 = &.{},
};

const usage =
    \\usage: myproj [--verbose] [--output=PATH] [--limit=N] [--] [FILE...]
;

fn parseArgs(argv: []const [:0]const u8) Cli {
    var cli: Cli = .{};
    var i: usize = 1; // argv[0] is the program name
    while (i < argv.len) : (i += 1) {
        const arg = argv[i];
        if (std.mem.eql(u8, arg, "--")) {
            cli.rest = argv[i + 1 ..]; // everything after `--` is an operand, even "-x"
            return cli;
        } else if (std.mem.eql(u8, arg, "--verbose") or std.mem.eql(u8, arg, "-v")) {
            cli.verbose = true;
        } else if (std.mem.cutPrefix(u8, arg, "--output=")) |value| {
            if (value.len == 0) std.process.fatal("--output= requires a path", .{});
            cli.output = value;
        } else if (std.mem.cutPrefix(u8, arg, "--limit=")) |value| {
            cli.limit = std.fmt.parseInt(u32, value, 10) catch
                std.process.fatal("--limit=: not a u32: '{s}'", .{value});
        } else if (std.mem.startsWith(u8, arg, "-")) {
            std.process.fatal("unrecognized flag: '{s}'\n{s}", .{ arg, usage });
        } else {
            cli.rest = argv[i..]; // first operand ends flag parsing
            return cli;
        }
    }
    return cli;
}

test "flags, --, and operands" {
    const argv: []const [:0]const u8 = &.{ "myproj", "-v", "--limit=3", "--", "--not-a-flag" };
    const cli = parseArgs(argv);
    try std.testing.expect(cli.verbose);
    try std.testing.expectEqual(3, cli.limit);
    try std.testing.expectEqualStrings("--not-a-flag", cli.rest[0]);
}
```

Keep `parseArgs` a pure function of a `[]const [:0]const u8` rather than reading `init` directly:
that is what makes the table of cases above a unit test instead of a subprocess test. `main` then
does one thing — `const cli = parseArgs(try init.minimal.args.toSlice(arena));`.

**Check:** no `std.process.argsAlloc`, no invented `argsParse`/`ArgIterator.parse`, no `main` with a
second parameter; every `std.process.fatal` call site passes exactly two arguments; and the parser
has a `--` case and a test for it.

### ZS-BUILD-39 [S] `.zon` is a usable project config format, not just `build.zig.zon`

A config file you control is ZON before it is JSON, TOML, or YAML; `references/data.md` ZS-DATA-35
owns reading it, with `@import("config.zon")` at comptime or `std.zon.parse` at runtime. Prefer the
comptime form for anything fixed at build time (feature toggles, table sizes, endpoints per
environment). This rule is about where the file goes:

- a `.zon` file is a compilation input, so it sits inside `.paths` (ZS-BUILD-12), or consumers get a
  missing-file error;
- `zig fmt` formats `.zon`, so it goes in the `fmt` step's path list, as `build.zig.zon` does.

**Why:** an `@import`ed `.zon` file is source to the build, and needs what a `.zig` file gets: a
place in the package and in the formatting gate. Left out of `.paths`, it exists only on the
author's machine.

**Check:** every `.zon` file under the repo appears in `.paths` and in the `b.addFmt` path list; no
JSON/TOML/YAML dependency was added for a config file the project itself defines.
