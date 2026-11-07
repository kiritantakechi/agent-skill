// Canonical build.zig for a library + CLI project, lifted verbatim from
// references/build.md ZS-BUILD-01, where it is marked verified against
// Zig 0.17.0. Rename `myproj` and delete the steps you do not need.
// Referenced by ZS-BUILD-01, ZS-BUILD-04, ZS-BUILD-29.

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

    // ONE test binary per module (ZS-BUILD-04). Unit tests hang off `test`.
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
    // (ZS-BUILD-04). CI runs both steps.
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
