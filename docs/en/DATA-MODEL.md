# SourceLore Data Model

> This document details the **current implementation**: data structures, identity rules, index and version rules, and status enumerations. It is evidenced from `src/storage/`, `src/facts/`, `src/evidence_claims/`, `src/trust/`, `src/lifecycle/`, and `src/views/`. Commands, status codes, and enum values are kept verbatim from the source. Historical planning (e.g. the early D-layer "50 fields" phrasing) is kept separate from current behavior.

## 1. Core stance: three identities are not interchangeable

`src/storage/asset_models.py` states it plainly: **logical_identity ≠ content_hash ≠ asset_version**; none can substitute for another. `src/facts/models.py` likewise separates `fact_id` / `content_hash` / `snapshot_identity` / `asset_id`.

| Concept | Determined by | Changes when | Not |
|---|---|---|---|
| `logical_identity` | business subject name (repository-scoped) | subject semantics change | content hash |
| `content_hash` | payload only (sha256 of `canonical_json`) | any byte of the payload changes | logical identity; two different kinds of knowledge may share a payload |
| `asset_version` | increasing physical version under one logical identity | each adopted write, +1 | identity |
| `asset_id` | internally generated `SL-A-` + first 32 sha256 hex chars | identity/version/content any change | a user-supplied file path or name |
| `fact_id` | rule + parameters + snapshot identity | rule/parameters/snapshot identity change | observation time `observed_at` |
| `claim_id` | the proposition itself | proposition changes | evidence list |
| `verification_id` | evidence set + rule version | evidence or rule changes | timestamp |

### asset_id generation rule

`_asset_id_for()` in `src/storage/knowledge_store.py`:

```
raw   = f"{repository_id}\x00{logical_identity}\x00{asset_version}\x00{content_hash}"
asset_id = "SL-A-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
```

**`repository_id` must be included**: initially the ID used only `(logical_identity, version, hash)`, so same-name records across repositories produced the same ID, collided on the primary key, and silently merged two pieces of knowledge — a real defect recorded in `F2_P1B_STORAGE_ARCHITECTURE.md`. IDs are computed internally; user input is data only and never determines a file path or ID. ID validity: `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` (`validate_id`); path traversal, null bytes, and overlong values are rejected at the model layer.

A `captured_blob_content` asset stores only metadata; the bytes live at `<data_root>/blobs/<content_sha256>.bin`, read back and verified by `blob_content_store.get_bytes()`.

---

## 2. Data Structures

### 2.1 Databases and namespaces

| Database | File | Transaction boundary | Authority |
|---|---|---|---|
| Knowledge asset store | `knowledge.db` (logical) / `<data_root>/kb.db` (actual) | A/B/C single transaction | Knowledge authority |
| Checkpoint store | `cp.db` | Independent | Execution-state authority |
| Derived index | Same knowledge store (`index_rows` / `asset_fts`) | Augmented in the A/B transaction | Not authoritative, rebuildable |

`schema_version = 1` is stored in the `meta` table; a mismatch raises `RuntimeError` directly with no silent migration. When opened with `create=False`, `PRAGMA integrity_check` runs first; a non-ok result raises `CHECKPOINT_CORRUPT`. PRAGMA order: `busy_timeout=5000` → `synchronous=FULL` → `foreign_keys=ON` → `journal_mode=WAL` (with 12 idempotent retries).

### 2.2 Layer A `assets` (immutable authoritative history)

```sql
assets(
  asset_id          TEXT PRIMARY KEY,        -- internally generated
  asset_type        TEXT NOT NULL,
  logical_identity  TEXT NOT NULL,
  repository_id     TEXT NOT NULL,
  subject_id        TEXT,
  asset_version     INTEGER NOT NULL CHECK(asset_version >= 1),
  content_hash      TEXT NOT NULL,           -- determined by payload only
  payload_json      TEXT NOT NULL,           -- canonical_json (no spaces, sorted)
  commit_sha        TEXT,                    -- three fields are independent
  root_tree_sha     TEXT,
  tree_query_ref    TEXT,
  operation_id      TEXT,
  created_at        TEXT NOT NULL,
  UNIQUE(repository_id, logical_identity, asset_version)
)
CREATE TRIGGER assets_no_update BEFORE UPDATE ON assets
  BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;
CREATE TRIGGER assets_no_delete BEFORE DELETE ON assets
  BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;
```

