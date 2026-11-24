# Upgrading, updating and uninstalling

SourceLore separates the **installation** (program + Skill files) from the
**knowledge-base data root** (your `kb.db`, captured bytes and documents).
Update and uninstall only touch the installation; your data is preserved by
default.

## Check the current state

```sh
python3 tools/install.py doctor
python3 tools/install.py doctor --json
```

`doctor` reports detected install mode, installed version, launcher validity,
data root, and whether the data root exists. It never modifies anything.

## See the installed version

```sh
python3 <skill-dir>/scripts/sourcelore.py --version
```

The value must equal `RELEASE_VERSION` in `src/skill_interface/version.py` for
the installed release.

## Update

From a Git checkout:

```sh
git pull                       # fetch the new release
python3 tools/install.py update
```

From a downloaded release ZIP (no Git checkout needed):

```sh
python3 tools/install.py update --zip /path/to/sourcelore-skill-vX.Y.Z.zip
```

`update` stages the complete new version in a temporary directory, verifies
integrity (required files present, `RELEASE_INFO.json` consistent) **before**
switching, keeps the previous installation as a timestamped backup, and never
touches the data root. On any failure it rolls back to the previous install.

Pin to a fixed version by installing exactly that version's ZIP; SourceLore
does not auto-update or phone home.

## Rollback

If an update fails it rolls back automatically. To roll back manually, restore
the timestamped backup directory that `update` left next to the install, or
reinstall the previous ZIP:

```sh
python3 tools/install.py update --zip /path/to/sourcelore-skill-vPREVIOUS.zip
```

## Data compatibility

- Upgrade ≠ database migration. The data root is not modified by an update.
- If a future release needs a schema change, it must provide a backup, a
  compatibility check and a reproducible migration with a fail-stop condition;
  see VERSIONING.md and DATA-MODEL.md.
- The A/B/C/D integrity rules and the runtime `distribution_allowed=false`
  gate are preserved across updates.

## Uninstall

```sh
python3 tools/install.py uninstall
```

Default uninstall removes only SourceLore's installed program and Skill files.
It **keeps** your knowledge database, configuration, generated project
documents and any files you modified yourself. Deleting user data requires an
explicit separate confirmation; the installer never does it silently.

## Preserving local modifications

The installer refuses to overwrite a Skill directory it does not own (no
`.sourcelore-install.json` marker). If you edited installed files, `doctor`
flags the install as locally modified; `update` keeps a backup rather than
discarding it silently. Compare before deciding to replace.
