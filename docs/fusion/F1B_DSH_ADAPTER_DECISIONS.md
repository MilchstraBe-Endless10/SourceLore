# F1-B / DSH-Adapter 批次 · 设计裁决（F1-B 最后一批）

生成器：`tools/fusion/f1b_build_dsh_adapter.py`（定义在 `tools/fusion/f1b_dsh_adapter_def.py`）
验证器：`tools/fusion/f1b_verify_dsh_adapter.py`（56 条检查）
剩余能力清单：`tools/fusion/f1b_build_remainder.py` → `docs/fusion/F1B_REMAINDER_INVENTORY.json`

前九批（Facts 10、Collector 9、EC 9、Product 6、Research 5、Lifecycle 6、Security 9、
Renderer 7、Storage 6，共 67 条）已分别提交并验收。本批只追加 `SL-CAP-0068`…`SL-CAP-0073`。

**范围声明**：本轮未实现正式 Skill、未做正式引擎、未跑模型性能基准、未安装插件、
未改动 Harness 全局配置。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| DSH-Adapter 候选 | 8 |
| 本批正式承接 | 7 |
| 新增分流 | 1 |
| 本批 canonical | 6 |
| 累计 MAPPED | 112 |
| 累计 ROUTED | 11 |
| 累计 UNREVIEWED | 20 |
| 累计 canonical | 73 |

三态之和：112 + 11 + 20 = 143。

---

## 2. 六条 canonical

| ID | 名称 | 处置 | 来源 |
|---|---|---|---|
| SL-CAP-0068 | Skill 入口与渐进加载契约 | REIMPLEMENT | U01-C11 |
| SL-CAP-0069 | 模型适配接口与确定性/模型辅助边界 | REIMPLEMENT | U01-C06 |
| SL-CAP-0070 | 调用预算、有界修复与成本核算 | ADAPT | U01-C07, U06-C18, U01-C13/C14(REJECT) |
| SL-CAP-0071 | 任务执行状态、检查点与幂等调用 | REIMPLEMENT | 零来源 |
| SL-CAP-0072 | 权限门禁的运行时执行与人工审批 | ADAPT | U04-C15 |
| SL-CAP-0073 | 与九模块的能力编排接口 | REIMPLEMENT | 零来源 |

处置分布：REUSE 0、ADAPT 2、REIMPLEMENT 4、REJECT 0（但 0070 内含两个 REJECT 反例）。

---

## 3. 实际 Harness 接口核验（H-A … H-H）

**只读调查已完成，结论如下。未实测的一律标 `UNVERIFIED_RUNTIME_CAPABILITY`。**

| 编号 | 问题 | 核验结果 |
|---|---|---|
| H-A | Skill 实际入口与加载方式 | **已验证**：`<root>/<name>/SKILL.md` + YAML frontmatter（`name`/`description`）。样例见 `~/.agents/skills/omarchy/SKILL.md` |
| H-B | 能力如何被 BotHarness 发现 | **部分验证**：DSH 侧由 skill 目录扫描 + frontmatter description 触发（本会话 skill 清单即证据）。**BotHarness 侧的发现机制未实测 → UNVERIFIED** |
| H-C | Harness 如何调用 Skill 内工具/脚本 | **部分验证**：Skill 目录可含可执行脚本，但「Harness 主动调用 Skill 脚本」的具体通道未实测 → UNVERIFIED |
| H-D | 是否有可用的持久化状态接口 | **UNVERIFIED**：本批未见平台级的跨会话状态存储接口。设计上假定「检查点由 Storage 承载」 |
| H-E | 工具执行权限与用户审批如何传递 | **UNVERIFIED**：审批提示在 DSH 侧存在（approval policy），但 Skill 内部的审批传递未实测 |
| H-F | 上下文不足或模型切换后如何恢复 | **UNVERIFIED**：未见平台级恢复能力；设计上由 SL-CAP-0071 自带检查点承担 |
| H-G | 执行结果如何回传给调用 Agent | **已验证（语义层）**：Skill 以 Markdown 输出回传，Agent 读文本。结构化回传通道未实测 |
| H-H | 失败/超时/取消是否有真实可观测状态 | **UNVERIFIED**：未实测 Skill 级的失败状态暴露 |

