# F1-B / Collector 批次设计裁决

任务：`M1-FUSION-GATE-F1 / F1-B` 第二批 —— Collector 模块。
范围：只做能力归并、设计裁决、验收、提交。不进入 F2，不实现正式 Collector。

---

## 一、本批产出

| 项 | 值 |
|---|---|
| canonical 条目 | 9 条（`SL-CAP-0011` … `SL-CAP-0019`） |
| 归入 Collector 的原始身份 | 11 个 |
| Collector 主动分流给其他模块 | 5 条 |
| 全表 canonical 总数 | 19（Facts 10 + Collector 9） |

`SL-CAP-0001` … `SL-CAP-0010` 逐字节未改动，编号从 `SL-CAP-0011` 起连续，无断号、无重排。

---

## 二、进度统计口径（本次修正的核心）

此前进度里记的是 `raw_assigned` / `raw_pending`，把「已归入」和「已分流」混成一个数。本轮起分成三个互斥状态：

| 状态 | 含义 | 本批结束 |
|---|---|---|
| `mapped_count` | 已被某条 canonical 正式承接 | 22 |
| `routed_pending_count` | 去向已裁决、但接收模块尚未真正承接 | 14 |
| `unreviewed_count` | 尚未审阅 | 107 |
| 合计 | | 143 |

`22 + 14 + 107 = 143`，与原始身份集等势，无重复、无遗漏。`canonical_count = 19` 单列，不与原始身份混算。

**ROUTED 不等于 MAPPED。** 分流只是说「这条该归谁」，不等于那个模块已经把它接住；只有写进某条 canonical 的 `upstream_refs` 才算 `mapped`。

---

## 三、逐条裁决

### SL-CAP-0011 唯一采集入口与传输层可替换性
处置 REIMPLEMENT / V1_REQUIRED。来源 4 条：`U01-C15` REJECT、`U02-C18` REJECT、`U02-C01` ADAPT、`U02-C04` ADAPT。
两条 REJECT 提供同一个反向约束的两份证据（都存在第二套独立客户端）。`U02-C01` 给出端点规格表，`U02-C04` 只保留「单一依赖不阻塞」这一判断，其 urllib 双通道做法丢弃。
设计分四层：逻辑接口 / 当前鉴权与传输适配（`gh api`）/ 可验证原始数据 / 未来可替换传输。数据契约不绑定 GitHub CLI 的输出格式。

### SL-CAP-0012 输入识别规范化与身份解析
处置 REUSE / V1_REQUIRED。来源 `U02-C02`。
身份用 `repository_id` / `node_id`，不用可变的 owner/name —— 仓库改名换主后 owner/name 会指向别处。

### SL-CAP-0013 Commit 与根 Tree 的钉定（三字段分列）
处置 REIMPLEMENT / V1_REQUIRED。**无上游来源。**
本条是对上游缺口的补足：上游只做「用 HEAD 解析」，从不钉死 SHA，同一仓库两次分析可能对着不同提交。
`commit_sha` / `root_tree_sha` / `tree_query_ref` 三个字段独立，禁止互相替代。根树必须取 `GET /commits/{ref}` 的 `commit.tree.sha`——Trees API 会把你请求的 commit-ish 原样回显到 `sha` 里，直接读它就会把提交 SHA 当成树 SHA。依据勘误 E-02 / E-03。

### SL-CAP-0014 分页遍历与完整覆盖判据
处置 ADAPT / V1_REQUIRED。来源 `U02-C06` ADAPT。
`if len(items) < limit: break` 明确判为错误，改用 `Link` 响应头的 `rel=next`。短页不等于末页。

### SL-CAP-0015 原始正文直取与结构化树采集
处置 REUSE / V1_REQUIRED。来源 `U02-C03` REUSE、`U02-C09` REJECT。
`format_tree` 判 REJECT：`lines[:100]` 与 `max_depth=3` 会静默截断，截断后下游无法分辨「树就这么多」还是「被砍了」。

### SL-CAP-0016 Issue 与 PR 的分离采集
处置 REUSE / V1_REQUIRED。来源 `U02-C07` REUSE（上游提交 `5ca17829be`）。
Issue 与 PR 在 GitHub 上是两张表，混采会把 PR 摘要混进 Issue 计数。

### SL-CAP-0017 失败即异常与错误分类
处置 REUSE / V1_REQUIRED。来源 `U02-C08` REJECT。
错误分五类：鉴权 / 限流 / 未找到 / 网络 / 格式异常。V1 只分类并记录，不自动重试。
**本条刻意不引用 `U02-C05`**：该条已归入 Facts 的 `SL-CAP-0007`「事实抽取失败与缺失的显式表示」。Facts 承接的是失败如何被表示，Collector 承接的是失败如何被抛出，是上下游两件事。改取 `U02-C08` 作反面证据——`summarize_repo` 三处 `except Exception` 静默吞异常，让失败和「确实没有数据」在下游无法区分，正是这条能力要防的情形。

### SL-CAP-0018 只读缓存与一致性校验
处置 REIMPLEMENT / **V1_DEFERRED**。来源 `U06-C13` REJECT。
驳的是静默回退到注册表这种失败模式。缓存路径与布局归 Storage，边界留给 F1-C 裁决。UPSTREAM-06 无许可证授权，只取非著作权的通用思路。

### SL-CAP-0019 统一只读数据接口
处置 REIMPLEMENT / V1_REQUIRED。**无上游来源。**
独立架构决策。`SnapshotRequest` 进，`SnapshotBundle` 出，下游只许读 Bundle，不许自己再去调 GitHub。正式 schema 留到 F2 的 Manifest V2。

---

## 四、分流的 5 条（不属于 Collector）

| 原始身份 | 去向 | 理由 |
|---|---|---|
| `U04-C11` | Evidence-Claims | verified-against 时效判断 |
| `U05-C17` | Lifecycle | 按内容哈希判陈旧 |
| `U06-C18` | Security | 成本报告 |
| `U06-C24` | Security | PR diff 增量审查 |
| `U02-C11` | Research | Broad-to-Narrow 查询策略 |

---

## 五、冲突处理记录

本轮构建首次运行报出五处归属冲突，全部在定义文件里解决，没有放松任何校验：

1. `U02-C05` 已被 Facts `SL-CAP-0007` 占用 → `SL-CAP-0017` 改取 `U02-C08`。
2. `U02-C06` / `U02-C09` 上一批已分流给 Collector → 本批接手，分流记录转为正式归属，草稿新增 `routed_promotions` 留痕。
3. `U02-C02` 在 `SL-CAP-0012` 与 `SL-CAP-0013` 重复出现 → `0013` 改为无来源（理由见上）。
4. 三态计数之和 145 ≠ 143 → 因重叠归属导致，随 1–3 修正后回到 143。
5. 构建器原先在校验前就写盘，失败会留下半成品 → 改为全部校验通过后才落盘；配 `git checkout` 恢复基线。

---

## 六、验收

`python3 tools/fusion/f1b_verify_collector.py` 26 项全通过，结果写入 `docs/fusion/F1B_COLLECTOR_VERIFICATION.json`。
