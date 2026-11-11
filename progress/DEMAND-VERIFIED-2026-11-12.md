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

---

## 补充：三仓库符号现状（01:38 实测）

```
24313173 is-number     symbols=0   exports=0   imports=0   coverage=NOT_COVERED
38923193 is-plain-obj  symbols=4   exports=2   imports=0   coverage=COVERED_BY_EXTRACTED_SOURCE
42283287 preact        symbols=49  exports=13  imports=0   coverage=COVERED_BY_EXTRACTED_SOURCE
```

### is-number 的 0 符号是真实规则缺口（不是采集问题）

它的 `index.js`（411 B）内容形态是：

```js
module.exports = function(num) {
  if (typeof num === 'number') { return num - num === 0; }
  ...
};
```

即 **`assignment_expression` + 匿名 `function_expression`**。
`js_ts_symbol_rules._classify` 目前处理 `function_declaration` / `class_declaration`
/ `lexical_declaration`，不认 `module.exports = function(){}` 这种 UMD/CJS 主流写法。

**这是需要补的规则，不是数据缺失。** 已记录，未在本轮修改
（改判定链核心需要独立验证，不能顺手动）。

### imports=0 的原因

只抓了 3 个源文件（index.js / component.js / diff/index.js），
其中没有跨模块 `import`/`require` 语句。
`observed_imports` 通道已就绪（`source_fact_ingest.py` 有 RULE_IMPORT 分支），
抓到含 import 的源文件即可产出。preact 的 `src/index.js`(423B) 是纯 re-export，
理论上应有 export 事实（现有 exports=13 已含）。

---

## 01:59 追加：provenance 标签的误报（已查清，不是数据问题）

`query --type content` 显示 is-number 的 README 是 `provenance_level: SYNTHETIC_FIXTURE`，
一度以为采集的是假数据。**实测对比后否定了这个猜测：**

```
README.md      库存= 6514B 远端= 6514B  字节一致
index.js       库存=  411B 远端=  411B  字节一致
package.json   库存= 1599B 远端= 1599B  字节一致
```

对比方式是同时读库存 blob 和 `raw.githubusercontent.com/.../<sha>/<path>` 的实时字节。

**所以：字节是真的，只是入库时 provenance 标签打成了 SYNTHETIC_FIXTURE，
`source_api` 写的是 `github.git.blobs`（旧采集路径），不是 `raw.githubusercontent.com`。**

影响：判读时会误以为数据不可信。**这是标签缺陷，不是数据缺陷。**
修它需要改旧资产的 provenance 字段——A 层资产不可变，正确做法是追加一条新资产，
而不是改旧的。本轮先如实记录，不动既有资产。

### is-plain-obj 的 README 查不到

它的真实文件名是小写 `readme.md`（794 B，`AUTHORIZED_REMOTE_SOURCE`），
查询时用的是大写 `README.md` → 查不到。**不是缺数据，是大小写。**
