# Migration: What 3.14 and 3.15 Removed, Changed, and Merely Discourage

Scope: the complete table of spellings that no longer work, the ones that still work and should
not be used, and the crucial difference between them. Also what to write today so that 3.16 does
not break it. Why a spelling is wrong is the chapter that owns it; this chapter is the list and
the grep.

One source: the **CPython "What's New" documents for 3.14 and 3.15**, plus the deprecation and
removal schedules they cite. Ruff's `UP` family catches the statically decidable subset; the rest is
a grep, because a removed name is a string and nothing clever is required.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **The four tiers**
  - PS-MIG-01 [M] Distinguish removed, rejected, unlisted and discouraged
  - PS-MIG-02 [M] Never report a soft deprecation as a removal
  - PS-MIG-03 [M] Run the dead-API grep before reading a diff
- **Removed outright**
  - PS-MIG-04 [M] Do not use a name 3.15 removed
  - PS-MIG-05 [M] Do not use a C API 3.15 removed
- **Rejected spellings of live names**
  - PS-MIG-06 [M] Construct `NamedTuple` and `TypedDict` with the class form
  - PS-MIG-07 [M] Give `strptime` a year directive when the format has `%d`
- **Unlisted but importable**
  - PS-MIG-08 [M] Treat `ByteString` as gone, not as deprecated
  - PS-MIG-09 [M] Stop reading `__version__` from a standard-library module
- **Changed underneath you**
  - PS-MIG-10 [M] Re-examine every `contextmanager` used as a decorator
  - PS-MIG-11 [M] Re-examine every `isinstance(x, dict)`
  - PS-MIG-12 [M] Re-examine every default-encoding dependence
- **Forward compatibility**
  - PS-MIG-13 [M] Write against 3.16's asyncio today
  - PS-MIG-14 [S] Do not write against 3.16's other changes yet
- **Tool migrations**
  - PS-MIG-15 [M] Follow pytest's own removal ladder
  - PS-MIG-16 [M] Re-verify this table on every interpreter bump

---

## The four tiers

### PS-MIG-01 [M] Distinguish removed, rejected, unlisted and discouraged

Four categories, and only the first two fail a build.

| Tier | What it means | In the grep? |
|---|---|---|
| **Removed** | The name is gone. `AttributeError` or `ImportError`. | Yes — fails |
| **Rejected** | The name lives; a call form no longer works. | Yes, as a shape — fails |
| **Unlisted** | Dropped from `__all__`, still importable, removal scheduled. | Yes — warns |
| **Discouraged** | Works, warns about nothing, no removal planned. | **No** |

**Why:** conflating them produces a check that cries wolf, and a check people learn to route
around is worse than no check — which is why this standard states the tiers before the table. The
fourth tier is the one that gets this wrong: Python has a documented notion of *soft
deprecation*, where a spelling is discouraged but explicitly never removed, and treating those as
errors makes the whole table untrustworthy.

**Check:** every entry in the table below carries its tier. An entry without one is the finding.

### PS-MIG-02 [M] Never report a soft deprecation as a removal

`re.match` is the canonical example. It is soft-deprecated in favour of `re.prefixmatch`, and the
documentation says outright: *"We do not plan to remove the older `match()` name, as it has been
used in code for over 30 years."*

**Why:** a grep that flags `re.match` fires on almost every codebase in existence, none of which is
broken. That single false positive is enough to make a reviewer skip the whole table, and then the
genuine removals go unnoticed too. The same applies to `struct`'s `'F'` and `'D'` codes and to the
`PyGILState` C APIs: all soft-deprecated, all staying.

**Check:** run the grep against a codebase you know is current. Any hit is either a real finding
or a tier error in the table.

### PS-MIG-03 [M] Run the dead-API grep before reading a diff

First, before anything else in the review.

**Why:** a superseded spelling means the author's model of the language is out of date, which makes
every other judgement in the diff suspect — so finding one changes how you read the rest. It is also
the cheapest check available: one command, no interpretation.

**Check:** the command is the rule.

```sh
# verified — the removal tier: every name here is gone in 3.15
grep -rnE 'ctypes\.SetPointerType|glob\.glob[01]|CGIHTTPRequestHandler' src/
grep -rnE 'is_reserved\(|platform\.java_ver|import sre_(compile|constants|parse)' src/
grep -rnE 'co_lnotab|no_type_check_decorator|zipimporter\(\)\.load_module' src/
grep -rnE '\.(getmark|setmark|getmarkers)\(' src/
```

## Removed outright

### PS-MIG-04 [M] Do not use a name 3.15 removed

