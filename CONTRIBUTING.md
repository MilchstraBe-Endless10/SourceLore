# Contributing to SourceLore

Thanks for helping improve SourceLore. This document covers development setup,
tests, source/Skill synchronization, contributing changes and the license
boundary. Read [SECURITY.md](docs/en/SECURITY.md) first: SourceLore captures
public GitHub content but never executes it.

## Development setup

```sh
git clone https://github.com/MilchstraBe-Endless10/SourceLore.git
cd SourceLore
python3 --version                 # Python 3; developed/tested on 3.14
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
python3 skill/sourcelore/scripts/sourcelore.py --version
```

The core CLI uses only the Python standard library. JS/TS parsing needs
optional tree-sitter grammars in a project-local `.venv/`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-treesitter.txt
```

Never install these into system Python. Keep `GITHUB_TOKEN` in the environment
only; never commit it.

## Repository layout

- `src/` — flat Python modules grouped by concern (storage, collector, facts,
  evidence_claims, lifecycle, views, renderer, skill_interface, content,
  source_analysis, ...). There is no single package; `paths.ensure_import_path()`
  wires the directories into `sys.path`.
- `skill/sourcelore/` — the Skill source (`SKILL.md`, `references/`, `scripts/`).
- `tools/` — installer, release packaging and probes.
- `tests/` — test files.
- `docs/{en,zh-CN}/` — bilingual documentation.

## Running tests

Tests are standalone scripts with module-level `sys.exit`; run each file
directly (do not rely on a single `unittest discover` across mixed directories):

```sh
PYTHONPATH=src SOURCELORE_DATA_ROOT=<temp-dir> python3 tests/<path>/test_<name>.py
```

Run the P0 trust tests and the installed-CLI tests specifically before a
release. Record the real pass/fail output; do not claim "tests pass" from an
exit code alone.

## Source / Skill synchronization

Three copies of the Skill commonly exist: project source
`skill/sourcelore/`, installed `~/.agents/skills/sourcelore/`, and
`~/.hermes/skills/sourcelore/`. After changing the Skill, sync all copies and
verify with `md5sum`. The installer (`tools/install.py install`) is the
preferred way to install/update so the marker and launcher stay consistent.

## Contributing a change

1. Fork the repository and create a topic branch.
2. Make a focused change; add or update a test.
3. Run the relevant tests and `python3 tools/install.py doctor`.
4. Update both English and Chinese docs if behavior or commands changed.
5. Open a pull request describing the change, the tests run, and any impact on
   data compatibility or the `distribution_allowed=false` policy.

Do not commit `kb.db`, captured bytes, third-party snapshots, `.venv/`, local
config, tokens or marker files. Do not rewrite Git history or force-push.

## Versioning and releases

Versions follow Semantic Versioning from the single source
`src/skill_interface/version.py`. See [VERSIONING.md](docs/en/VERSIONING.md),
[UPGRADING.md](docs/en/UPGRADING.md) and [CHANGELOG.md](CHANGELOG.md). Releases
are built with `tools/build_release.py` and published only after CI passes.

## License boundary

By contributing you agree your contribution is licensed under the project's
MIT License (see `LICENSE`). That license covers first-party code only — not
captured third-party knowledge data or the user's database, which remain under
the runtime `distribution_allowed=false` policy. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
