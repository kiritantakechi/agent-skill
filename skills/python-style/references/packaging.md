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
  - PS-PKG-01 [M] Cite the living specification, never the PEP
  - PS-PKG-02 [M] Keep `[project]` static; use `dynamic` only where a backend computes it
  - PS-PKG-03 [M] Write the licence as an SPDX expression, and ship `license-files`
  - PS-PKG-04 [M] Give `requires-python` a floor and no ceiling
  - PS-PKG-05 [M] Use the well-known `[project.urls]` labels
  - PS-PKG-06 [M] Classify the package honestly, including its typing and threading status
- **Dependencies**
  - PS-PKG-07 [M] Put development tooling in `[dependency-groups]`, never in extras
  - PS-PKG-08 [M] Pin every tool that decides whether the build passes
  - PS-PKG-09 [M] Give a library floors, not pins
  - PS-PKG-10 [M] Commit `uv.lock`, and keep it the only lock artefact
  - PS-PKG-11 [M!] Refuse a dependency published in the last few days
- **Building**
  - PS-PKG-12 [M] Build with `uv_build`, and never invoke `setup.py`
  - PS-PKG-13 [M] Build the package from `src/`, and ship `py.typed`
  - PS-PKG-14 [M] Give the distribution and the module the same name
  - PS-PKG-15 [M] Keep the built artefact reproducible from the repository alone
- **Publishing**
  - PS-PKG-16 [M] Publish with Trusted Publishing, never a long-lived token
  - PS-PKG-17 [S] Emit attestations, and do not rely on anyone verifying them
  - PS-PKG-18 [M] Cut a new version rather than adding a file to an old release
- **The free-threaded build**
  - PS-PKG-19 [M] A `cp3XXt` wheel tag is not a declaration of thread safety
  - PS-PKG-20 [M] Assert in CI that the GIL is actually off
  - PS-PKG-21 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

---

## Metadata

### PS-PKG-01 [M] Cite the living specification, never the PEP

`packaging.python.org/en/latest/specifications/pyproject-toml/`, not PEP 621.

**Why:** every packaging PEP this chapter would otherwise cite now opens with *"This PEP is a
historical document"* and redirects to the PyPA specifications, which are the maintained text. The
difference is not academic: a PEP records what was decided once, and the specification records what
is true now. The same applies to typing — `typing.python.org/spec` rather than PEP 484.

**Check:** every packaging or typing reference in the project's own documentation. A bare PEP number
as the normative citation is the finding; naming the PEP as provenance alongside the spec is fine.

### PS-PKG-02 [M] Keep `[project]` static; use `dynamic` only where a backend computes it

Version from a VCS tag is a legitimate `dynamic`. Everything else should be written down.

**Why:** static metadata can be read without executing anything, which is what lets an index, a
resolver, or a security scanner answer questions about your package without installing it. Every
`dynamic` field is one those tools must give up on. `version` is the field with a real case for it;
`dependencies` and `requires-python` almost never are.

**Check:** the `dynamic` list. Each entry needs the backend hook that computes it.

### PS-PKG-03 [M] Write the licence as an SPDX expression, and ship `license-files`

`license = "MIT"` as a **string**. Not `{ text = ... }`, not `{ file = ... }`, and no
`License :: OSI Approved ::` classifier.

**Why:** the table forms and the licence classifiers are both deprecated in favour of an SPDX
expression, which is machine-readable and unambiguous — `"MIT"` means exactly one licence, where the
classifier and the free-text field between them could disagree. `license-files` is what puts the
actual text in the distribution, which several licences require.

**Check:** `grep -n 'License ::' pyproject.toml` and `grep -n 'license' pyproject.toml` — a table
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

### PS-PKG-04 [M] Give `requires-python` a floor and no ceiling

`>=3.15`. Never `<4`, never `<3.16`.

**Why:** an upper bound is a promise about interpreters that do not exist yet, and it is wrong by
default — it makes your package uninstallable on the next release even when it would have worked,
and the fix requires a new release from you. PyPA advises against it for exactly this reason. If
a future version genuinely breaks you, yank or patch then.

**Check:** `grep -n 'requires-python' pyproject.toml` — any `<` is the finding.

### PS-PKG-05 [M] Use the well-known `[project.urls]` labels

`homepage`, `source`, `issues`, `changelog`, `documentation` — lowercase.

**Why:** the labels are normalised and recognised, so an index can render the right icons and a
tool can find your issue tracker without guessing. Ad-hoc labels render as plain text. The
normalisation strips punctuation and case, so `"Bug Tracker"` does work — but the plain label is
the safe spelling.

**Check:** the `[project.urls]` table against the well-known list.

