"""多仓库与语义覆盖 Gold：20 项人工预定义预期。"""

GOLD = [
 ("M01","PLAN","同状态下 plan 与实际执行一致","PLAN_EQ_EXEC"),
 ("M02","PLAN","计划生成后资产变化 → 重校验","STALE_REVALIDATED"),
 ("M03","PLAN","不同 data_root 的计划不能复用","CONTEXT_MISMATCH"),
 ("M04","PLAN","计划只读零网络","READ_ONLY_0"),
 ("M05","BUDGET","预算回归","BUDGET_OK"),
 ("M06","COVERAGE","CommonJS 判为未支持形态","UNSUPPORTED_CJS"),
 ("M07","COVERAGE","真空结果正确判定","VALID_EMPTY"),
 ("M08","COVERAGE","语义覆盖度报告字段完整","REPORT_COMPLETE"),
 ("M09","COVERAGE","不宣称完整理解 JS","NOT_OVERCLAIM"),
 ("M10","ESM","真实 ESM Symbol","ESM_SYMBOL"),
 ("M11","ESM","真实 ESM Default Export","ESM_DEFAULT_EXPORT"),
 ("M12","INTEGRITY","真实 Blob OID 校验","OID_OK"),
 ("M13","PERSIST","源码 Fact 持久化","FACT_PERSISTED"),
 ("M14","CLAIM","源码 Claim 入库","CLAIM_SAVED"),
 ("M15","CLAIM","源码 Verification 入库","VERIF_SAVED"),
 ("M16","QUERY","跨进程查询读回","CROSS_PROCESS"),
 ("M17","CARD","源码卡片生成","CARD_OK"),
 ("M18","ISOLATION","两仓库身份隔离","ISOLATED"),
 ("M19","ISOLATION","同名文件不覆盖","SAME_NAME_OK"),
 ("M20","OFFLINE","零网络离线复用","OFFLINE_0"),
]
