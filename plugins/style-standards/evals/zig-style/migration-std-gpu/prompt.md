---
schema_version: "1.1"
name: zig-style-migration-std-gpu
description: 'What Zig 0.17 writes for `std.gpu`; the reply gives `std.spirv` and cites ZS-MIG-01.'
tags: [zig-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Zig code was written for an earlier release, and Zig 0.17 rejects it:

```zig
std.gpu
```

What does Zig 0.17 write in its place, and which rule of the project's standards says so?
