# Migration: What 3.14 and 3.15 Removed, Changed, and Merely Discourage

Scope: the complete table of spellings that no longer work, the ones that still work and should not
be used, and the crucial difference between them. Also what to write today so that 3.16 does not
break it. Why a spelling is wrong is the chapter that owns it; this chapter is the list and the
grep.

One source: the **CPython "What's New" documents for 3.14 and 3.15**, plus the deprecation and
removal schedules they cite. Ruff's `UP` family catches the statically decidable subset; the rest is
a grep, because a removed name is a string and nothing clever is required.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- **The five tiers**
  - PS-MIG-01 [M] Distinguish removed, rejected, unlisted, deprecated and discouraged
  - PS-MIG-02 [M] Run the dead-API grep before reading a diff
- **Removed outright**
  - PS-MIG-03 [M] Do not use a name 3.15 removed
  - PS-MIG-04 [M] Do not use a C API 3.15 removed
- **Rejected spellings of live names**
  - PS-MIG-05 [M] Give `strptime` a year directive when the format has `%d`
- **Unlisted or deprecated, still importable**
  - PS-MIG-06 [M] Stop reading `__version__` from a standard-library module
- Changed underneath you
- **Forward compatibility**
  - PS-MIG-07 [S] Do not write against 3.16's other changes yet
- **Tool migrations**
  - PS-MIG-08 [M] Follow pytest's own removal ladder
  - PS-MIG-09 [M] Re-verify this table on every interpreter bump
- Decided by tools

---

## The five tiers

### PS-MIG-01 [M] Distinguish removed, rejected, unlisted, deprecated and discouraged

Five categories, and only the first two fail a build.

| Tier | What it means | In the grep? |
|---|---|---|
| **Removed** | The name is gone. `AttributeError` or `ImportError`. | Yes — fails |
| **Rejected** | The name lives; a call form no longer works. | Yes, as a shape — fails |
| **Unlisted** | Dropped from `__all__`, still importable, removal scheduled. | Yes — warns |
| **Deprecated** | Still listed or never was, works, removal scheduled; most warn on use. | Yes — warns |
| **Discouraged** | Works, warns about nothing, no removal planned. | **No** |

`re.match` is the canonical discouraged name: soft-deprecated in favour of `re.prefixmatch`, and the
documentation says outright, *"We do not plan to remove the older `match()` name, as it has been
used in code for over 30 years."* The same holds for `struct`'s `'F'` and `'D'` codes and for the
`PyGILState` C APIs: all soft-deprecated, all staying.

**Why:** conflating them produces a check that cries wolf, and a check people learn to route around
is worse than no check. The last tier is where it goes wrong: a *soft deprecation* is discouraged
but explicitly never removed, so treating one as an error discredits the whole table.

**Check:** every entry in this chapter carries its tier. An entry without one is the finding. Then
run the grep against a codebase you know is current: any hit is a real finding or a tier error.

### PS-MIG-02 [M] Run the dead-API grep before reading a diff

First, before anything else in the review.

**Why:** a superseded spelling means the author's model of the language is out of date, which makes
every other judgement in the diff suspect — so finding one changes how you read the rest. It is also
the cheapest check available: one command, and only its `ast` line needs reading.

**Check:** the command is the rule.

```sh
# verified — removed and rejected fail; unlisted and deprecated warn
# Removed: every name here is gone in 3.15.
grep -rnE 'ctypes\.SetPointerType|glob\.glob[01]|CGIHTTPRequestHandler' src/
grep -rnE 'is_reserved\(|platform\.java_ver|import sre_(compile|constants|parse)' src/
grep -rnE 'co_lnotab|no_type_check_decorator|\.load_module\(|__cached__' src/
grep -rnE '\.(getmark|setmark|getmarkers)\(' src/
grep -rnE 'files\(package=|is_python_build\([^)]|RLock\([^)]' src/
grep -rnE 'http\.server.*--cgi' .
grep -rnE '\bast\.[A-Z][A-Za-z]*\(' src/  # read each: every field given, nothing else
# Rejected: the name lives, and this shape of call fails.
grep -rnE 'strptime\(.*%d' src/ | grep -vE '%[Yy]'
# Unlisted or deprecated: importable today, removal scheduled.
grep -rnE 'ByteString|AnyStr|^\s*(import|from) profile\b' src/
grep -rnE '\b(argparse|csv|ctypes|decimal|json|logging)\.__version__' src/
grep -rnE '\b(pickle|platform|re|tarfile|zlib)\.__version__' src/
grep -rnE 'get_event_loop_policy|set_event_loop_policy|EventLoopPolicy' src/
```

## Removed outright

### PS-MIG-03 [M] Do not use a name 3.15 removed

