# F1-B / Product 批次 · 检查点（已完成）

## 做到哪

**本批已 DONE。** 四个验证器全绿，幂等已验证。下一个批次是 Research。

### 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_product_def.py` | 6 条 canonical 定义 + `CONSUMED_THIS_BATCH`（10 个承接）+ `DEFERRED_TO_OTHER_MODULE`（2 条分流） |
| `tools/fusion/f1b_build_product.py` | 增量构建器，幂等，写入延后到校验通过 |
| `tools/fusion/f1b_verify_product.py` | 43 条独立检查，只写 `F1B_PRODUCT_VERIFICATION.json` |
| `docs/fusion/F1B_PRODUCT_DECISIONS.md` | 设计裁决，误合并防护 A–F + 验证语义 P-1..P-5 逐条落章 |
| `docs/fusion/F1B_PRODUCT_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Product` 到 `_MODULE_DEFS` 与 `BATCH_NAMES` |

### 实测数字（磁盘实算）

- 本批承接 10 个身份、合成 6 条 canonical（`SL-CAP-0029`…`0034`）、外推 2 条
- 累计：MAPPED 44 / ROUTED 7 / UNREVIEWED 92 = 143，canonical 34
- 批次视图：Facts 11/1、Collector 11/4、EC 12/0、Product 10/2
- 晋升记录 18 条全在盘，分流表 7 条零重复

### 验证（实际退出码）

```
python3 tools/fusion/f1b_verify.py            → 12/12 PASS (exit 0)
python3 tools/fusion/f1b_verify_collector.py  → 30/30 PASS (exit 0)
python3 tools/fusion/f1b_verify_ec.py         → 50/50 PASS (exit 0)
python3 tools/fusion/f1b_verify_product.py    → 43/43 PASS (exit 0)
```

重建链 `f1b_build_product.py` 重跑后 `canonical_capabilities` / `cross_module_redirections` /
`routed_promotions` / `batches` / `global_state_counts` / `module_rollup` 六个核心字段逐字节一致。

## 本批核心裁决

1. **声明不可替代实现证据。** `claim_type` 四值 + 硬规则：`evidence_refs` 为空时只能是
   inference 或 unknown，不得是 fact 或 declaration。
2. **有配置 ≠ 在运行。** 集成三态（confirmed_runtime / configured_boundary / integration_unknown），
   检测到配置或依赖声明即必须产出条目，哪怕状态是 unknown。

## 本批踩的坑（下一批务必注意）

1. **★ 构建器自有键集合必须同时包含「承接键」和「本批分流键」。**
   Product 构建器起初只装了承接键，导致本批推给其它模块的分流每跑一次追加一份，
   累积成 5 份重复记录，由 Collector c4c 抓到。修正为
   `own_keys = set(CONSUMED_THIS_BATCH) | set(DEFERRED_TO_OTHER_MODULE)`。
   映射与分流是两件事，但剥离必须用同一个键集合，否则幂等只在映射侧成立。
2. **验证器基线写死仍会假阳性。** EC 的 c17（batch_summary 必须指向自己）与 c47（当前全局数卡历史文档）
   在本批推进后必然报红，已按「历史批次判历史事实」修正，核心不变量未放宽。
3. **自写验证器的低级错误。** 批次 redirected 断言漏括号（`len(...)==0` 恒 False）、
   分流去向 `mod[0]` 误把字符串首字符当模块名。写多行表达式后先 `python3 -c "import ast; ast.parse(...)"`。
4. **全库检索比关键词直觉更可靠。** U03 之外五源无一命中 ≥2 关键词，人工逐一核对后确认确实没有
   产品语义类未审项——不能凭「产品建模总该有几条」的印象去凑数。

## 下一步

**F1-B 下一批：Research。** 候选方向：`U02::C10`（四轮研究流程）、`U02::C12`（五层来源优先级）、
`U02::C13`（报告九节结构）、`U02::C14`（来源分桶）、`U02::C16`（强制内联引用）、
`U02::C11`（Broad to Narrow，已由 Collector 分流指向 Research）。
新 ID 从 `SL-CAP-0035` 起。

其余待办：Lifecycle → Security → Renderer → Storage → DSH-Adapter。
F1-C、F1-D 仍未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_product.py | tail -2
```

检索词：F1B Product batch checkpoint。
