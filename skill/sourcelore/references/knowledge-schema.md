# 知识模型（简版）

## 四层

- **A 不可变来源资产**：Snapshot、Fact、Claim、Verification。写入后不可修改。
- **B 当前指针**：指向某身份的当前版本。
- **C 可重建索引**：`index_rows`，可按 repository_id / commit_sha / asset_type 查询。
- **D 只读视图**：KnowledgeView，50 字段，五轴分离。

## 五轴（不可合并）

| 轴 | 取值 | 来源 |
|---|---|---|
| `verification_status` | supported / refuted / insufficient_evidence | Evidence-Claims |
| `freshness_state` | ALIGNED / POSSIBLY_STALE / UNKNOWN … | Lifecycle |
| `review_status` | pending_review / approved / rejected | **仅人工** |
| `execution_status` | SUCCESS / FAILED … | Runtime |
| `provenance_level` + `authorization_class` | 分层来源 / 授权类别 | 分别判定 |

**`supported` 不等于已人工审核；`fresh` 不等于已发布；`preview` 不等于可分发。**

## 裁决含义（唯一允许的措辞）

- `supported` → "在指定范围内，现有经过验证的证据支持该命题。"
- `refuted` → "现有有效反证与该命题矛盾。"（仅对该 Commit）
- `insufficient_evidence` → "证据不足，无法作出支持或反驳裁决。"

## 覆盖与完整性

- `completeness_status: COMPLETE` 才代表整棵树都看到了
- `PARTIAL` → 未覆盖部分**不得判为不存在**
- `coverage_state`（研究层）与 `verification_status`（裁决层）**是两个不同的东西**
