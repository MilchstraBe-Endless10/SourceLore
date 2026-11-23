# SourceLore 数据模型

> 本文详述**当前实现**的数据结构、身份规则、索引与版本规则、状态枚举表。依据 `src/storage/`、`src/facts/`、`src/evidence_claims/`、`src/trust/`、`src/lifecycle/`、`src/views/` 源码取证；命令、状态码、枚举值保持源码原文。历史规划（如 D 层早期「50 字段」说法）与当前实现分开陈述。

## 1. 核心立场：三种身份不可互换

`src/storage/asset_models.py` 明确：**逻辑身份（logical_identity）≠ 内容哈希（content_hash）≠ 物理版本（asset_version）**，三者任一都不能替代另一个。`src/facts/models.py` 同样把 `fact_id` / `content_hash` / `snapshot_identity` / `asset_id` 四者分开。

| 概念 | 由什么决定 | 变化条件 | 不是 |
|---|---|---|---|
| `logical_identity` | 业务主体名（按仓库作用域） | 主体语义变化 | 内容哈希 |
| `content_hash` | 仅 payload（`canonical_json` 后 sha256） | payload 任一字节变 | 逻辑身份；两条不同知识可有相同 payload |
| `asset_version` | 同一逻辑身份下的递增物理版本 | 每次被采纳的写入 +1 | 身份 |
| `asset_id` | 内部生成的 `SL-A-` + sha256 前 32 位 | 身份/版本/内容任一变 | 用户输入的文件路径或名称 |
| `fact_id` | 规则+参数+快照身份 | 规则/参数/快照身份变 | 观测时间 `observed_at` |
| `claim_id` | 命题本身 | 命题变 | 证据列表 |
| `verification_id` | 证据集合 + 规则版本 | 证据或规则变 | 时间戳 |

### asset_id 生成规则

`_asset_id_for()`（`src/storage/knowledge_store.py`）：

```
raw   = f"{repository_id}\x00{logical_identity}\x00{asset_version}\x00{content_hash}"
asset_id = "SL-A-" + sha256(raw).hexdigest()[:32]
```

