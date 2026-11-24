# Public release readiness — release `v0.1.0-beta.1`

## Amendment: `v0.1.0-beta.3`

Beta.3 repairs the online GitHub capture pipeline: the formal `analyze` entry
now uses the recursive `TreeCollector` with real coverage reporting; the
content-capture budget object bug is removed; explicit `--commit` is enforced;
all GitHub requests share one global `max_requests` budget; and cross-source
identity binding uses non-destructive content-address anchors. See
[CHANGELOG.md](../../CHANGELOG.md) and [RELEASE-ARTIFACTS.md](RELEASE-ARTIFACTS.md).
The `v0.1.0-beta.1` and `v0.1.0-beta.2` tags/releases were **not** moved; beta.3
is a new tag, Pre-release and ZIP. The release ZIP bundles the MIT `LICENSE`
and `THIRD_PARTY_NOTICES.md`.

> The repository was subsequently made Public. This document records the
> verification of the first open-source beta, `v0.1.0-beta.1`, and is retained
> as historical evidence. The beta.1 tag and release are unchanged.

## Amendment: `v0.1.0-beta.2`

A follow-up patch release fixes two installation defects found after beta.1:
the standalone release ZIP now embeds its own `install.py` (so ZIP-only users
can bootstrap without a Git clone), and `doctor` now uses an explicit status
contract that never reports a damaged/missing install as healthy while still
treating an uninitialized knowledge database as normal. See [CHANGELOG.md](../../CHANGELOG.md),
[RELEASE-ARTIFACTS.md](RELEASE-ARTIFACTS.md) and [INSTALLATION.md](INSTALLATION.md).
The `v0.1.0-beta.1` tag and GitHub Release were **not** moved; beta.2 is a new
tag and a new Release. Host integration (OpenBot / DSH / Hermes) remains
unverified — CLI success is not claimed as host acceptance.

## 1. Two independent decisions

- **First-party code visibility/license**: SourceLore's own code is released
  under the [MIT License](../../LICENSE) (`Copyright (c) 2026
  MilchstraBe-Endless10 (Cosmos)`). Making the GitHub repository Public is a
  separate owner decision and has not been performed in this engineering round.
- **Third-party knowledge output**: the runtime `distribution_allowed=false`
  gate (B-1/B-2/B-3) remains closed. MIT covers first-party code only, not
  captured repository bytes, derived knowledge data or the user's database.

## 2. Privacy / secret audit (actually executed)

A full scan of the working tree and all reachable Git objects was performed:

- 193 reachable commits; 1,553 text blobs scanned (full `git cat-file --batch`
  stream, not truncated).
- Secret patterns scanned: GitHub tokens (`ghp_/gho_/github_pat_`), AWS keys,
  private-key blocks, `api_key/secret/token/password` assignments, Slack tokens.
- Result: **no real secret found**. The single `api_key_kv` hit is a synthetic
  string in a test fixture (`tests/content/test_content_e2e.py`), not a
  credential.
- Private local paths: ~340 hits across historical docs (`progress/`,
  `docs/environment-audit.md`, `docs/implementation/*`), i.e. the developer's
  username and mount paths. These are **not secrets** but do disclose local
  directory structure once the repository is Public. Historical commits still
  contain them; deleting them from the current tree alone does not remove them
  from history.

**Owner decision pending**: whether to scrub private paths from Git history
(requires history rewrite + force push, an explicitly gated irreversible
operation) or accept them as-is when making the repository Public. No rewrite
was performed.

## 3. Third-party rights

See [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md): six upstreams
reviewed; all were read-only research, zero code/prompt/rule/template copying.
UPSTREAM-06 has no license and was treated most conservatively (zero copy).
No third-party snapshots are tracked (`.gitignore` excludes `upstreams/`).

## 4. Release artifacts actually built and verified

- Version from single source `src/skill_interface/version.py`:
  `0.1.0-beta.1` (tag `v0.1.0-beta.1`).
- `python3 tools/build_release.py --out dist` produced
  `sourcelore-skill-v0.1.0-beta.1.zip` (self-contained: Skill files + bundled
  `src/` + `RELEASE_INFO.json`), with `SHA256SUMS.txt` verified by
  `sha256sum -c`.
- ZIP contains no `kb.db`, captured bytes, tokens, markers or local config.
- Clean-environment install verified for both Git-checkout and standalone ZIP
  modes; launcher works with no `SOURCELORE_PROJECT_ROOT` and after deleting
  the ZIP; works in paths with spaces, parentheses and Chinese characters.

## 5. Remaining owner gates

- [ ] Approve making the repository Public (irreversible visibility change).
- [ ] Decide on Git-history private-path scrubbing (history rewrite + force push).
- [ ] Confirm the copyright holder string in LICENSE.
- [ ] After going Public: anonymous-browser check of README, LICENSE, docs,
      tag and Release, and ZIP download.

## 6. Not claimed in this round

Making the repo Public, rewriting history, creating the GitHub Release, or
opening distribution gates B-1/B-2/B-3. See
[VERSIONING.md](VERSIONING.md), [UPGRADING.md](UPGRADING.md) and
[CHANGELOG.md](../../CHANGELOG.md).
