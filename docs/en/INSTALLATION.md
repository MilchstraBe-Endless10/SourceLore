# SourceLore Installation Guide

This guide explains how to install SourceLore from scratch and use it through the CLI, as a Skill, or from an OpenBot / DSH / Hermes agent. Every command in this document is taken from the real CLI `--help` output. If there is any discrepancy, the authoritative source is always the actual output of `python3 <skill-dir>/scripts/sourcelore.py --help` and `python3 <skill-dir>/scripts/sourcelore.py <subcommand> --help`.

SourceLore is a **local knowledge-base tool**, not a model service. It captures a fixed commit of a public GitHub repository into verifiable, re-queryable knowledge assets (Fact, Claim, Verification, Evidence) and exposes them to agents through a Skill plus CLI. It does not perform open-ended reasoning and it never executes code from the target repository.

> This repository contains source code, documentation and tests only. The knowledge database, captured content bytes, third-party snapshots and local caches are all stored outside the repository.

---

## 1. Requirements

| Item | Requirement | Notes |
|---|---|---|
| Python | Python 3 (developed and tested on 3.14) | The CLI is launched directly with Python 3; there is no build step |
| Dependency manifest | There is **no** top-level `requirements.txt` | The core CLI needs no third-party Python packages to start |
| Git | Any working installation | Used for snapshots and commit pinning |
| Virtual environment | Optional but recommended | Used only to isolate JS/TS parser dependencies; never touches system Python |
| SQLite | FTS5 support is optional | Used for the derived index; absence degrades gracefully and does not affect core functions |
| `GITHUB_TOKEN` | Optional | Raises the GitHub API limit (unauthenticated: 60 requests/hour). Never required for offline queries |
| Network | Needed only for capture | Queries, answers and card generation make zero network requests |

The entry-point script **locates the SourceLore project root on its own** (you can also set it explicitly with the `SOURCELORE_PROJECT_ROOT` environment variable). As long as `skill/sourcelore/` keeps its original relative structure to the source tree, the script works without extra configuration.

### 1.1 Paths containing parentheses and spaces

The project root may contain parentheses, spaces or non-ASCII characters (Chinese), for example a path shaped like:

```
/mnt/<volume>/<team-dir(中文)>/<knowledge-base(中文)>/SourceLore
```

- In the shell, always **quote** such paths.
- In Python, use `pathlib` or `open()` with an absolute path; **do not** build it by string concatenation.
- Do not rely on `cd` and relative paths; the agent session's working directory is usually not the project root.

---

## 2. Obtain the source

Clone or copy the SourceLore project into a fixed local directory. Below, `<project-root>` refers to that directory; the CLI script is located at:

```
<project-root>/skill/sourcelore/scripts/sourcelore.py
```

---

## 3. Verify the CLI runs directly

Before installing the Skill into an agent, confirm the script itself is runnable:

```sh
python3 "<project-root>/skill/sourcelore/scripts/sourcelore.py" --version
python3 "<project-root>/skill/sourcelore/scripts/sourcelore.py" --help
python3 "<project-root>/skill/sourcelore/scripts/sourcelore.py" help
```

`--version` returns JSON such as:

```json
{
  "ok": true,
  "skill_version": "0.1.0-beta.3"
}
```

`--help` lists all subcommands:

```
usage: sourcelore [-h] [--data-root DATA_ROOT] [--version]
                  {status,repositories,help,analyze,inspect,history,query,derive,answer,card} ...
```

If the script reports that it cannot locate the project root, set:

```sh
export SOURCELORE_PROJECT_ROOT="<project-root>"
```

---

## 4. Install the Skill

### 4.0 Official installer (recommended)

From a Git checkout, or from a downloaded standalone release ZIP, use the
official installer instead of copying files by hand:

