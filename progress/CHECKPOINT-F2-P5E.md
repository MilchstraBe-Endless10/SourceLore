# F2-P5E（检查点）· 基线 a06b9e1 · Crosswalk 已复算匹配

## 目标（把现有模块连成真实链路）
授权 Blob → 不可变持久化 → Observation → Fact → Claim → Verification
→ Research → KnowledgeView → 卡片

## ★ 本轮第一个真缺陷（已定位，待修）
`blob_content_store.put_bytes` 现有逻辑：
```python
if target.exists():
    if sha_of(target.read_bytes()) == hexd: return reused
    # 否则
    target.unlink(missing_ok=True)      # ← 删掉已有文件
...
os.replace(tmp, target)                 # ← 然后覆盖
```
**问题**：目标已存在但内容不符时，**直接删除并覆盖**。
这违反「已存在错误内容拒绝覆盖」（题面 §4.1 明令不得直接覆盖）。

正确做法：
- 目标存在 + 内容一致 → 复用
- 目标存在 + 内容不一致 → **返回 CONTENT_INTEGRITY_CONFLICT，不删不写**
- 目标不存在 → exclusive create（O_EXCL）发布

## 待做清单
1. 修 put_bytes 的覆盖语义（exclusive create）
2. 五维权限分离：FETCH/PERSIST/DERIVE_FACTS/PREVIEW/DISTRIBUTION
3. 结构化 authorization_ref（不接受布尔）
4. Observation 落库 + Content Facts 落库 + Claim/Verification
5. Research/KnowledgeView/卡片集成
6. 原创 Git 夹具 E2E（AUTHORIZED_LOCAL_FIXTURE）
7. 25 项 Content Gold

## 硬约束
- 不改冻结 Crosswalk；不动 B-1/B-2/B-3；copy_permitted 保持 false
- A 层不可 UPDATE；自引用写入前确定
- 不改 Collector/Storage 既有体系

## 已完成 + 实测（2026-11-05 20:58）

### 1. Blob Store 无覆盖语义（真缺陷，已修）
原逻辑：目标存在且校验失败 → `unlink` 再 `os.replace` 覆盖。
改为：`os.link` exclusive create（FileExistsError = 竞态），冲突时返回
`CONTENT_INTEGRITY_CONFLICT`，**绝不删、绝不覆盖**。
实测：写入 ORIGINAL → 人为篡改 → 再写同摘要 → `ok=False, error=CONTENT_INTEGRITY_CONFLICT`，
文件内容仍为 `TAMPERED!!`（未被覆盖）。另加 `_fsync_dir`。

### 2. 五维权限分离（已测通）
`FETCH / PERSIST / DERIVE_FACTS / PREVIEW / DISTRIBUTION` 各自独立 decision dict，
含 decision/reason_code/evidence_reference/policy_version/repository_identity/
commit_sha/file_path/permitted_operation/limitations。

结构化授权引用 `build_authorization_ref`（四类依据 × VERIFIED/UNVERIFIED）：
- PROJECT_OWNED_WORK / ORIGINAL_TEST_FIXTURE / LICENSE_OBSERVED / USER_EXPLICIT_GRANT
- 裸布尔不再能当授权；错仓库 → AUTHORIZATION_REPO_MISMATCH；未核验 → UNKNOWN
- DISTRIBUTION 恒 DENY（B-1/B-2/B-3 OPEN）

实测（ORIGINAL_TEST_FIXTURE）：前四维 ALLOW，DISTRIBUTION DENY。

### 3. Content Fact 构造（已测通）
`src/content_persistence/content_fact_ingest.py`，`build_fact` 成功：
`fact_id=SL-FACT-<40hex>`（**必须符合 SAFE_FACT_ID 正则**）、
`observation=OBSERVED_PRESENT`（**必须用既有三态之一**）、
补齐 `item_key / input_digest(snapshot_content_hash 与 item_key 必填) / content_hash / extractor_version`。

## 框架硬约束（血泪，后续必读）
| 契约 | 约束 |
|---|---|
| `SAFE_FACT_ID` | `^SL-FACT-[0-9a-f]{40}$` —— 别的前缀一律拒绝 |
| `OBSERVATION_STATES` | 只有 OBSERVED_PRESENT / OBSERVED_ABSENT_IN_COVERED_SCOPE / UNKNOWN |
| `make_input_digest` | 必填 snapshot_content_hash + item_key |
| `SUPPORTED_CLAIM_TYPES` | 目前仅 `repository_path_exists` —— 内容命题须扩展 |
| A 层 | 不可 UPDATE；自引用写入前算好 |

## 下一步
1. 扩展 SUPPORTED_CLAIM_TYPES + 内容裁决器（复用 Verification 三态）
2. Research/KnowledgeView 支持内容事实
3. 原创 Git 夹具 E2E（AUTHORIZED_LOCAL_FIXTURE）
4. 25 项 Content Gold
5. 全量回归 + 文档 + 提交
