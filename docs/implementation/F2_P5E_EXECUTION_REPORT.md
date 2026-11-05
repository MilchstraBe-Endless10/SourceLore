# F2-P5E 执行报告

**基线** `a06b9e1`

## 结论

原创夹具的完整链路走通了：**字节 → 不可变存储 → 离线读回 → 解析 → Observation → Fact → Claim → 裁决**。

真实 GitHub 内容仍然没有落库——因为没有可核验的授权依据。这条门禁保持 OPEN，我没有伪造。

## 一、授权边界（本轮核心修复）

P5D 用一个含糊的 `AUTHORIZATION_UNKNOWN` 同时代表五种行为，这是错的设计。本轮拆成五维：

```
FETCH_DECISION / PERSIST_DECISION / DERIVE_FACTS_DECISION
PREVIEW_DECISION / DISTRIBUTION_DECISION
```

每一项都带 `decision / reason_code / evidence_reference / policy_version /
repository_identity / commit_sha / file_path / permitted_operation / limitations`。

实测（原创夹具授权）：

```
FETCH      ALLOW
PERSIST    ALLOW
DERIVE     ALLOW
PREVIEW    ALLOW
DISTRIBUTE DENY     ← B-1/B-2/B-3 OPEN，恒不打开
```

结构化授权引用 `build_authorization_ref`，四类依据：

`PROJECT_OWNED_WORK` / `ORIGINAL_TEST_FIXTURE` / `LICENSE_OBSERVED_AND_APPLICABLE` / `USER_EXPLICIT_GRANT`

**裸布尔不再能当授权**——`--license-known` 与 `repo_looks_third_party=False` 都必须转成结构化引用，且要 `VERIFIED`。绑定错仓库返回 `AUTHORIZATION_REPO_MISMATCH`，未核验返回 `UNKNOWN`。

`copy_permitted=false` / `distribution_allowed=false` 原值保留，未改。

## 二、Blob Store 不覆盖证明（真缺陷）

P5D 的 `put_bytes` 在目标已存在但校验失败时，**先 `unlink` 再 `os.replace`**——直接违反不可变语义。

改为：

```
目标存在 → 核对内容
  一致   → 复用（reused=True）
  不一致 → CONTENT_INTEGRITY_CONFLICT，不删、不写
目标不存在 → os.link 独占发布（FileExistsError 即竞态）→ 核对后复用
```

实测：

```
写入 ORIGINAL → exclusive=True
人为篡改该文件 → 再写同摘要
结果 ok=False, error=CONTENT_INTEGRITY_CONFLICT
文件内容仍为 TAMPERED（未被覆盖回原内容）
```

另加 `_fsync_dir` 让目录项也落盘。

并发 4 线程写同内容 → 一份字节、摘要一致、无损坏。

## 三、内容 Fact / Claim

### 三类事实

| 规则 | 能确认 | 不能确认 |
|---|---|---|
| `README_HEADING_EXISTS` | 某 Commit 的 README 在某行有某级标题 | 功能已实现 |
| `MANIFEST_DEPENDENCY_DECLARED` | 清单声明了某依赖 | 依赖已安装 |
| `MANIFEST_FIELD_PRESENT` | 某字段存在 | 真实部署状态 |

`FactObservation` 框架有三条硬约束，撞了三次才对齐：

- `fact_id` 必须 `^SL-FACT-[0-9a-f]{40}$`
- `observation` 只能用既有三态，我用 `OBSERVED_PRESENT`
- `make_input_digest` 必填 `snapshot_content_hash` + `item_key`

### 裁决契约

每种命题在 `CONTRACTS` 里显式写出 supported / refuted / insufficient / forbidden。

关键规则：**内容不可用、PARTIAL、解析失败 → 一律 `insufficient_evidence`，绝不 refuted。**

## 四、真缺陷 D-13：主体未比对

最初只按 `rule_id` 匹配事实。后果：查询 "Nonexistent" 标题，会命中已有的 "Usage" 标题，**凭空确认一条不存在的命题**。

改为 subject 子集精确匹配 + `commit_sha` / `repository_id` / `file_path` 三项比对。

修后实测：

```
查 Usage H3      → supported
查 Nonexistent   → insufficient_evidence (NO_MATCHING_FACT)
查 错 Commit     → insufficient_evidence
```

## 五、Content Gold（25 例）

覆盖：标题层级、空 README、纯文本、UTF-8、CRLF、代码围栏、依赖声明/缺失、清单字段、非法 JSON、TOML、数组非对象、幂等、跨 Commit、跨仓库。

```
错误肯定 0
错误否定 0
正确 abstention：C05 C06 C14 C15 C17 C19 C20 C22 共 8 例
```

## 六、验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63
= 867 项，失败 0
f1d 26/26（已登记 src/content_persistence/ tests/content_persistence/）
Crosswalk 42841207… 未变
```

阻断级指标全部 0：错误 Blob 接受 / 错误 Commit Fact / 未授权持久化 /
无证据 supported / 不完整 refuted / 未授权原文复制 / 历史资产被改。

## 七、门禁

| 门禁 | 状态 |
|---|---|
| A_CONTENT_OPERATION_AUTHORIZATION | **DONE** |
| B_IMMUTABLE_BLOB_STORAGE | **DONE** |
| C_AUTHORIZED_CONTENT_PERSISTENCE | DONE_FIXTURE_ONLY |
| D_OFFLINE_CONTENT_RELOAD | DONE_FIXTURE_ONLY |
| E_CONTENT_OBSERVATION_PERSISTENCE | DONE_FIXTURE_ONLY |
| F_CONTENT_FACT_PERSISTENCE | DONE_FIXTURE_ONLY |
| G_CONTENT_CLAIM_VERIFICATION | DONE_FIXTURE_ONLY |
| H_CONTENT_RESEARCH_QUERY | DONE_FIXTURE_ONLY |
| I_SKILL_CONTENT_CARD | PARTIAL（沿用既有渲染器） |
| J_REAL_GITHUB_CONTENT_E2E | **NOT_VERIFIED** |
| K_NATURAL_LANGUAGE_AUTO_TRIGGER | NOT_VERIFIED |
| L_DISTRIBUTION_READY | NOT_READY |

## 八、证据级别（严格区分）

`AUTHORIZED_LOCAL_FIXTURE` DONE ／ `REAL_GITHUB_FETCH_VERIFIED` DONE(P5D) ／
`REAL_GITHUB_BYTES_PERSISTED` **BLOCKED** ／ `CONTENT_FACTS_PERSISTED` DONE_FIXTURE_ONLY ／
`CONTENT_CLAIMS_VERIFIED` DONE_FIXTURE_ONLY ／ `REAL_GITHUB_KNOWLEDGE_E2E` NOT_VERIFIED

## 九、下一批起点

只缺一样东西：**可核验的真实仓库授权**。有了它，`REAL_GITHUB_KNOWLEDGE_E2E` 一次就能走通——管线已经全部接好了。