```sh
# From a Git checkout:
python3 tools/install.py install
python3 tools/install.py doctor

# From a standalone release ZIP, using the installer in your checkout:
python3 tools/install.py install --zip /path/to/sourcelore-skill-vX.Y.Z.zip

# ZIP-only bootstrap (no clone and no checkout installer at all):
# download the ZIP, extract it, then run the install.py INSIDE the ZIP:
python3 /path/to/extracted/sourcelore/install.py install

# Later: update (safe staged + rollback), uninstall (keeps your data):
python3 tools/install.py update --zip /path/to/sourcelore-skill-vNEWER.zip
python3 tools/install.py uninstall
```

The standalone ZIP is **self-bootstrapping**: it contains its own `install.py`
and bundled program source, so downloading only the ZIP artifacts is enough —
no access to the source repository is required. The embedded `RELEASE_INFO.json`
records the installer's SHA-256 so you can verify it before running. The
installer installs a **self-contained** Skill, so the original checkout/ZIP and
the extraction directory can be deleted afterwards. It never writes to the
knowledge-base data root, refuses to overwrite a Skill directory it does not
own, and needs no root privileges. See [UPGRADING.md](UPGRADING.md).

`doctor` is read-only and reports an explicit `status`:

| `status` | Meaning | `ok`/exit code |
|---|---|---|
| `ok` | Installed, owned, launcher runs, version matches | `true` / 0 |
| `not_installed` | Skill directory does not exist | `false` / 1 |
| `unowned` | Directory exists but has no SourceLore marker | `false` / 1 |
| `incomplete` | Install directory is missing required files | `false` / 1 |
| `launcher_failed` | Launcher exists but fails to run | `false` / 1 |
| `version_mismatch` | Launcher version differs from expected/marker | `false` / 1 |

A missing or empty knowledge database is **not** an install failure: it is
reported as `data_root_status=not_created`/`empty` while a healthy install still
reports `status=ok`. Use `--expect-version` to pin the expected launcher version.

The manual copy procedure below is retained for reference and for hosts that
require a specific discovery layout.

The Skill is loaded by the platform's filesystem discovery mechanism. Copy the **entire** `<project-root>/skill/sourcelore/` directory into the agent's Skill discovery directory, for example:

```sh
# Do not accidentally create sourcelore/sourcelore in an existing destination
mkdir -p "$HOME/.agents/skills"
# First install: cp -a "<project-root>/skill/sourcelore" "$HOME/.agents/skills/sourcelore"
# For complete commands and root-marker creation see docs/en/QUICKSTART.md
```

Key points:

- The entry point `SKILL.md` must carry both `name` and `description` frontmatter fields; the `description` should contain explicit trigger phrases so the filesystem discovery mechanism can hot-load it.
- Discovery depends on the host; some hot-load while others require a new conversation or an index refresh. Verify the actual Skill tool trace rather than assuming success.
- Discovery usually scans only direct bundles of the form `<discovery-root>/<name>/SKILL.md`, so the installation depth must be exact — do not add an extra nesting level.

### 4.1 User-level and project-level discovery roots

Taking DSH/OpenBot as an example:

- **User-level root** (e.g. `<DSH_HOME>/skills` or `~/.agents/skills/`): discovered by every session. If the agent session's working directory is not the project root, this is the only dependable way for the Skill to be triggerable.
- **Project-level root** (e.g. `<project-root>/.dsh/skills`): discovered only by sessions whose working directory is inside that project.

Install to the user-level root at minimum, so the Skill is callable from any session.

### 4.2 Keep the three copies in sync (important)

There are commonly three copies of the SourceLore Skill:

1. Project source: `<project-root>/skill/sourcelore/`
2. Installed copy: `~/.agents/skills/sourcelore/`
3. Hermes copy: `~/.hermes/skills/sourcelore/`

**Changing only the project source is not enough.** A session that actually loads the installed copy will not see new commands or rules; a claim that a command "is registered" would be false. Historically, editing only the project source left the installed copy without the `answer` command registered. After every change:

- Copy the updated `SKILL.md` and any added or modified `references/*.md` and `scripts/` files to all three locations.
- Verify the three `SKILL.md` files match by checksum:

