# Build: Metadata, Dependencies, Locking, Publishing, and the Free-Threaded Wheel

Scope: what `pyproject.toml` must say, how dependencies are declared and pinned, how a package is
built and published, and what the free-threaded build demands of a dependency tree. Package layout
is the modules chapter; the public surface is the API chapter.

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
  - PS-BUILD-11 [M] Lock nothing younger than seven days but what you pinned exactly
  - PS-BUILD-12 [M] Justify every dependency; the standard library is the default
- **Building**
  - PS-BUILD-13 [M] Build with `uv_build`, and never invoke `setup.py`
  - PS-BUILD-14 [M] Give the distribution and the module the same name
  - PS-BUILD-15 [M] Keep the built artefact reproducible from the repository alone
  - PS-BUILD-16 [M] Add to the source distribution with `source-include`, never by excluding
- **Publishing**
  - PS-BUILD-17 [M] Publish with Trusted Publishing, never a long-lived token
  - PS-BUILD-18 [S] Emit attestations, and do not rely on anyone verifying them
  - PS-BUILD-19 [M] Cut a new version rather than adding a file to an old release
- **Continuous integration**
  - PS-BUILD-20 [M] Run `ruff format`; it is not a suggestion
  - PS-BUILD-21 [M] Pin every third-party CI action to a full commit, with its release as a comment
- **The free-threaded build**
  - PS-BUILD-22 [M] A free-threaded wheel tag is not a declaration of thread safety
  - PS-BUILD-23 [M] Assert in CI that the GIL is actually off
  - PS-BUILD-24 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

---

## Metadata

### PS-BUILD-01 [M] Cite the living specification, never the PEP

`packaging.python.org/en/latest/specifications/pyproject-toml/`, not PEP 621. The same applies to
typing: `typing.python.org/spec`, not PEP 484.

**Why:** every packaging PEP this chapter would otherwise cite now opens with *"This PEP is a
historical document"* and redirects to the PyPA specifications. A PEP records what was decided once;
the specification is the maintained text and records what is true now.

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

**Check:** `rg -n 'License ::' pyproject.toml` and `rg -n 'license' pyproject.toml` — a table form
or a classifier is the finding.

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

`>=3.15`. Never `<4`, never `<3.16`. If a future version genuinely breaks the package, yank or patch
then.

**Why:** an upper bound is a promise about interpreters that do not exist yet: it makes the package
uninstallable on the next release even where it would have worked, and only a new release from you
fixes it. PyPA advises against it for exactly this reason.

**Check:** `rg -n 'requires-python' pyproject.toml` — any `<` is the finding.

### PS-BUILD-05 [M] Use the well-known `[project.urls]` labels

`homepage`, `source`, `issues`, `changelog`, `documentation` — lowercase. Normalisation strips
punctuation and case, so `"Bug Tracker"` does work, but the plain label is the safe spelling.

**Why:** the labels are normalised and recognised, so an index can render the right icons and a tool
can find your issue tracker without guessing. Ad-hoc labels render as plain text.

**Check:** the `[project.urls]` table against the well-known list.

### PS-BUILD-06 [M] Classify the package honestly, including its typing and threading status

`Typing :: Typed` when you ship `py.typed` (PS-API-03). The free-threading classifier when you have
tested it.

**Why:** the classifiers are how a consumer filters, and a wrong one wastes their time in the
direction that is hardest to diagnose — they install expecting support and find none. The
free-threading classifier in particular is a claim about testing, not about building.

**Check:** every classifier against reality. `Typing :: Typed` without `py.typed` is the common lie.

## Dependencies

### PS-BUILD-07 [M] Put development tooling in `[dependency-groups]`, never in extras

`[dependency-groups] test = [...]`. Not `[project.optional-dependencies] test = [...]`.

**Why:** extras are shipped runtime metadata — anyone can install `acmewidget[test]`, and the index
displays them as part of your package. Dependency groups are local to the repository and appear
nowhere in the built distribution, which is exactly right for a linter.

**Check:** every extra. If a user would never install it, it is a group.

### PS-BUILD-08 [M] Pin every tool that decides whether the build passes

`ruff==0.17.4`, `ty==0.0.99`, `pytest==9.2.0` — exact, in the dependency group.

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

### PS-BUILD-11 [M] Lock nothing younger than seven days but what you pinned exactly

