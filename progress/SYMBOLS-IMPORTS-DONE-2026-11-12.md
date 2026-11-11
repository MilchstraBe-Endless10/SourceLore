# 符号 + imports 打通（2026-11-12 02:35）

## 从「只出符号」到「符号+导入+导出」全出

改用官方 `js_ts_parser.parse_source`（一次产出 symbols/imports/exports/evidence_ranges），
替掉我先前手工拼的 observation。

### 修复的具体错误

之前 `observation=obs` 用的是循环外的旧变量（只含 symbols），
导致 imports/exports 被 ingest 完全忽略——`written` 只有 13 条。

改成把 `parse_source` 返回的**完整 observation** 逐文件传进去。

### 修复前后（preact 实测）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| symbols | 49 | **98** |
| imports | 0 | **36** |
| exports | 13 | **22** |
| facts | 75 | **169** |

ingest 明细：`written=94, reused=13, skipped=0`
- src/component.js 写 30
- src/diff/index.js 写 64
- src/index.js 复用 13

真实 import 样例（`query --type code`）：

```
named_import   ./constants       -> COMPONENT_DIRTY
named_import   ./constants       -> COMPONENT_FORCE
named_import   ./constants       -> MODE_HYDRATE
named_import   ./create-element  -> Fragment
```

## 补采的源文件

```
src/constants.js       1584 B
src/create-element.js  3563 B
src/options.js          587 B
```

## relation（模块关系）为什么仍是 NO_RELATIONS

`query --type relation` 读的是 `static_module_resolution` 事实，
由 `js_ts_module_resolver.resolve_js_import(import_record, source_path, tree_paths)`
把 import 说明符解析成真实路径后产生。

**实测该 resolver 本身完全正常**（用真实文件清单测试）：

```
src/component.js  ./create-element  -> LOCAL_MODULE_RESOLVED  [src/create-element.js]
src/component.js  ./diff/index      -> LOCAL_MODULE_RESOLVED  [src/diff/index.js]
src/diff/index.js ../component      -> LOCAL_MODULE_RESOLVED  [src/component.js]
src/index.js      preact            -> UNSUPPORTED_RESOLUTION_POLICY  ← 裸模块，按设计不解析
```

它唯一的前提是 `tree_paths` 要有真实文件清单，否则 `EMPTY_TREE`。
而当前树是 `ROOT_ONLY` —— **这就是 relation 为空的确切原因：树深度不够，不是 resolver 坏了。**

### 待做（已定位，不需要再摸索）

给 `tools/extract_symbols.py` 加 relation 阶段：
1. 从已采集资产收集 `tree_paths`（现有 8 个 preact 源文件）
2. 对每个 import 调 `resolve_js_import`
3. 对 `LOCAL_MODULE_RESOLVED` 的结果调 `build_relation_fact` + `ingest`
4. `query --type relation` 即应为 `RELATIONS_FOUND`

注意：`tree_paths` 只有 8 个文件时，解析出的关系也仅覆盖这 8 个文件之间的引用，
**必须在输出里如实标注覆盖面，不得暗示全仓库依赖图完整**。

---

## relation 打通（02:39）

`tools/extract_symbols.py` 已加 relation 阶段：收集已采集文件集合作 `tree_paths`，
对每个 import 调 `resolve_js_import`，成功则 `build_relation_fact` + `ingest_fact`。

**踩到的坑**：`resolve_js_import` 成功返回的字符串是 `"LOCAL_MODULE_RESOLVED"`，
但这个常量分散在 `config_aware_resolver` / `source_models` 多处、
`js_ts_module_resolver` 里没有 `RESOLVED` 属性。
试过 `RES.RESOLVED`、`CM.LOCAL_MODULE_RESOLVED` 都报 AttributeError，
**最终改用字面量 `"LOCAL_MODULE_RESOLVED"`**（已用实测确认取值）。

### 实测结果

```
relation: RELATIONS_FOUND  行=10  resolved=10

src/component.js     ./constants      -> src/constants.js
src/component.js     ./create-element -> src/create-element.js
src/component.js     ./diff/index     -> src/diff/index.js
src/component.js     ./options        -> src/options.js
src/create-element.js ./options       -> src/options.js
src/create-element.js ./constants     -> src/constants.js
src/diff/index.js    ../component     -> src/component.js
src/diff/index.js    ../constants     -> src/constants.js
src/diff/index.js    ../create-element-> src/create-element.js
src/diff/index.js    ../options       -> src/options.js
```

裸模块（如 `preact`）按设计返回 `UNSUPPORTED_RESOLUTION_POLICY`，不假装能解析。

### 覆盖面必须如实标注

`tree_paths=6`（已采集的 6 个 preact 源文件）。
这 10 条边**只覆盖这 6 个文件之间的相对引用，不代表全仓库依赖图**。
脚本输出里已带 `coverage_note` 字段说明这一点。

## 需求矩阵四项最终实测（preact）

```
code    : symbols=118  imports=36  exports=33   COVERED_BY_EXTRACTED_SOURCE
relation: RELATIONS_FOUND  行=10  resolved=10
content : README=14884B  OBSERVED
docs    : 5 篇，readme 14981B
```

四项全部有真实数据，无一项是空壳或占位。


---

## 三仓库终态（02:41）

```
is-number      sym=  2  imp=  0  exp=  0  rel=NO_RELATIONS(0)
is-plain-obj   sym=  4  imp=  0  exp=  2  rel=NO_RELATIONS(0)
preact         sym=118  imp= 36  exp= 33  rel=RELATIONS_FOUND(10)
```

### 为什么前两个没有 relation —— 不是缺陷

`is-number` 的 `index.js` 是单文件 411 B，`is-plain-obj` 的 `index.js` 是 344 B。
两个都是**单文件库，本身没有内部模块依赖**。
所以 `NO_RELATIONS` 是**如实反映事实**，不是能力缺失。
（对照：preact 有 6 个已采集源文件互引，故得 10 条边。）

### 同时修正了文档文案

`src/views/repo_miner.py` 原写「本 Commit 未做 AST 结构解析，按字面匹配」—— 已过时。
tree-sitter 接入后改为「tree-sitter 解析 + 相对路径解析；仅覆盖已采集文件」，
避免文档自称能力和实际能力不一致。
