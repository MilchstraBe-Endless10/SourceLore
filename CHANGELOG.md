# Changelog

All notable changes to SourceLore are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

SourceLore's release version is defined in one place:
`src/skill_interface/version.py` (`RELEASE_VERSION`). The internal development
codename `f2p5a` is kept separately and is no longer used as a public version.

## [Unreleased]

### P2-C graph-driven deep answer (development branch, not a released version)

This is an **unreleased development change** on branch `dev/p2c-deep-answer`,
based on the P2-B commit `fb56e18`. It does not change `RELEASE_VERSION` (still
`0.1.0-beta.3`), creates or moves no release tag, and must not be presented as a
published version.

- Fixed the P2-B graph consumption defect: source facts are now classified by
  real `rule_id` through a shared contract (`source_fact_contract.py`), Python
  AST import fields (`module_name` / `relative_level` / `imported_name`) are
  normalized to a specifier, and unknown rules are never disguised as symbols.
  Specifier-less from-imports no longer masquerade as declarations; `IMPORT`
  and `RE_EXPORT` edges are kept distinct.
- Replaced silent 200-row truncation with real bounded pagination
  (`ORDER BY asset_id` + `offset` + `has_more` probe). Sample A actually has
  553 source facts (218 symbols + 335 imports), not the old truncated 200;
  sample B has 236 (129 symbols + 43 imports + 64 exports).
- Added a read-only, deterministic graph query engine (`graph_query.py`):
  entity resolution with ambiguity, single-node queries, forward/reverse
  static dependencies, and bounded multi-hop paths with cycle detection,
  truncation state and honest `NO_PATH_FOUND`.
- Added `deep_answer.py`: deterministic, no-LLM, zero-network, zero-write
  unified retrieval that overlays graph results on the existing `answer()`
  contract. Query status distinguishes answered / not-located / ambiguous /
  unavailable / not-found from a bare `ok=true`.
- D3 supplement sources and relations are consumed with their identity kept
  distinct from the primary GitHub source; same-name nodes are never merged and
  content equivalence never expands authorization. AST declarations now reach
  project documents, and multi-candidate resolutions no longer blindly pick
  `verified[0]`.

### P2-B knowledge graph trust fixes (development branch, not a released version)

This is an **unreleased development change** on branch `dev/p2b-knowledge-graph`,
based on the P2-A commit `5777e75`. It does not change `RELEASE_VERSION` (still
`0.1.0-beta.3`), creates or moves no release tag, and must not be presented as a
published version.

- Fixed fixed-commit derivation mixing: all snapshot/blob/symbol/relation reads
  now go through one versioned-asset entry keyed by repository id + commit SHA;
  a missing pinned commit returns a missing state instead of falling back to a
  newer version, and unpinned reads use the single `current_view` pointer.
- Unified source-symbol reading: AST facts win per file; regex extraction is only
  a clearly labelled `LITERAL_FALLBACK`, never disguised as AST facts. Derive
  now reads source facts through the formal `source_knowledge.query_code()`
  entry with bounded pagination.
- The derived graph consumes P2-A static relations and only turns evidence-
  verified local resolutions into `RESOLVES_TO` edges; unresolved imports stay
  observation-only. Node/edge ids carry repository, commit, path and scope so
  same-name symbols never merge across versions or repos; `graph_digest` is
  deterministic. Coverage and limitations are recorded honestly.

### P2-A static module-relation ingest closure (development branch, not a released version)

This is an **unreleased development change** on branch `dev/p2a-static-relation`.
It does not change `RELEASE_VERSION` (still `0.1.0-beta.3`) and creates or moves
no release tag. It must not be presented as a published version.

- Added a shared static module-relation pipeline (`module_relation_pipeline.py`)
  used by GitHub online capture, local Git capture and offline backfill: verified
  bytes → existing parsers → import observations → same-commit tree → language
  resolver → evidence check → idempotent ingest. The online path previously
  parsed sources but never called `ingest_resolution()`, so relation queries
  always returned `NO_RELATIONS`; it is now connected and persists relations.
- Fixed relation evidence location: importer, config and target identities are
  strictly separated; a config blob no longer masquerades as the importing
  source blob, and an observation ID is no longer passed off as a persisted
  Fact ID. The online fixture confirms the importer blob OID is used correctly.
