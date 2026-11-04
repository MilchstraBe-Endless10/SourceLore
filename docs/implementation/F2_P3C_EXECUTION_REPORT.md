# F2-P3C · 执行报告

产物：`F2_P3C_VERIFICATION.json`（20/20）、`F2_P3C_E2E_REPLAY.json`、
`F2_P3C_INTERFACE_AUDIT.json`、`F2_P3C_GATE_RESULTS.json`、`F2_P3C_EXECUTION_ARCHITECTURE.md`

**两个结论分开报：A. LOCAL_CONTROLLED_EXECUTION = DONE；B. REAL_HARNESS_AUTHORIZED_E2E = OPEN。**

---

## 1. 实际执行器与授权契约

**执行器**是一条 8 阶段流水线：

```
PREFLIGHT → AUTHORIZATION_CHECK → SNAPSHOT_COLLECT → FACT_EXTRACT
→ TARGET_CLAIM_CREATE → EVIDENCE_VERIFY → RESULT_PERSIST → COMPLETION_CHECK
```

复用现有 Collector / Facts / EC / Storage，**没有新建第二套引擎**。
Collector 通过 `collector_adapter`（`RealGhAdapter` / `FakeGhAdapter`）包装，
它只做"按 sha 取 commit、按 tree sha 取树"两件事，**不做 Ref 解析**。

**授权契约**：`validate_execution_authorization(candidate, plan, authorization, now, require_production)`

四类批准分开（`DEV_BATCH_APPROVAL` / `TEST_ONLY` / `HUMAN_OPERATOR` / `PLATFORM_APPROVAL`），
16 个拒绝原因码，默认拒绝。

---

## 2. 真实授权与测试授权的隔离

| 检查 | 结果 |
|---|---|
| TEST_ONLY 带 `test_only=True` | ✓ |
| TEST_ONLY 在 `require_production=True` 下 | **拒绝**（`TEST_ONLY_IN_PRODUCTION`） |
| 正式模式只接受 HUMAN_OPERATOR / PLATFORM_APPROVAL | ✓ |
| 正式模式必须带 `authorization_proof` | ✓（缺失 → `MISSING_VERIFIABLE_PROOF`） |
| `approved=True` 但无 source | **拒绝**（`AGENT_SELF_APPROVED`） |
| source 为 AGENT/SELF/MODEL/LLM | **拒绝** |

**本会话审批提示被禁用，Y6-P3 仍 UNVERIFIED** —— 所以本批**没有制造任何真实审批回执**，
B 类保持 OPEN。

---

## 3. 候选到执行任务的状态映射

```
候选（P3B）：PROPOSED / BLOCKED / SUPERSEDED / CANCELLED      ← 知识侧状态
执行（P3C）：SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN   ← 运行侧状态
```

**两套状态不合并。** `revalidation_run` 有自己的 `current_stage` 与 8 条阶段记录；
阶段状态用内部词（`PENDING/RUNNING/COMMITTED/FAILED_RETRYABLE/FAILED_FATAL/UNKNOWN`），
不冒充 Harness 原生状态。

`run_id = H(candidate_id, plan_digest, authorization_id)`，同候选+同计划+同授权幂等。

---

## 4. Collector 固定 Commit 执行结果

实测调用序列（端到端回放真实记录）：

```
[('fetch_commit', 'bbbb…'), ('fetch_tree', '1111…')]
```

**没有任何 Ref 解析调用。** 关键校验：

- 返回 sha ≠ 请求的 B → `COLLECTED_COMMIT_MISMATCH`（不悄悄改用）
- `root_tree_sha` 必须来自 `commit.tree.sha` → 缺失则 `ROOT_TREE_NOT_FROM_COMMIT_OBJECT`
- **条目 sha 非法 → 拒绝**（初版接受 `sha="zzz"`，实测抓出后修复）

---

## 5. 新 Claim 与旧 Claim 的身份关系

```
source_claim_id  → Commit A（7fd1a60b…）
target_claim_id  → Commit B（bbbb…）
```

