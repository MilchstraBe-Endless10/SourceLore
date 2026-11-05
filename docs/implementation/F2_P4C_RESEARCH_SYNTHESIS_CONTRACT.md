# F2-P4C · LLM 研究综合与逐句引用校验契约

产物：`F2_P4C_E2E_REPLAY.json`、`F2_P4C_GOLD_SYNTHESIS.json`、
`F2_P4C_VERIFICATION.json`、`F2_P4C_GATE_RESULTS.json`、`F2_P4C_EXECUTION_REPORT.md`
回放：`docs/preview/f2p4c/`

**结论：`DETERMINISTIC_SYNTHESIS_GATE = DONE`（陈述池 + 逐句校验 + 分级）。
`REAL_LLM_CALL_VERIFIED` 保持 `OPEN` —— 真实 DeepSeek-V4.1 Flash 调用未验证、未声称。**

---

## 0. 先修三个前置问题（本轮入场条件）

| # | 问题 | 实测结论 | 处理 |
|---|---|---|---|
| 1 | 不能只凭非空 `evidence_refs` 判断证据可信 | **确认是真缺陷** | 逐条解析引用，四等级判定 |
| 2 | `content_digest` 必须覆盖影响结论与可信度的字段 | 原十项已覆盖；**新增字段需补** | `evidence_integrity_summary` 并入摘要 |
| 3 | 不能长期依赖 SQLite `rowid` 判定业务运行顺序 | **确认是测试/工具缺陷** | 改业务键 `logical_identity + asset_version` |

**问题 3 的真相**：`revalidation_run_store._latest` 带 `logical_identity` 过滤，
`asset_version` 在该身份内单调递增，所以**生产代码是对的**；
错的是我自己的测试与验证器用全局 `rowid`/`asset_version` 排序 ——
库里一旦有第二个 candidate 的 run 就会取错。

---

## 1. Trusted Statement Bank

从 Research Packet 抽出**可引用陈述池**，全部模板转录、非 LLM 生成：

| 种类 | 来源 | 说明 |
|---|---|---|
| `FACT_SUPPORTED` / `FACT_REFUTED` / `FACT_INSUFFICIENT` | 每条 finding | 带 commit、claim_id、verification_id、证据完整性 |
| `COVERAGE_STATE` | coverage_assessment | 明确声明"这不是证据裁决" |
| `LIMITATION` | limitations | 逐条转录 |
| `SCOPE_BOUND` | distribution_restrictions | 固定范围声明 |

铁律：
- 每条陈述必须绑定 `finding_refs`（有测试）
- 研究包没有 finding → **不得**生成事实陈述（有测试）
- 陈述池确定性：同 packet 同 `bank_digest`

---

## 2. 逐句引用校验

句子切分后逐句判定，六类结果：

```
CITED_OK                        通过
NO_CITATION                     无引用 → 只能 INFERENCE
INVALID_STATEMENT_REF           引用不存在的 statement_id → 阻断
AMPLIFIED_BEYOND_EVIDENCE       越界措辞 → 阻断
INSUFFICIENT_AS_NEGATION        把证据不足写成否定 → 阻断
NOT_GROUNDED_IN_CITED_STATEMENT 引用真实但与句意无关 → 不得 STRICT
```

**接地检查**：句子与所引陈述的词汇重合度低于 `GROUNDING_MIN=0.20`
即视为"引用了但没支撑"。这条是本轮实测发现并补上的缺口 ——
最初版本只看"有没有引用"，导致提示注入文本只靠随意挂引用就能通过。

越界措辞清单（研究与 P4A 同口径）：

```
完全正确 / 该软件正确 / 功能完备 / 项目质量高 / 该软件存在漏洞 /
当前最新 / 当前有效 / 已发布 / 因此该项目 / 由此可见该项目 …
```

否定化清单：`该命题错误 / 该命题为假 / 可以确认不存在 / 已证实不存在 …`

---

## 3. 合成分级

```
STRICT_CITED          全部句子 CITED_OK，可用于内部严格引用场景
DRAFT_FOR_REVIEW      存在无引用/未接地句子，只能待审，不得肯定语气使用
REJECTED_NOT_CITABLE  存在阻断级违规，整条拒绝
```

**无客户端时**：`NO_SYNTHESIS`，`text=""`，绝不产出叙述。

---

## 4. LLM Adapter

`src/research/llm_adapter.py` —— **不含任何真实网络调用**。

- `make_stub_client(preset)` 提供离线 stub，仅验证校验通路
- `invoke(client, ...)`：`client=None` → `NOT_CONFIGURED`
- 适配器状态：`NOT_CONFIGURED` / `OFFLINE_STUB` / `REAL_CALL_ATTEMPTED` /
  `REAL_CALL_VERIFIED` / `REAL_CALL_FAILED`
- **`real_call_verified` 恒为 `False`** —— 本轮没有真实调用证据

Prompt 只含结构化陈述与引用 ID，**不含原始仓库文本**。

---

## 5. 不可发布

任何合成产物：

```
is_knowledge_authority = false
publishable            = false
distribution_restrictions.distribution_allowed = false
```

回放用 P4A Renderer 呈现：`preview_allowed=true`、`distribution_allowed=false`、
HTML 无 script、CSP 生效。

---

## 6. 明确不做

不建立 Agent 自主研究循环、不做多轮自我批判、
不把合成产物写回 Claim/Verification/review_status、
不关闭 B-1/B-2/B-3、不宣称真实 LLM 已验证。
