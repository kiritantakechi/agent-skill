---
schema_version: "1.1"
name: zig-style-review-zs-test-15
description: 'The BAD example of ZS-TEST-15, sent for review; the reply cites ZS-TEST-15.'
tags: [zig-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Zig code against the project's standards; report each problem with the rule it breaks:

```zig
const std = @import("std");

fn parsePort(text: []const u8) !u16 {
    return std.fmt.parseInt(u16, text, 10);
}

test "parsePort fails on an out-of-range port" {
    if (parsePort("65536")) |_| return error.TestUnexpectedResult else |_| {}
}
```
