# python-style: moving to CPython 3.15.0 final, ruff 0.17.1, ty 0.0.89

Research for the planning document, gathered on 2026-10-20. I edited nothing in the repository and did not run `agent-skill check` or `pytest`.

What I did run, all of it from the scratchpad:
- `uvx ruff@0.16.5` and `uvx ruff@0.17.1`
- `uvx ty@0.0.75` and `uvx ty@0.0.89`
- `uvx --from uv==X uv python list` (listing only)
- a scratch venv on the already-installed 3.15.0rc1t, holding pytest, used only to give ty a site-packages

Scratchpad paths below are relative to `<scratch>/`.

## Sources

**CPython 3.15**
- Changelog with the rc2, rc3 and final sections: https://docs.python.org/3.15/whatsnew/changelog.html (copy at `web/changelog.html`)
- What's New: https://docs.python.org/3.15/whatsnew/3.15.html
- 3.15 release schedule: https://peps.python.org/pep-0790/
- 3.16 release schedule: https://peps.python.org/pep-0826/
- Release pages:
  - https://www.python.org/downloads/release/python-3150rc1/
  - https://www.python.org/downloads/release/python-3150rc2/
  - https://www.python.org/downloads/release/python-3150rc3/
  - https://www.python.org/downloads/release/python-3150/
- Announcements on discuss.python.org:
  - rc3: https://discuss.python.org/t/python-3-15-following-tradition-lets-have-a-surprise-rc3/109313
  - final: https://discuss.python.org/t/python-3-15-0-final-is-here/109415
- rc1-to-final compare: https://github.com/python/cpython/compare/v3.15.0rc1...v3.15.0
- Free-threading HOWTO: https://docs.python.org/3.15/howto/free-threading-python.html (copy at `web/howto.html`)
- Thread Safety Guarantees: https://docs.python.org/3.15/builtins/threadsafety.html (copy at `web/threadsafety.html`)
- Library FAQ: https://docs.python.org/3.15/faq/library.html

**uv**
- Release 0.13.0: https://github.com/astral-sh/uv/releases/tag/0.13.0
- PyPI release dates: https://pypi.org/pypi/uv/json
- `uv python list` output from uv 0.12.6, 0.12.20 through 0.12.24, and 0.13.0, run locally

**ruff**
- Changelog: https://github.com/astral-sh/ruff/blob/main/CHANGELOG.md
- Releases: https://github.com/astral-sh/ruff/releases/tag/0.17.0 and https://github.com/astral-sh/ruff/releases/tag/0.17.1
- Formatter conflict list: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
- Rule pages: https://docs.astral.sh/ruff/rules/<name>/
- Local catalogues from `ruff rule --all --output-format json`: `r165.json` and `r171.json`
- Enabled sets under the shipped asset, from `--show-settings`: `enabled-0.16.5.txt` and `enabled-0.17.1.txt`
- Probes: `lt/`

**ty**
- Changelog: https://github.com/astral-sh/ty/blob/main/CHANGELOG.md
- Releases: https://github.com/astral-sh/ty/releases
- Rules: https://docs.astral.sh/ty/reference/rules/
- Configuration: https://docs.astral.sh/ty/reference/configuration/
- Security advisory: https://github.com/astral-sh/ty/security/advisories/GHSA-vxvm-j4xq-q7m4
- Local catalogues from `ty explain rule --output-format json`: `ty75.json` and `ty89.json`
- Probes: `tyt/`
- Example sweep: `ex/`, results in `ty-ex-*.txt` and `ruff-ex-*.txt`

## CPython rc1 → final

**Dates**, from the PEP 790 "Actual" table and the changelog headings:

| Release | Date |
|---|---|
| rc1 | 2026-08-04 |
| rc2 | 2026-09-01 |
| rc3 (unplanned) | 2026-10-02 |
| **3.15.0 final** | **2026-10-09** |

- Final was planned for 2026-10-01. Lazy-import release blockers forced the extra rc3 (discuss thread 109313).
- The changelog entry for final reads "There were no new changes in version 3.15.0". So rc3 and final are the same code.

**No feature the skill relies on was reverted, renamed or deferred.** The CPython research agent read every commit subject in the rc1-to-final compare.
- The only code revert is gh-157914 (rc3), which reverts gh-146064, a PyMutex spin change. It was reverted because it regressed performance, and semantics are unchanged.

**Code changes after rc1 that touch skill topics.** All of these are in the changelog sections for rc2 and rc3.

- Lazy imports (PS-NAME-15, §2.3):
  - gh-157757: `lazy import a.b as c` now binds the submodule.
  - gh-158140: sibling lazy submodules now resolve independently.
  - gh-155695: `sys.lazy_modules` cleanup.
  - gh-154196: better `AttributeError` messages.
  - **gh-156924:** `annotationlib.ForwardRef.evaluate()` resolves lazy-import proxies. Under FORWARDREF an unresolvable lazy import yields a `ForwardRef`; under VALUE the exception propagates. This supports PS-TYPE-07 as written.
- `TaskGroup.cancel()` (PS-ASYNC-07): gh-155433 (outside cancellation was lost after `cancel()`) and gh-155418 (hang with the eager task factory). Both are fixed in rc3.
- contextvars on the free-threaded build (PS-FT-21, PS-FT-22): gh-155519 (rc2) fixes a data race on reading and writing context variables from different threads. gh-155515 (rc2) fixes a Context iterator leak.
- Dict iteration (PS-FT-08): gh-158254 (rc3). Reverse iterators over a dict and its views now raise `RuntimeError` when the keys change, as forward iterators always did.
- Free-threaded internals that are bug fixes only:
  - gh-157838
  - gh-157377 (`gc.get_count()` could stop cyclic GC)
  - gh-156995
  - gh-156910
  - gh-155400, gh-151377 (type-slot races)
  - gh-155978, gh-155363 (leaks)
  - gh-157660 (`profiling.sampling` line numbers)

**Documentation changed after rc1 in ways that touch skill text:**
1. **The HOWTO sentence the skill quotes was deleted in rc3.**
   - The deleted text: "should be treated as a description of the current implementation, not a guarantee of current or future behavior". Commit 585221fbf347a0f8446c4f921c5835cb4fdaba51.
   - I verified that neither phrase appears in the live 3.15 HOWTO.
   - The HOWTO now points to a new normative page, *Thread Safety Guarantees* (`builtins/threadsafety.html`).
   - That page says "The `sort()` method is not atomic … the list appears empty for the duration of the sort" (verified).
   - The library FAQ is unchanged: it still lists `L.sort()` as atomic and still gives the bytecode-atomicity reason (verified).
