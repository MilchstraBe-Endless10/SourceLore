#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Research 模块：canonical 定义与跨模块去向。

导出符号（构建器与验证器只读这三样）：
    MODULE                    "Research"
    FIRST_ID                  "SL-CAP-0035"
    CANON                     5 条 canonical（0035–0039）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的 3 个身份
    CONSUMED_THIS_BATCH       本批正式承接的 9 个身份（1 条 ROUTED + 8 条未审直采）

ID 规则：从 SL-CAP-0035 起连续分配，不重排 0001–0034。
"""

MODULE = "Research"
FIRST_ID = "SL-CAP-0035"

CANON = [
    {
        "id": "SL-CAP-0035",
        "name": "有界研究阶段流水线（R0–R4 状态机 · 预算 · 可恢复）",
        "description": (
            "研究必须走五个有界阶段，每个阶段有各自的输入、最小输出与退出条件，不得把「读完了」当完成：\n"
            "R0 定题——明确研究问题、要回答的具体问句、以及本次不研究什么；输出 research_scope。\n"
            "R1 内读——只消费 Facts 与 Product 已有的确定性产物，不发起任何采集；输出 internal_gap_list。\n"
            "R2 外研——仅针对 R1 列出的缺口，经 Collector 取外部证据；每条外部材料必须标来源类型与采集时刻。\n"
            "R3 交叉——对不同来源的结论做比对，产出 claim_candidates[] 与 conflict_items[]，不自行裁决真伪。\n"
            "R4 收口——综合、登记未知项与研究质量状态，产出 research_report 与 remaining_questions[]。\n"
            "阶段可跳过但必须留痕：跳过要写 skip_reason 与 affected_conclusions；R1 无缺口时可直接进 R4。\n"
            "每阶段必须有预算（读取条目数上限、调用次数上限），预算耗尽时停下并保存已完成的有效证据与待研究清单，"
            "不得产出「看起来完整」的报告。中断恢复时从阶段边界续跑，只补缺口，不重跑已完成的采集与分析。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["research_question", "facts_bundle（Facts/Product 产物）", "stage_budget"],
        "outputs": [
            "stage_record{stage_id, inputs_used, outputs_produced, budget_used, skip_reason?}",
            "research_state{completed_stages[], current_stage, remaining_questions[]}",
            "resume_point{stage_id, evidence_already_gathered[]}",
        ],
        "depends_on_modules": ["Facts", "Collector", "Product"],
        "overlaps": (
            "与 Product 的 SL-CAP-0032 是不同层的分轮：0032 管「单个仓库内产品语义怎么分轮取数」，"
            "本条管「跨越仓库边界、需要外部资料的调查怎么分阶段推进」。两者共享分轮思想，不共享阶段定义"
        ),
        "unresolved": [
            "各阶段的预算数值待 F2 按仓库规模与模型窗口定，本批只要求「每阶段必须声明预算」",
            "R2 的外部资料是否允许在无网络环境下以缓存证据替代，待 F1-C",
            "研究中断与 Lifecycle 的知识失效如何保持正交：本条只管「这次研究跑到哪」，"
            "不管「上次研究结论今天还成不成立」，后者属 Lifecycle 的 SL-CAP-0027（新鲜度）",
        ],
        "refs": [("UPSTREAM-02", "C10", "REIMPLEMENT")],
        "notes": (
            "U02-C10 判 REIMPLEMENT：上游的分轮与由广到深的探索顺序正确，但四条轮次只是散文——"
            "无状态载体、无轮间交接结构、无预算强制、无退出路径（审计 blocker 级缺陷）。"
            "本能力把散文改写成五阶段状态机，并为每阶段定义输入、最小输出、跳过条件与恢复点。"
            "关键是两条反教条：阶段完成不等于结论正确（R3 只产出候选，裁决交 Evidence-Claims）；"
            "资料读完不等于研究完成（R4 必须显式列出 remaining_questions）。"
        ),
    },
    {
        "id": "SL-CAP-0036",
        "name": "由广到窄的查询策略与来源去重",
        "description": (
            "外部研究采用由广到窄的查询序列：先取仓库元数据与顶层结构，再取README/文档与发行说明，"
            "再取社区信号（Issue/PR/Discussion），最后才做针对性深挖。每一步都必须记录查询式、"
            "结果条数与是否命中预期，未命中的查询同样要留痕（negative_result）。\n"
            "去重是硬要求：URL 必须规范化（去 utm_* 与追踪参数、统一大小写主机名、去掉尾部斜杠、"
            "解析重定向到最终地址），内容必须按正文哈希去重——镜像转载、聚合站二次发布、"
            "同一 Release 的多种呈现都必须折叠为一条来源。去重后的独立来源计数才是「多来源交叉」的有效计数。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["research_question", "query_plan", "raw_results[]"],
        "outputs": [
            "query_record{query, step, hits, expected_hit, negative_result?}",
            "normalized_source{canonical_url, content_hash, original_urls[], mirror_of?}",
            "independent_source_count",
        ],
        "depends_on_modules": ["Collector"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0020（存档契约）是前后关系：本条负责去重与规范化，"
            "0020 负责去重后那一条怎么存档。与 Collector 的 SL-CAP-0014（分页覆盖）不重叠："
            "那条管单端点翻页，本条管跨来源的同一性判定"
        ),
        "unresolved": [
            "内容哈希的去重粒度（全文 vs 首段 vs 正文去标签后）待 F2，V1 取正文去标签后的 SHA-256",
            "negative_result 是否要求记录「已尝试但无结果」的具体查询式，V1 取必填",
            "同一来源反复更新时（如 Issue 有新评论）是否视为新来源，待 F1-C",
        ],
        "refs": [("UPSTREAM-02", "C11", "ADAPT")],
        "notes": (
            "U02-C11 判 ADAPT：查询模板序列可直接借用，但上游完全没做去重与 URL 规范化——"
            "这会让镜像转载击穿它自己的「2+ 独立来源」三角验证要求（审计缺陷）。"
            "补上规范化与内容哈希折叠后，「独立来源数」才是一个可核对的量，而不是作者自报的错觉。"
            "本条同时承接了 Collector 批次留下的分流：U02-C11 原本被判「Broad to Narrow 属研究流程、"
            "不是数据采集」而挂起，本批建 canonical 正式承接。"
        ),
    },
    {
        "id": "SL-CAP-0037",
        "name": "来源类型标记与覆盖记录（优先级不替代验证）",
        "description": (
            "每条外部材料必须携带结构化来源标记：source_type 四值（github_api / readme_claim / "
            "external_web / inference）、retrieved_at（采集时刻）、verified_against_commit（"
            "本次结论所针对的源码快照 SHA，可为空）、coverage（full / partial / truncated），"
            "以及 unavailable_reason（当数据因限流、权限、分页失败或端点缺失而拿不到时的具体原因）。\n"
            "硬规则一：来源类型不构成真伪排序。不因为来自 GitHub API 就认定内容为真——"
            "Issue 正文可能是用户报告，README 可能是维护者声明，两者都是待验证的主张而非事实。\n"
            "硬规则二：不得使用未校准的置信度百分比。\n"
            "硬规则三：partial、truncated、unavailable 与实际为空（empty）四种状态必须分别记录，"
            "禁止把「没拿到」写成「没有」。\n"
            "两个时间必须分开保存：retrieved_at（这次采集发生在什么时候）与 verified_against_commit"
            "（这次结论对哪个源码版本成立），前者会过期，后者是版本锚点，二者不可互换。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["raw_material", "collection_metadata{retrieved_at, endpoint, page_state}", "pinned_snapshot"],
        "outputs": [
            "source_marker{source_type, retrieved_at, verified_against_commit, coverage, unavailable_reason?}",
            "coverage_record{requested[], obtained[], partial[], truncated[], unavailable[]}",
        ],
        "depends_on_modules": ["Collector", "Evidence-Claims"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0020 有明确分界：0020 管「材料本体怎么存档」（哈希、脱敏、形态三分），"
            "本条管「这条材料是什么类型的来源、覆盖到什么程度、对哪个版本成立」。"
            "与 SL-CAP-0022（引用三态校验）不重叠：那条校验引用是否可定位，本条标记来源是否可信与完整"
        ),
        "unresolved": [
            "source_type 四值是否足够（是否需要区分官方文档、第三方博客、自动生成摘要），待 F1-C",
            "verified_against_commit 为空的合法情形（纯生态研究无源码依赖时）需明确，待 F2",
            "本条与 Evidence-Claims 的 evidence_record 在产物中如何避免字段重复，待 F2",
        ],
        "refs": [
            ("UPSTREAM-02", "C14", "ADAPT"),
            ("UPSTREAM-02", "C12", "ADAPT"),
        ],
        "notes": (
            "合并依据：C14 的来源分桶（Primary/Media/Academic/Community）是「这条材料是什么类型」，"
            "C12 的五层来源优先级是「不同类型该怎么排序」——两者是同一件事的正反两面，"
            "且都必须落成字段才能机器校验。合并后明确：分桶保留为 source_type，"
            "而优先级被显式降级为「不构成真伪排序」，这正是用户第 4.B 节要求的区分。"
            "C14 判 ADAPT：思想正确（全套资产里最接近来源类型标记的设计），但只是模板里的分组小标题，"
            "须升级为结构化字段 + retrieved_at + commit_sha。"
            "C12 判 ADAPT：分层直觉正确，但仅有序数无权重、且「verified media outlet」无定义——"
            "本条不追求量化权重，改采「有定义才可用」的立场：进层规则不可判定时该层不启用。"
            "这条裁决同时化解了用户第 5 节第 1 项冲突：来源优先级不得替代 Evidence-Claims 的验证规则。"
        ),
    },
    {
        "id": "SL-CAP-0038",
        "name": "研究质量状态与结论边界（三态 + 不产报告的许可）",
        "description": (
            "研究产出必须带质量状态，三值且语义互斥：complete（所声明的研究范围已满足本批验收要求）、"
            "partial（部分完成，缺口已在 coverage_record 中逐条登记）、facts_only（只完成事实收集，"
            "不足以支撑解释性结论）。质量状态描述「研究的完备程度」，不描述「任务是否成功」，"
            "两者必须分开记录，不得用质量状态替代执行状态。\n"
            "硬规则一：不要求每次研究都产出报告。无新发现、或只完成 facts_only 时，"
            "允许只登记研究结果与空结论，禁止为了「有产物」而填充解释。\n"
            "硬规则二：结论边界必须显式——报告必须声明本次研究覆盖了什么、没覆盖什么、"
            "哪些结论依赖单一来源、哪些还需进一步验证。\n"
            "硬规则三：多来源综合得出的推断若与已有 claim 冲突，不得自行裁决，"
            "必须产出 handoff_item 移交 Evidence-Claims 的裁决状态机（SL-CAP-0028）。\n"
            "本能力只定义研究产物的内容骨架（结论、证据引用、覆盖、边界、移交项），"
            "不含章节顺序、排版、图表等呈现决策——那些属 Renderer。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim_candidates[]", "coverage_record", "remaining_questions[]"],
        "outputs": [
            "research_quality{status: complete|partial|facts_only, basis}",
            "research_report{conclusions[], evidence_refs[], coverage_summary, boundaries[], handoff_items[]}",
            "handoff_item{claim, conflicting_claim_ref, sources[], reason}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Renderer"],
        "overlaps": (
            "与 Renderer 的分界：本条定「报告必须包含哪些内容项」，Renderer 定「这些项怎么排版成文档」。"
            "与 Evidence-Claims 的 SL-CAP-0028 是移交关系：本条的 handoff_item 是 0028 的输入之一"
        ),
        "unresolved": [
            "complete/partial/facts_only 的判定阈值（覆盖率达到多少算 complete）待 F1-C，最终枚举留给 F2",
            "handoff_item 与 EC 的 conflict_item 在产物中如何避免双写，待 F2",
            "Research 与 Product 对同一功能的分析如何避免重复生成 claim："
            "本批原则是「Product 产产品语义 claim 候选、Research 产生态与研究 claim 候选，"
            "两者都进 Evidence-Claims 去重」，具体去重键待 F2",
        ],
        "refs": [
            ("UPSTREAM-02", "C13", "ADAPT"),
            ("UPSTREAM-02", "C15", "REJECT"),
            ("UPSTREAM-03", "C27", "REJECT"),
            ("UPSTREAM-06", "C23", "ADAPT"),
            ("UPSTREAM-04", "C26", "REJECT"),
        ],
        "notes": (
            "合并依据：C13 给报告内容骨架，U06-C23 给「不评质量只评敢不敢用」的结论形态，"
            "U04-C26 与 U02-C15 是两个必须显式拒绝的反面约束（「必须产报告」「用百分比标置信度」），"
            "四者都指向同一件事：研究结论该以什么形态落地、什么叫「够了」。"
            "C13 判 ADAPT：九节划分覆盖面合理可作骨架，但必须去掉固定基数与无条件 Status: Complete，"
            "把置信度换成可机械复核的条件陈述。"
            "U06-C23 判 ADAPT：其「不评代码质量，只评敢不敢用、需要什么补偿控制」的裁决结构最接近"
            "SourceLore 的研究目的；只借裁决结构，不借其锁模型层与跳过阶段的做法。"
            "U04-C26 判 REJECT：要求「即使无新发现也必须产报告」在跨仓库跨会话场景会产生大量无价值写入；"
            "本条改采「允许只登记不产报告」。"
            "U02-C15 判 REJECT：90%+/70-89%/50-69% 未经任何校准，属虚假精准度；U03-C27 判 REJECT：上游允许「项目明确偏好时用百分比」却未给校准方法——两者是同一虚假精准度的两个出口，本条一并拒绝，明令禁止未校准百分比。"
        ),
    },
    {
        "id": "SL-CAP-0039",
        "name": "内联引用约束与可追溯性（校验器执行而非提示词）",
        "description": (
            "研究产物中每一条实质性陈述必须内联引用到具体来源，引用形式统一为可解析的引用标识，"
            "指向 Evidence-Claims 的证据记录 ID。约束分三层：\n"
            "其一，陈述级：无引用的陈述只能是 inference 或 unknown，不得以肯定事实语气出现。\n"
            "其二，覆盖级：引用必须覆盖结论的关键要素（数字、版本、行为断言），"
            "不得只在段落末尾挂一个泛泛的来源链接。\n"
            "其三，可校验：引用标识必须能被独立校验器解析——解析失败（指向不存在的证据 ID、"
            "URL 已失效且无存档）即判引用无效，产物不得通过验收。\n"
            "关键立场：引用纪律不能只靠提示词里的祈使句，必须由独立的校验器执行；"
            "提示词只是让模型尽量做对，校验器才能判定是否做到。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["research_text", "evidence_ids[]"],
        "outputs": [
            "citation{statement_ref, evidence_id, span}",
            "citation_check{valid, reason}",
            "uncited_statements[]（应审计出的无引用断言）",
        ],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0025（产物自证出处）相邻但不同：0025 要求在产物头部声明"
            "生成者与快照，本条要求正文每条陈述挂具体证据 ID。与 SL-CAP-0022（引用三态校验）"
            "共享「校验器执行」的立场，对象不同：0022 校验代码引用，本条校验研究陈述引用"
        ),
        "unresolved": [
            "引用的最小粒度（句 / 子句 / 数值）与 span 表示待 F2",
            "「关键要素」的机械判定规则（哪些数字与断言必须有引用）待 F1-C",
            "校验器归属：本条定义约束，具体实现落 Renderer 的产物校验还是独立 linter，待 F1-C",
        ],
        "refs": [("UPSTREAM-02", "C16", "ADAPT")],
        "notes": (
            "U02-C16 判 ADAPT：引用纪律正确、好/坏示例教学可借，但整条只是祈使句、无任何机械校验手段——"
            "上游自己写着「必须内联引用」，却没有任何机制能判定产物是否真的引用了。"
            "本条把校验从提示词搬到校验器，并明确三层约束中最可判定的一层（引用标识可解析）"
            "作为验收硬门槛。这同时回应了用户第 5 节第 4 项：内联引用的约束由本模块定义，"
            "执行校验的归属留 unresolved 交 F1-C，但「必须有校验器」这一点不可协商。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-04", "C24"): (
        "Evidence-Claims",
        "「无法复现的外部观察标记」正是 EC 的 SL-CAP-0020 已定义的 reproducible 三态；"
        "本批不重复建条目，身份交 EC 归属",
    ),
    ("UPSTREAM-05", "C24"): (
        "Evidence-Claims",
        "与 U04-C24 同名同义（不可复现外部观察的字段缺失），同属 EC 的 SL-CAP-0020 reproducible 语义",
    ),
    ("UPSTREAM-02", "C17"): (
        "Renderer",
        "Mermaid 图表硬要求属呈现决策；Research 只决定结论内容，图表是否生成由 Renderer 按数据触发",
    ),
}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-02", "C10"): ("SL-CAP-0035", "unreviewed_adopted"),
    ("UPSTREAM-02", "C11"): ("SL-CAP-0036", "cross_module_redirections"),
    ("UPSTREAM-02", "C12"): ("SL-CAP-0037", "unreviewed_adopted"),
    ("UPSTREAM-02", "C13"): ("SL-CAP-0038", "unreviewed_adopted"),
    ("UPSTREAM-02", "C14"): ("SL-CAP-0037", "unreviewed_adopted"),
    ("UPSTREAM-02", "C15"): ("SL-CAP-0038", "unreviewed_adopted"),
    ("UPSTREAM-02", "C16"): ("SL-CAP-0039", "unreviewed_adopted"),
    ("UPSTREAM-03", "C27"): ("SL-CAP-0038", "unreviewed_adopted"),
    ("UPSTREAM-04", "C26"): ("SL-CAP-0038", "unreviewed_adopted"),
    ("UPSTREAM-06", "C23"): ("SL-CAP-0038", "unreviewed_adopted"),
}
