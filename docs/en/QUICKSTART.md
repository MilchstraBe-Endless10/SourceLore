# SourceLore — quick start

[简体中文](../zh-CN/QUICKSTART.md) · English · [Full installation guide](INSTALLATION.md) · [Public release readiness](PUBLIC-RELEASE.md)

This is a **realistic first-use sequence**, based on the current Skill launcher and CLI. SourceLore's source repository does **not** include a pre-populated knowledge database. Installing the Skill gives you the tooling; it does not magically install the author's three locally registered sample repositories.

## 1. Obtain the source and test the in-tree launcher

```sh
git clone https://github.com/MilchstraBe-Endless10/SourceLore.git
cd SourceLore
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
python3 skill/sourcelore/scripts/sourcelore.py --help
```

> The `git clone` example works for everyone **only after** the owner switches the repository to Public. While private, authorized GitHub access is required. There is no first-party open-source license yet.

The CLI's accepted subcommands are `status`, `repositories`, `help`, `analyze`, `inspect`, `history`, `query`, `derive`, `answer` and `card`.

## 2. Install the Skill safely (OpenBot / compatible agents)

The installed launcher lives outside the source checkout and needs a reliable way to locate that checkout. The launcher resolves the root in this order: `SOURCELORE_PROJECT_ROOT` environment variable; `.sourcelore-skill.json` marker in the installed Skill folder; discovery of the source tree among its ancestors.

From the SourceLore checkout:

```sh
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
mkdir -p "$HOME/.agents/skills"

if [ -e "$HOME/.agents/skills/sourcelore" ]; then
  echo "Skill folder already exists: review/sync it; do not nest another copy."
else
  cp -a "$SOURCELORE_PROJECT_ROOT/skill/sourcelore" "$HOME/.agents/skills/sourcelore"
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ['SOURCELORE_PROJECT_ROOT']).resolve()
assert (root / 'src/skill_interface/cli.py').is_file(), 'Invalid SourceLore source root'
skill = Path.home() / '.agents/skills/sourcelore'
assert (skill / 'SKILL.md').is_file(), 'Skill not installed'
marker = skill / '.sourcelore-skill.json'
marker.write_text(json.dumps({'project_root': str(root)}, ensure_ascii=False), encoding='utf-8')
print('Launcher root recorded at', marker)
PY

python3 "$HOME/.agents/skills/sourcelore/scripts/sourcelore.py" --help
```

This procedure does **not** overwrite an existing Skill folder. If you already have an installed SourceLore Skill, compare it to the checkout and update it deliberately; keep `SKILL.md`, `references/`, and `scripts/` synchronized. The marker contains a local path; **never commit it to Git**.

In OpenBot, point the assistant at its accessible workspace and start a fresh conversation if the Skill is not immediately discoverable. A specific model does not guarantee automatic Skill invocation; verify the tool trace.

## 3. Data root and runnable shell shortcut

The root priority is: global `--data-root` option → `SOURCELORE_DATA_ROOT` → `~/.config/sourcelore/config.json` key `data_root` → `~/.sourcelore/`.

For a new database you may explicitly choose a location outside the checkout:

```sh
export SOURCELORE_DATA_ROOT="$HOME/SourceLore_Data"
sourcelore() {
  python3 "$HOME/.agents/skills/sourcelore/scripts/sourcelore.py" "$@"
}
sourcelore status
sourcelore repositories
```

The `sourcelore()` shell function is **only defined in this terminal**. The project does not install a global `sourcelore` binary by default. If you have existing data elsewhere, use the **existing** configured data root; do not create an empty database and mistake it for data loss.

## 4. Plan capture, then analyze a real fixed Commit

```sh
# Read-only plan; no repository content is captured by this step.
sourcelore analyze https://github.com/OWNER/REPO --plan

# First actual collection, when network use and source authorization are allowed.
# Supply a real 40-hex commit SHA for reproducibility.
sourcelore analyze https://github.com/OWNER/REPO --commit COMMIT_SHA --request-limit 8

# Offline reuse only after a suitable local snapshot exists.
sourcelore analyze https://github.com/OWNER/REPO --commit COMMIT_SHA --offline
```

Replace `OWNER/REPO` and `COMMIT_SHA` with real values. First capture may be limited by GitHub quota and by SourceLore's five-dimensional authorization policy. `--offline` on a brand-new uncached repository returns `OFFLINE_CACHE_MISS` rather than creating knowledge. Tree coverage and captured file-content coverage are different; `ROOT_ONLY` is not a complete repository analysis.

## 5. Ask practical questions

```sh
sourcelore repositories
sourcelore answer REPOSITORY_ID "What does this project do?"
sourcelore answer REPOSITORY_ID "How is it installed and used?"
sourcelore answer REPOSITORY_ID "Explain the source implementation"
sourcelore query REPOSITORY_ID --commit COMMIT_SHA --type claims
```

The `answer` command assembles evidence-backed local knowledge; it does not run an LLM. If README bytes or source code have not been authorized and captured, it **cannot** infer their implementation from filenames. CLI verdicts are not human review; source repository commits are historical snapshots, not guaranteed current upstream versions.

## 6. Troubleshooting and safety

| Symptom | Verify |
|---|---|
| `找不到 SourceLore 工程根` | Marker `.sourcelore-skill.json` or `SOURCELORE_PROJECT_ROOT` points to the actual checkout |
| `sourcelore: command not found` | Re-create the shell function or invoke `python3 .../scripts/sourcelore.py` directly |
| Empty `repositories` | Check the configured data root before creating or migrating any database |
| `OFFLINE_CACHE_MISS` | The requested fixed Commit has not been captured locally; `--offline` cannot fetch |
| `CONTENT_NOT_CAPTURED` | A path/metadata entry is not proof that file bytes were obtained |
| An apparently complete tree | Inspect effective `ROOT_ONLY`/partial/full scope, not only the old raw snapshot status |

SourceLore never needs to execute untrusted third-party repository code. Do not paste GitHub tokens into committed files or chat logs. Outputs remain subject to the existing runtime `DISTRIBUTE` restriction.
