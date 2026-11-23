# SourceLore Roadmap

This document describes what SourceLore has completed, partially completed, not yet implemented, and plans to extend. Statuses strictly follow the requirements-document vocabulary: `IMPLEMENTED`, `PARTIAL`, `PLANNED`, `BLOCKED`, and `NOT_VERIFIED`. The Chinese version is [docs/zh-CN/ROADMAP.md](../zh-CN/ROADMAP.md); facts, interfaces, and statuses are identical in both languages.

## 1. Status overview

| Area | Status |
|---|---|
| M0 environment diagnosis | IMPLEMENTED |
| M1 read-only audit of six upstreams | IMPLEMENTED |
| F1 fusion decisions | IMPLEMENTED |
| F2 implementation of P0–P6H | IMPLEMENTED |
| P0 trust integrity fixes | IMPLEMENTED |
| P1 content Q&A layer (`answer`) | IMPLEMENTED |
| Recursive subtree capture | PARTIAL (`recursive` parameter implemented, blocked by GitHub API quota) |
| Deep content coverage | PARTIAL (only 3/4/9 files captured across three repositories) |
| Source `imports` relations | PARTIAL (`imports=0`; only a few source files captured) |
| README semantic parsing | PARTIAL (skewed toward structural observation) |
| `answer` wired to AST Facts / LLM | PLANNED |
| Full call graph / runtime analysis | PLANNED (explicitly out of scope for now) |
| Compliant distribution path | BLOCKED (requires resolving B-1/B-2/B-3 and licensing) |

## 2. Completed (IMPLEMENTED)

### 2.1 M0 environment diagnosis

Verified the local OS, Python, Git, Node, DSH, Skill discovery mechanism, SQLite FTS5, and GitHub API reachability through real command execution. Conclusion: PASS, no blocking items (see `docs/environment-audit.md`).

### 2.2 M1 read-only audit of six upstreams

Pinned each of six upstreams to a specific commit, downloaded read-only local snapshots, and read them statically, separating "abstract design ideas" from "concrete implementation". The audit produced six `docs/upstream-audit-0N-*.md` files and `docs/upstream-manifest.json`. UPSTREAM-06 has no license and was copied zero times, and is treated most strictly (see `THIRD_PARTY_NOTICES.md`).

### 2.3 F1 fusion decisions

Completed the capability index, Crosswalk, batch decisions, and frozen baseline; the frozen SHA-256 of `docs/fusion/CAPABILITY_CROSSWALK.json` is `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b`.

### 2.4 F2 implementation of P0–P6H

Implemented and accepted the stages from P0 through P6H: storage layering (A immutable / B current pointers / C index / D derived), collector, Facts, Evidence-Claims, Lifecycle, Renderer, Research, Skill interface, product acceptance, and multi-repository support. Per-batch decisions and verification records are in `docs/fusion/` and `docs/implementation/`.

### 2.5 P0 trust integrity fixes

Fixed identity checks, evidence gating, and view isolation: placeholder commits are rejected, cross-repository commits are blocked, `current_view` is the sole authority, evidence-integrity downgrade rules apply, and `ROOT_ONLY` is never presented as `COMPLETE`. Enforced by `src/trust/policy.py`, `src/trust/tree_scope.py`, and `tests/trust` (25 P0 items).

### 2.6 P1 content Q&A layer (`answer`)

After verifying that the four foundations — content bytes, the authorization gate, parsers, and project-document generation — already existed, **nothing was rebuilt**; only the user-facing natural-language intent-routing and knowledge-answering layer was added: `src/skill_interface/knowledge_answer.py` and the `answer` subcommand, supporting six intents (introduce / usage / architecture / code / evidence / completeness), content-first, read-only, zero-network, non-fabricating, and non-writing. Acceptance is documented in `progress/P1-CONTENT-QA-2026-11-23.md` (all 12 criteria met).

## 3. Partially completed (PARTIAL)

