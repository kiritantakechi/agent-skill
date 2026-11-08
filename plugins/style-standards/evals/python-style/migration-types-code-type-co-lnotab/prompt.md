---
schema_version: "1.1"
name: python-style-migration-types-code-type-co-lnotab
description: 'What Python 3.15 writes for `types.CodeType.co_lnotab`; the reply gives `co_lines()` and cites PS-MIG-04.'
tags: [python-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Python code was written for an earlier release, and Python 3.15 rejects it:

```python
types.CodeType.co_lnotab
```

What does Python 3.15 write in its place, and which rule of the project's standards says so?
