---
schema_version: "1.1"
name: python-style-migration-cached
description: 'What Python 3.15 writes for `__cached__`; the reply gives `__spec__.cached` and cites PS-MIG-04.'
tags: [python-style, migration]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This Python code was written for an earlier release, and Python 3.15 rejects it:

```python
__cached__
```

What does Python 3.15 write in its place, and which rule of the project's standards says so?
