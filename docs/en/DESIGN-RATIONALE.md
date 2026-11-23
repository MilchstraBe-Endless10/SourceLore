# SourceLore Design Rationale

> This document answers "why is it designed this way?"; it does not repeat the "what / how connected" material in [Architecture](ARCHITECTURE.md). Architecture describes structure; this document describes trade-offs.
>
> **Evidence discipline**: every reason points to a real decision record, source fact or measured result — `progress/DECISIONS.md` (D-001..D-007), `docs/fusion/BASELINE.md` (F0 errata), `docs/implementation/F2_P0_ADAPTER_DECISIONS.md` (AD-1..AD-6), `docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md`, `docs/implementation/F2_P1C_COLLECTOR_ARCHITECTURE.md`, `docs/implementation/F2_P2A_FACTS_ARCHITECTURE.md`, `docs/implementation/F2_P2B_EC_ARCHITECTURE.md`, plus `src/trust/policy.py`, `src/collector/` and `src/runtime/`. Where only the current implementation can be observed and the original motivation is unknown, the text is labelled **technical reason for the current implementation**; it never invents what the developers were thinking. Where an ADR applies, it cites the real decision records above rather than invented numbers.

---

## 6.1 Why a fixed commit is the knowledge foundation

**Problem**: a GitHub branch is mutable. The README read today may differ from next week's; if the knowledge base records only "the repo's main branch", a conclusion cannot be traced to a specific version or reproduced by someone else.

**Decision evidence**:
- `progress/DECISIONS.md` D-006: all fact collection is done by deterministic scripts writing JSON; the model reads only structured results, avoiding "written-out" unverified facts. A fixed commit is this discipline applied to the version dimension.
- `docs/fusion/BASELINE.md` §3: all six upstream sources are pinned to specific commits and compared entry-by-entry against the real root tree hashes. The premise that "a field-semantics error is not data corruption" only holds because the version is pinned.

**Why**:
1. **Eliminate version drift**. A fixed commit makes "which file tree is this conclusion about?" answerable; a mutable ref binds a conclusion implicitly to time and cannot be verified.
2. **Reproducibility**. Given the same commit, collection, extraction, adjudication and derivation should all yield the same result — the technical precondition for "re-queryable".
3. **Evidence location**. A fact carries `commit_sha` and a path, so a reader can jump to the exact remote version and check, rather than seeing only "somewhere in that repo".

**What is not done**: a mutable branch is never treated as knowledge identity. `src/skill_interface/SKILL.md` ("offline-first and caching") states that with no `--commit` the result carries `branch_current_unknown: true`, and that a local snapshot proves only "a version observed in the past", not that the branch still points at it.

---

## 6.2 Why `commit_sha`, `root_tree_sha` and `tree_query_ref` must be separate

**Problem**: it is tempting to assume a tree's SHA and a commit's SHA are interchangeable. Measurement proves they are not.

**Decision evidence (real measurement)**:
- `docs/fusion/BASELINE.md` F0-D01 (high): for four upstream sources (03/04/05/06), `tree.json.sha` equals their own commit SHA and not the real root tree SHA — a systematic result of the same fetch method.
- `docs/implementation/F2_P1C_TREE_ECHO_EXPERIMENT.json`: requesting the Trees API with `commit_sha=7fd1a60b…` returns `sha=7fd1a60b…`; requesting with `root_tree_sha=b4eecafa…` returns `sha=b4eecafa…`. `echo_confirmed: true`.
- `docs/implementation/F2_P1C_COLLECTOR_ARCHITECTURE.md` §2: the only legitimate source of `root_tree_sha` is the Commit object's `commit.tree.sha`, never the Trees API response `sha`.

**Why**: when the ref is commit-ish, the GitHub Trees API **echoes the request identifier** in the response `sha` instead of the SHA of the tree it expanded. If downstream code treats that echo as tree identity or a snapshot fingerprint, it reaches wrong conclusions. Separating the three fields gives each a single source with no backfilling, so the error cannot propagate silently.

**Technical reason for the current implementation**: `build_snapshot()` requires all three fields to be passed explicitly and does no backfilling; the fixture `fake_gh.py` deliberately reproduces the "echo the request ref" behaviour, and that is exactly what the tests assert. This is the implementation-layer defence against F0-D01, not a guessed preference.

---

## 6.3 Why layer A is immutable and fixes use new versions, not overwrites

**Problem**: knowledge gets corrected. If authoritative records can be rewritten in place, historical conclusions vanish, the audit chain breaks, and "what did this conclusion used to be?" becomes unanswerable.

