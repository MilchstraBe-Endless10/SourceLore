#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-C 阶段 1：3 项 DEFER 的归属与承接裁决（纯数据）。

这三项在 F1-C-B 被标为 DEFER，理由都是「owner 存疑 / 分流自相矛盾 / 指向悬空」。
本批逐个定夺，给出唯一 owner 与承接方式。

生效顺序：本模块的裁决**覆盖** f1c_routed_decisions 中对同一身份的 DEFER 行为。
"""

BATCH = "F1-C-C1"

DECISIONS = [
    # ── U04-C16 ────────────────────────────────────────────────────────
    {
        "identity": ["UPSTREAM-04", "C16"],
        "previous_owner": "Lifecycle",
        "previous_direction": "DEFER_WITH_REASON",
        "final_owner": "DSH-Adapter",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0071",
        "verdict": "ADAPT",
        "split_answers": {
            "checks_task_or_knowledge": (
                "**任务执行完成**。三处 where 分别是 external-probe.md L35（外部探测做完没）、"
                "repository-impact.md L30–L32（影响分析做完没）、SKILL.md L127（主流程阶段完成没）"
                "——全部是「这一步做完没有」，不涉及「这条知识还成不成立」。"
            ),
            "overlaps_with_0071": (
                "**不重合，但有 gap**。SL-CAP-0071 定义的是「状态怎么记、中断后怎么恢复」"
                "（current_stage、checkpoint_ref、I-1..I-5），**没有定义「什么算完成」**。"
                "记录状态 ≠ 判定退出条件。本条补的正是这个 gap。"
            ),
            "new_duty_vs_lifecycle": (
                "**不是 0040–0045 的职责**。0043 管「变更怎么分类、按什么顺序调度」，"
                "0044 管「影响面怎么找」，两者都讲动作序列，不讲「一次分析任务何时算做完」。"
                "Lifecycle 的视野是「知识随时间是否失效」，本条的视野是「这次运行是否收尾」。"
            ),
            "can_adopt_existing": (
                "**可以**。作为 SL-CAP-0071 的补充约束（amendment）而非新建卡——"
                "因为 0071 已经拥有了任务状态机的全部骨架，缺的只是退出判据这一条。"
            ),
        },
        "reason": (
            "分流当初判给 Lifecycle 是误判。Lifecycle 管知识失效与重验，"
            "而三处 Completion Check 检查的全是「某个执行阶段做完没有」。"
            "唯一的正确归属是拥有任务状态机的 DSH-Adapter。"
            "上游的四条散文要求（「确认已覆盖」「确认无遗漏」等）没有判据，"
            "必须翻译成可判定 gate，否则重蹈 D14（散文要求无判据）。"
        ),
        "amendment": {
            "target": "SL-CAP-0071",
            "append_note": (
                "补充退出判据（F1-C-C1 由 U04-C16 引入）：任务的每个阶段必须有**可机器判定的完成判据**，"
                "不得以「看起来做完了」收尾。三条最低要求：\n"
                "G-1 阶段完成必须有产出物或显式 skipped 记录（与 SL-CAP-0074 的完整性投影对齐）；\n"
                "G-2 完成判据不得由模型自评——模型声称完成不构成完成证据（承接 I-2）；\n"
                "G-3 判据本身必须可复算：给定同一输入与产出，任何执行者应得出相同结论。"
            ),
        },
        "interfaces": ["SL-CAP-0074（阶段产物完整性投影）", "SL-CAP-0064（写入提交）"],
        "unresolved": [
            "每个阶段的具体判据清单待 F2（本批只定「判据必须可判定且不可自评」这一层）",
            "G-1 与 SL-CAP-0074 的 skipped 记录如何共用同一份投影待 F2",
        ],
        "license_note": "MIT / copy_permitted=true（只借形态，未复制散文要求原文）",
    },
    # ── U05-C10 ────────────────────────────────────────────────────────
    {
        "identity": ["UPSTREAM-05", "C10"],
        "previous_owner": "Lifecycle",
        "previous_direction": "DEFER_WITH_REASON",
        "final_owner": "Storage",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0064",
        "verdict": "ADAPT",
        "split_answers": {
            "what_is_validated": (
                "**写盘后的产物本身**，不是任务状态、也不是知识有效性。"
                "机制原文：「写盘后必须满足的硬条件」——校验对象是落盘后的结构、引用、字段约束。"
            ),
            "who_defines_success": (
                "**Storage**。写入契约的语义（什么是合法落盘）归 Storage 的 SL-CAP-0064；"
                "具体 postcondition 条目来自产物类型所属模块（如 SL-CAP-0025 的溯源字段、"
                "SL-CAP-0074 的阶段完整性），Storage 只负责「按定义校验」。"
            ),
            "who_executes_validation": (
                "**Storage**（写入路径上执行）。下游模块定义条目，Storage 在提交点逐条核对。"
            ),
            "failure_behavior": (
                "**阻止提交**（对应 SL-CAP-0064 的 W-4 版本一致才提交）。"
                "不回滚已提交的历史对象（A 层只追加），也不触发重验证（那是 Lifecycle 的事）。"
                "失败即写回执 rejected 并列出未通过的条目。"
            ),
            "covered_by_existing": (
                "**部分覆盖，存在 gap**。SL-CAP-0064 的 W-2 是**写入前**校验（结构完整性与引用完整性），"
                "本条要求的是**写入后**校验（落盘结果是否满足该产物类型声明的硬条件）。"
                "写入前通过不等于写入后满足——中间还有写入本身可能引入的偏差。"
            ),
        },
        "reason": (
            "分流理由当初写「归 Lifecycle 的增量调度与 Storage 的写入校验」——**一句话指两个 owner，"
            "本身就不合规**，违反「一个身份一个 owner」。"
            "从校验对象看（写盘后的产物），这纯粹是 Storage 的写入契约；"
            "Lifecycle 的 0043 讲「该不该重做」，与「这次写对了没有」是不同问题。"
            "与 U04-C16 的分野：C16 判「任务做完没」（DSH-Adapter），C10 判「写对了没」（Storage）——"
            "两者是不同层的退出条件，不得混为一谈。"
        ),
        "amendment": {
            "target": "SL-CAP-0064",
            "append_note": (
                "补充写入后校验（F1-C-C1 由 U05-C10 引入）：W-2 是写入前校验，本条增加**写入后**校验步骤。\n"
                "W-2' 提交后、对外可见前，按该产物类型声明的 postcondition 逐条核对；"
                "任一条不满足即拒绝本次提交（写回执 rejected 并列出未通过条目），"
                "不得先提交再补救。\n"
                "硬规则：postcondition 条目必须具名且可逐条核对（上游原文的价值正在于此），"
                "「数据看起来没问题」不构成校验通过。"
                "写入前通过（W-2）不能替代写入后校验（W-2'）——中间写入本身可能引入偏差。"
            ),
        },
        "interfaces": ["SL-CAP-0025（产物自证出处）", "SL-CAP-0074（阶段完整性）", "SL-CAP-0071（任务状态）"],
        "unresolved": [
            "各产物类型的 postcondition 条目清单待 F2",
            "W-2' 与 W-4 的提交顺序（先校验后提交 vs 先提交后校验再可见）待 F2",
        ],
        "license_note": "Apache-2.0 / copy_permitted=true（借「具名 postcondition」形式，未复制条目原文）",
    },
    # ── U01-C12 ────────────────────────────────────────────────────────
    {
        "identity": ["UPSTREAM-01", "C12"],
        "previous_owner": "Evidence-Claims",
        "previous_direction": "DEFER_WITH_REASON",
        "final_owner": "Evidence-Claims",
        "direction": "NEW_CANONICAL",
        "target_canonical": None,
        "verdict": "ADAPT",
        "split_answers": {
            "A_eval_data_and_tasks": (
                "**纳入本新条**。gold 集（标准答案）+ 基准任务定义。可离线准备，零外部依赖。"
            ),
            "B_deterministic_metrics": (
                "**纳入本新条**。F1、精确匹配、召回等确定性指标，零成本可复算。"
                "审计原文已证实「确定性指标零成本可用」。"
            ),
            "C_model_judge": (
                "**明确排除于 V1**。judge 依赖外部 provider，与被 REJECT 的 U01-C13（直连外部 API）、"
                "U01-C14（多模型 judge）同一边界。**本条只登记为可选扩展点，V1 不实现。**"
                "审计原文亦记「click 案例 F1=0.00 说明不可作单一门槛」——即使有 judge 也不能单独定谳。"
            ),
            "D_quality_gate_and_report": (
                "**部分纳入**：本新条定义「怎么算过」，但**不定义「过了之后能否发布」**——"
                "发布授权归 Security 的 SL-CAP-0053、结论状态归 EC 的 SL-CAP-0028。"
                "门禁出口=（本条的指标阈值）→（EC 状态机）→（Security 发布门）。"
            ),
            "E_execution_scheduling_and_cost": (
                "**不归本新条**。已在 SL-CAP-0070（DSH-Adapter）覆盖："
                "预算三件、成本四类分列、有界修复。原 F1-B 的 DSH-Adapter 裁决原文即写明"
                "「DSH Adapter 只记录评测运行的执行证据与成本，不定义质量判据」——"
                "这句话已把 E 从本条的 owner 排除，同时把定义权留给判定方。"
            ),
        },
        "reason": (
            "两批都把它推向 EC 而 EC 无对应 canonical，说明「指向 EC」本身悬空。"
            "但复核后 EC 确实是最合适的 owner——理由不是路由惯性，而是**判定器的主人必须证明判定器准**："
            "EC 拥有裁决状态机（0028）、显式未知（0023）、四段结构（0026），"
            "那么「这个裁决器有多准」的校准责任自然归它。"
            "这不是「判定某条 claim 真假」，而是「判定这套判据本身是否可信」——层次不同，故需独立 canonical。"
            "**关键区分**：拒绝 U01-C13/C14 的付费 API 与多模型 judge，不等于拒绝离线基准评测。"
            "本条的 V1 只用 gold 集 + 确定性指标，完全离线、零外部依赖、可复算，"
            "与被 REJECT 的方案是两个东西。"
        ),
        "new_canonical_def": {
            "name": "离线评测基线与判据校准（拒绝付费 API 与多模型 judge）",
            "description": (
                "判定器本身必须可被检验。三条硬规则：\n"
                "E-1 基准可离线：评测集（gold 输入与标准答案）与确定性指标（精确匹配、召回、"
                "字段级命中率等）必须能在无外部依赖的情况下复算。**V1 不使用任何付费 API。**\n"
                "E-2 指标不得单独定谳：任何单一指标（含 F1）都不得作为「质量达标」的唯一门槛——"
                "上游 click 案例 F1=0.00 已证明单指标会误判。必须至少两类指标交叉，并报告各自数值。\n"
                "E-3 评测结果必须可追溯：每次评测产出 eval_record{基准集版本, 指标名与数值, "
                "被测判据版本, 运行快照}，缺任一项即判评测无效。\n"
                "边界声明（硬规则四）：\n"
                "本条**不定义**「结论真假」（归 SL-CAP-0028 裁决状态机）、"
                "**不定义**「能否发布」（归 SL-CAP-0053 发布门禁）、"
                "**不管**评测的执行调度与成本（归 SL-CAP-0070）。\n"
                "本条只回答「这套判据本身有多可信」，不回答「这一条结论对不对」。\n"
                "明确排除（硬规则五）：多模型 judge 集成与直连外部 LLM API **不在本能力范围内**——"
                "二者已在 U01-C13/C14 被 REJECT。judge 若将来引入，须重新立项并单独过许可与成本审查，"
                "不得借本条名义复活。"
            ),
            "owner_module": "Evidence-Claims",
            "spdx": "MIT",
            "copy_permitted": True,
            "dependencies": ["Evidence-Claims", "DSH-Adapter", "Product"],
            "v1_scope": "V1_REQUIRED",
            "input_boundary": ["benchmark_set{gold_inputs[], gold_expected[]}", "judge_criteria_version"],
            "output_boundary": [
                "eval_record{benchmark_version, metrics{name, value}, criteria_version, source_snapshot}",
                "metric_matrix{deterministic_metrics[], cross_checks[]}",
            ],
            "unresolved": [
                "基准集的构成与规模待 F2（本批只定「可离线复算」与「不得单指标定谳」两条）",
                "多指标交叉的具体组合与权重待 F2",
                "judge 若重新引入的许可与成本审查流程待 F1-C 后续或 F2",
            ],
            "merge_note": (
                "本条由 F1-C-C1 新建，承接 DEFER 身份 UPSTREAM-01::C12。"
                "F1-C-B 判 DEFER 的理由是「EC 无对应 canonical，指向悬空」——本批确认该 gap 真实存在，"
                "故新建而非强行并入 SL-CAP-0028（0028 讲单条 claim 的状态迁移，不讲判定器整体校准）。"
                "处置 ADAPT：借上游「gold + 确定性指标」的形态，明确剔除其 judge 实现（依赖外部 provider）。"
                "MIT 许可，可复制形态；但本条为自建契约，未复制其评测脚本与数据。"
            ),
        },
        "interfaces": ["SL-CAP-0028（状态机，被校准对象）", "SL-CAP-0070（执行与成本）", "SL-CAP-0001（Facts 产出作为评测输入）"],
        "unresolved": [
            "基准集的构成与规模待 F2",
            "多指标交叉的组合方式待 F2",
            "评测通过的阈值是否需人工确认待 F1-C 后续",
        ],
        "license_note": "MIT / copy_permitted=true（只用形态，不用其 judge 实现与数据）",
    },
]

# ── 历史记录：这三项在 F1-C-B 的 DEFER 裁决不删除，只标记已被本批解决 ──────────
SUPERSEDES = {
    ("UPSTREAM-04", "C16"): "F1-C-B 的 DEFER 成立（owner 误判于 Lifecycle），本批改判 DSH-Adapter",
    ("UPSTREAM-05", "C10"): "F1-C-B 的 DEFER 成立（分流含双 owner 不合规），本批定为 Storage 单 owner",
    ("UPSTREAM-01", "C12"): "F1-C-B 的 DEFER 成立（EC 无对应 canonical），本批新建 SL-CAP-0075 填补",
}
