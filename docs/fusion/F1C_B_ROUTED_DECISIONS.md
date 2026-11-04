# F1-C-B · 11 项 ROUTED 全量清算

产物：
- 裁决数据 `tools/fusion/f1c_routed_decisions.py`
- 应用层 `tools/fusion/f1c_apply_routed.py`（从冻结基线重建，非打补丁）
- 只读审计 `tools/fusion/f1c_b_routed_audit.py` → `F1C_B_ROUTED_AUDIT.json`
- 清算记录 `docs/fusion/F1C_B_ROUTED_RECONCILIATION.json`
- 验收 `tools/fusion/f1c_b_verify.py`

---

## 1. 门禁一：ROUTED 数量核对

**真实集合是 11，不是 14。**

| 项 | 值 |
|---|---|
| `cross_module_redirections` 条数 | 11 |
| `global_state_counts.routed_pending_count` | 11 |
| `batches` 中各批 `raw_redirected` 之和 | 11 |
| 唯一身份 | 11（无重复） |

按当前目标 owner：

| 目标 | 数量 | 身份 |
|---|---|---|
| Evidence-Claims | **7** | U01-C12、U04-C24、U05-C04、U05-C19、U05-C24、U06-C10、U06-C20 |
| Lifecycle | **2** | U04-C16、U05-C10 |
| Renderer | **1** | U05-C14 |
| Storage | **1** | U06-C25 |

### 14 与 11 的差异来源

**数据文件正确，是我上一轮（F1-C-A）的汇报抄错了。**
`F1C_REMAINDER_BASELINE.json` 里记的就是 7/2/1/1，合计 11，可逐个数出。
汇报时把四个子数字拼成了 14——14 恰好是 F1-B 早期某时点的历史 ROUTED 峰值，属记忆串扰。

可复算：`python3 tools/fusion/f1c_b_routed_audit.py`，逐条枚举后计数即为 11。

**结论：未触发「停止应用阶段」的异常条件。**

---

## 2. 门禁二：SL-CAP-0071 交叉引用勘误

| 项 | 内容 |
|---|---|
| 原文错误 | F1-C-A 写作「与 **Storage 的** SL-CAP-0071 的「工具成功与模型生成成功分开记录」同族」 |
| 事实 | SL-CAP-0071 的 owner 是 **DSH-Adapter**（name: 任务执行状态、检查点与幂等调用） |
| Storage 的相关条目 | SL-CAP-0062（四层资产模型）、SL-CAP-0063（身份层级与版本标识）、SL-CAP-0064（原子写入）、SL-CAP-0065（派生索引与查询） |
| 修正 | Storage 侧真正支撑「完整性约束」的是 **SL-CAP-0062**（D 层不得回写权威层、单一权威副本）；SL-CAP-0071 作**跨模块依赖**引用，不得当作 Storage 自身能力举证 |
| 语义裁决 | **不变**。U06-C25 → Storage 依然成立 |

勘误已写入 `F1C_DECISION_REGISTER.json` 的 `decisions[F1C-A-001].errata_applied`。

---

## 3. 11 项逐项裁决