Closed set of `asset_type` values (`ASSET_TYPES`): `repository_snapshot`, `capability_record`, `subject_record`, `evidence_record`, `claim_record`, `relationship_record`, `captured_blob_content`, `extracted_fact`, `claim_candidate`, `claim_verification`, `lifecycle_watch`, `ref_observation`, `freshness_assessment`, `revalidation_queue`, `revalidation_candidate`, `revalidation_run`, `revalidation_result`.

Sensitive fields are rejected by name (`FORBIDDEN_FIELDS`): `api_key`, `apikey`, `api-key`, `token`, `cookie`, `secret`, `password`, `passwd`, `credential`, `private_key`, `authorization`, `env`, `environ`, `envvars`, `access_token`, `refresh_token` — a hit raises `ModelError` before any write.

### 2.3 Layer B `current_view` (current pointer + CAS)

```sql
current_view(
  logical_identity TEXT NOT NULL,
  repository_id    TEXT NOT NULL,
  current_asset_id TEXT NOT NULL,
  pointer_version  INTEGER NOT NULL CHECK(pointer_version >= 1),
  last_known_good  TEXT,                     -- diagnostic only, never the current value
  updated_at       TEXT NOT NULL,
  PRIMARY KEY (repository_id, logical_identity)
)
```

The composite primary key includes `repository_id`: same-name `logical_identity` across repositories is **different knowledge** and must not share a pointer. Pointer advancement sets `pointer_version = old + 1` with CAS on `expected_version`; `expected_version=None` means a first publish (no existing B record).

### 2.4 Layer C `index_rows` + `asset_fts` (derived index)

```sql
index_rows(
  asset_id         TEXT PRIMARY KEY,
  asset_type       TEXT NOT NULL,
  logical_identity TEXT NOT NULL,
  repository_id    TEXT NOT NULL,
  subject_id       TEXT,
  commit_sha       TEXT,
  asset_version    INTEGER NOT NULL
)
-- indexes: repository_id / subject_id / asset_type / commit_sha / logical_identity
-- FTS5 (when available): asset_fts(asset_id UNINDEXED, logical_identity, asset_type,
--   payload_text, tokenize='unicode61 remove_diacritics 2')
```

`commit_sha` has a three-level fallback: `source_snapshot` → `payload["commit_sha"]` → `payload["source_snapshot"]["commit_sha"] / baseline_commit_sha / observed_commit_sha`. This fixes historical defect D-1 (`index_rows.commit_sha` was once entirely NULL): it does not copy `assets.commit_sha` directly. A `claim_verification` payload contains no commit, so during rebuild a `claim_id → commit` map is built first and then backfilled.

### 2.5 `repo_bindings` / `operation_log`

```sql
repo_bindings(
  binding_id    TEXT PRIMARY KEY,            -- SL-B- + first 32 sha256 hex chars
  subject_id    TEXT NOT NULL,
  repository_id TEXT NOT NULL,
  evidence_ref  TEXT NOT NULL,                -- required: no evidence, no binding
  created_at    TEXT NOT NULL,
  UNIQUE(subject_id, repository_id, evidence_ref)
)
operation_log(
  operation_id     TEXT PRIMARY KEY,
  kind             TEXT NOT NULL,
  logical_identity TEXT,
  asset_id         TEXT,
  pointer_version  INTEGER,
  result_hash      TEXT,                      -- must equal checkpoint result_digest
  committed_at     TEXT NOT NULL
)
```

`bind_repo()` without `evidence_ref` → `PERMISSION_DENIED`; `same_subject_across_repos()` lists relations without merging identities. `operation_log` is the cross-store reconciliation anchor: one operation_id appears only once (`assert_no_version_double_advance`).

### 2.6 Knowledge-model data structures

