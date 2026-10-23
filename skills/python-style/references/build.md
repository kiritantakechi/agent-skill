# Packaging: Metadata, Dependencies, Locking, Publishing, and the Free-Threaded Wheel

Scope: what `pyproject.toml` must say, how dependencies are declared and pinned, how a package is
built and published, and what the free-threaded build demands of a dependency tree. Module and
package layout is the naming chapter; the public surface is the API chapter.

Two sources are merged here: the **PyPA living specifications** at
`packaging.python.org/specifications`, which is where every packaging PEP now redirects — 621, 639,
735 and 751 all carry a "this PEP is a historical document" banner — and the **empirical conventions
of `uv`**, which scaffolds the layout this chapter prescribes. Ruff's `INP` and `TID` families reach
only the edges of this; most of it is a review matter with a runnable command.

Unless a block shows its own imports, it assumes nothing beyond the standard library.

## Contents

- **Metadata**
  - PS-BUILD-01 [M] Cite the living specification, never the PEP
  - PS-BUILD-02 [M] Keep `[project]` static; use `dynamic` only where a backend computes it
  - PS-BUILD-03 [M] Write the licence as an SPDX expression, and ship `license-files`
  - PS-BUILD-04 [M] Give `requires-python` a floor and no ceiling
  - PS-BUILD-05 [M] Use the well-known `[project.urls]` labels
  - PS-BUILD-06 [M] Classify the package honestly, including its typing and threading status
- **Dependencies**
  - PS-BUILD-07 [M] Put development tooling in `[dependency-groups]`, never in extras
  - PS-BUILD-08 [M] Pin every tool that decides whether the build passes
  - PS-BUILD-09 [M] Give a library floors, not pins
  - PS-BUILD-10 [M] Commit `uv.lock`, and keep it the only lock artefact
  - PS-BUILD-11 [M!] Refuse a dependency published in the last few days
- **Building**
  - PS-BUILD-12 [M] Build with `uv_build`, and never invoke `setup.py`
  - PS-BUILD-13 [M] Build the package from `src/`, and ship `py.typed`
  - PS-BUILD-14 [M] Give the distribution and the module the same name
  - PS-BUILD-15 [M] Keep the built artefact reproducible from the repository alone
- **Publishing**
  - PS-BUILD-16 [M] Publish with Trusted Publishing, never a long-lived token
  - PS-BUILD-17 [S] Emit attestations, and do not rely on anyone verifying them
  - PS-BUILD-18 [M] Cut a new version rather than adding a file to an old release
- **The free-threaded build**
  - PS-BUILD-19 [M] A free-threaded wheel tag is not a declaration of thread safety
  - PS-BUILD-20 [M] Assert in CI that the GIL is actually off
  - PS-BUILD-21 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

---

## Metadata

### PS-BUILD-01 [M] Cite the living specification, never the PEP

`packaging.python.org/en/latest/specifications/pyproject-toml/`, not PEP 621. The same applies to
typing: `typing.python.org/spec`, not PEP 484.

**Why:** every packaging PEP this chapter would otherwise cite now opens with *"This PEP is a
historical document"* and redirects to the PyPA specifications. A PEP records what was decided
once; the specification is the maintained text and records what is true now.

**Check:** every packaging or typing reference in the project's own documentation. A bare PEP number
as the normative citation is the finding; naming the PEP as provenance alongside the spec is fine.

### PS-BUILD-02 [M] Keep `[project]` static; use `dynamic` only where a backend computes it

Version from a VCS tag is a legitimate `dynamic`. Everything else should be written down.

**Why:** static metadata can be read without executing anything, which is what lets an index, a
resolver, or a security scanner answer questions about your package without installing it. Every
`dynamic` field is one those tools must give up on.

**Check:** the `dynamic` list. Each entry needs the backend hook that computes it.

### PS-BUILD-03 [M] Write the licence as an SPDX expression, and ship `license-files`

`license = "MIT"` as a **string**. Not `{ text = ... }`, not `{ file = ... }`, and no
`License :: OSI Approved ::` classifier.

**Why:** the table forms and the licence classifiers are both deprecated in favour of an SPDX
expression, which names exactly one licence where the classifier and the free-text field could
disagree. `license-files` puts the actual text in the distribution, which several licences require.

**Check:** `rg -n 'License ::' pyproject.toml` and `rg -n 'license' pyproject.toml` — a table
form or a classifier is the finding.

```toml
# verified — GOOD
[project]
name = "acmewidget"
version = "0.1.0"
requires-python = ">=3.15"
license = "MIT"
license-files = ["LICENSE"]
classifiers = [
  "Programming Language :: Python :: Free Threading :: 2 - Beta",
  "Typing :: Typed",
]
```

