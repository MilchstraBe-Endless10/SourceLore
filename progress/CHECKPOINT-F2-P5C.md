# F2-P5C（检查点）· 基线 f3bf6f6 · Crosswalk 已复算匹配

## ★ 已确认的关键事实（决定整批走向）

**Blob 内容字节未保存。** 实测 `blob_refs` 只有：
`{"blob_sha":"980a0d5...","path":"README","size":13,"mode_kind":null}`
DB 里无 blob 内容表（只有 `asset_fts_content`，那是 FTS 索引）。

→ 真实 README 内容**不可离线解析**，必须报 `BLOB_CONTENT_NOT_AVAILABLE`。
→ 真实侧验收只能到"确认引用存在、内容缺失"，**不得猜 README 内容**。
→ 内容抽取引擎用**明确标注 SYNTHETIC_FIXTURE** 的合成夹具验证。
→ GitHub 限流中（未认证 60/h 已耗尽），不绕过。

## 任务清单

### 2. 历史索引重建安全审计
- `tools/sourcelore_rebuild_index.py`：--check/--dry-run/--verify/--apply
- 默认只读；只重建 C 层；不动 A 层/B 指针/Runtime/Claim/Verification
- **修 commit_sha 映射风险**：不能无条件把 baseline_commit_sha / observed_commit_sha
  当统一 commit_sha —— 必须按 asset_type 定投影规则；冲突时返回歧义状态而非任选
- 在隔离副本验收，正式库需单独授权

### 3-9. 内容级能力
- content_models / blob_reader / content_budget / evidence_ranges / extractor
- parsers: readme, package_json, pyproject_toml（至少两类真实解析器）
- ContentEvidenceRef 字节+行号双定位
- Content Facts 走既有 Facts/EC 框架（不建第二套裁决机）
- 预算：256KiB/blob、2MiB/批、32 路径、100 facts/文件
- 错误码：BLOB_TOO_LARGE/BINARY_CONTENT/UNSUPPORTED_ENCODING/CONTENT_NOT_CAPTURED/
  CONTENT_HASH_MISMATCH/CONTENT_PARTIAL/CONTENT_PARSE_FAILED

### 10-11. CLI + Skill 同步
--include-content / --content-summary / --type content / --content-fact-id

### 12-14. 验收
真实侧（受限）+ 15 类合成夹具 + Gold ≥25 案例 + 全量回归

## 硬约束
- 不改冻结 Crosswalk；不编造 SL-CAP 编号（新能力记 local increment）
- 不发大段第三方原文进卡片；不动分发门禁 B-1/B-2/B-3
- 不执行仓库代码；不建第二个 CLI
