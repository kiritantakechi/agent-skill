# Migration: What 3.14 and 3.15 Removed, Changed, and Deprecated

Scope: every spelling that is removed, aliased, changed or deprecated on 3.15, keyed by the old
spelling, with the release since which it is and the rule that owns it; how to read a row; and what
to write now so that 3.16 does not break it. Why a spelling is wrong is its owning rule's to say;
this chapter is the table and the command it generates.

Every rule ID a revision of this standard changed, and what it became, is in
`references/renames.md`.

## Contents

- Old spellings
- **Reading the table**
  - PS-MIG-01 [M] Read each row by its status, and give a discouraged name no row
  - PS-MIG-02 [M] Run the dead-API command before reading a diff
- **Removed and rejected**
  - PS-MIG-03 [M] Do not use a name 3.15 removed
  - PS-MIG-04 [M] Never call a live name in a shape 3.15 rejects
- **Deprecated**
  - PS-MIG-05 [M] Stop reading `__version__` from a standard-library module
  - PS-MIG-06 [S] Do not write against 3.16's other changes yet
- **Tool migrations**
  - PS-MIG-07 [M] Follow pytest's own removal ladder
  - PS-MIG-08 [M] Re-verify this table on every interpreter bump
- Decided by tools

---

## Old spellings

| Old | Python 3.15 | Status | Since | Rule |
|---|---|---|---|---|
| `__cached__` | `__spec__.cached`; a module's `__cached__` is no longer set or read | gone | 3.15 | PS-MIG-03 |
| `ctypes.SetPointerType` | nothing; it was undocumented | gone | 3.15 | PS-MIG-03 |
| `glob.glob0` | `glob.glob()` with `root_dir=` | gone | 3.15 | PS-MIG-03 |
| `glob.glob1` | `glob.glob()` with `root_dir=` | gone | 3.15 | PS-MIG-03 |
| `http.server.CGIHTTPRequestHandler` | nothing | gone | 3.15 | PS-MIG-03 |
| `python -m http.server --cgi` | nothing | gone | 3.15 | PS-MIG-03 |
| `importlib.abc.Loader.load_module` | `exec_module()`; the import system no longer calls it | gone | 3.15 | PS-MIG-03 |
| `pathlib.PurePath.is_reserved` | `os.path.isreserved()` | gone | 3.15 | PS-MIG-03 |
| `platform.java_ver` | nothing | gone | 3.15 | PS-MIG-03 |
| `sre_compile` | `re` | gone | 3.15 | PS-MIG-03 |
| `sre_constants` | `re` | gone | 3.15 | PS-MIG-03 |
| `sre_parse` | `re` | gone | 3.15 | PS-MIG-03 |
| `types.CodeType.co_lnotab` | `co_lines()` | gone | 3.15 | PS-MIG-03 |
| `typing.no_type_check_decorator` | nothing | gone | 3.15 | PS-TYPE-11 |
| `wave.Wave_read.getmark` | nothing | gone | 3.15 | PS-MIG-03 |
| `wave.Wave_read.getmarkers` | nothing | gone | 3.15 | PS-MIG-03 |
| `wave.Wave_write.getmark` | nothing | gone | 3.15 | PS-MIG-03 |
| `wave.Wave_write.getmarkers` | nothing | gone | 3.15 | PS-MIG-03 |
| `wave.Wave_write.setmark` | nothing | gone | 3.15 | PS-MIG-03 |
| `zipimport.zipimporter.load_module` | `exec_module()` | gone | 3.15 | PS-MIG-03 |
| `PyImport_ImportModuleNoBlock` | `PyImport_ImportModule` | gone | 3.15 | PS-MIG-03 |
| `PySys_ResetWarnOptions` | nothing | gone | 3.15 | PS-MIG-03 |
| `PyUnicode_AsDecodedObject` | `PyCodec_Decode` | gone | 3.15 | PS-MIG-03 |
| `PyUnicode_AsDecodedUnicode` | `PyCodec_Decode` | gone | 3.15 | PS-MIG-03 |
| `PyUnicode_AsEncodedObject` | `PyCodec_Encode` | gone | 3.15 | PS-MIG-03 |
| `PyUnicode_AsEncodedUnicode` | `PyCodec_Encode` | gone | 3.15 | PS-MIG-03 |
| `PyWeakref_GET_OBJECT` | `PyWeakref_GetRef` | gone | 3.15 | PS-MIG-03 |
| `PyWeakref_GetObject` | `PyWeakref_GetRef` | gone | 3.15 | PS-MIG-03 |
| `Py_GetExecPrefix` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `Py_GetPath` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `Py_GetPrefix` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `Py_GetProgramFullPath` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `Py_GetProgramName` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `Py_GetPythonHome` | `PyConfig_Get()` | gone | 3.15 | PS-MIG-03 |
| `ast.<Node>(…)` | raises `TypeError` for a field missing or a keyword no field has; give each of the node's `_fields`, and only those | gone | 3.15 | PS-MIG-04 |
| `datetime.strptime(…, "%d/%m")` | raises `ValueError` for a day with no year; give the format a year directive | gone | 3.15 | PS-MIG-04 |
| `importlib.resources.files(package=…)` | raises `TypeError`; pass the package positionally | gone | 3.15 | PS-MIG-04 |
| `sysconfig.is_python_build(check_home=…)` | raises `TypeError`; call it with no argument | gone | 3.15 | PS-MIG-04 |
| `threading.RLock(…)` | raises `TypeError` given any argument; `threading.RLock()`, which never used them | gone | 3.15 | PS-MIG-04 |
| `typing.NamedTuple(…, x=…)` | raises `TypeError` for a field given as a keyword; `class P(NamedTuple)` | gone | 3.15 | PS-MIG-04 |
| `typing.TypedDict("…")` | raises `TypeError` given a name and no fields; `class TD(TypedDict)` | gone | 3.15 | PS-MIG-04 |
| `asyncio.get_event_loop` | raises `RuntimeError` with no running loop; `asyncio.get_running_loop()` | changed | 3.14 | PS-ASYNC-02 |
| `contextlib.contextmanager` | a decorator built from one, on a generator function, holds until the generator is exhausted | changed | 3.15 | PS-CONC-21 |
| `from __future__ import annotations` | stringifies every annotation, so `annotationlib`'s `VALUE` and `FORWARDREF` return bare strings | changed | 3.14 | PS-TYPE-04 |
| `functools.singledispatchmethod` | called through its class, dispatches on the argument after the instance | changed | 3.15 | PS-TYPE-17 |
| `isinstance(x, dict)` | `False` for a `frozendict`; `isinstance(x, collections.abc.Mapping)` | changed | 3.15 | PS-DATA-13 |
| `locale.getpreferredencoding` | `'utf-8'` under UTF-8 mode, whatever the locale; `locale.getencoding()` | changed | 3.15 | PS-OUT-03 |
| `obj.n += 1` | on `3.15t`, loses updates when two threads run it | changed | 3.13 | PS-CONC-02 |
| `open(path)` | UTF-8 whatever the locale, while UTF-8 mode is on | changed | 3.15 | PS-OUT-02 |
| `sys.getfilesystemencoding` | `'utf-8'` under UTF-8 mode, so argv, environment variables and filenames decode as UTF-8 whatever the locale | changed | 3.15 | PS-OUT-02 |
| `sys.stdout` | writes with the `surrogateescape` error handler under UTF-8 mode, as `sys.stdin` reads, where an unencodable character raised | changed | 3.15 | PS-OUT-02 |
| `cProfile` | `profiling.tracing` | alias | 3.15 | PS-PERF-02 |
| `typing.Text` | `str` | alias | 3.11 | PS-TYPE-11 |
| `<module>.__version__` | `sys.version_info`, or `importlib.metadata.version()`; removed in 3.20 | deprecated | 3.15 | PS-MIG-05 |
| `array.array("u")` | `array.array("w")`; removed in 3.16 | deprecated | 3.13 | PS-MIG-06 |
| `asyncio.AbstractEventLoopPolicy` | `asyncio.Runner`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `asyncio.DefaultEventLoopPolicy` | `asyncio.Runner`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `asyncio.WindowsProactorEventLoopPolicy` | `loop_factory=`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `asyncio.WindowsSelectorEventLoopPolicy` | `loop_factory=`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `asyncio.get_event_loop_policy` | `asyncio.run(main(), loop_factory=...)`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `asyncio.set_event_loop_policy` | `asyncio.run(main(), loop_factory=...)`; removed in 3.16 | deprecated | 3.14 | PS-ASYNC-02 |
| `collections.abc.ByteString` | `collections.abc.Buffer`; removed in 3.17 | deprecated | 3.15 | PS-TYPE-11 |
| `profile` | `profiling.tracing`; removed in 3.17 | deprecated | 3.15 | PS-PERF-02 |
| `shutil.ExecError` | nothing; no `shutil` function raises it; removed in 3.16 | deprecated | 3.14 | PS-MIG-06 |
| `typing.AnyStr` | a constrained type parameter, `def f[S: (str, bytes)](s: S) -> S`; removed in 3.18 | deprecated | 3.13 | PS-TYPE-11 |
| `typing.ByteString` | `collections.abc.Buffer`; removed in 3.17 | deprecated | 3.15 | PS-TYPE-11 |

