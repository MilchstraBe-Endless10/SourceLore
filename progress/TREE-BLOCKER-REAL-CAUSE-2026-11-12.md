# 树采集卡在 ROOT_ONLY 的真实原因（2026-11-12 实测）

## 结论

**GitHub REST API 匿名配额已耗尽：`limit=60, remaining=0`。**

```
$ curl https://api.github.com/rate_limit
  配额 60  剩余 0  重置 1794418471

$ curl "https://api.github.com/repos/preactjs/preact/git/trees/<sha>?recursive=1"
{"message": "API rate limit exceeded for 203.10.98.186. ..."}
```

而 raw 通道完全正常（不受 API 限流）：

```
package.json  -> HTTP 200
src/index.js  -> HTTP 200
```

## 这解释了两件事

1. **为什么三个仓库都是 `ROOT_ONLY`**
   递归树必须走 `POST/GET /repos/{o}/{r}/git/trees/{sha}?recursive=1`，
   配额用尽 → 只能退回根层（根层是建快照时一次性拿到的 commit.tree.sha 结果）。
   `deep_walk_used: false` 不是没实现，是**没额度去调**。

2. **为什么需求文档里 `REAL_GITHUB_*` 门禁一直开不开**
   `docs/implementation/F2_P1C_REAL_GITHUB.json` 记录 `credential_used: false`，
   `docs/implementation/F2_P6A_PRODUCT_ACCEPTANCE.md` 明写
   「GitHub API 已限流（HTTP 403），拿不到真实仓库」。
   **这不是代码缺陷，是缺凭据。**

## 代码侧已就绪，无需改

`src/collector/github_client.py:296` 已支持递归：

```python
def ...(..., recursive: bool = False, ...):
    params = {"recursive": "1"} if recursive else None
```

`src/collector/source_snapshot.py` 已有 `tree_truncated_seen` / `deep_walk_used` 字段。
缺的只是调用时的额度。

## 三条出路（按推荐度）

### A. 配 GITHUB_TOKEN（推荐）
匿名 60 次/小时 → 认证 5000 次/小时。一个只读公开仓库的 fine-grained token 即可。
**注意：按四条硬线，凭据不读、不复述、不交出。** 需要用户自己写入环境变量或配置，
我不读取其值，只使用其存在性。

配好后验证方式（不打印 token）：
```bash
[ -n "$GITHUB_TOKEN" ] && echo "token 已就位" || echo "未配置"
```

### B. 等配额重置
`reset=1794418471` 换算后约 1 小时。重置后跑一次递归树，
单个仓库约 1 次 API 调用（recursive=1 一次拿全树），三个仓库 3 次，足够。

### C. 不再依赖 Trees API（长期正解，但工程量大）
从 raw 逐个探测已知路径。缺点：无法发现未知路径，
本质上做不到「完整文件树」，会违反 `GIT_TREE_COMPLETENESS` 的要求。
**不建议**——那等于用猜测代替采集。

## 当前真实状态（三仓库）

| 仓库 | 正文 blob | sha256 校验 | 树深度 |
|---|---|---|---|
| is-number | 3 | 全通过 | ROOT_ONLY（13 条目） |
| is-plain-obj | 4 | 全通过 | ROOT_ONLY（13 条目） |
| preact | 5 | 全通过 | ROOT_ONLY（32 条目） |

**正文已真实可读**（preact README 14884 B），**树深度受限于配额**。