- Added an honest query status contract (`status` / `status_counts` / `attempts`);
  unresolved imports are recorded as B-layer `module_resolution_attempt` audit
  records, never authoritative A-layer facts. `NO_RELATIONS` no longer means
  "verified no dependency". D3 verified supplement sources can optionally be
  attached to relation queries (`include_supplements`) with their identities.
- Added offline incremental backfill (`cli.py backfill-relations <rid> --commit
  <sha>`): reuses already-captured bytes only, zero network, idempotent, A-layer
  unchanged. Sample A (arch-grower copy) yields 196 relations + 139 external;
  sample B (Preact copy) yields 33 relations + 2 config facts + 1 project fact;
  second runs write 0 assets with identical A-layer fingerprints.

### D3 cross-source knowledge binding (development commit, not a released version)

This is an **unreleased development change** on branch `dev/d3-source-binding`.
It does not change `RELEASE_VERSION` (still `0.1.0-beta.3`) and does not create
or move any release tag. It is recorded here only to keep the development
history explicit; it must not be presented as a published version.

- Strict source-provenance verification before binding: a numeric GitHub ID is
  trusted only when an authoritative A-layer `subject_record` with an explicit
  `resolved_repository` exists, the fixed commit and root tree match, and the
  GitHub root-level `blob_refs` are a hash-consistent subset of the local
  recursive blob map. Same commit + root tree alone is never treated as proof
  of identity (guards against forks / spoofed remotes).
- `repo_bindings` written only through the official `KnowledgeStore.bind_repo`
  interface (B-layer relation table); A-layer immutable assets are unchanged.
- `answer`, `query`, `inspect` now resolve verified local supplement sources
  from a GitHub ID alone: `answer` appends supplement blocks tagged with
  `source_repository_id`, `query` falls back to the verified supplement and
  tags `supplement_of`, all with zero network requests and no knowledge-base
  writes during reads.
- Historical ROOT_ONLY snapshots no longer display as COMPLETE: `inspect`
  derives `coverage_scope=ROOT_ONLY` from objective fields and keeps the old
  value only as `recorded_completeness_status` for audit.
- New standalone test fixture (`tests/trust/test_source_provenance_d3.py`)
  builds temporary databases and contains no author-machine path hardcoding.

Planned but not yet implemented: deeper repository content coverage beyond
ROOT_ONLY, full call-graph analysis, native card UI, first-party model/model
provider integration.

## [0.1.0-beta.3] - 2026-11-24

Focused repair of the online GitHub capture pipeline, plus release-compliance
fixes. The `v0.1.0-beta.1` and `v0.1.0-beta.2` tags and releases are untouched.

### Fixed
- (D1) The formal `analyze` entry point now reuses the recursive `TreeCollector`
  (`recursive=True`) instead of issuing a single non-recursive `client.tree()`
  call. Nested directory entries are persisted in the snapshot and the real
  coverage is reported via `coverage.scope`. A truncated or depth-limited walk
  is marked `PARTIAL`/`ROOT_ONLY`, never `COMPLETE`. Cache hits are derived
  from real recursive coverage, so a historical root-only snapshot is no
  longer mistaken for a complete tree.
- (D2) `content_capture.capture` no longer overwrites the caller's
  `GitHubRequestBudget` with an internal dict. Internal byte-batch accounting
  uses a separate `byte_budget`; the external budget keeps `can_spend` /
  `consume`. This removes the `AttributeError: 'dict' object has no attribute
  'can_spend'` failure on online `--include-content` captures.
- (D4) An explicit `--commit` is now a hard contract: the resolved commit is
  checked against it and a mismatch aborts with `COMMIT_MISMATCH` before any
  tree/blob request. Ref resolution uses the fixed commit, not the branch ref.
- (D5) Identity, commit, tree and content capture now share one
  `GitHubRequestBudget` under a single `max_requests` hard cap. Tree queries
  are charged to the same budget; `request_budget` and `network_requests` are
  reported in analyze output. The first identity request is allowed without
  authoritative rate-limit headers while still respecting the local cap.
- (D3) Added non-destructive cross-source binding via content-address anchors
  (`commit_sha` + `root_tree_sha`) in `src/trust/source_binding.py`. Two
  independent snapshots of the same content (GitHub skeleton and local Git
  mirror) can be related with an evidence-backed `repo_bindings` entry;
  repository identities are never merged and A-layer assets are never changed.
  Verified on an isolated database copy.
