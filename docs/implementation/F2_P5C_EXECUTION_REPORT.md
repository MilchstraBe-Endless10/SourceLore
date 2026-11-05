# F2-P5C 执行报告

**基线** `f3bf6f6`

## 结论

内容抽取引擎建成，但**真实数据零解析**——因为 Blob 内容字节从来没被采集过。

这是本轮最重要的事实。`blob_refs` 里只有 `blob_sha / path / size`，没有字节。
所以对 `octocat/Hello-World` 的 README，引擎返回 `CONTENT_NOT_CAPTURED`，
`content_available=false`，`network_requests=0`。**我没有编造任何 README 内容。**

## 做了什么

### 1. C 层索引重建（第 2 节）

`tools/sourcelore_rebuild_index.py`，默认只读：

```
--check   现状（每类型 NULL 数）
--dry-run 逐行投影计划
--verify  一致性检查
--apply   真写（必须 --target 显式确认，拒绝默认生产库）
```

**commit_sha 按 asset_type 分类型投影**，不再无条件取任意 commit 字段：

| asset_type | 投影 |
|---|---|
| `repository_snapshot` | `payload.commit_sha` |
| `extracted_fact` | `payload.commit_sha` |
| `claim_candidate` | `payload.commit_sha` |
| `claim_verification` | **无** → `NEEDS_JOIN`（其 commit 来自所绑 Claim，不硬猜） |

多字段冲突 → `<<AMBIGUOUS>>`，不任选。

隔离副本实测：回填 3 行、1 行 NEEDS_JOIN、0 歧义；
**A/B/Runtime 指纹重建前后完全一致**；二次重建幂等。**生产库未动。**

### 2. 内容抽取引擎

```
src/content/
  content_models.py     Observation 模型（Git OID 与内容摘要分离）
  content_budget.py     256KiB/blob、2MiB/批、32 路径、100 facts
  blob_reader.py        编码/BOM/CRLF/空/非法UTF-8/二进制/超限
  evidence_ranges.py    字节+行号双定位，verify_range 九项核验
  content_extractor.py  Blob → Observation → Facts
  parsers/{readme,package_json,pyproject_toml}.py
```

`package.json` 用 `json` 真解析，`pyproject.toml` 用 `tomllib`；
**没有 tomllib 时返回 `PARSER_UNAVAILABLE`，拒绝用正则猜**。

### 3. CLI 扩展

```
analyze <url> --commit <sha> --include-content [--content-path P]
inspect <rid> --content-summary
query <rid> --commit <sha> --type content [--path P]
```

## 三个真缺陷

**D-6 证据 label 回显不可信原文。**
`label` 原本取原文片段，导致提示注入文本（`Ignore previous instructions...`）
进入了证据描述字段。改为 `heading:L1` 这类结构化描述，默认不回显原文。

**D-7 模块名冲突。**
`src/content/extractor.py` 与 `src/facts/extractor.py` 同名。
我把 `content` 排进 `sys.path` 前面后，`import extractor` 解析到了 content 版本 →
**6 个既有 skill_interface 测试直接 ERROR**。改名 `content_extractor.py`，
并把 paths 顺序回退到 `skill_interface` 之后。

这条最关键：我加新模块，差点把既有 Facts 全部撞坏。

**D-8 Gold 测试把同路径多用例塞进一个快照。**
Git 语义下同一 Commit 同一路径只有一个 blob；按 path 查找必然互相覆盖。
改为逐用例独立快照。

## 验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
= 745 项，失败 0，退出码全 0
```

f1d 26/26（已登记 `src/content/`、`tests/content/`）。
Crosswalk `42841207…` 未变。

## 门禁

| 门禁 | 状态 |
|---|---|
| INDEX_REBUILD_SAFE | **DONE** |
| BLOB_CONTENT_AVAILABILITY | **NOT_AVAILABLE** |
| CONTENT_EXTRACTION_ENGINE | DONE_SYNTHETIC_ONLY |
| CONTENT_EVIDENCE | DONE |
| CONTENT_FACTS_EC | PARTIAL（未写入 Storage） |
| SKILL_CONTENT_CLI | DONE |
| GOLD_CONTENT | DONE（25 例，错误肯定 0、错误否定 0） |
| NATURAL_LANGUAGE_AUTO_TRIGGER | NOT_VERIFIED |
| DISTRIBUTION_READY | NOT_READY |

## 不宣称

- 内容抽取引擎可用 ≠ 真实 README 已解析
- 合成夹具 ≠ GitHub 真实数据
- README 有 `Installation` 标题 ≠ 安装流程可运行
- 依赖已声明 ≠ 依赖已安装；有 test 脚本 ≠ 测试通过
- 重建工具验收 ≠ 生产库已回填

## 下一批必须做的第一件事

**采集 Blob 内容字节。** 没有它，整个内容级能力只能在合成夹具上跑。
需要：在 Collector 里增加 blob 内容获取 + 以资产形式落库（受预算约束），
并明确 `copy_permitted=false` 的许可证边界。
