# Release artifacts

Each SourceLore GitHub Release for version `vX.Y.Z` publishes:

| Artifact | Purpose |
|---|---|
| Source code (auto archive) | Full repository at the tag; clone-based install |
| `sourcelore-skill-vX.Y.Z.zip` | Standalone Skill install — no Git clone needed |
| `SHA256SUMS.txt` | SHA-256 of the ZIP; verify with `sha256sum -c SHA256SUMS.txt` |
| `RELEASE_INFO.json` | Version, tag, artifact name and checksum metadata |

## ZIP contents

```
sourcelore/
├── SKILL.md                       # Skill entry + frontmatter
├── references/                    # commands, safety, schema, content-qa
├── scripts/sourcelore.py          # launcher (self-locating)
├── _sourcelore_src/src/           # bundled first-party program source
└── RELEASE_INFO.json              # embedded version metadata
```

The ZIP is **self-contained**: after installation you may delete the ZIP and
its extraction directory; the Skill keeps working because the program source
is bundled inside the installed Skill folder.

The ZIP does **not** contain: `kb.db` or any knowledge database, captured
third-party bytes, `upstreams/` snapshots, API tokens, local config, install
markers, `.venv/`, or any developer machine path.

## Version correspondence

```
Git tag vX.Y.Z
  → src/skill_interface/version.py RELEASE_VERSION = X.Y.Z
  → ZIP RELEASE_INFO.json version = X.Y.Z
  → installed CLI --version = X.Y.Z
```

The release workflow (`/.github/workflows/release.yml`) refuses to publish if
the pushed tag does not equal `v` + `RELEASE_VERSION`, and only runs after the
full test suite passes.

## Install from a release

```sh
# Download the ZIP and checksum, verify, then:
python3 tools/install.py install --zip sourcelore-skill-vX.Y.Z.zip
python3 tools/install.py doctor
```

See [INSTALLATION.md](INSTALLATION.md) / [UPGRADING.md](UPGRADING.md) for the
full command set.
