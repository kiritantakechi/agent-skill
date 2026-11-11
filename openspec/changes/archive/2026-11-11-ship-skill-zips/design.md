## Context

`build.package` zips a skill's shipped files (`shipped`, which leaves out what `.gitignore` keeps out,
plus `.git` and `.DS_Store`). Each file sits at `<name>/<path below the skill>`. Agensi's
pre-publish checklist asks for exactly that: one top-level folder named after the skill,
`SKILL.md` directly in it, a `name` equal to the folder, and at least one supporting file. Every
skill here has `references/`, and the `frontmatter` check already holds `name` to the folder.

## Decisions

### 1. One archive, written under both names

The package is one zip archive. `build.SUFFIXES` is `(".skill", ".zip")`: `.skill` is what a skill
file is called, and `.zip` is what an upload that wants a zip accepts. The owner asked for both.
`package` writes the archive once and copies it under each other suffix, so the names hold the same
bytes, and a test holds that. A CI step renaming files would put the second name outside the one
place that names the package.

### 2. The workflow builds with the harness, never with `zip`

The workflow runs `agent-skill build`. `shipped` stays the only owner of what a skill ships. A
`zip -r … -x …` line in YAML would be a second copy of `EXCLUDE`, free to drift from it.

### 3. Releases carry one asset per skill; a dispatch carries one artifact

- **On a tag:** each zip is attached to the tag's release as its own asset. Uploading to a
  marketplace is then one download per skill. The job alone gets `contents: write`, and only the
  release step uses the token, through the `gh` CLI the runner ships.
- **On dispatch:** an `upload-artifact` run cannot upload several files unarchived without naming
  each one. Naming each would be a second list of the skills, which the tree already lists. So a
  dispatch uploads `dist/*.zip` as one artifact, and a tag is the route to separate files.
- **Pin:** `actions/upload-artifact` is pinned to `cf430e030ddbb5b0abf93d22962f4752f3646cd9`,
  v7.0.2. That is the newest release at least seven days old (2026-10-07), as every other pin is.

### 4. The setup is python-style's

The job's first four steps are `check.yml`'s and python-style's asset's. `self-application`
holds a shared step to the asset's, so the two workflows cannot drift apart in setup.

## Risks / Trade-offs

- **bevy-style is a delta on rust-style.** Its zip is complete as a package, but it is read
  together with rust-style's. That belongs in the bevy-style listing, not in the packaging.
- **Agensi's file-type and size limits are not published** where this session could read them. The
  largest skill zip is well under the 50 MB other skill platforms allow.