### PS-PKG-06 [M] Classify the package honestly, including its typing and threading status

`Typing :: Typed` when you ship `py.typed`. The free-threading classifier when you have tested it.

**Why:** the classifiers are how a consumer filters, and a wrong one wastes their time in the
direction that is hardest to diagnose — they install expecting support and find none. The
free-threading classifier in particular is a claim about testing, not about building.

**Check:** every classifier against reality. `Typing :: Typed` without `py.typed` is the common lie.

## Dependencies

### PS-PKG-07 [M] Put development tooling in `[dependency-groups]`, never in extras

`[dependency-groups] test = [...]`. Not `[project.optional-dependencies] test = [...]`.

**Why:** extras are shipped runtime metadata — anyone can install `yourpkg[test]`, and the index
displays them as part of your package. Dependency groups are local to the repository and appear
nowhere in the built distribution, which is exactly right for a linter. Putting test tooling in
extras publishes your development choices as part of your API.

**Check:** every extra. If a user would never install it, it is a group.

### PS-PKG-08 [M] Pin every tool that decides whether the build passes

`ruff==0.16.4`, `ty==0.0.74`, `pytest==9.1.1` — exact, in the dependency group.

**Why:** a linter version is part of the build's definition: a floor means a new release can fail
your CI on code nobody touched, and can do it differently for two developers on the same commit.
Pinning makes the upgrade a reviewed change with its own diff. This matters most for tools with
no stability guarantee — `ty` states that breaking changes including diagnostics may occur
between any two versions.

**Check:** every entry in `[dependency-groups]`. A `>=` on a linter, formatter or type checker is
the finding.

### PS-PKG-09 [M] Give a library floors, not pins

`httpx>=0.28` in `[project.dependencies]`. Never `==`.

**Why:** the opposite of PS-PKG-08, and for the opposite reason: a library's dependencies are
resolved alongside everyone else's, so an exact pin makes your package uninstallable next to any
other package with a different pin. Applications pin, through the lock file; libraries constrain.

**Check:** `grep -n '==' pyproject.toml` inside `[project.dependencies]`.

### PS-PKG-10 [M] Commit `uv.lock`, and keep it the only lock artefact

`uv.lock` in the repository. Nothing else locks, and nothing is exported alongside it.

**Why:** the lock file is what makes a build reproducible, and it belongs in version control for the
same reason the source does. A second lock artefact is a second source of truth that nothing in this
toolchain reads — `uv sync` cannot consume one — so it drifts silently and is discovered stale by
whoever trusted it.

**Check:** the lock file in `.gitignore` is the finding. A second lock artefact committed beside it
is the other one.

### PS-PKG-11 [M!] Refuse a dependency published in the last few days

`uv lock --exclude-newer`, as a date or a relative duration.

*Relaxed form:* a project that reviews every dependency change by hand may skip the cooldown, and
should say so where the CI configuration would otherwise carry it.

**Why:** the window between a compromised release being published and being pulled is measured in
hours — a documented incident had malicious versions live for two and a half and three and a half
hours. A cooldown removes that window entirely for the cost of installing yesterday's version. The
flag is `--exclude-newer`; there is no `--cooldown`, and `--exclude-newer-package` narrows it to one
dependency when a project needs the newest of something specific.

**Check:** the CI install step. No cooldown and no manual review is the finding.

## Building

### PS-PKG-12 [M] Build with `uv_build`, and never invoke `setup.py`

`requires = ["uv_build>=0.12.6,<0.13"]` and `build-backend = "uv_build"`. Build with `uv build`.

**Why:** `python setup.py install` and its relatives are deprecated and `distutils` was removed from
the standard library in 3.12, so the old path no longer exists. The backend is declared and the
frontend calls it, which is what makes the build reproducible from the declaration rather than from
whatever a script happens to do. One backend is named rather than a choice offered, because a
standard that lists two has moved the decision to the reader with less information than it had. The
upper bound is required: `uv_build` follows uv's versioning policy and may break across minor
versions. That is not the ceiling PS-PKG-04 forbids — that rule governs `requires-python`, a claim
about interpreters you cannot test, while this is a build dependency you do.

**Check:** `grep -rn 'setup.py' .` — every invocation is the finding. `setup.py` may still exist
as a shim; calling it directly may not.

### PS-PKG-13 [M] Build the package from `src/`, and ship `py.typed`

`src/acmewidget/`, with `py.typed` inside the package directory.

**Why:** `src/` is what makes the tests exercise the installed package rather than the working
copy — see PS-NAME-16. `py.typed` is what makes your annotations visible downstream at all;
without it a type checker ignores them entirely. `uv_build` includes the marker automatically
because it lives inside the package — but that is a fact to verify against the built wheel, not to
take on trust.