| Structure (source) | Key fields | Identity / hash rule |
|---|---|---|
| `SourceSnapshot` (`asset_models.py`) | `commit_sha` / `root_tree_sha` / `tree_query_ref` | first two must be 40 lowercase hex characters; `tree_query_ref` ≤256 chars; the three fields are not interchangeable |
| `AssetDraft` / `Asset` | type, logical identity, repository, version, payload, source_snapshot | `content_hash = content_hash_of(payload)`; `verify_integrity()` checks on read |
| `FactObservation` (`facts/models.py`) | `fact_type` (fixed `file_path_observation`), `observation`, `repository_id`, `snapshot_asset_id`, `commit_sha`, `rule_id`(/version), `normalized_parameters`, `item_key`, `observed_value`, `completeness_status`, `evidence_refs`, `input_digest`, `content_hash`, `extractor_version`, `unknown_reason`, `observed_at`, `manifest_version` | `SL-FACT-` + 40 hex; `observed_at` participates in neither identity nor content_hash |
| `Claim` (`ec_models.py`) | `claim_id`, `claim_type`, `repository_id`, `commit_sha`, `normalized_path`, `expected_exists`, `claim_scope`, `claim_origin`, `claim_schema_version`, `review_status`, `human_authored`, `knowledge_freshness`, `normalized_parameters`, `created_at` | `SL-CLAIM-` + 40 hex; `identity_payload()` excludes evidence |
| `Verification` | `verification_id`, `claim_id`, `status`, `reason_code`, `fact_ids`, `fact_content_hashes`, `rule_version`, `normalized_verification_params`, `evidence_refs`, `conflict_detected`, `local_coverage_only`, `supporting_fact_ids`, `counter_fact_ids`, `verified_at`, `evidence_level` | `SL-VERIF-` + 40 hex; sorted evidence set + rule + parameters |
| `Evidence refs` | `source_snapshot` (with the three fields + coverage status) / `tree_entry` (path, object_type, mode, blob_sha) | structured objects, not natural language |

Path normalization (`normalize_path`, same rules in Facts and EC): non-empty, non-absolute, unified `/`, rejects `..`, empty segments, backslashes, null bytes; **no case folding** (Git paths are case-sensitive).

---

## 3. Index and Version Rules

### 3.1 Index rebuild

`rebuild_index()` (`src/storage/index_store.py`):

1. Compute the A/B fingerprint `_ab_fingerprint()`.
2. `BEGIN IMMEDIATE` → `DELETE FROM index_rows` / `asset_fts` → reload from the full `assets` table.
3. Apply `TRUST.identity_check()` admission to all assets except `repository_snapshot`; failures go into `quarantined` (first 50 returned), are excluded from C, and leave A untouched.
4. `COMMIT` → recompute the fingerprint; return `a_b_unchanged` (true only if equal), `indexed`, `source_assets`, `quarantined_count`, `fts5`.

If the `index_rows` table does not exist, `query()` returns `INDEX_MISSING`, **never an empty list** (I3: missing index ≠ missing knowledge). Every result is decorated by `_decorate()` with `asset_id` / `asset_version` / `is_current` / `authority` ("layer A assets table; this result is not an authoritative fact, re-check against A"). Full-text search uses FTS5 when available, falls back to LIKE otherwise, and additionally backfills with LIKE (phrase queries such as `"LI-1"` are quoted to avoid being parsed as operators).

### 3.2 Versioning and idempotency

- **W-1..W-5** (single `BEGIN IMMEDIATE`): validate draft → CAS-check `expected_version` → INSERT assets + advance current_view + postcondition (before commit) + layer C augmentation + operation_log → COMMIT; any exception → ROLLBACK.
- **Idempotency**: an already-committed `operation_id` → `idempotent: True`, no rewrite; same-version same-content → idempotent; same-version different-content → `CONFLICT`.
- **CAS**: `expected_version` must equal the current `pointer_version`, otherwise `CONFLICT`; a first publish requires no existing B record.
- **postcondition before COMMIT**: a raising postcondition rolls back all three layers (`test_failing_postcondition_rolls_back_everything`).

### 3.3 Pointer states

| State | Meaning | Return |
|---|---|---|
| `ok` | points to an existing asset | `ok=True` + `current_asset_id` / `pointer_version` |
| `dangling_pointer` | points to a missing asset | `ok=False`, `error=CHECKPOINT_CORRUPT`, `state=dangling_pointer`, with `last_known_good` for diagnosis only |
| no record | never published | `error=NOT_FOUND` |

A dangling pointer must **never** be reported as `NOT_FOUND` (the record is broken vs. the knowledge does not exist).

### 3.4 Cross-store reconciliation states

