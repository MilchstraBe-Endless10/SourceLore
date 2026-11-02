#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Collector 模块：canonical 定义与跨模块去向。

ID 从 SL-CAP-0011 起，不得改动 0001–0010（Facts）。
每条 refs 三元组：(upstream_id, original_capability_id, verdict)。
verdict 是本模块对该原始能力的采纳方式，与 disposition / 许可三者独立。
"""

MODULE = "Collector"

# ── canonical 能力 ──────────────────────────────────────────────────────
CANON = [
    {
        "id": "SL-CAP-0011",
        "name": "唯一采集入口与传输层可替换性",
        "description": (
            "SourceLore 只存在一个逻辑 Collector。逻辑接口（端点语义、请求构造、结果规范化）"
            "与传输适配（当前为已认证 gh api 子进程）分离；传输层只负责把一次逻辑请求变成一次 HTTP 往返，"
            "并把原始响应体与状态码原样交回。任何数据契约都建立在本层规范化后的结构上，"
            "不依赖 gh 的输出格式（不支持 --jq 结果直通、不解析 CLI 的人类可读输出）。"
            "禁止出现第二套客户端：无自带 token 通道、无直接 urllib/requests 旁路、无第二份配额口径。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["logical_request{endpoint, params, accept} ", "authenticated_transport"],
        "outputs": ["raw_response{status, headers, body}", "transport_identity{kind, version}"],
        "depends_on_modules": [],
        "overlaps": "U01-C15 与 U02-C18 都是「自建客户端」，被本能力吸收为反例约束而非实现来源",
        "unresolved": [
            "传输适配当前绑定 gh api 子进程；未来替换为直连 HTTP 时，接口需保持 logical_request 不变，验证方式待 F2 定",
            "gh api 的 --paginate 与 --slurp 语义需在实现时逐个实测确认，本批不做",
        ],
        "refs": [
            ("UPSTREAM-01", "C15", "REJECT"),
            ("UPSTREAM-02", "C18", "REJECT"),
            ("UPSTREAM-02", "C01", "ADAPT"),
            ("UPSTREAM-02", "C04", "ADAPT"),
        ],
        "notes": (
            "合并依据：U01-C15 与 U02-C18 是同一件事在两个上游里各自做了一份，"
            "裁决相同（都判 REJECT 自建客户端），因此不是两条能力而是一条负向约束的两个证据源。"
            "U02-C01 的端点清单与 Accept 用法正确，保留为端点规格表来源；"
            "U02-C04 只取「单一依赖不阻断运行」的取向，明确弃用其 urllib 双通道实现。"
        ),
    },
    {
        "id": "SL-CAP-0012",
        "name": "输入识别规范化与身份解析",
        "description": (
            "把用户给出的 GitHub URL、owner/repo、repository id 三种形态统一规范化为内部身份，"
            "并解析出仓库的稳定身份（repository_id 与 node_id，而非可变 owner/name）与默认分支。"
            "默认分支不硬编码 main/master，交由服务端在解析阶段确定。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["url | owner/repo | repository_id"],
        "outputs": ["canonical_repo_identity{repository_id, node_id, owner, name}",
                    "default_branch", "normalization_record{input_form, rejected_variants}"],
        "depends_on_modules": [],
        "overlaps": "U02-C02 的 HEAD 解析只用于这一次解析，解析完必须立刻钉 SHA，与 Facts 的 SL-CAP-0002 交接",
        "unresolved": [
            "repository_id 与 owner/name 变更（转移、改名）同时出现时的判定优先级，V1 先以前者为准，待实现验证",
            "私有仓库无权限时的错误语义归入 SL-CAP-0017 的错误分类，本能力不重复定义",
        ],
        "refs": [("UPSTREAM-02", "C02", "REUSE")],
        "notes": (
            "U02-C02 是全部六源里唯一设计正确的一处：不把默认分支写死。直接采纳。"
            "但采纳范围严格限定为「解析那一次」——上游没有在解析后钉 SHA，这一步必须由本能力补上。"
        ),
    },
    {
        "id": "SL-CAP-0013",
        "name": "Commit 与根 Tree 的钉定（三字段分列）",
        "description": (
            "解析得到默认分支后立即把完整 commit SHA 钉死，之后所有取数一律以该 SHA 为 ref，不再使用分支名。"
            "根 tree SHA 必须来自 GET /commits/{ref} 的 commit.tree.sha，不得从 trees 端点响应的 sha 字段取。"
            "commit_sha、root_tree_sha、tree_query_ref 是三个独立字段，禁止互相替代或视为同义词。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["canonical_repo_identity", "default_branch | explicit_ref"],
        "outputs": ["pinned_snapshot{commit_sha, root_tree_sha, tree_query_ref, resolved_at}",
                    "pin_consistency_report{checks[], verdict}"],
        "depends_on_modules": ["Collector"],
        "overlaps": "与 SL-CAP-0012 是解析与钉定的两段；与 F0 勘误 E-02 直接相关",
        "unresolved": [
            "F2 的 snapshot_manifest_v2 需把三字段固化为 schema 必填，本批只裁决语义不定义 schema",
            "使用归档包获取（archive_tarball）的仓库没有 tree_query_ref，字段缺失的表示形式待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源：上游只做了「用 HEAD 解析」，没有做「解析完立刻钉 SHA」，更没有区分根 tree 与查询标识。"
            "F0 勘误 E-02 已实测：GitHub Trees API 在 ref 为 commit-ish 时 sha 字段回显请求标识，"
            "四源的 tree.json.sha 全部等于各自 commit SHA 而非真实根 tree。"
            "因此本能力必须是 REIMPLEMENT：目标对，上游无对应实现。"
        ),
    },
    {
        "id": "SL-CAP-0014",
        "name": "分页遍历与完整覆盖判据",
        "description": (
            "按 per_page 逐页取数，直到服务端明确表示没有下一页（Link 的 rel=next 缺失），"
            "不得用「返回条数少于 limit」作为终止判据。每页的覆盖范围必须累计记录，"
            "最终产出一个可核对的 total_fetched 与 expected_total 对照。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["endpoint", "per_page", "pagination_mode"],
        "outputs": ["items[]", "pagination_record{pages, per_page, next_link_seen, total_fetched}", "coverage_verdict"],
        "depends_on_modules": ["Collector"],
        "overlaps": "与 SL-CAP-0018 的覆盖记录共用 coverage 结构",
        "unresolved": [
            "部分端点不支持 Link 头（如某些 search 结果），其终止判据需按端点单独登记，待实现时逐个确认",
        ],
        "refs": [("UPSTREAM-02", "C06", "ADAPT")],
        "notes": (
            "循环结构可借，但上游的 if len(items) < limit: break 是错的——"
            "PR 密集仓库会因此提前退出，覆盖不全且无声。"
            "改为以 Link rel=next 为准，或与 per_page 比较而非与调用方 limit 比较。"
        ),
    },
    {
        "id": "SL-CAP-0015",
        "name": "原始正文直取与结构化树采集",
        "description": (
            "文件正文取用 raw media type（Accept: application/vnd.github.raw）直接拿到字节，"
            "绕开 base64 编解码环节；目录结构取用 trees 端点 recursive=1 并保留结构化条目"
            "（path、mode、type、sha、size），不生成供人阅读的缩进字符串。"
            "所有请求的 ref 必须是 SL-CAP-0013 钉定的 SHA。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["pinned_snapshot", "path[]"],
        "outputs": ["blob_bytes[]", "tree_entries[{path, mode, type, sha, size}]", "tree_truncated_flag"],
        "depends_on_modules": ["Collector"],
        "overlaps": "树数据供 Facts 的 SL-CAP-0004 做截断降级；本能力只负责取回与标注 truncated 标志",
        "unresolved": [
            "trees 响应 truncated=true 时的补取策略（逐子树递归 vs 换用归档包）待 F2 裁决",
        ],
        "refs": [
            ("UPSTREAM-02", "C03", "REUSE"),
            ("UPSTREAM-02", "C09", "REJECT"),
        ],
        "notes": (
            "U02-C03 正确：raw accept 避免 base64 往返，沿用。"
            "U02-C09 的 format_tree 判 REJECT——lines[:100] 静默截断、max_depth=3 静默丢层，"
            "Collector 需要结构化数据而非渲染用字符串，且静默截断违反「缺失必须显式」。"
            "两条原始能力在此合成一条：一条是正面做法，一条是反面约束。"
        ),
    },
    {
        "id": "SL-CAP-0016",
        "name": "Issue 与 PR 的分离采集",
        "description": (
            "GitHub /issues 端点混排 Issue 与 Pull Request，采集时必须按 pull_request 字段的存在与否分流，"
            "分别进入 issue 集合与 pr 集合，不得混为一谈。PR 额外采集其 diff 与 head/base 元数据。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["endpoint=/issues", "items[]"],
        "outputs": ["issues[]", "pull_requests[]", "classification_record{total, issue_n, pr_n, unclassified}"],
        "depends_on_modules": ["Collector"],
        "overlaps": "PR diff 采集与 Security 模块的增量审查需求相邻，但原始记录采集归 Collector",
        "unresolved": [
            "unclassified（既无 pull_request 字段也无 issue 特征）的记录如何处理，V1 先单列不丢，具体裁决待 F1-C",
        ],
        "refs": [("UPSTREAM-02", "C07", "REUSE")],
        "notes": (
            "上游为这个坑专门发过 commit 5ca17829be，是被实践反复证明的语义，直接沿用。"
        ),
    },
    {
        "id": "SL-CAP-0017",
        "name": "失败即异常与错误分类",
        "description": (
            "采集失败必须以异常形式中断，携带 endpoint、HTTP 状态码、响应体与分类标签；"
            "失败绝不允许写成一条看起来像数据的记录（例如空数组、空 README）从同一个通道流下去。"
            "错误分类至少覆盖：认证失败、限流、未找到、网络不可达、响应格式异常。"
            "限流需携带 reset 时刻并可被上层安排重试。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["raw_response"],
        "outputs": ["collection_error{endpoint, status, category, retry_after, body_excerpt}"],
        "depends_on_modules": ["Collector"],
        "overlaps": "与 Facts 的 SL-CAP-0007 是上下游：Collector 抛出的错误状态被 Facts 记录为 failed/unavailable",
        "unresolved": [
            "哪些分类属于「可恢复失败」、重试几次，待实现时结合真实限流数据确定，V1 先只做分类不做自动重试",
        ],
        "refs": [("UPSTREAM-02", "C08", "REJECT")],
        "notes": (
            "本条不引用 UPSTREAM-02::C05——该条已归入 Facts 的 SL-CAP-0007「事实抽取失败与缺失的显式表示」，"
            "Facts 层承接的是「失败如何在产物里被表示」，本能力承接的是「失败如何在采集层被抛出」，"
            "两者是上下游而非同一件事，故此处按归属唯一性改用其他来源。"
            "采用的反面证据是 U02-C08 summarize_repo：该函数三处 except Exception 静默吞掉异常，"
            "使失败与「确实没有数据」在下游无法区分，直接催生了错误分类的结构要求。"
            "故本能力对 C08 判 REJECT，只取其反例，不取其实现。"
        ),
    },
    {
        "id": "SL-CAP-0018",
        "name": "只读缓存与一致性校验",
        "description": (
            "对已钉 SHA 的采集结果做只读缓存，缓存键为 commit_sha 加端点加参数，缓存内容带自校验"
            "（内容哈希与条目清单哈希）。缓存只能加速、不能改变语义：命中缓存与重新采集必须返回等价结构。"
            "缓存缺失时不得静默回落到远端并假装命中，必须记录 cache_status。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_DEFERRED",
        "inputs": ["pinned_snapshot", "logical_request"],
        "outputs": ["cache_entry{key, content_sha256, manifest_sha256, created_at}",
                    "cache_status{hit|miss|stale|corrupt}"],
        "depends_on_modules": ["Collector", "Storage"],
        "overlaps": "缓存内容落在磁盘上，与 Storage 的持久化边界相邻；本能力只定义缓存语义与完整性校验，不定义存储布局",
        "unresolved": [
            "缓存目录与失效策略属 Storage 决策，边界待 F1-C 确认",
            "U06-C13 的「本地缓存优先 + 缺失静默回落」判为不可采纳的手法，本能力只保留「缺失必须显式」",
        ],
        "refs": [("UPSTREAM-06", "C13", "REJECT")],
        "notes": (
            "上游六源没有任何一个实现了「只读缓存 + 完整性校验」，U06-C13 有的是依赖包缓存且手法错误"
            "（缓存缺失时静默回落 registry，审计记为 D17）。故本能力 REIMPLEMENT，"
            "只取「锁来源、缺口写入产物」的方向，具体实现与缓存路径一律不可复用。"
            "U06 无许可，只取非著作权的一般思想。"
        ),
    },
    {
        "id": "SL-CAP-0019",
        "name": "统一只读数据接口",
        "description": (
            "Collector 对上只暴露一个只读接口：输入 SnapshotRequest，输出 SnapshotBundle。"
            "Bundle 内含 repo_identity、pinned_snapshot、tree_entries、blobs、issues、pull_requests、"
            "commits、releases、coverage_record、errors[]、cache_status。"
            "下游模块（Facts、Evidence、Product）只能读 Bundle，不得自行发起 GitHub 请求。"
            "接口一旦发布即冻结，变更需版本号。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["SnapshotRequest{repo, ref, scope[], budget}"],
        "outputs": ["SnapshotBundle（只读、带 schema_version）"],
        "depends_on_modules": ["Collector"],
        "overlaps": "与 Facts 的 SL-CAP-0002 是消费关系：Facts 从 Bundle 派生 repo_facts.json，不重新取数",
        "unresolved": [
            "Bundle 的正式 schema 属 F2 的 Manifest V2 范畴，本批只定义字段清单与只读约束",
            "scope 的粒度（全量 vs 按需分区）待实现时按真实仓库规模确定",
        ],
        "refs": [],
        "notes": (
            "本条无直接上游来源，是本次裁决的架构决定：六源中没有统一的只读数据接口，"
            "每个源各取各的。既然 SourceLore 只允许一个 Collector，就必须显式定义这个出口，"
            "否则「唯一入口」在下游会退化成多个隐性入口。属于不依赖上游著作权的独立设计。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-04", "C11"): (
        "Evidence-Claims",
        "verified-against 是 Claim 的新鲜度字段，属 Evidence；Collector 只提供 commit_sha 作为比对锚点",
    ),
    ("UPSTREAM-05", "C17"): (
        "Lifecycle",
        "过期检测按内容哈希比对，属生命周期管理；Collector 只保证快照可复算",
    ),
    ("UPSTREAM-06", "C18"): (
        "Security",
        "成本报告是安全审查运行的自报字段，与采集无关",
    ),
    ("UPSTREAM-06", "C24"): (
        "Security",
        "PR diff 增量审查属安全模块的审查逻辑；Collector 只负责把 diff 原样取回",
    ),
    ("UPSTREAM-02", "C11"): (
        "Research",
        "Broad to Narrow 是查询策略，属研究流程，不是数据采集",
    ),
}

# ── 从 Facts 批次分流中接手的身份 ────────────────────────────────────────
# Facts 批次把这两项判给了 Collector 但其 canonical 尚未建立，因此在 F1-B/Facts
# 的产出里它们是 DEFERRED_TO_MODULE 状态。本批为它们真正建了 canonical，
# 身份从 ROUTED 迁移到 MAPPED —— 必须有据可查，否则「ROUTED -> MAPPED」无声发生。
# 键：(upstream_id, original_capability_id) -> (承接它的 canonical_id, 迁移理由)
# 该声明是幂等的基石：草稿合并后原始分流记录已被消费，无法再从磁盘反推。
PROMOTED_FROM_FACTS = {
    ("UPSTREAM-02", "C06"): (
        "SL-CAP-0014",
        "Facts 批次判为分页语义、去向 Collector；本批建 SL-CAP-0014 正式承接该身份",
    ),
    ("UPSTREAM-02", "C09"): (
        "SL-CAP-0015",
        "Facts 批次判为结构化树采集、去向 Collector；本批建 SL-CAP-0015 正式承接该身份",
    ),
}