```sh
rg -n -F -w \
  -e '__cached__' \
  -e 'ctypes.SetPointerType' \
  -e 'glob.glob0' \
  -e 'glob.glob1' \
  -e 'http.server.CGIHTTPRequestHandler' \
  -e 'python -m http.server --cgi' \
  -e 'importlib.abc.Loader.load_module' \
  -e 'pathlib.PurePath.is_reserved' \
  -e 'platform.java_ver' \
  -e 'sre_compile' \
  -e 'sre_constants' \
  -e 'sre_parse' \
  -e 'types.CodeType.co_lnotab' \
  -e 'typing.no_type_check_decorator' \
  -e 'wave.Wave_read.getmark' \
  -e 'wave.Wave_read.getmarkers' \
  -e 'wave.Wave_write.getmark' \
  -e 'wave.Wave_write.getmarkers' \
  -e 'wave.Wave_write.setmark' \
  -e 'zipimport.zipimporter.load_module' \
  -e 'PyImport_ImportModuleNoBlock' \
  -e 'PySys_ResetWarnOptions' \
  -e 'PyUnicode_AsDecodedObject' \
  -e 'PyUnicode_AsDecodedUnicode' \
  -e 'PyUnicode_AsEncodedObject' \
  -e 'PyUnicode_AsEncodedUnicode' \
  -e 'PyWeakref_GET_OBJECT' \
  -e 'PyWeakref_GetObject' \
  -e 'Py_GetExecPrefix' \
  -e 'Py_GetPath' \
  -e 'Py_GetPrefix' \
  -e 'Py_GetProgramFullPath' \
  -e 'Py_GetProgramName' \
  -e 'Py_GetPythonHome' \
  -e 'cProfile' \
  -e 'typing.Text' \
  .
```

