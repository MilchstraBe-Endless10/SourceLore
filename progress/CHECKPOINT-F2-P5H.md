# F2-P5H（检查点）· 基线 467603d · Crosswalk 已复算匹配

## ★ 最关键前置：tree-sitter 全部未安装
```
tree_sitter            NOT INSTALLED
tree_sitter_javascript NOT INSTALLED
tree_sitter_typescript NOT INSTALLED
Python 3.14.8 (GCC 16.2.1)    ← 极新，ABI = cp314
项目无 requirements/pyproject 依赖声明
```

## 本轮成败取决于一件事
**是否有 cp314 wheel**。tree-sitter 是 C 扩展（非纯 Python），
若 PyPI 无 cp314 预编译 wheel，需现场编译（可能失败或无编译器/无 Rust 工具链）。

两条路：
1. 有 wheel → 装到隔离 venv → 真实探针 → 锁定版本
2. 无 wheel 且编译失败 → **PARSER_UNAVAILABLE + 失败证据**，绝不用正则冒充

## 硬约束（禁止违反）
- 不执行被分析源码
- 不修改全局 Python（须隔离 venv）
- 不放宽许可证/分发限制
- 不把 JS/TS 卡片画成运行时调用
- 语法错误时**不从错误恢复的节点生成权威 Facts**
- JS/TS 模块解析**不套用 Python 规则**（ESM/CJS/tsconfig/exports 各异）

## 待做
1. tree-sitter 兼容探针（本轮第一道门）
2. JS/TS/JSX/TSX parser adapter
3. 符号/导入/导出规则
4. 模块解析（七态，相对路径优先）
5. 40 项 Gold、三层测试、CLI、卡片
6. 全量回归

## ★ 门禁 A 已通过（2026-11-06 00:24）
```
Python 3.14.8
tree-sitter            0.26.0   cp314 wheel 原生支持
tree-sitter-javascript 0.25.0   cp310-abi3 (稳定 ABI，可装 3.14)
tree-sitter-typescript 0.23.2   cp39-abi3
装载于隔离 venv: /tmp/sl_ts_venv
```
探针实测（tools/f2p5h_parser_probe.py）：
| 语言 | ABI | 状态 | 节点类型 |
|---|---|---|---|
| javascript | 15 | PARSE_COMPLETE | function_declaration / lexical_declaration / class_declaration |
| jsx | 15 | PARSE_COMPLETE | function_declaration |
| typescript | 14 | PARSE_COMPLETE | interface/type_alias/enum/function_declaration |
| tsx | 14 | PARSE_COMPLETE | interface/function_declaration |

确定性 ✓ 错误检测 ✓（`function ( {` → has_error=True）

## ⚠ 未解决的架构问题（本轮核心难点）
tree-sitter 只装在 **/tmp/sl_ts_venv**，但：
- SourceLore CLI 用**系统 python3**（无 tree-sitter）
- 安装版 Skill launcher 也用系统 python3

三条路：
1. 系统 python3 装（违反"不修改用户全局 Python"）
2. **项目内 venv + launcher 自动选解释器**（符合隔离要求）
3. 纯 Python 降级 → 不允许（会变成正则冒充）

倾向方案 2：仓库内建 `.venv`，launcher 检测到则用其解释器。
但需确认这是否算"修改系统环境"。

## 已完成（2026-06-06 00:27）
```
src/source_analysis/treesitter_runtime.py      runtime + 预算 + 五状态
src/source_analysis/js_ts_symbol_rules.py      14 类符号
src/source_analysis/js_ts_import_export_rules.py  10 导入 + 7 导出
src/source_analysis/js_ts_module_resolver.py   七态解析
src/source_analysis/js_ts_parser.py            统一入口
src/content_persistence/source_dispatch.py     按扩展名分派
requirements-treesitter.txt                    锁定版本
tools/f2p5h_parser_probe.py                    兼容探针
```

## 已修真缺陷（本轮 3 个）
1. **generator 丢失**：tree-sitter 用独立节点 `generator_function_declaration`，
   我只匹配 `function_declaration` → 加独立类型判断
2. **限定名重复** `start.start` / `obj.obj`：`_scope_prefix` 把变量声明自身名字当前缀
   → 变量声明作为前缀时继续向外找
3. **JS/TS 导入字段名与 Python 不同**（module_specifier vs module_name）
   → fact subject 同时记录两者

## 关键安全验证
`function ( {` → PARSE_WITH_ERRORS，**symbols=0**（语法错误不产权威事实）

## 待做
1. tests/js_ts_analysis/ 三层测试 + 40 项 Gold
2. CLI 需用项目 venv 解释器（系统 python3 无 tree-sitter）
3. 卡片 JS/TS 类型
4. 全量回归 + 提交
