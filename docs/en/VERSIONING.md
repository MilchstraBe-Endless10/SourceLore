# Versioning

SourceLore follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

The single authoritative version constant is `RELEASE_VERSION` in
`src/skill_interface/version.py`. Every release-facing surface must read from
that module — CLI `--version`, `status`, installer metadata, update/uninstall,
release packaging, CHANGELOG, Git tag and GitHub Release title. No file may
hardcode a separate version string.

## Format

`MAJOR.MINOR.PATCH[-prerelease]`

- **MAJOR** — incompatible changes to the CLI/Skill interface or data model.
- **MINOR** — backward-compatible new functionality.
- **PATCH** — backward-compatible fixes.
- **Prerelease** (`-beta.N`, `-rc.N`) — not yet stable; may change between
  prereleases. The current first public release is `0.1.0-beta.1`.

The Git tag is the version prefixed with `v` (for example `v0.1.0-beta.1`),
also exposed as `RELEASE_TAG` in `version.py`.

## Internal codename vs public version

The historical internal development codename `f2p5a` is kept as
`DEV_CODENAME` for documentation only. It is not a version and must not be
shown as one. `SKILL_VERSION` remains as a compatibility alias equal to
`RELEASE_VERSION` for older callers.

## Version ↔ artifact correspondence

For every release the following must agree:

```
Git tag (vX.Y.Z) → Git commit → Release ZIP (manifest VERSION) → installed CLI --version
```

`tools/build_release.py` embeds `RELEASE_VERSION` into the ZIP's
`RELEASE_INFO.json`; the installer writes the installed version into its
marker; `sourcelore.py --version` reads the same `version.py`. A mismatch is a
release error.

## Database compatibility

The knowledge-base **data root** (including `kb.db`) is user data and lives
outside the source installation. Upgrading SourceLore never migrates or clears
it implicitly. `SCHEMA_VERSION` in `version.py` records the current schema
version; a future schema change must provide a backup, a compatibility check,
a reproducible migration and a fail-stop condition. See
[UPGRADING.md](UPGRADING.md) and the A/B/C/D integrity rules in DATA-MODEL.md.

## What is not versioned here

- Captured third-party repository snapshots and derived knowledge data — those
  remain under the runtime `distribution_allowed=false` policy.
- The user's own knowledge database and generated documents.
- Per-machine local paths and agent-host markers (never committed).
