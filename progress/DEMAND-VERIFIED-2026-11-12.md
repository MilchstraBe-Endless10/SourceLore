# 按需求文档逐项实测（2026-11-12 01:37）

需求文档位置：`docs/implementation/`（137 个文件，F2-P0…P6H）。
产品验收：`F2_P6A_PRODUCT_ACCEPTANCE.md`；树采集实测：`F2_P1C_REAL_GITHUB.json`；
符号契约：`F2_P4A_RENDERER_CONTRACT.md`、`F2_P5H_EXECUTION_REPORT.md`。

## 修复前的真实缺陷（都在这轮修掉了）

| 缺口 | 症状 | 根因 |
|---|---|---|
| 采集层抓不到正文 | preact blob=0，readme.md 227 B 空壳 | 采集没走 raw 路径 |
| 文档字段名不一致 | `/repocard` 的 documents 每项 id 为空 | 数据是 `document_id`，客户端读 `id` |
| 符号从未提取 | `query --type code` 返回 0 行 | `source_structure_observation` 资产类型完全不存在 |
| 树只有根层 | 三仓库全是 ROOT_ONLY | GitHub API 配额 0/60（非代码问题） |

## 修复后实测（每项都是真实数据）

### 1. 正文采集 + sha256 校验

```
✓ is-number      资产= 3  校验通过= 3  正文合计=  8524 B
✓ is-plain-obj   资产= 4  校验通过= 4  正文合计=  3013 B
✓ preact         资产= 5  校验通过= 5  正文合计= 54424 B
```

### 2. 代码符号（需求 F2-P6A 承诺的能力）

```
query 42283287 --type code --commit dbeba0d5
  symbols 49 行   coverage_status: COVERED_BY_EXTRACTED_SOURCE
  counts: {symbols: 49, exports: 13, facts: 62, imports: 0}

  js_function   BaseComponent              src/component.js:20
  js_function   getDomSibling              src/component.js:95
  js_function   renderComponent            src/component.js:127
  js_function   updateParentDomPointers    src/component.js:166
  js_function   resetRenderCount           src/component.js:196
  ...
```

入库统计：`written=49, reused=0, skipped=0`，两个文件均 `PARSE_COMPLETE`。

### 3. 派生文档

| 文档 | 修复前 | 修复后 |
|---|---|---|
| preact readme.md | 227 B | **14981 B**（真实 README） |
| preact 五篇合计 | 4462 B | **23667 B** |

### 4. 正文查询

```
query 42283287 --type content --commit dbeba0d5 --path README.md
  raw_byte_length: 14884
  provenance_level: OBSERVED
  capture_status: CAPTURED
```

## 新增工具（都走官方入口，不自造格式）

- `tools/capture_raw.py` — raw 正文补采，Git blob OID 校验，走 `ingest_captured_blob`
- `tools/extract_symbols.py` — tree-sitter 符号提取，走 `ingest_source_facts`

## 仍未解决（有明确原因，不是含糊）

1. **树深度 ROOT_ONLY** — GitHub API 配额 `remaining=0`。
   `src/collector/github_client.py:296` 的 `recursive` 参数早就实现了，
   等配额重置或配 token 即可。文档见 `progress/TREE-BLOCKER-REAL-CAUSE-2026-11-12.md`。
2. **imports=0** — 目前只抓了 3 个源文件，其中没有跨模块 import 语句。
   `observed_imports` 通道已就绪，抓到含 import 的源文件即可产出。