| State | Condition | Action |
|---|---|---|
| `RECONCILED` | operation committed, checkpoint missing or has intent but no receipt | Backfill checkpoint, do not rewrite assets |
| `RETRY_SAFE` | operation not committed and no definite external side effect | Retry by idempotency rules |
| `NEEDS_HUMAN` | store unreadable / digest contradiction / corruption | Never auto-redo; escalate to a human |

---

## 4. Status Enumeration Tables (verbatim from source)

### 4.1 Commit authenticity — five codes (`src/trust/policy.py`)

| Code | Meaning |
|---|---|
| `COMMIT_UNKNOWN` | not 40 hex characters |
| `COMMIT_FORMAT_VALID` | valid format but not bound to this repository's snapshot, or a known placeholder (`aaaa…` / `0000…` / `ffff…`) |
| `COMMIT_BOUND_TO_REPOSITORY` | commit hit in a `repository_snapshot` of this repository (no payload) |
| `COMMIT_SNAPSHOT_VERIFIED` | hit with a snapshot payload for the same commit |
| `COMMIT_IDENTITY_CONFLICT` | multiple payloads for the same commit with differing `root_tree_sha` |

Only the last two (accepted by `is_authenticated_commit()`) may serve as a current trusted version identity.

### 4.2 Fact observation states and UNKNOWN reasons (`src/facts/models.py`)

| Observation state | Meaning |
|---|---|
| `OBSERVED_PRESENT` | actually present in the snapshot |
| `OBSERVED_ABSENT_IN_COVERED_SCOPE` | actually absent within fully covered scope |
| `UNKNOWN` | indeterminate; must carry `unknown_reason` |

`UNKNOWN_REASONS`: `MANIFEST_ABSENT`, `PARTIAL_SNAPSHOT`, `SCOPE_NOT_COVERING`, `TREE_TRUNCATED`, `ENTRY_REQUIRED_MISSING`, `BLOB_VERIFY_FAILED`, `ASSET_INTEGRITY_FAILED`, `ASSET_NOT_FOUND`, `MALFORMED_MANIFEST`, `DUPLICATE_ENTRY`.

Tree object types: `blob` / `tree` / `commit` / `unknown`; mode semantics: `120000` (symlink), `160000` (submodule), `040000` (directory).

### 4.3 Evidence-integrity levels (`src/trust/policy.py`)

| Code | Meaning | Admission |
|---|---|---|
| `FULLY_LOCATABLE` | fully locatable | raw verdict admitted |
| `PARTIALLY_LOCATABLE` | partially locatable | downgraded to `insufficient_evidence`, `EVIDENCE_FIELD_MISSING` |
| `UNRESOLVED_NO_INTEGRITY` | unlocatable, no integrity | downgraded to `insufficient_evidence`, `FACT_NOT_FOUND` |
| `NO_EVIDENCE` | no evidence | downgraded to `insufficient_evidence`, `PARTIAL_EVIDENCE_INSUFFICIENT` |

### 4.4 Three-state adjudication (`src/evidence_claims/ec_models.py`)

`supported` / `refuted` / `insufficient_evidence`. Constraints: `insufficient_evidence` must carry a reason_code from the closed `INSUFFICIENT_REASONS` table; `supported` must have `supporting_fact_ids`; a non-insufficient verdict must not carry a reason_code.

`INSUFFICIENT_REASONS`: `NO_FACTS`, `FACT_NOT_FOUND`, `FACT_INTEGRITY_FAILED`, `SNAPSHOT_NOT_FOUND`, `SNAPSHOT_INTEGRITY_FAILED`, `REPOSITORY_MISMATCH`, `COMMIT_MISMATCH`, `PATH_MISMATCH`, `SCOPE_NOT_COVERING`, `PARTIAL_EVIDENCE_INSUFFICIENT`, `PARTIAL_CANNOT_REFUTE`, `EVIDENCE_FIELD_MISSING`, `CONFLICTING_EVIDENCE`, `UNSUPPORTED_CLAIM_TYPE`, `FACT_IS_UNKNOWN`, `STORAGE_ERROR`.

Supported claim types: `repository_path_exists`, `readme_heading_exists`, `manifest_dependency_declared`, `manifest_field_present`, `source_symbol_declared`, `source_import_declared`, `source_local_module_resolved`, `source_export_declared`, `static_module_relation_resolved`, `module_config_paths_declared`, `tsconfig_project_declared`, `tsconfig_project_reference_declared`, `tsconfig_file_membership_candidate`; `claim_schema_version = claim-schema/1`.