- 新 Claim **重新计算**（`ec_models.build_path_claim`），不是复制旧 ID 再改字段
- 断言 `claim_id == expected_target_claim_identity`；
  不一致 → `TARGET_CLAIM_IDENTITY_MISMATCH`，停在 `TARGET_CLAIM_CREATE` 阶段，
  **且不写出错误 Claim**（测试断言 Claim 数不变）
- 旧 Claim 仍绑 A、`review_status` 仍 `pending_review`
- 新 Claim 也从 `pending_review` 开始，**不继承旧的人工审核状态**

---

## 6. 新 Verification 三态实测

| 场景 | execution_status | verification_status |
|---|---|---|
| B 上存在 README | SUCCESS | **supported** |
| B 上不存在 README | SUCCESS | **refuted** |
| B PARTIAL 且未观察到 | SUCCESS | **insufficient_evidence** |
| B 获取失败 | FAILED | `None`（不产生裁决） |
| 证据损坏 | 失败或非确定性 | 不得 supported/refuted |

**执行成功 ≠ 裁决肯定**：PARTIAL 那条就是执行 SUCCESS 而裁决 `insufficient_evidence`。

---

## 7. B→C 目标漂移保护

- B 的结果 payload 带 `target_commit_sha=B`
- `freshness_context.is_current_ref_target = False`（明确标注"已不是当前 Ref 目标"）
- C 出现后，B 的结果不变；C 产生新候选
- **用 B 的授权执行 C 的候选 → 拒绝，且 Collector 零调用**（有测试）
- 不把 B 的结果提升为当前 master 的权威结论

---

## 8. 各阶段 Checkpoint

每阶段记录 `input_digest / operation_id / expected_outputs / actual_outputs /
execution_status / checkpoint_version / error_code`。

**授权在 `SNAPSHOT_COLLECT` 之后复查一次**（不只在开头）——
撤销的授权会在中途被拦下（有测试，且断言此时无外部调用）。

**不宣称跨两个独立 SQLite 的全局原子事务** —— 靠 `operation_id` 对账。

---

## 9. 跨库对账、SIGKILL 与幂等结果

| 实验 | 结果 |
|---|---|
| C-1 快照已提交后 SIGKILL | 快照仍在、`OP-COL-` 落账；重放不新增快照 |
| C-2 Fact 已提交后中断 | 重放同 `fact_id`，不推进 fact 版本 |
| C-3 Claim 已写、Verification 未写 | 恢复后复用同一目标 Claim，**不产生第二个** |
| C-4 Verification 已提交、回执丢失 | 恢复后复用同一 `verification_id`，不重复推进 |
| 重复运行（真调两次） | 同 `verification_id`，verification 数不变 |
| 错误 `expected_version` | `CONFLICT` |
| UNKNOWN（只读 API 超时） | `uncertain_side_effect=True`，**不自动重试**（断言只调一次） |

SIGKILL 是真实的 `os.kill(getpid(), 9)`，父进程断言 `returncode != 0` 且 stdout 有提交标记。

---

## 10. 旧历史与人工审核状态保护

- 旧 Claim payload 指纹前后一致（仍绑 A）
- 旧 Verification payload 指纹仍在（2 条 verification 并存）
- `review_status` 全部 `pending_review`，`human_authored` 全部 False
- 执行失败时，旧 Claim/Verification 指纹**完全不变**

---

## 11. 本地受控端到端执行结果

**A. LOCAL_CONTROLLED_EXECUTION = DONE**

链路：Candidate → TEST_ONLY 授权 → Collector(固定 B) → Facts → 新 Claim B → EC → Storage。

```
源 A          → supported
B 缺失 README → refuted（execution SUCCESS）
B 存在 README → supported
B PARTIAL     → insufficient_evidence（execution SUCCESS）
B 获取失败     → FAILED，无裁决
无授权        → 拒绝，Collector 零调用
```

`auth_kind = TEST_ONLY`、`test_only = True` —— 明确标注为隔离测试。