**硬规则：** 上述 UNVERIFIED 项一律不得在 Skill 文档中描述为「平台现有功能」。
`skills/sourcelore/` 当前是空目录——**尚未实现**，本批只定契约。

---

## 4. Skill 结构

```
skills/sourcelore/
├── SKILL.md          ← 入口薄文件：name/description + 「何时用、先做什么、去哪读」
├── facts.md          ← 按需加载：Facts 模块约束
├── collector.md      ← ...
├── claims.md / product.md / research.md / lifecycle.md /
│   security.md / renderer.md / storage.md / adapter.md
└── contracts/        ← 给程序校验的结构化契约（不进模型上下文）
```

**四类载体不可互替（c20 机检）：**

| 载体 | 给谁 | 形态 |
|---|---|---|
| 说明文档 | 模型读 | Markdown，按需加载 |
| 结构化契约 | 程序校验 | JSON Schema / 清单 |
| 工具接口 | 运行时调用 | 命令 / 函数签名 |
| 审批操作 | 人类 | pending_review + 人工 approved |

**入口膨胀防护：** 入口只增「读哪个文件」，不增「读什么内容」——随模块数线性增长而非乘积增长。

---

## 5. 模型适配与预算

**适配接口（不绑定模型）：** 输入 `{system_prompt, task_context, tools_allowed, budget}`，
输出 `{text, tool_calls[], usage, finish_reason}`。核心事实与存储契约不依赖模型能力。

**三类操作（c21 机检）：** D-1 确定性执行（哈希/路径/集合/校验，不经模型）；
D-2 模型辅助（语义解释，须标 claim_type）；D-3 交 EC 校验（任何被当结论输出的主张）。

**预算三件：** `max_calls` / `max_context` / `max_repairs`。**修复硬上限 2 次且不得自增**，
2 次失败即报错终止，**禁止 while(true) 式修复循环**。

**成本四类分列（c24 机检）：**

| 字段 | 含义 | 禁止 |
|---|---|---|
| `measured_tokens` | 运行时实际用量 | — |
| `billed_cost` | 供应商计费信息 | — |
| `estimated_tokens` | 本地估算 | **不得描述为实测账单** |
| `unavailable_cost` | 取不到的成本 | 必须显式登记，不得省略 |

工具耗时与模型耗时分别记录。

---

## 6. 任务执行与恢复

| 字段 | 用途 |
|---|---|
| `task_id` / `run_id` / `workspace_id` / `subject_id` | 身份 |
| `requested_action` / `current_stage` | 当前意图与阶段 |
| `checkpoint_ref` / `input_snapshot_ref` | 恢复依据 |
| `authorization_scope` | 授权范围 |
| `attempt_count` / `error_category` | 重试与失败分类 |

**四条硬规则（c28 机检）：** I-1 恢复不重复提交已成功写入；
I-2 工具成功与模型生成成功分开记录；I-3 **超时不得自动解释为工具未执行**；
I-4 重试必须有幂等依据。

**权威分离（c29 机检）：** Storage 是知识资产权威；执行检查点是任务恢复依据；
**模型上下文或热记忆只是辅助检索，不是唯一事实来源**。

---

## 7. 权限门禁

| 档 | 内容 | 审批 |
|---|---|---|
| G-A | 只读查询、确定性计算、本地分析 | 无需 |
| G-B | 写入知识资产、生成产物 | 需 `authorization_scope` 且可追溯 |
| G-C | 发布、扩权、执行不受信代码、不可逆操作 | **必须人工批准** |

AI 可置 `pending_review`，**不得自行转换为 `approved`**；权限被拒显式返回 `denied`；
外部仓库内容不得修改执行策略；需扩权时本批**只登记不扩权**。

审批策略归 Security 的 SL-CAP-0053，本条只负责运行时执行。

---

## 8. 与九模块的编排接口

