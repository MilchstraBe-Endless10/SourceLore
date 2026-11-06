# F2-P6B 执行报告

基线 `1b1426c`。

## 结论

真实 GitHub 仓库 `jonschlinkert/is-number` 的**字节**已经走通完整的入库到查询链路，
来源可核验（OID 逐一比对）。

两处外部条件仍然没关：GitHub 每小时 60 次的匿名配额，以及 Harness 自然语言触发需要你的独立会话。

本轮抓到 **5 个新缺陷**，全部是「逻辑存在但链路没接通」：
声明式空参数、只入库不建命题、查询侧字段缺失、对象 id 不对齐、变量被覆盖。全部已修。

## 一、限流诊断

```
GET https://api.github.com/rate_limit   2026-11-06T13:20:53+08
status 200, authenticated false
X-RateLimit-Limit      60
X-RateLimit-Remaining  0
X-RateLimit-Used       60
X-RateLimit-Resource   core
X-RateLimit-Reset      1793942591 → 2026-11-06T05:23:11Z
Retry-After            无
```

判为主限流（primary）：remaining=0 且 used=limit。
次级限流的特征是 403/429 配 Retry-After 且 remaining 通常非 0，此处不成立。

13:23:41 复检 remaining=45，配额已重置，开始采集。
13:25:52 再复检 remaining=0 —— 120 秒内再次耗尽（探测 + 内容采集都计入）。

恢复依据始终是响应头给出的 reset 时间，没有一次是猜的。

## 二、真实仓库身份

| 项 | 值 |
|---|---|
| 仓库 | jonschlinkert/is-number |
| repository_id | 24313173 |
| 固定 Commit | 98e8ff1da1a89f93d1397a24d7413ed15421c139 |
| Commit 日期 | 2018-07-04 |
| root tree | 37450e1347ebbad642393376ee3ef67f576d1109 |
| tree 条目 | 13，truncated=false |

## 三、许可证与授权

LICENSE blob `9af4a67d206f24ecdbb5fdff2839041ca0bbd346`，1091 字节：

```
The MIT License (MIT)
Copyright (c) 2014-present, Jon Schlinkert.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software ... to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute...
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
```

判定：`LICENSE_OBSERVED_AND_APPLICABLE`，适用于该 Commit。
五维：FETCH/PERSIST/DERIVE_FACTS 允许，PREVIEW 允许，DISTRIBUTE **仍然 DENY**。
`copy_permitted=false`、`distribution_allowed=false` 未改动。

## 四、真实字节核验

| 文件 | GitHub OID | 字节 | OID 自校验 | 本地 git 复算 |
|---|---|---|---|---|
| LICENSE | 9af4a67d206f… | 1091 | ✓ | ✓ 一致 |
| README.md | eb8149e8cf5f… | 6514 | ✓ | ✓ 一致 |
| package.json | 3715072609d6… | 1599 | ✓ | ✓ 一致 |
| index.js | 27f19b757f7c… | 411 | ✓ | —（未入库） |

真实字节落到本地对象库，commit `41dee5ac90993da43b1b253cb393ef97d8dddd5a`。
**本地 git 复算出的 blob OID 与 GitHub 报告的完全相同** —— 这是字节真实性的独立验证。

## 五、入库结果

```
snapshot   1
captured_blob_content  2  (README.md, package.json)
extracted_fact        51  (README 44 + package.json 7)
claim_candidate        5
claim_verification     5
```

`analyze` 输出 `content_facts_total=51`，`success_contract.highest=KNOWLEDGE_QUERYABLE`。

## 六、查询

```
query --type content --path README.md
→ state=SUPPORTED  net=0
   claims 3  verifications 3（supported ×3）
```

之前这里是 `INSUFFICIENT_EVIDENCE`。差别就是 D-47 那一条：内容事实入库了，
但没有任何命题与之对应，查询判定「证据不足」本身是完全正确的。

## 七、离线复用

```
首次：51 事实 / 5 claim / 5 verif / 2 blob / 1 snapshot
二跑：net=0，指纹完全不变
卡片：16613 字节，README_CONTENT_CARD
```

## 八、五个新缺陷

**D-46 `license_known` 是声明式空参数。** CLI 有 `--license-known`，`capture()` 签名里有
`license_known`，函数体**零引用**。所以带不带这个开关都一样：FETCH/PERSIST 全 UNKNOWN。
这种参数最阴——它出现在 `--help` 里，用户以为开了就会生效。

**D-47 内容链路只入库不建命题。** P6A 只建了路径命题（`repository_path_exists`），
内容事实虽然入了 A 层，但没有 Claim/Verification 覆盖它们。查询因此正确地报证据不足。

**D-48 查询侧缺字段。** `query_content_facts` 返回扁平记录，缺 `normalized_parameters` 与
`repository_id`，而裁决侧 `_matches` 读的是嵌套结构。D-31/D-41 的第三次复现。

