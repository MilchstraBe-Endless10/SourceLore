# F1-D · 能力基线冻结报告

正式产物：`docs/fusion/CAPABILITY_CROSSWALK.json`
冻结清单：`docs/fusion/F1D_FREEZE_MANIFEST.json`
F2 准入：`docs/fusion/F1D_F2_ENTRY_GATES.json`

---

## 1. 冻结判定

**`FROZEN_INTERNAL_RESTRICTED`**

| 维度 | 状态 |
|---|---|
| 结构不变量 | **PASS**（身份 / canonical / 三态 / 终态 / amendment / 历史映射全部满足） |
| 可复现构建 | **PASS**（两次生成逐字节一致） |
| 分发许可门禁 | **OPEN**（B-1 / B-2 / B-3 未闭环） |

**这个判定意味着什么：**

- **内部设计基线已冻结**——75 条 canonical 与 143 项终态可以作为后续工作的权威输入。
- **不代表可以公开分发。** 三项许可/署名义务仍在。
- **不代表产品实现可用。** 产品代码 0 文件、Skill 未创建、数据库未创建。
- **不代表 F2 可以启动。** F2 需要独立批准。

**为什么不是 `FROZEN_RELEASE_READY`：** B-1（声明措辞）、B-2（U06 边界需法务）、
B-3（SL-CAP-0023 署名义务）三项均未闭环。按第 7 节要求，不得仅凭结构 20/20 自动升级。

**为什么不是 `FREEZE_BLOCKED`：** 无身份丢失、无重复映射、无未记录历史修改、
无 canonical 归属冲突、无许可权限被错误提升、可复现、Crosswalk 与裁决登记一致。

---

## 2. 正式 Crosswalk

| 项 | 值 |
|---|---|
| SHA-256 | `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b` |
| 字节数 | 355,795 |
| canonical | **75** |
| 上游身份 | **143**（含 4 项未映射的拒绝身份） |

**关键：正式文件包含 143 项全部身份，不只 139 项已映射的。**
那 4 项 `REJECTED_WITH_REASON` 在 `upstream_identities` 数组里以
`mapping_status=UNREVIEWED`、`bound_canonical_ids=[]` 保留，可取可查。

### 终态统计

| terminal_disposition | 数量 |
|---|---|
| ADOPTED | 122 |
| ADOPTED_AS_COUNTEREXAMPLE | 17 |
| REJECTED_WITH_REASON | 4 |
| DEFERRED_WITH_REASON | 0 |

### 映射进度

| mapping_status | 数量 |
|---|---|
| MAPPED | 139 |
| ROUTED | 0 |
| UNREVIEWED | 4 |

三态之和 = 143。**没有为了好看把 4 项拒绝身份改成 MAPPED。**

---

## 3. 历史完整性

| 项 | 状态 |
|---|---|
| F1-B 原始映射 | **112 项全部保持**，无一改绑到别的 canonical |
| 历史 amendment | **21 条全部保留**，逐条与草稿一致 |
| canonical ID | 1–75 连续，无跳号、无复用、无身份漂移 |
| 反例绑定 | **17 条边**，全部可定位到原始身份 |
| 独立拒绝 | **4 项**，全部 `UNREVIEWED`、`bound_canonical_ids` 为空 |

---

## 4. 六源来源与许可

| 源 | 仓库 | Commit | SPDX | copy_permitted |
|---|---|---|---|---|
| UPSTREAM-01 | jeannie-jy/repo-analyzer-skill | `b8c000f6…` | MIT | true |
| UPSTREAM-02 | bytedance/deer-flow | `44e372dd…` | MIT | true |
| UPSTREAM-03 | maboasoft/repository-discovery | `557703ff…` | **CC-BY-4.0** | true |
| UPSTREAM-04 | SNIKO/agent-skills | `a3e5e9da…` | MIT | true |
| UPSTREAM-05 | walterfan/lazy-rabbit-skills | `284971cd…` | Apache-2.0 | true |
| UPSTREAM-06 | Consensys/repo-security-review | `d5128b03…` | **无** | **false（28/28）** |

---

## 5. 三项许可/分发阻塞（**均未闭环，不得记为 PASS**）

### B-1 · 第三方声明措辞

`THIRD_PARTY_NOTICES.md` 总述句「本仓库不包含任何第三方源代码、提示词、规则文本或模板」
与事实不完全吻合——`docs/` 六份审计文档中存在上游英文原文的**引文式短句**
（按 ≥6 连续英文词统计：03 有 14 处、04 有 21 处、02 有 5 处、01/06 各 2 处、05 有 1 处）。

**核心主张属实**（产品代码、提示词、规则正文、模板确实零复制），但字面覆盖了引文。
**原计划在 F5 重写为分层表述。本轮未修订，该项保留为分发前门禁。**