| # | 身份 | 目标 owner | 方向 | 落实 | 许可 |
|---|---|---|---|---|---|
| 1 | U04::C24 无法复现的外部观察标记 | EC | ADOPT_EXISTING | → SL-CAP-0020 | MIT ✓ |
| 2 | U05::C24 不可复现外部观察标记 | EC | ADOPT_EXISTING | → SL-CAP-0020 | Apache-2.0 ✓ |
| 3 | U05::C04 review_status 人机权限分离 | EC | ADOPT_EXISTING | → SL-CAP-0028（+值域约束） | Apache-2.0 ✓ |
| 4 | U06::C10 动态否证只降级到人工复核 | EC | ADOPT_EXISTING | → SL-CAP-0028 | **U06 无许可** |
| 5 | U06::C20 延迟裁决与跨仓库解析 | EC | ADOPT_EXISTING | → SL-CAP-0028 | **U06 无许可** |
| 6 | U06::C25 三态分离的产物契约 | Storage | **NEW_CANONICAL** | → **SL-CAP-0074** | **U06 无许可** |
| 7 | U04::C16 完成检查（三处） | Lifecycle | **DEFER** | 保持 ROUTED | MIT ✓ |
| 8 | U05::C10 契约式 Postconditions | Lifecycle | **DEFER** | 保持 ROUTED | Apache-2.0 ✓ |
| 9 | U05::C14 版本页脚七字段 | Renderer | ADOPT_EXISTING | → SL-CAP-0060（+呈现细则） | Apache-2.0 ✓ |
| 10 | U05::C19 人类主导的语义补充 | EC | ADOPT_EXISTING | → SL-CAP-0028（+字段级约束） | Apache-2.0 ✓ |
| 11 | U01::C12 eval baseline | EC | **DEFER** | 保持 ROUTED | MIT ✓ |

统计：**承接已有 7 项、新建 1 项、DEFER 3 项、REJECT 0 项。**

### 关键裁决理由

**U04-C24 / U05-C24 → SL-CAP-0020**
SL-CAP-0020 的强制元数据已含 `reproducible` 三态（yes|no|unknown），且 minimal 形态要求「不可复现说明」。
两身份是同一需求在上游两份审计里的独立记录，合到同一字段，不新建。

**U05-C04 → SL-CAP-0028（补值域约束）**
上游把「谁有权批准」编码进字段值域，是五源中最干净的权限边界表达。
SL-CAP-0028 已有「状态不得由作者自评决定」的骨架，本批把「approved 只能由人设、AI 永远 pending」
作为值域约束追加。

**U06-C10 / U06-C20 → SL-CAP-0028（无许可，只借思想）**
「不可验证只产生 insufficient_evidence、禁止落成 refuted」与「单仓库无法裁决是合法中间态」
分别对应 SL-CAP-0028 的硬规则与 `adjudication_blocked` 旁支状态。
**UPSTREAM-06 无复制许可，只作抽象设计来源，不复制任何规则文本。**

**U06-C25 → 新建 SL-CAP-0074（承接形态裁决）**
F1-C-A 已定 owner=Storage，本批只裁承接形态。
不并入 SL-CAP-0062 的理由：0062 讲四层读写权限与单一权威，**插入「阶段集合完整性」会混淆两个维度**。
不并入 SL-CAP-0064 的理由：0064 讲单次写入的原子性，不回答「整个 run 的产物集合是否完整」。
SL-CAP-0074 专讲「阶段产物完整性投影」，作为 0062 D 层的具体子契约。

**三条 DEFER 的理由（都不是「懒得做」，是 owner 或层级存疑）**

- **U04-C16**：分流判给 Lifecycle，但 Lifecycle 的 0040–0045 没有一条定义「任务完成判据」；
  而 DSH-Adapter 的 SL-CAP-0071 恰恰定义了任务级状态。**owner 存疑，交 F1-C-C。**
  按 F1-C-A 的教训，不擅自改 owner。
- **U05-C10**：分流理由自相矛盾——同时指向 Lifecycle 与 Storage，**违反「一个身份一个 owner」**。
  内容上最接近 SL-CAP-0064 的 W-2，但 0064 讲单次写入五步，不是通用后置条件集合。交 F1-C-C 定 owner。
- **U01-C12**：两批都把它推向 EC，但 **EC 没有任何 canonical 覆盖「评测集构建」**——指向是悬空的。
  它是方法学资产而非运行时能力，且与被 REJECT 的 U01-C13/C14（付费 API / 多模型 judge）边界相交。
  交 F1-C-C 决定「新建方法学 canonical」还是「明确拒绝」。

**本批没有为了让 ROUTED 归零而把 REJECT/DEFER 假装成映射。** 3 项 DEFER 仍保持 ROUTED 状态。

---

