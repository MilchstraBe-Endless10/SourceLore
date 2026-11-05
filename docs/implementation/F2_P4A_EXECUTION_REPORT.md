# F2-P4A · 执行报告

产物：`F2_P4A_VERIFICATION.json`、`F2_P4A_E2E_PREVIEW.json`、
`F2_P4A_RENDERER_CONTRACT.md`、`F2_P4A_GATE_RESULTS.json`、`F2_P4A_STATS_AUDIT.json`

**结论：`SAFE_RENDERER_CORE = DONE`；`LOCAL_VISUAL_PREVIEW = DONE`（含真实浏览器实测）。
`DISTRIBUTION_READY` 保持 `NOT_READY`；`FULL_RENDERER` 未启动、未声称。**

---

## 1. Renderer 实际结构

```
src/renderer/safe_html.py          转义 / 清洗 / URL 白名单 / 可信模板 / CSP
src/renderer/card_models.py        视图→卡片投影 + 措辞约束 + card_id
src/renderer/card_renderer.py      JSON 渲染 + HTML 渲染 + 阻断页
src/renderer/report_renderer.py    多版本对照报告
src/renderer/pre_publish_check.py  8 类分发检查
```

**无状态、无网络、无数据库写入。** 写文件只发生在 `tools/f2p4a_e2e_preview.py`。

---

## 2. JSON / HTML 输出契约

**JSON**：`json.dumps(..., indent=2, sort_keys=True)`，键序固定，无时间戳。

**HTML**：单文件，内联可信 CSS，无脚本、无外部资源、无 `<link>`。
含 `<meta http-equiv="Content-Security-Policy">`。

三个输出：`rendered_card.json` / `knowledge_card.html` / `knowledge_report.html`。

---

## 3. 知识卡片实际内容

以 `s1_refuted` 为例（真实链路产出）：

```
标题        仓库路径「README」存在
仓库        1296269
固定 Commit 7fd1a60b01f91b314f59955a4e4d4e80d8edf11d（完整保留）
范围        本卡片只描述该 Commit 这一个固定 Commit 上的命题，
            不代表该仓库的当前最新状态
证据裁决    supported 支持 —— 在指定范围内，现有经过验证的证据支持该命题
新鲜度      可能已过时 —— 所跟踪版本已经变化，旧结论对该 Ref 的当前适用性
            有待核查。这不表示旧结论已经失效或错误
人工审核    pending_review 待人工审核（人工撰写：否）
来源        合成夹具 SYNTHETIC_FIXTURE｜判定依据 executor_adapter
授权        隔离测试授权（TEST_ONLY）
隔离测试    本卡片由隔离测试授权（TEST_ONLY）产生，未通过真实平台授权验收
限制        3 条（合成来源 / 未人工批准 / 分发门禁受限）
分发门禁    允许分发：否｜FROZEN_INTERNAL_RESTRICTED｜B-1 B-2 B-3 全 OPEN
```

---

## 4. 五轴状态与限制呈现

| 轴 | 呈现方式 |
|---|---|
| 证据裁决 | 独立「证据裁决」区 + badge（**文字+颜色双通道**） |
| 新鲜度 | 独立「新鲜度与适用性」区，状态与含义分开 |
| 人工审核 | 独立「人工审核」区，非 approved 时额外提示 |
| 执行 | 页脚与历史区（run_ref / status） |
| 来源+授权 | 独立「来源与授权」区，两层分开显示 |

**限制从不隐藏**：每条 limitations 逐条列出，分发门禁单独成区并列表 B-1/B-2/B-3。

---

## 5. HTML 安全与注入测试

`tests/renderer/test_html_security.py` **13 项**，`PAYLOADS` 含 12 种攻击向量：

```
script 标签 / 属性注入 / 单引号属性 / javascript URL / data URL /
iframe / object / svg 脚本 / body onload / markdown 原标签 /
样式注入 / 闭环注释
```

逐项断言：`<script`/`<iframe`/`<object`/`<svg`/`<style`/`<body` 全部不可执行，
事件属性正则为空，尖括号必须实体化。

URL 白名单：`javascript:`/`data:`/`vbscript:`/`file:`/`about:blank` 全部 `None`；
`http://`、非白名单 host、`github.com.evil.com`、userinfo、`..` 全部拒绝。

**加深测试**：同时污染 `title`、`repository_id`、`limitations`、`claim_scope`
四个注入点，断言全部实体化且无事件属性。

---

## 6. 本地浏览器视觉检查结果

**真实执行**（Playwright + 本地 HTTP，非 file://）：

| 检查项 | 卡片页 | 报告页 |
|---|---|---|
| 页面标题 | 仓库路径「README」存在 | 多版本知识对照报告 |
| 横向溢出 | **false** | **false** |
| 页面尺寸 | 1920×2036 | — |
| `<script>` | **0** | **0** |
| iframe/object/embed | **0** | **0** |
| 事件属性 | **0** | **0** |
| CSP meta | **有**，`script-src 'none'` | 有 |
| 语义 h2 | 8 个（裁决/新鲜度/审核/来源/证据/限制/分发门禁） | 5 个（总览/两版本/门禁） |
| table | — | 1 |
| 不同 Commit 数 | — | **2** |

**视觉证据**：`docs/preview/f2p4a/s1_refuted/preview.png`（1920×2036，256 KB）。

---

## 7. 多版本报告结果

```
H2 版本 1：7fd1a60b01f91b314f59955a4e4d4e80d8edf11d   supported
H2 版本 2：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb   refuted
```

报告顶部显式声明：