`exclude-newer = "7 days"` under `[tool.uv]`, as `assets/pyproject.toml` ships it, so every
`uv lock` resolves as if the last week's releases did not exist; and `exclude-newer-package` naming
exactly the dependencies pinned with `==`, no more and no fewer. An exact pin is a review written
down — moving it is the reviewed change — so it needs no week to be safe, while everything it pulls
in still waits. `uv lock --exclude-newer` takes the same date or relative duration for one run;
there is no `--cooldown`.

**Why:** the window between a compromised release being published and being pulled lasts hours — a
documented incident had malicious versions live for two and a half and three and a half hours. Seven
days covers that window many times over, for the cost of a week-old version.

**Check:** the `[tool.uv]` table. No `exclude-newer`, or an `exclude-newer-package` whose exempt
names differ from the `==` pins, is the finding.

### PS-BUILD-12 [M] Justify every dependency; the standard library is the default

Every entry in `[project.dependencies]` is justified, in the commit that adds it, by something it
does that would take meaningfully longer than an hour to write and maintain. A package for padding a
string, for `is_even`, or for what the standard library already does is not. Development tooling in
a group (PS-BUILD-07) is justified the same way: it runs on every developer's machine and in CI.

**Why:** each dependency adds an author who can compromise your users, a constraint that can
conflict with theirs (PS-BUILD-09), and an install for every consumer. Those costs are permanent and
shared; the saved hour is one-off and yours.

**Check:** for each entry in `[project.dependencies]`, find the commit that added it and the
sentence naming what it replaces. An entry with no such sentence, or one the standard library
covers, is the finding.

## Building

### PS-BUILD-13 [M] Build with `uv_build`, and never invoke `setup.py`

`requires = ["uv_build>=0.13.3,<0.14"]` and `build-backend = "uv_build"`. Build with `uv build`. The
upper bound is required: `uv_build` follows uv's versioning policy and may break across minor
versions. That is not the ceiling PS-BUILD-04 forbids — that rule governs `requires-python`, a claim
about interpreters you cannot test, while this is a build dependency you do.

**Why:** `python setup.py install` and its relatives are deprecated, and `distutils` is not in the
standard library. A declared backend that the frontend calls makes the build reproducible from the
declaration rather than from whatever a script happens to do.

**Check:** `rg -n 'setup.py' .` — every invocation is the finding. `setup.py` may still exist as a
shim; calling it directly may not.

### PS-BUILD-14 [M] Give the distribution and the module the same name

`name = "acmewidget"` and `src/acmewidget/`. Not `acme-widget` wrapping a directory called
`acmewidget`.

**Why:** a backend finds your package by normalising the distribution name — `acme-widget` becomes
`acme_widget` — and looking for that directory under `src/`. Name them differently and the build
fails outright until a `module-name` override papers over it; matched, the layout is inferred.

**Check:** `rg -n '^name' pyproject.toml` against the directory under `src/`. Any difference is the
finding.

### PS-BUILD-15 [M] Keep the built artefact reproducible from the repository alone

No network at build time, no generated files that are not in version control or generated by the
build itself.

**Why:** a build that reaches out is a build that produces different artefacts on different days, so
the version number stops identifying the contents. It also cannot be built in an air-gapped or
audited environment, which is increasingly where builds happen.

**Check:** build with the network disabled. Anything that fails is a hidden input.

### PS-BUILD-16 [M] Add to the source distribution with `source-include`, never by excluding

`uv_build` ships an allowlist: the module under `src/`, `pyproject.toml`, the readme and the licence
files. Add what a consumer needs to build or test from with
`[tool.uv.build-backend] source-include`, say `["tests/**"]`, and read `tar -tzf dist/*.tar.gz`
before publishing.

**Why:** a list of what to leave out ships every file added next until someone remembers to exclude
it, and a stray `.env` or notebook in a published release stays there (PS-BUILD-19). A list of what
to put in ships what was named.

**Check:** `uv build`, then `tar -tzf dist/*.tar.gz`. Anything a consumer does not need to build is
the finding.

## Publishing

### PS-BUILD-17 [M] Publish with Trusted Publishing, never a long-lived token

OIDC from the CI workflow. No API token in a repository secret. PyPI recommends Trusted Publishing
over tokens wherever the CI provider supports it.

**Why:** a long-lived token is a credential that exists whether or not you are publishing, so it can
be stolen at any time and used from anywhere. Trusted Publishing mints a short-lived credential
scoped to one workflow in one repository, so there is nothing durable to steal.

