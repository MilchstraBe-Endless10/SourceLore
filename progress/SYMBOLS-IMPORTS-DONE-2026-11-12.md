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
