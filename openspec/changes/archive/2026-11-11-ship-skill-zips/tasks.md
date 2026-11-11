## 1. Package

- [x] 1.1 `build.package` writes `<name>.zip`; the CLI's help and docstring say so; the package test
  also holds the suffix, `SKILL.md` directly in the one top-level folder, and the frontmatter
  `name` equal to that folder. Result: `test_the_package_is_what_a_skill_upload_takes` holds all
  three; `tests/test_install.py`, `test_cli.py` and `test_evals.py` pass (70)

## 2. Workflow

- [x] 2.1 Write `.github/workflows/package.yml`: python-style's setup steps, `agent-skill build`, the
  zips as an artifact, and on a `style-standards--v*` tag each zip attached to the tag's release.
  Result: actionlint 1.7.12 reports nothing; `self-application` passes, so the four setup steps
  are the asset's; `actions/upload-artifact` is at v7.0.2 (`cf430e0`, 2026-10-07), the newest
  release at least seven days old

## 3. Docs and verify

- [x] 3.1 The README's command list, layout, packaging sentence and CI section name the zip and the
  workflow
- [x] 3.2 `check --fast`, the tests not marked `toolchain`, ruff, ruff format and ty pass; `agent-skill
  build` writes four zips whose layout is checked; record the result here. Result: four zips, each
  one folder named after the skill with its `SKILL.md` and matching `name`: bevy-style 118 KB,
  python-style 118 KB, rust-style 221 KB, zig-style 294 KB, holding Markdown and the assets'
  `.toml`, `.yml`, `.zig` and `.zon`. ruff, ruff format, ty and `openspec validate --strict` pass;
  1009 tests pass. `pins` fails, and with it `controls` and three tests, because ty 0.0.101 was
  released on 2026-11-11 and `pyproject.toml` pins 0.0.99; that is upstream, not this change, and
  moving the pin is left to its own change

## 4. Both names

- [x] 4.1 At the owner's request, `build` writes each package as `<name>.skill` and `<name>.zip`,
  one archive copied under the second name; the workflow publishes both; a test holds that every
  name holds the same bytes. Result: `tests/test_install.py`, `test_cli.py` and `test_evals.py`
  pass (71)