**Decision evidence**:
- `docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md` §3: layer A is made immutable by database triggers — `assets_no_update` / `assets_no_delete` both `RAISE(ABORT, 'A_LAYER_IMMUTABLE')`; tests actually run `UPDATE` and `DELETE` and both are blocked.
- `progress/DECISIONS.md` D-002: knowledge assets (`knowledge/`, `cache/`, `upstreams/`, etc.) are strictly isolated from source Git; artefacts stay local and are never pushed with code.

**Why**:
1. **History is preserved**. Old versions are audit evidence and must not be erased by newer conclusions.
2. **Fixes use a new version + isolated view + re-derivation**, never an overwrite of the authoritative asset: the new answer becomes a new versioned asset, layer B's pointer decides which one is current, and layer D documents are re-derived. The old version remains queryable in layer A.
3. **Not by good intentions**. Triggers rather than conventions mean even buggy caller code cannot destroy history.

**What is not done**: layer A is not deletable or updatable, and user input never determines an asset ID — `asset_id` is generated internally (`SL-A-` + first 32 hex of sha256, input includes `repository_id`), avoiding the measured P1B pitfall where same-named records across repositories collided on the primary key and were silently merged.

---

## 6.4 Why the current pointer is separated from historical assets

**Problem**: layer A retains every version, but "which one is valid today" must have a single authoritative answer; otherwise stale Verifications leak into current conclusions.

**Decision evidence**:
- `docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md` §4: layer B `current_view(repository_id, logical_identity)` points to the current asset version using compare-and-swap; a mismatched `pointer_version` yields `CONFLICT`; three pointer states — `ok` / `dangling_pointer` / no record — with dangling never reported as `NOT_FOUND`.
- `src/trust/policy.py`: `current_asset_ids()` is the sole source of "currently valid assets"; `resolve_verification_for_claim()` takes only the Verification in the current view, while historical adjudications go through a separate `list_historical_verifications()` channel.

**Why**: historical assets serve audit and traceability; the current pointer serves conclusions. Separating them means:
- a Claim's historical Verification, even if overturned by newer evidence, cannot "zombie" back into current queries;
- the pointer is CAS-protected so concurrent writes cannot overwrite one another;
- "record is broken" (dangling pointer) and "knowledge does not exist" (NOT_FOUND) no longer share a meaning; the former carries `last_known_good` for diagnosis.

**Technical reason for the current implementation**: `evidence_admission()` returns `admitted=False / insufficient_evidence` for non-current adjudications — the second enforcement of "history does not enter current conclusions" at the evidence-admission layer.

---

## 6.5 Why Facts are separated from Claims, Verification is tri-state, and locatability ≠ correctness

**Problem**: a fact observed in source code and the knowledge claim built on it are not the same thing. Storing them together lets "there is a Fact" be misread as "the claim is verified".

**Decision evidence**:
- `docs/implementation/F2_P2A_FACTS_ARCHITECTURE.md`: Facts are only mechanically recomputable observations (e.g. `file_path_observation`), read only from committed `repository_snapshot` assets; the extractor has no network import and no SQL in its source.
- `docs/implementation/F2_P2B_EC_ARCHITECTURE.md` §1–2: `claim_id` is determined by repository + fixed commit + claim type + normalised parameters + schema version and does not change with evidence; `verification_id` changes with evidence. `verification_status` is tri-state `supported / refuted / insufficient_evidence`; `review_status=approved` can only be produced by a human (`Claim.__post_init__` blocks AI self-approval).
- `src/trust/policy.py` `evidence_admission()` and `src/skill_interface/SKILL.md`: evidence completeness is `FULLY_LOCATABLE / PARTIALLY_LOCATABLE / UNRESOLVED_NO_INTEGRITY`.

**Why**:
1. **Separating observation from proposition** lets evidence be recomputed independently and claims adjudicated independently.
2. **Tri-state** avoids forced binary choices: with insufficient evidence, guess neither "yes" nor "no" — fall to `insufficient_evidence`.
3. **A locatable reference is not a correct conclusion**. `FULLY_LOCATABLE` only means the evidence chain is complete and checkable; the original `status` is retained. Partial or unresolved references **downgrade** the verdict to `insufficient_evidence`, never to `refuted`. Completeness measures "can the reference be traced back", not "is the proposition true".
4. **Five orthogonal states**: `claim_type`, `verification_status`, `review_status`, `knowledge_freshness` and `execution_status` are independent — execution status belongs to the runtime and does not enter knowledge adjudication.