Review states: `pending_review` / `approved` / `rejected_review`; `approved` requires `human_authored=True`.

### 4.5 Tree coverage — three values (`src/trust/tree_scope.py`)

`COMPLETE` (`DEEP_WALK_COMPLETE` or `ROOT_TREE_ENUMERATED_NO_SUBTREES`) / `ROOT_ONLY` (`ROOT_ONLY_SUBTREES_UNENUMERATED`, root-level enumeration with unexpanded subtrees) / `PARTIAL` (`TRUNCATED` or `UNKNOWN_COVERAGE`). Only `COMPLETE` means the whole tree was seen; `ROOT_ONLY` can still decide exact root-level paths but cannot refute paths inside subdirectories.

### 4.6 Freshness — four values (`src/lifecycle/lc_models.py`)

`NOT_APPLICABLE_TO_PINNED`, `VERSION_ALIGNED`, `POSSIBLY_STALE`, `UNKNOWN`. Constraints: `VERSION_ALIGNED` requires a trusted observed commit with `observed == baseline`; `POSSIBLY_STALE` requires a reason_code and a trusted newer commit, and `observed == baseline` cannot be judged stale.

### 4.7 View five status axes (`src/views/knowledge_view_assembler.py`)

| Axis | Source | Values |
|---|---|---|
| `verification_status` | EC | `supported` / `refuted` / `insufficient_evidence` |
| `freshness_state` | Lifecycle | `NOT_APPLICABLE_TO_PINNED` / `VERSION_ALIGNED` / `POSSIBLY_STALE` / `UNKNOWN` |
| `review_status` | Claim | `pending_review` / `approved` (human only) |
| `execution_status` | Runtime | `SUCCESS` / `FAILED` / `TIMEOUT` / `CANCELLED` / `UNKNOWN` |
| provenance + authorization | observation / execution records | `evidence_source_level` / `execution_source_level` / `snapshot_source_level` / `authorization_class`, judged separately |

The view has **no** `is_valid` / `overall_status` / `combined_status` / `final_verdict` (explicitly forbidden by tests). `view_schema_version = knowledge-view/1`, `projection_rule_version = projection/1`. Diagnostic codes include `VIEW_INTEGRITY_FAILED`, `DANGLING_REFERENCE`, `SOURCE_MISSING`, `VERSION_MISMATCH`, `CLAIM_NOT_FOUND`, `VERIFICATION_NOT_FOUND`, `CLAIM_VERIFICATION_MISMATCH`, `REPOSITORY_MISMATCH`, `COMMIT_MISMATCH`, `EVIDENCE_CORRUPT`, `CURRENT_APPLICABILITY_UNKNOWN`, `PARTIAL_COVERAGE_ONLY`.

### 4.8 Source-analysis states (`src/source_analysis/`)

| Category | Values |
|---|---|
| Extraction status | `EXTRACTED`, `PARSE_FAILED`, `PARSER_UNAVAILABLE`, `UNSUPPORTED_ENCODING`, `BINARY_CONTENT` |
| tree-sitter parse | `PARSE_COMPLETE`, `PARSE_WITH_ERRORS`, `PARSE_UNSUPPORTED_SYNTAX`, `SOURCE_INCOMPLETE`, `CONTENT_INTEGRITY_FAILED` |
| Symbol kinds | `module`, `class`, `function`, `async_function`, `method`, `async_method`, `nested_function` |
| Local module resolution | `LOCAL_MODULE_RESOLVED`, `EXTERNAL_OR_UNRESOLVED`, `AMBIGUOUS_CANDIDATES`, `INSUFFICIENT_TREE_COVERAGE`, `UNSUPPORTED_IMPORT_FORM` |
| Specifier status | `LITERAL_MODULE_SPECIFIER`, `DYNAMIC_MODULE_SPECIFIER` |
| Import kinds | `default_import`, `named_import`, `namespace_import`, `side_effect_import`, `require_literal_call`, `dynamic_import` |
| Export kinds | `named_export`, `default_export`, `export_declaration`, `export_list`, `re_export`, `export_all` |

