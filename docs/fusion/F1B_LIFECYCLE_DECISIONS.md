# F1-B / Lifecycle 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_lifecycle.py`（定义在 `tools/fusion/f1b_lifecycle_def.py`）
验证器：`tools/fusion/f1b_verify_lifecycle.py`（48 条检查，只写 `F1B_LIFECYCLE_VERIFICATION.json`）

本批是 F1-B 的第六批。前五批（Facts 10、Collector 9、Evidence-Claims 9、Product 6、Research 5，
共 39 条）已分别提交并验收。本批只追加 `SL-CAP-0040`…`SL-CAP-0045`，不改写 0001–0039。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| Lifecycle 候选（优先 6 + ROUTED 承接 2 + 补充核验） | 16 |
| 本批正式承接的原始身份 | 12 |
| 判给其它模块的身份（新增分流） | 5 |
| 本批 canonical 能力 | 6 |
| 累计 MAPPED（全模块） | 66 |
| 累计 ROUTED（挂起分流） | 12 |
| 累计 UNREVIEWED | 65 |
| 累计 canonical | 45 |
| 去重比（本批 原始:canonical） | 2.0 : 1 |

三态之和校验：66 + 12 + 65 = 143。

按来源分布（本批 12 个身份）：U01 0、U02 0、U03 1、U04 7、U05 3、U06 1。

---

## 2. 六条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0040 | Subject 稳定身份与知识复用判定 | REIMPLEMENT | 必需 | U04-C02, C18, C12 |
| SL-CAP-0041 | 可变层与不可变层分离（当前可改写，历史只追加） | REIMPLEMENT | 必需 | U04-C01, C20 |
| SL-CAP-0042 | 内容哈希驱动的精确失效检测（保守降级） | REIMPLEMENT | 必需 | U05-C17（承接自分流）, U04-C19, U06-C26 |
| SL-CAP-0043 | 变更类型分类与增量重建调度 | ADAPT | 必需 | U03-C08（承接自分流）, U05-C02, C11 |
| SL-CAP-0044 | 变更影响面分析（路径 A / 路径 B 分离） | ADAPT | 必需 | U04-C17 |
| SL-CAP-0045 | 外部可变来源的新鲜度与不可复现观察保留 | REIMPLEMENT | 必需 | **零来源**（见第 6 节说明） |

处置分布：REUSE 0、ADAPT 2、REIMPLEMENT 4、REJECT 0。

---

## 3. Subject 身份六问（S-A … S-F）

### S-A Subject 的稳定身份依据是什么
三件套：`subject_key`（规范化主题标识）、`repo_binding`（`repository_id`）、`claim_scope`（断言范围）。
三者共同构成身份，任一不足以单独标识——只按主题会跨仓库误并，只按仓库会把不同主题压成一条。

### S-B Repository ID、路径、URL、Commit SHA 与 Subject ID 如何区分
`repository_id` 是 GitHub 稳定数字 ID，改名不改号，**是唯一身份锚点**；
`owner/name` 是可变的显示名；URL 是取数位置（改名即变）；`commit_sha` 是内容快照标识（随时间变）。
`subject_id` 不等于上述任何一个——它是三件套的组合结果。四者**不可互换**，尤其禁止用 URL 或
owner/name 作身份键。这是 F0 勘误 E-01「三字段不可互换」在本模块的同构延伸。

### S-C 仓库改名后是否仍属原 Subject
是。`repository_id` 不变即同一 Subject；旧记录保留，`name_history` 追加一条旧名。

### S-D Fork 与原仓库是身份延续还是关联
关联，不是延续。Fork 有自己的 `repository_id`，属独立 Subject，
通过 `forked_from` 字段关联，**不得合并**。

### S-E 如何避免同一问题在不同会话重复创建 Subject
靠确定性候选匹配先行：进入 Create 之前必须已算过候选集。
候选为空才允许 Create；候选非空时必须走 Reuse 或 Extend，或显式记录「已知候选但判为不同 Subject」的理由。

### S-F Reuse / Extend / Create 各需哪些可检查条件
硬顺序：`subject_key` 精确匹配 → Reuse；`claim_scope` 包含关系 → Extend；两者皆无 → Create。
上游那四个主观短语（plausibly covers / already answers it / is still valid / no existing subject covers it）
**不得作为唯一判据**——它们只能出现在模型辅助判断那一段，且该判断不得被记录为「已通过确定性身份校验」。

---

## 4. 知识状态三轴正交

| 轴 | 取值范围 | 答什么 | 归属 |
|---|---|---|---|
| 任务执行状态 | running / succeeded / failed / paused / resumed | 这次更新跑完了没有 | Lifecycle（本条） |
| 知识有效性状态 | verified / needs_revalidation / dependency_changed / source_removed / detection_incomplete | 现有知识对当前目标版本还成立吗 | Lifecycle（SL-CAP-0042） |
| Claim 验证状态 | supported / refuted / insufficient / conflict | 这条主张本身算不算成立 | Evidence-Claims（SL-CAP-0028） |