### PS-BUILD-04 [M] Give `requires-python` a floor and no ceiling

`>=3.15`. Never `<4`, never `<3.16`. If a future version genuinely breaks the package, yank or
patch then.

**Why:** an upper bound is a promise about interpreters that do not exist yet: it makes the package
uninstallable on the next release even where it would have worked, and only a new release from you
fixes it. PyPA advises against it for exactly this reason.

**Check:** `rg -n 'requires-python' pyproject.toml` — any `<` is the finding.

### PS-BUILD-05 [M] Use the well-known `[project.urls]` labels

`homepage`, `source`, `issues`, `changelog`, `documentation` — lowercase. Normalisation strips
punctuation and case, so `"Bug Tracker"` does work, but the plain label is the safe spelling.

**Why:** the labels are normalised and recognised, so an index can render the right icons and a
tool can find your issue tracker without guessing. Ad-hoc labels render as plain text.

**Check:** the `[project.urls]` table against the well-known list.

### PS-BUILD-06 [M] Classify the package honestly, including its typing and threading status

`Typing :: Typed` when you ship `py.typed`. The free-threading classifier when you have tested it.

**Why:** the classifiers are how a consumer filters, and a wrong one wastes their time in the
direction that is hardest to diagnose — they install expecting support and find none. The
free-threading classifier in particular is a claim about testing, not about building.

**Check:** every classifier against reality. `Typing :: Typed` without `py.typed` is the common lie.

## Dependencies

### PS-BUILD-07 [M] Put development tooling in `[dependency-groups]`, never in extras

`[dependency-groups] test = [...]`. Not `[project.optional-dependencies] test = [...]`.

**Why:** extras are shipped runtime metadata — anyone can install `yourpkg[test]`, and the index
displays them as part of your package. Dependency groups are local to the repository and appear
nowhere in the built distribution, which is exactly right for a linter.

**Check:** every extra. If a user would never install it, it is a group.

### PS-BUILD-08 [M] Pin every tool that decides whether the build passes

`ruff==0.17.2`, `ty==0.0.91`, `pytest==9.1.1` — exact, in the dependency group.

**Why:** a floor lets a new linter release fail CI on code nobody touched, and differently for two
developers on the same commit; a pin makes the upgrade a reviewed change with its own diff. `ty`
states that breaking changes including diagnostics may occur between any two versions.

**Check:** every entry in `[dependency-groups]`. A `>=` on a linter, formatter or type checker is
the finding.

### PS-BUILD-09 [M] Give a library floors, not pins

`httpx>=0.28` in `[project.dependencies]`. Never `==`.

**Why:** the opposite of PS-BUILD-08, and for the opposite reason: a library's dependencies are
resolved alongside everyone else's, so an exact pin makes your package uninstallable next to any
other package with a different pin. Applications pin, through the lock file; libraries constrain.

**Check:** `rg -n '==' pyproject.toml` inside `[project.dependencies]`.

### PS-BUILD-10 [M] Commit `uv.lock`, and keep it the only lock artefact

`uv.lock` in the repository. Nothing else locks, and nothing is exported alongside it.

**Why:** the lock file is what makes a build reproducible, so it belongs in version control with the
source. A second lock artefact is a source of truth nothing in this toolchain reads — `uv sync`
cannot consume one — so it drifts silently until whoever trusted it finds it stale.

**Check:** the lock file in `.gitignore` is the finding. A second lock artefact committed beside it
is the other one.

### PS-BUILD-11 [M!] Refuse a dependency published in the last few days

`uv lock --exclude-newer`, as a date or a relative duration. There is no `--cooldown`;
`--exclude-newer-package` narrows it to one dependency when a project needs the newest of something
specific.

*Relaxed form:* a project that reviews every dependency change by hand may skip the cooldown, and
should say so where the CI configuration would otherwise carry it.

**Why:** the window between a compromised release being published and being pulled is measured in
hours — a documented incident had malicious versions live for two and a half and three and a half
hours. A cooldown removes that window entirely for the cost of installing yesterday's version.

**Check:** the CI install step. No cooldown and no manual review is the finding.

## Building

### PS-BUILD-12 [M] Build with `uv_build`, and never invoke `setup.py`

`requires = ["uv_build>=0.13.3,<0.14"]` and `build-backend = "uv_build"`. Build with `uv build`.
The upper bound is required: `uv_build` follows uv's versioning policy and may break across minor
versions. That is not the ceiling PS-BUILD-04 forbids — that rule governs `requires-python`, a claim
about interpreters you cannot test, while this is a build dependency you do.

**Why:** `python setup.py install` and its relatives are deprecated, and `distutils` is not in the
standard library. A declared backend that the frontend calls makes the build reproducible from the
declaration rather than from whatever a script happens to do.

