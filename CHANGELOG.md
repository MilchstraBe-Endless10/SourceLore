# Changelog

All notable changes to SourceLore are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

SourceLore's release version is defined in one place:
`src/skill_interface/version.py` (`RELEASE_VERSION`). The internal development
codename `f2p5a` is kept separately and is no longer used as a public version.

## [Unreleased]

Planned but not yet implemented: deeper repository content coverage beyond
ROOT_ONLY, full call-graph analysis, native card UI, first-party model/model
provider integration.

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

[Unreleased]: https://github.com/MilchstraBe-Endless10/SourceLore/compare/v0.1.0-beta.1...HEAD
[0.1.0-beta.1]: https://github.com/MilchstraBe-Endless10/SourceLore/releases/tag/v0.1.0-beta.1