## Reading the table

### PS-MIG-01 [M] Read each row by its status, and give a discouraged name no row

A row's status says what 3.15 does with the old spelling, and so how to find it:

- `gone` — 3.15 rejects it: the name is absent, an `AttributeError`, an `ImportError` or a failed
  build where it is reached, or the call shape raises a `TypeError` or `ValueError` where it was
  accepted. The command after the table finds every one but a shape.
- `changed` — 3.15 accepts it, and it does something else. Its owning rule's Check finds it.
- `alias` — 3.15 accepts it, and it resolves to its replacement. The command finds it; rewrite it.
- `deprecated` — 3.15 accepts it, and it works as it did; most warn on use, and a release removes
  it, which the row names.

A spelling with `…` in it is a shape: code left out where the `…` stands, which no fixed string
finds, so the command leaves it to its owning rule's Check.

Its Since is the release from which it does so: the one that removed, aliased, changed or deprecated
it. Section 2.1 lists the `changed` rows of 3.15 and section 2.2 the `gone` ones; code written for
an older release reads the rows since that one.

A *discouraged* name has no row. `re.match` is the canonical one: soft-deprecated in favour of
`re.prefixmatch`, and the documentation says outright, *"We do not plan to remove the older
`match()` name, as it has been used in code for over 30 years."* The same holds for `struct`'s `'F'`
and `'D'` codes and for the `PyGILState` C APIs: all soft-deprecated, all staying.

**Why:** conflating them produces a check that cries wolf, and a check people learn to route around
is worse than no check. A discouraged name is where it goes wrong: a soft deprecation is never
removed, so treating one as an error discredits the whole table.

**Check:** run the command after the table against a codebase you know is current: any hit is a real
finding or a row whose status is wrong. A row naming a soft-deprecated name is the finding.

### PS-MIG-02 [M] Run the dead-API command before reading a diff

First, before anything else in the review: the command after the table, then the Check of each rule
that owns a `changed` row or a shape.

**Why:** a superseded spelling means the author's model of the language is out of date, which makes
every other judgement in the diff suspect — so finding one changes how you read the rest. It is also
the cheapest check available: one command, generated from the table, so it cannot drift from it.

**Check:** the review's order. One that ran the command after reading the diff, or not at all, is
the finding.

## Removed and rejected

### PS-MIG-03 [M] Do not use a name 3.15 removed

Every `gone` row the rule column gives to PS-MIG-03 is a name 3.15 removed, from Python or from its
C API, and names its replacement or says there is none.

**Why:** a Python name raises where it is reached, usually not where the module is imported, so the
failure appears in production on a path the tests did not take; a C API name fails the build, but
only of an extension built against 3.15. The command finds both statically.

**Check:** the command after the table; every hit is the finding.