**Check:** unpack the built wheel and look for `py.typed`. Its absence is the finding.

### PS-PKG-14 [M] Give the distribution and the module the same name

`name = "acmewidget"` and `src/acmewidget/`. Not `acme-widget` wrapping a directory called
`acmewidget`.

**Why:** a backend finds your package by normalising the distribution name — `acme-widget` becomes
`acme_widget` — and looking for that directory under `src/`. Name them differently and the build
fails outright until you add a `module-name` override to paper over it. Matched, the layout is
inferred and `[build-system]` is the only thing in the file that names a backend at all. PS-NAME-09
already forbids a separator in the importable name; this is that same name, spelled once.

**Check:** `grep -n '^name' pyproject.toml` against the directory under `src/`. Any difference is
the finding.

### PS-PKG-15 [M] Keep the built artefact reproducible from the repository alone

No network at build time, no generated files that are not in version control or generated by the
build itself.

**Why:** a build that reaches out is a build that produces different artefacts on different days, so
the version number stops identifying the contents. It also cannot be built in an air-gapped or
audited environment, which is increasingly where builds happen.

**Check:** build with the network disabled. Anything that fails is a hidden input.

## Publishing

### PS-PKG-16 [M] Publish with Trusted Publishing, never a long-lived token

OIDC from the CI workflow. No API token in a repository secret.

**Why:** a long-lived token is a credential that exists whether or not you are publishing, so it can
be stolen at any time and used from anywhere. Trusted Publishing mints a short-lived credential
scoped to one workflow in one repository, so there is nothing durable to steal. PyPI's own guidance
is explicit that it is recommended over tokens where the CI provider supports it.

**Check:** the publish workflow. A `password:` referencing a secret is the finding.

### PS-PKG-17 [S] Emit attestations, and do not rely on anyone verifying them

The PyPA publish action emits them by default under Trusted Publishing. Leave it on.

**Why:** they cost nothing — they are on by default — and they give an auditor a cryptographic link
from the artefact to the workflow that built it. What they do not do is gate anything: no installer
verifies them at install time, `uv` included, and the specification deliberately declines to
recommend mandatory verification. So emit them as evidence, and do not build a security argument
on consumers checking them.

**Check:** `attestations: false` in the publish step is the finding.

### PS-PKG-18 [M] Cut a new version rather than adding a file to an old release

A new wheel for a new interpreter goes in a new version.

**Why:** PyPI now rejects new files on a release more than fourteen days old, which was introduced
after supply-chain incidents where an attacker added a poisoned wheel to an established, trusted
release. The consequence for ordinary work is that back-filling a wheel is no longer possible — plan
to cut a release instead.

**Check:** any process that expects to add artefacts to a published version.

## The free-threaded build

### PS-PKG-19 [M] A `cp3XXt` wheel tag is not a declaration of thread safety

A package can ship a free-threaded wheel and still re-enable the GIL on import, and several do.

**Why:** the wheel tag says only that the artefact was built for the free-threaded ABI. Whether the
package actually runs with the GIL off is a separate fact, and the two come apart in practice:
SQLAlchemy 2.0.49 shipped a free-threaded wheel that re-enabled the GIL on import, and lxml has
shipped `cp314t` wheels while its own tracker says support is not released. Major numerical
libraries describe their support as "experimental" or "preliminary" in the same documents that
announce the wheels, and say explicitly that it does not mean the library is thread-safe.

**Check:** import the whole dependency tree on the free-threaded build and assert the GIL is still
off — PS-PKG-20's command. The wheel tag cannot tell you this.

### PS-PKG-20 [M] Assert in CI that the GIL is actually off

`python -c "import yourpkg; import sys; assert not sys._is_gil_enabled()"`.

**Why:** the re-enable is silent apart from a `RuntimeWarning` that CI logs swallow, so without this
assertion a dependency upgrade can quietly turn a free-threaded deployment into a GIL one and
everything still passes — just slower, and with the parallelism you were relying on gone. This one
line is the only thing standing between you and that.

**Check:** the CI workflow. No such assertion is the finding.

### PS-PKG-21 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

Not in production, not in CI, not in a Dockerfile.

**Why:** the flag does not fix whatever re-enabled the GIL — it skips the runtime check and runs
without the GIL anyway, which is precisely the situation the check exists to prevent. It also
suppresses the warning, so the one signal you had is gone. CPython's own message says "at your own
risk"; the risk is memory corruption rather than a wrong answer.

**Check:** `grep -rn 'PYTHON_GIL\|gil=0' .github/ Dockerfile* 2>/dev/null` — every hit is the
finding.
