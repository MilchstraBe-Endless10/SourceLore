#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / DSH-Adapter 模块：canonical 定义（F1-B 最后一批）。

导出符号：
    MODULE                    "DSH-Adapter"
    FIRST_ID                  "SL-CAP-0068"
    CANON                     6 条 canonical（0068–0073）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的身份（本批 1 条）
    CONSUMED_THIS_BATCH       本批正式承接的 7 个身份（1 条 ROUTED + 6 条未审直采）
"""

MODULE = "DSH-Adapter"
FIRST_ID = "SL-CAP-0068"

CANON = [
    {
        "id": "SL-CAP-0068",
        "name": "Skill 入口与渐进加载契约（入口薄、能力按需读）",
        "description": (
            "SourceLore Skill 的入口只有一个薄文件：YAML frontmatter（name + description 触发语）+ "
            "Markdown 正文，只承载「何时用、先做什么、去哪里读细节」三件事。"
            "具体模块约束、字段契约、检查清单一律放在按需加载的独立文件中，"
            "由入口按当前任务指向对应文件，**不把全部 canonical 约束复制进入口提示词**。"
            "已核实的运行时事实（只读调查结果）：\n"
            "V-1 Skill 由 `<root>/<name>/SKILL.md` 承载，frontmatter 的 name 与 description 决定发现与触发。\n"
            "V-2 同目录可放多个 Markdown 子文件（如 omarchy skill 的 capture.md / hyprland.md / theming.md），"
            "构成渐进加载的天然载体。\n"
            "V-3 项目内 `skills/sourcelore/` 目前是空目录——**尚未实现**，本批只定契约不建 Skill。\n"
            "硬规则一：四类内容不可互相替代——给模型读的说明、给程序校验的结构化契约、"
            "给运行时调用的工具接口、需要人类审批的操作，各有独立载体。"
            "硬规则二：入口文件的行数应随模块数量线性增长而非乘积增长：只增「读哪个文件」，不增「读什么内容」。"
            "硬规则三：Skill 文档不得要求自主安装未知脚本；不得通过提示词覆盖系统级安全约束。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["skill_entry_payload", "task_kind"],
        "outputs": [
            "skill_entry{frontmatter{name, description}, body_sections[], load_pointers[]}",
            "load_pointer{module, file, when}",
            "runtime_capability_claim{capability, status: verified|UNVERIFIED_RUNTIME_CAPABILITY}",
        ],
        "depends_on_modules": [],
        "overlaps": (
            "与 EC 的 SL-CAP-0025（产物自证出处）无关：那条管生成产物，本条管 Skill 入口结构。"
            "与 Renderer 的 SL-CAP-0055（视图契约）分界：本条面向「模型读什么」，0055 面向「人读什么」"
        ),
        "unresolved": [
            "Skill 的正式目录与命名约定待 F2；本批只定「入口薄 + 按需加载」结构",
            "description 触发语的写法规范（何时触发、何时不触发）待 F2",
            "BotHarness 对 Skill 的发现是否与 DSH 完全一致，未经实测，标 UNVERIFIED_RUNTIME_CAPABILITY",
        ],
        "refs": [("UPSTREAM-01", "C11", "ADAPT")],
        "notes": (
            "U01-C11 判 ADAPT：上游把 prompt 资产当 markdown 知识组织，方向正确，"
            "但它没有「入口薄、能力按需读」的约束——上游倾向于把说明堆进单一文件。"
            "本条把该取向收紧为结构的硬规则：入口只放路由指针，约束下沉到独立文件。"
            "运行时事实 V-1/V-2 来自本机只读调查（~/.agents/skills/omarchy 的实际结构），"
            "V-3 是本项目的真实状态（skills/sourcelore 为空）。"
            "未实测的部分一律标 UNVERIFIED_RUNTIME_CAPABILITY，不写成平台现有功能。"
        ),
    },
    {
        "id": "SL-CAP-0069",
        "name": "模型适配接口与确定性/模型辅助边界",
        "description": (
            "模型调用必须经由单一适配接口，接口契约不绑定任何具体模型或供应商："
            "输入 {system_prompt, task_context, tools_allowed, budget}，"
            "输出 {text, tool_calls[], usage, finish_reason}。"
            "**核心事实与知识存储契约不依赖模型能力**——更换模型只改变「谁来解释」，"
            "不改变「解释什么、存成什么形状」。\n"
            "三类操作的边界必须显式：\n"
            "D-1 必须确定性执行：哈希计算、路径解析、集合运算、结构校验——不经模型。\n"
            "D-2 允许模型辅助分析：语义解释、产品含义推断、研究结论——必须标 claim_type。\n"
            "D-3 必须交 Evidence-Claims 校验：任何被当作结论输出的主张。\n"
            "硬规则一：能力要求必须来自实际运行时验证，不得默认所有模型都有视觉、工具调用或结构化输出。"
            "未知能力一律标 UNVERIFIED_RUNTIME_CAPABILITY。\n"
            "硬规则二：模型输出格式错误只允许有界修复（见 SL-CAP-0070），且修复失败必须报错而非降级为猜测。\n"
            "硬规则三：不得因更换模型而重写已有 canonical 的事实或存储契约。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["adapter_request{system_prompt, task_context, tools_allowed, budget}",
                   "model_capability_profile{verified[], unverified[]}"],
        "outputs": [
            "adapter_response{text, tool_calls[], usage, finish_reason}",
            "operation_class{operation, class: deterministic|model_assisted|requires_ec}",
            "capability_gap{capability, status: UNVERIFIED_RUNTIME_CAPABILITY}",
        ],
        "depends_on_modules": ["Evidence-Claims", "Facts"],
        "overlaps": (
            "与 Facts 的 SL-CAP-0001（确定性事实抽取）分界：0001 说「抽取必须零模型」，"
            "本条说「调用层怎么把确定性操作与模型操作分开」。与 EC 的 SL-CAP-0023 分界："
            "0023 管 claim 措辞，本条管操作分类"
        ),
        "unresolved": [
            "适配接口的具体形态（命令行 / 库函数 / MCP 工具）待 F2",
            "当前模型的能力画像（是否支持结构化输出、工具调用）未经实测，标 UNVERIFIED",
            "多模型并存时的选择策略待 F1-C",
        ],
        "refs": [("UPSTREAM-01", "C06", "REUSE")],
        "notes": (
            "U01-C06 判 REUSE：上游用 Protocol 把 LLM provider 解耦，是本轮少见可直接沿用的设计——"
            "接口与实现分离，换供应商不改调用方。本条沿用该结构，并补上 SourceLore 需要的"
            "「三类操作边界」与「能力必须实测」两条约束（上游没有）。"
            "注意：解耦的是**适配层**，不是把 REJECT 的直连外部 API 重新引入（见 SL-CAP-0070 的反例登记）。"
        ),
    },
    {
        "id": "SL-CAP-0070",
        "name": "调用预算、有界修复与成本核算（估算与实测分离）",
        "description": (
            "每次模型调用必须声明预算并在超限时安全停止，禁止无界循环。"
            "预算三件：max_calls（调用次数上限）、max_context（单次上下文上限）、max_repairs（修复次数上限，"
            "**硬上限 2 次，且不得自增**）。\n"
            "有界修复：输出格式校验失败时允许至多 2 次重试，每次必须携带「上一次错在哪」的具体反馈；"
            "2 次仍失败即报错终止，**不得降级为猜测、不得跳过校验**。禁止 while(true) 式修复循环。\n"
            "成本四类必须分列，不得混为一谈：\n"
            "C-1 measured_tokens——运行时实际获得的 token 用量（有则记）。\n"
            "C-2 billed_cost——供应商返回的计费信息（有则记）。\n"
            "C-3 estimated_tokens——本地按字数估算（可用的近似值，**不是账单**）。\n"
            "C-4 unavailable_cost——无法取得的成本信息（必须显式登记，不得省略）。\n"
            "硬规则一：**不得把估算值描述为供应商实测账单**。estimated_tokens 与 billed_cost 是不同字段。\n"
            "硬规则二：预算耗尽后必须保留可恢复检查点（见 SL-CAP-0071），不得丢弃已完成的有效产物。\n"
            "硬规则三：工具执行耗时与模型调用耗时分别记录——两者是不同的成本来源。\n"
            "明确拒绝继承：上游的「直连外部模型 API」（自建 client、自带 token 通道）与"
            "「多模型 judge 集成」——后者需要多个付费 API 且无校准依据。"
            "本条只保留「成本必须可观测」的取向。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["budget{max_calls, max_context, max_repairs}", "call_record{model, tokens, duration}"],
        "outputs": [
            "budget_state{used_calls, used_context, repairs_done, exhausted: bool}",
            "repair_attempt{attempt_no, prior_error, outcome}",
            "cost_record{measured_tokens?, billed_cost?, estimated_tokens?, unavailable_cost?, "
            "tool_duration_ms, model_duration_ms}",
        ],
        "depends_on_modules": [],
        "overlaps": (
            "与 Lifecycle 的 SL-CAP-0043 分界：0043 管「知识该不该重做」，本条管「这次调用花了多少、够不够」。"
            "与 DSH Adapter 自身的 SL-CAP-0071 是配合关系：预算耗尽产出恢复检查点"
        ),
        "unresolved": [
            "max_context 的具体数值待 F2（按模型窗口定）",
            "estimated_tokens 的估算方法（字数比 vs tokenizer）待 F2",
            "工具耗时的采集粒度（单工具 vs 阶段）待 F2",
        ],
        "refs": [
            ("UPSTREAM-01", "C07", "ADAPT"),
            ("UPSTREAM-06", "C18", "ADAPT"),
            ("UPSTREAM-01", "C13", "REJECT"),
            ("UPSTREAM-01", "C14", "REJECT"),
        ],
        "notes": (
            "合并依据：U01-C07（单次推理 + 有界修复）给「怎么限制调用次数」，"
            "U06-C18（运行成本与可观测性）给「怎么记录花了多少」——两者是同一预算体系的两面："
            "一面限制、一面记账。拆开会出现「限制了但不知道花了多少」或反之。"
            "U01-C07 判 ADAPT：上游的有界修复取向正确，但未规定次数上限与失败后的确定行为。"
            "U06-C18 判 ADAPT：上游把运行代价做成可比较的结构字段，方向对；"
            "但纯 chars/4 估算、无独立核验（审计 D15），SourceLore 只能当自报值——"
            "这正是本条要把 estimated_tokens 与 billed_cost 分成两个字段的原因。"
            "U01-C13（直连外部 LLM API 客户端）与 U01-C14（多模型 judge 集成）判 REJECT 并登记为本条反例——"
            "它们是本批唯一的两处 REJECT，用来约束「不得通过重命名把被拒方案重新引入」。"
            "U06-C18 该身份来自 Security 批次的改路由分流，本批建 canonical 正式承接。"
        ),
    },
    {
        "id": "SL-CAP-0071",
        "name": "任务执行状态、检查点与幂等调用",
        "description": (
            "每个任务携带一组逻辑标识，用于恢复与幂等判定："
            "task_id、run_id、workspace_id、subject_id、requested_action、current_stage、"
            "checkpoint_ref、input_snapshot_ref、authorization_scope、attempt_count、error_category。"
            "（逻辑字段候选，Schema 留 F2。）\n"
            "四条硬规则：\n"
            "I-1 同一任务恢复时不得重复提交已成功的知识写入——幂等依据是 checkpoint_ref 记录了"
            "「哪些写入已确认提交」，而不是「上次好像成功了」。\n"
            "I-2 工具执行成功与模型生成成功必须分开记录：模型说「我完成了」不构成执行证据。\n"
            "I-3 超时不得自动解释为工具未执行——超时可能是执行成功但回传失败，必须按 unknown 处理并核对。\n"
            "I-4 重试必须有明确的幂等依据（checkpoint 或内容哈希），无依据的重试等于重复写入。\n"
            "权威分离（硬规则五）："
            "**Storage 是知识资产权威；执行检查点是任务恢复依据；模型上下文或热记忆只是辅助检索，"
            "不是唯一事实来源。** 不得把记忆系统的检索命中当作当前任务状态的权威依据。"
            "需要人工批准的操作不能由 Agent 自批（见 SL-CAP-0072）。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["task_context{task_id, run_id, workspace_id, subject_id}", "checkpoint_ref"],
        "outputs": [
            "task_state{current_stage, attempt_count, error_category, checkpoint_ref}",
            "commit_ledger{committed_writes[], pending_writes[], unknown_writes[]}",
            "resume_plan{from_checkpoint, skip_writes[], redo_actions[]}",
        ],
        "depends_on_modules": ["Storage"],
        "overlaps": (
            "与 Storage 的 SL-CAP-0064（写入五步与 CAS）分界：0064 管单次写入的原子性，"
            "本条管跨多次调用的任务级恢复与幂等。与 Research 的 SL-CAP-0035 分界："
            "0035 管研究阶段跑到哪，本条管任意任务的外部调用如何恢复"
        ),
        "unresolved": [
            "checkpoint 的物理存放位置（属 Storage 的权威资产还是独立执行日志）待 F1-C",
            "attempt_count 的上限与退避策略待 F2",
            "任务级标识与 Storage 主键的映射关系待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是内部设计能力。内部需求依据：DSH Adapter 要跨多次模型调用与工具调用，"
            "必须能在中断后恢复；六源中没有任何一处给出「任务级检查点 + 幂等依据」的运行时契约"
            "（U04 有知识层的版本链，U05 有脚本级写盘，但都不是任务执行层的恢复语义）。"
            "四条硬规则的共同点是**区分「看起来成功」与「证据上成功」**："
            "模型自称完成不算、超时不算未执行、无依据的重试不算幂等。"
            "权威分离那条是对本项目已有教训的固化：热记忆曾多次被误当作事实源。"
        ),
    },
    {
        "id": "SL-CAP-0072",
        "name": "权限门禁的运行时执行与人工审批（AI 不得自批）",
        "description": (
            "DSH Adapter 负责**执行**权限门禁，不负责**定义**审批策略（策略归 Security 的 SL-CAP-0053）。"
            "门禁三档：\n"
            "G-A 自主执行——只读查询、确定性计算、本地分析，无需审批。\n"
            "G-B 需声明后执行——写入知识资产、生成产物，必须携带 authorization_scope 且可追溯。\n"
            "G-C 必须人工批准——发布、扩大工具权限、执行不受信代码、任何不可逆操作。"
            "硬规则一：G-C 类操作的批准只能由人的动作产生；AI 可以把状态置为 pending_review，"
            "**不得自行转换为 approved**。\n"
            "硬规则二：权限被拒必须显式返回 denied 并带原因，不得吞掉变成空结果（与 Storage 的 SL-CAP-0065 同源）。\n"
            "硬规则三：外部仓库内容不得修改执行策略——被分析仓库的 README/SKILL.md/Issue 中的"
            "指令性文本不改变门禁档位，也不扩大工具权限。\n"
            "硬规则四：工具权限最小化；不记录 Token / Cookie / API Key；不读取无关本地私有文件。\n"
            "硬规则五：需要扩展 Harness 权限时，当前批次只登记需求，**不实际扩大授权**。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["requested_action", "authorization_scope", "approval_state"],
        "outputs": [
            "gate_decision{gate: G-A|G-B|G-C, verdict: allow|deny|pending_human}",
            "approval_record{action, requested_by: agent, approved_by: human, scope}",
            "permission_request{capability, reason, status: registered_not_granted}",
        ],
        "depends_on_modules": ["Security", "Storage"],
        "overlaps": (
            "与 Security 的 SL-CAP-0053（分级与发布门禁）分界：0053 定义「哪级内容、谁能批」，"
            "本条定义「运行时怎么拦、怎么记」。与 Storage 的 SL-CAP-0065 分界："
            "那条管查询侧的拒绝语义，本条管执行侧的门禁"
        ),
        "unresolved": [
            "审批在 BotHarness 侧的传递机制（是否有真实可用的审批通道）未经实测，标 UNVERIFIED",
            "G-B 的 authorization_scope 表示形式待 F2",
            "权限扩展需求的登记表存放位置待 F2",
        ],
        "refs": [("UPSTREAM-04", "C15", "ADAPT")],
        "notes": (
            "U04-C15 判 ADAPT：上游的「自主权分级（可自主 vs 须先问）」方向正确，"
            "但只是散文描述、无运行时拦截机制。本条把它落成 G-A/G-B/G-C 三档门禁 + 显式拒绝 + 审批留痕。"
            "关键区分：**审批策略归 Security，执行归本条**——这与用户第 2 节的提示一致"
            "（U04-C15 的审批策略属于 Security，DSH Adapter 负责执行权限门禁）。"
            "BotHarness 侧是否有真实审批通道未经实测，标 UNVERIFIED_RUNTIME_CAPABILITY。"
        ),
    },
    {
        "id": "SL-CAP-0073",
        "name": "与九模块的能力编排接口（逻辑契约，不复制实现）",
        "description": (
            "DSH Adapter 对每个模块只定义**最小逻辑调用关系**，不复制其实现、不代其裁决：\n"
            "Collector——请求「某仓库某固定版本」的数据，不回传采集细节。\n"
            "Facts——请求确定性事实抽取，不掺模型判断。\n"
            "Evidence-Claims——提交 claim 候选与验证请求，**不由本模块判定真伪**。\n"
            "Product——请求产品语义分析，不代其推断业务含义。\n"
            "Research——委派有界研究计划，不代其定研究范围。\n"
            "Lifecycle——查询「某知识是否需要重新验证」，不自定失效。\n"
            "Security——查询安全约束与权限要求，不改其策略。\n"
            "Renderer——请求生成指定派生视图，不自造排版。\n"
            "Storage——查询、登记与提交权威资产。\n"
            "硬规则一：**禁止 DSH Adapter 绕过 Storage 直接改写知识资产目录**。\n"
            "硬规则二：错误必须原样向上传播并保留来源模块标识，"
            "不得把上游失败吞成空结果或改写成成功（与各模块的失败语义一致）。\n"
            "硬规则三：编排只决定「调谁、按什么顺序」，不决定「结论是什么」。\n"
            "硬规则四：不得把其他模块的全部功能复制进 Skill 提示词——能力通过调用获得，不通过描述获得。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["orchestration_plan{stages[], modules[]}", "module_request{module, payload}"],
        "outputs": [
            "orchestration_state{stage, module, status}",
            "module_response{module, payload, status: ok|failed|denied}",
            "error_propagation{origin_module, error_category, preserved: true}",
        ],
        "depends_on_modules": ["Collector", "Facts", "Evidence-Claims", "Product",
                               "Research", "Lifecycle", "Security", "Renderer", "Storage"],
        "overlaps": (
            "与 Research 的 SL-CAP-0035（研究阶段流水线）分界：0035 是研究内部的阶段，"
            "本条是「跨模块编排」的调度。与 Lifecycle 的 SL-CAP-0043 分界："
            "0043 决定知识动作序列，本条决定模块调用序列"
        ),
        "unresolved": [
            "调用形态（进程内函数 / 子进程 / MCP 工具）待 F2",
            "并行编排的可行性（哪些模块可并发）待 F1-C",
            "错误码在各模块间的统一表示待 F2",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是内部设计能力。内部需求依据：SourceLore 有九个职责模块，"
            "而六源中的任何一个都不是「多模块编排器」——它们要么是单脚本、要么是单提示词流水线。"
            "本条把九个模块的调用契约集中定义，并钉死两条最容易出事的边界："
            "**不绕过 Storage 改数据**、**不吞上游错误**。"
            "硬规则四是对「Skill 提示词膨胀」的直接防护：能力靠调用获得，不靠描述获得"
            "（与 SL-CAP-0068 的渐进加载互为表里）。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-01", "C12"): (
        "Evidence-Claims",
        "Eval Baseline（gold + 确定性指标 + judge）的核心是「质量如何判定」，"
        "其确定性指标与 judge 的裁决语义已由 EC 的 SL-CAP-0028（裁决状态机）与 SL-CAP-0034"
        "（可判定终止条件与置信度）覆盖；DSH Adapter 只记录评测运行的执行证据与成本，不定义质量判据",
    ),
}

CONSUMED_THIS_BATCH = {
    ("UPSTREAM-01", "C06"): ("SL-CAP-0069", "unreviewed_adopted"),
    ("UPSTREAM-01", "C07"): ("SL-CAP-0070", "unreviewed_adopted"),
    ("UPSTREAM-01", "C11"): ("SL-CAP-0068", "unreviewed_adopted"),
    ("UPSTREAM-01", "C13"): ("SL-CAP-0070", "unreviewed_adopted"),
    ("UPSTREAM-01", "C14"): ("SL-CAP-0070", "unreviewed_adopted"),
    ("UPSTREAM-04", "C15"): ("SL-CAP-0072", "unreviewed_adopted"),
    ("UPSTREAM-06", "C18"): ("SL-CAP-0070", "cross_module_redirections"),
}