> 本报告并列展示**不同 Commit** 上的独立结论。它们各自成立于自己的版本，
> **不构成同一事实的矛盾**。报告不推断这些 Commit 之间的祖先/先后关系。

报告按 `commit_sha` 排序，**传入顺序无关**（有测试）。

---

## 8. 只读性及资产指纹对比

| 检查 | 结果 |
|---|---|
| A 层资产指纹 | 不变（含 16+ 资产逐条比对） |
| B 层指针版本 | 不变 |
| C 层索引 | 不变 |
| Checkpoint（revalidation_run 数） | 不变 |
| `operation_log` | 不变 |

**负向对照**：主动写一条资产后断言指纹确实变化 —— 证明"不变"非空转。

---

## 9. 确定性渲染哈希

```
card_id = SL-CARD- + H(view_id, verdict, commit, review, freshness,
                       applicability, provenance, auth, schema, renderer)[:32]
```

实测：同输入重复渲染 `html` 与 `json` **逐字节一致**；
`assembled_at` 变化只改页脚、不改 `card_id`；
A/B 两个 Commit 的 `card_id` 不同。

---

## 10. 发布门禁实际结果

```
preview_allowed      = True
distribution_allowed = False
publish_blocked      = True
```

检查发现（s1 场景）：`ARTIFACT_IS_TEST_ONLY`、`SYNTHETIC_PROVENANCE`、
`DISTRIBUTION_GATE_OPEN`。

**即使裁决改成 supported、审核改成 approved，`distribution_allowed` 仍为 False**
（测试 `test_distribution_never_true_even_all_supported` 固化）。

---

## 11. P3C 阶段追踪补验结果

**发现真缺陷**：`revalidation_run_store.set_stage` **从未被调用** ——
八个阶段在 run 记录里全部停在 `PENDING`，只有开始与结束两处有状态。

按 §13 授权做最小修复（不重写 P3C 执行器）：

- 每阶段进入记 `RUNNING`，离开记 `COMMITTED`
- 失败出口把当前阶段标 `FAILED_FATAL` 并带 `error_code`
- 补齐 `PREFLIGHT` 记录时机（须在 `create_run` 之后）

实测最终 run：

```
PREFLIGHT=COMMITTED  AUTHORIZATION_CHECK=COMMITTED
SNAPSHOT_COLLECT=COMMITTED  FACT_EXTRACT=COMMITTED
TARGET_CLAIM_CREATE=COMMITTED  EVIDENCE_VERIFY=COMMITTED
RESULT_PERSIST=COMMITTED  COMPLETION_CHECK=COMMITTED
```

P3C 142 项 + P3D 50 项回归全绿。

---

## 12. P3D 统计差异结论

```
清单 [24,20,22,18,17,15,22,16,22,26] 算术和 = 202
报告写 = 203，差 1
```

**结论：人工加法错误，不是验证遗漏。**
十个验证器实跑全部 `exit 0`（f2p3d 24/24、f2p3c 20/20、f2p3b 22/22、
f2p3a 18/18、f2p2b 17/17、f2p2a 15/15、f2p1c 22/22、f2p1b 16/16、
f2p1a 22/22、f1d 26/26）。

**自动汇总**：`tools/f2p4a_stats_audit.py` 逐个 subprocess 运行并解析
`N/M PASS`，不再依赖手工相加。权威口径 `F2_P4A_STATS_AUDIT.json`。
历史报告未修改。

---

## 13. 新增代码与测试

```
src/renderer/{__init__,safe_html,card_models,card_renderer,
              report_renderer,pre_publish_check}.py
tests/renderer/{__init__,rfx,test_cards(16),test_html_security(13),
                test_read_only(11),test_render_multiversion(10),
                test_distribution_gates(9)}.py
tools/{f2p4a_verify,f2p4a_e2e_preview,f2p4a_stats_audit}.py
docs/preview/f2p4a/{s1_refuted,s2_supported,s3_partial,s4_multi}/
docs/implementation/F2_P4A_*（4 份）
```

修改：`src/lifecycle/revalidation_executor.py`（§13 阶段记录补齐）。

---

## 14. 所有测试数量、失败数及退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle        142 OK   exit 0
tests/views             50 OK   exit 0
tests/renderer          59 OK   exit 0
```

---

## 15. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变。

---

## 16. 仍未完成的门禁

| 门禁 | 状态 |
|---|---|
| `DISTRIBUTION_READY` | **NOT_READY**（B-1/B-2/B-3 全 OPEN） |
| `FULL_RENDERER` | **NOT_STARTED**（模板体系/交互卡片/发布流程未做） |
| `RESEARCH` | **NOT_STARTED** |
| 正式 Skill 集成 | **NOT_STARTED** |
| `REAL_HARNESS_AUTHORIZED_E2E` | **OPEN** |
| Y6-P3 / Y6-P6 | **UNVERIFIED** / **OPEN** |

---

## 17. 下一批 Research 最小可执行起点

1. **输入契约**：只消费 `rendered_card.json` 或 `KnowledgeView`，
   **不直接读数据库**，不重新裁决。
2. **输出边界**：Research 产出只作为**新的待审材料**，
   不得回写 Claim / Verification / review_status。
3. **必须携带限制**：任何产出都必须原样带出 `limitations` 与
   `distribution_restrictions`，不得在摘要中丢弃。
4. **禁止推断**：不得推断 Commit 祖先关系、不得把 B 的结论当作 C 的有效结论。
5. **失败模式**：证据不足/来源损坏时，必须输出"无法给出结论"，
   不得用自然语言补造肯定结论。
6. **必测**：输入顺序无关、确定性输出、注入防护、分发恒 False。