- (D7) Raw stdout/stderr of `inspect local:` was captured byte-for-byte:
  valid UTF-8, no stray logs/ANSI, standard `json.loads()` succeeds. The
  earlier parse failure was host tool-output truncation, not a program defect;
  no output-layer change was made.
- Release ZIP now bundles `LICENSE` (MIT) and `THIRD_PARTY_NOTICES.md`.
- Release workflow marks beta/rc/alpha tags as Pre-release automatically.
- Standalone installer, doctor and CLI report version `0.1.0-beta.3`; marker
  points to the final install directory and the knowledge data root is
  isolated.

## [0.1.0-beta.2] - 2026-11-24

Fix release installation defects found after the first public beta. The
`v0.1.0-beta.1` tag and release are left untouched.

### Fixed
- The standalone release ZIP now embeds its own installer (`install.py`) and
  records that installer's SHA-256 in the embedded `RELEASE_INFO.json`. A user
  who only downloads ZIP artifacts can bootstrap SourceLore without cloning
  the source repository: extract the ZIP and run `python3 install.py install`
  from the extracted directory (no `--source` or `--zip` needed). This fixes
  the gap where docs told ZIP-only users to run `tools/install.py`, a file
  that was not inside the ZIP.
- `doctor` now has an explicit status contract (`ok`, `not_installed`,
  `unowned`, `incomplete`, `launcher_failed`, `version_mismatch`). Damaged or
  missing installs report `ok=false` / `healthy=false` and exit code 1; they
  can no longer be reported healthy. An uninitialized or empty knowledge
  data root (`data_root_status=not_created`/`empty`) is reported separately
  and never counts as a Skill install failure. `--expect-version` pins the
  expected launcher version.
- Added an offline acceptance test file (`tests/release_installer/`) covering
  ZIP self-bootstrap, deletion of the ZIP and extraction directory, all six
  `doctor` states, data-root isolation, and update/uninstall/reinstall; wired
  into both CI and the release workflow.

## [0.1.0-beta.1] - 2026-11-24

First public beta. Core read-only knowledge-base pipeline is functional;
several coverage and distribution limits remain (see SECURITY.md, ROADMAP.md).

### Added
- Unified version source (`src/skill_interface/version.py`); CLI `--version`
  and `status` report the semantic version consistently.
- MIT `LICENSE` for SourceLore first-party code. The runtime
  `distribution_allowed=false` gate for captured third-party knowledge output
  is a separate policy and is unchanged.
- Official installer `tools/install.py` with `install`, `doctor`, `update`,
  `uninstall` and `doctor --json` subcommands, supporting both Git-checkout
  and standalone ZIP installs, with safe update/rollback that preserves the
  user's knowledge-base data root.
- Release packaging script `tools/build_release.py` producing a self-contained
  Skill ZIP plus a SHA-256 manifest.
- Minimal least-privilege GitHub Actions CI (`ci.yml`) and a release workflow
  (`release.yml`) that builds and verifies artifacts before publishing.
- Bilingual CONTRIBUTING, VERSIONING, UPGRADING and public-release documents.

### Changed
- `paths.py` no longer hardcodes the internal codename as the version;
  `SKILL_VERSION` is now a compatibility alias of `RELEASE_VERSION`.
- README files explain the open-source license boundary between first-party
  code and captured third-party knowledge data.

### Fixed
- None in this beta beyond the version-source consolidation.

### Known limitations
- Repository capture is often `ROOT_ONLY`; absence of a path is not proof of
  non-existence.
- AST/source-structure analysis requires optional tree-sitter grammars;
  Python `ast` works without them.
- First-party LLM/model inference is not part of SourceLore; `answer` assembles
  evidence-backed local knowledge only.
- OpenBot / DSH / Hermes Skill discovery is host-dependent and verified only
  on the hosts documented in INSTALLATION.md.

[Unreleased]: https://github.com/MilchstraBe-Endless10/SourceLore/compare/v0.1.0-beta.2...HEAD
[0.1.0-beta.2]: https://github.com/MilchstraBe-Endless10/SourceLore/releases/tag/v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/MilchstraBe-Endless10/SourceLore/releases/tag/v0.1.0-beta.1
