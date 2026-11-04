#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-B 的裁决数据源（纯数据，无逻辑）。

11 项 ROUTED 的逐项裁决。由 f1c_apply_routed.py 消费并应用。

裁决方向取值：
    ADOPT_EXISTING   承接到已有 canonical（需 target_canonical）
    NEW_CANONICAL    新建 canonical（需 new_canonical_def）
    REJECT_WITH_REASON  明确拒绝
    DEFER_WITH_REASON   明确延期
"""

BATCH = "F1-C-B"

DECISIONS = [
    {
        "identity": ["UPSTREAM-04", "C24"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0020",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "完全覆盖。SL-CAP-0020 的强制元数据已含 `reproducible` 三态（yes|no|unknown），"
                         "并要求 minimal 形态附「不可复现说明」。本身份要求的正是「为无法复现的观察留标记」，已在其内。",
            "B_counterexample": "否。不是反例，是已实现的正面能力。",
            "C_independent": "否。无独立语义。",
            "D_owner_correct": "是。EC 的 SL-CAP-0020 已承载该字段。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "MIT，可复制；但本批不复制实现，只登记身份归属。",
        },
        "reason": "该身份要求「无法复现的外部观察必须有标记」。SL-CAP-0020 已把 `reproducible` 三态列入强制元数据，"
                  "并为 minimal 形态要求「不可复现说明」。归属 EC 已由 Collector 批次分流指定，本批将其正式写入 refs。",
        "license_note": "MIT / copy_permitted=true（仅指可复制，不等于已复制）",
    },
    {
        "identity": ["UPSTREAM-05", "C24"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0020",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "完全覆盖。与 U04-C24 同名同义，均落在 SL-CAP-0020 的 reproducible 三态。",
            "B_counterexample": "否。",
            "C_independent": "否。",
            "D_owner_correct": "是。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "Apache-2.0，可复制。",
        },
        "reason": "与 UPSTREAM-04::C24 是同一需求的两次独立记录（上游两份审计都发现「没有为当时观察到、现在无法复现的证据留字段」）。"
                  "合并到同一条 canonical 的同一个字段，不新建。",
        "license_note": "Apache-2.0 / copy_permitted=true",
    },
    {
        "identity": ["UPSTREAM-05", "C04"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0028",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "基本覆盖但需补一条硬规则。SL-CAP-0028 有状态机与「不得由作者自评决定」，"
                          "但未明确「approved 只能由人设、AI 永远 pending」这一条值域约束。本批登记为 SL-CAP-0028 的补充约束。",
            "B_counterexample": "否。",
            "C_independent": "否——该约束属 SL-CAP-0028 的值域，不是独立能力。",
            "D_owner_correct": "是。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "Apache-2.0，可复制。上游原话是「照抄这一取向」，但本批不复制其实现。",
        },
        "reason": "上游把「谁有权批准」编码进字段值域而非写在文档里，是五源中最干净的权限边界表达。"
                  "SL-CAP-0028 已有「状态不得由作者自评决定」的骨架，本批把「人机权限分离」作为值域约束登记进其补充约束。",
        "license_note": "Apache-2.0 / copy_permitted=true",
        "canonical_amendment": {
            "target": "SL-CAP-0028",
            "append_note": "补充值域约束（F1-C-B 由 U05-C04 引入）：review_status 的 approved 只能由人的动作产生；"
                           "AI 只能置 pending，不得自行转换为 approved。该约束编码进字段值域，不写成文档建议。",
        },
    },
    {
        "identity": ["UPSTREAM-06", "C10"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0028",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "覆盖。SL-CAP-0028 的硬规则「不可验证只产生 insufficient_evidence，禁止落成 refuted」"
                         "与该身份「只能把 CONFIRMED 降到 NEEDS_RUNTIME，绝不直接判 FALSE_POSITIVE」同构。",
            "B_counterexample": "否。",
            "C_independent": "否。",
            "D_owner_correct": "是。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "**copy_permitted=false（UPSTREAM-06 无许可）**。只借抽象思想，不得复制其规则文本。",
        },
        "reason": "「代码级证据与运行时证据冲突时仲裁权归人」是 SL-CAP-0028 已有的降级方向。"
                  "UPSTREAM-06 无复制许可，本条只作设计思想来源，不复制任何原文。",
        "license_note": "UPSTREAM-06 / copy_permitted=false —— 仅抽象设计借鉴",
    },
    {
        "identity": ["UPSTREAM-06", "C20"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0028",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "覆盖。SL-CAP-0028 的 adjudication_blocked（依赖缺失，无法启动裁决）正是该身份要求的"
                         "「单仓库无法裁决」这一合法中间态；「解析必须引用新增证据、不得复述原论断」由其状态机驱动规则承接。",
            "B_counterexample": "否。",
            "C_independent": "否。",
            "D_owner_correct": "是。EC 的裁决时序。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "**copy_permitted=false**。只借抽象思想。",
        },
        "reason": "「单仓库无法裁决是合法中间态」与 SL-CAP-0028 的 adjudication_blocked 同义。跨仓库证据解析的纪律"
                  "（必须引入新证据）由其状态驱动规则承接。UPSTREAM-06 无许可，不复制原文。",
        "license_note": "UPSTREAM-06 / copy_permitted=false",
    },
    {
        "identity": ["UPSTREAM-06", "C25"],
        "current_owner": "Storage",
        "direction": "NEW_CANONICAL",
        "target_canonical": None,
        "verdict": "REIMPLEMENT",
        "answers": {
            "A_covered": "**部分覆盖**。SL-CAP-0062 四层资产模型定义了「产物属于 D 层、不得回写权威层」，"
                         "但未定义「阶段产物一阶段一文件」的落地形态，也未定义「跳过阶段必须显式缺失而非空对象」这一完整性规则。"
                         "SL-CAP-0071 属 DSH-Adapter，是任务级检查点语义，不是产物模型。",
            "B_counterexample": "否。",
            "C_independent": "**是**。它定义的是「阶段产物集合的完整性投影」：哪些阶段跑过、哪些没跑、没跑的如何显式表示。"
                             "这是 SL-CAP-0062 的四层分类与 0064 的原子写入都不回答的问题。",
            "D_owner_correct": "是。Storage（F1-C-A 已裁决，本批不重议）。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "**copy_permitted=false**。只借「一阶段一产物、跳过显式缺失」的抽象结构，"
                                "不复制其模板、脚本或 JSON 格式。",
        },
        "reason": "F1-C-B 的承接形态裁决：不并入 SL-CAP-0062（0062 讲四层读写权限与单一权威，插入「阶段完整性」会混淆两个维度），"
                  "也不并入 0064（0064 讲单次写入的原子性，不回答「整个 run 的产物集合是否完整」）。"
                  "新建一条，专讲「阶段产物完整性投影」，作为 SL-CAP-0062 D 层的一个具体子契约。",
        "license_note": "UPSTREAM-06 / copy_permitted=false",
        "new_canonical_def": {
            "id": "SL-CAP-0074",
            "name": "阶段产物完整性投影（跳过阶段显式缺失，禁止空对象冒充已完成）",
            "description": (
                "一次分析运行的产物是一组按阶段划分的记录，而非单一报告。三条硬规则：\n"
                "S-1 一阶段一产物：每个阶段各自落地自己的记录（阶段标识、输入快照引用、产出内容、状态），"
                "报告层只做聚合与引用，不复制阶段内容。\n"
                "S-2 跳过阶段必须显式缺失：某阶段未执行时，产物集合中该阶段记为 skipped 并附原因，"
                "**不得写入空对象、空数组或占位默认值**。空对象与「已执行但无产出」在设计上不可区分，"
                "是完整性失真的直接来源。\n"
                "S-3 完整性投影可机械判定：给定产物集合与预期阶段清单，必须能判定「哪些跑了、哪些跳了、"
                "哪些失败了」，且三种状态的判定不依赖读取产物内容之外的信息。\n"
                "硬规则一：本契约只定义产物集合的完整性，**不定义任何证据是否足以支撑结论**——"
                "那归 Evidence-Claims（SL-CAP-0028）。它不是第二套状态机。\n"
                "硬规则二：阶段产物属 SL-CAP-0062 的 D 层（展示产物）或 A 层（若为不可变记录），"
                "具体归层由该产物是否可重建决定；无论如何归属，都不得回写权威层。\n"
                "硬规则三：与 SL-CAP-0071（DSH-Adapter 的任务级检查点）是不同粒度：0071 管「任务中断后从哪续跑」，"
                "本条管「这次运行的产物集合是否完整」。两者可互引，不得互相替代。"
            ),
            "owner_module": "Storage",
            "dependencies": ["Storage", "DSH-Adapter", "Evidence-Claims"],
            "v1_scope": "V1_REQUIRED",
            "input_boundary": ["一次运行的阶段清单（expected_stages）", "各阶段落地的产物记录"],
            "output_boundary": [
                "stage_product{stage_id, status: executed|skipped|failed, reason?, output_ref}",
                "completeness_projection{expected[], executed[], skipped[], failed[], complete: bool}",
            ],
            "unresolved": [
                "阶段清单由谁定义（固定枚举 vs 运行时注册）待 F2",
                "skipped 与 failed 是否需要在产物集合外另行告警待 F1-C",
                "与 SL-CAP-0071 检查点的物理共存方式待 F2",
            ],
            "merge_note": (
                "本条由 F1-C-B 新建，承接 ROUTED 身份 UPSTREAM-06::C25。"
                "F1-C-A 已裁决其 owner=Storage（依据 mechanism 逐字：阶段各写 JSON、报告层聚合、跳过阶段显式缺失）；"
                "本批裁决其承接形态为**新建**而非并入 SL-CAP-0062，理由是 0062 讲四层读写权限、"
                "本条讲阶段集合完整性，两个维度不同，合并会混淆。"
                "UPSTREAM-06 无复制许可，本条为自建契约，未复制其模板与 JSON 格式。"
            ),
        },
    },
    {
        "identity": ["UPSTREAM-04", "C16"],
        "current_owner": "Lifecycle",
        "direction": "DEFER_WITH_REASON",
        "target_canonical": None,
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "**未覆盖**。SL-CAP-0043 讲「变更怎么分类与调度」，SL-CAP-0044 讲「影响面两条路径」，"
                         "都不回答「一次具体任务的完成判据是什么」。",
            "B_counterexample": "否。",
            "C_independent": "**是**——但它不是「知识生命周期」问题，是**运行时任务完成判定**问题。",
            "D_owner_correct": "**否**。分流把它判给 Lifecycle 是误判：Lifecycle 管知识的失效与重验，"
                               "而「三处 Completion Check」管的是「这次分析任务算不算做完」。后者属 DSH-Adapter 的运行编排。",
            "E_reject_or_defer": "**DEFER**。原因见下：owner 存疑，且与 DSH-Adapter 的 SL-CAP-0071（任务状态）重叠，"
                                 "需在 F1-C-C 重新裁决 owner 后再定承接形态。",
            "F_copy_permitted": "MIT，可复制。",
        },
        "reason": "分流记录写的是「完成检查是「任务何时算完成」的判定，属 Lifecycle 的变更调度与调度完成语义」。"
                  "但 Lifecycle 的 canonical（0040–0045）没有一条定义「任务完成判据」——"
                  "0043 的「调度必须可恢复与幂等」讲的是调度动作，不是完成判据。"
                  "而 DSH-Adapter 的 SL-CAP-0071 恰恰定义了任务级状态与检查点。"
                  "本批不擅自改 owner（F1-C-A 的教训），改为 DEFER 并在 F1-C 登记表标注 owner 存疑，交 F1-C-C 裁决。",
        "license_note": "MIT / copy_permitted=true",
        "defer_condition": {
            "blocked_by": "owner 待 F1-C-C 重裁",
            "proposed_owner_if_reopened": "DSH-Adapter",
            "trigger": "F1-C-C 裁决 owner 后，若归 DSH-Adapter 则补入 SL-CAP-0071 的完成判据；若保持 Lifecycle 则需新建",
        },
    },
    {
        "identity": ["UPSTREAM-05", "C10"],
        "current_owner": "Lifecycle",
        "direction": "DEFER_WITH_REASON",
        "target_canonical": None,
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "**未覆盖**。与 U04-C16 同类：SL-CAP-0043/0044 不回答「写入后必须满足什么」。",
            "B_counterexample": "否。",
            "C_independent": "**是**——「写盘后必须满足的硬条件」是可判定的后置条件，"
                             "但更接近 Storage 的 SL-CAP-0064（写入五步契约）而非 Lifecycle。",
            "D_owner_correct": "**否**。分流写「归 Lifecycle 的增量调度与 Storage 的写入校验」——"
                               "一句话指两个 owner，本身就不合规（一个身份只能一个 owner）。",
            "E_reject_or_defer": "**DEFER**。同 U04-C16，owner 必须先在 F1-C-C 定夺。",
            "F_copy_permitted": "Apache-2.0，可复制。",
        },
        "reason": "分流理由自相矛盾：同时指向 Lifecycle 与 Storage，违反「一个身份一个 owner」。"
                  "从内容看，「写盘后必须满足的硬条件」与 SL-CAP-0064 的 W-2（校验结构完整性与引用完整性）最接近，"
                  "但 0064 讲的是单次写入的五步，不是通用后置条件集合。本批不裁 owner，DEFER 交 F1-C-C。",
        "license_note": "Apache-2.0 / copy_permitted=true",
        "defer_condition": {
            "blocked_by": "分流记录本身含双 owner，需 F1-C-C 先定唯一 owner",
            "proposed_owner_if_reopened": "Storage（依次于 SL-CAP-0064 扩展）",
            "trigger": "F1-C-C 定 owner 后，若归 Storage 则作为 0064 的 W-2 扩展；若归 Lifecycle 则需新建",
        },
    },
    {
        "identity": ["UPSTREAM-05", "C14"],
        "current_owner": "Renderer",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0060",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "**部分覆盖**。SL-CAP-0060 定义了「元信息如何忠实呈现」，但未列版本页脚的具体字段集。"
                         "该身份的价值是字段清单（last_updated/commit/updated_by/review_status 等七项）。",
            "B_counterexample": "否。",
            "C_independent": "否——字段清单属 SL-CAP-0060 的呈现细则，不是独立能力。",
            "D_owner_correct": "是。Renderer。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "Apache-2.0，可复制。",
        },
        "reason": "上游该能力有价值的部分是七字段清单，但其 `commit` 存短 SHA、粒度不足以定位内容变化（审计原文）。"
                  "SourceLore 借字段名，值换成 content_hash——这正好落在 SL-CAP-0060「忠诚呈现确认等级与限制」与 "
                  "SL-CAP-0063「内容身份用 content_hash」的交界。本批登记为 SL-CAP-0060 的呈现细则补充。",
        "license_note": "Apache-2.0 / copy_permitted=true",
        "canonical_amendment": {
            "target": "SL-CAP-0060",
            "append_note": "补充呈现细则（F1-C-B 由 U05-C14 引入）：版本页脚至少含 last_updated、"
                           "content_hash、updated_by、review_status、source_snapshot、generated_at、generator_version 七项；"
                           "其中定位内容变化的字段必须是 content_hash，不得用短 commit SHA（粒度不足）。",
        },
    },
    {
        "identity": ["UPSTREAM-05", "C19"],
        "current_owner": "Evidence-Claims",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0028",
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "覆盖。SL-CAP-0028 的「状态不得由作者自评决定」与人机权限分离，正是该身份要求的"
                         "「人写的字段带签名、AI 写入直接拒绝」的语义。",
            "B_counterexample": "否。",
            "C_independent": "否。",
            "D_owner_correct": "是。EC（与 Security 的 SL-CAP-0053 协同）。",
            "E_reject_or_defer": "不需要。",
            "F_copy_permitted": "Apache-2.0，可复制。",
        },
        "reason": "「人类主导的语义补充」本质是「谁有权写哪个字段」。SL-CAP-0028 已有状态机与人工确认分支，"
                  "本批将其登记为该状态机的字段级约束，与 U05-C04 的补充约束合并论述（同属人机权限分离）。",
        "license_note": "Apache-2.0 / copy_permitted=true",
        "canonical_amendment": {
            "target": "SL-CAP-0028",
            "append_note": "补充字段级约束（F1-C-B 由 U05-C19 引入）：被标记为 human_authored 的字段，"
                           "AI 写入必须被拒绝（不是警告）；人写字段带签名，签名验证失败即拒绝写入。",
        },
    },
    {
        "identity": ["UPSTREAM-01", "C12"],
        "current_owner": "Evidence-Claims",
        "direction": "DEFER_WITH_REASON",
        "target_canonical": None,
        "verdict": "ADAPT",
        "answers": {
            "A_covered": "**部分覆盖**。SL-CAP-0028 讲「结论状态如何判定」，但 Eval Baseline 讲的是"
                         "「评测方法本身怎么建」——gold 集、确定性指标、judge。这是流程层，不是结论层。",
            "B_counterexample": "否。",
            "C_independent": "**是**——评测基线是一套独立的方法学，与 claim 状态机不同粒度。",
            "D_owner_correct": "**存疑**。分流把它判给 EC，理由是「核心是质量如何判定」；"
                               "但 DSH-Adapter 批次反向把它判给了 EC（作为外推）。两批都指向 EC，"
                               "然而 EC 的 canonical 里没有任何一条覆盖「评测集构建」。",
            "E_reject_or_defer": "**DEFER**。它是**方法学资产**（如何建评测），不是运行时能力；"
                                 "且涉及付费 API 与多模型 judge 的边界（U01-C13/C14 已 REJECT）。交 F1-C-C 定夺。",
            "F_copy_permitted": "MIT，可复制。",
        },
        "reason": "该身份在两批中都被推向 EC，但 EC 无对应 canonical——说明「指向 EC」本身是悬空的。"
                  "其内容（gold + 确定性指标 + judge）是评测方法论，与 SL-CAP-0028 的结论状态机不是一个层次。"
                  "且审计原文已指出 judge「依赖外部 provider 需替换」、click 案例 F1=0.00「不可作单一门槛」，"
                  "涉及被 REJECT 的 U01-C13/C14 边界。本批 DEFER，交 F1-C-C 决定是新建方法学 canonical 还是明确拒绝。",
        "license_note": "MIT / copy_permitted=true",
        "defer_condition": {
            "blocked_by": "EC 无对应 canonical；且与被 REJECT 的多模型 judge 边界相交",
            "proposed_owner_if_reopened": "新建独立方法学 canonical（owner 待定，EC 或 Research）",
            "trigger": "F1-C-C 裁定「评测方法学是否需要独立 canonical」后处理",
        },
    },
]

# ── 前置勘误（第 2 节） ─────────────────────────────────────────────────
ERRATA = [
    {
        "errata_id": "F1C-B-E01",
        "subject": "ROUTED 分布数字 14 与真实 11 的差异",
        "claim_previous": "F1-C-A 汇报的模块分布写作 EC 5 + Lifecycle 4 + Renderer 4 + Storage 1 = 14",
        "truth": "真实集合是 11 条（EC 7 + Lifecycle 2 + Renderer 1 + Storage 1），与 Routed 总数 11 一致。",
        "root_cause": (
            "数字来源错误，不是数据错误。`docs/fusion/F1C_REMAINDER_BASELINE.json` 里记录的分布是正确的"
            "（EC 7 / Lifecycle 2 / Renderer 1 / Storage 1，合计 11，可由该文件的 routed_by_module 逐个数出）。"
            "F1-C-A 的最终汇报把 14 这四个子数字抄错了（四个数字互不相关地拼成了 14），"
            "而 14 恰好是 F1-B 早期某一时点的历史 ROUTED 峰值（Facts/Collector 统计修订后的一段时间内曾是 14），"
            "属记忆串扰。"
        ),
        "recomputable": (
            "python3 tools/fusion/f1c_b_routed_audit.py —— 从草稿的 cross_module_redirections 逐条枚举，"
            "按 owner_module 计数，输出必须与 11 及 7/2/1/1 完全相符。"
        ),
        "verdict": "数据文件正确，汇报数字有误。不修正任何数据文件，只记录勘误。",
        "fixed": False,
        "note": "按用户第 2 节要求：真实集合是 11，未触发应用阶段停止条件。",
    },
    {
        "errata_id": "F1C-B-E02",
        "subject": "SL-CAP-0071 的模块归属引用错误",
        "claim_previous": (
            "F1-C-A 的裁决文档与登记表把 SL-CAP-0071 写作「Storage 的 SL-CAP-0071」，"
            "原文：与 Storage 的 SL-CAP-0071 的「工具成功与模型生成成功分开记录」同族"
        ),
        "truth": (
            "SL-CAP-0071 的真实 owner 是 **DSH-Adapter**（name: 任务执行状态、检查点与幂等调用）。"
            "Storage 的四条相关 canonical 是 SL-CAP-0062（四层资产模型）、SL-CAP-0063（身份层级与版本标识）、"
            "SL-CAP-0064（原子写入、乐观并发与崩溃恢复）、SL-CAP-0065（可重建派生索引与跨会话查询）。"
        ),
        "root_cause": (
            "F1-C-A 论证 U06-C25「跳过阶段显式缺失而非空对象」时，把「用空值冒充已完成」类比到"
            "「工具执行成功与模型生成成功分开记录」。后者的真实编号是 SL-CAP-0071，但 owner 是 DSH-Adapter，"
            "不是 Storage。引用时把「Storage」与「SL-CAP-0071」错误地连在了一起。"
        ),
        "recomputable": (
            "python3 -c \"import json;d=json.load(open('docs/fusion/CAPABILITY_CROSSWALK.draft.json'));"
            "print([ (c['canonical_id'],c['owner_module']) for c in d['canonical_capabilities'] "
            "if c['canonical_id'] in ('SL-CAP-0071','SL-CAP-0062','SL-CAP-0063','SL-CAP-0064','SL-CAP-0065') ])\""
        ),
        "verdict": (
            "**语义裁决不变**（U06-C25 → Storage 依然成立）。只修正引用："
            "Storage 侧真正支撑「完整性约束」的是 SL-CAP-0062（D 层不得回写权威层）；"
            "SL-CAP-0071 是 DSH-Adapter 的任务级检查点语义，cross-module 依赖，不得当作 Storage 的能力举证。"
            "本批已在 F1C_DECISION_REGISTER.json 的 F1C-A-001 记录中写入勘误指针。"
        ),
        "fixed": True,
        "fix_location": "docs/fusion/F1C_DECISION_REGISTER.json → decisions[F1C-A-001].errata_applied",
    },
]