### 3.1 Recursive subtree capture

`src/collector/tree_collector.py` implements full-tree enumeration with `recursive=True` and a per-level `_deep_walk` fallback, with a depth limit of 12; `src/trust/tree_scope.py` can derive historically mislabeled `COMPLETE` values into `ROOT_ONLY` from objective fields. However, the three registered repositories are still actually `ROOT_ONLY`: subdirectories have not been systematically captured. The recursive capability is **implemented but blocked by the GitHub API quota**, and awaits sufficient quota or token conditions for large-scale use.

### 3.2 Deep content coverage

The registered `captured_blob_content` assets are single-file, root-level supplementary captures; the three repositories contain only **3 / 4 / 9** captured files respectively. README parsing is skewed toward structural observation (headings, links, code-block languages), and functional semantics come only from quoted README text. This is insufficient to answer full architecture or module-design questions.

### 3.3 Source relations (`imports`)

Source knowledge already includes Python AST, JS/TS tree-sitter, and tsconfig-aware module resolution, but currently `imports=0` and only a few source files were captured, so module-relation coverage is severely insufficient. Missing coverage does not mean "no dependency exists".

### 3.4 Knowledge sources for `answer`

`answer` is deterministic retrieval and assembly: content-first, answering from verified bytes and registered assets. It is **not wired to AST Facts, not wired to an LLM, and does not perform open-ended reasoning**.

## 4. Not implemented / planned (PLANNED)

- **Expand content-capture depth**: cover complete architecture, module design, and implementation ideas for large projects, subject to quota, budget, and authorization-gate constraints.
- **Integrate existing AST Facts more fully**: let `answer` use already-analyzed functions, symbols, and module facts, not just literal excerpts of content bytes.
- **Full call graph**: explicitly out of scope for now; this tool does not produce call graphs, runtime behavior, or test-pass conclusions.
- **Other future extensions**: expand query and Q&A capabilities while preserving the read-only, offline-first, evidence-groundable properties.

## 5. Blocked (BLOCKED)

- **Compliant distribution path**: `distribution_allowed=false`, `copy_permitted=false`, and all distribution gates B-1/B-2/B-3 are open; output is internal preview only. Any public distribution must first resolve these three gates and the licensing questions and complete human P-3 / P-4 approval.
- **Scaling recursive capture**: technically implemented, but blocked by the GitHub API quota (unauthenticated 60 requests/hour); it must wait for quota or token conditions.

## 6. Not verified (NOT_VERIFIED)

- Conclusions about full call graphs, runtime behavior, and test results: not produced by this tool, hence not verified.
- The effect of wiring `answer` to AST Facts / LLM: not yet implemented, hence not verified.
- File-permission isolation on multi-user hosts: `kb.db` defaults to `0644` and directories to `0755`, with no additional hardening; the isolation effect is not verified.

## 7. Common limitations (apply to all stages)

- The three repositories are `ROOT_ONLY`: subdirectories have not been systematically captured; architecture-level answers cover only captured files.
- `captured_blob_content` is a single-file, root-level supplementary capture; the three repositories have only 3/4/9 files captured.
- No call graph, runtime behavior, or test-pass evidence is produced — the tool explicitly does not produce such conclusions.
- README parsing is skewed toward structure; functional semantics come only from quoted README text.
- `distribution_allowed=false`, B-1/B-2/B-3 all open; output is internal preview only, never distributed.
- `answer` is deterministic retrieval and assembly, not wired to an LLM, and does not perform open-ended reasoning.

## 8. References

- Historical acceptance and gaps: `progress/P1-CONTENT-QA-2026-11-23.md`
- Status vocabulary and per-item basis: `docs/en/REQUIREMENTS.md`, `docs/zh-CN/REQUIREMENTS.md`
- Related documents: [Security](SECURITY.md), [Testing](TESTING.md), [Installation](INSTALLATION.md)
