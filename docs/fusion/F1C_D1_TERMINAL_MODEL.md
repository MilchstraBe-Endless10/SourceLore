# F1-C-D1 · 终态模型迁移

产物：
- 推导模块 `tools/fusion/f1c_terminal_model.py`（纯函数，由应用链调用）
- 迁移工具 `tools/fusion/f1c_d1_migrate_terminal.py`（薄封装：跑应用链 + 导出快照）
- 迁移记录 `docs/fusion/F1C_D1_TERMINAL_MIGRATION.json`
- 验收 `tools/fusion/f1c_d1_verify.py`

---

## 1. 三个正交概念

| 概念 | 字段 | 表达什么 | 取值 |
|---|---|---|---|
| **A 融合进度** | `mapping_status` | 该身份在融合流程中走到哪一步 | MAPPED / ROUTED / UNREVIEWED |
| **B 设计终态** | `terminal_disposition` | SourceLore 对该原始能力作出的最终设计处置 | ADOPTED / ADOPTED_AS_COUNTEREXAMPLE / REJECTED_WITH_REASON / DEFERRED_WITH_REASON |
| **C 来源性质** | `canonical_origin_type` | 该 canonical 的来源性质 | UPSTREAM_DERIVED / INTERNAL_DESIGN_ONLY |

**三条正交律（写入 `terminal_model.laws`）：**

1. 终态与 `mapping_status` 正交：`REJECTED_WITH_REASON` 可以对应 `UNREVIEWED`，**不伪造 MAPPED**。
2. 终态与复制权限正交：`ADOPTED` **不推导** `copy_permitted`；UPSTREAM-06 仍为 `false`。
3. `ADOPTED_AS_COUNTEREXAMPLE` 只表示把被拒机制当作反面约束，**不表示采纳其行为**。
4. `INTERNAL_DESIGN_ONLY` 是 **canonical 的来源性质**，不强制赋给任何上游身份。

**特别注意：** 前轮草案里的 `INTERNAL_DESIGN_ONLY` 曾被误当作上游身份终态之一。本批已纠正——
它是 C 字段的取值，不是 B 字段的取值。上游身份终态只有四个值。

---

## 2. 推导方式（不手填）

**核心决定：终态推导并入应用链，而不是独立后置步骤。**

第一版把终态写在独立迁移工具里，结果任何验证器重跑应用链都会把它冲掉——
`f1c_b_verify` 的幂等检查当场就红了。这不是验证器的错，是架构的错：
终态是「draft 的派生属性」，必须与应用链同生同灭。

修正后的结构：

```
f1c_apply_routed.py
  ↓ 重建（基线 → F1-C-B → C1 → C2 → C3）
  ↓ recompute（三态、批次、晋升）
  ↓ f1c_terminal_model.derive(draft, raw, decided_reject)   ← 终态在此推导
  ↓ 写盘（draft 含 terminal_model / origin_type / 分布计数）
```

因此任何重跑（含各验证器的幂等检查）都会重新生成终态，**不存在丢失可能**。

`f1c_d1_migrate_terminal.py` 退化为薄封装：跑一次应用链，把终态导出成独立快照文件供审计。

**推导规则（纯函数，遍历前显式排序，不依赖 dict 顺序）：**

| 情形 | terminal_disposition | role |
|---|---|---|
| 在 mapped，且 refs 中只有非 REJECT verdict | `ADOPTED` | positive |
| 在 mapped，且 refs 中只有 REJECT verdict | `ADOPTED_AS_COUNTEREXAMPLE` | counterexample |
| 在 mapped，且同时有两种（理论上存在，本批实际 0 例） | `ADOPTED` | mixed |
| 在 routed | `DEFERRED_WITH_REASON` | positive |
| 不在 mapped/routed，但有拒绝裁决 | `REJECTED_WITH_REASON` | counterexample |
| 以上都不是 | **抛错终止**，不默认 ADOPTED | — |