| Removed | Use instead |
|---|---|
| `ctypes.SetPointerType()` | nothing; it was undocumented |
| `glob.glob0()`, `glob.glob1()` | `glob.glob()` with `root_dir=` |
| `http.server.CGIHTTPRequestHandler`, `python -m http.server --cgi` | nothing |
| `importlib.resources.files(package=...)` keyword | the positional argument |
| `pathlib.PurePath.is_reserved()` | `os.path.isreserved()` |
| `platform.java_ver()` | nothing |
| `sre_compile`, `sre_constants`, `sre_parse` | `re` |
| `sysconfig.is_python_build(check_home=...)` keyword | nothing |
| `types.CodeType.co_lnotab` | `co_lines()` |
| `typing.no_type_check_decorator` | nothing |
| `wave` `getmark`, `setmark`, `getmarkers` | nothing |
| `zipimport.zipimporter.load_module()` | `exec_module()` |

**Why:** each of these raises at the moment it is reached, which is usually not the moment the
module is imported — so the failure appears in production on a code path the tests did not take.
The grep finds them all statically.

**Check:** the command in PS-MIG-03.

### PS-MIG-05 [M] Do not use a C API 3.15 removed

`PyUnicode_AsDecodedObject`, `PyUnicode_AsDecodedUnicode`, `PyUnicode_AsEncodedObject`,
`PyUnicode_AsEncodedUnicode` — use `PyCodec_Decode` and `PyCodec_Encode`.
`PyImport_ImportModuleNoBlock` — use `PyImport_ImportModule`.
`PyWeakref_GetObject`, `PyWeakref_GET_OBJECT` — use `PyWeakref_GetRef`.
`PySys_ResetWarnOptions` — nothing.
`Py_GetExecPrefix`, `Py_GetPath`, `Py_GetPrefix`, `Py_GetProgramFullPath`, `Py_GetProgramName`,
`Py_GetPythonHome` — all replaced by `PyConfig_Get()`.

**Why:** these fail at compile time rather than at run time, which is the good case — but only if
you compile against 3.15 before shipping. A project that builds against 3.14 and runs on 3.15
finds out later. The borrowed-reference removals are also the ones a free-threaded build most
needs gone.

**Check:** `rg -n 'PyUnicode_As(Decoded|Encoded)(Object|Unicode)' -g '*.c' -g '*.h'`,
`rg -n 'PyImport_ImportModuleNoBlock|PyWeakref_GET?_?Object' -g '*.c' -g '*.h'`,
`rg -n 'PySys_ResetWarnOptions' -g '*.c' -g '*.h'`, and
`rg -n 'Py_Get(ExecPrefix|Path|Prefix|ProgramFullPath|ProgramName|PythonHome)' -g '*.c' -g '*.h'`.

## Rejected spellings of live names

### PS-MIG-06 [M] Construct `NamedTuple` and `TypedDict` with the class form

`NamedTuple("P", x=int)` and `TypedDict("TD")` with no fields are both rejected in 3.15. The names
still exist.

**Why:** this is the tier that a name-based grep misses entirely — `NamedTuple` is fine, and the
keyword-argument call form is not. It raises at class-creation time, which is import time, so at
least it fails early. PS-DATA-05 and PS-DATA-06 prefer the class form anyway.

**Check:** `rg -n 'NamedTuple\([^)\n]*=|TypedDict\((["\x27][A-Za-z_]+["\x27])[ \t]*\)' src/`

### PS-MIG-07 [M] Give `strptime` a year directive when the format has `%d`

`datetime.strptime(s, "%d/%m")` now raises `ValueError`.

**Why:** parsing a day without a year silently defaulted to 1900, which produced wrong dates rather
than an error — so this change turns a quiet bug into a loud one. Code that relied on the default is
code that was wrong.

**Check:** `rg -n 'strptime' src/` and read each format string for `%d` without `%Y` or `%y`.

## Unlisted but importable

### PS-MIG-08 [M] Treat `ByteString` as gone, not as deprecated

`collections.abc.ByteString` and `typing.ByteString` were dropped from `__all__` in 3.15. The names
still import — and now emit a `DeprecationWarning` when they do. Removal is 3.17.

**Why:** the middle tier exists for exactly this: the code works, warns, and will stop working in
two releases. Treating it as fine because it works is how a project arrives at 3.17 with a broken
import; treating it as removed is how a reviewer loses faith in the table. Use `bytes | bytearray
| memoryview`.

**Check:** `rg -n 'ByteString' src/` — a hit warns today and fails in 3.17.