---

## 6.6 Why missing evidence is not judged as non-existence

**Problem**: "not found" has two meanings: outside the covered scope (not collected), or genuinely absent within scope. Writing both as "does not exist" produces confident wrong conclusions.

**Decision evidence**:
- `README.md` / `src/skill_interface/SKILL.md`: `ROOT_ONLY` means only the repository root was enumerated and is never presented as `COMPLETE`; missing content is "not analysed", not "does not exist".
- `src/trust/policy.py` `refutation_soundness()`: an ABSENT refutation requires the refuting fact to declare `COMPLETE` coverage; a non-root path with unexpanded subtrees cannot refute; a "missing observation" with `object_type=unknown / blob_sha=null / mode=""` cannot form a definitive `refuted`.
- `docs/fusion/BASELINE.md` F0-D06: the upstream rule "cannot build a complete chain → FALSE_POSITIVE (judge false)" conflicts with SourceLore's "insufficient evidence → insufficient"; F2 adopts `insufficient`, keeping only the useful "must be locatable hop by hop" part.

**Why**: refutation needs a stronger coverage premise than support. An exact root-level missing path is decidable under `ROOT_ONLY`, but a subdirectory path is not — with subtrees unexpanded, a missing path may simply not have been collected. A real misjudgement occurred historically: `progress/AUDIT-2026-11-11.md` records one `refuted` for preact whose README was then a 227-byte stub (body not captured); the real README was 14884 bytes. Such misreads were downgraded to `insufficient_evidence`. This is a recorded lesson, not a hypothetical.

---

## 6.7 Why the Skill + CLI form, and why reuse and self-build are distinguished

**Problem**: capabilities must be delivered in a form an agent can call, but the platform does not provide everything.

**Decision evidence**: `docs/implementation/F2_P0_ADAPTER_DECISIONS.md` AD-1..AD-6, all based on P1–P6 measurements:

| Component | Reuse / self-build | Reason |
|---|---|---|
| Skill discovery & registration | **Reuse** filesystem discovery | Dropping `~/.agents/skills/<name>/SKILL.md` makes it discovered; removing it makes it disappear; hot reload, so a self-built registry is worse (AD-1) |
| Entry structure | **Reuse + comply with SL-CAP-0068** | Thin entry + on-demand loading of sub-files (AD-1) |
| Checkpoint storage & recovery coordination | **Self-build** | No platform cross-session state API; the 1246 `sessions` are replay logs — **replay provides context, not authoritative state** (AD-2) |
| Authorization token | **Self-build** | In-skill approval propagation is unverified; write operations require explicit `authorization_scope`, missing/out-of-scope means `DENIED`, never a downgraded empty result (AD-3) |
| Five result states | **Self-build** | No native platform enum: `SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN` (AD-4) |
| Model routing | **Reuse single adapter interface** | `dsh headless` failed with `MISSING_CREDENTIAL`, an environment blocker not a design flaw; no provider hard-coded (AD-5) |

**Why**: the governing principle is "do not disguise a self-built solution as a platform-native capability, and do not declare the project impossible because the platform lacks something". Among the five states, `TIMEOUT` must not be inferred as "not executed", and `UNKNOWN` must not default to `SUCCESS` or `FAILED`; `src/runtime/execution_result.py` further makes `UNKNOWN` non-terminal: when side effects may have occurred but the receipt is missing, only `UNKNOWN` is allowed and no automatic redo is permitted.

---

## 6.8 Why knowledge documents and `answer` cannot be replaced by database records

**Problem**: Fact / Claim / Verification records are machine assets, but users need directly readable project knowledge; and a natural-language `answer` wired to an LLM would reintroduce non-recomputable inference.

**Decision evidence**:
- `src/views/repo_derive_runner.py`: turns a one-off script into `sourcelore derive <rid>`, offline and network-free, producing five layer-D documents: `project-overview.md`, `file-structure.md`, `module-dependencies.md`, `claim-network.md`, `evidence-index.md`. All sources are registered authoritative assets (snapshot `tree_entries`, `claim_candidate`, `claim_verification.fact_ids`, `query --type code` results).
- `src/skill_interface/knowledge_answer.py`: iron rule — "no LLM: this module performs only deterministic retrieval and assembly"; read-only, zero network, no asset writes, content-first, with audit fields shown only when the user asks "why is this trustworthy?".

