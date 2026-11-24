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
├── install.py                     # self-contained installer (bootstrap entry)
├── _sourcelore_src/src/           # bundled first-party program source
└── RELEASE_INFO.json              # embedded version metadata + installer sha256
```

The ZIP is **self-contained and self-bootstrapping**: it ships its own
`install.py`, so a user who downloads only the ZIP can install without a Git
clone — extract it and run `python3 install.py install` from the extracted
`sourcelore/` directory. `RELEASE_INFO.json` records that installer's SHA-256.
After installation you may delete the ZIP and its extraction directory; the
Skill keeps working because the program source is bundled inside the installed
Skill folder.

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
# Download the ZIP and checksum, verify, then either:
# (a) ZIP-only bootstrap — run the installer FROM INSIDE the extracted ZIP:
python3 /path/to/extracted/sourcelore/install.py install
# (b) from a checkout: python3 tools/install.py install --zip sourcelore-skill-vX.Y.Z.zip
python3 tools/install.py doctor --expect-version X.Y.Z
```

See [INSTALLATION.md](INSTALLATION.md) / [UPGRADING.md](UPGRADING.md) for the
full command set.
