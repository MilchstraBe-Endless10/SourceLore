# F2-P5H 执行报告

**基线** `467603d`

## 结论

JS/JSX/TS/TSX 源码结构知识打通：`Verified Blob → tree-sitter → Observation → Fact → Claim → CLI → Card`。真实持久化、绝对字节证据、零网络，安装版 Skill 实测通过。

## 一、依赖组合（实测锁定）

| 包 | 版本 | 安装形态 | ABI |
|---|---|---|---|
| tree-sitter | 0.26.0 | cp314 wheel（原生） | — |
| tree-sitter-javascript | 0.25.0 | cp310-abi3 | 15 |
| tree-sitter-typescript | 0.23.2 | cp39-abi3 | 14 |

Python 3.14.8。安装在项目内 `.venv/`（已 gitignore），**不修改系统 Python**，不自动下载 grammar。

探针 `tools/f2p5h_parser_probe.py` 六项断言全过：grammar 加载 / Parser 构建 / 节点类型 / 字节范围 / 错误检测 / 两次一致。

## 二、JS/TS 语义

### 14 类符号

`js_function` / `js_async_function` / `js_generator_function` / `js_class` /
`js_method` / `js_object_method` / `js_variable` / `js_arrow_function` /
`js_function_expression` / `ts_interface` / `ts_type_alias` / `ts_enum` / `ts_namespace`

关键区分：
- `const start = () => {}` → **`js_arrow_function`**，不是 function declaration
- `interface I` → **`ts_interface`**，不是 class
- `function*` → **`js_generator_function`**
- 匿名 `export default function() {}` → `exported_name=None`、`anonymous=True`，**不编造名字**

### 导入/导出

导入 7 类：default / named / namespace / side-effect / `require()` 字面量 / `import()` 动态。
导出 6 类：named / default / declaration / list / re-export / export-all。

★ `require("x")` 记为 **`LITERAL_REQUIRE_CALL_OBSERVED`**（调用观察），不是 ESM 声明。
★ `require(var)` / `import(var)` → `DYNAMIC_MODULE_SPECIFIER`，不猜。
★ `import type` → `is_type_only=true`。

### 模块解析七态

本版**只支持相对路径**。裸模块、`@/alias`、`#hash` 一律 `UNSUPPORTED_RESOLUTION_POLICY`。

## 三、字节证据

tree-sitter 的 `start_byte`/`end_byte` **已是绝对字节偏移**（不像 Python AST 的 col_offset）。直接校验边界，行号用 `bisect` 从字节偏反查。

## 四、解析完整性

`PARSE_COMPLETE` / `PARSE_WITH_ERRORS` / `PARSE_UNSUPPORTED_SYNTAX` / `PARSER_UNAVAILABLE` / `SOURCE_INCOMPLETE` / `CONTENT_INTEGRITY_FAILED`

**语法错误时不产生任何权威符号/导入/导出**——实测 `function ( {` → `PARSE_WITH_ERRORS`，symbols=0。

## 五、五个真缺陷

**D-24 generator 完全丢失。** tree-sitter 用独立节点类型 `generator_function_declaration`，我只匹配 `function_declaration`。

**D-25 对象方法用 `pair` 查找无效。** tree-sitter 实际产出 `method_definition`（父节点是 `object`），不是 `pair`。

**D-26 限定名重复 `start.start`。** 变量声明自身被当作前缀。

**D-27 JS/TS 符号缺 `symbol_id`。** 同名声明无法区分，下游建不出稳定身份。

**D-28 同一节点被重复计入。** `lexical_declaration` 内外层各遍历一次。

## 六、实测

```
写入（进程1）：app.js → 5 符号 / 2 导入 / 3 导出 / 10 事实
              types.ts → 5 符号 / 1 导入 / 2 导出 / 8 事实
查询（进程2）：Commit A → Worker.run；Commit B → Worker.execute
卡片（进程3）：JAVASCRIPT_SOURCE_CARD 6980B / TYPESCRIPT_SOURCE_CARD 6571B

安装版 CLI：query --type code → sym=5 imp=2 exp=3 network=0
```

## 七、验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63 content_skill49
source_analysis88 js_ts_analysis72
= 1076 项，失败 0（保留原 1004 + 新增 72）
f1d 26/26
Crosswalk 42841207… 未变
```

## 八、门禁

| 门禁 | 状态 |
|---|---|
| A_TREE_SITTER_RUNTIME | **DONE** |
| B_JAVASCRIPT_AST | **DONE** |
| C_TYPESCRIPT_AST | **DONE** |
| D_JSX_TSX_AST | **DONE** |
| E_JS_TS_SYMBOL_SEMANTICS | **DONE** |
| F_JS_TS_IMPORT_EXPORT | **DONE** |
| G_JS_TS_MODULE_RESOLUTION | **DONE** |
| H_JS_TS_EVIDENCE | **DONE** |
| I_JS_TS_FACT_PERSISTENCE | **DONE** |
| J_JS_TS_CLAIM_VERIFICATION | **DONE** |
| K_JS_TS_RESEARCH_QUERY | **DONE** |
| L_JS_TS_KNOWLEDGE_CARDS | **DONE** |
| M_INSTALLED_SKILL_JS_TS_E2E | **DONE** |
| N_PYTHON_ANALYSIS_REGRESSION | **DONE** |
| O_MULTI_COMMIT_JS_TS_ISOLATION | **DONE** |
| P_REAL_GITHUB_JS_TS_E2E | **NOT_VERIFIED** |
| Q_NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| R_DISTRIBUTION_READY | **NOT_READY** |

证据级别：`PARSER_AVAILABLE` DONE ／ `PARSER_TESTED` DONE ／ `FACTS_PERSISTED` DONE ／
`CLAIMS_VERIFIED` DONE ／ `INSTALLED_SKILL_E2E` DONE ／ `REAL_GITHUB_E2E` **NOT_VERIFIED**

## 九、下一批

alias / bare module 解析需要 tsconfig 与 package.json exports 支持；调用图需要独立分析器，不在本轮范围。
