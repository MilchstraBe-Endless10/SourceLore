#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Renderer 模块：canonical 定义与跨模块去向。

导出符号：
    MODULE                    "Renderer"
    FIRST_ID                  "SL-CAP-0055"
    CANON                     7 条 canonical（0055–0061）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的 2 个身份
    CONSUMED_THIS_BATCH       本批正式承接的 11 个身份（3 条 ROUTED + 8 条未审直采）

ID 规则：从 SL-CAP-0055 起连续分配，不重排 0001–0054。
"""

MODULE = "Renderer"
FIRST_ID = "SL-CAP-0055"

CANON = [
    {
        "id": "SL-CAP-0055",
        "name": "知识视图的统一呈现契约（多类型视图共享同一事实源）",
        "description": (
            "呈现层对外只暴露一种能力：把上游权威数据渲染成可阅读视图。视图类型至少四种，"
            "共享同一份事实来源，但布局各自独立：完整报告（跨 Subject 的综合）、"
            "摘要视图（一页概览）、单条 Subject 卡片（结构化知识资产）、导航索引（派生视图）。"
            "四类视图必须从同一份上游数据生成——同一事实在不同视图里不得出现不同数值。"
            "硬规则一：卡片不是 Claim 的第二份权威副本。卡片所有内容都从上游权威数据派生，"
            "不得在卡片里创造未经验证的新主张；发现需要新主张时应回到上游产出 claim 候选，"
            "而不是在渲染阶段顺手补一句。"
            "硬规则二：卡片可以被重新生成，但不得覆盖不可变的历史 Claim 或 Evidence。"
            "重生成产出的是新视图，不是历史改写。"
            "硬规则三：视图必须自行声明它展示了什么范围的权威数据（source_snapshot），"
            "使读者能判断「这张卡片依据的是哪个快照」。"
            "硬规则四：不得把 UPSTREAM-02 的九节结构规定为所有输出的统一模板。"
            "九节结构只作报告类视图的内容槽位来源之一；卡片与导航视图允许完全不同的布局。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["authoritative_bundle{claims[], evidence[], product_model, research_report, subject}",
                   "view_type: report|summary|card|index", "source_snapshot{commit_sha}"],
        "outputs": [
            "view{view_type, source_snapshot, content_slots[], layout_id, generated_at}",
            "content_slot{slot_id, populated_by, upstream_ref}",
            "view_regeneration_record{prev_view_id, reason}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Product", "Research", "Storage"],
        "overlaps": (
            "与 Research 的 SL-CAP-0038 分界：0038 定义「报告必须包含哪些内容项」，"
            "本条定义「这些项在不同视图里怎么组织」。内容槽位归 Research，布局归本条。"
            "与 Product 的 SL-CAP-0029 分界：0029 定义产品语义八要素，本条只决定八要素在卡片上怎么摆"
        ),
        "unresolved": [
            "四类视图的槽位清单与必填项待 F2；本批只要求「共享事实源 + 各自布局」这一结构",
            "九节结构作为报告类槽位来源是否保留全部九节，待 F1-C",
            "source_snapshot 引用 commit_sha 还是 Bundle manifest 哈希，取决于 F2 的 Bundle 契约",
        ],
        "refs": [("UPSTREAM-01", "C10", "REIMPLEMENT")],
        "notes": (
            "合并依据：U01-C10 提供「report schema + markdown render」的呈现骨架，"
            "U02-C13 提供九节报告的内容槽位——两者一个是渲染机制、一个是内容划分，"
            "合起来才构成「同一事实源、多类型布局」的统一契约。"
            "U02-C13（九节报告结构）已在 Research 批次由 SL-CAP-0038 正式承接，"
            "同一原始身份只能映射一次，故本条的 refs 里只有 U01-C10；"
            "对九节结构的引用是跨模块依赖（「报告类视图的槽位来源之一」），不是身份复用。"
            "U01-C10 判 REIMPLEMENT 而非审计建议的 REUSE：上游的 13 顶层键结构确实合理，"
            "但它把 schema 与 render 焊在一个模块里，且 evidence 字段太窄（审计 D5 已记）。"
            "本条只取「结构化 schema 驱动渲染」的取向，四类视图的分层结构是自建。"
            "U02-C13 的正确归属是 Research 的 SL-CAP-0038（内容槽位），"
            "本条只作为跨模块依赖引用其槽位定义，不重复占用原始身份。"
        ),
    },
    {
        "id": "SL-CAP-0056",
        "name": "受众差异化信息密度与呈现风格",
        "description": (
            "同一份事实按受众调整信息密度，而不改变事实本身。至少三档受众画像："
            "决策者（要结论与影响面，不要实现细节）、维护者（要关键路径与风险，不要完整调用链）、"
            "审计者（要完整证据链与限制说明）。"
            "信息密度由三个可调参数表达：展开深度（摘要 / 标准 / 完整）、"
            "证据可见度（只引 ID / 引 ID 与摘要 / 内联证据片段）、术语密度（白话 / 混合 / 专业）。"
            "硬规则一：密度调整只允许裁剪与改写，不允许改变结论的确认等级。"
            "降密度不得把 insufficient 写成「未发现问题」，也不得省略限制说明。"
            "硬规则二：无论如何裁剪，唯一不可省略的四项是：结论、确认等级、覆盖缺口、生成快照。"
            "这四项构成视图的最小完整性。"
            "硬规则三：受众画像只是调整参数，不是推断读者身份的依据；"
            "不得因为某受众「不需要细节」就删掉否定性证据。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["audience_profile{role}", "density_params{depth, evidence_visibility, jargon}"],
        "outputs": [
            "render_profile{audience, depth, evidence_visibility, jargon}",
            "omitted_items[]（被裁剪项及其类别，用于审计）",
            "minimal_completeness_check{passed, missing[]}",
        ],
        "depends_on_modules": ["Product"],
        "overlaps": (
            "与 Product 的 SL-CAP-0034（字段置信度）分界：0034 判「这条字段有多可信」，"
            "本条判「这条字段该以多少细节呈现」。两者是证据强度与呈现粒度的不同轴"
        ),
        "unresolved": [
            "三档受众画像是否足够（是否需要面向终端用户的第四档），待 F1-C",
            "omitted_items 是否需要在产物里显式列出，V1 取必须列出",
            "术语密度的判定（哪些词算专业术语）待 F2",
        ],
        "refs": [("UPSTREAM-03", "C15", "ADAPT")],
        "notes": (
            "U03-C15 判 ADAPT：L995 的受众清单可直接用于卡片层与渲染层的信息密度决策，"
            "其余风格条款（句式偏好、语气建议）价值不大且不可判定，本批只取受众清单这一条实质内容，"
            "改造成三档画像 + 三个可调参数。"
            "该身份来自 Product 批次的既有分流（Product 判定「受众清单用于信息密度决策、属渲染层」），"
            "本批建 canonical 正式承接。"
            "硬规则二的四项最小完整性是本条自建的约束——上游只说「按受众调整」，"
            "没说「调整时哪些不能删」，而那正是密度调整最容易出问题的地方。"
        ),
    },
    {
        "id": "SL-CAP-0057",
        "name": "可选图表呈现与数据追溯（拒绝强制出图）",
        "description": (
            "图表是可选的呈现手段，不是完成分析的门禁。触发条件必须由数据决定："
            "存在明确的关系结构（实体间的归属/引用/调用/数据流）且该结构在文本里表达笨拙时，才生成图表。"
            "三条硬规则："
            "其一，无法可靠提取关系时不生成图表——不得为凑齐「有架构图」而编造节点或边。"
            "其二，图表内容必须可追溯：每个节点与每条边都要指向上游数据项（entity / flow_evidence / "
            "relation），无上游来源的视觉元素一律不得出现。"
            "其三，图表不是完成判据。没有生成图表的报告与生成了图表、报告在完成标准上等价；"
            "不得以「缺图」判报告不完整。"
            "明确拒绝继承的是上游的强制图表机制（固定 4 节点 flowchart 必须填写、"
            "与实际架构无关也照画），而不是拒绝图表功能本身。"
            "图表格式（Mermaid / SVG / 其他）属实现选择，由渲染目标决定，不在本能力内锁定。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["relation_structure{entities[], relations[], flows[]}", "render_target"],
        "outputs": [
            "diagram_decision{generate: bool, trigger_basis, relation_source}",
            "diagram_spec{nodes[]{id, upstream_ref}, edges[]{from, to, kind, upstream_ref}}",
            "diagram_omission_reason{why_not_generated}",
        ],
        "depends_on_modules": ["Product", "Evidence-Claims"],
        "overlaps": (
            "与 Product 的 SL-CAP-0031（业务实体与关系）是数据来源关系："
            "图表节点只能来自该能力产出的实体与关系，不在渲染阶段新增。"
            "与 EC 的 SL-CAP-0021（四节点数据流）是同一数据来源的另一形态"
        ),
        "unresolved": [
            "「结构在文本里表达笨拙」的判定标准无法机械化，待 F1-C；V1 取「有明确结构即允许生成」",
            "图表格式中立性如何落到具体渲染目标，待 F2",
            "生成图表是否需要单独的发布审查（与 SL-CAP-0061 的门禁关系）待 F1-C",
        ],
        "refs": [("UPSTREAM-02", "C17", "REIMPLEMENT")],
        "notes": (
            "U02-C17 在原始索引中判 REJECT，理由是「为出图而出图：模板固定 4 节点 flowchart，"
            "与真实架构无关时也必须填，是形式驱动虚构的直接来源」。"
            "本批保留这一 REJECT 证据，并把它的处置改为 REIMPLEMENT——"
            "因为要拒绝的是**强制出图机制**，不是图表功能本身。"
            "把二者混为一谈会导致 SourceLore 连「有真实关系时画个图」都不敢做，那是另一个极端。"
            "本条把触发条件交给数据、把内容追溯钉到上游引用、把完成判据与图表解耦，"
            "三条硬规则正好对应上游的三处失误。"
            "该身份来自 Research 批次的既有分流（Research 判定「Mermaid 硬要求属呈现决策」）。"
        ),
    },
    {
        "id": "SL-CAP-0058",
        "name": "生成产物与人工维护内容物理隔离（旁车机制）",
        "description": (
            "自动生成内容与人工维护内容必须物理隔离，隔离靠目录与命名强制，不靠人记得别覆盖。"
            "三层约束："
            "L-1 目录级隔离：自动生成产物一律写入独立命名空间（候选约定 _generated/），"
            "写侧代码不得提供指向人工维护目录的分支——这是结构约束，不是流程提醒。"
            "L-2 标识级隔离：每个生成产物头部必须带 auto_generated 标识，"
            "含生成器名与版本、run_id、source_snapshot、生成时间四项。"
            "L-3 覆盖边界：重生成只允许覆盖同一命名空间内的旧生成产物；"
            "人工维护文档永不被覆盖，即使内容看起来过时——过时由人工或 Lifecycle 判，不由渲染器判。"
            "硬规则一：局部生成失败时，保留该产物的上一份有效版本，不得用半成品替换。"
            "同时必须在生成清单里标注该项为 failed，使「有清单但某页是旧的」可被察觉。"
            "硬规则二：生成内容与权威数据版本绑定——每个产物记录其 source_snapshot，"
            "版本不一致的产物不得与新版产物混排在同一导航里而不加标注。"
            "硬规则三：具体原子写入与文件锁归 Storage；本条只定义「哪些文件可被覆盖」的语义边界。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["generated_artifact{path, content}", "authoritative_snapshot", "prev_artifact?"],
        "outputs": [
            "artifact_namespace{root, pattern, writable_scope}",
            "artifact_header{auto_generated, generator, run_id, source_snapshot, generated_at}",
            "render_failure_record{artifact_id, kept_prev_version, failed_reason}",
        ],
        "depends_on_modules": ["Storage", "Evidence-Claims"],
        "overlaps": (
            "与 EC 的 SL-CAP-0025（产物自证出处）相邻但不同：0025 要求产物头部声明生成者与快照，"
            "本条要求「写入位置被结构强制隔离」——前者是标识，后者是空间边界。两者互补不重复"
        ),
        "unresolved": [
            "正式目录契约（是否确为 _generated/）待 F2；本批只要求「独立命名空间 + 写侧无分支」",
            "哪些文档必须人工审阅的清单待 F1-C",
            "人工维护文档的局部更新是否允许自动插入片段（而非整篇覆盖）待 F1-C",
        ],
        "refs": [
            ("UPSTREAM-05", "C03", "REUSE"),
            ("UPSTREAM-04", "C14", "ADAPT"),
        ],
        "notes": (
            "合并依据：U05-C03 给「旁车产物与叙事页分离」的空间约束，U04-C14 给「产物命名与链接规范」"
            "——前者决定写在哪，后者决定怎么写名、怎么被引用，合起来才是可执行的隔离。"
            "U05-C03 在原始索引判 REUSE，理由写得准：「唯一在两个上游里真正被代码强制的边界」。"
            "但本批判 REIMPLEMENT：上游那套 generated_output_path() 是 Python 函数级强制，"
            "SourceLore 要的是同样的语义在不同实现里重做，且必须补上「重生成时的覆盖边界」与"
            "「局部失败保留上一版」两条上游没有的规则。"
            "U04-C14 判 ADAPT：稳定描述性命名 + 每个产物必须从 report 链接并说明证明什么，两条都实用；"
            "须加机检规则（文件存在性、链接可达）。"
        ),
    },
    {
        "id": "SL-CAP-0059",
        "name": "呈现层静态校验（结构一致性、链接完整性与措辞规则）",
        "description": (
            "生成的视图在交付前必须过静态校验，校验必须是可执行的规则集，不是散文提醒。"
            "三类规则："
            "V-1 结构一致性：每个视图必须声明并满足其类型要求的槽位集合（缺槽即失败，"
            "不得用占位空段填充）；导航视图的每条链接都必须指向真实存在的产物（文件存在性 + 链接可达）。"
            "V-2 措辞规则：陈述句的措辞必须与其确认等级匹配——insufficient 不得写成肯定句，"
            "inference 不得写成事实陈述，conflict 必须同时呈现双方。措辞规则以文本扫描器实现，"
            "每条带 rule_id 与检测模式。"
            "V-3 反模式检测：为二十条反模式清单提供可判定检测条件，"
            "每条反模式映射为至少一条 rule_id；不可判定的反模式不得进入校验集（宁可少检，不检伪）。"
            "硬规则一：校验规则必须有 rule_id，且失败必须有明确处置（阻断 / 降级 / 仅告警），"
            "不得只记录「发现问题」而无动作。"
            "硬规则二：校验未跑或部分未跑时，必须在产物里标注 coverage_gap，禁止声称「已通过全部校验」。"
            "硬规则三：五十五问类自检清单只作规则来源，不被渲染进产物——"
            "自检是内部质量门，不是交付内容。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["rendered_view", "view_type_slot_spec", "artifact_registry{paths[]}"],
        "outputs": [
            "rule_definition{rule_id, category: structure|wording|antipattern, condition, failure_action}",
            "rule_result{rule_id, status: passed|failed|skipped, detail}",
            "validation_gap{rule_id, reason}",
        ],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": (
            "与 EC 的 SL-CAP-0022（引用三态校验）分界：0022 校验「引用能不能定位到快照中的节点」，"
            "本条校验「产物里的链接能不能指向存在的产物」——对象不同：一个是源码位置，一个是产物文件。"
            "与 Security 的 SL-CAP-0047（四项独立检查）无关：那条判安全发现成立与否，本条判呈现是否完整"
        ),
        "unresolved": [
            "三类规则的完整条目集待 F2",
            "「不可判定的反模式」是否允许部分机械化，待 F1-C",
            "校验失败时的默认处置（阻断 vs 降级）按视图类型区分，待 F2",
        ],
        "refs": [
            ("UPSTREAM-03", "C18", "REIMPLEMENT"),
            ("UPSTREAM-03", "C19", "REIMPLEMENT"),
            ("UPSTREAM-03", "C20", "REIMPLEMENT"),
            ("UPSTREAM-03", "C21", "REIMPLEMENT"),
            ("UPSTREAM-03", "C22", "REIMPLEMENT"),
            ("UPSTREAM-03", "C12", "ADAPT"),
        ],
        "notes": (
            "合并依据：C18（十八条结构一致性检查）、C19（wiki link 校验）、C20（五条一致性规则）、"
            "C21（五十五问自检）、C22（主张措辞规则）、C12（二十条反模式清单）六项讲的是同一件事："
            "「产物交付前怎么机械检查」。它们分别对应结构、链接、规则仲裁、自检、措辞、反模式，"
            "拆成六条 canonical 会得到六套各自为政的校验器，而实际需要的是一个带 rule_id 的规则集。"
            "C18 判 REIMPLEMENT：上游 L712 自称必需质量门却无 schema、无 linter、无失败处置（审计 D6），"
            "检查项内容有价值，须自行实现为带 rule id 的 linter。"
            "C19 判 REIMPLEMENT：真可机器检查，但上游无页面清单可对照、无校验算法，须先有 registry 才能实现。"
            "C20 判 REIMPLEMENT：§15.1/§15.2 部分可机检，§15.4 因 evidence strength 未定义不可执行（D9），"
            "§15.5 三种处置无仲裁顺序；须重写为可判定规则集。"
            "C21 判 REIMPLEMENT：问题质量不低但无通过标准、无计分、无阈值、无产物（D16）；"
            "改造为结构化 gate，且明确「自检不渲染进产物」。"
            "C22 判 REIMPLEMENT：全文最强的可机检措辞规则，但未附任何检测器；"
            "可实现为文本扫描器，成本低收益直接。"
            "C12 判 ADAPT：条目具体，可作 linter 检查项来源；须为每条补可判定检测条件，否则只是警告语。"
        ),
    },
    {
        "id": "SL-CAP-0060",
        "name": "确认等级与限制的忠实呈现（禁止视觉掩盖）",
        "description": (
            "Renderer 的核心纪律是「忠实呈现上游判断，不自行改写」："
            "R-1 有引用不等于引用支持结论。引用完整性由本条校验（链接能不能点、ID 存不存在），"
            "但「这条引用是否支持该结论」归 Evidence-Claims，Renderer 不得代为判断，"
            "也不得因为「有引用」就把措辞写得更确定。"
            "R-2 状态必须显式呈现：claim 处于 insufficient / conflict / 等待重新验证 / "
            "detection_incomplete 时，视图必须在正文可见位置呈现该状态，不得只在元数据里写。"
            "R-3 禁止把 facts_only 渲染成完整研究报告——facts_only 的视图必须自述「只有事实、"
            "没有解释性结论」，且不得填充解释性段落。"
            "R-4 禁止使用视觉样式掩盖数据缺失：不得用空白、省略号、「暂缺」之外的任何装饰替代"
            "明确的不完整标注；不得用颜色/图标暗示比数据更强的确定性。"
            "R-5 禁止使用未经校准的百分比表达真实性。"
            "R-6 不允许 Renderer 私自提高任何结论的确认等级；"
            "上游给的等级是渲染输入，不是可优化项。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim{validation_status, report_tier}", "evidence_refs[]", "coverage_record"],
        "outputs": [
            "rendered_claim{text, displayed_tier, status_badge}",
            "fidelity_check{check_id: R_1..R_6, verdict}",
            "downgrade_violation{claim_id, upstream_tier, rendered_tier, reason}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Research"],
        "overlaps": (
            "与 EC 的 SL-CAP-0023（显式未知优于自信猜测）分界：0023 管「写这句话时的措辞层级」，"
            "本条管「渲染时有没有把这个层级忠实带出来」。0023 是产出侧，本条是呈现侧。"
            "与 Research 的 SL-CAP-0038 分界：0038 定义质量三态，本条定义三态怎么显示"
        ),
        "unresolved": [
            "status_badge 的视觉形式（文字 / 图标 / 颜色）待 F2；本批只要求「必须在正文可见位置」",
            "「等待重新验证」状态的显示是否与 insufficient 区分，待 F1-C",
            "R-2 的「正文可见位置」如何机械判定，待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是独立设计。理由写清楚，否则读者会以为漏了引用。"
            "U02-C16（内联引用规则）已在 Research 批次由 SL-CAP-0039 正式承接，"
            "同一原始身份只能映射一次；本条与它的关系是「0039 定义引用约束、本条定义呈现忠实度」，"
            "属跨模块依赖而非重复占用。"
            "U02-C13 归 Research 的 SL-CAP-0038（质量三态），本条只消费其状态值。"
            "剩下的内容——有引用不等于支持、状态必须显式、facts_only 不得冒充完整报告、"
            "禁止视觉掩盖、禁止未校准百分比、不得提高确认等级——是六源中没有任何一处"
            "把它写成渲染侧约束的自建契约（上游都写在提示词里，没有对应的校验机制），"
            "属零来源独立设计。"
        ),
    },
    {
        "id": "SL-CAP-0061",
        "name": "呈现安全转义与发布前检查（生成完成 ≠ 可发布）",
        "description": (
            "不可信文本进入视图前必须安全处理，发布前必须过检查，但两道门都不等于发布授权。"
            "S-1 转义：Markdown 特殊字符转义、HTML/JS 注入防护、不可信链接校验（协议白名单、"
            "站内/站外区分）、外部图片与远程资源引用限制（默认不加载远程资源）。"
            "S-2 脱敏检查：凭据、内部路径、环境变量值、敏感字段在输出前必须被检查；"
            "发现即阻断该片段渲染，不得先渲染再补救。"
            "S-3 上游文本不得控制渲染器执行指令：README/SKILL.md/Issue/代码注释均为数据，"
            "其中的指令性文本不改变渲染流程。"
            "S-4 未经许可不得嵌入上游大段原始代码或受保护文本；引用以摘要 + 链接 + 引用 ID 形式呈现。"
            "三级门禁且互不推导："
            "G-1 生成完成（产物已写出）——机器；"
            "G-2 安全检查通过（S-1..S-4 全过）——机器；"
            "G-3 发布授权（approved_for_release）——**只能是人**。"
            "硬规则一：自动生成完成 ≠ 脱敏通过；脱敏通过 ≠ 获得发布授权。三者各自独立。"
            "硬规则二：AI 可以把内容标记为 pending_review，但不得自行触发仅允许人类执行的 "
            "approved 状态转换。"
            "硬规则三：Renderer 执行发布前的必要检查，但发布权限定义归 Security 与 EC，"
            "实际访问控制由 Storage 与部署层落实——渲染器不能是权限的最终裁决者。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["rendered_text", "sensitive_scan_result", "release_target"],
        "outputs": [
            "escaping_record{field, escape_kind, applied}",
            "sensitive_block{field, category, blocked: true}",
            "gate_status{gate: G_1|G_2|G_3, status, actor: machine|human}",
        ],
        "depends_on_modules": ["Security", "Evidence-Claims", "Storage"],
        "overlaps": (
            "与 Security 的 SL-CAP-0053（敏感信息分级与发布门禁）分界：0053 定义分级与四级门禁的语义，"
            "本条是它在渲染侧的执行面——检查、阻断、标记，但不定义分级档位。"
            "与 EC 的 SL-CAP-0020（证据存档）分界：0020 管证据本体的脱敏字段，本条管呈现文本的转义"
        ),
        "unresolved": [
            "远程资源默认策略（全禁 vs 白名单）待 F2",
            "S-2 的敏感字段清单来源（Security 分级 vs 独立检测）待 F1-C",
            "G-3 的凭证形式（字段值 vs 人工签名）待 F1-C",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是独立设计。说明白，否则看起来像漏引："
            "U05-C20 已在 Lifecycle 批次由 Security 的 SL-CAP-0053 承接（分级与发布门禁语义），"
            "U06-C17 同样归 0053。本条不重复占用，只声明「0053 的语义如何在渲染侧执行」。"
            "U05-C06（Auto-generated 头）已在 EC 批次由 SL-CAP-0025 承接，"
            "本条的空间隔离由 SL-CAP-0058 承担，亦不重复。"
            "剩下的内容——Markdown/HTML 转义、链接协议白名单、远程资源限制、"
            "上游文本不得控流程、三段门禁互不推导、AI 不得自批 approved——"
            "六源里没有任何一处把它写成渲染器契约（上游的安全关注点都在被分析仓库一侧，"
            "没有一个讨论「渲染器自己会不会被注入」），属零来源独立设计。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-04", "C16"): (
        "Lifecycle",
        "完成检查（三处 Completion Check）是「任务何时算完成」的判定，"
        "属 Lifecycle 的变更调度与调度完成语义，不属呈现层",
    ),
    ("UPSTREAM-05", "C10"): (
        "Lifecycle",
        "契约式 Postconditions（写入后校验）属变更动作的后置条件，归 Lifecycle 的增量调度与 Storage 的写入校验",
    ),
}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-01", "C10"): ("SL-CAP-0055", "cross_module_redirections"),
    ("UPSTREAM-02", "C17"): ("SL-CAP-0057", "cross_module_redirections"),
    ("UPSTREAM-03", "C15"): ("SL-CAP-0056", "cross_module_redirections"),
    ("UPSTREAM-03", "C12"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-03", "C18"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-03", "C19"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-03", "C20"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-03", "C21"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-03", "C22"): ("SL-CAP-0059", "unreviewed_adopted"),
    ("UPSTREAM-04", "C14"): ("SL-CAP-0058", "unreviewed_adopted"),
    ("UPSTREAM-05", "C03"): ("SL-CAP-0058", "unreviewed_adopted"),
}
