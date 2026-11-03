#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Storage 模块：canonical 定义与跨模块去向。

导出符号：
    MODULE                    "Storage"
    FIRST_ID                  "SL-CAP-0062"
    CANON                     6 条 canonical（0062–0067）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的身份（本批 3 条）
    CONSUMED_THIS_BATCH       本批正式承接的 11 个身份（5 条 ROUTED + 6 条未审直采）

ID 规则：从 SL-CAP-0062 起连续分配，不重排 0001–0061。
"""

MODULE = "Storage"
FIRST_ID = "SL-CAP-0062"

CANON = [
    {
        "id": "SL-CAP-0062",
        "name": "四层资产模型与单一权威（历史 / 当前视图 / 派生索引 / 展示产物）",
        "description": (
            "Storage 管理的全部数据分四层，读写权限各不相同，且同一事实只有一个权威副本："
            "A 层 不可变历史资产——已固定版本的 Evidence、Findings、历史 Claim、来源快照引用、变更记录。"
            "只允许追加，禁止原地覆盖已提交记录。"
            "B 层 可变当前视图——Subject 当前使用的知识版本、当前引用关系、最新有效视图。"
            "允许更新，但更新当前指针不得破坏 A 层任何记录。"
            "C 层 派生索引——全文搜索索引、关系查询索引、导航索引及其他加速数据。"
            "必须能从 A+B 层完整重建；禁止作为唯一权威来源。"
            "D 层 展示产物——Markdown、卡片、报告、导航页。"
            "其生成失败、删除或重建不得破坏 A/B/C 层。"
            "硬规则一：任何事实不得同时存在两个可独立修改的权威副本。"
            "B 层的「当前值」若与 A 层某条历史记录冲突，以 A 层为事实源，B 层只是指针。"
            "硬规则二：C 层可被整体删除：删除后权威数据不受影响，重建后查询结果等价。"
            "硬规则三：D 层不得回写 A/B 层；Renderer 的重生成只产新 D 层产物。"
            "硬规则四：四层的读写依赖必须在设计文档中画清，禁止出现「展示层顺手补一条权威数据」的暗通道。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["write_intent{layer, object, payload}", "read_query{layer_scope}"],
        "outputs": [
            "layer_contract{layer: A|B|C|D, write_mode: append|update|rebuild|generate, authority: bool}",
            "authority_violation{attempted_layer, offending_write, reason}",
            "rebuild_record{index_id, source_layers[], equivalent: bool}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Lifecycle", "Renderer"],
        "overlaps": (
            "与 Lifecycle 的 SL-CAP-0041（可变层与不可变层分离）是同一结构的两个视角："
            "0041 定语义规则（哪些能改、哪些只追加），本条定物理层面的读写权限与重建契约。"
            "两者不重复：0041 说「历史只追加」，本条说「因此 A 层只接受 append 写入且无 delete 接口」"
        ),
        "unresolved": [
            "四层各自的存储介质（单文件 / 目录树 / 数据库表）待 F2；本批只定语义契约",
            "B 层当前视图与 A 层历史记录冲突时的判定 UI 与提示归 Renderer，本批只定「以 A 为事实源」",
            "D 层产物是否需要登记进权威清单（还是纯文件系统）待 F1-C",
        ],
        "refs": [
            ("UPSTREAM-04", "C03", "REIMPLEMENT"),
            ("UPSTREAM-05", "C18", "REIMPLEMENT"),
        ],
        "notes": (
            "合并依据：U04-C03（索引是派生视图、禁止手改）与 U05-C18（索引生成）是同一件事的两处证据——"
            "U04 给出「派生索引消除并发冲突」的理由，U05 给出「上游把矛盾改名而不是解决」的反例"
            "（gen_index.py 输出的是 Index Regeneration Candidate，从不写 index.md，权威索引仍靠人手写）。"
            "两者合起来说明：派生层必须是 C 层，且 A/B 层才是权威。"
            "U04-C03 判 REIMPLEMENT 而非审计建议的 REUSE：上游只写了「索引由报告派生」这一句话，"
            "没有任何写入侧的强制；本条把它升格为带读写权限的四层契约。"
            "U05-C18 判 REIMPLEMENT：上游的索引生成器只产出候选、不落最终索引，闭环缺最后一步（审计 D2）。"
            "该身份来自 U04 的既有分流（指向 Storage），本批建 canonical 正式承接。"
        ),
    },
    {
        "id": "SL-CAP-0063",
        "name": "身份层级与版本标识（对象身份、内容哈希、业务版本三者分离）",
        "description": (
            "知识对象携带三种身份，语义严格分离，不得混用："
            "逻辑身份——长期稳定、跨版本不变：repository_id（仓库身份锚点）、subject_id（知识主体）、"
            "claim_id / evidence_id（对象自身 ID）。逻辑身份一旦分配永不复用。"
            "内容身份——由内容算出的确定性摘要：content_hash。同一内容哈希必同一内容；"
            "内容变化必然改变哈希。用于完整性校验与「是否真的变过」的判定。"
            "业务版本——人为推进的版本号：artifact_version、当前版本指针、superseded_by 链。"
            "硬规则一：不得用仓库 URL、文件路径或 Commit SHA 作为 Subject 的永久唯一身份。"
            "repository_id 可作为仓库身份锚点，但不得自动等同于所有知识 Subject 的唯一身份"
            "（一个仓库可以有多个 Subject，一个 Subject 也可能跨仓库）。"
            "硬规则二：对象身份、内容哈希与业务版本不得互相替代。"
            "六个标识必须分列：repository_id、subject_id、commit_sha、root_tree_sha、evidence_id/claim_id、"
            "artifact_version。这是 F0 勘误 E-01「三字段不可互换」的扩展。"
            "硬规则三：不可变对象的内容身份 = content_hash；其逻辑身份 = 对象 ID；两者共同定位一条记录。"
            "硬规则四：superseded_by 链必须可追溯，且只作用于当前视图（B 层），不改写历史记录。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["object{logical_id, content, proposed_version}", "identity_context{repository_id, subject_id}"],
        "outputs": [
            "object_identity{logical_id, content_hash, artifact_version}",
            "identity_conflict{field, attempted_value, reason}",
            "version_chain{current_version, superseded_by[]}",
        ],
        "depends_on_modules": ["Collector", "Lifecycle", "Evidence-Claims"],
        "overlaps": (
            "与 Lifecycle 的 SL-CAP-0040（Subject 身份）是同一契约的两端：0040 定义 Subject 身份三件套，"
            "本条定义「存储层怎么分配主键、怎么保证不复用、怎么与内容哈希和版本号分离」。"
            "与 Collector 的 SL-CAP-0013（三字段分列）直接承接 F0 勘误 E-01"
        ),
        "unresolved": [
            "subject_id 的分配算法（内容派生 vs 单调计数）待 F2",
            "跨仓库 Subject 的主键表示待 F1-C（与 SL-CAP-0040 的 unresolved X-3 关联）",
            "artifact_version 是单调数还是 commit 派生，待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是内部设计能力。内部需求依据写明："
            "SourceLore 的四层模型（SL-CAP-0062）落地必须有主键契约，而六源中没有任何一处"
            "给出「逻辑身份 / 内容哈希 / 业务版本」三者分离的存储层定义——上游的索引表只有四列且"
            "summary 被要求不含结论（U04-C23 的审计说明），既无内容哈希也无版本链。"
            "本条与 SL-CAP-0040（Subject 身份）的关系是「语义定义 vs 存储分配」："
            "0040 说 Subject 由哪三件确定，本条说存储层怎么把它们落成不复用的主键。"
            "F0 勘误 E-01 的三字段不可互换是本条的直接前身，本条把它从「取数三字段」扩展到「全部身份标识」。"
        ),
    },
    {
        "id": "SL-CAP-0064",
        "name": "原子写入、乐观并发与崩溃恢复",
        "description": (
            "写入必须走五步契约，任一步失败都不得暴露半写入的权威资产："
            "W-1 先写入临时/隔离区域，不触碰权威位置。"
            "W-2 写入前校验结构完整性与引用完整性（引用的对象必须存在、类型必须匹配）。"
            "W-3 记录预期的当前版本（expected_version），作为后续 CAS 的比较基准。"
            "W-4 只有版本一致才允许提交当前指针（B 层）；版本不一致必须返回明确的并发冲突，"
            "禁止静默覆盖。"
            "W-5 失败或崩溃后，权威位置保持上一份已提交状态；临时区域残留可被安全清理。"
            "四条硬规则："
            "其一，多文件重命名不得宣称跨文件原子事务——文件系统的 rename 只保证单文件原子性，"
            "跨文件的原子性需要显式记录提交日志或使用真正的事务存储，本条要求如实声明原子性范围。"
            "其二，并发冲突必须明确返回（CONFLICT），不得吞掉并降级为空结果。"
            "其三，重试不得重复创建相同的不可变对象（A 层按 content_hash 幂等）。"
            "其四，崩溃恢复后必须能判断哪些写入已提交：已提交 = 权威位置可见；未提交 = 仅临时区域可见。"
            "可选实现手段（文件系统 + 原子 rename / SQLite 事务 / 单写者队列 / 乐观 CAS / "
            "不可变对象存储 + 当前指针）由 F2 选定，本条只定接口语义。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["write_intent{payload, expected_version}", "target_layer"],
        "outputs": [
            "write_receipt{status: committed|conflict|invalid|failed, committed_version, atomicity_scope}",
            "conflict_detail{expected_version, actual_version, retryable}",
            "recovery_report{committed[], pending[], orphaned_temp[]}",
        ],
        "depends_on_modules": ["Lifecycle"],
        "overlaps": (
            "与 Lifecycle 的 SL-CAP-0043（增量调度）分界：0043 决定「该做哪些动作、按什么顺序」，"
            "本条决定「每个动作落地时怎么保证不写坏」。0043 的幂等性要求由本条的 CAS 与内容哈希幂等实现"
        ),
        "unresolved": [
            "具体存储引擎（文件系统 / SQLite / 其他）待 F2，本轮不安装依赖、不建库、不实现引擎",
            "跨文件原子性的实现（提交日志 vs 单文件事务库）待 F2",
            "单写者队列与多 Agent 并发的取舍待 F1-C（与 DSH Adapter 的调度边界关联）",
        ],
        "refs": [
            ("UPSTREAM-04", "C22", "REIMPLEMENT"),
            ("UPSTREAM-05", "C22", "REIMPLEMENT"),
        ],
        "notes": (
            "合并依据：U04-C22 与 U05-C22 是同一条缺口在两份审计里的独立记录——"
            "U04 侧无锁、无原子写、无幂等、无冲突检测（D8）；U05 侧所有脚本直接 write_text_file 覆写，"
            "无锁无版本校验，多人或 AI 与人同时更新会静默丢写入。两处描述的是同一个失败模式。"
            "两处均判 REIMPLEMENT：上游完全没有实现，只留下「应当这样」的取向。"
            "本条的 W-1..W-5 与四条硬规则是自建——特别是「多文件重命名不得宣称跨文件原子事务」这一条，"
            "是对「看起来原子」的常见误判的直接防护。"
        ),
    },
    {
        "id": "SL-CAP-0065",
        "name": "可重建派生索引与跨会话结构化查询",
        "description": (
            "查询接口分三类，且都必须保留来源与版本："
            "Q-1 按身份定位：按 repository_id 找仓库知识、按 subject_id 恢复 Subject、"
            "按 claim_id 找证据与裁决、按 commit_sha 查历史版本。"
            "Q-2 按属性过滤：按路径或组件找受影响知识、按状态找需要重新验证的条目、"
            "按知识类别（Product / Research / Security）筛选、按版本/来源/状态复合过滤。"
            "Q-3 双通道：查新知识走索引（C 层），消费已知知识走直链（按 ID 直达），"
            "避免每次消费都扫全库。"
            "硬规则一：每条查询结果必须携带 source_snapshot 与 retrieved_from_layer，"
            "使「这条答案依据哪个版本」可判定。"
            "硬规则二：查询结果来自已登记知识，不意味着被查仓库的实时状态；"
            "检索命中不能自动成为已验证的新 Claim。"
            "硬规则三：索引可整体重建，重建后同一查询返回等价结果（除时间戳外）。"
            "硬规则四：不得在没有必要时引入向量数据库或图数据库；"
            "文本检索、结构化检索可并存，向量/图仅在有明确必要性时由 F2 议定。"
            "硬规则五：权限拒绝必须显式返回 denied，不得伪装成空结果。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["query{kind: identity|filter|direct, criteria}", "caller_context{permissions}"],
        "outputs": [
            "query_result{items[], source_snapshot, retrieved_from_layer, truncated}",
            "query_denied{reason, required_permission}",
            "index_health{built_at, source_versions[], stale: bool}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Lifecycle"],
        "overlaps": (
            "与 Renderer 的 SL-CAP-0055（视图派生）分界：本条提供数据检索接口，Renderer 消费其结果做呈现。"
            "与 Lifecycle 的 SL-CAP-0042（失效检测）分界：本条提供「按状态筛选需要重验的条目」的通道，"
            "判定何时失效归 0042"
        ),
        "unresolved": [
            "查询接口的具体形态（CLI 子命令 / 库函数 / 文件级 API）待 F2",
            "索引结构（倒排 / 关系表 / 扁平 JSON）待 F2",
            "是否最终需要向量或图检索，留 F1-C 议定（本批明确不预设）",
        ],
        "refs": [
            ("UPSTREAM-04", "C23", "REIMPLEMENT"),
            ("UPSTREAM-05", "C23", "REIMPLEMENT"),
            ("UPSTREAM-04", "C04", "ADAPT"),
        ],
        "notes": (
            "合并依据：U04-C23 与 U05-C23 是同一条缺口的两次独立记录——"
            "U04 的索引只有四列且 summary 被要求不含结论（D10），无法按结论/commit/证据检索；"
            "U05 全文只有文件系统遍历与文本搜索，没有任何索引数据结构或查询接口。"
            "U04-C04（双通道检索）提供第三条信息来源：找新知识走索引、消费已有知识走直链，"
            "是四源中唯一考虑检索成本的架构，补上「查询不只是过滤、还有两条使用路径」这一层。"
            "U04-C23 / U05-C23 判 REIMPLEMENT（上游无实现）；U04-C04 判 ADAPT"
            "（取向正确但只是散文描述，本条把它落成 Q-3 通道定义）。"
            "U04-C23 该身份来自既有分流（指向 Storage）。"
        ),
    },
    {
        "id": "SL-CAP-0066",
        "name": "多仓库关系持久化（五类关系分离，禁止凭空推断影响）",
        "description": (
            "跨仓库关系必须分类持久化，五类各有独立的证据要求与验证状态："
            "R-1 同一仓库身份延续——靠 repository_id 不变判定（改名、转移）。"
            "R-2 Fork 关系——靠 forked_from 判定，是关联不是延续，两者各自独立 Subject。"
            "R-3 代码依赖关系——靠依赖清单解析（从 Facts 取），不是靠名字相似。"
            "R-4 Submodule / 其他仓库引用——靠仓库内引用声明（.gitmodules、清单字段）。"
            "R-5 研究中发现的外部关联——靠 Research 的证据，必须带 evidence_refs。"
            "硬规则一：关系条目必须携带 relation_kind、evidence_refs、verification_status 三件。"
            "无证据的关联只能是 suspected，不得记为 verified。"
            "硬规则二：不得因为两个仓库名称相同、依赖同名包、或作者相同，就认定它们具有"
            "经过验证的组织、供应链或安全影响关系。"
            "硬规则三：跨仓库影响推断不属 Storage——需要 Research、Security 与 EC 参与；"
            "Storage 只提供关系持久化与查询，不做影响判定。"
            "硬规则四：不得引入图数据库；关系以普通记录形式持久化，需要图状查询时由查询层自行组装。"
            "本条只承接「跨仓库引用与关联」这一层语义；上下游链合成、服务拓扑、跨服务攻击面合成"
            "均不属于本模块。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["relation{from, to, kind, evidence_refs[], verification_status}"],
        "outputs": [
            "relation_record{relation_id, from, to, relation_kind, evidence_refs[], verification_status}",
            "relation_query_result{relations[], source_snapshot}",
            "inference_violation{attempted_inference, reason}",
        ],
        "depends_on_modules": ["Collector", "Facts", "Research", "Evidence-Claims"],
        "overlaps": (
            "与 Lifecycle 的 SL-CAP-0040（Subject 身份）有交集：R-1 / R-2 依赖其身份判定。"
            "与 Research 的 SL-CAP-0035 分界：Research 负责发现外部关联并产出证据，本条负责持久化"
        ),
        "unresolved": [
            "五类关系的字段清单待 F2",
            "suspected 关系是否允许出现在默认查询结果中，待 F1-C",
            "关系图的呈现归 Renderer（SL-CAP-0057 的可选图表），本批只定持久化形态",
        ],
        "refs": [("UPSTREAM-06", "C19", "REIMPLEMENT")],
        "notes": (
            "U06-C19 判 REIMPLEMENT，但裁决中明确缩小了范围，理由写清以免误读："
            "上游是「多仓库拓扑与跨服务合成」（phase0-topology 全文 + phase7-synthesis L55–L162），"
            "其形态可借鉴，但 SourceLore 的跨源关系不是服务拓扑，而是知识单元之间的依赖与矛盾——"
            "审计原文已指出「直接搬用会产生第二套关系模型，违反单一模型约束」。"
            "故本条只承接其中**跨仓库引用与关联关系**这一层，明确排除服务拓扑与跨服务攻击面合成。"
            "该身份来自 Security 批次的既有分流（Security 判定「会产生第二套关系模型、应落在 Storage」），"
            "本批建 canonical 正式承接。UPSTREAM-06 无复制授权，只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0067",
        "name": "知识资产根目录隔离与路径安全",
        "description": (
            "知识资产根目录必须独立于被分析仓库，并具备四层隔离："
            "P-1 根目录显式声明——根路径必须由显式配置或参数确定，禁止隐式假设当前工作目录。"
            "P-2 按仓库命名空间隔离——每个 repository_id 一个独立子命名空间，"
            "路径由 identity 派生而非用户输入的 owner/name（后者可变、可重复）。"
            "P-3 路径穿越防护——任何由外部数据（仓库文件内容、Issue 文本、配置值）派生的路径，"
            "在拼接前必须做规范化与根目录包含校验；符号链接必须解析后校验真实路径，"
            "禁止通过链接、文件名或 Markdown 链接跳出根目录。"
            "P-4 只读源快照与可写产物的边界——外部源码快照一律只读存放且与可写产物物理分处；"
            "自动扫描结果永不写回被分析仓库。"
            "硬规则一：第三方仓库内容一律作为数据处理，不因其出现在配置或清单里而获得写权限。"
            "硬规则二：不可信内容不得通过任何方式访问本地私有文件或环境变量；"
            "分析任务的工具调用遵循最小权限。"
            "硬规则三：知识资产根目录不得位于被分析仓库内部（candidate：违反者一律拒绝），"
            "这是对上游「一仓库一 corpus 住在仓库内」模型的明确拒绝。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["knowledge_root（显式）", "repository_id", "external_derived_path"],
        "outputs": [
            "namespace_layout{root, repo_namespace, readonly_snapshot_area, writable_artifact_area}",
            "path_rejection{attempted_path, normalized_path, reason}",
            "root_binding{root, source: config|cli|env, validated: bool}",
        ],
        "depends_on_modules": ["Collector", "Security"],
        "overlaps": (
            "与 Renderer 的 SL-CAP-0058（生成/人工隔离）相邻但不同：0058 隔离「生成产物 vs 人工文档」，"
            "本条隔离「知识资产 vs 被分析源码」，是两个不同层次的边界。"
            "与 Security 的 SL-CAP-0052（不可信数据处理）是执行面关系：0052 定规则，本条定路径落点"
        ),
        "unresolved": [
            "知识根目录的默认位置约定待 F2",
            "同一仓库不同分支/不同 commit 的快照是否共用命名空间，待 F1-C",
            "路径穿越防护的具体实现（realpath 校验 vs 沙箱）待 F2",
        ],
        "refs": [
            ("UPSTREAM-05", "C09", "ADAPT"),
            ("UPSTREAM-04", "C25", "REJECT"),
            ("UPSTREAM-05", "C26", "REJECT"),
        ],
        "notes": (
            "合并依据：U05-C09（PKB_ROOT 与项目分离）给「显式声明根路径」的正面做法；"
            "U04-C25 与 U05-C26 是同一错误模型的两次独立 REJECT——「一个仓库一个 corpus，住在仓库内」"
            "会导致语料无法跨仓库复用、污染被分析对象的 git 历史，且 worktree 不复制等一整套做法失效。"
            "三者合起来才构成完整裁决：正的取「显式根路径」，反的取「绝不写在仓库内」。"
            "U05-C09 判 ADAPT：可借的是显式声明根路径这一做法（避免隐式假设 cwd），不借其存放位置策略。"
            "U04-C25 与 U05-C26 均判 REJECT 并作为反面约束登记在本条 refs 中——"
            "这是本条唯一包含 REJECT verdict 的地方，因为它们确实被本条用来约束设计（硬规则三）。"
            "该 U05-C09 身份来自既有未审项，非分流。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-05", "C19"): (
        "Evidence-Claims",
        "人类主导的语义补充（人写的字段带签名、AI 写入该字段直接拒绝）本质是「谁有权写哪个字段」的"
        "权限语义，已由 EC 的 SL-CAP-0028（裁决状态机，含人工确认分支）与 Security 的 SL-CAP-0053"
        "（发布门禁，P-3/P-4 只能由人触发）承接；Storage 只执行访问控制，不定义权限语义",
    ),
    ("UPSTREAM-05", "C14"): (
        "Renderer",
        "版本页脚七字段属产物呈现格式（作者、更新时间、版本等元信息的展示形态），归 Renderer 的视图契约",
    ),
}

CONSUMED_THIS_BATCH = {
    ("UPSTREAM-04", "C03"): ("SL-CAP-0062", "cross_module_redirections"),
    ("UPSTREAM-05", "C18"): ("SL-CAP-0062", "unreviewed_adopted"),
    ("UPSTREAM-04", "C22"): ("SL-CAP-0064", "cross_module_redirections"),
    ("UPSTREAM-05", "C22"): ("SL-CAP-0064", "unreviewed_adopted"),
    ("UPSTREAM-04", "C23"): ("SL-CAP-0065", "cross_module_redirections"),
    ("UPSTREAM-05", "C23"): ("SL-CAP-0065", "unreviewed_adopted"),
    ("UPSTREAM-04", "C04"): ("SL-CAP-0065", "unreviewed_adopted"),
    ("UPSTREAM-06", "C19"): ("SL-CAP-0066", "cross_module_redirections"),
    ("UPSTREAM-05", "C09"): ("SL-CAP-0067", "unreviewed_adopted"),
    ("UPSTREAM-04", "C25"): ("SL-CAP-0067", "unreviewed_adopted"),
    ("UPSTREAM-05", "C26"): ("SL-CAP-0067", "unreviewed_adopted"),
}
