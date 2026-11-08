"""The zig toolchain analyses every declaration a verified block has."""

lazy from pathlib import Path

import pytest

from agent_skill.checks.toolchain import verify
from agent_skill.lang.zig import ZIG, force_analysis, libc
from agent_skill.model import Skill
from agent_skill.proc import have

#: A private function with a type error that no test reaches: the
#: case a `pub`-only declaration list let through.
PRIVATE_DEFECT = """const std = @import("std");

fn private() u32 {
    const flag: bool = 3;
    return if (flag) 1 else 0;
}

pub fn public() u32 {
    return 2;
}
"""


@pytest.mark.parametrize(
    "source",
    [
        'extern "c" fn strlen(s: [*:0]const u8) usize;',
        "const pid = std.c.getpid();",
        "const gpa = std.heap.c_allocator;",
        "const raw = std.heap.raw_c_allocator;",
        "const c = @cImport({});",
    ],
)
def test_a_block_naming_libc_is_linked_against_it(source: str) -> None:
    assert libc(source) == ["-lc"]


@pytest.mark.parametrize(
    "source",
    [
        "const H = extern struct { a: u8 };",
        "extern fn zs_c_add(a: u32, b: u32) u32;",
        "// std.c.abs is mentioned, not called",
        "const n = std.mem.indexOfScalar(u8, s, 0);",
    ],
)
def test_every_other_block_is_verified_without_libc(source: str) -> None:
    assert libc(source) == []


def test_every_top_level_declaration_is_named() -> None:
    body = (
        'const std = @import("std");\n'
        "pub fn open() void {}\n"
        "fn helper() void {}\n"
        'pub const @"type" = u8;\n'
        "var counter: u32 = 0;\n"
        'extern "c" fn write(fd: c_int) isize;\n'
        "export fn entry() void {}\n"
        "pub const Config = struct {\n"
        "    const nested = 1;\n"
        "};\n"
    )

    wrapper = force_analysis(body)

    named = [line.strip() for line in wrapper.splitlines() if line.startswith("    ")]
    assert named == [
        "_ = &std;",
        "_ = &open;",
        "_ = &helper;",
        '_ = &@"type";',
        "_ = &counter;",
        "_ = &write;",
        "_ = &entry;",
        "_ = &Config;",
    ]


def test_a_block_with_no_declarations_gets_no_wrapper() -> None:
    assert force_analysis('test "only a test" {}\n') == ""


@pytest.mark.toolchain
@pytest.mark.skipif(not have("zig"), reason="needs zig")
def test_a_private_function_is_analysed(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "demo-style"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo-style\n---\n\n# Demo\n")
    fence = "```zig\n// verified\n" + PRIVATE_DEFECT + "```\n"
    (skill / "references" / "data.md").write_text(
        "# Data\n\n## Contents\n\n---\n\n### DS-DATA-01 [M] X\n\n" + fence
    )
    extraction = ZIG.extract(Skill(skill, None), tmp_path / "out")

    findings = list(verify(ZIG, extraction))

    assert any("expected type 'bool'" in f.message for f in findings), findings
