---
schema_version: "1.1"
name: zig-style-review-zs-data-15
description: 'The BAD example of ZS-DATA-15, sent for review; the reply cites ZS-DATA-15.'
tags: [zig-style, review]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Zig code against the project's standards; report each problem with the rule it breaks:

```zig
const std = @import("std");
test "anonymous initializer is not atomic" {
    var pair: [2]u32 = .{ 1, 2 };
    pair = .{ pair[1], pair[0] };
    try std.testing.expectEqualSlices(u32, &.{ 2, 2 }, &pair);
}
```