**Check:** `rg -n 'setup.py' .` — every invocation is the finding. `setup.py` may still exist
as a shim; calling it directly may not.

### PS-BUILD-13 [M] Build the package from `src/`, and ship `py.typed`

`src/acmewidget/`, with `py.typed` inside the package directory. `uv_build` includes the marker
automatically because it lives inside the package — but verify that against the built wheel rather
than taking it on trust.

**Why:** `src/` is what makes the tests exercise the installed package rather than the working
copy — see PS-NAME-12. `py.typed` is what makes your annotations visible downstream at all;
without it a type checker ignores them entirely.

**Check:** unpack the built wheel and look for `py.typed`. Its absence is the finding.

### PS-BUILD-14 [M] Give the distribution and the module the same name

`name = "acmewidget"` and `src/acmewidget/`. Not `acme-widget` wrapping a directory called
`acmewidget`.

**Why:** a backend finds your package by normalising the distribution name — `acme-widget` becomes
`acme_widget` — and looking for that directory under `src/`. Name them differently and the build
fails outright until a `module-name` override papers over it; matched, the layout is inferred.

**Check:** `rg -n '^name' pyproject.toml` against the directory under `src/`. Any difference is
the finding.

### PS-BUILD-15 [M] Keep the built artefact reproducible from the repository alone

No network at build time, no generated files that are not in version control or generated by the
build itself.

**Why:** a build that reaches out is a build that produces different artefacts on different days, so
the version number stops identifying the contents. It also cannot be built in an air-gapped or
audited environment, which is increasingly where builds happen.

**Check:** build with the network disabled. Anything that fails is a hidden input.

## Publishing

### PS-BUILD-16 [M] Publish with Trusted Publishing, never a long-lived token

OIDC from the CI workflow. No API token in a repository secret. PyPI recommends Trusted Publishing
over tokens wherever the CI provider supports it.

**Why:** a long-lived token is a credential that exists whether or not you are publishing, so it can
be stolen at any time and used from anywhere. Trusted Publishing mints a short-lived credential
scoped to one workflow in one repository, so there is nothing durable to steal.

**Check:** the publish workflow. A `password:` referencing a secret is the finding.

### PS-BUILD-17 [S] Emit attestations, and do not rely on anyone verifying them

The PyPA publish action emits them by default under Trusted Publishing. Leave it on.

**Why:** they cost nothing and give an auditor a cryptographic link from the artefact to the
workflow that built it. They gate nothing: no installer verifies them at install time, `uv`
included, and the specification deliberately declines to recommend mandatory verification.

**Check:** `attestations: false` in the publish step is the finding.

### PS-BUILD-18 [M] Cut a new version rather than adding a file to an old release

A new wheel for a new interpreter goes in a new version.

**Why:** PyPI now rejects new files on a release more than fourteen days old, a guard introduced
after supply-chain incidents where an attacker added a poisoned wheel to an established, trusted
release. Back-filling a wheel is therefore no longer possible.

**Check:** any process that expects to add artefacts to a published version.

## The free-threaded build

### PS-BUILD-19 [M] A free-threaded wheel tag is not a declaration of thread safety

`cp315t`, or `abi3t` for the free-threaded stable ABI: a package can ship either and still re-enable
the GIL on import, and several do.

**Why:** the tag says only that the wheel was built for the free-threaded ABI. SQLAlchemy 2.0.49
shipped one that re-enabled the GIL on import, and major numerical libraries call their support
"experimental" or "preliminary" and say explicitly that it does not mean the library is thread-safe.

**Check:** import the whole dependency tree on the free-threaded build and assert the GIL is still
off — PS-BUILD-20's command. The wheel tag cannot tell you this.

### PS-BUILD-20 [M] Assert in CI that the GIL is actually off

Two assertions, because a GIL build fails the second for a different reason:

```sh
python -c "import sys; assert sys.abi_info.free_threaded"           # the CI image
python -c "import sys, yourpkg; assert not sys._is_gil_enabled()"  # the dependency tree
```

**Why:** the re-enable is silent apart from a `RuntimeWarning` that CI logs swallow, so without this
assertion a dependency upgrade can quietly turn a free-threaded deployment into a GIL one and
everything still passes — just slower, and with the parallelism you were relying on gone.

**Check:** the CI workflow. No such assertion is the finding.

### PS-BUILD-21 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

Not in production, not in CI, not in a Dockerfile.

**Why:** the flag does not fix whatever re-enabled the GIL — it skips the runtime check, runs
without the GIL anyway, and suppresses the one warning you had. CPython's own message says "at your
own risk"; the risk is memory corruption rather than a wrong answer.

**Check:** `rg -n 'PYTHON_GIL|gil=0' .github/ Dockerfile* 2>/dev/null` — every hit is the
finding.
