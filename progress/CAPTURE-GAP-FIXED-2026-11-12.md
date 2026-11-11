# 采集层缺口已修复：preact 从 0 正文 → 54KB 真实源码

日期：2026-11-12 · 提交前记录

## 发现的真实问题（这才是「知识库没做」的根因）

不是 UI，是**采集层根本没抓到文件正文**：

| 仓库 | 修复前 blob 数 | 修复前 readme.md |
|---|---|---|
| jonschlinkert/is-number | 3 | 6575 B |
| sindresorhus/is-plain-obj | 4 | 884 B |
| **preactjs/preact** | **0** | **227 B（"未采集到 README 正文"）** |

同机验证网络正常：
`curl raw.githubusercontent.com/preactjs/preact/<sha>/README.md` → **HTTP 200 / 14884 B**。
所以不是网络、不是权限，是采集环节漏了 raw 路径。

## 修复

新增 `tools/capture_raw.py`：
- 从 `raw.githubusercontent.com` 抓真实文件字节
- 计算 Git blob OID = `sha1("blob <len>\0" + bytes)`
- 走**官方入口** `content_ingest_coordinator.ingest_captured_blob`
  （字节落 blob 内容寻址存储，元数据落 A 层 assets）
- `copy_permitted` / `distribution_allowed` 一律 False（继承既有分发门禁）
- 幂等：同 (repo, commit, path, blob_oid, sha256) 复用既有资产

## 修复后实测（sha256 逐条实算）

```
✓ is-number      资产= 3  校验通过= 3  正文合计=  8524 B
✓ is-plain-obj   资产= 4  校验通过= 4  正文合计=  3013 B
✓ preact         资产= 5  校验通过= 5  正文合计= 54424 B
```

preact 抓到：README.md 14884B、package.json 6739B、src/index.js 423B、
src/component.js 7763B、src/diff/index.js 24615B。

## 派生文档对比

| 文档 | 修复前 | 修复后 |
|---|---|---|
| preact readme.md | 227 B（空壳） | **14981 B（真实 README）** |
| preact project-overview.md | 761 B | 3279 B |
| preact dependencies.md | 250 B | 2143 B |
| preact 五篇合计 | 4462 B | **23667 B** |

## 顺带修掉的字段 bug

`card-data.json` 里文档字段是 `document_id`，但客户端按 `id` 取值，
导致 `/repocard` 返回的 documents 每项 `id` 为空。
已在 `plugin/dsh-sourcelore-cards/index.js` 补 `id` 别名归一化。

## 仍未解决

- 树仍是 `ROOT_ONLY`（32 条目，最大深度 0）—— 子目录未采集，
  需要 GitHub Trees API 递归；无 token 时受速率限制。
- `code_rows: 0`（`query --type code` 对这些仓库返回空），
  IMPORTS 边目前靠已抓源码字面匹配，未做 AST 解析。