```sh
md5sum <project-root>/skill/sourcelore/SKILL.md \
       ~/.agents/skills/sourcelore/SKILL.md \
       ~/.hermes/skills/sourcelore/SKILL.md
```

All three lines should show the same hash.

---

**Important:** the launcher copied under `~/.agents/skills/sourcelore/` is no longer inside the source checkout. It must have `SOURCELORE_PROJECT_ROOT` or an installed `.sourcelore-skill.json` marker containing `{"project_root":"/absolute/path/to/SourceLore"}`. Otherwise it may fail to locate the project root. Use the validated [Quick Start](QUICKSTART.md) for safe marker creation.

## 5. Configure the knowledge-base data root

The knowledge-base root defaults to `~/.sourcelore/` and can be overridden in two ways:

```sh
# Option 1: global command-line option (must appear before the subcommand)
python3 <skill-dir>/scripts/sourcelore.py --data-root /path/to/data status

# Option 2: environment variable
export SOURCELORE_DATA_ROOT="/path/to/data"
```

Important constraints:

- The database file `kb.db` is **never** written into the source repository; there is a guard in the script that raises an error on a repository path.
- Cards and reports are written to `<data-root>/preview/`.
- Do not commit the knowledge database, captured bytes, third-party snapshots or local configuration into Git.
- On first launch, check that the intended persistent data root is configured and actually contains real repositories. If it is missing or empty, do not silently create a new empty database in place of existing data, and do not delete, merge or migrate historical assets on your own.

---

## 6. Optional: install the JS/TS parser

Source-structure analysis supports:

- Python (`.py`) via the standard library `ast`, with no extra dependency.
- JS/JSX/TS/TSX via tree-sitter, with pinned versions recorded in `requirements-treesitter.txt`:

```
tree-sitter==0.26.0
tree-sitter-javascript==0.25.0
tree-sitter-typescript==0.23.2
```

These dependencies must be isolated in a **project-local virtual environment `.venv/`**; do not modify system Python and do not auto-download grammars:

```sh
cd <project-root>
python3 -m venv .venv
.venv/bin/pip install -r requirements-treesitter.txt
```

When these grammars are unavailable, the parser returns `PARSER_UNAVAILABLE` and **does not** fall back to regex. Python source analysis still works in that case.

---

## 7. Optional: configure a GitHub token

Setting the `GITHUB_TOKEN` environment variable raises the quota (unauthenticated: 60 requests/hour):

```sh
export GITHUB_TOKEN="<your-token>"
```

Security constraints:

- It is read only from the process environment; it is never written to logs, assets or Git.
- A single invocation can force-disable it with `--no-token`, even when it is present in the environment.
- When rate-limited, the CLI returns within **2 seconds** with error `RATE_LIMITED` and the real `retry_after` value in seconds. It **does not** retry automatically, wait idly, or bypass the limit. Prefer `--offline` to consult local data first, or retry later with `--refresh`.

---

## 8. Set up a convenient alias (optional)

The real entry point is the full script path. For convenience you can define an alias so commands match the `usage: sourcelore ...` form shown in `--help`:

```sh
alias sourcelore='python3 <skill-dir>/scripts/sourcelore.py'
```

Then you can write:

```sh
sourcelore status
sourcelore repositories
```

Throughout the rest of this document, `sourcelore` denotes that entry point; when executing, replace it with the full path or use the alias above.

---

## 9. Verify the installation

```sh
sourcelore status
sourcelore repositories
```

- `status` reports runtime state: skill version, data root, whether the database exists, repository count and the most recent operation. No credentials are emitted.
- `repositories` lists registered repositories: `repository_id`, `commits`, `snapshot_count`, `fact_count`, `claim_count` and `knowledge_state`.

In an agent, trigger a natural-language verification:

- "What GitHub projects are in my knowledge base?"
- "Introduce this GitHub project."