**Why**: record-level assets answer "what evidence supports this claim", while document-level assets answer "what is this project, how is it used, how is it structured" — the former cannot replace the latter, hence `derive`. Wiring `answer` to an LLM would violate the determinism discipline of D-006, so it is a deterministic mapping from intent to document sections: with no supporting source it says "not analysed / insufficient evidence" and never guesses functionality from a filename.

---

## 6.9 Known technical trade-offs

These are not "unfinished"; they are explicit choices of which side to stand on, with the other side's cost stated.

| Trade-off | Choice | Cost / boundary |
|---|---|---|
| Offline cache vs network freshness | Offline first; `--commit` hit on a complete snapshot means zero-request reuse | A local snapshot proves only "a version observed in the past", not that the branch still points at it; no `--commit` sets `branch_current_unknown`; use `--refresh` for a newer version (SKILL.md, "offline-first and caching") |
| Raw content persistence vs authorization | Bytes land in `blobs/`; five independent gates FETCH / PERSIST / DERIVE / PREVIEW / DISTRIBUTE | `distribution_allowed=false` is constant; preview allowance does not imply distribution allowance; gates B-1/B-2/B-3 remain open (`content_acquisition_policy.py`, F2_P5E report) |
| Static parsing vs runtime analysis | Static observation of symbols and imports via Python `ast` and JS/TS `tree-sitter` | Repository code is never executed; no call graph, runtime behaviour or test-pass evidence; a missing parser reports `PARSER_UNAVAILABLE` rather than falling back to regex (README, SKILL.md) |
| Simple vs large repositories | Tiered budgets, `ROOT_ONLY` to start | Subdirectories of large repositories are not systematically captured; coverage is limited; when the tree is `truncated=true`, collection falls back to level-by-level traversal and marks `PARTIAL` (`tree_collector.py`) |
| Parsing coverage vs collection cost | 256 KiB per blob, 2 MiB per batch, 32 candidate paths, 100 facts per file; request limit 8, reserve 5 | Over-limit returns `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT`; coverage is bounded by budget and never claimed complete (`content_budget.py`, `request_budget.py`) |
| Local use vs distribution | Internal preview only; knowledge DB written outside the repository | The DB is never inside the Git repo (`paths.guard_inside_project_db`); this project has no open-source licence (README / INSTALLATION) |

**Why these trade-offs**: each pair corresponds to a hard constraint — context window, GitHub quota, licensing and authorization, and never executing third-party code. The result is "state the boundary explicitly" rather than "claim completeness".

---

## 6.10 Why the pipeline is staged and recovery reconciles on `operation_id`

**Problem**: collection spans network, bytes, parsing, storage, adjudication and derivation; after an interruption at any stage, work must be resumable without duplicate writes or misjudged results.

**Decision evidence**:
- `src/skill_interface/cli.py`: `analyze --plan` (read-only inventory, no network, no asset writes), `--resume` (zero-network recovery inventory, continues from storage gaps), `--offline` (no requests at all), `--request-limit` (default 8), `--reserve-requests` (default 5). `--plan` / `--resume` used to be "declarative empty arguments"; D-60 wired them to real function bodies.
- `src/runtime/asset_checkpoint_coordinator.py`: the knowledge asset DB and the checkpoint DB are separate physical files with independent transaction boundaries — **no global ACID**; cross-DB ATTACH with WAL commits "looks atomic" but is not a guarantee, so it is not used. The anchor is `operation_id` in the knowledge DB's `operation_log`.
- Reconciliation states: `RECONCILED` (committed, checkpoint missing → fill checkpoint, do not rewrite assets), `RETRY_SAFE` (not committed and no definite external side effect → retry allowed), `NEEDS_HUMAN` (DB unreadable / contradictory → never auto-redo). Judgement is based only on persisted records, not model context.

**Why**: staging makes each step independently verifiable and independently budgeted; budget preflight (build request DAG → inventory local assets as `LOCAL_REUSE` → fetch authoritative headers → three-condition decision) prevents a "no network needed" run from being misjudged as `INSUFFICIENT_REMAINING`; `--plan` makes "look at the gap first" a zero-risk action; `operation_id` reconciliation converges two inconsistent DBs without fabricating a global transaction. The five result states (6.7) and three reconciliation states together guarantee "timeout does not mean not executed, UNKNOWN does not mean success".

**What is not done**: no claim of global ACID across the two DBs; no claim of exactly-once for GitHub requests (local idempotence covers local registration only). For step-by-step detail, real commands and status codes, see [Pipeline](PIPELINE.md).
