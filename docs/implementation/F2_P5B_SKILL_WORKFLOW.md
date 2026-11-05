# F2-P5B Skill 工作流

**基线** `eb781f3`

## 三级决策

```
LOCAL_KNOWLEDGE_LOOKUP  →  CACHE_DECISION  →  OPTIONAL_REMOTE_REFRESH
```

| 输入 | 本地命中 | 行为 | 网络请求 |
|---|---|---|---|
| `--commit <sha>` | CACHE_HIT_COMPLETE | 直接复用 | **0** |
| `--commit <sha>` + `--offline` | 命中 | 复用并注明未联网 | **0** |
| `--offline` | 未命中 | `OFFLINE_CACHE_MISS`，退出码 3 | 0 |
| `--offline` | 有多 Commit | `BRANCH_CURRENT_UNKNOWN` | 0 |
| `--refresh` | 任意 | 重新采集 | 有 |
| 无 `--commit` | 有缓存 | `branch_current_unknown: true` | 0 |
| 无 `--commit` | 无缓存 | 联网采集 | 有 |

## 缓存完整性九判据

1. `repository_id` 归属
2. `commit_sha` 匹配
3. `source_snapshot` 资产身份可 `get_asset(verify=True)`
4. 内容摘要（由既有 verify 提供，不自造哈希）
5. `retrieval_scope`
6. `completeness_status`（PARTIAL 不得冒充 COMPLETE）
7. `tree_entries` 存在
8. Facts / Claims 版本
9. 悬空 / 损坏引用 → `CACHE_INTEGRITY_FAILED`（**不当成"没有缓存"**）

## 身份解析（不猜）

payload **不保存仓库名**（实测 keys 无 `resolved_repository`）。
因此离线按 URL 查找需要旁路映射：`<data_root>/repo_slugs.json`（`owner/repo → repository_id`），
采集成功时写入。**这不是知识权威数据**，只是本地速查表。

若同一 URL 解析出多个 `repository_id` → `CACHE_INTEGRITY_FAILED`，**不自动合并身份**。

## 限流

`max_retries = 0`、`max_retry_after = 0`。
被限流时 **2 秒内**返回 `RATE_LIMITED` + 真实 `retry_after` + hint。
不自动重试、不空等、不绕过。**不改 Collector 的通用重试语义**（那是 P1C 契约）。

## GitHub Token

`GITHUB_TOKEN` 只从进程环境读取，传给现有 `GitHubClient`（**单处实例化**）。
不进 Git、不进日志、不进资产、不进对话。`--no-token` 可单次禁用。
没有 Token 时功能完整可用（只是配额低）。

## Tree 语义

`tree_summary` 给出：`entry_count` / `object_types` / `completeness` / `description`。

- `COMPLETE + 1` → 已完整枚举，确实只有 1 个条目
- `COMPLETE + 0` → 已完整枚举，该范围为空
- `PARTIAL` → 只有部分，不能推断未出现路径不存在

`object_types` 保留 blob / directory / submodule / symlink，不合并成"文件"。

## 索引修复

`index_rows.commit_sha` 曾经恒为 NULL，根因是 `AssetDraft` 不传 `source_snapshot`。
现改为三级回退解析 payload。A 层未动、哈希未变、C 层可重建。
**历史库需重建索引才回填**；本轮未做批量重建。