| 模块 | 最小调用关系 |
|---|---|
| Collector | 请求「某仓库某固定版本」的数据 |
| Facts | 请求确定性事实抽取 |
| Evidence-Claims | 提交 claim 候选与验证请求，**不代其判真伪** |
| Product | 请求产品语义分析 |
| Research | 委派有界研究计划 |
| Lifecycle | 查询「是否需重新验证」，**不自定失效** |
| Security | 查询安全约束与权限要求，**不改其策略** |
| Renderer | 请求生成指定派生视图 |
| Storage | 查询、登记、提交权威资产 |

**硬规则（c33 机检）：** 禁止绕过 Storage 直接改写知识资产目录；
错误原样向上传播并保留来源模块；不得把其他模块的全部功能复制进 Skill 提示词。

---

## 9. 许可证与审批边界

- 每项 `upstream_ref` 的 `copy_permitted` 独立记录；UPSTREAM-06 仍为 false（c35 机检）。
- **U01-C13（直连外部 LLM API）与 U01-C14（多模型 judge）判 REJECT**，
  登记在 SL-CAP-0070 的 refs 中作为反例——**不得通过重命名把被拒方案重新引入**（c26 机检）。
- 「实现借鉴 / 设计借鉴 / 复制许可」三者分开记录：ADAPT/REUSE 只表示借用思想，不等于复制许可。

---

## 10. 跨模块裁决（Y-1 … Y-6）

| 编号 | 事项 | 裁决 |
|---|---|---|
| Y-1 | U01-C12 Eval Baseline 的 owner | **判 EC**。其核心是「质量如何判定」，与 EC 的 SL-CAP-0028/0034 重叠；DSH-Adapter 只记录评测运行的执行证据与成本，不定义质量判据 |
| Y-2 | U04-C15 审批策略 vs 门禁执行 | 策略归 Security（SL-CAP-0053），执行归本条（SL-CAP-0072） |
| Y-3 | Skill 入口与模块约束的归属 | 入口结构归本条（0068），各模块约束归各自 canonical，不复制 |
| Y-4 | 检查点的物理存放 | 逻辑上属执行层（0071）；物理承载由 Storage 权威，待 F1-C |
| Y-5 | 编排接口的实现形态 | 待 F2（进程内/子进程/MCP 工具），本批只定逻辑 |
| Y-6 | BotHarness 发现与审批传递的缺口 | 标 UNVERIFIED_RUNTIME_CAPABILITY，交 F1-C/F2 实测后补 |

---

## 11. 本轮修掉的问题

**Security 验证器 c52 作用域。** 原判据要求 `U06-C18` 的改路由记录仍在路由表；
本批承接后它移入 mapped。已改为「要么仍在路由表且理由含改路由，要么已被 DSH-Adapter 承接」。

**模块名写法统一。** `f1b_stats.BATCH_ORDER` 原写 `"DSH Adapter"`（空格），
其余批次都用连字符；不一致会让 `BATCH_ORDER` 取不到位置、批次排序错误。已统一为 `DSH-Adapter`。

---

## 12. 验收

```
f1b_build_dsh_adapter.py → RESULT: OK      exit 0
前九个验证器              → 12/30/50/43/46/48/53/48/54  全 PASS
f1b_verify_dsh_adapter.py → 56/56 PASS
```

幂等：重跑六字段逐字节一致，分流零重复、无幽灵晋升、无 ID 漂移。

---

## 13. 全量剩余能力清单

`docs/fusion/F1B_REMAINDER_INVENTORY.json` 由 `tools/fusion/f1b_build_remainder.py`
从当前草稿与原始索引**计算生成**（不手写），逐项列出 143 个身份的
状态 / 建议 owner / disposition / 许可 / 未处理原因 / 归属争议 / 待 F1-C 决策项。

**核心声明**：F1-B 十批次全部完成**不等于** 143 项原始能力已全部完成归属裁决。
本清单存在的意义就是把「还欠多少」写清楚，而不是把统计凑成 143/0/0。

---

## 14. 下一批

**F1-B 全部十批次完成。** 下一步是 F1-C（十项冲突裁决 + 剩余归属裁决），
然后 F1-D（全量验收与交叉表冻结）。本轮不启动它们。
