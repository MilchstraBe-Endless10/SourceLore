# F2-P3C 检查点（中途落盘）

**基线**：6ef7919 · Crosswalk sha256 `42841207…` 已验证未变

## 已完成（可运行、已验证）

| 文件 | 状态 |
|---|---|
| `src/lifecycle/revalidation_authorization.py` | 完成。四类批准严格分开；16 拒绝原因码；默认拒绝 |
| `src/lifecycle/revalidation_run_store.py` | 完成。run 记录 + 8 阶段 + 结果登记 + CAS |
| `src/lifecycle/collector_adapter.py` | 完成。RealGhAdapter / FakeGhAdapter（标 SYNTHETIC_FIXTURE） |
| `src/lifecycle/revalidation_executor.py` | 完成。PREFLIGHT→AUTH→COLLECT→FACT→CLAIM→VERIFY→RESULT→COMPLETION |
| `docs/implementation/F2_P3C_INTERFACE_AUDIT.json` | 完成。§1 十四项核验 + 三个缺口 |

**改动**：
- `revalidation_models.py` 加 `target_claim_parameters`
- `revalidation_planner.py` 填该字段（`_target_claim_params`）
- `asset_models.py` 登记 `revalidation_run` / `revalidation_result`
- `test_lifecycle.py::t25` 收窄到"写入语义"（原断言误伤 `PLATFORM_APPROVAL` 常量名）

## 已验证的实测（冒烟）

```
源 Claim A        → supported
候选（B=bbbb…）   → VERSION_ADDED / PROPOSED
计划              → PLAN_READY
TEST_ONLY 授权    → ok
执行              → SUCCESS
B 上无 README     → refuted
collector 调用    → [fetch_commit(bbbb…), fetch_tree(1111…)]  ← 只碰 B，未解析 Ref
```

`tests/lifecycle` **77/77 OK**（P3A 40 + P3B 37，全回归）

## 尚未完成

1. 测试套件 `tests/lifecycle/test_revalidation_execution.py`（T-1..T-14、T-21..T-27、T-30…）
2. `test_revalidation_authorization.py`（T-1..T-8）
3. `test_revalidation_crash.py`（T-32..T-37，真实 SIGKILL）
4. `test_revalidation_end_to_end.py`（T-21..T-25、T-28..T-29）
5. `tools/f2p3c_verify.py`、`tools/f2p3c_e2e_replay.py`
6. 三份文档 + 账本 + 提交

## 关键设计（续跑必读）

- **固定目标**：`adapter.fetch_commit(B)` 按 sha 直取，断言返回 sha==B；`tree_sha` 必须来自 `commit.tree.sha`
- **新 Claim 身份**：`ec_models.build_path_claim(...)` 后用 `expected_target_claim_identity` 断言，不等则 `TARGET_CLAIM_IDENTITY_MISMATCH` 立即停
- **授权复查**：`SNAPSHOT_COLLECT` 之后**再查一次**（C-5）
- **执行/裁决分离**：`ExecResult.execution_status` 与 `.verification_status` 两个字段
- **UNKNOWN 不入库**：Facts 层 UNKNOWN 直接按 insufficient 走，不写成确定性 fact