`require("x")` is recorded as `LITERAL_REQUIRE_CALL_OBSERVED` (a call observation), not an ESM declaration; multiple simultaneously available conditional exports yield `MULTIPLE_CONDITIONS_AVAILABLE` (no arbitrary pick), and a missing subpath yields `SUBPATH_NOT_IN_EXPORTS`. tree-sitter grammar versions are pinned: core `0.26.0`, javascript `0.25.0`, typescript `0.23.2`, loaded only from the project `.venv`; a missing grammar yields `PARSER_UNAVAILABLE`, never an automatic download or regex-guess fallback.

### 4.9 Request-budget states (`src/collector/request_budget.py`)

| Category | Values |
|---|---|
| Budget state | `BUDGET_OK`, `REQUEST_BUDGET_INSUFFICIENT`, `BUDGET_EXHAUSTED`, `BUDGET_RATE_LIMITED` |
| Rate-limit kind | `PRIMARY`, `SECONDARY`, `UNKNOWN` |
| Plan-item result | `NOT_RUN`, `SUCCESS`, `CACHE_HIT`, `RATE_LIMITED`, `HTTP_ERROR`, `SKIPPED_BUDGET_INSUFFICIENT` |

`can_spend()` uses three gates: the execution has not exceeded the local cap; real remaining ≥ cost + reserve; not currently rate-limited. Defaults: `DEFAULT_REQUEST_LIMIT=8`, `DEFAULT_RESERVE=5`. No authoritative headers → `REQUEST_BUDGET_INSUFFICIENT` (rather send nothing). Local records are not the network's real quota (anonymous quota is per source IP and other processes consume it); remaining is inferred only from headers.

### 4.10 Content-acquisition authorization (`src/collector/content_acquisition_policy.py`)

| Category | Values |
|---|---|
| Preflight authorization | `ACQUISITION_ALLOWED`, `METADATA_ONLY`, `ACQUISITION_BLOCKED`, `AUTHORIZATION_UNKNOWN` |
| Five operations | `fetch`, `persist_bytes`, `derive_facts`, `internal_preview`, `external_distribution` |
| Decision | `ALLOW`, `DENY`, `UNKNOWN` |
| Evidence kinds | `PROJECT_OWNED_WORK`, `ORIGINAL_TEST_FIXTURE`, `LICENSE_OBSERVED_AND_APPLICABLE`, `USER_EXPLICIT_GRANT` |
| Verification status | `VERIFIED`, `UNVERIFIED` |

`external_distribution` is always `DENY` (`DISTRIBUTION_GATE_OPEN_BLOCKED`) unless the gate is independently opened. Public visibility ≠ permission to copy permanently; `copy_permitted` affects redistribution only, not internal acquisition.

### 4.11 Answer intents (`src/skill_interface/knowledge_answer.py`)

`introduce` (default fallback) / `usage` / `architecture` / `code` / `evidence` / `completeness`. `audit` is attached only for `evidence` / `completeness`, and is `null` otherwise. Fixed output fields: `network_requests=0`, `wrote_assets=0`, `distribution_allowed=false`, `freeze_state=FROZEN_INTERNAL_RESTRICTED`.

---

## 5. Interaction Rules for Identity, Evidence, and Current View

1. **Current view is the only source**: `current_asset_ids()` JOINs `current_view` with `assets`, returning only identities adopted by the current pointer that actually exist and match. Historical verdicts never mix into current conclusions.
2. **Evidence admission**: a raw verdict is not the same as a currently admissible finding; non-current verdicts are not admitted; with an incomplete evidence chain, supported/refuted are both downgraded to `insufficient_evidence`.
3. **Refutation constraints**: paths must match exactly; an absent-path refutation relies on a `COMPLETE` coverage declaration; a non-root-level path under unexpanded subtrees cannot refute.
4. **Not collected ≠ does not exist**: `UNKNOWN` is never faked with empty lists / False / NOT_FOUND; `OBSERVED_ABSENT_IN_COVERED_SCOPE` holds only under COMPLETE coverage.
5. **Cross-repository anchoring**: `repository_id` is the repository anchor, `subject_id` is the knowledge-subject identity, `commit_sha` is the version, `workspace_id` is a run scope and not a Subject identity; bindings must carry `evidence_ref`.
6. **Immutable protection**: layer A is append-only with UPDATE/DELETE blocked by triggers; content_hash is determined by payload only and is not logical identity; asset_id includes repository_id to avoid primary-key collisions.