### PS-MIG-04 [M] Never call a live name in a shape 3.15 rejects

Every `gone` row the rule column gives to PS-MIG-04 is a call earlier releases accepted and 3.15
raises on: a keyword it removed, arguments it never used, a field an `ast` node needs, a functional
form with no fields, or a day without a year. Each is a shape, which the command after the table
does not find; this Check does.

**Why:** each was accepted silently — ignoring what it was given, or filling a default as `strptime`
filled the year 1900, a wrong date rather than an error. Now each raises, and like a removed name it
raises where the call is reached, not where the module is imported.

**Check:** `rg -n 'files\(package=|is_python_build\(check_home=|RLock\([^)]' src/` — every hit is
the finding. `rg -n 'strptime\(' src/`, `rg -n '\bast\.[A-Z][A-Za-z]*\(' src/` and
`rg -n '(TypedDict|NamedTuple)\("' src/` — read each hit: a format with `%d` and no `%Y` or `%y`, a
node missing a field or given one it lacks, or a functional form with no fields or with keywords, is
the finding.

## Deprecated

### PS-MIG-05 [M] Stop reading `__version__` from a standard-library module

The `<module>.__version__` row: `argparse`, `csv`, `ctypes`, `decimal`, `http.server`, `imaplib`,
`ipaddress`, `json`, `logging`, `optparse`, `platform`, `re`, `socketserver`, `tabnanny`,
`wsgiref.simple_server` and `zlib` among the modules, each warning on access. It is deprecated, not
a name a module ever listed: it was in no module's `__all__`.

**Why:** the attribute was never meaningful — it recorded the module's own historical version, not
the interpreter's — and code reading it was almost always answering the wrong question. Use
`sys.version_info` for the interpreter, `importlib.metadata.version()` for a distribution.

**Check:**
`rg -n '\b(argparse|csv|ctypes|decimal|imaplib|ipaddress|json|logging|optparse|platform|re|socketserver|tabnanny|zlib)\.__version__' src/`
— every hit is the finding.

### PS-MIG-06 [S] Do not write against 3.16's other changes yet

Anything 3.16 adds can still be reverted before its first beta, so nothing written for 3.15 relies
on one. What 3.16 removes is in the table already, each deprecated on 3.15 with a replacement that
works now: the asyncio policy rows, `array`'s `'u'` code and `shutil.ExecError`.

**Why:** the deprecated rows are safe to act on because their replacements already run on 3.15.
Anything that requires a 3.16 *addition* is a bet on unreleased behaviour, and this standard's whole
position is that examples must run on the interpreter they target.

**Check:** any code path guarded on `sys.version_info >= (3, 16)`.

## Tool migrations

### PS-MIG-07 [M] Follow pytest's own removal ladder

pytest runs the same tiered process the interpreter does:

| Tier | What |
|---|---|
| **Removed in 9.1** | Everything that warned `PytestRemovedIn9Warning`, which 9.0 had already turned into an error |
| **Deprecated in 9.1, removal in 10** | Class-scoped fixtures defined as instance methods; `request.getfixturevalue()` during teardown; a generator or iterator as `parametrize` argvalues; `config.inicfg`; `--pastebin`; `pytest.console_main()` |
| **Changed, not removed** | `pytest a/ a/b` now means `pytest a` — restore the old behaviour with `--keep-duplicates`; CI mode now needs `$CI` or `$BUILD_NUMBER` defined **and non-empty** |

**Why:** the same discipline as PS-MIG-01 applies to tools, and pytest's ladder is the one this
standard's own configuration sits on. The CI-detection change is the quiet one: a shell that exports
`CI=` with an empty value used to enable CI mode and now does not.

**Check:** run the suite with `-W error::DeprecationWarning` and read what fires.

### PS-MIG-08 [M] Re-verify this table on every interpreter bump

Not on every release of your own project — on every change to the interpreter you target.

**Why:** a migration table is a snapshot, and its failure mode is silence: entries that became wrong
do not announce themselves, and the command goes on passing while missing things. "What's New" keeps
moving after the first candidate: 3.15's gained four removals between rc1 and the final release.

**Check:** diff the target version's "What's New" removals section against this table.

## Decided by tools

A tool settles these on its own; the shipped configuration enables each at the level shown.

| Tool | Lint | Level | Forbids |
|---|---|---|---|
| ruff | `UP013` | error | the functional `TypedDict("TD", …)` form — listed because its fix is the class form, which PS-MIG-04's row asks for |
| ruff | `UP014` | error | the functional `NamedTuple("P", …)` form — listed because its fix is the class form, which PS-MIG-04's row asks for |