## 4. 应用方式：从基线重建，不是打补丁

`tools/fusion/f1c_apply_routed.py` 每次运行：

1. 从 `docs/fusion/F1B_FROZEN_BASELINE.json`（F1-B 收官快照，`git show HEAD:` 导出）读起点；
2. 叠加 `f1c_routed_decisions.py` 里**已批准**的裁决；
3. 重算 `global_state_counts` / `batches` / `routed_promotions` 去重；
4. 同步 `CROSSWALK_PROGRESS.json`。

因此**撤销或修改一项裁决后重跑，不会遗留历史路由**——不是靠手动删残留项，而是根本没有残留。

已验证：
- 运行两次，草稿逐字节一致（幂等）；
- 新 ID 从真实最大 ID 后分配（`SL-CAP-0074`，不是预置常量）；
- 同一身份不重复映射（应用前检查 `k in mapped_keys` 即抛错）。

**未修改十个旧批次的历史来源声明。** 对 canonical 的修订（SL-CAP-0028 / SL-CAP-0060）
以 `f1c_amendments` 数组留痕，不改原 description。

---

## 5. terminal_disposition 处理原则

本批按第 7 节要求：

- 3 项 DEFER **保留真实旧状态 ROUTED**，未假称 MAPPED；
- 最终处置（`DEFERRED_WITH_REASON`）已写入裁决数据与清算记录；
- 标记「等待终态迁移」，**全局状态模型调整交 F1-C-D 统一实施**；
- 本批完成标准是「11 项均有明确裁决」，不是「MAPPED 达到 123」。

---

## 6. 数字

| 项 | F1-B 收官 | F1-C-B 后 |
|---|---|---|
| MAPPED | 112 | **120** |
| ROUTED | 11 | **3** |
| UNREVIEWED | 20 | **20** |
| 合计 | 143 | **143** |
| canonical | 73 | **74** |

新建：`SL-CAP-0074`「阶段产物完整性投影（跳过阶段显式缺失，禁止空对象冒充已完成）」。

---

## 7. 本批修掉的问题

**应用层真 bug（一处）**：首版只写 Crosswalk，没有同步 `CROSSWALK_PROGRESS.json`，
导致所有验证器的「进度统计与草稿同源」检查全部失败。已把 `update_progress()` 并入应用层。

**★ 元组换行写法，本轮又踩 5 次。**
`return (expr),` 换行接字符串会被解析成单元素元组，报 `ValueError: not enough values to unpack`。
正确写法必须先算 `detail = (...)` 再 `return (cond), detail`。
这条已在 F1-C-A 记录过、本批仍重复——已加全局正则自检，写完立即扫一遍。

**历史验证器作用域（11 处，全部是「快照 vs 当前」问题）**：
各批的 `mapped` 定格断言从 `==` 改为 `>=`（后续批次合法承接只会增加）；
Storage 的 `canonical_ids` 从「完全等于本批 6 条」改为「本批 6 条全在」；
Storage `c51`/`c53` 改为「仍在路由表且正确 / 已被预期目标承接」；
DSH-Adapter `c44` 改为「清单不得陈旧」并要求重跑生成器。
**核心不变量（身份唯一性、三态守恒、许可隔离）一处未放宽。**

---

## 8. 下一步：F1-C-C

最小执行起点：

1. **先裁 3 项 DEFER 的 owner**（U04-C16、U05-C10、U01-C12）——它们卡在 owner 存疑上，
   不裁就无法定承接形态。
2. 处理 20 项 UNREVIEWED，建议从 U05 系 11 项起（量大且同源）。
3. 8 项待裁 REJECT 逐条定性（`REJECTED_WITH_REASON` vs `ADOPTED_AS_COUNTEREXAMPLE`）。
4. 十项冲突裁决（F1 原定任务）。

F1-C-D 再统一实施 `terminal_disposition` 正交字段与配套验证器，以及 `CAPABILITY_CROSSWALK.json` 冻结。