**三条硬规则：**
1. 不得把任务失败当作知识失效。任务 `failed` 只影响执行轴，不触发任何 validity 迁移。
2. 不得把新鲜度变化自动映射成 `refuted`。`dependency_changed` 只进重验证队列，
   claim 的 supported/refuted 仍归 EC 判定。
3. 不得因为重新验证未完成就删除已有证据支持的旧结论。

**旧结论对旧版本成立与否，与它对新版本是否成立，是两个不同问题。**
前者是历史事实，不可撤销；后者是当前判定，可变。把它们压成一个布尔值就是本批要防的核心错误。

---

## 5. 精确失效检测设计

依赖链：`claim → evidence_refs[]`，`evidence → {path, content_hash}`。

| 变化情形 | 判定 | 动作 |
|---|---|---|
| 路径内容未变 | `unchanged` | 直接重用，不重验 |
| 路径内容已变 | `dependency_changed` | 进重验证队列，不改 claim 状态 |
| 路径已删除 | `source_removed` | 进重验证队列 + 记录来源消失 |
| 路径已重命名 | `path_moved` | 追踪到新路径，保留旧路径以便追溯 |
| 变化集不完整 | `detection_incomplete` | 降级并附未覆盖范围，**禁止输出「已知依赖未变」** |

三条原则：
- 只有变化集完整且依赖登记充分时，才能作出「已知依赖未变」。
- 不得把「旧文件哈希未变」扩大解释为「产品功能未变」——功能可能由未登记为依赖的
  配置、路由表、生成脚本驱动。
- 不得用 mtime 作判据。上游 `check_pkb_staleness.py` 正是用 mtime 与归档时间差比对，
  单向下界（src_mtime <= doc_mtime 直接 continue），mtime 被 reset 或文件被回退就完全看不见。

### 路径 A 与路径 B
- **路径 A（已知依赖检测）**：以 claim 登记的 evidence 依赖为起点，定位受影响的既有 claim。
- **路径 B（新事实发现）**：以变化集本身为起点，识别新增文件/路由/配置/依赖及清单外变化。
两条共享同一份 Collector 变化元数据，但起点、判据、产物不同。
**路径 A 的「未受影响」不能替代路径 B 的「无新事实」。**

---

## 6. 历史与当前理解

| 问题 | 裁决 |
|---|---|
| 历史 Findings/Evidence 是否不可变 | 是，只追加，永不覆盖或删除 |
| 当前有效 Claim 如何指向历史 | 通过 `prev_version_ref` 链与 `snapshot_boundary` |
| 新 Claim 如何 supersede 旧 Claim | 写 `superseded_by` 标记；标记只作用于当前视图，不修改历史记录 |
| 纠正与否定是否相同 | 不同。纠正 = 新版本替换当前视图；否定 = 旧结论被标记 disputed/refuted，历史仍在 |
| 同一 Subject 内矛盾如何处理 | 允许并存，标 `conflict`，移交 EC 裁决；不得静默择一 |
| 是否允许多条互相冲突的历史 Claim 共存 | 允许。冲突是知识状态，不是错误 |
| 恢复到旧版本如何确定边界 | 以该版本的 `snapshot_boundary` 为界；恢复是「生成指向旧版本的新视图」，不是抹掉记录 |

**不得因为结论被取代就删除旧证据。不得由 Renderer 直接覆盖历史记录。**
版本写入、事务、并发控制与物理存储由 Storage 实现，本批只定义语义契约与所需原子性。

### 关于 SL-CAP-0045 的零来源
本条无上游来源，原因写在此处以免误读：
- `U04-C24` 与 `U05-C24`（不可复现外部观察的字段缺失）**已由 Research 批次判定归入 Evidence-Claims**，
  当前仍在路由表、未被承接；本批不重复占用，归属以 EC 批次为准。
- `U06-C26` 已由 SL-CAP-0042 承接，同一原始身份只能正式映射一次。
- 剩下的内容（按可变性给来源分类、`verified_against_commit` 只对 commit 固定的源码有效、
  `retrieved_at` 只证明取回时刻、TTL/ETag 只能作辅助、不可复现观察永不被判 stale 只标
  `unverifiable_since`）是六源中没有任何一处提供过的自建语义，属**零来源独立设计**。

### 关于 U06-C26 的特别说明
U06-C26 在原始索引中的 `where` 字段标注为「缺失」——它描述的是上游**没有**的东西
（上游做的是「对某个 commit 扫一遍」，产物与 commit 绑定但没有回取与失效机制）。
本批只把它作为「SourceLore 必须独立设计」的**需求来源**，
**不得宣称上游已提供相应实现**。这条已写入 SL-CAP-0042 的 merge_note，由 c31 机检。