2. What's New is no longer marked draft.
3. The PS-MIG-04 table is missing removals that What's New now lists:
   - `importlib.abc.Loader.load_module()`, added to What's New after rc1
   - the C `RLock`'s arbitrary arguments
   - AST node constructors now raising `TypeError`
   - `__cached__` no longer being set
4. The io docs dropped "it is highly recommended that you specify the encoding explicitly" (gh-148603). What's New still tells readers to pass `encoding=`, so PS-FMT-01 remains sourced. The skill does not quote the io sentence (grep).
5. `library/{functions,stdtypes,constants,threadsafety}.html` moved to `builtins/…` (GH-156682). The old paths 301-redirect.
6. abi3t: rc1 said build tools did not support it. Final says meson-python, scikit-build-core and Maturin do.
7. The JIT figures were restated as 7–8% on x86-64 Linux and 11–12% on AArch64 macOS. PS-PERF-16's point stands: configure at v3.15.0 still warns that `--enable-experimental-jit` does not work with `--disable-gil`.

**3.15 claims the agent re-checked and found unchanged:**
- contextlib decorators now hold across a generator
- PEP 686 and its six surfaces
- `frozendict` is not a `dict` subclass
- `singledispatchmethod` dispatches on the second argument
- `sentinel` is a builtin
- `lazy` is module-scope only
- PEP 798 comprehension unpacking
- TypeForm, PEP 728 and `disjoint_base`
- the `profiling` package
- 3.15t is still a separate build, under PEP 779 phase II
- `threading.serialize_iterator`, `synchronized_iterator` and `concurrent_tee` exist under those names (threading.html#iterator-synchronization)
- `sys.flags.thread_inherit_context` and `context_aware_warnings` defaults are unchanged
- `sys._is_gil_enabled` and `PYTHON_GIL` are unchanged

## uv pin

- **Exact key:** `cpython-3.15.0+freethreaded`.
  - `uv python list --all-versions` under uv 0.13.0 lists `cpython-3.15.0+freethreaded-macos-aarch64-none <download available>`.
  - `--all-platforms --all-arches` lists the linux x86_64/aarch64 gnu+musl, macOS x86_64/aarch64 and Windows x86/x86_64/aarch64 builds.
  - The short request `3.15.0t` resolves to the same build.
  - The key matches the `RELEASE` regex in `src/agent_skill/checks/pins.py`.
- **ci.yml must also move `astral-sh/setup-uv` off `0.12.6`.**
  - uv 0.12.6 lists only `cpython-3.15.0rc1+freethreaded`. So do 0.12.20, 0.12.21, 0.12.22, 0.12.23 and 0.12.24 (2026-10-08), all checked locally.
  - **uv 0.13.0 (2026-10-09) is the first release that knows 3.15.0 final**, so the minimum is `0.13.0`. The latest is 0.13.3 (2026-10-20).
  - Source: local listing, PyPI dates, and the uv 0.13.0 release notes ("CPython 3.15.0").
- Consequence for PS-PKG-12:
  - The skill upper-bounds `uv_build` "because uv_build follows uv's versioning policy": `>=0.12.6,<0.13` in assets/pyproject.toml:7 and packaging.md:197.
  - A move to uv 0.13 invites `uv_build>=0.13.x,<0.14`. uv_build 0.13.3 is on PyPI.
  - The old bound still builds, so this is a consistency choice, not a requirement.
- Places that name the interpreter or the uv version:
  - `skills/python-style/assets/ci.yml` lines 23, 25, 38 and 39
  - `src/agent_skill/lang/python.py:30` (`INTERPRETER`)
  - `src/agent_skill/checks/controls.py:147`. This control fixture `edit()`s the literal `uv python install cpython-3.15.0rc1+freethreaded`, so the anchor must change with the pin.
  - The `.cache/python315t` venv must be rebuilt: `uv venv --python cpython-3.15.0+freethreaded .cache/python315t`. I did not do this.

## ruff changes affecting the skill

**Sources for this section:**
- CHANGELOG 0.17.0 and 0.17.1: https://github.com/astral-sh/ruff/blob/main/CHANGELOG.md
- 0.16.6–0.16.10: https://github.com/astral-sh/ruff/blob/main/changelogs/0.16.x.md
- Releases: https://github.com/astral-sh/ruff/releases/tag/0.17.0 and /0.17.1. There is no 0.17.0 blog post; `astral.sh/blog/ruff-v0.17.0` returns 404.
- `#N` means https://github.com/astral-sh/ruff/pull/N.
- Mechanical diff of `ruff rule --all --output-format json` between 0.16.5 (969 rules) and 0.17.1 (971 rules): `r165.json` and `r171.json`.
- Both of my research agents produced the same diff independently.

**Catalogue:**

| Change | Codes |
|---|---|
| Added (both preview-only) | RUF077 method-receiver-default (0.16.7, #26700); UP052 context-manager-iterator (0.16.10, #29000) |
| Stabilised in 0.17.0 | TID254 lazy-import-mismatch (#28760); TID255 lazy-import-immediately-resolved (#28761); RUF071 os-path-commonprefix |
| Removed, deprecated, renamed, recoded or redirected | **none**. The 17 `Removed` statuses are the same set in both versions, and `rule_redirects.rs` is untouched |
| Fix availability changed | PT020 None→Sometimes; PTH208 None→Sometimes; TID254 Always→Sometimes; UP023 and UP026 Always→Sometimes (lazy-import awareness, #28459) |
| Recategorised | FURB152 (preview): correctness→suspicious, fix now unsafe (#28405) |

**Effect on the shipped asset:**
- Under `assets/ruff.toml` the enabled set grows from 786 to **789** codes. `diff` shows exactly +TID254, +TID255 and +RUF071, because `select = ["ALL"]` picks up newly stable rules.
- TID254 is inert until `[lint.flake8-tidy-imports] require-lazy` or `ban-lazy` is set. Those options came with the rule (`ruff config`).
- TID255 is live. It flags a `lazy` import that module load resolves immediately, which is directly relevant to PS-NAME-15.
- RUF071 is live and is not in the skill's migration chapter. ty 0.0.89 independently flags `os.path.commonprefix` as `deprecated` ("Deprecated since Python 3.15").

**Every ruff code the skill, its assets or the harness names** (120 codes, Q000–Q004 expanded):
- All of them exist in 0.17.1.
- None changed name, code, preview status or category.
- Only E111, E114 and E117 are preview-only, as they already were in 0.16.5. The asset only *ignores* them, so nothing changes.
- Full name list: `r171.json`. The ruff agent's report is also in this session.

**Default-behaviour changes that touch the skill:**
1. **The py315 warning is gone** (#28792, 0.17.0). 0.17.1 prints no "Support for Python 3.15 is under development…" with or without preview. 0.16.5 did (verified both). This removes the stated reason for `preview = true` in assets/ruff.toml:14-21 and for `--preview` in `src/agent_skill/lang/python.py:92`.
   - Under 0.17.1, `preview = false` gives a byte-identical enabled set: 789 codes, empty `diff`.
   - Preview still switches on preview *behaviour* inside stable rules, so "byte-identical enabled set" was never "identical behaviour".
2. **Names vs codes:** unchanged. `--preview` still prints rule names, as assets/ruff.toml:8 says, and `output-prefer-rule-codes` is unchanged.
3. **TC001, TC002, TC003 on py315** (#28541, 0.16.8):
   - Lazy imports, including `__lazy_modules__`, are exempt.
   - The fix prefers adding `lazy` to single-name imports, unless `flake8-tidy-imports.ban-lazy` forbids it. The new message is "Make … import `x` lazy" (verified in the probe).
   - The asset's `[lint.flake8-type-checking]` comment describes only the TYPE_CHECKING path, which is now the py≤3.14 behaviour.
   - This now agrees with SKILL.md §2.3 and PS-NAME-15, which tell readers to keep a costly import at module scope with `lazy`. The fix now does exactly that. Worth saying in the asset.
4. **`runtime-evaluated-base-classes` and `runtime-evaluated-decorators`** (#26508, 0.17.0):
   - Each now also accepts a table mapping a name to `"required"` or `"ambiguous"`. The list form the asset uses still works and means "required".
   - Annotations inside function scopes are never runtime-required for decorators (#29183).
5. **Formatter:**
   - There is no new style guide.
   - One stable change: a trailing pragma inside a mixed comment is excluded from the line width (#28795). This also changes I001, E501 and W505.
   - Nested-quote alternation changed in format specs below py312 (#28259).
   - The skill's 52 verified examples format identically under both versions (51 already formatted, the same one file differs in both).
6. **Formatter-conflict list:** unchanged (`docs/formatter.md` is identical apart from the pre-commit `rev`).
   - It still lists W191, E111, E114, E117, D203, D206, D300, Q000–Q004, COM812, COM819, and ISC002 (conditional), which is 15 entries.
   - ISC001 is still not on it.
   - The asset disables all 15. D203 sits under "mutually exclusive" rather than under the conflict header.
   - Verified that `ruff format --check` warns only for COM812 when all of them are selected, in both versions.
7. **Not relevant to the asset:**
   - The default rule set lost the DTZ rules and gained F406 (#28786); the asset selects ALL.
   - The `target-version` default is now py311; the asset sets py315.

**Behaviour or fix changes to codes the skill names:**
- **A001:** now flags `for`, `with … as` and `:=` targets in class bodies (#29076).
- **ANN401:** its documentation now says return types are checked (#28334). That is consistent with PS-TYPE-15.
- **ASYNC230:** now recognises `builtins.open` (#28021).
- **ASYNC240:** new message, and the docs now recommend `asyncio.to_thread` (#28008), which matches PS-ASYNC-13.
- **B006, B008, RUF008:**
  - Defaults built from `weakref.WeakKeyDictionary`, `WeakValueDictionary`, `WeakSet`, `collections.ChainMap`, `UserDict`, `UserList` and `UserString` now report as B006 or RUF008 rather than B008 or RUF009 (#29213).
  - So a dataclass `WeakSet()` default now gets both RUF008 and RUF009.
- **I001, E501, W505:** a trailing pragma no longer counts toward line length (#28795). PS-NAME-18's line-length rule is unaffected in substance.
- **PERF401:** the fix parenthesises ternary and lambda iterables, and drops the fix when a walrus is present (#29366).
- **RET505–RET508:** a safe-fix dedent bug when the `else` body starts with comments is fixed (#29382).
- **SLF001:** no longer flags `object.__new__(cls)` instances (#29001).
- **UP035:**
  - stops rewriting `typing.ByteString` to `collections.abc.ByteString` (#28498)
  - stops suggesting `typing_extensions.no_type_check_decorator` (#28475)
  - suggests `typing.TypeForm` on py315 (#29084), which helps PS-TYPE-20
- **UP040:** **the fix is now always unsafe** (#28526). It skips `TypeVarTuple` and `ParamSpec` with bounds (#28505).
- **UP046, UP047:** the same skip.
- **No behaviour change** for the rest of the skill's codes. The ruff agent checked the changelog and per-file commits from 2026-08-27 to 2026-10-15.

**Harness note:**
- `PYTHON_STYLE.ruff_args` runs `--preview` with `--select=…,UP,…,RUF` and *without* `--explicit-preview-rules`.
- So the snippet run enforces preview rules in those families, and the new preview rules RUF077 and UP052 enter the harness selection under 0.17.1.
- Verified: the 52 verified examples still produce 0 ruff diagnostics with the harness arguments under both 0.16.5 and 0.17.1 (`ruff-ex-*.txt`).

## ty changes affecting the skill

From `ty explain rule --output-format json` on 0.0.75 and 0.0.89, diffed (`ty75.json` and `ty89.json`), and confirmed by the ty research agent against the changelog and the rules page. Each item is at https://docs.astral.sh/ty/reference/rules/#<name>, and the release is https://github.com/astral-sh/ty/releases/tag/0.0.NN.

**Catalogue:**
- 129 rules became 140. Nothing was removed or renamed. Eleven rules were added:

| Rule | Added in | Default |
|---|---|---|
| `missing-direct-dependency` | 0.0.76 | ignore; **preview**, silent without `TY_UV` |
| `disjoint-cast` | 0.0.78 | ignore |
| `redundant-condition` | 0.0.79 | **warn** |
| `redundant-condition-strict` | 0.0.79 | ignore |
| `invalid-init-type-variable` | 0.0.83 | error |
| `truthiness-test-of-callable` | 0.0.83 | **warn** |
| `truthiness-test-of-iterable` | 0.0.83 | **warn** |
| `truthiness-test-of-none-union` | 0.0.85 | ignore |
| `invalid-property-type-override` | 0.0.86 | error |
| `invalid-mutable-override` | 0.0.86 | error since 0.0.87 |
| `mismatched-sentinel-name` | 0.0.87 | ignore |

- Default-level change: `invalid-legacy-positional-parameter` went from warn to **ignore** in 0.0.84 (#28834).

**The default-off set is now 18, not 12.**
- The twelve the asset names are all still `ignore`. None was renamed or removed.
- The six new default-off rules:
  - `disjoint-cast`
  - `invalid-legacy-positional-parameter`
  - `mismatched-sentinel-name`
  - `missing-direct-dependency` (preview)
  - `redundant-condition-strict`
  - `truthiness-test-of-none-union`
- These texts are stale:
  - `assets/ty.toml:8-9` ("twelve rules that are off by default; these are them")
  - SKILL.md:300 ("the twelve ignore-by-default rules")
  - `src/agent_skill/lang/python.py:68` ("The twelve that are off by default")
- Decision for the plan: name the six new ones in the asset, or state why not.
  - `missing-direct-dependency` is preview and needs uv integration.
  - `redundant-condition-strict` and `truthiness-test-of-none-union` are documented as false-positive-prone, which fits the asset's existing `warn` tier.
  - `mismatched-sentinel-name` is the obvious companion to PS-TYPE-22.
  - The harness `ty_rules` table and the asset must move together, because `checks/citations.py` compares them.

**Config claims in ty.toml:**

| Claim | Status in 0.0.89 | Source |
|---|---|---|
| No `strict` preset | Still true: the schema's root sections are unchanged | configuration page |
| `error-on-warning` defaults true since 0.0.52 | Still true | configuration#error-on-warning |
| The four rules are false-positive-prone | Still documented that way | each rule page |
| `all = "error"` enrols future rules | True. It also enables the preview rule `missing-direct-dependency`. A per-rule key beats `all` regardless of order | configuration#rules |
| `[analysis] strict-equality-semantics` | Unchanged | configuration page |
| `[analysis] strict-generic-narrowing` | Unchanged; its description now also covers `TypeIs` narrowing | configuration page |

- New option `[analysis] return-type-inference = "never" | "always"`, default `never`, added in 0.0.89 (#29253). Unannotated returns are still `Unknown` by default, so PS-API-06's "ty does not require annotations at all" stays true.
- The concise output shape `path:line:col: <severity>[<rule>] message` is unchanged across 0.0.75 through 0.0.89. Severity prints as `error`, `warning` or `info`.
  - The asset's word "stable" is not something Astral promises: UNCONFIRMED as a guarantee.
  - The harness `DIAGNOSTIC` regex still matches.
- Python 3.15:
  - 0.0.79 declared support.
  - 0.0.86 made 3.15 the default `python-version` (#28792). The asset's `python-version = "3.15"` is now redundant but harmless.
  - TypeForm, PEP 728 closed/`extra_items`, the `sentinel` builtin, `disjoint_base`, `frozendict` and `lazy import` all type-check in both 0.0.75 and 0.0.89 (ty agent probes). Verified myself: `closed=True` TypedDict extra key → `invalid-key`, and `frozendict` and `sentinel` resolve.

**Diagnostics the skill relies on, and what changed under them:**
- **Newly flagged by 0.0.89, which was silent on 0.0.75** (verified), both via typeshed updates:
  - `asyncio.iscoroutinefunction` → `deprecated` (warn). This backs PS-ASYNC-03 and PS-MIG-13.
  - `os.path.commonprefix` → `deprecated`
- **Unchanged in both versions** (verified):
  - `get_event_loop_policy` and `set_event_loop_policy` → `deprecated`
  - every PS-MIG-04 removal → `unresolved-attribute`, `unresolved-import` or `unknown-argument`
- **PS-TYPE-03 problem, identical in 0.0.75 and 0.0.89** (verified, `tyt/ign.py`):
  - `blanket-ignore-comment` fires only on a bare `# ty: ignore`.
  - A bare `# type: ignore` is silently honoured as a blanket suppression.
  - `# type: ignore[assignment]` (the rule's own example) does **not** suppress the ty error.
- **Upgrade risk to user code:**
  - New default-on warn rules fail a run under `error-on-warning`: `redundant-condition` and `truthiness-test-of-callable/iterable`.
  - So do the new error rules.
  - Instantiating an abstract class is now `call-non-callable` (0.0.82, #28167).
  - Reassigning an enum member is rejected (0.0.81).
- **The skill's own examples are unaffected.** All 52 `# verified` Python blocks give 0 diagnostics under both 0.0.75 and 0.0.89, using the harness's ty config and a venv with pytest 9.1.1 (`ty-ex-*.txt`). Execution on 3.15.0 final was not tested, because no interpreter was installed.
- **Security:** 0.0.84 fixes GHSA-vxvm-j4xq-q7m4, a use-after-free during incremental checking. 0.0.75 is affected. This is a reason for the bump in itself.
- **Release cadence:** typing.md:61 says "Its last twenty releases were zero to six days apart". That is now false: 0.0.84 (2026-09-24) to 0.0.85 (2026-10-06) was 12 days (PyPI dates).

## Lint classification

Method:
- Every code below was checked against the `ruff rule --all --output-format json` catalogue of ruff 0.17.1 and the `ty explain rule --output-format json` catalogue of ty 0.0.89.
- Where it says "verified", the code was also seen firing (or staying silent) on a probe file:
  - ruff probe: `scratchpad/lt/`
  - ty probe: `scratchpad/tyt/`
- "asset ON" means the code is in `linter.rules.enabled` from `ruff@0.17.1 check --config skills/python-style/assets/ruff.toml --show-settings`. With the 0.17.1 binary that set has 789 codes; with 0.16.5 it had 786 (`scratchpad/enabled-0.17.1.txt`).
- "off (preview)" means the code exists but is preview-only. `explicit-preview-rules = true` keeps it out of `ALL`, so to enable it you must name it in `extend-select`.
- For ty, "default" is the rule's built-in level. "asset" means `assets/ty.toml` raises it.

Two things the planner should keep in mind:
- The `citations` check (`src/agent_skill/checks/citations.py`) fails any rule that cites a code missing from the asset's enabled set. A lint-table row for a preview code will fail it unless the asset also adds that code to `extend-select`.
- Read "LINT" as: collapsing the rule into a table row loses only the rationale. Read "PARTIAL" as: collapsing it loses a prescriptive clause, and the Notes column names that clause.

### SKILL.md §4 core rules

| ID | Class | Code(s) | Enabled in assets? | Notes |
|---|---|---|---|---|
| PS-CORE-01 | PARTIAL | N801–N818, plus `ruff format --check` | N: ON. Formatter: ci.yml `lint` job | No lint checks SCREAMING_SNAKE_CASE for module constants or the trailing-underscore convention |
| PS-CORE-03 | PARTIAL | RET505, RET506, RET507, RET508, PLR0911 | ON | These cover else-after-return only. The guard-first shape itself is review |
| PS-CORE-05 | LINT (gate) | `ty check` with assets/ty.toml | ci.yml `lint` job | The rule *is* the tool |
| PS-CORE-07 | LINT | UP006, UP007, UP035, UP040, UP045, UP046, UP047 | ON | |
| PS-CORE-08 | PARTIAL | ANN401 | ON | Requires a comment on every `Any`; prefers `object` |
| PS-CORE-11 | LINT | B006, B008, RUF008, RUF009 (also RUF012) | ON. The harness snippet run ignores B008, but the asset enables it | |
| PS-CORE-13 | PARTIAL | E722, BLE001, S110, SIM105 (also S112) | ON | "Cannot handle" is review |
| PS-CORE-14 | LINT | **B012** jump-statement-in-finally | ON | Not cited anywhere in the skill. Verified firing on `return` in `finally` |
| PS-CORE-15 | LINT | S101 | ON (ignored under tests/) | |
| PS-CORE-23 | PARTIAL | ANN001, ANN201 (and the rest of ANN0xx/ANN2xx), F401 in `__init__.py` | ON | The re-export half is F401's hint. "Pick one style" is not checked |
| PS-CORE-24 | LINT (off) | PLW1514 unspecified-encoding | **off (preview)** | Verified preview in 0.17.1 |
| PS-CORE-25 | PARTIAL | G001, G002, G003, G004 | ON | "Never configure logging in a library" is not linted |

### references/*.md

| ID | Class | Code(s) | Enabled in assets? | Notes |
|---|---|---|---|---|
| PS-NAME-01 | PARTIAL | N801–N818 (N804/N805 cover `self`/`cls`) | ON | Constant casing is not linted, although the rule's Check claims "N decides all of it" |
| PS-NAME-07 | LINT | A001, A002, A003 (also A004, A005, A006) | ON | |
| PS-NAME-10 | LINT | I001 | ON | |
| PS-NAME-11 | PARTIAL | TID252 | ON, but default `ban-relative-imports = "parents"` | Verified: `from .sibling import x` does **not** fire, `from ..up import x` does. Setting `[lint.flake8-tidy-imports] ban-relative-imports = "all"` makes this LINT. That setting would also flag PS-NAME-13 and PS-API-02's own `from ._core import Widget as Widget` |
| PS-NAME-12 | LINT | F403, F405 | ON | |
| PS-NAME-13 | PARTIAL | F401 (in `__init__.py`, with the hint to use a redundant alias or `__all__`) | ON | Verified. "Pick one per project" is not linted |
| PS-NAME-15 | PARTIAL | PLC0415 import-outside-top-level; TID255 lazy-import-immediately-resolved; TID254 lazy-import-mismatch | PLC0415 ON. TID254 and TID255 are **newly ON**: they became stable in 0.17.0 and `ALL` picks them up | TID254 does nothing until `[lint.flake8-tidy-imports] require-lazy` is set (a 0.17 option). `require-lazy = "all"` would mechanise the "use `lazy`" half |
| PS-NAME-17 | LINT (gate) | `ruff format --check` | ci.yml | |
| PS-NAME-18 | PARTIAL | E501 (88 columns); W505 doc-line-too-long (72 columns) | E501 ON. W505 ON but **inert**, because `max-doc-length` is unset | Adding `[lint.pycodestyle] max-doc-length = 72` makes it LINT |
| PS-NAME-19 | LINT (formatter) | `ruff format`, `skip-magic-trailing-comma = false` | asset [format] | |
| PS-NAME-21 | PARTIAL | E262, E265, E266 (also E261) | off (preview) | Still preview in 0.17.1, so the rule's text is still accurate. Capitalisation and full stop are not linted |
| PS-NAME-22 | LINT | ERA001 | ON | |
| PS-TYPE-01 | LINT (gate) | `ty check` | ci.yml | |
| PS-TYPE-03 | PARTIAL | PGH003 (bare `# type: ignore`); ty `blanket-ignore-comment` (bare `# ty: ignore` only) | PGH003 ON. blanket-ignore-comment is `error` in the asset (default ignore) | See accuracy note A |
| PS-TYPE-05 | LINT | UP037 | ON | Verified firing at py315 with no `__future__` import |
| PS-TYPE-06 | PARTIAL | RUF063 access-annotations-from-class-dict | ON | Covers only the `__dict__["__annotations__"]` and `.get` forms, not `obj.__annotations__` |
| PS-TYPE-08 | LINT | UP007, UP045, RUF036 none-not-at-end-of-union | ON | RUF036 is not cited by the skill but covers "None last". Verified |
| PS-TYPE-09 | LINT | UP006, UP035 | ON | Verified that UP035 rewrites `typing.Callable` |
| PS-TYPE-10 | LINT | UP046, UP047 | ON | |
| PS-TYPE-11 | PARTIAL | UP040 | ON | Bare-assignment aliases (`X = int`) are not detected. Since 0.17 the UP040 fix is always unsafe |
| PS-TYPE-12 | PARTIAL | UP046, UP047 (flag the legacy TypeVar that carries hand-written variance) | ON | Verified UP046 fires on a `covariant=True` TypeVar class |
| PS-TYPE-13 | PARTIAL | UP019 (Text), UP047 (AnyStr as a legacy TypeVar), PYI057 (ByteString), UP013, UP014 (functional forms); ty `unresolved-attribute` (no_type_check_decorator) | all ON / ty default error | `# type:` comments and the `Unpack` clause are not linted |
| PS-TYPE-15 | PARTIAL | ANN401 | ON | Since 0.17, ANN401 also covers return types (explanation diff) |
| PS-DATA-02 | PARTIAL | SLOT000, SLOT001, SLOT002 | ON | `slots=True` on dataclasses is not linted |
| PS-DATA-08 | LINT | B006, RUF008 (also RUF012) | ON | The rule cites RUF009 for "dataclass forms". RUF009 is call-in-default, which is PS-DATA-10's concern. Since 0.17.1, weakref and `collections.User*`/`ChainMap` defaults also count as mutable (#29213) |
| PS-DATA-09 | PARTIAL | RUF008 | ON | A custom mutable `field(default=...)` is review |
| PS-DATA-10 | PARTIAL | RUF009 (dataclass), B008 (function defaults) | ON | Non-dataclass class bodies are not covered |
| PS-DATA-11 | PARTIAL | ty `dataclass-field-order` | default error | Verified. The KW_ONLY design half is review |
| PS-DATA-20 | PARTIAL | PLW1641 eq-without-hash | ON | Verified. It fires on *every* `__eq__` without `__hash__`, including the mutable case the rule calls correct, so that case needs a `noqa` |
| PS-ERR-05 | PARTIAL | TRY002 | ON | The "RuntimeError as a general complaint" clause is review. TRY004 is a different concern |
| PS-ERR-06 | LINT | B904 | ON | |
| PS-ERR-07 | LINT | EM101, EM102 (also EM103) | ON | |
| PS-ERR-08 | LINT | S101 | ON | |
| PS-ERR-09 | LINT | E722 | ON | |
| PS-ERR-10 | PARTIAL | BLE001 | ON | |
| PS-ERR-11 | PARTIAL | S110, SIM105 (also S112) | ON | |
| PS-ERR-14 | PARTIAL | SIM401 (also RUF019) | ON | |
| PS-ERR-15 | LINT | **B012** | ON | The rule's Check is a grep, and the profile lists it as NotDecisive. B012 is decisive and stable. Verified |
| PS-ERR-16 | PARTIAL | SIM115 open-file-with-context-handler | ON | Covers `open` only |
| PS-ERR-18 | PARTIAL | RET505–RET508, PLR0911 | ON | |
| PS-ERR-19 | PARTIAL | SIM103, SIM108, SIM110 (also SIM201, SIM202, SIM208) | ON | |
| PS-ASYNC-02 | PARTIAL | ty `deprecated` | default warn (blocks under error-on-warning) | Verified: flags `get_event_loop_policy` and `set_event_loop_policy`. Does **not** flag `get_event_loop`, `new_event_loop`, `AbstractEventLoopPolicy` or `DefaultEventLoopPolicy` |
| PS-ASYNC-03 | LINT | ty `deprecated` | default warn | Verified **new in 0.0.89**: 0.0.75 was silent on `asyncio.iscoroutinefunction` |
| PS-ASYNC-05 | LINT | RUF006 | ON | |
| PS-ASYNC-12 | PARTIAL | ASYNC210, ASYNC212, ASYNC220, ASYNC221, ASYNC222, ASYNC230, ASYNC240, ASYNC250, ASYNC251 | ON (all stable in 0.17.1) | Verified firing. CPU-bound blocking is review |
| PS-ASYNC-14 | LINT | ASYNC251 | ON | |
| PS-ASYNC-20 | LINT (off) | RUF029 unused-async | off (preview) | Still preview in 0.17.1, so the rule's text is accurate |
| PS-FMT-01 | LINT (off) | PLW1514 (plus the runtime `-X warn_default_encoding`) | off (preview) | Still preview in 0.17.1 |
| PS-FMT-06 | PARTIAL | UP031, UP032 (also FLY002) | ON | Concatenation is not linted |
| PS-FMT-07 | PARTIAL | S608, S602–S607 | ON | Paths and markup are not linted |
| PS-FMT-11 | LINT | G001, G002, G003, G004 | ON | |
| PS-FMT-12 | PARTIAL | LOG015, LOG002 (also LOG001) | ON | Hand-written names and module scope are not linted |
| PS-FMT-13 | LINT | TRY400, TRY401 | ON | |
| PS-FMT-17 | LINT | T201, T203 | ON | |
| PS-PERF-07 | LINT (off) | PLR6201 literal-membership | off (preview) | Still preview in 0.17.1, so the rule's text is accurate |
| PS-PERF-09 | PARTIAL | C419 (C4 family) | ON | |
| PS-PERF-14 | LINT | PERF401, PERF402 | ON | |
| PS-API-02 | PARTIAL | F401 in `__init__.py` | ON | Duplicate of PS-NAME-13 |
| PS-API-05 | PARTIAL | SLF001 (attribute access); PLC2701 import-private-name (the import form) | SLF001 ON. PLC2701 **off (preview)** | Verified that PLC2701 fires on `from other._internal import x`. Selecting it makes this LINT |
| PS-API-06 | LINT | ANN001, ANN201 (and the rest of ANN0xx/ANN2xx) | ON | |
| PS-API-07 | PARTIAL | PLR0917 too-many-positional-arguments, PLR0913 | ON | They catch more than 5 positional parameters; the rule's threshold is 2 |
| PS-API-08 | LINT | FBT001, FBT002, FBT003 | ON | |
| PS-API-12 | LINT | B006, B008 | ON | Duplicates PS-DATA-08 and PS-CORE-11 |
| PS-API-16 | LINT (off) | RUF067 non-empty-init-module (with `lint.ruff.strictly-empty-init-modules` for the strict form) | off (preview) | RUF067 is not cited by the skill. Verified that PLC0414 exempts `__init__.py`, so `from x import Y as Y` re-exports pass the asset |
| PS-DOC-01 | LINT | D100–D107 | ON | |
| PS-DOC-02 | PARTIAL | D200, D415 | ON. D401 is off (google convention) | |
| PS-DOC-03 | LINT | D205, D209 | ON | |
| PS-DOC-04 | LINT | formatter docstring-quote normalisation, D301 | ON. D300 is deliberately off (conflict list) | |
| PS-DOC-05 | LINT (inert) | W505 | ON but inert without `max-doc-length = 72` | The rule says "a review matter". That is stale advice: W505 exists and only needs the setting |
| PS-DOC-07 | LINT | D417 | ON | |
| PS-DOC-09 | PARTIAL | DOC501, DOC502 | off (preview) | Verified that DOC501 fires |
| PS-DOC-13 | PARTIAL | D417 (missing params only); DOC102 docstring-extraneous-parameter | D417 ON. DOC102 off (preview) | See accuracy note B |
| PS-TEST-11 | PARTIAL | PT006, PT007 | ON | |
| PS-TEST-14 | PARTIAL | PT003 | ON | |
| PS-TEST-18 | PARTIAL | PT011, PT012 | ON | PT011 fires only for `raises-require-match-for`, whose default list is BaseException, Exception, ValueError, OSError, IOError, EnvironmentError and socket.error. Verified that `pytest.raises(KeyError)` without `match` is silent. Setting `[lint.flake8-pytest-style] raises-require-match-for = ["*"]` makes this LINT |
| PS-TEST-20 | PARTIAL | DTZ005 | ON | Clock injection is review |
| PS-MIG-04 | LINT | ty `unresolved-attribute` / `unresolved-import` / `unknown-argument` at `python-version = "3.15"` | ty default error | Verified that all twelve rows are flagged by ty 0.0.89: SetPointerType, glob0, CGIHTTPRequestHandler, `files(package=)`, is_reserved, java_ver, sre_compile, `is_python_build(check_home=)`, co_lnotab, no_type_check_decorator, wave getmark/setmark/getmarkers, zipimporter.load_module |
| PS-MIG-06 | LINT | UP013, UP014; ty `missing-argument` | ON / ty error | Verified on `NamedTuple("P", x=int)` and `TypedDict("TD")` |
| PS-MIG-08 | LINT | PYI057; ty `unresolved-attribute` (collections.abc.ByteString) | ON / ty error | Verified. ty treats `collections.abc.ByteString` as absent at 3.15 but accepts `typing.ByteString` |
| PS-MIG-09 | PARTIAL | ty `unresolved-attribute` | ty error | Verified on `json.__version__` only |
| PS-MIG-12 | PARTIAL | PLW1514 | off (preview) | |
| PS-MIG-13 | PARTIAL | ty `deprecated` | default warn | Same coverage as PS-ASYNC-02 plus PS-ASYNC-03. The policy *classes* are not flagged |

Gate or formatter rows that have no lint code (PS-NAME-17, PS-NAME-19, PS-TYPE-01, PS-CORE-05, PS-DOC-04) can become a "tools" row instead of a lint-code row.

### Rules whose Check cites a lint that does not enforce the rule (NONE, but the planner should know)

| Rule | Lint cited | What that lint actually checks |
|---|---|---|
| PS-NAME-03 | SLF001 | Access to someone else's private member, not the choice between `_` and `__` |
| PS-NAME-16 | INP001 | A missing `__init__.py`, not the src layout |
| PS-NAME-20 | ERA001 | Commented-out code (that is PS-NAME-22's job) |
| PS-API-01 | F822 | That the names in an existing `__all__` exist, not that `__all__` is present |
| PS-API-11 | ARG | Unused arguments |
| PS-TYPE-18 | "ruff PYI for the stub cases" | Nothing that requires `@final` or `Final` |
| PS-ASYNC-08 | "ASYNC and BLE001" | No ruff rule detects a swallowed `CancelledError` |

ty also *checks* some constructs once you have written them, though nothing makes you write them:
- `assert_never` exhaustiveness → `type-assertion-failure`
- `Final` reassignment → `invalid-assignment`
- subclassing a `@final` class → `subclass-of-final-class`
- sentinel naming → `mismatched-sentinel-name` (default ignore, new in 0.0.87)

### Accuracy notes found while verifying

- **A. PS-TYPE-03.** Verified the same way on ty 0.0.75 and 0.0.89:
  - `blanket-ignore-comment` flags only a bare `# ty: ignore`.
  - A bare `# type: ignore` is honoured as a blanket suppression, and ty does not report it.
  - `# type: ignore[assignment]` does **not** suppress a ty diagnostic. ty does not know mypy's codes, so the error is still reported.
  - So the rule's example spelling does nothing under the mandated checker. The ty-native form is `# ty: ignore[invalid-assignment]`.
  - PGH003 is what catches a bare `# type: ignore`.
- **B. PS-DOC-13** says "`D417` catches a documented parameter that is not in the signature and vice versa".
  - Verified: D417 is silent on an extraneous documented parameter.
  - The rule that catches it is DOC102 docstring-extraneous-parameter, which is preview.
- **C. PS-PERF-06** says "the ruff rules that catch the mechanical cases are preview". No ruff 0.17.1 rule, preview or stable, detects `s += piece` string building in a loop; I searched the catalogue explanations. UNCONFIRMED which rule was meant.
- **D. §2.3 `sum(lists, [])`.**
  - RUF017 quadratic-list-summation is stable and ON.
  - On py315 its fix *is* `[*sublist for sublist in lists]`.
  - So this §2.3 row is fully lint-backed.
- **E. §2.3 "moving an import into a function".** PLC0415 flags it, and TID254 with `require-lazy` can require `lazy`.
- **F.** `from __future__ import annotations` (PS-TYPE-04, PS-CORE-06) still has **no** ruff 0.17.1 rule: verified silent with `--preview --select ALL`. The PS-TYPE-04 sentence "ruff has no rule for this yet" stays true. The grep in the profile (`FUTURE_ANNOTATIONS`) remains the only enforcement.

## Stale claims

### A. Stale because of the version move: must change with the pins

| Location | Now says | Should reflect | Evidence |
|---|---|---|---|
| assets/ci.yml:23, :38 | `setup-uv` `version: "0.12.6"` | at least `0.13.0`: older uv cannot install 3.15.0 | uv listing, PyPI |
| assets/ci.yml:25, :39 | `cpython-3.15.0rc1+freethreaded` | `cpython-3.15.0+freethreaded` | uv listing |
| assets/ruff.toml:1 | "Validated against ruff 0.16.5" | 0.17.1 | |
| assets/ruff.toml:8 | "0.16 prints rule NAMES rather than codes when preview is on" | Still true in 0.17.1 (verified: `--preview` prints `unused-import:`). Only the version label changes | `lt/` probe |
| assets/ruff.toml:14-21 | "preview: required for Python 3.15 semantics, and without it every run prints 'Support for Python 3.15 is under development…'" | **False in 0.17.1** (verified) | See note below |
| assets/ruff.toml, `[lint.flake8-type-checking]` comment | "At py314+ a TC001-TC003 fix moves the import into TYPE_CHECKING and leaves the annotation UNQUOTED" | Incomplete for py315 in 0.17. Those rules now exempt lazy imports, and their fix *prefers adding `lazy`*, controlled by the new `ban-lazy` | `ruff rule TC003` diff; probe message "Make standard library import … lazy" |
| assets/ty.toml:1 | "Validated against ty 0.0.75" | 0.0.89 | |
| assets/ty.toml:8-9 | "twelve rules that are off by default; these are them" | 18 | `ty89.json` |
| assets/pyproject.toml:45-46 | `ruff==0.16.5`, `ty==0.0.75` | the new pins | |
| assets/pyproject.toml:7, packaging.md:197 (PS-PKG-12) | `uv_build>=0.12.6,<0.13` | optional: `>=0.13.x,<0.14` if CI's uv moves to 0.13 | |
| SKILL.md:300 | "the twelve ignore-by-default rules" | 18, or "the default-off rules" | |
| references/typing.md:52 (PS-TYPE-01) | `ty==0.0.75` | 0.0.89 | |
| references/typing.md:61 | "last twenty releases were zero to six days apart" | false: a 12-day gap from 0.0.84 to 0.0.85 | PyPI |
| references/packaging.md:145 (PS-PKG-08) | `ruff==0.16.5`, `ty==0.0.75` | the new pins | |
| repo pyproject.toml:24 | `ruff==0.16.5`, `ty==0.0.75` | the new pins | |
| src/agent_skill/lang/python.py:30 | `INTERPRETER = "cpython-3.15.0rc1+freethreaded"` | `cpython-3.15.0+freethreaded` | |
| src/agent_skill/lang/python.py:68 | "The twelve that are off by default" | 18 | |
| src/agent_skill/lang/python.py:92 | `--preview` in `ruff_args` | The same stated reason as ruff.toml:14-21, now gone. The flag still matters in two ways. First, it prints names instead of codes; the `DIAGNOSTIC` regex keeps `rest` verbatim, so only the message text changes. Second, without `--explicit-preview-rules` it enforces preview rules in the selected families, which now include RUF077 and UP052 | `ruff-ex-*.txt` |
| src/agent_skill/checks/controls.py:147 | control anchor `uv python install cpython-3.15.0rc1+freethreaded` | must match the new ci.yml text, or the control's `edit` finds nothing | |
| src/agent_skill/checks/controls.py:482 | control anchor `typecheck = ["ty==0.0.75"]` | must match the new asset | |
| src/agent_skill/checks/citations.py:9-10 | "the enabled set is 786 codes" | 789 under 0.17.1 (TID254, TID255 and RUF071 became stable) | `enabled-*.txt` |

Note on assets/ruff.toml:14-21:
- Without preview, 0.17.1 prints no 3.15 warning, and `lazy import` and PEP 798 parse fine.
- With `preview = false` the enabled set is byte-identical: 789 codes, `diff` empty.
- So the preview-plus-`explicit-preview-rules` pair now has no stated reason.
- The pair still turns on preview *behaviour* inside stable rules, which is a reason to drop it, not keep it.
- If preview goes, `output-prefer-rule-codes` also loses its reason.

### B. Stale or inaccurate for 3.15.0 final (CPython)

| Location | Claim | Status | Source |
|---|---|---|---|
| SKILL.md:88-91 (§2.2); free-threading.md:247-251 (PS-FT-05) | The HOWTO says the locking is "a description of the current implementation, not a guarantee" | **Deleted from the HOWTO in rc3** (verified absent). Replaced by *Thread Safety Guarantees*, which documents guarantees. Rewrite the argument around that page; the FAQ half of the argument still stands | commit 585221f; builtins/threadsafety.html |
| free-threading.md:242-243 (PS-FT-05) | "`L.append(x)`, `D[x] = y`, `D1.update(D2)`, `L.sort()` are each individually safe" | `L.sort()` is wrong: "The sort() method is not atomic … the list appears empty for the duration of the sort" (verified). The other three match the page | builtins/threadsafety.html |
| references/migration.md:249 (PS-MIG-14) | "3.16 has had no alpha release" | **Outdated:** 3.16.0a1 shipped 2026-10-13 | PEP 826; python.org/downloads/release/python-3160a1/ (200) |
| references/migration.md:282-284 (PS-MIG-16) | "What's New was still marked draft" | Outdated: the draft banner was removed at final | rc1→final compare |
| references/migration.md PS-MIG-04 table | the list of 3.15 removals | Missing four: `importlib.abc.Loader.load_module()`, C `RLock` arbitrary args, AST node constructor `TypeError`, `__cached__` | What's New §Removed |
| references/migration.md:179 (PS-MIG-09) | "twenty-three modules" | 24 in final What's New | What's New §New deprecations |
| references/migration.md:186-188 (PS-MIG-09 Check) | regex `\. __version__` | **Can never match**: a stray space inside the pattern. Not version-related | verified by reading |
| references/strings-and-output.md:154 (PS-FMT-08) | t-strings "New in 3.15" | Wrong, and wrong before rc1 too: PEP 750 is 3.14, and templatelib says "Added in version 3.14" | peps.python.org/pep-0750; library/string.templatelib.html |
| references/performance.md:61, :69 (PS-PERF-02) | "Not `cProfile`"; every `cProfile` hit has a replacement | cProfile "remains available as an alias to profiling.tracing … in all future Python versions" and is not deprecated. `profile` is still pending removal in 3.17 | library/profiling.html#legacy-compatibility |
| SKILL.md:209-210 (PS-CORE-14); errors-and-control-flow.md:289 (PS-ERR-15) | PEP 765 "will become an error" / "is scheduled to become an error" | PEP 765 leaves "whether, and when" open. 3.15 is still a compile-time SyntaxWarning. This predates rc1 | peps.python.org/pep-0765 |
| references/typing.md:470-471 (PS-TYPE-22) | sentinels "survive copying and pickling, which `object()` does not" | Only a sentinel bound at module or class scope under its own name pickles. One created in a function does not | builtins/functions.html#sentinel |
| SKILL.md:224-226 (PS-CORE-19); free-threading.md (PS-FT-13) | "everything else silently duplicates or drops elements" | Too broad. The shared `range` iterator (gh-129068) and several itertools iterators (chain, cycle, product, combinations, permutations, accumulate, zip_longest) are documented safe under free threading in 3.15. This predates rc1 | changelog a4/b-series entries |

Unchanged and confirmed, so nothing to do:
- every §2.1 row
- every §2.3 and §2.4 row
- PS-NAME-15's scope rules for `lazy`
- PS-FT-14, PS-FT-15 and PS-FT-17's API names
- PS-FT-22's context-inheritance defaults
- PS-PERF-16 (the JIT is unusable on free-threaded builds)
- PS-PERF-17's 20%
- PS-PKG-19, PS-PKG-20 and PS-PKG-21

### C. Inaccurate tool claims found while classifying (the tool versions do not change these)

- **PS-TYPE-03:**
  - The example `# type: ignore[assignment]` does not suppress a ty diagnostic.
  - `blanket-ignore-comment` does not catch a bare `# type: ignore`. PGH003 does.
  - Verified identically on 0.0.75 and 0.0.89.
- **PS-DOC-13:** D417 does not catch a documented parameter that is not in the signature. DOC102 does, and DOC102 is preview (verified).
- **PS-DOC-05:** "a review matter". W505 with `max-doc-length = 72` decides it, and W505 is stable and already in the enabled set, though inert.
- **PS-PERF-06:** "the ruff rules that catch the mechanical cases are preview". No 0.17.1 rule, preview or stable, matches string `+=` in a loop (catalogue search). UNCONFIRMED which rule was meant.
- **PS-DATA-08:** cites RUF009 for the "dataclass forms" of a mutable default. RUF009 is call-in-default; RUF008 and RUF012 are the mutable ones.
- **PS-NAME-01:** "N decides all of it". No N rule checks constant casing.
- **PS-ERR-15, PS-CORE-14:** B012 (stable, ON) is the decisive lint, but the rule uses a grep and the profile marks it NotDecisive.
- **PS-NAME-11** versus **PS-NAME-13 / PS-API-02:**
  - TID252 at its default only flags parent-relative imports.
  - Making PS-NAME-11 enforceable (`ban-relative-imports = "all"`) would flag the relative re-export example `from ._core import Widget as Widget` that the other two rules show.
