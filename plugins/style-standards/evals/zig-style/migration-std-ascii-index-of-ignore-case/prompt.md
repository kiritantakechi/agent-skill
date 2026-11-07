---
schema_version: "1.1"
name: zig-style-migration-std-ascii-index-of-ignore-case
description: 'What Zig 0.17 writes for `std.ascii.indexOfIgnoreCase`; the reply gives `std.ascii.findIgnoreCase` and cites ZS-DATA-36.'
tags: [zig-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Zig code was written for an earlier release, and Zig 0.17 rejects it:

```zig
std.ascii.indexOfIgnoreCase
```

What does Zig 0.17 write in its place, and which rule of the project's standards says so?