If the agent cannot invoke it, check: whether the Skill is in the correct discovery root, whether `SKILL.md` has both `name` and `description`, and whether the three copies are in sync.

---

## 10. Common errors and troubleshooting

### 10.1 Exit codes

All JSON output goes to stdout and errors to stderr. Exit codes:

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Execution failure (including GitHub errors) |
| 2 | Argument error |
| 3 | Knowledge base unavailable (not established) |

An error JSON looks like:

```json
{"ok": false, "error": "...", "message": "..."}
```

When you see `ok: false`, report the failure truthfully rather than glossing over it.

### 10.2 Typical error states

| State / symptom | Cause | Resolution |
|---|---|---|
| `PARSER_UNAVAILABLE` | JS/TS tree-sitter grammars not installed | Install `requirements-treesitter.txt` into `.venv`; or use Python source analysis; do not substitute regex |
| `OFFLINE_CACHE_MISS` (exit 3) | `--offline` used with no local snapshot for that commit | Capture once without `--offline`, or use an already registered commit |
| `RATE_LIMITED` | GitHub API quota exhausted | Read `retry_after`, retry later; use `--offline` to consult local data first; do not auto-retry or bypass |
| `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT` | Content extraction exceeded budget (256 KiB per blob, 2 MiB per batch, 32 candidate paths, 100 facts per file) | Narrow the scope with `--content-path` |
| Exit 3 / knowledge base unavailable | Data root not established or pointing to the wrong place | Point `--data-root` or `SOURCELORE_DATA_ROOT` at a root with real data |
| `kb.db` write rejected | Attempt to write the database into a Git repository | Use a data root outside the repository |
| New command does not work in the agent | Only the project source was edited; installed / Hermes copies not synced | Sync all three copies as in section 4.2 and confirm with `md5sum` |
| Path not found / command fails | Parentheses or spaces in path not quoted, or a relative path was used | Quote it in the shell; use `pathlib` in Python; use absolute paths |

### 10.3 Offline semantics

`analyze` performs a local lookup first, then decides whether to use the network:

| Situation | Behavior |
|---|---|
| `--commit <sha>` with a complete local snapshot | Reuse directly, **zero network requests** |
| `--offline` with local data present | Reuse, explicitly marked "GitHub was not contacted" |
| `--offline` with no local data | Report `OFFLINE_CACHE_MISS` (exit code 3); do not fabricate a result |
| `--refresh` | Allow re-fetching from the network |
| No `--commit` (mutable branch) | Return `branch_current_unknown: true` |

A local snapshot proves only "a version observed in the past"; it cannot prove that a branch still points to it.

---

## 11. Limitation semantics (understand these clearly)

- **`ROOT_ONLY`** means only the repository root was enumerated. It is **never** equivalent to full `COMPLETE` coverage; missing content is "not analyzed", not "does not exist". A `tree_status=ROOT_ONLY` from `derive` is the genuine coverage state — do not "correct" it to COMPLETE.
- **`distribution_allowed=false`**: all cards and reports are internal previews; distribution gates B-1/B-2/B-3 remain open. This applies to **captured third-party knowledge output only**, not to SourceLore first-party code, which is MIT-licensed (see `LICENSE`).
- **`review_status=pending_review`**: every `supported` verdict carries this field, meaning it is a CLI adjudication not yet human-reviewed; it must not be described as "confirmed".
- **`completeness_status: PARTIAL`**: when the tree is truncated, uncovered parts must not be judged as "non-existent".
- **`insufficient_evidence`**: say only "insufficient evidence", never "the proposition is false".
- **`refuted`**: holds only for that commit; do not extrapolate to other versions or to "the project does not exist".
- The tool **does not execute** repository code: no `exec`, `eval`, import, test run or shell execution.
- Only `https://github.com/<owner>/<repo>` is accepted; internal addresses, non-GitHub hosts and unusual ports are rejected; private repositories are not supported.

After installation, continue with the [User Guide](USER-GUIDE.md).
