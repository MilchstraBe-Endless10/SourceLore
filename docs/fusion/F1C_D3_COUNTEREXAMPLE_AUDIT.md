# F1-C-D3 · 反例角色专项审计

产物：`tools/fusion/f1c_d3_review.py` → `F1C_D3_COUNTEREXAMPLE_AUDIT.json` +
`F1C_D3_PROVENANCE_LICENSE_AUDIT.json`

---

## 1. 先说清统计口径

| 项 | 实测 |
|---|---|
| `ADOPTED_AS_COUNTEREXAMPLE` 唯一身份 | **17** |
| 实际 `identity → canonical` 的 `verdict=REJECT` 关联边 | **17**（一对一） |
| `REJECTED_WITH_REASON` 且**无任何绑定** | **4** |
| counterexample **角色**合计 | **21** |

**没有边就没有绑定。** 4 项拒绝身份虽 `role=counterexample`（表示其机制可作反面参照），
但未与任何 canonical 建立关联，**不能计入「反例绑定」数量**。

---

## 2. 17 项反例绑定

| 身份 | 上游处置 | 绑定 canonical | 许可 |
|---|---|---|---|
| `U01::C13` | REJECT | SL-CAP-0070 | MIT（可复制，未复制） |
| `U01::C14` | REJECT | SL-CAP-0070 | MIT（可复制，未复制） |
| `U01::C15` | REJECT | SL-CAP-0011 | MIT |
| `U02::C08` | REJECT | SL-CAP-0017 | MIT |
| `U02::C09` | REJECT | SL-CAP-0015 | MIT |
| `U02::C15` | REJECT | SL-CAP-0038 | MIT |
| `U02::C18` | REJECT | SL-CAP-0011 | MIT |
| `U03::C23` | REJECT | SL-CAP-0037 | CC BY 4.0（须署名） |
| `U03::C24` | REJECT | SL-CAP-0057 | CC BY 4.0（须署名） |
| `U03::C25` | REJECT | SL-CAP-0001 | CC BY 4.0（须署名） |
| `U03::C26` | REJECT | SL-CAP-0055 | CC BY 4.0（须署名） |
| `U03::C27` | REJECT | SL-CAP-0038 | CC BY 4.0（须署名） |
| `U04::C25` | REJECT | SL-CAP-0067 | MIT |
| `U04::C26` | REJECT | SL-CAP-0038 | MIT |
| `U05::C26` | REJECT | SL-CAP-0067 | Apache-2.0 |
| `U06::C13` | **ADAPT** | SL-CAP-0018 | **U06 无许可（零复制）** |
| `U06::C28` | REJECT | SL-CAP-0051 | **U06 无许可（零复制）** |

**唯一一处上游 disposition 与 SourceLore verdict 相反的是 `U06::C13`**
（上游 ADAPT → SourceLore REJECT），已在 F1-C-D2 §8 给出独立理由。

---

## 3. 4 项无绑定的拒绝身份

| 身份 | 能力 | 处置 |
|---|---|---|
| `U04::C27` | HTML/excalidraw 等具体产物格式 | REJECTED_WITH_REASON |
| `U05::C27` | 产出面向人类的整册项目文档 | REJECTED_WITH_REASON |
| `U05::C28` | 双语 Sphinx 站与 gettext 流程 | REJECTED_WITH_REASON |
| `U06::C21` | 模型分层（Deep / Standard） | REJECTED_WITH_REASON |

四项**均无 canonical 关联**，`mapping_status` 仍为 `UNREVIEWED`，未伪造 MAPPED。

---

## 4. ★ 复活检查：被拒机制没有换名字重新进来

这是本节最重要的一项——不能只查 `verdict=REJECT` 是否存在，必须查机制有没有从别的门进来。

| 被拒机制 | 来源 | 守卫 canonical | 结果 |
|---|---|---|---|
| 强制图表成为完成门禁 | U02::C17 / U03::C24 | SL-CAP-0057 | **PASS**（含「图表不是完成判据」，无「必须出图」） |
| 外部付费 API / 多模型 judge | U01::C13 / U01::C14 | SL-CAP-0075 | **PASS**（含「V1 不使用任何付费 API」，无「接入外部 LLM API」） |
| 知识库驻留被路径别名绕过隔离 | U05::C28 同源 | SL-CAP-0067 | **PASS**（含「根目录显式声明」，无「默认当前工作目录」） |
| 证据优先级替代验证规则 | U03::C23 | SL-CAP-0037 | **PASS**（含「来源类型不构成真伪排序」，无「优先级决定真伪」） |
| 不可验证即否证 | U03::C25 | SL-CAP-0028 | **PASS**（含「不可验证只产生 insufficient_evidence」，无「无法证明即已证伪」） |

**五项全部 PASS。** 被拒机制没有借新名称复活。

---

## 5. 实际复用情况

| 分类 | 数量 | 说明 |
|---|---|---|
| 零复制（仅 refs 标记） | 21 | 反例角色全部未把上游文本搬入设计文本 |
| 逐字短句（许可允许，须署名） | 1 | `SL-CAP-0023` 含 CC BY 4.0 来源 6 词英文原句，已标记 REVIEW_REQUIRED |

**产品代码、Skill、Schema 全部未实现（`find src tests schemas skills -type f` = 0）**，
因此不存在代码层面的复制。

---

## 6. 待人工复核队列

按第 5 节要求，**不能因字符串未命中就宣称已证明零复制**。

- **必须法务判断**：`U06::C13`、`U06::C28`（U06 无许可证，抽象思想与受保护表达的边界，见 U06 审计 U10）
- **须履行署名义务**：所有 CC BY 4.0 来源（U03 系列），分发物须含署名与许可链接
- **须保留修改声明**：Apache-2.0（U05 系列），若再分发需保留 LICENSE 与修改说明
- **机器检测盲区**：语义级改写与结构搬运无法通过字符串重合判定

**本轮不宣称「已证明零复制」，只宣称「机器检查未发现逐字复制」+ 已登记的盲区。**
