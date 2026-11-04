#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-C3：剩余 10 项原始能力终裁（纯数据）。

集合：U03-C23/C24/C25/C26、U04-C05/C06/C13/C21/C27、U06-C21。
不重复裁决 U05-C27/C28。

方向：
  ADOPT_EXISTING     承接已有 canonical（可带 amendment）
  REJECT_WITH_REASON 明确拒绝，**保持 UNREVIEWED**（三态无法表达拒绝），等 F1-C-D 迁移
"""

BATCH = "F1-C-C3"

DECISIONS = [
    # ══ UPSTREAM-03 四条方法论约束（不批量填同一理由）══
    {
        "identity": ["UPSTREAM-03", "C23"],
        "capability": "五档证据优先级",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0037",
        "final_owner": "Research",
        "verdict": "REJECT",
        "split_answers": {
            "what_five_levels_for": (
                "上游用它给**研究资料排序**（哪个来源先看、更可信）。where 是 §12.2 L1142–L1154，"
                "属研究取数方法，不属 Claim 验证。"
            ),
            "three_things_distinguished": (
                "① 研究资料选择顺序——本条涉这个；"
                "② 来源可靠性判断——本条也涉，但只能做到「标类型」；"
                "③ Claim 的实际证据支持关系——**不属本条**，归 EC 的 SL-CAP-0028。"
            ),
            "can_priority_replace_ec": (
                "**不能。** 来源优先级不能替代验证规则。SL-CAP-0037 已有硬规则一"
                "「来源类型不构成真伪排序」——不因为来自 GitHub API 就认定内容为真。"
            ),
            "mechanical_truth_ranking": (
                "**是。** 审计 why 已指出「五档无权重不构成全序；L1152–L1153 又允许源码处任意层级，"
                "唯一排序机制自我消解（D10）」。它想做的正是机械真实性排序。"
            ),
        },
        "reason": (
            "**拒绝的是「五档机械排序」这个机制，不是拒绝「给来源标类型」。**"
            "该机制有致命缺陷：五档无权重不构成全序，且同时允许「源码处任意层级」，排序机制自我消解。"
            "SourceLore 已有 `source_type` 四值（SL-CAP-0037）与确定性事实，再叠一套优先级会产生"
            "两套互不兼容的证据体系。"
            "**保留的合理部分是「资料收集与标注原则」**——已由 SL-CAP-0037 承载（标类型、记采集时刻、"
            "记覆盖状态），本批补一条：优先级不得用于判定真伪。"
        ),
        "amendment": {
            "target": "SL-CAP-0037",
            "append_note": (
                "补充反例约束（F1-C-C3 由 U03-C23 引入）：**明确拒绝「多档证据优先级排序」机制**。"
                "理由：五档无权重不构成全序、且允许任意层级，排序自我消解（上游审计 D10）；"
                "叠加会让 SourceLore 出现两套互不兼容的证据体系。"
                "硬规则：来源优先级**只能**用于「先看哪个资料」的取数次序，"
                "**不得**用于判定 claim 真伪、不得作为 report_tier 的输入——后者归 SL-CAP-0028。"
            ),
        },
        "license_note": "CC-BY-4.0 / copy_permitted=true（只作反例引用，未复制其五档定义）",
        "interfaces": ["SL-CAP-0028（真伪裁决，与本条严格分离）"],
        "unresolved": ["取数次序是否需显式记录待 F2"],
    },
    {
        "identity": ["UPSTREAM-03", "C24"],
        "capability": "D2 图规范（强制 D2）",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0057",
        "final_owner": "Renderer",
        "verdict": "REJECT",
        "split_answers": {
            "d2_requirements": (
                "要求所有架构图用 D2（Declarative Diagramming）语法产出，§11.1–§11.6 L1044–L1113。"
                "但 L1046 强制 D2 却**无工具链、无语法校验**。"
            ),
            "scope": "上游所有架构文档；无「不适用」出口。",
            "covered_by_0057": (
                "**部分覆盖且更严格。** SL-CAP-0057 已定「图表是可选手段、不是完成门禁」、"
                "「无法可靠提取关系时不生成图表」、「图表格式属实现选择，由渲染目标决定，不在本能力内锁定」。"
                "D2 强制恰恰违反这三条中的后两条。"
            ),
            "global_dependency": "**不引入。** 不因上游强制 D2 就把 D2 变成 SourceLore 全局依赖。",
        },
        "reason": (
            "**拒绝的是「强制单一图示语法 + 无校验」这个机制。**"
            "审计 why 写得很准：L1046 强制 D2 却无工具链、无语法校验，无法检测装饰性图表（§11.2）"
            "与一图一意（§11.6）（D12）。图形态应由渲染层决定，不应被锁定为 D2。"
            "SL-CAP-0057 已覆盖其合理部分（可选图表 + 可追溯 + 格式中立），本条无需新增能力，"
            "只需把「拒绝锁定具体语法」写成显式反例。"
        ),
        "amendment": {
            "target": "SL-CAP-0057",
            "append_note": (
                "补充反例约束（F1-C-C3 由 U03-C24 引入）：**明确拒绝「强制单一图示语法」**"
                "（上游强制 D2 却无工具链、无语法校验，且无「不适用」出口）。"
                "硬规则：任何具体图示语法（D2 / Mermaid / PlantUML / SVG）都只是**实现选择**，"
                "不得写入 canonical 作为必备产出，也不得因「没用某语法」判报告不完整。"
                "**不得为了使用某语法而编造数据关系**——与 0057 第二、三条硬规则同源。"
            ),
        },
        "license_note": "CC-BY-4.0 / copy_permitted=true（只作反例引用，未复制其 D2 语法与模板）",
        "interfaces": ["SL-CAP-0055（视图契约，图表属其可选形态）"],
        "unresolved": ["F2 若选型某语法，是否需在 Renderer 的 slot 中声明待议"],
    },
    {
        "identity": ["UPSTREAM-03", "C25"],
        "capability": "「不得依赖 AST 解析器/图数据库/静态分析管线/索引系统」",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0001",
        "final_owner": "Facts",
        "verdict": "REJECT",
        "split_answers": {
            "what_actually_banned": (
                "上游 §2 L52–L53 明令**禁止其自身**依赖四类基础设施：AST 解析器、图数据库、"
                "静态分析管线、索引系统。这是**对上游自我设限**的声明，不是「这些技术有害」。"
            ),
            "over_generalization_risk": (
                "**有，且是本条最大的风险。** 不得把「上游不推荐」扩大成「SourceLore 永远不得采用」。"
                "SourceLore 的 Facts 模块**恰恰要**用 AST 解析器（确定性事实抽取），"
                "Storage **恰恰要**用可重建索引（SL-CAP-0065）。这两处若照搬该禁令会直接自毁。"
            ),
            "conflict_with_storage": (
                "**正面冲突。** SL-CAP-0065 已确立「C 层派生索引必须可重建」，"
                "SL-CAP-0065 硬规则四也说「不得在没有必要时引入向量/图数据库」——"
                "注意那是「没有必要时不引入」，不是「永远禁止」，且把判断权留给 F2。"
            ),
            "what_to_record": (
                "记录的是**拒绝「禁止使用确定性设施」这条方法论限制**，"
                "不是拒绝这些技术本身。"
            ),
        },
        "reason": (
            "该条与 SourceLore 确定性 CLI 架构**正面冲突**——审计 why 已明说"
            "「与 UPSTREAM-01 已确立的『确定性工具算事实、模型只解释含义』路线相反」、"
            "「本源最主要的架构不兼容点」。"
            "**拒绝的是这条自我设限的禁令，不是这四类技术。**"
            "Facts 需要 AST（SL-CAP-0001 确定性事实抽取）、Storage 需要可重建索引（SL-CAP-0065）。"
            "技术选型权留给 F2，按真实需求、性能、复杂度与风险决定。"
        ),
        "amendment": {
            "target": "SL-CAP-0001",
            "append_note": (
                "补充技术选型立场（F1-C-C3 由 U03-C25 引入）：**明确拒绝「禁止使用 AST 解析器 / "
                "图数据库 / 静态分析管线 / 索引系统」这条方法论设限**。"
                "硬规则：确定性事实抽取（本能力）**可以且应当**使用 AST 等确定性工具；"
                "派生索引的可重建性归 SL-CAP-0065。"
                "技术选型不设永久禁令——由 F2 按真实需求、性能、复杂度与风险决定；"
                "「上游不推荐某技术」不构成 SourceLore 的禁用理由。"
            ),
        },
        "license_note": "CC-BY-4.0 / copy_permitted=true（只作反例引用，未复制其禁令原文）",
        "interfaces": ["SL-CAP-0065（索引需求，与本禁令直接冲突处）"],
        "unresolved": ["F2 是否最终引入图数据库待其自行按需求判断"],
    },
    {
        "identity": ["UPSTREAM-03", "C26"],
        "capability": "每个术语必须独立成页（含小仓库）",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0055",
        "final_owner": "Renderer",
        "verdict": "REJECT",
        "split_answers": {
            "renderer_nav_or_doc": (
                "**是呈现/导航决策**，属 Renderer 的视图契约（SL-CAP-0055 的导航索引一型），"
                "不是知识对象定义。"
            ),
            "forced_mechanism": (
                "**是强制机制**：§7.2 L534、L557 要求「每个术语独立成页，**含小仓库**」，"
                "无「不必」出口。"
            ),
            "existing_coverage": (
                "SL-CAP-0055 多类型视图共享同一事实源，导航索引是其一型；"
                "「术语表条目 + 按需升格为页」正是 0055 允许的布局差异。"
            ),
            "new_authoritative_object": (
                "**不得。** 术语页存在不等于新知识对象——术语只是既有知识的一种呈现单位，"
                "不得因它存在就制造新的权威对象。"
            ),
        },
        "reason": (
            "审计 why 判准：「与低 token 目标冲突：小仓库也会被迫产出大量单句页，"
            "而 §15.1 只有散文级去重无检测手段。应改为术语表条目 + 按需升格为页的两级策略」。"
            "**拒绝的是「无条件强制逐术语建页」**，采纳其合理替代形态（两级策略），"
            "由 SL-CAP-0055 的多类型视图承载——术语表属摘要/索引视图，单页属完整卡片视图。"
            "**不因术语页存在就制造新的权威知识对象**——术语仍是既有 Subject 的呈现单位。"
        ),
        "amendment": {
            "target": "SL-CAP-0055",
            "append_note": (
                "补充导航策略（F1-C-C3 由 U03-C26 引入）：**拒绝「每个术语强制独立成页」**"
                "（上游含小仓库也强制，与低 token 目标冲突）。"
                "采纳两级策略：默认以**术语表条目**呈现（摘要视图），"
                "当某术语满足「被多次引用 / 有独立证据链 / 人工要求升格」之一时，方可升格为独立页。"
                "硬规则：术语页只是既有 Subject 的**呈现单位**，"
                "**不得因建页而制造新的权威知识对象**——权威对象仍只由上游模块产生。"
            ),
        },
        "license_note": "CC-BY-4.0 / copy_permitted=true（只借「两级策略」取向，未复制其术语页模板）",
        "interfaces": ["SL-CAP-0040（Subject 身份，术语不是新 Subject）"],
        "unresolved": ["升格条件的具体阈值待 F2"],
    },

    # ══ UPSTREAM-04 五条 ══
    {
        "identity": ["UPSTREAM-04", "C05"],
        "capability": "按需加载的模式指引",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0068",
        "final_owner": "DSH-Adapter",
        "verdict": "REUSE",
        "split_answers": {
            "original_mechanism": (
                "L78–L86：参考文档（共 67 行）不常驻上下文，按问题类型只加载匹配的指引。"
                "L80 原话「Load only the guidance that matches the question」。"
            ),
            "not_deflt_lifecycle": (
                "**不归 Lifecycle。** 它不涉及任何知识失效语义，纯属「运行时该加载哪份说明」。"
                "原始 disposition=REUSE 不代表 owner 就是 Lifecycle。"
            ),
            "compare_with_capabilities": (
                "对照五模块：Facts（源事实，无关）、Research（研究阶段，无关）、"
                "Lifecycle（失效，无关）、Storage（持久化，无关）、**DSH-Adapter（Skill 加载，直接对应）**。"
            ),
            "which_owner": (
                "**DSH-Adapter。** SL-CAP-0068 的「入口薄、能力按需读」正是同一机制，"
                "且已在 F1-B 定为 V1_REQUIRED。"
            ),
        },
        "reason": (
            "该机制与 SL-CAP-0068「渐进加载」完全同构：都是「不把全部约束常驻上下文、按需加载」。"
            "本批价值在于**把它作为 0068 的上游来源正式登记**，并为「按问题类型匹配」补一条细则。"
            "不归 Lifecycle——原 disposition=REUSE 只说明可复用，与 owner 无关。"
        ),
        "amendment": {
            "target": "SL-CAP-0068",
            "append_note": (
                "补充匹配细则（F1-C-C3 由 U04-C05 引入）：按需加载的触发条件必须**按问题类型匹配**，"
                "不得按「总是加载全部」或「随机选一份」。"
                "硬规则：指引文件的总行数可以增长，但**单次上下文只装载本次任务匹配的那几份**。"
            ),
        },
        "license_note": "MIT / copy_permitted=true（形态可直接复用）",
        "interfaces": ["SL-CAP-0070（上下文预算）"],
        "unresolved": ["问题类型到指引文件的映射表待 F2"],
    },
    {
        "identity": ["UPSTREAM-04", "C06"],
        "capability": "不存密钥/凭据/个人数据（全模式适用）",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0053",
        "final_owner": "Security",
        "verdict": "REUSE",
        "split_answers": {
            "original_mechanism": (
                "L72 双重强调「every retained artifact, in every investigation mode」；"
                "references/external-probe.md L10、L13。审计 why 称其为「四源中最完整的秘密处理规则」。"
            ),
            "not_deflt_lifecycle": (
                "**不归 Lifecycle。** 它不涉失效，是**持久化时的秘密约束**——"
                "对象是「落盘的每个产物」。"
            ),
            "compare_with_capabilities": (
                "Facts/Research/Product/Lifecycle 均不涉秘密处理；Storage 负责落盘但不定义分级；"
                "**Security 的 SL-CAP-0053 已是分级+脱敏+门禁**。"
            ),
            "which_owner": (
                "**Security。** 0053 已有「敏感信息分级、脱敏与发布门禁」与硬规则四「密钥打码规则必须覆盖所有产物形态」；"
                "本条补的是「**全模式适用**」这一覆盖面声明。"
            ),
        },
        "reason": (
            "上游的价值在于覆盖面措辞：不是「某些模式下不存」，而是「**每个保留产物、每种模式**」都不存。"
            "SL-CAP-0053 已覆盖分级与打码，但未明确「无模式例外」这一条。本批把它补成硬规则。"
            "不归 Lifecycle——落盘秘密约束与知识新鲜度无关。"
        ),
        "amendment": {
            "target": "SL-CAP-0053",
            "append_note": (
                "补充覆盖面硬规则（F1-C-C3 由 U04-C06 引入）：密钥、凭据、个人数据**在任何模式下、"
                "任何保留产物中都不得存储**——不存在「宽松模式」或「调试模式」的例外。"
                "该约束覆盖产物全形态（报告、中间件、缓存、日志、索引）。"
            ),
        },
        "license_note": "MIT / copy_permitted=true",
        "interfaces": ["SL-CAP-0062（四层资产，约束覆盖各层）"],
        "unresolved": ["个人数据的判定边界待 F2"],
    },
    {
        "identity": ["UPSTREAM-04", "C13"],
        "capability": "报告粒度禁令",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0040",
        "final_owner": "Lifecycle",
        "verdict": "ADAPT",
        "split_answers": {
            "original_mechanism": (
                "L67「不要为每次搜索或次要子问题建报告」；L66「不强加固定段落」。"
                "审计 why：方向对但「没有可判定的粒度标准，须补 subject_key 规范化规则与最小内容门槛」。"
            ),
            "not_deflt_lifecycle": (
                "**归 Lifecycle。** 其核心是「**什么构成一个独立的知识单元**」——"
                "这正是 SL-CAP-0040 的 Subject 身份与复用判定。"
                "不是 Renderer（不是排版）、不是 Research（不是研究范围）。"
            ),
            "compare_with_capabilities": (
                "0040 已有 subject_key 规范化 + claim_scope 重叠度；缺的是「**最小内容门槛**」"
                "与其与「报告粒度」的连接。"
            ),
            "which_owner": "**Lifecycle（SL-CAP-0040）。**",
        },
        "reason": (
            "上游禁止「为每次搜索或次要子问题建报告」，其实质是**防止知识单元碎片化**——"
            "属 Subject 身份与复用判定，归 SL-CAP-0040。"
            "审计指出它「没有可判定的粒度标准」，本批补两条可判定门槛："
            "一是 subject_key 必须经规范化（已由 0040 有），二是最小内容门槛（本批新增）。"
        ),
        "amendment": {
            "target": "SL-CAP-0040",
            "append_note": (
                "补充粒度门槛（F1-C-C3 由 U04-C13 引入）：**不得为每次搜索或次要子问题单建知识单元**。"
                "两条可判定门槛：\n"
                "K-1 subject_key 必须经规范化（同一实体不得产生多个键）；\n"
                "K-2 最小内容门槛——一个独立知识单元至少须有「可独立陈述的一句话结论 + 至少一条证据引用」；"
                "不满足者并入既有单元或进待定出口，**不得单建**。\n"
                "本条只定「什么算一个单元」，不规定报告的章节与排版（归 Renderer）。"
            ),
        },
        "license_note": "MIT / copy_permitted=true",
        "interfaces": ["SL-CAP-0055（呈现层，不涉粒度）"],
        "unresolved": ["最小内容门槛的具体字数/字段数待 F2"],
    },
    {
        "identity": ["UPSTREAM-04", "C21"],
        "capability": "冲突处理（两个报告判断不同）",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0038",
        "final_owner": "Research",
        "verdict": "REIMPLEMENT",
        "split_answers": {
            "original_object": (
                "**两份研究报告之间的解释不一致。** where 写「全文缺失」、why 写"
                "「SKILL.md 通篇未提如何处理互斥结论（D5）」——即上游根本没定义，"
                "而该上游的语境是「每次调查产出一份报告」，故其缺口是**报告与报告之间**的判断冲突。"
            ),
            "four_possibilities": (
                "① 两份研究报告之间的解释不一致——**是本条对象**；"
                "② 两次研究的时间版本差异——部分涉（属 Lifecycle 0042 的失效）；"
                "③ 证据来源相互矛盾——涉但不由本条裁决（转 EC）；"
                "④ 模型推断结果不一致——涉但转 EC。"
            ),
            "vs_u05_c21": (
                "**严格区分**：U05-C21 的对象是**两条 Claim 的证据互相矛盾**（已归 EC/SL-CAP-0028 的 conflict 旁支）；"
                "U04-C21 的对象是**两份研究的解释不一致**——这是研究层的「同一事实、两种读法」，"
                "可能两者都成立（视角不同），也可能是其一错了。**不能先验地当 claim 冲突处理。**"
            ),
            "which_owner": (
                "**Research。** SL-CAP-0038 已有硬规则三「多来源综合得出的推断若与已有 claim 冲突，"
                "不得自行裁决，必须产出 handoff_item 移交 EC」——本批补的是**报告间**那一层。"
            ),
        },
        "reason": (
            "**这是本批最易判错的一项。** 同名「冲突处理」但对象完全不同："
            "U05-C21 是 Claim 级证据矛盾（已归 EC），U04-C21 是报告级解释分歧。"
            "报告间的分歧有两种性质：一是**视角差异**（两者都成立，应并列呈现并标注适用条件），"
            "二是**事实冲突**（须交 EC 裁决）。Research 的职责是**先分辨这两类**，不是自己当裁判。"
            "故归 SL-CAP-0038（研究质量状态与结论边界），补 report_conflict 的登记与分流规则。"
            "**不为所有冲突建第二套统一状态机**——裁决仍只由 EC 的 0028 一处拥有。"
        ),
        "amendment": {
            "target": "SL-CAP-0038",
            "append_note": (
                "补充报告间冲突处理（F1-C-C3 由 U04-C21 引入）：两份研究对同一事实的解释不一致时，"
                "**必须先分辨两类**，不得直接当 claim 冲突：\n"
                "R-1 **视角差异**（如「架构好」vs「维护差」分别从不同维度评价，两者都成立）→ "
                "并列呈现，各自标注适用条件与评价维度，**不判谁错**；\n"
                "R-2 **事实冲突**（对同一可验证断言给出互斥结论）→ 产出 handoff_item 移交 EC 的 SL-CAP-0028，"
                "**Research 不自行裁决**。\n"
                "硬规则：本条只负责**分辨与分流**，不拥有任何裁决权；"
                "**不得为报告冲突另建第二套状态机**——结论状态只有 SL-CAP-0028 一处。"
                "与 U05-C21 的边界：U05-C21 管 Claim 间证据矛盾，本条管报告间解释分歧，两者不得合并。"
            ),
        },
        "license_note": "MIT / copy_permitted=true（上游无实现，本条为自建分流规则）",
        "interfaces": ["SL-CAP-0028（唯一裁决权）", "SL-CAP-0042（版本失效，另一类时间差异）"],
        "unresolved": ["视角差异的判定是否需人工确认待 F2"],
    },
    {
        "identity": ["UPSTREAM-04", "C27"],
        "capability": "HTML/excalidraw 等具体产物格式",
        "direction": "REJECT_WITH_REASON",
        "target_canonical": None,
        "final_owner": None,
        "verdict": "REJECT",
        "split_answers": {
            "specific_reject": (
                "上游 spec 用 HTML（`spec.html`）、架构图用 excalidraw。"
                "审计 why：「SourceLore 用 Markdown + schema，形态不兼容，无复用价值」。"
            ),
            "rejected_behavior": (
                "**拒绝的是「以 HTML / excalidraw 文件作为权威产物格式」**，"
                "不是拒绝「人类可读的富媒体呈现」。"
            ),
            "alternative": (
                "SourceLore 用 **Markdown + schema（结构化契约）**；"
                "富媒体呈现若需要，属 Renderer 的 D 层实现选择（可生成派生 HTML/图），"
                "但**不得成为权威产物的存储格式**（权威层归 Storage 的 A/B 层，见 SL-CAP-0062）。"
            ),
            "counterexample_use": (
                "**可以作反面设计依据**：它说明「产物格式绑死具体工具」会导致形态不兼容。"
                "已可作为 SL-CAP-0062 的反例引用。"
            ),
        },
        "reason": (
            "原始 disposition 已是 **REJECT**，维持并给出终裁。"
            "拒绝的是「HTML/excalidraw 作为权威产物格式」这一具体机制；"
            "替代是 Markdown + schema。富媒体呈现允许作 Renderer 的**派生**产物，"
            "但不得成为权威层存储格式——这与 SL-CAP-0062 的 D 层「不得回写权威层」一致。"
        ),
        "terminal_disposition": "REJECTED_WITH_REASON",
        "license_note": "MIT / copy_permitted=true（机制不采纳，不复制其 HTML/excalidraw 文件）",
        "interfaces": ["SL-CAP-0062（权威格式归 A/B 层）", "SL-CAP-0055（富媒体属 D 层派生）"],
        "unresolved": ["无——已终裁"],
        "awaiting": "F1-C-D terminal_disposition 迁移",
    },

    # ══ UPSTREAM-06 ══
    {
        "identity": ["UPSTREAM-06", "C21"],
        "capability": "模型分层（Deep / Standard）",
        "direction": "REJECT_WITH_REASON",
        "target_canonical": None,
        "final_owner": None,
        "verdict": "REJECT",
        "split_answers": {
            "original_mechanism": (
                "仅 Phase 2 用 Deep 层、其余全部 Standard；只按家族别名（opus/sonnet/haiku）派发，"
                "不固定版本。SKILL.md L130–L330。"
            ),
            "binding_problem": (
                "审计 why：「整条机制绑死在 Claude 家族与 Agent 工具上，无法迁移到 DSH；"
                "且 Phase 4b/7 明确写『moved off the Deep tier』这类只对特定供应商有意义的说明」。"
            ),
            "reasonable_core": (
                "其合理内核是「**按任务复杂度与工具能力选路**」——这与 SL-CAP-0069 的"
                "「能力要求必须来自实际运行时验证、未知能力标 UNVERIFIED」同源。"
                "但**不得把某供应商或具体模型名写死为架构前提**。"
            ),
            "copy_boundary": (
                "**copy_permitted=false。** UPSTREAM-06 无明确复制许可，"
                "不得复制其提示词、规则原文、代码或模板。只作抽象思想来源。"
            ),
        },
        "reason": (
            "原始 disposition 已是 **REJECT**，维持。"
            "拒绝的是「固定模型分层 + 按供应商家族别名派发」这一机制——它绑死 Claude 家族与 Agent 工具，"
            "无法迁移；且含只对特定供应商有意义的说明。"
            "**合理内核已被 SL-CAP-0069/0070 覆盖**：按任务复杂度与工具能力选路对应 0069 的"
            "三类操作边界（确定性/模型辅助/需 EC 校验），预算与成本对应 0070。"
            "**UPSTREAM-06 无复制许可**，本条只作抽象设计背景，未复制任何原文。"
        ),
        "terminal_disposition": "REJECTED_WITH_REASON",
        "license_note": "**UPSTREAM-06 / copy_permitted=false —— 零复制，仅抽象思想**",
        "interfaces": ["SL-CAP-0069（模型适配与能力边界）", "SL-CAP-0070（预算成本）"],
        "unresolved": ["无——已终裁"],
        "awaiting": "F1-C-D terminal_disposition 迁移",
    },
]

# 本批终裁后仍保持 UNREVIEWED 的（等 F1-C-D 迁移）：U05-C27/C28（前批）+ 本批 3 项 REJECT
STILL_UNREVIEWED_AFTER = [
    "UPSTREAM-05::C27", "UPSTREAM-05::C28",
    "UPSTREAM-04::C27", "UPSTREAM-06::C21",
]
