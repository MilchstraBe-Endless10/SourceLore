# 面向用户的自然语言问答层（answer）

用于"介绍这个项目""怎么使用""分析架构""核心函数是什么""为什么可信""检查完整性"这类自然语言提问。
只读、零网络、零写入、不执行第三方代码；答案全部来自已登记、已验证的本地字节与资产。

## 命令

```
answer <repository_id> "<问题>" [--commit <sha>]
```

默认取该仓库最新已登记快照 Commit；`--commit` 可指定固定版本。
输出含 `intent`、`blocks[]`（每块 `heading`/`body`/`refs`）、`audit`、`network_requests=0`、`wrote_assets=0`。

## 意图与返回内容

| intent | 触发问题 | 展示内容 |
|---|---|---|
| `introduce` | 介绍 / 用途 / 功能 / 概览（默认） | 项目用途、技术栈与清单、主要导出、核心实现摘录 |
| `usage` | 怎么使用 / 安装 / API / 示例 | README 的 Install/Usage/示例章节 + Manifest 清单 |
| `architecture` | 架构 / 结构 / 模块 / 依赖 / 入口 | 导出与模块指向、文件结构、依赖声明 |
| `code` | 源码 / 函数 / 类 / 导出 / 符号 | 符号表、核心实现摘录、依赖 |
| `evidence` | 为什么可信 / 证据 / 依据 | 主张与裁决、证据定位，并附 `audit` |
| `completeness` | 完整性 / 覆盖 / 检查知识库 | 覆盖说明、文件结构，并附 `audit` |

**审计字段只在 `evidence`/`completeness` 返回**；其余意图 `audit=null`，避免统计淹没普通答案。

## 操作要点

1. 先判断问题属于"内容问题"还是"盘点/审计问题"；单仓库内容问题直接用 `answer`，不要用 `inspect`+`query claims` 拼统计报告。
2. 文档需刷新时再跑 `derive <rid>`（离线，只重建 D 层派生视图，不碰 A/B/C 层）；先看 `tree_status`，ROOT_ONLY 是正常真实状态。
3. 展示答案时优先呈现 `blocks[].body`（真实正文），`refs` 用于追溯来源；不要改写正文、不要用模型推理补内容。
4. 需要证据链时才显示 `audit`；始终附 common limitations（Commit 非最新、`distribution_allowed=false`、ROOT_ONLY 子目录未采集）。

## 坑（按机制）

- **先盘点已有能力再动手建"内容理解"**：内容字节、解析器、`derive` 文档往往已存在，真正缺的常是消费层；不盘点就实现会重复建设并引入回归。核实点：`<data_root>/blobs/*.bin` 是否存在且摘要匹配、`derive` 能否产出含正文的文档。
- **内部模块被 dispatch 调用时收到 `data_root=None`，定位 blob 前必须 `data_root = data_root or DEFAULT_DATA_ROOT`**：字节在 `<data_root>/blobs/<sha256>.bin`，用 None 拼路径会失败并被误报成"内容未采集"。
- **中文提问对英文 README 标题要做中英映射**：使用/安装 → `install`/`usage`，性能 → `benchmark`，许可 → `license`；否则"怎么使用"只命中 Manifest 清单，丢掉真实的 Install/Usage 示例。
- **匿名导出不编造名字**：`module.exports = function(...)` 记成 `(anonymous function)` 并保留参数名，不推断函数名或用途。
- **核心函数摘录要逐字引用已验证字节并附行号 + blob 摘要引用**：只陈述字面代码，不推断运行行为；没有采集到字节时写"未分析"。
- **`answer` 全程只读零网络不写库**：内容已捕获时直接复用，不要为了回答去重新采集或联网。
- **`derive` 输出 `tree_status=ROOT_ONLY` 不要"修正"成 COMPLETE**：那是 P0 后的真实覆盖状态；为显得完整而回退会重新引入 ROOT_ONLY 冒充 COMPLETE 的缺陷。
- **全量回归用逐目录 `unittest discover`**：带 `__init__.py` 的包目录加 `-t .`，无包目录不加；混用会触发同名模块冲突或"Start directory is not importable"，那是运行方式问题不是逻辑回归。

## 与其他流程的边界

- 多仓库盘点、证据覆盖统计 → `references/survey-and-report.md`。
- 可信性审计、身份污染、错误否定复核 → `references/trustworthiness-audit.md`。
- 用户明确要"检查完整性/为什么可信"时才输出审计字段，否则一律内容优先。
