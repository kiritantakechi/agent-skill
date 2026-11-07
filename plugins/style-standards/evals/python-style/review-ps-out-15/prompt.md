---
schema_version: "1.1"
name: python-style-review-ps-out-15
description: 'The BAD example of PS-OUT-15, sent for review; the reply cites PS-OUT-15.'
tags: [python-style, review]
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