| Removed | Use instead |
|---|---|
| `ctypes.SetPointerType()` | nothing; it was undocumented |
| `glob.glob0()`, `glob.glob1()` | `glob.glob()` with `root_dir=` |
| `http.server.CGIHTTPRequestHandler`, `python -m http.server --cgi` | nothing |
| `importlib.abc.Loader.load_module()`, which the import system no longer calls | `exec_module()` |
| `importlib.resources.files(package=...)` keyword | the positional argument |
| a module's `__cached__`, which is no longer set or read | `__spec__.cached` |
| `pathlib.PurePath.is_reserved()` | `os.path.isreserved()` |
| `platform.java_ver()` | nothing |
| `sre_compile`, `sre_constants`, `sre_parse` | `re` |
| `sysconfig.is_python_build(check_home=...)` keyword | nothing |
| `threading.RLock(...)` given arguments, which it never used | `threading.RLock()` |
| an `ast` node constructor missing a required field, or given a keyword that is not a field | the node's `_fields`, each given |
| `types.CodeType.co_lnotab` | `co_lines()` |
| `typing.no_type_check_decorator` | nothing |
| `wave` `getmark`, `setmark`, `getmarkers` | nothing |
| `zipimport.zipimporter.load_module()` | `exec_module()` |

**Why:** each of these raises at the moment it is reached, which is usually not the moment the
module is imported — so the failure appears in production on a code path the tests did not take. The
grep finds them all statically.

**Check:** the command in PS-MIG-02.

### PS-MIG-04 [M] Do not use a C API 3.15 removed

`PyUnicode_AsDecodedObject`, `PyUnicode_AsDecodedUnicode`, `PyUnicode_AsEncodedObject`,
`PyUnicode_AsEncodedUnicode` — use `PyCodec_Decode` and `PyCodec_Encode`.
`PyImport_ImportModuleNoBlock` — use `PyImport_ImportModule`. `PyWeakref_GetObject`,
`PyWeakref_GET_OBJECT` — use `PyWeakref_GetRef`. `PySys_ResetWarnOptions` — nothing.
`Py_GetExecPrefix`, `Py_GetPath`, `Py_GetPrefix`, `Py_GetProgramFullPath`, `Py_GetProgramName`,
`Py_GetPythonHome` — all replaced by `PyConfig_Get()`.

**Why:** these fail at compile time rather than at run time, which is the good case — but only if
you compile against 3.15 before shipping; a project that builds against 3.14 and runs on 3.15 finds
out later. The borrowed-reference removals are also the ones a free-threaded build most needs gone.

**Check:** `rg -n 'PyUnicode_As(Decoded|Encoded)(Object|Unicode)' -g '*.c' -g '*.h'`,
`rg -n 'PyImport_ImportModuleNoBlock|PyWeakref_GET?_?Object' -g '*.c' -g '*.h'`,
`rg -n 'PySys_ResetWarnOptions' -g '*.c' -g '*.h'`, and
`rg -n 'Py_Get(ExecPrefix|Path|Prefix|ProgramFullPath|ProgramName|PythonHome)' -g '*.c' -g '*.h'`.

## Rejected spellings of live names

### PS-MIG-05 [M] Give `strptime` a year directive when the format has `%d`

`datetime.strptime(s, "%d/%m")` now raises `ValueError`.

**Why:** parsing a day without a year silently defaulted to 1900, which produced wrong dates rather
than an error — so this change turns a quiet bug into a loud one. Code that relied on the default is
code that was wrong.

**Check:** `rg -n 'strptime' src/` and read each format string for `%d` without `%Y` or `%y`.

## Unlisted or deprecated, still importable

| Importable in 3.15, removal scheduled | Removed in | Use instead | Find it with |
|---|---|---|---|
| Unlisted: `collections.abc.ByteString`, `typing.ByteString`, which now warn on every access | 3.17 | `collections.abc.Buffer` (PS-TYPE-11) | `rg -n 'ByteString' src/` |
| Deprecated: the `profile` module, which warns on import | 3.17 | `profiling.tracing` (PS-PERF-02) | `rg -nw 'profile' src/` |
| Deprecated: `typing.AnyStr`, which does not warn | 3.18 | a constrained type parameter, `def f[S: (str, bytes)](s: S) -> S` (PS-TYPE-11) | `rg -n 'AnyStr' src/` |
| Deprecated: the asyncio policy API, which warns on use | 3.16 | `loop_factory=` (PS-ASYNC-01, PS-ASYNC-02) | `rg -ni 'event_?loop_?policy' src/` |

### PS-MIG-06 [M] Stop reading `__version__` from a standard-library module

Deprecated across twenty-four modules in 3.15 — `argparse`, `csv`, `ctypes`, `decimal`, `json`,
`logging`, `pickle`, `platform`, `re`, `socketserver`, `tarfile`, `zlib` and more. Removal is 3.20.
The tier is deprecated rather than unlisted: the attribute was never in any module's `__all__`.