**必须包含 `repository_id`**：最初 ID 只用 `(logical_identity, version, hash)`，跨仓库同名记录算出同一个 ID 撞主键、两条知识被静默合并——这是设计记录 `F2_P1B_STORAGE_ARCHITECTURE.md` 记载的实测缺陷。ID 由内部计算，用户输入只作数据，永远不参与决定文件路径或 ID。ID 合法性 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`（`validate_id`），路径穿越、空字节、超长在模型层拒绝。

`captured_blob_content` 资产只存元数据；字节本身位于 `<data_root>/blobs/<content_sha256>.bin`，由 `blob_content_store.get_bytes()` 校验读回。

---

## 2. 数据结构

### 2.1 库与命名空间

| 库 | 文件 | 事务边界 | 权威性 |
|---|---|---|---|
| 知识资产库 | `knowledge.db`（逻辑名）/ `<data_root>/kb.db`（实际） | A/B/C 单事务 | 知识权威 |
| Checkpoint 库 | `cp.db` | 独立 | 执行状态权威 |
| 派生索引 | 同在知识库（`index_rows` / `asset_fts`） | 与 A/B 同事务增补 | 非权威，可重建 |

`schema_version = 1` 存于 `meta` 表；不符直接 `RuntimeError`，不静默迁移。打开 `create=False` 时先跑 `PRAGMA integrity_check`，非 ok 抛 `CHECKPOINT_CORRUPT`。PRAGMA 顺序：`busy_timeout=5000` → `synchronous=FULL` → `foreign_keys=ON` → `journal_mode=WAL`（带 12 次幂等重试）。

### 2.2 A 层 `assets`（不可变权威历史）

```sql
assets(
  asset_id          TEXT PRIMARY KEY,        -- 内部生成
  asset_type        TEXT NOT NULL,
  logical_identity  TEXT NOT NULL,
  repository_id     TEXT NOT NULL,
  subject_id        TEXT,
  asset_version     INTEGER NOT NULL CHECK(asset_version >= 1),
  content_hash      TEXT NOT NULL,           -- 只由 payload 决定
  payload_json      TEXT NOT NULL,           -- canonical_json（无空格、排序）
  commit_sha        TEXT,                    -- 三字段独立
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

`asset_type` 封闭集合（`ASSET_TYPES`）：`repository_snapshot`、`capability_record`、`subject_record`、`evidence_record`、`claim_record`、`relationship_record`、`captured_blob_content`、`extracted_fact`、`claim_candidate`、`claim_verification`、`lifecycle_watch`、`ref_observation`、`freshness_assessment`、`revalidation_queue`、`revalidation_candidate`、`revalidation_run`、`revalidation_result`。

敏感字段按名硬拒（`FORBIDDEN_FIELDS`）：`api_key`、`apikey`、`api-key`、`token`、`cookie`、`secret`、`password`、`passwd`、`credential`、`private_key`、`authorization`、`env`、`environ`、`envvars`、`access_token`、`refresh_token`——命中即 `ModelError`，在写库之前拒绝。

### 2.3 B 层 `current_view`（当前指针 + CAS）

```sql
current_view(
  logical_identity TEXT NOT NULL,
  repository_id    TEXT NOT NULL,
  current_asset_id TEXT NOT NULL,
  pointer_version  INTEGER NOT NULL CHECK(pointer_version >= 1),
  last_known_good  TEXT,                     -- 仅供诊断，不得当当前值
  updated_at       TEXT NOT NULL,
  PRIMARY KEY (repository_id, logical_identity)
)
```

复合主键带 `repository_id`：跨仓库同名 `logical_identity` 是**不同知识**，不得共享指针。指针推进 `pointer_version = 旧值 + 1`，以 `expected_version` 做 CAS；`expected_version=None` 表示首次发布（B 中不得已存在）。

### 2.4 C 层 `index_rows` + `asset_fts`（派生索引）

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
-- 索引：repository_id / subject_id / asset_type / commit_sha / logical_identity
-- FTS5（可用时）：asset_fts(asset_id UNINDEXED, logical_identity, asset_type,
--   payload_text, tokenize='unicode61 remove_diacritics 2')
```

`commit_sha` 的三级回退：`source_snapshot` → `payload["commit_sha"]` → `payload["source_snapshot"]["commit_sha"] / baseline_commit_sha / observed_commit_sha`。修复历史缺陷 D-1（`index_rows.commit_sha` 曾整列 NULL）：不直接照抄 `assets.commit_sha`。`claim_verification` 的 payload 不含 commit，重建时先建 `claim_id → commit` 映射再回填。

### 2.5 `repo_bindings` / `operation_log`

```sql
repo_bindings(
  binding_id    TEXT PRIMARY KEY,            -- SL-B- + sha256 前 32 位
  subject_id    TEXT NOT NULL,
  repository_id TEXT NOT NULL,
  evidence_ref  TEXT NOT NULL,                -- 必填，无证据拒绝
  created_at    TEXT NOT NULL,
  UNIQUE(subject_id, repository_id, evidence_ref)
)
operation_log(
  operation_id     TEXT PRIMARY KEY,
  kind             TEXT NOT NULL,
  logical_identity TEXT,
  asset_id         TEXT,
  pointer_version  INTEGER,
  result_hash      TEXT,                      -- 与 checkpoint result_digest 同值
  committed_at     TEXT NOT NULL
)
```

`bind_repo()` 无 `evidence_ref` → `PERMISSION_DENIED`；`same_subject_across_repos()` 只列关系不合并身份。`operation_log` 是跨库对账锚点：同一 operation_id 只出现一次（`assert_no_version_double_advance`）。

### 2.6 知识模型数据结构

| 结构（源码） | 关键字段 | 身份 / 哈希规则 |
|---|---|---|
| `SourceSnapshot`（`asset_models.py`） | `commit_sha` / `root_tree_sha` / `tree_query_ref` | 前两者必须 40 位小写十六进制；`tree_query_ref` ≤256 字符；三字段不可互换 |
| `AssetDraft` / `Asset` | 类型、逻辑身份、仓库、版本、payload、source_snapshot | `content_hash = content_hash_of(payload)`；`verify_integrity()` 读取时校验 |
| `FactObservation`（`facts/models.py`） | `fact_type`（固定 `file_path_observation`）、`observation`、`repository_id`、`snapshot_asset_id`、`commit_sha`、`rule_id`（/version）、`normalized_parameters`、`item_key`、`observed_value`、`completeness_status`、`evidence_refs`、`input_digest`、`content_hash`、`extractor_version`、`unknown_reason`、`observed_at`、`manifest_version` | `SL-FACT-` + 40 hex；`observed_at` 不参与身份与 content_hash |
| `Claim`（`ec_models.py`） | `claim_id`、`claim_type`、`repository_id`、`commit_sha`、`normalized_path`、`expected_exists`、`claim_scope`、`claim_origin`、`claim_schema_version`、`review_status`、`human_authored`、`knowledge_freshness`、`normalized_parameters`、`created_at` | `SL-CLAIM-` + 40 hex；`identity_payload()` 不含证据 |
| `Verification` | `verification_id`、`claim_id`、`status`、`reason_code`、`fact_ids`、`fact_content_hashes`、`rule_version`、`normalized_verification_params`、`evidence_refs`、`conflict_detected`、`local_coverage_only`、`supporting_fact_ids`、`counter_fact_ids`、`verified_at`、`evidence_level` | `SL-VERIF-` + 40 hex；排序后的证据集合 + 规则 + 参数 |
| `Evidence refs` | `source_snapshot`（含三字段 + 覆盖状态）/ `tree_entry`（path、object_type、mode、blob_sha） | 结构化对象，不是自然语言 |

`path` 规范化（`normalize_path`，Facts 与 EC 同口径）：非空、非绝对、统一 `/`、拒绝 `..`、空段、反斜杠、空字节；**不做大小写折叠**（Git 路径大小写敏感）。

---

## 3. 索引与版本规则

### 3.1 索引重建

`rebuild_index()`（`src/storage/index_store.py`）：

1. 计算 A/B 指纹 `_ab_fingerprint()`。
2. `BEGIN IMMEDIATE` → `DELETE FROM index_rows` / `asset_fts` → 从 `assets` 全表重灌。
3. 对非 `repository_snapshot` 资产用 `TRUST.identity_check()` 准入；失败进 `quarantined`（最多返回前 50 条），不进 C 层，A 层原封不动。
4. `COMMIT` → 再算指纹，返回 `a_b_unchanged`（前后相等才为 true）、`indexed`、`source_assets`、`quarantined_count`、`fts5`。

`query()` 若 `index_rows` 表不存在 → `INDEX_MISSING`，**不返回空列表**（I3：索引没有 ≠ 知识不存在）。每条结果经 `_decorate()` 补 `asset_id` / `asset_version` / `is_current` / `authority`（「A 层 assets 表；本结果不是事实权威，需回查」）。全文检索：FTS5 可用才用、不可用退化 LIKE，并额外用 LIKE 兜底（短语查询如 `"LI-1"` 加双引号避免被当运算符）。

### 3.2 版本与幂等

- **W-1..W-5**（单 `BEGIN IMMEDIATE`）：校验草稿 → CAS 校验 `expected_version` → INSERT assets + 推进 current_view + postcondition（提交前）+ C 层增补 + operation_log → COMMIT；异常 ROLLBACK。
- **幂等**：同一 `operation_id` 已提交 → 返回 `idempotent: True`，不重复写；同版本同内容 → 幂等；同版本不同内容 → `CONFLICT`。
- **CAS**：`expected_version` 必须等于当前 `pointer_version`，否则 `CONFLICT`；首次发布要求 B 中无记录。
- **postcondition 在 COMMIT 前**：抛异常三层一起回滚（测试 `test_failing_postcondition_rolls_back_everything`）。

### 3.3 指针状态

| 状态 | 含义 | 返回 |
|---|---|---|
| `ok` | 指向存产的资产 | `ok=True` + `current_asset_id` / `pointer_version` |
| `dangling_pointer` | 指向不存在的资产 | `ok=False`、`error=CHECKPOINT_CORRUPT`、`state=dangling_pointer`，带 `last_known_good` 仅供诊断 |
| 无记录 | 从未发布 | `error=NOT_FOUND` |

`dangling_pointer` **绝不能**报成 `NOT_FOUND`（前者记录坏了，后者知识不存在）。

### 3.4 跨仓库对账状态

| 状态 | 条件 | 动作 |
|---|---|---|
| `RECONCILED` | operation 已提交、checkpoint 缺失或只有意图无回执 | 补写 checkpoint，不重复写资产 |
| `RETRY_SAFE` | operation 未提交且无确定外部副作用 | 按幂等规则重试 |
| `NEEDS_HUMAN` | 库读不出 / 摘要矛盾 / 损坏 | 绝不自动重做，交人工 |

---

## 4. 状态枚举表（保持源码原文）

### 4.1 Commit 真实性五码（`src/trust/policy.py`）

| 码 | 含义 |
|---|---|
| `COMMIT_UNKNOWN` | 非 40 位十六进制 |
| `COMMIT_FORMAT_VALID` | 格式合法但未绑定本仓库快照，或已知占位（`aaaa…` / `0000…` / `ffff…`） |
| `COMMIT_BOUND_TO_REPOSITORY` | 命中仓库 `repository_snapshot` 的 commit（无 payload） |
| `COMMIT_SNAPSHOT_VERIFIED` | 命中且有同 commit 快照 payload |
| `COMMIT_IDENTITY_CONFLICT` | 同 commit 多个 payload 的 `root_tree_sha` 不一致 |

仅后两码（经 `is_authenticated_commit()`）可作为当前可信版本身份。

### 4.2 Fact 观察态与 UNKNOWN 原因（`src/facts/models.py`）

| 观察态 | 含义 |
|---|---|
| `OBSERVED_PRESENT` | 快照中确实存在 |
| `OBSERVED_ABSENT_IN_COVERED_SCOPE` | 在已完整覆盖范围内确实不存在 |
| `UNKNOWN` | 无法确定，必须带 `unknown_reason` |

`UNKNOWN_REASONS`：`MANIFEST_ABSENT`、`PARTIAL_SNAPSHOT`、`SCOPE_NOT_COVERING`、`TREE_TRUNCATED`、`ENTRY_REQUIRED_MISSING`、`BLOB_VERIFY_FAILED`、`ASSET_INTEGRITY_FAILED`、`ASSET_NOT_FOUND`、`MALFORMED_MANIFEST`、`DUPLICATE_ENTRY`。

Tree 对象类型：`blob` / `tree` / `commit` / `unknown`；mode 语义：`120000`（symlink）、`160000`（submodule）、`040000`（目录）。

### 4.3 证据完整性四级（`src/trust/policy.py`）

| 码 | 含义 | 准入 |
|---|---|---|
| `FULLY_LOCATABLE` | 全部可定位 | 采信原始 verdict |
| `PARTIALLY_LOCATABLE` | 部分可定位 | 降级 `insufficient_evidence`，`EVIDENCE_FIELD_MISSING` |
| `UNRESOLVED_NO_INTEGRITY` | 不可定位、无完整性 | 降级 `insufficient_evidence`，`FACT_NOT_FOUND` |
| `NO_EVIDENCE` | 无证据 | 降级 `insufficient_evidence`，`PARTIAL_EVIDENCE_INSUFFICIENT` |

### 4.4 裁决三态（`src/evidence_claims/ec_models.py`）

`supported` / `refuted` / `insufficient_evidence`。约束：`insufficient_evidence` 必须带封闭 `INSUFFICIENT_REASONS` 中的 reason_code；`supported` 必须有 `supporting_fact_ids`；非 insufficient 不得带 reason_code。

`INSUFFICIENT_REASONS`：`NO_FACTS`、`FACT_NOT_FOUND`、`FACT_INTEGRITY_FAILED`、`SNAPSHOT_NOT_FOUND`、`SNAPSHOT_INTEGRITY_FAILED`、`REPOSITORY_MISMATCH`、`COMMIT_MISMATCH`、`PATH_MISMATCH`、`SCOPE_NOT_COVERING`、`PARTIAL_EVIDENCE_INSUFFICIENT`、`PARTIAL_CANNOT_REFUTE`、`EVIDENCE_FIELD_MISSING`、`CONFLICTING_EVIDENCE`、`UNSUPPORTED_CLAIM_TYPE`、`FACT_IS_UNKNOWN`、`STORAGE_ERROR`。

支持的 claim 类型：`repository_path_exists`、`readme_heading_exists`、`manifest_dependency_declared`、`manifest_field_present`、`source_symbol_declared`、`source_import_declared`、`source_local_module_resolved`、`source_export_declared`、`static_module_relation_resolved`、`module_config_paths_declared`、`tsconfig_project_declared`、`tsconfig_project_reference_declared`、`tsconfig_file_membership_candidate`；`claim_schema_version = claim-schema/1`。

review 状态：`pending_review` / `approved` / `rejected_review`；`approved` 必须 `human_authored=True`。

### 4.5 树覆盖度三值（`src/trust/tree_scope.py`）

`COMPLETE`（`DEEP_WALK_COMPLETE` 或 `ROOT_TREE_ENUMERATED_NO_SUBTREES`）/ `ROOT_ONLY`（`ROOT_ONLY_SUBTREES_UNENUMERATED`，根层枚举但有未展开子树）/ `PARTIAL`（`TRUNCATED` 或 `UNKNOWN_COVERAGE`）。仅 `COMPLETE` 代表整棵树都看到了；`ROOT_ONLY` 对根级精确路径仍可判定，对子目录路径不可反证。

### 4.6 新鲜度四值（`src/lifecycle/lc_models.py`）

`NOT_APPLICABLE_TO_PINNED`、`VERSION_ALIGNED`、`POSSIBLY_STALE`、`UNKNOWN`。约束：`VERSION_ALIGNED` 必须有可信观测 commit 且 `observed == baseline`；`POSSIBLY_STALE` 必须有 reason_code 与可信新 commit，`observed == baseline` 不能判 stale。

### 4.7 视图五状态轴（`src/views/knowledge_view_assembler.py`）

| 轴 | 来源 | 取值 |
|---|---|---|
| `verification_status` | EC | `supported` / `refuted` / `insufficient_evidence` |
| `freshness_state` | Lifecycle | `NOT_APPLICABLE_TO_PINNED` / `VERSION_ALIGNED` / `POSSIBLY_STALE` / `UNKNOWN` |
| `review_status` | Claim | `pending_review` / `approved`（仅人工） |
| `execution_status` | Runtime | `SUCCESS` / `FAILED` / `TIMEOUT` / `CANCELLED` / `UNKNOWN` |
| provenance + authorization | 观测 / 执行记录 | `evidence_source_level` / `execution_source_level` / `snapshot_source_level` / `authorization_class`，分别判定 |

**视图无** `is_valid` / `overall_status` / `combined_status` / `final_verdict`（测试明确禁止合并）。`view_schema_version = knowledge-view/1`，`projection_rule_version = projection/1`。诊断码包括 `VIEW_INTEGRITY_FAILED`、`DANGLING_REFERENCE`、`SOURCE_MISSING`、`VERSION_MISMATCH`、`CLAIM_NOT_FOUND`、`VERIFICATION_NOT_FOUND`、`CLAIM_VERIFICATION_MISMATCH`、`REPOSITORY_MISMATCH`、`COMMIT_MISMATCH`、`EVIDENCE_CORRUPT`、`CURRENT_APPLICABILITY_UNKNOWN`、`PARTIAL_COVERAGE_ONLY`。

### 4.8 源码解析状态（`src/source_analysis/`）

| 类别 | 取值 |
|---|---|
| 解析状态 | `EXTRACTED`、`PARSE_FAILED`、`PARSER_UNAVAILABLE`、`UNSUPPORTED_ENCODING`、`BINARY_CONTENT` |
| tree-sitter 解析 | `PARSE_COMPLETE`、`PARSE_WITH_ERRORS`、`PARSE_UNSUPPORTED_SYNTAX`、`SOURCE_INCOMPLETE`、`CONTENT_INTEGRITY_FAILED` |
| 符号类型 | `module`、`class`、`function`、`async_function`、`method`、`async_method`、`nested_function` |
| 本地模块解析 | `LOCAL_MODULE_RESOLVED`、`EXTERNAL_OR_UNRESOLVED`、`AMBIGUOUS_CANDIDATES`、`INSUFFICIENT_TREE_COVERAGE`、`UNSUPPORTED_IMPORT_FORM` |
| 说明符状态 | `LITERAL_MODULE_SPECIFIER`、`DYNAMIC_MODULE_SPECIFIER` |
| 导入类型 | `default_import`、`named_import`、`namespace_import`、`side_effect_import`、`require_literal_call`、`dynamic_import` |
| 导出类型 | `named_export`、`default_export`、`export_declaration`、`export_list`、`re_export`、`export_all` |

`require("x")` 记为 `LITERAL_REQUIRE_CALL_OBSERVED`（调用观察），不是 ESM 声明；多条件导出同时可用 → `MULTIPLE_CONDITIONS_AVAILABLE`（不任选），子路径缺失 → `SUBPATH_NOT_IN_EXPORTS`。tree-sitter grammar 版本固定：core `0.26.0`、javascript `0.25.0`、typescript `0.23.2`，只从项目 `.venv` 加载，缺则 `PARSER_UNAVAILABLE`，绝不自动下载或降级为正则猜测。

### 4.9 请求预算状态（`src/collector/request_budget.py`）

| 类别 | 取值 |
|---|---|
| 预算状态 | `BUDGET_OK`、`REQUEST_BUDGET_INSUFFICIENT`、`BUDGET_EXHAUSTED`、`BUDGET_RATE_LIMITED` |
| 限流类型 | `PRIMARY`、`SECONDARY`、`UNKNOWN` |
| 计划项结果 | `NOT_RUN`、`SUCCESS`、`CACHE_HIT`、`RATE_LIMITED`、`HTTP_ERROR`、`SKIPPED_BUDGET_INSUFFICIENT` |

`can_spend()` 三重闸门：本次执行不超本地上限；真实剩余 ≥ cost + reserve；未处限流态。默认 `DEFAULT_REQUEST_LIMIT=8`、`DEFAULT_RESERVE=5`。无权威响应头 → `REQUEST_BUDGET_INSUFFICIENT`（宁可不发）。本地记录 ≠ 网络真实配额（匿名配额按来源 IP，其他进程也消耗），只用响应头推断。

### 4.10 内容采集授权（`src/collector/content_acquisition_policy.py`）

| 类别 | 取值 |
|---|---|
| 前置授权 | `ACQUISITION_ALLOWED`、`METADATA_ONLY`、`ACQUISITION_BLOCKED`、`AUTHORIZATION_UNKNOWN` |
| 五维操作 | `fetch`、`persist_bytes`、`derive_facts`、`internal_preview`、`external_distribution` |
| 决策 | `ALLOW`、`DENY`、`UNKNOWN` |
| 依据类型 | `PROJECT_OWNED_WORK`、`ORIGINAL_TEST_FIXTURE`、`LICENSE_OBSERVED_AND_APPLICABLE`、`USER_EXPLICIT_GRANT` |
| 核验状态 | `VERIFIED`、`UNVERIFIED` |

`external_distribution` 恒 `DENY`（`DISTRIBUTION_GATE_OPEN_BLOCKED`），除非独立关闭门禁。公开可见 ≠ 允许永久复制；`copy_permitted` 只影响再分发，不决定内部采集。

### 4.11 Answer 意图（`src/skill_interface/knowledge_answer.py`）

`introduce`（默认回退）/ `usage` / `architecture` / `code` / `evidence` / `completeness`。`audit` 只在 `evidence` / `completeness` 附加，其余为 `null`。固定输出：`network_requests=0`、`wrote_assets=0`、`distribution_allowed=false`、`freeze_state=FROZEN_INTERNAL_RESTRICTED`。

---

## 5. 身份、证据与当前视图的交互规则

1. **当前视图唯一来源**：`current_asset_ids()` JOIN `current_view` 与 `assets`，只返回当前指针采纳且实存、身份匹配的资产。历史裁决不得混入当前结论。
2. **证据准入**：原始 verdict ≠ 当前可采信 finding；非当前视图裁决不采信；证据链不完整时 supported/refuted 均降级为 `insufficient_evidence`。
3. **反证约束**：路径精确匹配；缺路径反证靠 `COMPLETE` 覆盖声明；未展开子树 + 非根级路径不可反证。
4. **未采集 ≠ 不存在**：`UNKNOWN` 不用空列表 / False / NOT_FOUND 冒充；`OBSERVED_ABSENT_IN_COVERED_SCOPE` 仅在 COMPLETE 覆盖下成立。
5. **跨仓库锚定**：`repository_id` 是仓库锚点，`subject_id` 是知识主体身份，`commit_sha` 是版本，`workspace_id` 是运行作用域、不是 Subject 身份；bindings 必带 `evidence_ref`。
6. **不可变保护**：A 层只追加，触发器拦 UPDATE/DELETE；content_hash 只由 payload 决定不等于逻辑身份；asset_id 含 repository_id 避免撞主键。