**D-49 `written` 不含 subject。** `ingest_content_facts` 返回的 `written` 条目只有
`fact_id/rule_id/asset_id/observation_id`。原始抽取 facts 的 id 与之不对齐。
建命题时拿不到主体，`bind={'level': None}`。

**D-50 变量被覆盖。** 循环里多写一行 `rid = w.get("rule_id") or ""`，
把刚从事实取到的 `rid` 覆盖成空串 → 全部落进 `else: continue`，静默零命题。

## 九、D-42 永久防护

新增 `src/skill_interface/success_contract.py`，把「成功」拆成八档：

```
COMMAND_EXECUTED → SNAPSHOT_SAVED → CONTENT_CAPTURED → PARSING_COMPLETED
→ FACTS_PERSISTED → CLAIMS_VERIFIED → KNOWLEDGE_QUERYABLE → CARD_RENDERED
```

`command_ok_is_success` 恒为 `False`。`analyze` 输出带 `success_contract`，
`ok=True` 不再等于「知识建立了」。

`assert_expected_facts` 只对调用方明确预期的输入断言，不设「每文件至少一条」的硬规则。

## 十、安装版完整性

```
launcher sha256  cfd254245b1dc043a725cc1fcb99f45586fb2c773776bb351fcaf8a374ebe66a
SKILL.md sha256  e710729b4a7665005d49fd4fa4765d7082c17a1e46799d01f5f2c0b9408be7fe
project_root     .../SourceLore
```

形态：**LOCAL_DEV_LINKED_INSTALL**。安装目录只有 launcher + SKILL.md + references，
业务模块从工程 `src/` 实时加载。不能复制到别的机器直接跑，也不是发行包。

## 十一、测试

```
1381 项，失败 0，退出码全 0
```

## 十二、门禁

| 门禁 | 状态 | 依据 |
|---|---|---|
| A INSTALLED_SKILL_INTEGRITY | **DONE** | 两个完整 SHA-256 已记录 |
| B LOCAL_DEV_INSTALL_PROVENANCE | **DONE** | 形态明确，未冒充发行包 |
| C LOCAL_PRODUCT_E2E_REGRESSION | **DONE** | product_acceptance 21/21 |
| D GITHUB_RATE_LIMIT_DIAGNOSIS | **DONE** | 完整头字段，判主限流 |
| E REAL_GITHUB_REPOSITORY_AUTHORIZATION | **DONE** | MIT 原文绑定该 Commit |
| F REAL_GITHUB_COLLECTION | **PARTIAL** | commit/tree 采到；blob 抓取被限流打断 |
| G REAL_GITHUB_CONTENT_PERSISTENCE | **DONE** | 真实字节入库，OID 复算一致 |
| H REAL_GITHUB_FACTS_AND_CLAIMS | **DONE** | 51 事实 / 5 claim / 5 verif |
| I REAL_GITHUB_INSTALLED_SKILL_QUERY | **DONE** | state=SUPPORTED, net=0 |
| J REAL_GITHUB_KNOWLEDGE_CARDS | **DONE** | 16613 字节 |
| K REAL_GITHUB_OFFLINE_REUSE | **DONE** | 指纹不变，net=0 |
| L NATURAL_LANGUAGE_SKILL_DISCOVERY | **NOT_VERIFIED** | 缺独立会话 |
| M NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** | 缺独立会话 |
| N D42_SUCCESS_CONTRACT_REGRESSION | **DONE** | 八档契约 + 零事实断言 |
| O CROSS_MODULE_SCHEMA_CONTRACT | **DONE** | D-48/D-49/D-50 修复 |
| P PATH_AND_STORAGE_SECURITY | **DONE** | 回归通过 |
| Q MULTI_COMMIT_ISOLATION | **DONE** | P6A 双 Commit 结论保持 |
| R F1D_FREEZE_INTEGRITY | **DONE** | 哈希复算匹配 |
| S DISTRIBUTION_READY | **NOT_READY** | B-1/B-2/B-3 OPEN |

F 给 PARTIAL 而不给 DONE：commit 和 tree 是真的采到了，但 4 个 blob 里只有
3 个走完 API 路径，第 4 个（index.js）在限流时被挡。字节是我在限流前抓到的，
不能倒过来算作「采集完成」。

## 十三、必须说清的边界

- 真实 GitHub 字节 → 本地对象库 → 完整链路，这条是真的。
- 但 `analyze https://github.com/...` 的**服务端 blob 抓取路径**没有全程跑完，
  因为配额不够。那个路径的状态是 `BLOB_HTTP_ERROR: RATE_LIMITED`。
- 我用了限流前抓到的字节，这不是绕过限流，但也**不等于**产品自己跑通了那条路径。
- 下一个月度窗口内配额重置后，需要再跑一次端到端，才能把 F 转成 DONE。

## 十四、下一阶段

可以进入用户使用与知识库维护阶段——本地和真实 GitHub 两条知识链路都已可用。
但**自然语言自动触发**这一关没你不行，那是 SourceLore 能不能被日常用起来的真正门槛。