---

## 3. 143 项最终处置分类统计

| 终态 | 数量 | 说明 |
|---|---|---|
| `ADOPTED` | **122** | 以非 REJECT verdict 正向承接 |
| `ADOPTED_AS_COUNTEREXAMPLE` | **17** | 仅以 REJECT verdict 登记为反例，未采纳其行为 |
| `REJECTED_WITH_REASON` | **4** | 已裁决拒绝，未建立任何 canonical 关联 |
| `DEFERRED_WITH_REASON` | **0** | 无残留延期 |
| **合计** | **143** | |

角色分布：`positive` 122、`counterexample` 21（17 纯反例 + 4 拒绝）。

映射进度（保持不变）：MAPPED **139** / ROUTED **0** / UNREVIEWED **4** = 143。

---

## 4. 4 项 REJECT 的迁移结果

| 身份 | 原始 disposition | 终态 | mapping_status | copy_permitted |
|---|---|---|---|---|
| `U04::C27` HTML/excalidraw 产物格式 | REJECT | `REJECTED_WITH_REASON` | UNREVIEWED | true（但机制不采纳） |
| `U05::C27` 整册项目文档 | REJECT | `REJECTED_WITH_REASON` | UNREVIEWED | true（但机制不采纳） |
| `U05::C28` 双语 Sphinx | REJECT | `REJECTED_WITH_REASON` | UNREVIEWED | true（但机制不采纳） |
| `U06::C21` 模型分层 | REJECT | `REJECTED_WITH_REASON` | UNREVIEWED | **false** |

八项要求逐条满足：

1. 保留真实原始身份 ✓
2. 保留 `upstream_disposition`（四条均为 REJECT，未被改写）✓
3. 保留拒绝理由（各批裁决记录中的 `reason`）✓
4. 设 `terminal_disposition = REJECTED_WITH_REASON` ✓
5. 不强制创建 canonical（四条均无 canonical 关联）✓
6. 不伪造 MAPPED（`mapping_status` 仍为 UNREVIEWED）✓
7. 不擦除历史 UNREVIEWED 状态 ✓
8. 记录为「已裁决、尚未映射」的合法组合 ✓

**未来若要改判其中一条为反例约束**，必须通过正式的裁决迁移记录修改终态或关联角色，不得静默修改。

---

## 5. 反例绑定的实际数量与含义

**17 项**原始身份仅以 `verdict=REJECT` 绑定到 canonical，不采纳其行为。
另有 **4 项** REJECTED_WITH_REASON 完全未绑定。合计 `counterexample` 角色 **21 项**。

反例绑定明细（canonical ← 身份）：

| canonical | 反例身份 |
|---|---|
| SL-CAP-0001 | U03-C25 |
| SL-CAP-0011 | U01-C15、U02-C18 |
| SL-CAP-0015 | U02-C09 |
| SL-CAP-0017 | U02-C08 |
| SL-CAP-0018 | U06-C13 |
| SL-CAP-0037 | U03-C23 |
| SL-CAP-0038 | U02-C15、U03-C27、U04-C26 |
| SL-CAP-0051 | U06-C28 |
| SL-CAP-0055 | U03-C26 |
| SL-CAP-0057 | U03-C24 |
| SL-CAP-0067 | U04-C25、U05-C26 |
| SL-CAP-0070 | U01-C13、U01-C14 |

**两处「上游 disposition 与 SourceLore verdict 反向」的个案已在迁移记录里显式标注（不静默）：**

| 身份 | 上游 disposition | SourceLore verdict | 说明 |
|---|---|---|---|
| `U06::C13` Semgrep 三层规则集 | ADAPT | **REJECT** | 上游认为可改，SourceLore 判为不可采纳（无许可 + 架构不兼容） |
| `U02::C17` Mermaid 硬要求 | REJECT | **REIMPLEMENT** | 上游拒绝的是「强制出图机制」，SourceLore 保留「可选图表」（SL-CAP-0057） |