**Check:** the publish workflow. A `password:` referencing a secret is the finding.

### PS-BUILD-18 [S] Emit attestations, and do not rely on anyone verifying them

The PyPA publish action emits them by default under Trusted Publishing. Leave it on.

**Why:** they cost nothing and give an auditor a cryptographic link from the artefact to the
workflow that built it. They gate nothing: no installer verifies them at install time, `uv`
included, and the specification deliberately declines to recommend mandatory verification.

**Check:** `attestations: false` in the publish step is the finding.

### PS-BUILD-19 [M] Cut a new version rather than adding a file to an old release

A new wheel for a new interpreter goes in a new version.

**Why:** PyPI now rejects new files on a release more than fourteen days old, a guard introduced
after supply-chain incidents where an attacker added a poisoned wheel to an established, trusted
release. Back-filling a wheel is therefore no longer possible.

**Check:** any process that expects to add artefacts to a published version.

## Continuous integration

### PS-BUILD-20 [M] Run `ruff format`; it is not a suggestion

In CI, as a gate, with `--check`. Never as a matter of individual discipline.

**Why:** formatting arguments have no right answer, so the only way to stop having them is to remove
the choice. A formatter that runs sometimes is worse than none, because the diff noise it produces
lands on whoever touches the file next rather than on whoever skipped it.

**Check:** `ruff format --check` in CI. Its stderr also names an enabled lint rule that conflicts
with the formatter — but only for some of the documented conflicts, so the rule set must be checked
against that list directly rather than inferred from a quiet run.

### PS-BUILD-21 [M] Pin every third-party CI action to a full commit, with its release as a comment

`uses: actions/checkout@<40 hex digits>  # v7.0.1`, as `assets/ci.yml` ships it. Not `@v7`, not a
branch, and not a commit without the release beside it, which a reviewer could not read. Choose the
newest release at least seven days old: the cooldown PS-BUILD-11 gives packages applies to what the
workflow runs too.

**Why:** a tag or a branch can be moved after review, and the commit it names moves with it; the
action then runs someone else's code with the workflow's token. A full commit names one tree for
good, and the comment keeps the upgrade a reviewed diff that says what it upgrades to.

**Check:** `rg -n 'uses: [^@ ]+@([0-9a-f]{0,39}([^0-9a-f]|$)|[0-9a-f]{40}\s*$)' .github/` — each hit
is a ref that is not a full commit, or a commit with no release comment.

## The free-threaded build

### PS-BUILD-22 [M] A free-threaded wheel tag is not a declaration of thread safety

`cp315t`, or `abi3t` for the free-threaded stable ABI: a package can ship either and still re-enable
the GIL on import, and several do.

**Why:** the tag says only that the wheel was built for the free-threaded ABI. SQLAlchemy 2.0.49
shipped one that re-enabled the GIL on import, and major numerical libraries call their support
"experimental" or "preliminary" and say explicitly that it does not mean the library is thread-safe.

**Check:** import the whole dependency tree on the free-threaded build and assert the GIL is still
off — PS-BUILD-23's command. The wheel tag cannot tell you this.

### PS-BUILD-23 [M] Assert in CI that the GIL is actually off

Two assertions, because a GIL build fails the second for a different reason:

**Why:** the re-enable is silent apart from a `RuntimeWarning` that CI logs swallow, so without this
assertion a dependency upgrade can quietly turn a free-threaded deployment into a GIL one and
everything still passes — just slower, and with the parallelism you were relying on gone.

**Check:** the CI workflow. No such assertion is the finding.

```sh
python -c "import sys; assert sys.abi_info.free_threaded"              # the CI image
python -c "import sys, acmewidget; assert not sys._is_gil_enabled()"  # the dependency tree
```

### PS-BUILD-24 [M] Never silence the re-enable warning with `PYTHON_GIL=0`

Not in production, not in CI, not in a Dockerfile.

**Why:** the flag does not fix whatever re-enabled the GIL — it skips the runtime check, runs
without the GIL anyway, and suppresses the one warning you had. CPython's own message says "at your
own risk"; the risk is memory corruption rather than a wrong answer.

**Check:** `rg -n 'PYTHON_GIL|gil=0' .github/ Dockerfile* 2>/dev/null` — every hit is the finding.
