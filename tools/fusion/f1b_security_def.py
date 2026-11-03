#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Security 模块：canonical 定义与跨模块去向。

导出符号：
    MODULE                    "Security"
    FIRST_ID                  "SL-CAP-0046"
    CANON                     8 条 canonical（0046–0053）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的 4 个身份（含改路由的 U06-C18）
    CONSUMED_THIS_BATCH       本批正式承接的 17 个身份（2 条 ROUTED + 15 条未审直采）

ID 规则：从 SL-CAP-0046 起连续分配，不重排 0001–0045。

许可证红线：UPSTREAM-06 无明确复制授权，本文件所有涉及 U06 的条目只取抽象设计思想，
不得复制其脚本、规则原文、提示词、模板或检查代码。
"""

MODULE = "Security"
FIRST_ID = "SL-CAP-0046"

CANON = [
    {
        "id": "SL-CAP-0046",
        "name": "两阶段信任边界与阶段间上下文卫生",
        "description": (
            "安全分析分为两类上下文且必须全程分离：finder（取证与候选发现）与 judgment（判定与评级）。"
            "finder 只产出结构化事实字段（路径、行号、内容哈希、调用点），不得产出结论性判断；"
            "judgment 只读 finder 的结构字段，不得读取 finder 的任何推断或措辞。"
            "硬规则一：证据可继承，结论不可继承。下游阶段可以复用上游的阶段产出的结构事实，"
            "但不得继承上游的判断、评级或措辞倾向——这是反锚定纪律，防止一个错误初判被后续阶段层层加固。"
            "硬规则二：这不是完整的安全边界。上游自己写明「第二层边界不防第一层」，"
            "本条只声明分层的一半，不宣称它能防住提示注入（见 SL-CAP-0052 的不可信数据处理契约）。"
            "硬规则三：两类上下文的交接物必须是可机读的结构，不是散文；"
            "任何自由文本结论都不得跨越这条边界。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["finder_output{paths[], line_ranges[], content_hashes[], call_sites[]}",
                   "stage_context{role: finder|judgment}"],
        "outputs": [
            "boundary_contract{stage_a_outputs[], stage_b_inputs[], inherited[]}",
            "anchor_violation{stage, offending_field, reason}",
            "context_hygiene_check{passed, violations[]}",
        ],
        "depends_on_modules": ["Collector", "Facts"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0023（显式未知优于自信猜测）相邻但不同："
            "0023 管一条 claim 的措辞层级，本条管「谁有权产结论、结论能不能跨阶段继承」。"
            "与 SL-CAP-0052 是同一安全模型的两面：本条管内部分层，0052 管外部不可信输入"
        ),
        "unresolved": [
            "finder 与 judgment 是否必须是独立进程/独立上下文，还是可以同进程不同提示层，待 F2",
            "anchor_violation 的检测手段（字段白名单校验 vs 全文扫描）待 F2",
            "上游自己承认第二层不防第一层，SourceLore 是否需要额外的注入防护层待 F1-C",
        ],
        "refs": [
            ("UPSTREAM-06", "C01", "ADAPT"),
            ("UPSTREAM-06", "C02", "REUSE"),
        ],
        "notes": (
            "合并依据：C01 给「委托与判断必须由不同上下文承担」的分层结构，"
            "C02 给「下游只读结构字段、不读上游 findings」的上下文卫生纪律——"
            "两者是同一信任边界的结构面与纪律面。C01 单用只是分层，没有卫生纪律就仍会锚定；"
            "C02 单用只是纪律，没有分层就无处施加。"
            "C01 判 ADAPT：抽象设计可采纳，但上游自陈「Boundary 2 不防 Boundary 1」，"
            "不是完整答案而是分层的一半，本条如实标注这一局限，不夸大其防护范围。"
            "C02 判 REUSE：这是可独立实现的反锚定纪律，且能直接映射为 SourceLore 的"
            "「证据可继承、结论不可继承」约束。UPSTREAM-06 无许可证，只取抽象思想，实现自建。"
        ),
    },
    {
        "id": "SL-CAP-0047",
        "name": "安全发现契约与四项独立检查（证据分级）",
        "description": (
            "每条安全发现必须携带固定字段集：source_commit_sha、affected_component、category、"
            "evidence_refs、data_flow（适用时）、validation_status、severity、remediation_priority、"
            "detection_limitations。缺任一项即判该发现不完整，不得进入报告。"
            "核心是把四件常被混为一谈的事做成四个独立检查结果，任一不可推出另一："
            "C-1 位置存在——文件与行号确实在被分析快照中；"
            "C-2 数据流链完整——从入口经各跳到达落地点的链路齐全（仅对需要链路的类型）；"
            "C-3 安全影响有充分证据——该模式确实构成风险而非写法风格；"
            "C-4 运行时可达性已验证——攻击者确实能触达。"
            "硬规则一：没有足够证据的风险只能停在 unconfirmed，不得直接成为确认漏洞。"
            "硬规则二：无法验证也不能自动标记为 false_positive——它停在 inconclusive。"
            "这条规则继承 F0 与 Evidence-Claims 对上游「can't prove → FALSE_POSITIVE」的既有拒绝。"
            "硬规则三：并非所有发现都需要完整数据流链。硬编码密钥、构建依赖风险、"
            "危险 Skill 指令这类不必要求 HTTP 入口；但缺链路的类型必须在 detection_limitations 里写明。"
            "硬规则四：evidence_refs 一律指向 Evidence-Claims 的证据记录 ID，"
            "不得另建一套 Security Evidence Registry。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["candidate{category, location, pattern_hit}", "pinned_snapshot",
                   "evidence_records[]（来自 EC）", "flow_evidence?（来自 EC 的 SL-CAP-0021）"],
        "outputs": [
            "security_finding{source_commit_sha, affected_component, category, evidence_refs[], "
            "data_flow?, validation_status, severity, remediation_priority, detection_limitations}",
            "check_result{check_id: C_1|C_2|C_3|C_4, verdict: passed|failed|not_applicable, basis}",
            "finding_status{unconfirmed|confirmed|inconclusive, blocked_by[]}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Facts", "Collector"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0021（四节点数据流证据定位）是引用关系："
            "本条需要链路时直接引用 EC 已定义的 flow_evidence 结构，不重复定义节点语义。"
            "与 EC 的 SL-CAP-0028（裁决状态机）分界：本条产出 unconfirmed/confirmed/inconclusive，"
            "EC 产出 supported/refuted/insufficient——前者是安全发现的专用状态，后者是通用 claim 状态"
        ),
        "unresolved": [
            "四檢查与 finding_status 的映射表（哪几项通过才算 confirmed）待 F2",
            "不要求数据流链的类型清单是否需要穷举，待 F1-C",
            "本条与 EC 的 claim_status 在产物里如何避免双写，待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是独立设计。理由写清楚，否则读者会以为漏了引用。"
            "U06-C05（四节点数据流契约）已在 Evidence-Claims 批次由 SL-CAP-0021 正式承接，"
            "同一原始身份只能映射一次，故本条不引用它，只声明「需要链路时引用 EC 的结构」。"
            "上一轮 Lifecycle 批次把 U06-C26 判给 SL-CAP-0042，Research 批次把 U04-C24 等判给 EC，"
            "本批同样遵守「起草前先确认候选未被占用」的纪律。"
            "剩下的内容——固定字段集、四项独立检查、unconfirmed/inconclusive 的硬规则、"
            "「不是所有发现都需要链路」——是 SourceLore 自建的安全发现契约，"
            "六源中没有任何一处把它落成结构字段，属零来源独立设计。"
        ),
    },
    {
        "id": "SL-CAP-0048",
        "name": "确定性前置门与失效安全（Surface / Boundary / 环境失败 / 保守降级）",
        "description": (
            "安全验证链路前必须设置确定性前置门，门的判定不得依赖模型主观判断。"
            "四类门与两条纪律："
            "Surface Gate——非生产面（测试目录、示例代码、生成物）的候选做确定性抑制与置信度封顶；"
            "但路径名只是信号，不得在缺乏证据时直接证明代码不进生产环境。"
            "Boundary Gate——按认证覆盖度决定是否降级：已证明受认证保护 / 已证明可匿名访问 / 覆盖情况未知，"
            "三态必须分列。认证覆盖的判定必须来自确定性抽取，不得用模型推断的 auth_coverage "
            "把高风险发现自动降级；覆盖未知时门不生效。"
            "Fail-safe gating——把「不确定」转成「降低覆盖面但不漏项」：不确定时扩大扫描面而非缩小。"
            "环境失败绝不改判——工具没跑起来、扫描器崩溃、网络不可达，都不是证据，"
            "不得因此把任何发现判为 false_positive，也不得因此降低严重度。"
            "硬规则：两道门都不允许因为发现严重度高就跳过；门不是误报判定，只是范围与开销的裁剪。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["candidate{location, category}", "auth_coverage{state, basis}",
                   "scan_environment{scanners_run[], failures[]}"],
        "outputs": [
            "gate_decision{gate: surface|boundary, verdict: suppress|pass|not_applicable, basis}",
            "auth_coverage_state{state: authenticated|anonymous|unknown, extraction_basis}",
            "coverage_gap{scanner, category, missing_scope}",
            "env_failure_record{failure, affected_checks[], verdict_untouched: true}",
        ],
        "depends_on_modules": ["Facts", "Collector"],
        "overlaps": (
            "与 SL-CAP-0050（族扫描与覆盖缺口）共同承担「覆盖不足必须显式」；"
            "本条管验证前的范围裁剪，0050 管验证后的否定结论覆盖面"
        ),
        "unresolved": [
            "非生产面的确定性抑制规则集（哪些目录模式可抑制）待 F2",
            "auth_coverage 确定性抽取能达到的精度，以及不足时门是否只能降级为标注，待 F1-C",
            "封顶语义：置信度封顶后是否仍需完整验证，待 F2",
        ],
        "refs": [
            ("UPSTREAM-06", "C03", "REUSE"),
            ("UPSTREAM-06", "C04", "ADAPT"),
            ("UPSTREAM-06", "C12", "REUSE"),
            ("UPSTREAM-06", "C09", "REUSE"),
        ],
        "notes": (
            "合并依据：C03（Surface Gate）、C04（Boundary Gate）、C12（失效安全门控）、"
            "C09（环境失败不改判）是同一「前置门 + 保守降级」机制的四条规则——"
            "两道门决定范围，失效安全决定不确定时往哪边倒，环境失败规则保护门的判定不被污染。"
            "拆开会出现四套各自为政的门，且「环境失败不得改判」这条保护会落到谁头上说不清。"
            "C03 判 REUSE：确定性前置门能省掉整条验证链开销，且明确区分「代码有漏洞」与「漏洞不在生产面」，"
            "不依赖任何模型判断，可原样独立实现。"
            "C04 判 ADAPT：门的形状可采纳，但上游依赖 Phase 2 产出的 auth_coverage，"
            "而该映射本身是模型生成的（coverage_confidence 为 none/low 时门直接跳过）；"
            "本条要求认证覆盖必须确定性抽取，覆盖未知时门不生效。"
            "C12 判 REUSE：把「不确定」转成「降低覆盖面但不漏项」，是可独立实现的确定性规则。"
            "C09 判 REUSE：环境失败绝不改判，与 SourceLore 既有不变量同源（两处独立收敛）。"
            "UPSTREAM-06 无许可证，四项均只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0049",
        "name": "依赖风险的五级分离与可达性三态",
        "description": (
            "依赖风险必须拆成五个独立判定层次，任一层不得推出另一层："
            "D-1 依赖存在性（清单里确实有）；D-2 依赖版本（具体解析出的版本）；"
            "D-3 漏洞公告匹配（该版本命中哪条公告）；D-4 代码可达性（本项目代码是否实际调用受影响路径）；"
            "D-5 实际部署暴露面（该组件是否进入构建产物与运行环境）。"
            "可达性三态：REACHABLE / UNREACHABLE / INDETERMINATE，必须写在 claim 本身就位，"
            "不得像上游那样先留 null 由后续阶段回填（中间态语义会丢失）。"
            "硬规则一：有界静态搜索未发现调用路径时，原则上不得直接宣称 UNREACHABLE——"
            "只判 INDETERMINATE 并记录搜索边界。"
            "硬规则二：保守默认——信息不足时取更严重的假设，但必须在产物里标注这是保守取值而非事实。"
            "硬规则三：技术严重度（severity）与修复优先级（remediation_priority）是两个独立字段。"
            "严重度描述脆弱性本身的强度；优先级描述「现在该先修哪个」，受暴露面、可达性、"
            "业务影响共同影响。不得压成一个数字。"
            "硬规则四：禁止使用未经校准的模型置信百分比。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["dependency_inventory{name, resolved_version}", "advisory_matches[]",
                   "call_site_evidence[]", "deployment_scope{build_artifact, runtime_env}"],
        "outputs": [
            "dependency_risk{d1_present, d2_version, d3_advisory, d4_reachability, d5_exposure}",
            "reachability{state: reachable|unreachable|indeterminate, search_bounds, basis}",
            "risk_rating{severity, remediation_priority, priority_basis}",
        ],
        "depends_on_modules": ["Facts", "Collector"],
        "overlaps": (
            "与 SL-CAP-0047 的 C-4（运行时可达性已验证）是同一概念的两层："
            "0047 的 C-4 是单条发现的检查项，本条 D-4 是依赖链路的专用三态判定"
        ),
        "unresolved": [
            "有界搜索的边界如何声明（目录深度、调用深度、是否含动态派发）待 F2",
            "KEV 类下限清单的维护方与更新频率待 F1-C",
            "D-5 部署暴露面的判定依赖构建产物分析，是否属 Collector 职责待 F1-C",
        ],
        "refs": [
            ("UPSTREAM-06", "C15", "ADAPT"),
            ("UPSTREAM-06", "C16", "REUSE"),
        ],
        "notes": (
            "合并依据：C15 给「可达性三态 + 保守默认 + KEV 下限」，C16 给「有效严重度与优先级分离」——"
            "两者都在回答「这条依赖风险到底有多要紧」，而答案必须由可达性与严重度共同决定。"
            "C15 判 ADAPT：三态与保守默认可采纳，但上游 reachable 字段在 P3 恒为 null、由 P3b 回填，"
            "中间态语义在产物里不显式；本条要求三态写进 claim 本身就位。"
            "C16 判 REUSE：技术严重度与处置优先级分离是本轮少见的正确分层，直接沿用。"
            "两处均只取抽象设计，UPSTREAM-06 无复制授权。"
        ),
    },
    {
        "id": "SL-CAP-0050",
        "name": "族扫描、覆盖缺口登记与诚实否定",
        "description": (
            "否定结论必须携带覆盖面证据，不得以「没扫到」代替「不存在」。"
            "族扫描：当某类风险在同一仓库内有多个同类载体（多个 curl 包装器、多个配置加载点、"
            "多个入口脚本）时，必须扫描整个族，不得只读其中一个就宣布该类风险不存在。"
            "覆盖缺口登记：任一扫描器未运行、任一类规则未覆盖、任一路径因权限或分页未取到时，"
            "必须产出 coverage_gap 记录，含 scanner、category、missing_scope 三字段。"
            "硬规则一：未运行某扫描器或未覆盖某类规则时，禁止输出「不存在该类漏洞」。"
            "硬规则二：否定结论必须携带 family_swept 与 class_negatives 两个字段——"
            "前者记录已扫的族成员，后者记录被判否定的类别及其依据。"
            "硬规则三：部分覆盖时结论只能是 partial_negative，不得写成 negative。"
            "上游给的失败案例极准：读了 curl 包装器就宣布「SSRF 确信无」，"
            "而同目录的 wget 包装器没读——这正是本条要挡的系统性缺陷。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["risk_class", "family_members[]", "scan_coverage{scanners[], categories[]}"],
        "outputs": [
            "negation_record{risk_class, verdict: negative|partial_negative, family_swept[], class_negatives[]}",
            "coverage_gap{scanner, category, missing_scope}",
        ],
        "depends_on_modules": ["Facts", "Collector"],
        "overlaps": (
            "与 SL-CAP-0048 的 coverage_gap 是同一字段的两种来源：0048 记验证前的工具缺口，"
            "本条记否定结论的覆盖面。两者共用结构，不重复定义"
        ),
        "unresolved": [
            "族成员的判定规则（同目录？同扩展名？同框架？）待 F2",
            "partial_negative 的降级展示方式归 Renderer，本批只定义字段",
            "与 Lifecycle 的知识失效：否定结论的覆盖面变化时如何重验，见跨模块 unresolved",
        ],
        "refs": [
            ("UPSTREAM-06", "C14", "REUSE"),
            ("UPSTREAM-06", "C08", "ADAPT"),
        ],
        "notes": (
            "合并依据：C14（族扫描与诚实否定）直接修复「一个文件有问题、其余文件没看」的系统性缺陷，"
            "C08（动态证据升级阶梯）提供「先取最便宜证据、不够再升级」的取证顺序——"
            "两者共同决定「这条否定结论到底扫了多少」。"
            "C14 判 REUSE：用产物字段（family_swept / class_negatives）强制留痕，"
            "可直接映射为 SourceLore 的否定结论契约。"
            "C08 判 ADAPT：阶梯本身正确，但上游默认路径包含 docker run 不受信仓库代码（审计 D3），"
            "SourceLore 只采纳其「逐级升级 + 每级独立同意」的结构，整体拒绝任何对不受信代码的动态执行。"
            "UPSTREAM-06 无许可证，只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0051",
        "name": "动态验证的双重控制与结构性构造门",
        "description": (
            "任何动态验证（构造并执行 PoC、运行不受信代码、对真实服务发起请求）必须由两个互不蕴含的开关同时打开："
            "控制一，留证据（允许持久化观察记录）；控制二，跑执行（允许实际执行）。"
            "任一单独打开都不构成授权：留证据不等于可以执行，执行也不等于可以把结果落盘。"
            "结构性构造门：PoC 的构造点必须钉在验证之后——被拒绝的 finding 永不进入构造阶段，"
            "即构造所需的所有前置条件（finding 已确认、证据已齐、授权已到）全部满足才允许构造。"
            "硬规则一：默认全关。未显式授权时两个开关都不得打开。"
            "硬规则二：不得一键跳过全部同意门。每次升级需要独立同意，前一阶段的同意不覆盖后一阶段。"
            "硬规则三：本能力只定义控制契约，不定义任何具体攻击工具；"
            "上游的一键安装外部扫描器（U06-C28）判 REJECT，不采纳。"
            "硬规则四：环境失败绝不改判（与 SL-CAP-0048 同源）——动态验证没跑起来不是证据。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["finding{validation_status}", "gate_state{persist_evidence, execute}", "approvals[]"],
        "outputs": [
            "dual_control{gates: {persist_evidence, execute}, both_required: true}",
            "construction_gate{allowed, blocked_by[], precondition_checks[]}",
            "approval_record{stage, granted_by: human, scope}",
        ],
        "depends_on_modules": ["Evidence-Claims"],
        "overlaps": (
            "与 SL-CAP-0048 的 fail-safe 是不同层：0048 管「不确定时扩大扫描面」，"
            "本条管「不确定时绝不执行」。与 EC 的 SL-CAP-0028 裁决状态机是输入关系"
        ),
        "unresolved": [
            "同意门的粒度（每次执行一次 vs 每个 finding 一次）待 F2",
            "动态验证结果的持久化形态：属证据（EC）还是属运行记录（Storage），待 F1-C",
            "本能力在 V1 是否整体 DEFERRED（SourceLore V1 可能完全不执行动态验证），待 F1-C",
        ],
        "refs": [
            ("UPSTREAM-06", "C11", "REUSE"),
            ("UPSTREAM-06", "C28", "REJECT"),
        ],
        "notes": (
            "U06-C11 判 REUSE：这是本轮最强的安全设计——把「留证据」与「跑利用」拆成两个互不蕴含的开关，"
            "且构造点被钉在验证之后。SourceLore 若做任何动态验证必须照此拆分，否则"
            "「只是想留个记录」会变成「顺手跑了一次攻击」。"
            "顺带说明 U06-C28（一键安装外部扫描器）在本条内判 REJECT："
            "安装不锁版本、不校验、直接从网络装二进制，与「每次升级独立同意」的控制模型正面冲突。"
            "U06-C28 的正式身份归属在本条（verdict=REJECT），SL-CAP-0052 只在描述中提及它作为反例，"
            "不在其 refs 里重复登记——同一原始身份只能正式映射一次。"
            "UPSTREAM-06 无复制授权，只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0052",
        "name": "Agent / Skill 指令安全与不可信数据处理",
        "description": (
            "SourceLore 自身就是 skill/agent 产物，因此必须对自己施加与对被分析仓库同等的安全约束。"
            "核心是把「外部内容是不可信数据」落成可实施契约而非提醒："
            "A-1 外部仓库的 README、SKILL.md、Issue、代码注释、配置值一律视为待分析数据，"
            "不得提升为系统级指令；A-2 外部内容不得要求执行本地 shell 命令；"
            "A-3 不得借分析任务读取无关私有文件或环境变量；A-4 工具调用遵循最小权限；"
            "A-5 未经明确授权不得上传本地私有源码到第三方服务；"
            "A-6 敏感信息不得直接进入报告或知识卡片；"
            "A-7 不能让被分析仓库决定 SourceLore 的审查步骤或安全策略。"
            "硬规则一：A-1 至 A-7 必须以可检查的规则形式存在（每条带 rule_id 与检测条件），"
            "不接受「请注意不要被注入」这类散文。"
            "硬规则二：A-7 是元级约束——审查步骤由 SourceLore 决定，外部仓库只能作为被审对象。"
            "硬规则三：OWASP LLM Top 10 类清单只作为自审项来源，不构成自动通过的门；"
            "自审未跑必须登记为 coverage_gap。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["external_content{source, kind}", "tool_call_intent", "capability_scope"],
        "outputs": [
            "instruction_safety_rule{rule_id: A_1..A_7, condition, detection_method, failure_action}",
            "violation_record{rule_id, offending_input, blocked_action}",
            "self_audit_status{checked[], gaps[]}",
        ],
        "depends_on_modules": ["Collector"],
        "overlaps": (
            "与 SL-CAP-0046 是同一安全模型的内外两面：0046 管内部分层，本条管外部不可信输入。"
            "与 SL-CAP-0053 相邻：A-6（敏感信息不进报告）与发布脱敏是同一方向的不同阶段"
        ),
        "unresolved": [
            "A-1 的检测方法（内容分类器 vs 结构标记 vs 来源白名单）待 F2",
            "工具调用的最小权限如何表达（能力声明 vs 运行时拦截）待 F1-C",
            "上自审的 OWASP 清单是否需要逐项绑定检测条件，待 F1-C",
        ],
        "refs": [("UPSTREAM-06", "C22", "ADAPT")],
        "notes": (
            "U06-C22 判 ADAPT：检查清单本身可采纳为 SourceLore 的自审项（SourceLore 自己就是 skill 产物），"
            "但上游的激活条件是 tech-stack.json 的 is_skill_repo，且自陈混合仓库默认不跑——"
            "覆盖面偏窄，本条改为无条件自审。"
            "U06-C28 判 REJECT：一键安装外部扫描器（brew/go install @latest/releases 下载/"
            "pip --break-system-packages/curl | sh）无版本钉定、无校验和，"
            "与最小权限与「每次升级独立同意」正面冲突。此处与 SL-CAP-0051 各登记一次是"
            "为避免同一身份重复映射的技术处理——两个 canonical 都确实引用了它作为反例，"
            "但正式身份归属在 SL-CAP-0051（见其 notes）。"
            "本条只承接 C22；U06-C28 的正式归属在 SL-CAP-0051（verdict=REJECT），"
            "此处仅作反例引用，不重复登记。"
            "UPSTREAM-06 无复制授权，只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0053",
        "name": "敏感信息分级、脱敏与发布门禁（脱敏通过 ≠ 允许发布）",
        "description": (
            "产物必须按敏感度分级，并在发布前机械剥离，且剥离通过不等于发布批准。"
            "分级：每条内容标敏感级（框架自定，可参考上游 L1–L5 但须独立定义），"
            "级别记在内容元数据里而非正文，使剥离可机械执行而不是靠人眼。"
            "脱敏：构建后对产物运行机械剥离，规则按分级匹配；剥离必须可复算、可审计，"
            "记录被剥离项的数量与类别（不记录原文）。"
            "发布门禁：分四级且互不推导——"
            "P-1 分级完成（每条内容都有级别）；"
            "P-2 脱敏完成（机械剥离已跑且无残留）；"
            "P-3 人工审查（人已看过，状态记 human_reviewed）；"
            "P-4 发布批准（人明确批准，状态记 approved_for_release）。"
            "硬规则一：AI 可以准备候选，但不得自行把需要人工批准的产物标记为 approved。"
            "P-3 与 P-4 只能由人的动作触发。"
            "硬规则二：脱敏通过（P-2）不等于允许公开发布。脱敏只是必要条件，"
            "发布范围由 P-4 决定。"
            "硬规则三：原始扫描输出不落盘是结构约束，不是事后删除。"
            "上游「尽力删除、失败仅告警」的做法不可采纳——一旦落盘就已经泄露。"
            "硬规则四：密钥打码规则必须覆盖所有产物形态（报告、知识卡片、日志、中间 JSON），"
            "不得只处理其中一种。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["artifact{content, metadata}", "classification_rules", "release_target{scope}"],
        "outputs": [
            "sensitivity_class{artifact_id, level, basis}",
            "redaction_record{artifact_id, removed_count, removed_categories[], residual_check}",
            "release_gate{gate: P_1|P_2|P_3|P_4, status, actor: machine|human}",
            "release_decision{scope, approved, approved_by, at}",
        ],
        "depends_on_modules": ["Storage", "Evidence-Claims"],
        "overlaps": (
            "与 EC 的 SL-CAP-0020（证据存档契约）分界：0020 的 redactions 字段是单条证据的脱敏清单，"
            "本条是全产物范围的分级与发布门禁。与 SL-CAP-0052 的 A-6 是上下游："
            "A-6 要求敏感信息不进报告，本条定义怎么拦"
        ),
        "unresolved": [
            "分级档数与每档定义（上游 L1–L5 只作设计来源，SourceLore 须独立定义）待 F2",
            "人工审查与发布批准的凭证形式（字段值 vs 独立签名）待 F1-C",
            "与 Storage 的实际访问控制接口：分级如何落地为读写权限，见跨模块 unresolved",
            "U05-C04（review_status 人机权限）已由 EC 的 SL-CAP-0028 承接部分语义，"
            "本条只登记跨模块依赖，不重新占用该原始身份",
        ],
        "refs": [
            ("UPSTREAM-05", "C20", "REIMPLEMENT"),
            ("UPSTREAM-06", "C17", "ADAPT"),
            ("UPSTREAM-06", "C27", "REIMPLEMENT"),
        ],
        "notes": (
            "合并依据：U05-C20 给「分级写在元数据、strip 在构建后运行、顺序强制」的机制，"
            "U06-C17 给「密钥打码与原始输出清理」的具体规则，U06-C27 给「密钥/数据分级」的缺口定义——"
            "三者是同一条「分级 → 剥离 → 发布」链路的三段。拆开则分级无处落实、剥离无规则可依。"
            "U05-C20 判 REIMPLEMENT：这是 U05 唯一有真测试背书的机制（12 个用例覆盖三处脚本），"
            "设计可借，但 SourceLore 不需要文档投放分级，需要同构的「产物按敏感度分级 + 发布前机械剥离」，"
            "故不是原样沿用。许可 Apache-2.0，须履行署名、许可链接与修改声明。"
            "U06-C17 判 ADAPT：打码规则可采纳，但上游删除是尽力而为、失败仅告警（审计 D11），"
            "且不覆盖 P3 的原始 JSON（D12）；本条改为「原始扫描输出不落盘」的结构约束。"
            "U06-C27 判 REIMPLEMENT：上游分级没有落成可配置字段，无法表达「哪类内容可进报告、"
            "哪类只能留快照」；本条自建分级字段与判定。U06 两项均只取抽象思想。"
        ),
    },
    {
        "id": "SL-CAP-0054",
        "name": "PR Diff 增量安全审查与移除控制回归",
        "description": (
            "对 PR 的增量差异做专项安全审查，而不是把全量扫描再跑一遍。这类问题全量扫描结构性看不到："
            "被删除的代码可能正是编码了某项控制（输入校验、权限判断、限流、边界条件），"
            "删除后测试仍可能通过、代码看起来更干净，但防护已经消失。"
            "审查判据三件套：D-1 删除行（只对 removed 行生效，不看新增）；"
            "D-2 控制模式命中（删除内容是否匹配安全控制模式集）；"
            "D-3 等价性核验（该控制是否在 diff 的其他位置以等价形式被重新引入）。"
            "三者全部满足才判为 control_regression；只命中 D-2 而 D-3 未核验时，"
            "结论只能是 suspected_regression 并附待核事项。"
            "硬规则一：不得在只看新增行的情况下判「本次 PR 无安全影响」——"
            "增量审查的核心证据在删除侧。"
            "硬规则二：diff 不完整（文件被截断、二进制、超出配额）时必须登记 coverage_gap，"
            "不得对被截断部分作任何否定判断。"
            "硬规则三：本条只产出候选与证据，验证状态仍走 SL-CAP-0047 的四项检查。"
        ),
        "disposition": "REUSE",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["pr_diff{added[], removed[], context}", "control_pattern_set",
                   "diff_completeness{complete, truncated_files[]}"],
        "outputs": [
            "control_regression{file, deleted_lines[], matched_control, equivalence_checked}",
            "increment_verdict{control_regression|suspected_regression|no_regression_found}",
            "coverage_gap{scanner: diff_review, category, missing_scope}",
        ],
        "depends_on_modules": ["Collector", "Evidence-Claims"],
        "overlaps": (
            "与 SL-CAP-0047 是上下游：本条产出增量候选，0047 的四项检查判其是否成立。"
            "与 SL-CAP-0050 的诚实否定共用 coverage_gap 结构："
            "本条针对 diff 截断，0050 针对族扫描覆盖"
        ),
        "unresolved": [
            "控制模式集的具体条目（校验/权限/限流/边界）待 F2",
            "等价性核验的实现手段（AST 比对 vs 语义标注 vs 人工）待 F1-C",
            "suspected_regression 的默认展示与优先级归 Renderer",
            "Security 发现的对象粒度（文件级 vs hunk 级 vs 行级）待 F2",
        ],
        "refs": [("UPSTREAM-06", "C24", "REUSE")],
        "notes": (
            "U06-C24 判 REUSE：这是全量扫描结构性看不到的一类问题，且判据确定"
            "（删除行 + 控制模式 + 等价性核验），SourceLore 的增量审查应直接采用这一形态。"
            "本批把它与 SL-CAP-0047 分开是因为二者的对象不同：0047 判单条发现成立与否，"
            "本条判「这次变更有没有削弱既有防护」——后者不看新增只看删除，是完全不同的证据形态。"
            "该身份来自 Collector 批次的既有分流（routed_promotions 记 cross_module_redirections）。"
            "UPSTREAM-06 无复制授权，只取抽象思想。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-06", "C18"): (
        "DSH-Adapter",
        "改路由：本条是运行成本与可观测性报告（时长 + token 估算），"
        "本质是 Agent 运行成本的自报字段，不属安全。此前 Collector 批次判给 Security 是"
        "按「成本报告是安全审查运行的自报字段」归类，本批按实际内容重新裁决，保留原始理由以便追溯",
    ),
    ("UPSTREAM-06", "C10"): (
        "Evidence-Claims",
        "动态否证只降级到人工复核——这是通用 claim 状态机的人工复核分支，"
        "已由 EC 的 SL-CAP-0028（裁决状态机，含 insufficient_evidence 与人工确认）承接语义",
    ),
    ("UPSTREAM-06", "C20"): (
        "Evidence-Claims",
        "延迟裁决与跨仓库解析属 claim 裁决的时序与跨源聚合，归 EC 的裁决状态机",
    ),
    ("UPSTREAM-06", "C19"): (
        "Storage",
        "多仓库拓扑与跨服务合成会产生第二套关系模型，违反单一模型约束；"
        "跨源关系应落在 Storage 的知识单元依赖与矛盾结构上，不属安全",
    ),
    ("UPSTREAM-06", "C25"): (
        "Storage",
        "三态分离的产物契约（run-metadata / 各阶段 JSON / 报告）是持久化产物模型，"
        "归 Storage 的写入与契约职责；上游该契约无新鲜度与失效语义，需自建",
    ),
}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-06", "C01"): ("SL-CAP-0046", "unreviewed_adopted"),
    ("UPSTREAM-06", "C02"): ("SL-CAP-0046", "unreviewed_adopted"),
    ("UPSTREAM-06", "C03"): ("SL-CAP-0048", "unreviewed_adopted"),
    ("UPSTREAM-06", "C04"): ("SL-CAP-0048", "unreviewed_adopted"),
    ("UPSTREAM-06", "C08"): ("SL-CAP-0050", "unreviewed_adopted"),
    ("UPSTREAM-06", "C09"): ("SL-CAP-0048", "unreviewed_adopted"),
    ("UPSTREAM-06", "C11"): ("SL-CAP-0051", "unreviewed_adopted"),
    ("UPSTREAM-06", "C12"): ("SL-CAP-0048", "unreviewed_adopted"),
    ("UPSTREAM-06", "C14"): ("SL-CAP-0050", "unreviewed_adopted"),
    ("UPSTREAM-06", "C15"): ("SL-CAP-0049", "unreviewed_adopted"),
    ("UPSTREAM-06", "C16"): ("SL-CAP-0049", "unreviewed_adopted"),
    ("UPSTREAM-06", "C17"): ("SL-CAP-0053", "unreviewed_adopted"),
    ("UPSTREAM-06", "C22"): ("SL-CAP-0052", "unreviewed_adopted"),
    ("UPSTREAM-06", "C24"): ("SL-CAP-0054", "cross_module_redirections"),
    ("UPSTREAM-06", "C27"): ("SL-CAP-0053", "unreviewed_adopted"),
    ("UPSTREAM-06", "C28"): ("SL-CAP-0051", "unreviewed_adopted"),
    ("UPSTREAM-05", "C20"): ("SL-CAP-0053", "cross_module_redirections"),
}