---

## 12. 真实 BotHarness 端到端状态

**B. REAL_HARNESS_AUTHORIZED_E2E = OPEN**

- 无真实可核验的人工授权通道
- Y6-P3 审批传递 **UNVERIFIED**
- Y6-P6 BotHarness 端到端 **OPEN**
- 本轮**未联网**（`live_github_refetch=false`）、**无真实人类授权**
  （`real_human_authorization=false`）

不得以 TEST_ONLY 授权代替真实审批。

---

## 13. 新增代码和测试文件

```
src/lifecycle/revalidation_authorization.py   四类批准 + 16 拒绝码 + 默认拒绝
src/lifecycle/revalidation_run_store.py       run 记录 + 8 阶段 + 结果 + CAS
src/lifecycle/revalidation_executor.py        8 阶段执行器
src/lifecycle/collector_adapter.py            RealGh / FakeGh 适配
tests/lifecycle/test_revalidation_authorization.py   21 项
tests/lifecycle/test_revalidation_execution.py       33 项
tests/lifecycle/test_revalidation_crash.py           6 项
tests/lifecycle/test_revalidation_end_to_end.py      8 项
tools/f2p3c_verify.py、tools/f2p3c_e2e_replay.py
docs/implementation/F2_P3C_*（5 份）
```

修改：`revalidation_models.py` 加 `target_claim_parameters`；
`revalidation_planner.py` 填该字段；`asset_models.py` 登记 2 个类型；
`test_lifecycle.py::t25` 收窄到"写入语义"。

---

## 14. 全部测试通过数、失败数及退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle        142 OK   exit 0    ← P3A 40 + P3B 37 + P3C 65
f2p3c_verify           20/20 PASS
f2p3b 22/22  f2p3a 18/18  f2p2b 17/17  f2p2a 15/15
f2p1c 22/22  f2p1b 16/16  f2p1a 22/22  f1d 26/26
```

368 项 unittest + 179 项验收断言，失败 0。

---

## 15. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，f1d_verify 26/26 通过。

---

## 16. 当前 OPEN 门禁

| 门禁 | 状态 |
|---|---|
| **B. REAL_HARNESS_AUTHORIZED_E2E** | **OPEN**（无真实授权通道） |
| Y6-P3 审批传递 | **UNVERIFIED** |
| Y6-P6 BotHarness 端到端 | **OPEN** |
| B-1/B-2/B-3 分发门禁 | **OPEN** |
| 实时 GitHub 重新验证 | 未执行（本轮未联网） |
| Research / Renderer / Skill | 未开始 |

---

## 17. 本轮三个真实缺陷

1. **`plan_digest` 未重新计算**：初版只比较 `plan["plan_digest"]` 字段，
   攻击者同时改计划内容和该字段即可绕过。已改为**重算比对**。
2. **tree 条目未校验**：`sha="zzz"` 的损坏 tree 仍被当成有效来源，进而产出确定性裁决。
   已加 path/sha 结构校验 → 拒绝。
3. **payload 字段名踩 Storage 禁词**：`authorization_ref` 含 `authorization`，
   被 `FORBIDDEN_FIELDS` 拒绝（这是正确护栏）。改名 `auth_ref`。

另有一处**设计生效**而非缺陷：历史来源候选是 `BLOCKED`，正式模式拒绝执行；
隔离测试模式（TEST_ONLY）才允许 —— 这正是 §13 的落地。

---

## 18. 下一阶段最小可执行起点

1. **先解决真实授权通道**（Y6-P3）：没有可核验的人类授权来源，B 类无法推进。
2. B 类需要 BotHarness 端到端（Y6-P6），当前 `dsh headless` 缺凭据。
3. A 类已 DONE，可作为 Research/Renderer 的可信输入 ——
   但**不得把 A 类结果当作已发布知识**。
4. 若要继续，建议下一批做 **F2-P3D：结果消费与知识视图装配的最小契约**
   （只读、不发布），而不是直接跳 Research。
