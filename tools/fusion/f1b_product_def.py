#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Product 模块：canonical 定义与跨模块去向。

导出符号（构建器与验证器只读这三样）：
    MODULE                    "Product"
    FIRST_ID                  "SL-CAP-0029"
    CANON                     6 条 canonical（0029–0034）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的 2 个身份
    CONSUMED_THIS_BATCH       本批正式承接的 9 个未审身份

ID 规则：从 SL-CAP-0029 起连续分配，不重排 0001–0028。
每条 refs 三元组：(upstream_id, original_capability_id, verdict)。
"""

MODULE = "Product"
FIRST_ID = "SL-CAP-0029"

# ── canonical 能力 ──────────────────────────────────────────────────────
CANON = [
    {
        "id": "SL-CAP-0029",
        "name": "产品语义模型八要素（每字段强制带声明层级与证据引用）",
        "description": (
            "把仓库事实组织成产品语义模型的八个固定要素：Frame（产品目标与边界）、"
            "Roles（用户角色）、Entities（业务实体）、Capabilities（功能能力）、"
            "Flows（主要业务流程）、Boundaries（外部集成边界）、Constraints（限制与前置条件）、"
            "Decisions-Risks-Unknowns（决策、风险与未知项）。"
            "八要素是结构而非内容清单：每一字段必须携带 claim_type 与 evidence_refs 两个必填项。"
            "claim_type 四值：fact（代码直接证实）、declaration（README 或文档中的产品声明）、"
            "inference（依据源码推导的产品解释）、unknown（证据不足）。"
            "evidence_refs 为空时 claim_type 只能是 inference 或 unknown，不得是 fact 或 declaration。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["repo_facts（Facts 交付的确定性事实）", "snapshot_manifest（Collector 钉定快照）",
                   "documentation_text（README / docs，可为空）"],
        "outputs": [
            "product_model{frame, roles[], entities[], capabilities[], flows[], "
            "boundaries[], constraints[], decisions_risks_unknowns[]}",
            "field_provenance{field_path → claim_type, evidence_refs[]}",
        ],
        "depends_on_modules": ["Facts", "Collector", "Evidence-Claims"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0023 是同一层级纪律在两个层的落点："
            "0023 管 claim 措辞不得越级，本条管产品字段的 claim_type 不得越过 evidence_refs。"
            "与 SL-CAP-0031 的实体建模是整体与局部关系"
        ),
        "unresolved": [
            "八要素的字段级 schema（类型、可选性、嵌套深度）属 F2，本批只定要素与 provenance 规则",
            "declaration 型 claim 是否允许在无 evidence_refs 时存在（即「文档里写着」本身算不算证据），待 F1-C",
            "Frame 要素的证据要求高于其余七项（产品目标常无源码可证），其降级规则待定",
        ],
        "refs": [("UPSTREAM-03", "C06", "ADAPT")],
        "notes": (
            "U03-C06 判 ADAPT：八要素划分合理完整，但上游只对 Roles、Flows、Boundaries 三处做了证据分级，"
            "其余五要素（Frame、Entities、Capabilities、Constraints、Decisions）没有任何证据要求，"
            "等于一半的模型可以凭想象填写。修正点是「每字段强制 claim_type + evidence_refs」，"
            "并补一条硬约束：无 evidence_refs 的字段不得标为 fact 或 declaration。"
            "这条约束不是形式主义——它正是防止「README 声称的功能被当成已实现功能」的唯一机械闸门。"
        ),
    },
    {
        "id": "SL-CAP-0030",
        "name": "外部集成边界三态（有配置 ≠ 在运行）",
        "description": (
            "产品语义中的每一个外部集成必须落在三态之一，不得只写「支持 X 集成」这种无状态断言："
            "confirmed_runtime（代码路径确实在运行时调用该集成，有可定位的调用点）、"
            "configured_boundary（仅存在配置文件、环境变量或依赖声明，无运行时调用证据）、"
            "integration_unknown（两者皆未找到，或找到但无法判定是否被加载）。"
            "硬规则：只要检测到 provider 配置文件或依赖声明，就必须产出对应的 integration 条目，"
            "哪怕其状态是 configured_boundary 或 integration_unknown；不得静默省略。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["integration_signals{config_files[], env_keys[], manifest_deps[]}",
                   "call_sites[]（来自 Facts 的调用点候选）"],
        "outputs": ["integration_boundary{provider, state, call_site?, config_ref, unknown_reason?}"],
        "depends_on_modules": ["Facts", "Collector"],
        "overlaps": (
            "与 SL-CAP-0029 的 Boundaries 要素是同一字段的实现细则：0029 定义该字段存在，"
            "本条定义该字段怎么填。与 Collector 的 SL-CAP-0001（facts）是读取关系，不重算"
        ),
        "unresolved": [
            "动态加载的集成（插件目录、反射、运行时装配）无法静态判定时，是否一律归 integration_unknown，待 F2",
            "integration_unknown 是否需要额外记录「已尝试哪些检测手段」，V1 取必填 unknown_reason",
        ],
        "refs": [("UPSTREAM-03", "C01", "REUSE")],
        "notes": (
            "U03-C01 判 REUSE：这是三个上游里唯一把「有配置 ≠ 在运行」写成显式三分的地方，"
            "且上游自己带了一条可直接采纳的强制规则（provider 配置文件存在则必须有 Integration 条目"
            "或解释性 Unknown）。三分不是分类学而是防伪机制：它挡住的是「仓库里有 openai 的 key 配置，"
            "于是报告写支持 OpenAI」这类从配置推到运行时行为的越级断言。"
            "直接沿用，无需改写。"
        ),
    },
    {
        "id": "SL-CAP-0031",
        "name": "业务实体建模与实体关系（页类型 + 判定清单）",
        "description": (
            "识别产品语义中的业务实体（领域对象，如订单、账户、任务、租户），为每个实体建立独立条目，"
            "并记录实体之间的关系（归属、引用、一对多、状态迁移）。每个实体条目必须给出："
            "entity_key 与别名集、支撑字段来源（来自 Facts 的模型/表/类型定义位置）、"
            "生命周期状态、与其他实体的关系清单、以及「为何判定它是业务实体而非技术结构体」的判据说明。"
            "判定必须有可核对的判据清单，不得只凭「看起来像业务对象」。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["repo_facts 中的类型/模型/表定义", "domain_vocabulary（领域词表，可由文档补充）"],
        "outputs": [
            "entity{entity_key, aliases[], definition_sites[], lifecycle_states[], relations[]}",
            "entity_relation{from, to, kind, evidence_refs[]}",
            "entity_decision_basis{entity_key, criteria_met[], criteria_failed[]}",
        ],
        "depends_on_modules": ["Facts", "Collector", "Evidence-Claims"],
        "overlaps": (
            "与 Storage 的实体身份注册无关：本条识别的是被测产品内部的领域对象，"
            "Storage 注册的是知识库自身的 subject 身份。两者名字接近但对象完全不同"
        ),
        "unresolved": [
            "技术结构体与业务实体的判定阈值（字段数、被引用次数、是否进 API 契约）未定量，待 F1-C",
            "实体关系是否要求双向可推导（A→B 存在是否必然产出 B→A），V1 取单向记录 + 反向索引由查询侧生成",
            "同一概念在代码里用多个类名表示时，entity_key 的归并规则属 F2",
        ],
        "refs": [("UPSTREAM-03", "C16", "REIMPLEMENT")],
        "notes": (
            "U03-C16 判 REIMPLEMENT：目标正确但上游的实现完全缺失——十四步构建序里没有实体步、"
            "章节结构里没有实体章、范围清单里没有实体项、README 的输出清单里也没有实体，"
            "属审计记录的 D4。上游唯一的判定标准（「它是不是一个业务实体」）是纯判断、无判据。"
            "所以本条不是补齐上游，而是自行设计：页类型 + 判定清单 + 关系结构。"
            "这也是本批最重要的一条自建能力——没有实体层，产品模型就只剩功能列表。"
        ),
    },
    {
        "id": "SL-CAP-0032",
        "name": "产品语义渐进构建序（分轮推进 · 禁止一次成型 · 精修动作集）",
        "description": (
            "产品语义必须分轮构建，不得对全仓一次性生成：第一轮取广度（结构、清单、入口），"
            "第二轮取角色与功能，第三轮取流程与实体，第四轮取边界与约束，后续轮只做精修。"
            "轮次之间存在硬依赖：Flow 必须在术语表、角色、功能之后；Overview 必须最后生成。"
            "每轮必须声明本轮的预算（读取文件数上限）与取样规则，且每轮产出的新字段必须可与前轮合并"
            "而不推倒重来。精修轮只允许十类动作（补证据、降 claim_type、拆字段、合并重复、补别名、"
            "补关系、补未知项、修正措辞、删除无据字段、标记冲突），不允许新增未取证的要素。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["round_budget{files_read_cap, tokens_cap}", "prior_round_output"],
        "outputs": [
            "round_record{round_no, scope, budget_used, fields_added[], fields_refined[]}",
            "build_order_violation{detail}（若违反依赖序则必须报错而非静默重排）",
        ],
        "depends_on_modules": ["Facts", "Collector"],
        "overlaps": (
            "与 Research 的多轮研究流程不是同一件事：本条管「产品语义在本仓内如何分轮取数」，"
            "Research 管「跨仓库、跨时间的外部资料如何收集」。两者共享分轮思想，不共享实现"
        ),
        "unresolved": [
            "轮数与预算的具体数值待 F2 按仓库规模定，本批只要求「每轮必须声明预算」这一结构",
            "上游「每阶段回看整仓」的假设必须去掉，替换后的取样规则（按入口/按依赖中心度/按体积）待 F1-C",
            "十类精修动作是否允许在首轮就使用，V1 取否（精修动作仅限第二轮及以后）",
        ],
        "refs": [
            ("UPSTREAM-03", "C07", "ADAPT"),
            ("UPSTREAM-03", "C13", "ADAPT"),
            ("UPSTREAM-03", "C14", "ADAPT"),
        ],
        "notes": (
            "合并依据：三项讲的是同一件事的三个侧面——C07 给现成的依赖序（先术语、再角色功能、"
            "后流程、Overview 最后），C13 给分轮推进的调度原则（广度优先、禁止一次成型），"
            "C14 给轮与轮之间的精修动作集。拆开则 C07 只有顺序没有预算、C13 只有原则没有顺序、"
            "C14 没有可以挂靠的阶段。三者合并为一条完整的构建序。"
            "三项均判 ADAPT：C07 的「每阶段回看整仓」与低 token 目标正面冲突（审计 D3），必须去掉；"
            "C13 缺每轮预算与取样规则；C14 上游把它写成流程阶段但无完成谓词，本条只保留动作集、"
            "去掉阶段含义。"
        ),
    },
    {
        "id": "SL-CAP-0033",
        "name": "产品语义的未知项与来源冲突登记",
        "description": (
            "产品语义中的不确定性必须作为一等条目记录，不得留空、不得用概括性描述掩盖。"
            "未知项条目五字段必填（全部为 MUST）：type（未知的是什么类别）、scope（影响哪些要素或字段）、"
            "why_unknown（为何未能确定，须区分「资料不存在」与「资料存在但互相矛盾」）、"
            "owner（谁负责补充，可为外部方或后续轮次）、resolved_by（以什么条件/证据可关闭）。"
            "未知项有生命周期：open → resolved | superseded | accepted_permanent。"
            "来源冲突单独记录：同一要素在两个来源给出不同结论时，必须落一条 conflict 条目，"
            "内含两个来源的 evidence_refs 与差异说明；冲突不得被静默择一，也不得另立来源优先级，"
            "裁定沿用 Evidence-Claims 已有的 source_type 体系。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["product_model 中的空字段与低置信字段", "multi_source_observations[]"],
        "outputs": [
            "unknown_item{unknown_id, type, scope, why_unknown, owner, resolved_by, status}",
            "conflict_item{conflict_id, element, source_a_refs[], source_b_refs[], delta_note, status}",
        ],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0028 有明确分界：0028 判的是「这条 claim 能不能算成立」"
            "（裁决状态机），本条记的是「产品语义里哪块还不知道、为什么不知道」（语义缺口）。"
            "unknown_item 不等于 insufficient_evidence：前者是被测产品的知识缺口，后者是本次裁决的证据不足。"
            "与 SL-CAP-0022 的技术执行失败也须分开：取数失败不等于产品未知"
        ),
        "unresolved": [
            "unknown_item 与 Evidence-Claims 的 insufficient_evidence 在产物中如何避免双写，待 F2 定产物形态",
            "conflict 的裁定程序（谁能裁、裁定结果写在哪）上游未给，本批只规定「必须记录 + 沿用 source_type」",
            "accepted_permanent 的授予条件未定（谁有权宣布某缺口永不补齐）",
        ],
        "refs": [
            ("UPSTREAM-03", "C09", "ADAPT"),
            ("UPSTREAM-03", "C10", "ADAPT"),
        ],
        "notes": (
            "合并依据：C09（未知项一等公民）与 C10（来源冲突必须记录）是同一件事的两个来源类别——"
            "未知可能因为「根本没有资料」，也可能因为「资料互相矛盾」。两者共用同一套登记与生命周期载体，"
            "拆开会出现两份互不知情的不确定性清单。"
            "C09 判 ADAPT：五字段可直接 schema 化，但上游缺 owner 与 resolved_by（审计 D13），"
            "且五字段只是 SHOULD——必须提为 MUST，否则整条规则退化为可省略。"
            "C10 判 ADAPT：规则正确必要，但上游只说记录冲突、不给解决程序；"
            "本条改为「冲突进 evidence 体系、按既有 source_type 裁定、不另立优先级」，"
            "避免与 Evidence-Claims 已有的证据体系形成两套互不兼容的排序。"
        ),
    },
    {
        "id": "SL-CAP-0034",
        "name": "产品语义的可判定终止条件与字段置信度",
        "description": (
            "产品语义构建必须有可计算的终止判据，不得以「再跑一轮也没多少新东西」这类主观判断收尾。"
            "三条终止条件任一成立即停：其一，连续一轮新增字段数为零且无字段 claim_type 升级；"
            "其二，剩余未覆盖区域全部已登记为 unknown_item 并带 owner；其三，本轮预算用尽且下一轮"
            "预计只能处理已登记未知项。终止必须产出终止记录（触发的是哪一条、当时计数）。"
            "每条产品字段另带三档置信度 High/Medium/Low，档位由证据强度决定而非作者自评："
            "High = 至少一条 fact 型证据且无冲突；Medium = 仅有 declaration 或 inference 型证据；"
            "Low = 仅有间接线索或多个来源不一致。置信度跨字段聚合时取最小值，不取平均。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["round_record[]", "unknown_item[]", "field_provenance{}"],
        "outputs": [
            "termination_record{triggered_rule, counters, at_round}",
            "field_confidence{field_path, tier, basis_claim_types[]}",
            "aggregate_confidence{minimum_tier, contributing_fields[]}",
        ],
        "depends_on_modules": ["Product"],
        "overlaps": (
            "与 SL-CAP-0032 是流程的两端：0032 规定怎么分轮推进，本条规定何时停、每轮成果的可信度如何标。"
            "置信度与 Evidence-Claims 的 report_tier 不是同一刻度：tier 是裁决结论的档位，"
            "confidence 是产品字段的证据强度；后者是前者的输入之一，不得互相替代"
        ),
        "unresolved": [
            "三条终止条件的优先级（同时成立时记录哪一条）待 F2，V1 取记录全部成立项，不择一",
            "聚合取最小值在字段稀疏时会过度保守，是否需要「覆盖字段数 ≥ N 才聚合」的门槛待 F1-C",
            "Medium 与 Low 的边界（「间接线索」的判定）需可执行定义，本批只给方向",
        ],
        "refs": [
            ("UPSTREAM-03", "C17", "REIMPLEMENT"),
            ("UPSTREAM-03", "C11", "ADAPT"),
        ],
        "notes": (
            "合并依据：终止条件要能判定，必须先有「本轮进展如何度量」，而进展度量正是字段置信度的升级；"
            "两者共用 round_record 与 field_provenance 两个输入。拆开则终止条件无处可算。"
            "C17 判 REIMPLEMENT：上游十三条终止条件全部是 SHOULD，且核心判据「additional passes produce "
            "little new product knowledge」不可度量（审计 D11），等于没有终止条件——必须自行设计可计算判据。"
            "C11 判 ADAPT：三档定义本身清晰，但上游缺聚合规则与跨页一致性度量（审计 D8/D9），"
            "且未覆盖其自身允许的百分比豁免（D7）；本条补「聚合取最小值」并明确禁止百分比。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
# 本批筛选过程中确认主要不属于 Product 的两个身份。裁决在此落盘，
# 目标模块接手时才由各自批次的 def 转成 MAPPED。
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-03", "C15"): (
        "Renderer",
        "受众清单（L995）的用途是决定卡片与报告的信息密度，属渲染层决策；"
        "Product 只产出要素内容，不决定呈现形态",
    ),
    ("UPSTREAM-03", "C08"): (
        "Lifecycle",
        "Rerun Protocol 的九个触发点（文件哈希变化、注册表增减、页面缺失）是知识库增量重建契约，"
        "属生命周期管理；Product 只管单次构建的分轮推进",
    ),
}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
# 全部来自 UNREVIEWED（草稿里没有指向 Product 的既有分流记录），
# 故迁移来源一律记 unreviewed_adopted。
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-03", "C01"): ("SL-CAP-0030", "unreviewed_adopted"),
    ("UPSTREAM-03", "C06"): ("SL-CAP-0029", "unreviewed_adopted"),
    ("UPSTREAM-03", "C07"): ("SL-CAP-0032", "unreviewed_adopted"),
    ("UPSTREAM-03", "C09"): ("SL-CAP-0033", "unreviewed_adopted"),
    ("UPSTREAM-03", "C10"): ("SL-CAP-0033", "unreviewed_adopted"),
    ("UPSTREAM-03", "C11"): ("SL-CAP-0034", "unreviewed_adopted"),
    ("UPSTREAM-03", "C13"): ("SL-CAP-0032", "unreviewed_adopted"),
    ("UPSTREAM-03", "C14"): ("SL-CAP-0032", "unreviewed_adopted"),
    ("UPSTREAM-03", "C16"): ("SL-CAP-0031", "unreviewed_adopted"),
    ("UPSTREAM-03", "C17"): ("SL-CAP-0034", "unreviewed_adopted"),
}