### B-2 · UPSTREAM-06 权限

28 项 `copy_permitted` 全部 `false`，canonical 中**无一覆写为 true**，**零逐字命中**。

许可状态：`status=none`、`claimed=null`、`/license` 端点 404、16 文件检索
LICENSE/Copyright/SPDX/© **命中 0**、无 LICENSE/COPYING/NOTICE 文件。

**法律立场：「不是许可不明，是没有许可」**——默认著作权保留全部权利，`reuse_scope=design-only`。
抽象思想与受保护表达的边界宽度需法务判断（U06 审计 U10）。**保留人工审查事项。**

**必须说明**：字符串零命中 **不等于** 完整的法律证明。语义级改写与结构搬运无法机器判定。

### B-3 · SL-CAP-0023 署名义务

| 项 | 内容 |
|---|---|
| 引用来源 | UPSTREAM-03 `maboasoft/repository-discovery`，§12.2，commit `557703ff…` |
| 许可 | CC BY 4.0（`copy_permitted=true`，`attribution_required=true`，`license_link_required=true`） |
| 实际使用内容 | `SL-CAP-0023` description 含 6 词英文原句 `Unsupported claims MUST NOT be presented as facts` |
| 须履行义务 | ① 适当署名 ② 提供许可证链接 ③ 标明是否修改 |
| 分发前任务 | 在分发物中加入署名段落与 CC BY 4.0 链接；说明该句为引用且有改写上下文 |
| 人工复核状态 | **未复核**（`review_status=OPEN`） |

**因为 F1-D 已冻结就取消该义务——不成立。这项义务随分发行为触发，不随冻结状态消失。**

---

## 6. 八项架构裁决与 F2 门禁移交

八项 F1-C-D2 裁决（X-2 / X-4 / X-5 / X-6 / X-7 / K-7 / Y-4 / Y-6）全部写入正式 Crosswalk 的
`architecture_decisions` 数组，状态可查。

F2 准入清单 `F1D_F2_ENTRY_GATES.json` 共 **42 条**：

| 阻塞范围 | 数量 | 含义 |
|---|---|---|
| `architecture_freeze` | **0** | 结构不变量全部满足，无架构阻塞 |
| `implementation` | **39** | 阻塞正式开发中的对应实现，不阻塞内部冻结 |
| `distribution` | **3** | B-1 / B-2 / B-3，阻塞对外分发 |

状态分布：`SATISFIED_AT_FREEZE` 22（D2 的 F1 阶段门禁，已在 F1-D 复核）、
`OPEN_PENDING_F2` 17、`OPEN` 3（三条分发门禁）。

**明确区分：** 这些门禁在 F2 才实测，**不得描述为 F1 阶段已验证**。

---

## 7. 可复现性

| 项 | 结果 |
|---|---|
| 首次生成 SHA-256 | `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b` |
| 隔离目录重建 SHA-256 | `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b` |
| 逐字节一致 | **是** |
| 含时间戳 | **否**（`determinism.no_timestamps=true`） |
| 数组排序 | canonical_id 升序 / identity_key 升序 / upstream_id 升序 |

冻结输入 20 份文件逐一计算 SHA-256 并记入 manifest，复算全部一致。

---

## 8. 本轮做了什么、没做什么

**做了：**
- 生成正式 `CAPABILITY_CROSSWALK.json`（143 身份 + 75 canonical，确定性可复现）
- 生成 `F1D_FREEZE_MANIFEST.json`（含 20 份输入哈希）
- 生成 `F1D_F2_ENTRY_GATES.json`（42 条，三类阻塞范围分开）
- 独立验证器 `f1d_verify.py`（26 项，不 import 任何批次验证器）
- 本报告

**没做：**
- **未进入 F2**
- **未创建正式 Skill**（`skills/sourcelore/` 仍 0 文件）
- **未实现产品引擎**（`src/` `tests/` `schemas/` 仍 0 文件）
- **未创建数据库**
- **未安装依赖**
- **未修改运行时配置**
- **未创建远程 Release、未推送公开仓库**
- **未修订 `THIRD_PARTY_NOTICES.md`**
- **未删除草稿、历史审计或裁决记录**

---

## 9. F2 最小可执行起点（**不执行**）

按顺序：

1. **Y6-P1..P6 六个运行时探测**——H-B / H-D / H-E / H-F / H-H 及「BotHarness 能否加载 SourceLore Skill」。
   **失败即走全自建路径，不得停工。**
2. **X-5 崩溃注入与并发 CAS 实测**——契约已在 F1-C-D2 定，实现未验证。
3. 其余实现门禁按模块推进。

**启动 F2 需要用户的独立批准。本轮到此为止。**
