# 技术债务登记

## TD-001 — tests/runtime/test_concurrency.py 偶发 UNIQUE 冲突

- **登记日期**：2026-11-25
- **状态（2026-11-26 更新）**：✅ **已修复**（根因定位 + 原子化修复 + RED→GREEN 回归 + 多轮压力验证）
- **现象**：`tests/runtime/test_concurrency.py` 偶发 `UNIQUE constraint failed: meta.k`；表现为全部测试文件逐项 OK，但整体退出码偶发为 1。
- **已知出现**：beta.3 Release CI run `45429491915`；D3 测试修复 commit `a001d7a` 的 CI run `45621430877`；本机复现约 1/3 概率。
- **根因（已确认）**：`src/runtime/checkpoint_store.py` 的 `_init_schema()` 用 `SELECT` 读 `meta.schema_version`，为空再 `INSERT`，是 check-then-act 非原子操作；多进程同时首开新库时都读到空、各自插入同一主键 `meta.k`，触发唯一键冲突。同类模式在 `src/storage/knowledge_store.py`。
- **修复**：两处均改为单条原子 `INSERT OR IGNORE INTO meta(k,v)` + 读回校验；保留唯一约束，不吞未知异常，不依赖 CI rerun。
- **验证证据**：隔离复现修复前 `16/30` 轮 UNIQUE 失败；新回归修复前 RED、修复后 `3/3`；原现场 `7/7`；修复后压力 `0/30`；knowledge_store 锁探测 `40×16 = 0` 失败。详见 `progress/TECH_DEBT_EXECUTION_EVIDENCE.md` §2。
- **归属判定**：beta.3 时期即存在，与 D3 跨来源绑定改动无关。

## TD-002 — 静态模块关系（relation）检索覆盖不足

- **登记日期**：2026-11-25
- **状态（2026-11-26 更新）**：🟡 **部分解决（边界已定位）**
- **现象**：`query <github_id> --type relation` 返回 `state=NO_RELATIONS`。此前 GitHub 根层快照未捕获静态模块关系，不能把 `NO_RELATIONS` 解释为"已验证无模块关系"。
- **根因判定（本轮）**：P2 已建立 relation 抽取/持久化/查询链路。三类情况已区分——① 新版解析器能力不足：否（同批事实在隔离副本可重建完整语义图谱）；② 历史 Facts 缺失：否（Preact 该 commit 有 236 条源码事实，`COVERED_BY_EXTRACTED_SOURCE`）；③ 历史派生视图过期：是（真实库该 commit 图谱仅 46 节点/32 边且全为 `TREE_CONTAINS`，隔离副本 155 节点/178 边）。
- **离线重建验证**：隔离副本经正式 CLI `derive` 重建 Preact，`ok=true`、`nodes=155`、`edges=178`、`RELATIONS_FOUND`（40 条全 RESOLVED）、A 层指纹不变、零网络。说明缺的是派生视图新鲜度，不是底层资产。
- **未解决边界**：按纪律本轮未在真实库执行重建；如需刷新真实派生视图须单独授权，仍不动 A 层、不联网。
- **证据**：详见 `progress/TECH_DEBT_EXECUTION_EVIDENCE.md` §3。

## TD-003 — 来源验证边界（本地真实性 / Fork 区分 / 第三方授权）

- **登记日期**：2026-11-25
- **状态（2026-11-26 更新）**：🟡 **部分解决（差距已明确，本轮不放宽门禁）**
- **已解决范围**：D3 完成"来源内容对应关系"验证——权威 `subject_record`（数字 ID + `resolved_repository`）+ 固定 Commit/Root Tree + GitHub 根层 blob_ref 是本地 blob map 的哈希一致子集；反例（伪造数字 ID、本地 ID 伪装、无权威记录、blob 冲突）均被拒。本轮核实生产链路（正式 CLI / 知识问答 / 来源查询）确实调用 `resolve_supplement`（不是只有函数存在）；真实库已有 4 条权威身份记录与 2 条 `source_verified=1;method=github_identity_record+blob_subset` 绑定。
- **未解决边界（需后续开发）**：① 独立的远端/链上身份二次认证缺失，当前依赖既有 A 层权威记录；② 第三方内容授权的新法律判定未做，不扩大授权、不改分发门禁；③ 通用 Fork 区分（多源交叉/签名）尚未扩展到所有仓库，当前仅对已建立绑定与权威记录的仓库生效。
- **影响**：不得把"内容对应验证通过"升格为"跨仓库身份与授权已全面可信"。跨来源门禁仍需保留人为裁决。
- **证据**：详见 `progress/TECH_DEBT_EXECUTION_EVIDENCE.md` §4。

## TD-004 — 宿主端到端自动触发与轨迹导出缺失

- **登记日期**：2026-11-25
- **状态（2026-11-26 更新）**：⚪ **未验证 / 待用户**（保持未完成）
- **现象**：已确认 SourceLore Skill 在宿主安装/启用，可手动读取；但宿主无调用轨迹导出工具，无法保存"真实 Skill 自动发现并端到端触发"的完整证据。
- **影响**：宿主端到端触发属于"未完成"，只能标记，不能用手动 `read_local_skill` 冒充自动触发成功。
- **本轮处理**：本轮未执行任何冒充行为（不用内部 CLI/模拟会话/已有长会话当作真实宿主自动触发）；必须由用户在真实 OpenBot 独立新会话中实际使用验收。证据见 `progress/TECH_DEBT_EXECUTION_EVIDENCE.md` §6。

> 说明：以上四项均为独立技术债务。TD-001 已修复；TD-002、TD-003 部分解决且边界明确；TD-004 未验证待用户。公开版不含作者本机绝对路径、真实知识库内容原文或第三方未授权知识原文。