### PS-MIG-09 [M] Stop reading `__version__` from a standard-library module

Deprecated across twenty-three modules in 3.15 — `argparse`, `csv`, `ctypes`, `decimal`, `json`,
`logging`, `pickle`, `platform`, `re`, `socketserver`, `tarfile`, `zlib` and more. Removal is 3.20.

**Why:** the attribute was never meaningful — it recorded the module's own historical version, not
the interpreter's — and code reading it was almost always answering the wrong question. Use
`sys.version_info` for the interpreter, `importlib.metadata.version()` for a distribution.

**Check:** `rg -n
'\b(argparse|csv|ctypes|decimal|json|logging|pickle|platform|re|tarfile|zlib)\. __version__'
src/`

## Changed underneath you

### PS-MIG-10 [M] Re-examine every `contextmanager` used as a decorator

In 3.15 the context stays open for the whole generator; it used to close when the generator object
was created.

**Why:** this is the most dangerous silent change in 3.15 for ordinary code and it is not in the
porting notes. Nothing errors on either version — only the *duration* changes, from effectively zero
to the full consumption of the generator. Anything holding a lock, a transaction, a `chdir` or a
`contextvars` token that way now holds it far longer, which under free threading is new contention
and a new deadlock shape.

**Check:** `rg -nB2 -A2 '@contextmanager' src/` and find every decorator derived from one that is
applied to a function containing `yield`.

### PS-MIG-11 [M] Re-examine every `isinstance(x, dict)`

3.15's `frozendict` inherits from `object`, not from `dict`.

**Why:** the check now returns `False` for a mapping that behaves like a dict in every way that
matters, so a function that accepted a dict silently rejects one. The standard library was updated
for this — `copy`, `json`, `pickle`, `pprint` and others — and third-party code was not. Test
`collections.abc.Mapping`.

**Check:** `rg -n 'isinstance\(.*, dict\)' src/`

### PS-MIG-12 [M] Re-examine every default-encoding dependence

UTF-8 mode is on by default, and it moves six surfaces — see PS-FMT-02.

**Why:** the change most people check is `open`. The ones that bite are `sys.stdout` gaining
`surrogateescape`, which turns encoding failures into silent mojibake, and
`locale.getpreferredencoding()` becoming a constant, which makes every branch on it take one path
forever.

**Check:** run the suite with `-X warn_default_encoding` and treat every `EncodingWarning` as a
finding.

## Forward compatibility

### PS-MIG-13 [M] Write against 3.16's asyncio today

The event-loop policy system is removed in 3.16, and the replacements already work.

| Removed in 3.16 | Write now |
|---|---|
| `asyncio.get_event_loop_policy()`, `set_event_loop_policy()` | `asyncio.run(main(), loop_factory=...)` |
| `AbstractEventLoopPolicy`, `DefaultEventLoopPolicy` | `asyncio.Runner` |
| `WindowsSelectorEventLoopPolicy`, `WindowsProactorEventLoopPolicy` | `loop_factory=` |
| `asyncio.iscoroutinefunction()` | `inspect.iscoroutinefunction()` |

**Why:** these cost nothing to adopt now and are a forced migration later. Writing them today means
the 3.16 bump is a version number rather than a project.

**Check:** `rg -n 'get_event_loop|EventLoopPolicy|asyncio\.iscoroutinefunction' src/`

### PS-MIG-14 [S] Do not write against 3.16's other changes yet

3.16 has had no alpha release. Everything in it can still be reverted.

**Why:** PS-MIG-13 is safe because those are removals with replacements that already exist — the
replacement works on 3.15 today. Anything that requires a 3.16 *addition* is a bet on unreleased
behaviour, and this standard's whole position is that examples must run on the interpreter they
target. Note the exceptions worth knowing: `array`'s `'u'` format code goes in 3.16 (use `'w'`), as
do `shutil.ExecError` and `functools.reduce`'s keyword arguments.

**Check:** any code path guarded on `sys.version_info >= (3, 16)`.

## Tool migrations

### PS-MIG-15 [M] Follow pytest's own removal ladder

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

### PS-MIG-16 [M] Re-verify this table on every interpreter bump

Not on every release of your own project — on every change to the interpreter you target.

**Why:** a migration table is a snapshot, and its failure mode is silence: entries that became wrong
do not announce themselves, and the grep goes on passing while missing things. The 3.15 "What's New"
document was still marked draft at the time this chapter was written, so several entries here were
read from a document that was still moving.

**Check:** diff the target version's "What's New" removals section against this table.
