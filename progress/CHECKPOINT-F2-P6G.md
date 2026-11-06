# F2-P6G 检查点 · 基线 73b0e89（实际 HEAD 4a67ef2，73b0e89 是其祖先）· Crosswalk 匹配

## 四条真实事实审计（is-plain-obj / index.js / commit 666df7c1…）
```
SYM SL-FACT-f8566008…s96c  js_function  isPlainObject            q=isPlainObject            L1-8  B15-343   rule=SOURCE_SYMBOL_DECLARED
SYM SL-FACT-355cb720…fe77  js_variable  prototype                q=isPlainObject.prototype  L6-6  B120-167  rule=SOURCE_SYMBOL_DECLARED
EXP SL-FACT-df8916ac…9227  export_declaration  isPlainObject  L1
EXP SL-FACT-401dfb46…b779  default_export      isPlainObject  L1
```

## 裁决机制实测（已有 adapter，无需新建）
```
A 函数存在        supported             FACT_FOUND        facts=1
C 局部变量        supported             FACT_FOUND        facts=1
D 不存在的函数    insufficient_evidence NO_MATCHING_FACT   ← 不误判 refuted
5 错 kind         insufficient_evidence NO_MATCHING_FACT
6 错 qname        insufficient_evidence NO_MATCHING_FACT
7 错 commit       insufficient_evidence NO_MATCHING_FACT
8 错仓库          insufficient_evidence NO_MATCHING_FACT
9 错文件          insufficient_evidence NO_MATCHING_FACT
```
★ `_matches` 逐字段比对（rule_id + file_path + commit + repo + binding 全 keys），
binding 为空直接 False —— 满足任务书 §4.3「不得只用 rule_id 就宣称 supported」。

## 待办
1. 源码 Claim/Verification 持久化（复用 content_claim_ingest.ingest_content_claim）
2. prototype 语义显示修正（q=isPlainObject.prototype 会被读成"函数对象属性"）
3. 导出事实去重审计（export_declaration vs default_export）
4. 查询裁决分层输出
5. 源码卡片
6. CLI --language/--relation 行为级测试（P6F 已删除，需重新提供真能力或明确拒绝）
7. 测试 ≥25 + 文档 + 提交

## 已完成（2026-06-18 18:59）
### 源码裁决闭环（真实数据）
```
A symbol isPlainObject  supported  SL-CLAIM-0b1f659b…  SL-VERIF-4f2016f8…
C local prototype       supported  SL-CLAIM-4428bc79…  SL-VERIF-ba03e9cb…
B default_export        supported  SL-CLAIM-9216e90f…  SL-VERIF-0f02ba41…
B2 export_declaration   supported  SL-CLAIM-b832e55c…  SL-VERIF-399fd628…
D 不存在函数            insufficient_evidence NO_MATCHING_FACT
E 错 Commit             insufficient_evidence NO_MATCHING_FACT
F 错仓库                insufficient_evidence NO_MATCHING_FACT
```
7 claim + 7 verification 全部入库。

### 新缺陷
**D-64 export 入库丢字段**：规则层有 start_byte/declaration_node_type，
`source_fact_ingest` 没传 → 两条导出事实无法关联同一 AST 节点。已追加式补齐。

**D-65 同一导出事件重复统计**：重抽后新旧资产并存 → 4 条变成 2 组重复。
查询层 `_dedupe_exports` 按 (export_kind, exported_name, start_byte, end_byte) 去重，
保留 declaration_node_type 非空的一条。只改视图，不改资产。

**D-66（进行中）claim 的 normalized_parameters 未持久化**：
payload 里是 null → 查询端无法按 subject 定位 claim → 全部显示 OBSERVED_SOURCE_FACT。

## D-66 根因（2026-06-18 18:59）
`ec_models.Claim` 是 dataclass，**没有 normalized_parameters 字段**。
`build_symbol_claim` 传了该参数，但只用于 `make_claim_id` 算身份，**从没进 payload**。
→ 查询端无 subject 可匹配 → 全部降级成 OBSERVED_SOURCE_FACT。

修法边界（重要）：
- **不得**加进 `identity_payload()` —— 那会改 claim_id 语义，破坏既有身份。
- 应加在 `to_dict()`：identity 不变，payload 多带 subject。
- 追加式：旧资产 payload 无该字段，查询端需兼容（用 expected_exists 兜底不现实，
  所以旧 claim 保持 OBSERVED，新 claim 可 SUPPORTED）。

## 当前代码状态（2026-06-18 18:59）
- `src/content_persistence/source_judgement.py` 已建（build_export_claim / judge / describe_symbol）
- `source_fact_ingest.py` export 分支已补 declaration_node_type + 字节范围（D-64）
- `source_knowledge_query.py` 已加 _dedupe_exports（D-65）+ _verdicts_block/_load_verdicts/_verdict_for
  但 **D-66 未修**：claim payload 无 normalized_parameters → claims 全 OBSERVED
- 真实数据：7 claim + 7 verification 已入库（4 supported / 3 insufficient）

## 下一步（D-66）
在 `ec_models.Claim.to_dict()` 追加 normalized_parameters 字段（**不改 identity_payload**），
并让 build_symbol_claim / build_export_claim / build_import_claim 传入。

## 剩余任务
源码卡片、CLI --language/--relation 行为、测试 ≥25、文档、提交

## D-66 已修（2026-06-18 19:00）
`Claim` 加 `normalized_parameters` 字段，**只进 to_dict 不进 identity_payload**（claim_id 语义不变）。
source_claim_adapter 两处构造 + source_judgement 一处，全部传 params。

重跑后看到 **asset_version 2** 的 payload 已带 subject：
```
source_symbol_declared v2: {file_path, qualified_name, symbol_kind, expected_present}
source_export_declared v2: {file_path, exported_name, export_kind, expected_present}
```
★ 但 `_load_verdicts` 取的是全部行且 dict key 覆盖 → 需按 asset_version 取最大。
