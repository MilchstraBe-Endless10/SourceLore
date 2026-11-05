# F2-P5G（检查点）· 基线 efd4e43 · Crosswalk 已复算匹配

## ★ 已完成：门禁 A（导入完整性）
`tools/f2p5g_import_audit.py` 四个场景全 PASS / 0 问题：
1. 从项目根 —— 15 个关键模块全部解析到 `src/<正确子目录>/`
2. 从 /tmp
3. **人为注入同名干扰模块**（decoy 目录置于 sys.path 首位，含 4 个同名 shim）
   → 仍解析到正确实现（因为 `sys.path.insert(0, p)` 逐条插入且工程路径在前）
4. **安装版 Skill 独立进程**：走 launcher 自身路径解析 → 命中工程 src

### 审计器自身踩的两个坑
- `sys.path.insert(0, [列表])` 会把整个列表当一条路径 → 必须逐条插
- 探针不能手工拼 sys.path，要走 launcher 的真实解析（否则测的是探针不是产品）

## 当前无同名模块（除 `__init__`）
但工程有 20+ 处 `sys.path.insert` + 顶层裸导入，属既有架构，不做大规模重构。

## 待做
1. src/source_analysis/ Python AST 解析（符号 + 导入 + 字节范围）
2. Source Structure Observation / Facts / Claim / Verification
3. 本地模块有界解析（5 种状态）
4. CLI `query --type code` + 源码卡片
5. 30 项源码 Gold、三层测试、全量回归

## 硬约束
- 不 exec/eval/import 被分析仓库代码
- AST col_offset 是 **UTF-8 字节**偏移，不是字符索引
- EC reason_code 是封闭码表，不可自造（D-17）
- 证据不完整只能出诊断卡

## 已完成模块（2026-11-05 23:23）
```
src/source_analysis/source_models.py       观察模型、五态、ID 生成
src/source_analysis/source_evidence.py     字节/行号定位（UTF-8 字节语义）
src/source_analysis/python_ast_parser.py   ast.parse 符号+导入
src/source_analysis/local_module_resolver.py 有界本地解析（五状态）
src/content_persistence/source_fact_ingest.py   Facts 入库
src/content_persistence/source_claim_adapter.py Claim + 裁决契约
src/content_persistence/source_knowledge_query.py 只读查询
```
tests/source_analysis/ 56 项全绿。

## 已修的真缺陷（本轮内部）
1. **方法被误判为嵌套函数**：`_in_class` 依赖的 `parent_is_class` 从未设置 →
   改为 `_ctx_of(..., parent_is_class=isinstance(child, ast.ClassDef))`
2. **装饰器取错节点**：`scope_ctx["decorators"]` 是父节点的 → 改 `_decorators_of(node)`
3. **候选匹配过宽**：前缀扫描把 `pkg/core.py` 当成 `import pkg` 的候选 →
   改精确路径构造；`from X import Y` 时子模块优先（Python 语义，非歧义）
4. **查询结果缺 repository_id** → 比对恒失败 → 补字段
5. **裁决不兼容扁平形态**：`_matches` 只认 `normalized_parameters` → 兼容两种

## 关键语义确认
- AST `col_offset` 是 **UTF-8 字节**偏移；中文注释/标识符实测正确
- `from ..x import y` → relative_level=2
- 条件导入、TYPE_CHECKING、star import、函数内导入均保留语境
- 解析失败/编码错误/二进制 → **不产生任何事实**

## 待做（剩余）
1. 30 项源码 Gold
2. CLI `query --type code`
3. 源码卡片（SOURCE_FILE / SYMBOL / IMPORT / MODULE_RELATION）
4. 三进程 E2E + 安装版 CLI 验收
5. 全量回归 + 文档 + 提交
