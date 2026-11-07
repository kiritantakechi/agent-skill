---
schema_version: "1.1"
name: bevy-style-negative-python-style
description: 'The first review prompt of python-style, in another language; bevy-style''s skill does not fire, with the plugin or without it.'
tags: [bevy-style, negative]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this Python code against the project's standards; report each problem with the rule it
breaks:

```python
import sys


def port(raw: str) -> int:
    if not raw.isdigit():
        sys.exit(f"port must be a number, got {raw!r}")
    return int(raw)
```
