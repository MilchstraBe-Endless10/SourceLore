#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Evidence-Claims 模块：canonical 定义与跨模块去向。

导出符号（本文件全部对外契约，构建器与验证器只读这三样）：
    MODULE                  本模块名 "Evidence-Claims"
    FIRST_ID                本批首个 canonical 编号 "SL-CAP-0020"
    CANON                   canonical 能力列表（9 条，ID 0020–0028）
    DEFERRED_TO_OTHER_MODULE 本批裁决后仍挂起的分流（本模块为 0 条，保留空声明）
    CONSUMED_THIS_BATCH    本批正式承接的 11 个原始身份（9 条 ROUTED + 2 条 ADAPT 并入）

ID 规则：从 SL-CAP-0020 起连续分配，不重排 0001–0019。
每条 refs 三元组：(upstream_id, original_capability_id, verdict)。
verdict 是本模块对该原始能力的采纳方式，与 disposition / 许可三者独立。
"""

MODULE = "Evidence-Claims"
FIRST_ID = "SL-CAP-0020"

# ── canonical 能力 ──────────────────────────────────────────────────────
CANON = [
    {
        "id": "SL-CAP-0020",
        "name": "证据材料存档契约（形态三分 + 强制元数据）",
        "description": (
            "每条结论背后的材料必须按三种形态之一存档，且存档记录必须是结构而不是散文："
            "full（完整原文可按内容哈希复算）、minimal（最小复现片段 + 不可复现说明）、"
            "none（不存，只登记引用与不可获取原因）。三种形态都必须携带强制元数据："
            "content_hash、reproducible 三态（yes|no|unknown）、redactions（脱敏清单）、"
            "以及对外部探测类材料的五样清单——响应体、相关响应头、无凭据的请求元数据、"
            "命令连同日期与工具版本与输入、与预期不符的差异说明。缺任何一项即判材料不完整，"
            "不得当作证据使用。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim_id", "raw_material（正文/响应/命令输出）", "probe_metadata"],
        "outputs": [
            "evidence_record{form: full|minimal|none, content_hash, reproducible, redactions[]}",
            "probe_record{response_body, response_headers, request_meta_no_credential, "
            "command{argv, version, date, input}, delta_note}",
            "evidence_completeness_verdict{complete|incomplete, missing_fields[]}",
        ],
        "depends_on_modules": ["Collector"],
        "overlaps": (
            "与 SL-CAP-0021 是同一证据的两层：本条管「材料本体怎么存」，"
            "0021 管「材料指向代码的哪一跳」。与 Collector 的 SL-CAP-0015 是上下游："
            "Collector 取回字节，本条决定留存形态"
        ),
        "unresolved": [
            "redactions 的语法（键名黑名单 vs 正则脱敏）与最小复现片段的切分粒度待 F2 定",
            "none 形态的材料是否允许在无网络环境下以引用字符串替代哈希，V1 先要求显式登记不可复现原因",
        ],
        "refs": [
            ("UPSTREAM-04", "C07", "ADAPT"),
            ("UPSTREAM-04", "C08", "ADAPT"),
        ],
        "notes": (
            "合并依据：U04-C07 的「完整存 / fixture + 说明 / 不存」三分法决定存档形态，"
            "U04-C08 的五样清单决定存档必须携带哪些元数据——它们是同一条能力的形态面与元数据面，"
            "拆成两条会各缺一半（三分法没有元数据就不可复算，清单没有形态就无法判完整性）。"
            "两处均判 ADAPT：C07 缺 content_hash 与 reproducible 三态，C08 的五样只是散文要求、"
            "未落为强制字段。修正方向都是把散文变成可机器校验的必填项。"
        ),
    },
    {
        "id": "SL-CAP-0021",
        "name": "逐跳数据流证据定位（四节点 file:line）",
        "description": (
            "把「这里有问题」表述成可核对的数据流链：entrypoint（外部输入进入点）→ hops[]（中间传播节点，"
            "每跳含 file:line 与传递语义）→ sink（实际发生作用的位置）。每个节点必须带"
            " path、line_start、line_end、symbol、role 五字段，行号必须指向采集快照中那份文件的真实行。"
            "链路不完整（缺入口或缺落地）时只能登记为 partial_flow，不得补写推测节点。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["conclusion_id", "pinned_snapshot（Collector 交付，含 path 与行号可定位）"],
        "outputs": [
            "flow_evidence{entrypoint: node, hops: node[], sink: node}",
            "partial_flow{missing_role, observed_nodes[]}",
            "node{path, line_start, line_end, symbol, role}",
        ],
        "depends_on_modules": ["Collector", "Facts"],
        "overlaps": "与 Facts 的 SL-CAP-0006（入口点候选识别）是同一概念的两种用途：Facts 用于抽取事实，本条用于挂证据",
        "unresolved": [
            "跨文件调用的 hop 是否需要附带调用点所在分支条件（if/loop）上下文，待 F2 定",
            "同一 sink 被多条链路命中时的去重键（path:line vs 链路签名）未定",
        ],
        "refs": [("UPSTREAM-06", "C05", "REIMPLEMENT")],
        "notes": (
            "U06-C05 的证据形态是全篇最可迁移的部分（entrypoint → hops → sink 逐跳 file:line），"
            "因此保留其结构思想。但判 REIMPLEMENT 而非 REUSE 有两个硬理由："
            "其一，U06 全 28 项 copy_permitted=false，任何实现不得复制，只能按非著作权的一般思想重做；"
            "其二，上游的四节点是散文式报告段落，没有结构化字段、没有 partial_flow 降级态，"
            "缺一跳就整条作废。本能力把结构固化为 schema 并补上显式降级。"
            "「逐跳」与「不可验证即判否」是两件事：逐跳定位只要求链路可核对，"
            "不因为查不到某跳就断定不存在——后者的裁决见 SL-CAP-0028。"
        ),
    },
    {
        "id": "SL-CAP-0022",
        "name": "引用存在性与定位校验",
        "description": (
            "任何引用（文件路径、符号、行号范围）在写入结论前必须对着钉定快照做一次存在性校验："
            "路径是否在树中、符号是否在文件里、行号是否落在有效范围内。校验结果三态记录："
            "present（可定位）、missing（快照中确实不存在）、unresolvable（快照被截断或不含该文件，无法判定）。"
            "missing 与 unresolvable 必须在产物里分列，不得合并为「未找到」。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["citation{path, symbol?, line_range?}", "pinned_snapshot", "tree_status"],
        "outputs": ["citation_check{citation, verdict: present|missing|unresolvable, observed_node?}"],
        "depends_on_modules": ["Collector", "Facts"],
        "overlaps": "与 SL-CAP-0021 的节点校验共用同一套存在性判定；与 Facts 的 SL-CAP-0004（树截断）直接相关：截断是 unresolvable 的正当来源",
        "unresolved": [
            "行号漂移的容忍度（同一 SHA 下行号不应漂移，故 V1 取精确匹配；若引入非钉定快照则需另定）",
            "符号解析在无语言分析器时的退化策略（仅做文本出现次数匹配）待 F2 定",
        ],
        "refs": [("UPSTREAM-01", "C03", "ADAPT")],
        "notes": (
            "U01-C03 判 ADAPT 的理由与审计一致：它只做了 tree_paths 集合的成员测试，"
            "既无行号校验也无哈希、没有「支撑关系」的概念，因此 present 之外的两种状态根本不存在。"
            "保留「引用必须先校验」的取向，补齐三态与符号/行号维度。"
            "特别强调 unresolvable 不得并入 missing：树被截断时「没找到」不等于「不存在」，"
            "这正是 F0 勘误与 Facts 的 SL-CAP-0004 反复强调的显式缺失语义在本模块的落点。"
        ),
    },
    {
        "id": "SL-CAP-0023",
        "name": "显式未知优于自信猜测",
        "description": (
            "证据不足时的输出必须显式标为未知或假设，不得以肯定语气陈述。硬规则："
            "无证据支撑的陈述不得以事实形态出现（Unsupported claims MUST NOT be presented as facts），"
            "只能记为 hypothesis 并附「为何不足」与「需要什么才能升级」。"
            "未知是合法终态：insufficient evidence 是成功产出，不是失败，也不是空白。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim{statement, evidence_refs[]}"],
        "outputs": ["claim_tier: fact|hypothesis|unknown", "insufficiency_note{why, what_would_upgrade}"],
        "depends_on_modules": [],
        "overlaps": "与 SL-CAP-0024 是同一方向的两种落点：本条管措辞层级，0024 管渲染占位符",
        "unresolved": [
            "fact / hypothesis / unknown 的判定是否允许由模型自评，还是必须由 evidence_refs 非空这一机械判据决定，V1 取后者（机械判据），前者待 F2",
        ],
        "refs": [("UPSTREAM-03", "C03", "REUSE")],
        "notes": (
            "U03-C03 两条原则短、无歧义、无工具依赖，且「Unsupported claims MUST NOT be presented as facts」"
            "可直接作 prompt 级硬规则，与 SourceLore「insufficient 是成功结果」的不变量同向，故判 REUSE。"
            "许可为 CC-BY-4.0：copy_permitted=true，但须履行署名、许可链接与修改声明三项义务。"
        ),
    },
    {
        "id": "SL-CAP-0024",
        "name": "缺料以占位符显式登记而非编造",
        "description": (
            "产物中任何因输入缺失而无法生成的位置，必须原样输出 [NEEDS INPUT] 占位，"
            "并在产物内列出 needs_input 清单（缺什么、为什么缺、需要谁提供）。"
            "禁止用示例值、默认值、看似合理的猜测填充。占位符必须可被机械检索（固定字面量），"
            "使「这份产物还缺哪些料」无需人工通读即可列出。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["slot{slot_id, required_field}", "available_inputs"],
        "outputs": ["rendered_slot（[NEEDS INPUT] 占位或真实内容）", "needs_input[]{slot_id, missing_field, requester}"],
        "depends_on_modules": [],
        "overlaps": "与 SL-CAP-0023 同向；与 SL-CAP-0027 的 incomplete 状态相邻（占位是产出侧，状态是裁决侧）",
        "unresolved": [
            "占位符的具体格式（[NEEDS INPUT] 字面量之外是否需要 slot_id 后缀）属实现决定，V1 只冻结字面量本身",
            "上游 U05-C05 的承接声明带 [NEEDS INPUT] 标记：本条只登记「缺料不编造」的语义与占位机制，"
            "不代为发明填充格式；填充格式的最终形态留 unresolved，不得凭空补写",
        ],
        "refs": [("UPSTREAM-05", "C05", "REUSE")],
        "notes": (
            "U05-C05 判 REUSE：直接对应「insufficient 是成功结果」这一不变量，且上游有代码出口"
            "（render_markdown_artifact 强制渲染 needs_input 列表），比 U04 的纯散文要求更强。"
            "许可 Apache-2.0，须履行署名、许可链接与修改声明。"
            "承接时遵守其 reason 自带的 [NEEDS INPUT]：本能力不编造渲染格式。"
        ),
    },
    {
        "id": "SL-CAP-0025",
        "name": "产物自证出处（Auto-generated 头 + 溯源字段）",
        "description": (
            "任何生成产物必须在头部声明自身是自动生成、由哪个工具版本、在哪次运行、基于哪个输入快照生成；"
            "正文中每条结论必须携带 evidence_refs 指向证据记录 ID。"
            "由此「这行字是谁写的、依据是什么」可机械判定，而不依赖读者相信作者的自我说明。"
            "手工编辑过的产物必须显式标注 edited_by_human 与编辑范围。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["artifact_body", "generator_identity{name, version}", "run_id", "evidence_ids[]"],
        "outputs": ["artifact_header{auto_generated, generator, run_id, source_snapshot, edited_by_human}",
                    "claim_traceability{claim_id → evidence_refs[]}"],
        "depends_on_modules": ["Collector"],
        "overlaps": "与 SL-CAP-0020 的证据记录是 ID 引用关系；与 Renderer 的产物渲染相邻，但溯源字段归本模块定义",
        "unresolved": [
            "edited_by_human 的编辑范围表示（行号区间 vs 段落 ID）待实现时定，V1 先要求布尔 + 自由说明",
            "source_snapshot 引用 commit_sha 还是 Bundle 的 manifest 哈希，取决于 F2 的 Bundle 契约",
        ],
        "refs": [("UPSTREAM-05", "C06", "REUSE")],
        "notes": (
            "U05-C06 判 REUSE：产物自证来源，使「这行字是谁写的」可机械判定，直接对应 evidence_refs 溯源要求。"
            "许可 Apache-2.0，须履行署名、许可链接与修改声明。"
            "与 SL-CAP-0024 同为 U05 的两条独立机制：一条管缺料，一条管出处，不合并。"
        ),
    },
    {
        "id": "SL-CAP-0026",
        "name": "结论四段结构与观察/解释分离",
        "description": (
            "每条结论必须由四段构成且段与段之间字段隔离："
            "answer（对问题的直接回答）、evidence（支撑该回答的证据引用）、"
            "artifacts（可复算的产物与命令）、limitations（本次结论的边界与已知不足）。"
            "核心约束是观察事实与解释必须可分离：evidence 段只允许写「看到了什么」（含 file:line 与原始输出），"
            "解释与推断只能出现在 answer 段并标明为推断。四段必须落为 schema 字段，不是 Markdown 段落标题。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["finding{question, observation, interpretation, evidence_refs[], artifacts[], limitations[]}"],
        "outputs": ["finding_record{answer, evidence[], artifacts[], limitations[], observation_separated: true}"],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": "与 SL-CAP-0021 的节点结构是引用关系（evidence 段引用 flow_evidence）；与 SL-CAP-0020 的存档记录是 ID 引用",
        "unresolved": [
            "answer 允许混入推断的比例与标注语法（如「推断：」前缀）待 F2 定；V1 只强制字段分离",
            "limitations 是否允许为空（若空是否等于「无限定」）待裁决，V1 取必填且可写 none",
        ],
        "refs": [("UPSTREAM-04", "C10", "ADAPT")],
        "notes": (
            "U04-C10 判 ADAPT：Answer/Evidence/Artifacts/Limitations 四段划分合理，"
            "L26「保持观察事实与解释可分离」是本模块最关键的一条不变量，但上游把它写成 Markdown 段落标题，"
            "无法机器校验「evidence 里混没混解释」。修正点即把四段转为 schema 字段并加字段隔离检查。"
        ),
    },
    {
        "id": "SL-CAP-0027",
        "name": "结论生命周期与新鲜度（四字段 + 结构化替代关系）",
        "description": (
            "每条结论携带结构化新鲜度：verified_commit（最后一次验证所针对的 commit SHA）、"
            "verified_deps（依赖清单哈希或版本集）、verified_env（工具与运行环境标识）、"
            "accessed_at（最后一次触达外部源的时间）。四项都必须可与其他结论比对，不得写成一段自由文本。"
            "结论的替代关系必须结构化：superseded_by / supersedes / retracted_reason 独立字段，"
            "被替代与已撤回的结论保留在产物中并标注状态，禁止删除历史。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim_id", "verification_context{commit_sha, deps, env, accessed_at}", "relation{kind, target_claim_id}"],
        "outputs": ["freshness{verified_commit, verified_deps, verified_env, accessed_at}",
                    "claim_relations{superseded_by?, supersedes[]?, retracted_reason?}",
                    "staleness_verdict{fresh|stale|unknown, basis}"],
        "depends_on_modules": ["Collector", "Lifecycle"],
        "overlaps": "与 Lifecycle 的过期检测共用 commit/deps 比对锚点；与 SL-CAP-0028 的状态机是输入关系（新鲜度是状态迁移的依据之一）",
        "unresolved": [
            "verified_deps 的表示（全量 lockfile 哈希 vs 直接依赖集合）待 F2；V1 取「可复算的哈希 + 依赖文件路径」",
            "superseded_by 与 retracted 是否允许同时存在（先替代后撤回）待裁决，V1 取互斥并要求显式选择",
        ],
        "refs": [
            ("UPSTREAM-04", "C11", "ADAPT"),
            ("UPSTREAM-04", "C09", "ADAPT"),
        ],
        "notes": (
            "合并依据：U04-C11 的 verified-against 与本条的四字段是同一个字段的拆分结果——"
            "上游把五种生命周期混在一个自由文本串里；U04-C09 的 superseded 关系是同一条结论的另一个维度"
            "（「这条结论还算不算数」）。两者共用 claim 的状态载体，拆开会出现两份互不知情的历史记录，故合并。"
            "C11 判 ADAPT：概念正确但不可比对（自由文本），须拆成四结构化字段。"
            "C09 判 ADAPT：思想对而形态太弱——superseded 只写在标题文字里、只有一种关系，无法机器查询；"
            "升级为独立关系字段并扩展为 superseded/supersedes/retracted 三态。"
        ),
    },
    {
        "id": "SL-CAP-0028",
        "name": "裁决状态机与 report_tier 映射（不可验证 ≠ 不存在）",
        "description": (
            "每条结论处于显式状态机的一态，状态由证据与校验结果驱动，不得由作者自评决定："
            "unverified（尚无证据）→ partially_supported（有部分证据且已校验）→ supported（证据完整且全部校验通过）"
            "→ refuted（存在反证）；旁支状态 insufficient_evidence（材料不足以判定，是合法终态）"
            "与 adjudication_blocked（依赖缺失，无法启动裁决）。"
            "source 侧九态压缩映射到本模块四态加两个旁支，映射表必须逐条落盘，不得隐式换算。"
            "report_tier 由状态固定映射（supported→confirmed、partially_supported→qualified、"
            "insufficient_evidence→insufficient、refuted→refuted），映射规则与状态机同表声明。"
            "硬规则：不可验证只产生 insufficient_evidence，禁止落成 refuted；"
            "「无法证明」不等于「已被证伪」。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim_id", "evidence_completeness_verdict", "citation_checks[]", "counter_evidence[]?"],
        "outputs": ["claim_status（六态之一）", "report_tier", "transition_record{from, to, trigger, evidence_ids[]}",
                    "state_mapping_table{source_state → local_state}"],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": "与 SL-CAP-0027 的 staleness_verdict 是并输入：新鲜度决定是否重开裁决；与 Renderer 的 report_tier 消费关系",
        "unresolved": [
            "refuted 需要几条独立反证才算成立、反证的证据强度如何分级，V1 先要求至少一条已校验反证 + 人工确认",
            "依赖缺失导致的 adjudication_blocked 何时转回 unverified（依赖补齐后是否自动重开）待 F2",
        ],
        "refs": [
            ("UPSTREAM-06", "C07", "ADAPT"),
            ("UPSTREAM-06", "C06", "ADAPT"),
        ],
        "notes": (
            "合并依据：U06-C07 提供状态机粒度与 report_tier 固定映射（这是状态机的骨），"
            "U06-C06 提供「不可验证该如何落状态」的判据（这是状态机的边）。"
            "若把 C06 单列，状态机会失去「查不到怎么算」这一关键分支；若把 C06 判 REUSE 原样搬用，"
            "则会把「不可验证」硬落成否定，与 SourceLore 的 insufficient 是成功结果直接冲突。故两者同条、均判 ADAPT。"
            "C07 判 ADAPT：九态偏多且与 SourceLore 四态 verification_status 不同构，"
            "本能力用六态（四主两辅）并保留逐条映射表，防止隐式换算。"
            "C06 判 ADAPT 并显式拒绝其原文语义：上游把「说不清」直接归入否定（can't prove → FALSE_POSITIVE），"
            "本能力只取其「必须给悬置一个确定去向」的取向，把去向改为 insufficient_evidence。"
            "该拒绝是裁决结论，不接受「不可验证即判否」作为可通过的规则。"
            "U06 两项均 copy_permitted=false，实现必须独立完成。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
# 本批裁决后，EC 不再把任何身份推给别的模块（本模块是接收方）。
# 保留空声明是为了让构建器的「def 声明 − 已晋升」公式对 EC 同样成立且为零。
DEFERRED_TO_OTHER_MODULE = {}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
# 9 条 ROUTED→EC（草稿 cross_module_redirections 里 owner_module=Evidence-Claims 的那批）
# 加 2 条在第 D 节判定为 ADAPT 并入本模块的未审命中（U04-C09、U06-C06）。
# 该声明是集成的唯一凭据：从路由表承接时 from="cross_module_redirections"，
# 从 UNREVIEWED 直接采纳时 from="unreviewed_adopted"。
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-01", "C03"): ("SL-CAP-0022", "cross_module_redirections"),
    ("UPSTREAM-03", "C03"): ("SL-CAP-0023", "cross_module_redirections"),
    ("UPSTREAM-04", "C07"): ("SL-CAP-0020", "cross_module_redirections"),
    ("UPSTREAM-04", "C08"): ("SL-CAP-0020", "cross_module_redirections"),
    ("UPSTREAM-04", "C09"): ("SL-CAP-0027", "unreviewed_adopted"),
    ("UPSTREAM-04", "C10"): ("SL-CAP-0026", "cross_module_redirections"),
    ("UPSTREAM-04", "C11"): ("SL-CAP-0027", "cross_module_redirections"),
    ("UPSTREAM-05", "C05"): ("SL-CAP-0024", "cross_module_redirections"),
    ("UPSTREAM-05", "C06"): ("SL-CAP-0025", "cross_module_redirections"),
    ("UPSTREAM-06", "C05"): ("SL-CAP-0021", "cross_module_redirections"),
    ("UPSTREAM-06", "C06"): ("SL-CAP-0028", "unreviewed_adopted"),
    ("UPSTREAM-06", "C07"): ("SL-CAP-0028", "unreviewed_adopted"),
}