这两个字段**必须独立**：全 143 项中有大量取值不同（`c10` 检查即验证「不全是复制」）。

---

## 6. 75 条 canonical 的来源性质

| origin_type | 数量 |
|---|---|
| `UPSTREAM_DERIVED` | **68** |
| `INTERNAL_DESIGN_ONLY` | **7** |

**零上游来源的 7 条（实际枚举，非写死）：**

| ID | owner | 名称 |
|---|---|---|
| SL-CAP-0013 | Collector | Commit 与根 Tree 的钉定（三字段分列） |
| SL-CAP-0019 | Collector | 统一只读数据接口 |
| SL-CAP-0045 | Lifecycle | 外部可变来源的新鲜度与不可复现观察保留 |
| SL-CAP-0047 | Security | 安全发现契约与四项独立检查 |
| SL-CAP-0061 | Renderer | 呈现安全转义与发布前检查 |
| SL-CAP-0063 | Storage | 身份层级与版本标识 |
| SL-CAP-0073 | DSH-Adapter | 与九模块的能力编排接口 |

每条均已具备：`origin_type`、内部需求依据（取 `merge_note`）、所属 owner、设计理由、
与其他模块的依赖。**未为零来源能力虚构 upstream_ref。**

完整质量审查留待 **F1-C-D3**。

---

## 7. 兼容性改动（第 7 节）

`mapping_status` 三态**未删除、未重定义**。新增的 `terminal_disposition` 与 `origin_type` 是正交字段。

**受影响的旧验证器（5 个）：** 它们的幂等检查使用「草稿逐字节比对」，
而 D1 之后草稿多了 `terminal_model` / `origin_type` / 分布计数字段，
这些由应用链内的终态推导产生，逐字节比对必然误判。

**改造方式（最小化）：** 抽出 `_core_fields(doc)` 辅助函数，只比较应用链负责的六个核心字段
（`canonical_capabilities` / `cross_module_redirections` / `routed_promotions` /
`batches` / `global_state_counts` / `module_rollup`）。

> **这不是放宽判据，是划清职责边界**：这六个字段是应用链的产物，幂等性应当针对它们断言；
> 终态字段也由应用链产生，但它属于 D1 的迁移契约，其幂等性由 `f1c_d1_verify` 的 c16 独立断言。

**未放宽任何核心不变量：** 身份唯一性、三态守恒、许可证隔离、历史迁移留痕全部保持原判据。

---

## 8. 数字总表

| 项 | F1-C-C3 后 | 本批后 |
|---|---|---|
| 原始身份 | 143 | 143 |
| MAPPED | 139 | **139**（未变） |
| ROUTED | 0 | 0 |
| UNREVIEWED | 4 | **4**（未变） |
| canonical | 75 | **75**（未变） |
| 终态覆盖 | — | **143 / 143** |
| ADOPTED | — | **122** |
| ADOPTED_AS_COUNTEREXAMPLE | — | **17** |
| REJECTED_WITH_REASON | — | **4** |
| DEFERRED_WITH_REASON | — | **0** |

---

## 9. 下一步：F1-C-D2

可执行起点：

1. **跨模块冲突总审**（8 项待议：X-2 / X-4 / X-5 / X-6 / X-7 / K-7 / Y-4 / Y-6）——
   清单在 `F1C_D_HANDOFF_INVENTORY.json` 的 `cross_module_conflicts_open`。
2. 复审两处「上游 disposition 与 verdict 反向」的个案（`U06-C13`、`U02-C17`），
   确认该表述已足够，或需在裁决登记中补记。
3. 核验 21 项反例绑定的许可证陈述（特别是 U06 两处零复制）。

**零来源 canonical 的质量审查留 F1-C-D3。**
**`CAPABILITY_CROSSWALK.json` 的冻结留 F1-D，本批未生成。**
