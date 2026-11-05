# F2-P5B 执行报告

**基线** `eb781f3`

## 结论

离线复用打通：固定 Commit + 本地完整快照 → **0 次网络请求**，可重复调用且不重复写资产。
`index_rows.commit_sha` 的 NULL 根因已定位并修复（新资产正确，历史库待重建）。
限流 2 秒内快速失败。多 Commit 确定性集成测试通过。

真实 Token 与真实第二 Commit 未验证（外部条件：无 Token、GitHub 限流）。
自然语言自动触发保持 NOT_VERIFIED。

## 主要改动

```
src/storage/knowledge_store.py     + _resolve_index_commit_sha（三级回退）
src/skill_interface/cache_policy.py  新增（九判据缓存决策）
src/skill_interface/analyze.py     + 缓存优先/offline/refresh/token/tree_summary/slug 映射
src/skill_interface/cli.py         + --commit/--offline/--refresh/--no-token
skill/sourcelore/SKILL.md          更新（离线/缓存/Token/限流/Tree 纪律）
tests/skill_interface/            +28 项（offline_cache / multicommit / authenticated_github）
```

## 离线复用实测

```
analyze <url> --commit 7fd1a60b... --offline
→ cache_decision: CACHE_HIT_COMPLETE
→ network_requests: 0
→ reused: true
→ branch_current_unknown: false
```

重复两次后：`assets 4→4`、`snapshots 1→1`（**不重复写入、不推进版本**）。

不带 `--commit`（可变 Branch）：
```
branch_current_unknown: true, assumed_current: false
```

## 两个新缺陷

**D-4 快照 payload 不保存仓库名。**
实测 payload keys 里**没有** `resolved_repository`（虽然 `SourceSnapshot` 有该入参）。
结果：有快照但按 URL 查不到 → 误报 `CACHE_MISS`。
修复：采集成功时写本地 `repo_slugs.json`（`owner/repo → repository_id`）。
这是速查表，不是知识权威数据。

**D-5 `_index_asset` 只认 `draft.source_snapshot`。**
`ingest_coordinator` 构造 `AssetDraft` 时**从不传** `source_snapshot`，于是该列恒 NULL。
修复：三级回退（`source_snapshot` → `payload.commit_sha` → `payload.source_snapshot.*`）。

## 限流

```
耗时 2s
error: RATE_LIMITED
retry_after: 2572
hint: 不绕过限流、不长时间等待
```

`max_retries=0`、`max_retry_after=0`。**未改 Collector 通用重试语义。**

## 验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 = 668 项，失败 0
Crosswalk 42841207… 未变
```

## 门禁

| 门禁 | 状态 |
|---|---|
| A_OFFLINE_KNOWLEDGE_REUSE | **DONE** |
| B_GITHUB_COLLECTION_USABILITY | PARTIAL（Token 未实测） |
| C_MULTI_COMMIT_KNOWLEDGE | PARTIAL（合成通过，真实双 Commit 未验） |
| D_SKILL_INSTALLATION_SYNC | **DONE** |
| E_NATURAL_LANGUAGE_SKILL_TRIGGER | NOT_VERIFIED |
| F_DISTRIBUTION_READY | NOT_READY |

## 不宣称

离线复用好 ≠ 能推断 Branch 当前版本；合成双 Commit ≠ 真实验收；
Token 支持已实现 ≠ 真实 Token 验证；Skill 被主动调用 ≠ 自然语言自动触发。

B-1/B-2/B-3 保持 OPEN。本轮未触碰模型 Provider / 网关 / 凭据 / Harness 全局配置。
