---
schema_version: "1.1"
name: bevy-style-migration-default-error-handler
description: 'What Bevy 0.20 writes for `DefaultErrorHandler`; the reply gives `FallbackErrorHandler` and cites BV-ERR-05.'
tags: [bevy-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Bevy code was written for an earlier release, and Bevy 0.20 rejects it:

```rust
DefaultErrorHandler
```

What does Bevy 0.20 write in its place, and which rule of the project's standards says so?
