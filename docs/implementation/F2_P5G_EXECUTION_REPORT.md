# F2-P5G 执行报告

**基线** `efd4e43`

## 结论

Python 源码结构知识打通：`Blob → ast.parse → Observation → Fact → Claim → Verification → CLI → Card`。真实持久化、精确字节证据、零网络。

JS/TS 保持 **NOT_IMPLEMENTED**——没有可靠 AST 解析器，按任务书要求不用正则凑数。

## 一、导入完整性（门禁 A）

`tools/f2p5g_import_audit.py` 四场景全部 0 问题：

| 场景 | 结果 |
|---|---|
| 项目根 | 15 个关键模块全部命中正确 `src/` 子目录 |
| 从 `/tmp` | 同上 |
| **人为注入同名干扰模块** | 仍解析到正确实现 |
| **安装版 Skill 独立进程** | 走 launcher 自身路径解析，命中工程 src |

这是 D-7 / D-15 类事故的结构性防线。

### 审计器自身踩的坑
- `sys.path.insert(0, [列表])` 会把整个列表当一条路径 → 必须逐条插入
- 探针不能手工拼 sys.path，要走 launcher 的真实解析，否则测的是探针不是产品

## 二、Python AST 能力

用标准库 `ast.parse`。**绝不 exec / eval / import / 跑测试 / shell**。

支持：Module / ClassDef / FunctionDef / AsyncFunctionDef / 方法 / 异步方法 / 嵌套函数 / 静态导入。

### 三个真缺陷

**D-19 方法被误判为嵌套函数。**
`_in_class` 依赖的 `parent_is_class` 从未设置——`Worker.run` 报成 `nested_function`。
改为 `_ctx_of(..., parent_is_class=isinstance(child, ast.ClassDef))`。

**D-20 装饰器取父节点。**
`scope_ctx["decorators"]` 是父节点的装饰器，`@staticmethod` 全部丢失。
改为 `_decorators_of(node)` 读节点自身。

**D-21 模块候选匹配过宽。**
`import pkg` 把 `pkg/core.py` 也算候选 → 假歧义。改精确路径构造；
`from X import Y` 时子模块优先（这是 Python 语义，不是歧义）。

## 三、字节证据

**AST `col_offset` 是 UTF-8 字节偏移，不是字符索引。** 这是最容易出错的地方。

`source_evidence.py` 按行累加真实字节长度换算绝对偏移，正确处理 LF / CRLF / 单独 CR / BOM。

实测：中文注释行、中文标识符 `def 函数()`、CRLF 文件——字节范围都精确对应声明。

每条符号/导入带 `byte_range + line_range + snippet_sha256`，label 只放结构化描述（`symbol:kind@L起-止`），不回显原文（D-6 规则）。

## 四、本地模块解析

五态：`LOCAL_MODULE_RESOLVED` / `EXTERNAL_OR_UNRESOLVED` / `AMBIGUOUS_CANDIDATES` / `INSUFFICIENT_TREE_COVERAGE` / `UNSUPPORTED_IMPORT_FORM`。

只在**当前 Commit 已登记 Tree** 内找候选；绝不跨 Commit 补全，绝不看本机已安装包。

**不建虚假依赖图**：无调用图、无数据流图、无动态分派。

## 五、实测

安装版 CLI（`~/.agents/skills/sourcelore/`）：

```
query 990001 --commit <A> --type code --path app.py
→ state=FOUND symbols=6 imports=5 network=0
   class Worker L14-22 / method Worker.build / method Worker.run
   async_function fetch / function outer / nested_function outer.inner

query ... --symbol Worker.run → hits=1
query ... --module os        → imports=1
card --repository-id 990001 --commit <A> --path app.py --code
→ SOURCE_FILE_CARD 6556 bytes, network=0
```

双 Commit：A=`Worker.run`，B=`Worker.execute`，各自 11 条事实，互不污染。

## 六、验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63 content_skill49 source_analysis88
= 1004 项，失败 0
f1d 26/26
Crosswalk 42841207… 未变
```

## 七、门禁

| 门禁 | 状态 |
|---|---|
| A_PACKAGE_IMPORT_INTEGRITY | **DONE** |
| B_PYTHON_AST_EXTRACTION | **DONE** |
| C_SOURCE_EVIDENCE_VERIFIED | **DONE** |
| D_SOURCE_FACT_PERSISTENCE | **DONE** |
| E_SOURCE_CLAIM_VERIFICATION | **DONE** |
| F_LOCAL_MODULE_RESOLUTION | **DONE** |
| G_SOURCE_RESEARCH_QUERY | **DONE** |
| H_SOURCE_KNOWLEDGE_CARDS | **DONE** |
| I_INSTALLED_SKILL_SOURCE_E2E | **DONE** |
| J_MULTI_COMMIT_SOURCE_ISOLATION | **DONE** |
| K_JS_TS_PARSER | **NOT_IMPLEMENTED** |
| L_REAL_GITHUB_SOURCE_E2E | **NOT_VERIFIED** |
| M_NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| N_DISTRIBUTION_READY | **NOT_READY** |

## 八、下一批

JS/TS 需要先解决可靠解析器（tree-sitter 固定版本）；跨语言调用关系需要独立分析器，不在本轮范围。