---

## 7. 增量重建与恢复

| 变化 | 动作 | 判定来源 |
|---|---|---|
| commit 前进且变化集非空 / 外部来源需重取 | `recollect` | 确定性 |
| 文件内容变但事实抽取结果未变 | `revalidate` | 确定性 + 模型辅助 |
| 知识未变、仅模板/呈现层变化 | `rerender` | 确定性 |
| 实体/流程定义被推翻 | `reanalyze` | 模型辅助 |
| 索引需重建 | `reindex` | 确定性（索引是派生视图） |
| 涉及人工业务解释 / 无法归类 | 人工补充判断 | **人工审批** |

三类判定来源必须显式标注（`decision_class`），且每次调度记录写明本次归属依据属于哪一类。

**三重分工不得混淆：**
- 研究任务中断后的恢复位置 → **Research**（SL-CAP-0035 的 `resume_point`）
- 知识需要重新验证的触发 → **Lifecycle**（本条与 SL-CAP-0042）
- 底层崩溃恢复与原子写入 → **Storage**

---

## 8. 新鲜度与外部来源分类

| 来源类型 | 新鲜度凭据 | 可否判 stale |
|---|---|---|
| Git commit 固定的不可变源码 | commit_sha + content_hash | 可（可精确复算） |
| 可变 Issue/PR/Release | retrieved_at（+ ETag/Last-Modified 辅助） | 仅辅助，不足时降为 `retrieved_at_only` |
| 外部网页/API | retrieved_at，同上 | 同上 |
| 不可复现观察 | — | **永不判 stale**，只标 `unverifiable_since` |
| 人工补充业务解释 | who/what/when | 不参与哈希复算 |

三条硬规则：
1. `verified_against_commit` 不是通用外部信息新鲜度凭据——只对 commit 固定的源码有效。
2. `retrieved_at` 只能证明何时取回，不能证明内容现在仍正确。
3. TTL / ETag / Last-Modified 只能作验证辅助，不得伪造来源支持。

---

## 9. 跨模块 unresolved（本批登记，不擅自更改）

| 编号 | 边界 | 归属 |
|---|---|---|
| X-1 | EC 的 Claim 有效性字段与本条的知识有效性字段如何避免双写 | F2 / F1-C |
| X-2 | Research 的 `resume_point` 与本条的重验证触发接口 | F1-C |
| X-3 | Facts 的 Canonical Knowledge Registry 与长期 Subject 身份的关系 | **F2（需裁决）** |
| X-4 | Storage 对不可变历史与当前视图的实际写入责任 | Storage 批次 |
| X-5 | Renderer 对派生索引与叙事页的更新权限 | Renderer 批次 |
| X-6 | Security 风险发现何时因变更必须重新验证 | Security 批次 |

**如果先前模块的能力归属需要调整，一律记入 F1-C 裁决事项，不得为让本批通过而静默重写已提交的
canonical。** 本批未改动任何 SL-CAP-0001…0039 的字段。

---

## 10. 验收

```
python3 tools/fusion/f1b_build_lifecycle.py     → RESULT: OK      exit 0
python3 tools/fusion/f1b_verify.py              → 12/12 PASS      exit 0
python3 tools/fusion/f1b_verify_collector.py    → 30/30 PASS      exit 0
python3 tools/fusion/f1b_verify_ec.py           → 50/50 PASS      exit 0
python3 tools/fusion/f1b_verify_product.py      → 43/43 PASS      exit 0
python3 tools/fusion/f1b_verify_research.py     → 46/46 PASS      exit 0
python3 tools/fusion/f1b_verify_lifecycle.py    → 48/48 PASS      exit 0
```

### 本轮修正的作用域错误（三处，均非数据缺陷）

Product 验证器因本批承接了它曾推出去的分流而报红三处：

1. **c14 批次出向计数** —— 原判据要求 `redirected == 2`。但出向按统计契约是现算视图
   （def 声明 − 已晋升），Lifecycle 接手 `U03-C08` 后必然降为 1。改为「与现算自洽」。
2. **c38 历史批次定格** —— 同上，`redirected` 不再是 2。mapped 仍定格为 10。
3. **c43 新增分流去向** —— 原判据要求两条都在路由表里。下游承接后它们会移入 mapped，
   这是晋升的正常结果。改为「要么仍在路由表且去向正确，要么已被预期目标模块承接（有晋升记录可查）」。

三处收窄都不放宽核心不变量（身份唯一、三态守恒、许可隔离、mapped 定格），
只是把「历史必须等于现在」这条不可能成立的要求去掉。

### 幂等性

`f1b_build_lifecycle.py` 重跑后六个核心字段逐字节一致，已实测。

---

## 11. 下一批

F1-B 剩余四个模块：Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0046` 起。

本批未启动 F2，未修改正式分析引擎，未处理其余四个模块。
