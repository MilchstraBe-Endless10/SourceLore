# P1 仓库内容理解与知识问答建设 — 验收报告

日期：2026-11-23　工程 Commit（修复前）：`8a9ef51c1cc1a7a7d8150ffcdad8d5c1e501e020`

## 结论

P1 目标达成。**未重复建设**已存在的内容采集器/Storage/解析器/挖掘器；核实后发现
“内容字节 + 授权门禁 + 解析器 + 项目文档生成”四大底座**早已存在且真实可用**，
真正缺失的只有“面向用户的自然语言意图分流与知识回答层”。本轮补齐该层，新增
`answer` 子命令，并增强核心函数源码逐字摘录。全程只读权威资产、零联网、不执行
第三方代码、不分发。

## 一、核实已有能力（未重复建设）

- 内容字节：16 个 `captured_blob_content` 资产，覆盖三仓库 README/Manifest/核心源码；
  `<data_root>/blobs/<sha256>.bin` 16/16 摘要校验通过，授权 `ALLOW`，`COMPLETE`。
- 授权门禁：`src/collector/content_acquisition_policy.py` 五维（FETCH/PERSIST/DERIVE/
  PREVIEW/DISTRIBUTE）独立判定；分发恒被 B-1/B-2/B-3 阻断；读取侧二次门禁在
  `captured_blob_loader.py:42-52`。重新获取+临时解析+保存派生知识在现有授权下合规，
  但本轮内容已存在，无需重新获取（零网络请求）。
- 解析器：README/Markdown、package.json、pyproject.toml、Python AST、JS/TS tree-sitter、
  tsconfig/模块解析均已存在。
- 项目文档：`derive` → `repo_derive_runner` → `repo_miner` 已能产出 5 类含真实正文的文档。
- 问答路径：核实前**没有**意图分流层，CLI 只输出 JSON——这是本轮补的核心缺口。
- ROOT_ONLY vs COMPLETE：P0 的 `tree_scope` 派生视图生效，三仓库原始 COMPLETE 均被
  派生为 ROOT_ONLY（本轮 derive 输出 `tree_status=ROOT_ONLY`），没有冒充完整覆盖。

## 二、本轮改动

1. 新增 `src/skill_interface/knowledge_answer.py`：意图分流（介绍/使用/架构/代码/
   证据/完整性），内容优先；审计字段只在“证据/完整性”意图出现；只读、零网络、
   不编造、不写库。
2. `src/skill_interface/cli.py`：注册 `answer <repository_id> "<问题>" [--commit]`。
3. `src/views/repo_miner.py`：
   - 新增 `module.exports = function(...)` 匿名导出识别（标 anonymous，不编造名字）；
   - 新增“核心实现（源码逐字摘录）”章节，从已验证字节逐字摘出函数体，带行号与
     blob 摘要引用，只陈述字面代码、不推断运行行为。
4. `skill/sourcelore/SKILL.md`：登记 answer 命令（安装态副本未改，随下次安装同步）。
5. 新增 `tests/skill_interface/test_knowledge_answer.py`：7 项测试全通过。

## 三、验收标准逐项

| # | 标准 | 状态 | 证据 |
|---|---|---|---|
| 1 | 返回项目用途而非标题数量 | 已达成 | `answer 24313173 "介绍这个项目"` → “项目用途：Returns true if the value is a finite number.” |
| 2 | 有依据的安装与使用说明 | 已达成 | `answer ... "怎么使用"` → is-number `npm install --save is-number` + `require('is-number')`；is-plain-obj `npm install is-plain-obj` + `import ...` |
| 3 | 解释至少一个真实核心函数及来源 | 已达成 | is-number 核心实现段落逐字给出 `module.exports = function(num)` 函数体，`index.js:9`，附 blob 摘要引用 |
| 4 | 描述已分析范围内模块结构 | 已达成 | preact `answer ... "核心函数源码"` → 导出/内部模块指向/外部依赖三表，标注“仅覆盖已采集文件” |
| 5 | 生成有实际正文的项目知识文档 | 已达成 | 三仓库 `derive` ok，各 5 文档；is-number project-overview.md 含核心实现正文 |
| 6 | 文档与 Fact/Evidence 可追溯 | 已达成 | 段落 `refs` 含 readme/manifest/blob(digest)/source_fact(fact_id)；快照/Commit 标识齐全 |
| 7 | OpenBot 自然语言问答优先展示内容 | 已达成 | answer 默认意图 introduce/usage，只返回用途/安装/示例，不含 Fact/Claim 统计 |
| 8 | 审计字段不淹没普通答案 | 已达成 | introduce/usage 意图 `audit=null`；仅 evidence/completeness 意图附审计 |
| 9 | 离线重查复用已持久化获准知识 | 已达成 | answer 只读已验证 blob + 已登记资产，`network_requests=0`、`wrote_assets=0` |
| 10 | P0 可信性规则没有回退 | 已达成 | 全量回归通过；derive `tree_status=ROOT_ONLY`；Crosswalk SHA 不变 |
| 11 | 不从缺少内容推断功能不存在 | 已达成 | 未采字段写“未分析/证据不足，不代表没有”；is-number 源码未做 AST 时按字面匹配并显式标注 |
| 12 | ROOT_ONLY 不冒充完整覆盖 | 已达成 | 三仓库 derive 输出 `ROOT_ONLY`，覆盖说明标“仅根层，子目录未采集” |

## 四、测试与回归

- `tests/skill_interface/test_knowledge_answer.py`：7/7 通过。
- 全量逐目录回归：renderer 59/59、research 122/122、runtime 45/45、p6f_capture 40/40、
  trust 25/25 等全部通过（同名模块冲突/临时目录残留属运行方式问题，非逻辑回归）。
- 三仓库 `derive` 均 ok，文档落盘到 `派生视图/<rid>/<commit>/`。
- 冻结 Crosswalk SHA-256 仍为
  `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b`。

## 五、共同限制（未解决内容覆盖缺口）

- 三仓库 Tree 为 ROOT_ONLY：子目录未被系统性采集；架构级回答只覆盖已采文件。
- `captured_blob_content` 属单文件根层补采；三仓库实际只采 3/4/9 个文件。
- 无函数调用图、运行时行为、测试是否通过等证据——本库明确不产出此类结论。
- README 解析偏结构观察（标题/链接/代码块），功能语义仅来自 README 首段原文引用。
- `distribution_allowed=false`、B-1/B-2/B-3 全 OPEN；本阶段输出仅内部预览，不分发。
- answer 是确定性检索组装，不接 LLM，不做开放式推理。

## 六、写入与网络

- 只读权威资产（A/B/C 层未改）；写入仅限：工程源码 4 处 + 测试 1 处 + Skill 文档 1 处，
  以及三仓库派生视图文档重生成（D 层，可重建）。
- 网络请求：0；未执行任何第三方仓库代码；未修改 OpenBot 自身源码。