**Why:** the attribute was never meaningful — it recorded the module's own historical version, not
the interpreter's — and code reading it was almost always answering the wrong question. Use
`sys.version_info` for the interpreter, `importlib.metadata.version()` for a distribution.

**Check:**
`rg -n '\b(argparse|csv|ctypes|decimal|json|logging|pickle|platform|re|tarfile|zlib)\.__version__' src/`

## Changed underneath you

Each of these runs on either version, so the upgrade flags none of them. SKILL.md §2.1 is the same
list, to read before writing code; this is the one to grep with.

| Changed in 3.15 | Find it with | Rule |
|---|---|---|
| A `@contextmanager`-derived decorator on a generator function holds its context until the generator is exhausted, not until it is created | `rg -nB2 -A2 '@contextmanager' src/` | PS-CONC-21 |
| `frozendict` is not a `dict` subclass, so `isinstance(x, dict)` rejects one | `rg -n 'isinstance\(.*, dict\)' src/` | PS-DATA-13 |
| UTF-8 mode is on by default and moves six surfaces, `sys.stdout`'s error handler among them | the suite under `-X warn_default_encoding`, where every `EncodingWarning` is a finding | PS-OUT-02 |
| `functools.singledispatchmethod` wrapping a regular method and called through the class, `A.m(a, 1)`, dispatches on the second argument, so a different registered implementation runs | `rg -n 'singledispatchmethod' src/`, then each call made through the class | — |
| On `3.15t` the GIL is gone, so a read-modify-write on shared state that worked by luck now loses updates | PS-CONC-02's Check | PS-CONC-02 |

## Forward compatibility

3.16 removes the event-loop policy system, in the deprecated tier on 3.15, and the replacements
already work on 3.15, so code is written against them now (PS-ASYNC-01, PS-ASYNC-02). Find the old
spellings with `rg -n 'get_event_loop|EventLoopPolicy' src/`.

| Removed in 3.16 | Write now |
|---|---|
| `asyncio.get_event_loop_policy()`, `set_event_loop_policy()` | `asyncio.run(main(), loop_factory=...)` |
| `AbstractEventLoopPolicy`, `DefaultEventLoopPolicy` | `asyncio.Runner` |
| `WindowsSelectorEventLoopPolicy`, `WindowsProactorEventLoopPolicy` | `loop_factory=` |

### PS-MIG-07 [S] Do not write against 3.16's other changes yet

3.16 is in alpha — 3.16.0a1 shipped on 2026-10-13 — and anything in it can still be reverted before
its first beta. The exceptions worth knowing: `array`'s `'u'` format code goes in 3.16 (use `'w'`),
as do `shutil.ExecError` and `functools.reduce`'s keyword arguments.

**Why:** the asyncio rows above are safe because they are removals whose replacements already work
on 3.15. Anything that requires a 3.16 *addition* is a bet on unreleased behaviour, and this
standard's whole position is that examples must run on the interpreter they target.

**Check:** any code path guarded on `sys.version_info >= (3, 16)`.

## Tool migrations

### PS-MIG-08 [M] Follow pytest's own removal ladder

pytest runs the same three-tier process the interpreter does, and it is currently mid-ladder.

| Tier | What |
|---|---|
| **Removed in 9.1** | Everything that warned `PytestRemovedIn9Warning`, which 9.0 had already turned into an error |
| **Deprecated in 9.1, removal in 10** | Class-scoped fixtures defined as instance methods; `request.getfixturevalue()` during teardown; a generator or iterator as `parametrize` argvalues; `config.inicfg`; `--pastebin`; `pytest.console_main()` |
| **Changed, not removed** | `pytest a/ a/b` now means `pytest a` — restore the old behaviour with `--keep-duplicates`; CI mode now needs `$CI` or `$BUILD_NUMBER` defined **and non-empty** |

**Why:** the same tiering discipline as PS-MIG-01 applies to tools, and pytest's ladder is the one
this standard's own configuration sits on. The CI-detection change is the quiet one: a shell that
exports `CI=` with an empty value used to enable CI mode and now does not.

**Check:** run the suite with `-W error::DeprecationWarning` and read what fires.

### PS-MIG-09 [M] Re-verify this table on every interpreter bump

Not on every release of your own project — on every change to the interpreter you target.

**Why:** a migration table is a snapshot, and its failure mode is silence: entries that became wrong
do not announce themselves, and the grep goes on passing while missing things. "What's New" keeps
moving after the first candidate: 3.15's gained four removals between rc1 and the final release.

**Check:** diff the target version's "What's New" removals section against this table.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `UP013` | error | the functional `TypedDict("TD", …)` form — 3.15 rejects it with no fields |
| ruff | `UP014` | error | the functional `NamedTuple("P", …)` form — 3.15 rejects its keyword form |
