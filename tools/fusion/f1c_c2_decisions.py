#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-C2：UPSTREAM-05 全部剩余 UNREVIEWED 身份终裁（纯数据）。

真实集合 10 项（非汇报稿里的 11）：
C07 C08 C12 C13 C15 C16 C21 C25 C27 C28
已在前批处理的 C04 C10 C14 C19 C18 C22 C23 C24 C26 不在本批。

方向：ADOPT_EXISTING（承接已有 canonical，可带 amendment）
      REJECT_WITH_REASON（明确拒绝，不改三态——保持 UNREVIEWED，等 F1-C-D）
"""

BATCH = "F1-C-C2"

DECISIONS = [
    {
        "identity": ["UPSTREAM-05", "C07"],
        "capability": "命令族与编号页集",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0040",
        "final_owner": "Lifecycle",
        "verdict": "ADAPT",
        "reason": (
            "上游 valuable 的部分只有一个：「可枚举优先于自由命名」。审计 why 明确写"
            "「页集本身绑死具体项目文档结构，SourceLore 不做项目文档生成，只需要它的"
            "『可枚举优先于自由命名』这一条」。这正好对应 SL-CAP-0040 的 Subject 身份命名——"
            "身份必须由确定性规则分配而非自由起名。20 个命令到 00–12 编号页的映射本身不采纳。"
        ),
        "amendment": {
            "target": "SL-CAP-0040",
            "append_note": (
                "补充命名原则（F1-C-C2 由 U05-C07 引入）：Subject 的命名空间必须**可枚举**——"
                "subject_key 由确定性规则生成并可在已知集合内穷举，不得由作者自由起名。"
                "理由：自由命名会让同一实体在不同批次得到不同键，破坏身份稳定性。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（只取「可枚举优先」原则，不复制其页集与命令表）",
        "interfaces": ["SL-CAP-0063（身份层级与版本标识）"],
        "unresolved": ["subject_key 的具体生成规则待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C08"],
        "capability": "Phase 0 三分路由",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0035",
        "final_owner": "Research",
        "verdict": "ADAPT",
        "reason": (
            "机制是「全量发现 / 快路径 / 仅输出」三类分流，分流依据是「要不要读仓库」。"
            "审计 why 判「与 SourceLore 的 research 成本分级同构」。SL-CAP-0035 的 R0–R4 已是"
            "带预算的有界阶段机，R1「只消费已有确定性产物、不发起采集」正是「快路径」的落点。"
            "把三分路由作为阶段入口的分流规则补入 0035，不借其具体命令。"
        ),
        "amendment": {
            "target": "SL-CAP-0035",
            "append_note": (
                "补充入口分流（F1-C-C2 由 U05-C08 引入）：进入 R0 前必须显式选择本次运行档位——"
                "full（需读仓库全量发现）/ fast（只消费既有确定性产物，等价于直接进 R1）/ "
                "output_only（知识已足够，只重生成产物，等价于直接进 R4）。"
                "档位必须记录在 research_scope 里，不得隐式选择。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（借骨架，不借命令）",
        "interfaces": ["SL-CAP-0043（增量调度）"],
        "unresolved": ["三档的判定阈值（何时该 full）待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C12"],
        "capability": "渐进式 AI 投喂",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0035",
        "final_owner": "Research",
        "verdict": "ADAPT",
        "reason": (
            "验明其真正解决的问题：**研究过程中的读取顺序**，不是模型上下文长度管理。"
            "机制是「三轮渐进阅读：概览→深潜→模块验收」，why 写「它的轮次划分（先全局后局部）"
            "可作为 research 任务的默认读取顺序参考」。这是 Research 阶段内部的读取策略，"
            "归 SL-CAP-0035 的 R1；**不新建第二套上下文加载机制**——"
            "上下文预算与按需加载已由 SL-CAP-0068（Skill 渐进加载）与 SL-CAP-0070（调用预算）覆盖。"
        ),
        "amendment": {
            "target": "SL-CAP-0035",
            "append_note": (
                "补充读取顺序（F1-C-C2 由 U05-C12 引入）：R1 内读必须按「概览→深潜→模块确认」三遍推进，"
                "不得一上来就逐文件深读。三遍的产物分别是：结构概览、缺口清单、模块级确认。"
                "该顺序管的是**读什么次序**，不管**上下文能装多少**——后者归 SL-CAP-0068/0070。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true",
        "interfaces": ["SL-CAP-0068（按需加载）", "SL-CAP-0070（调用预算）"],
        "unresolved": ["三遍之间是否允许回退到上一遍待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C13"],
        "capability": "C4 强制顺序",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0035",
        "final_owner": "Research",
        "verdict": "ADAPT",
        "reason": (
            "逐层区分：**C4 的合理部分是「从粗到细的阅读粒度定序」**，"
            "即先看 Context 层（系统与环境）、再看 Container（部署单元）、Component、最后 Code；"
            "这部分对应 SL-CAP-0035 的 R1 读取策略，采纳。"
            "**明确拒绝的是「强制所有仓库必须按 C4 四级产出」**——与该身份同源的强制输出机制"
            "已在 SL-CAP-0057 被拒绝（不得为凑图编造节点）。"
            "**不把 C4 变成 SourceLore 全局必执行规则**：结构层级只在关系证据充分时使用，"
            "证据不足时不补全、不输出。这与 SL-CAP-0057「无法可靠提取关系时不生成图表」同源。"
        ),
        "amendment": {
            "target": "SL-CAP-0035",
            "append_note": (
                "补充粒度降序（F1-C-C2 由 U05-C13 引入）：R1 的「概览」遍必须按粒度降序推进——"
                "系统边界 → 部署单元 → 组件 → 代码。"
                "**明确拒绝**：不得要求所有仓库都产出 C4 四级结构，也不得在关系证据不足时"
                "补全结构层级。结构层级属 SL-CAP-0057 的可选呈现，只在关系证据充分时才使用。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（只取粒度降序，拒绝强制 C4 产出）",
        "interfaces": ["SL-CAP-0057（可选图表，同源的强制输出拒绝）"],
        "unresolved": ["粒度层级的判定是否需人工确认待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C15"],
        "capability": "发布节奏绑定",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0043",
        "final_owner": "Lifecycle",
        "verdict": "ADAPT",
        "reason": (
            "机制是「文档更新挂到 release/PR 检查单」，指**变更触发的时机绑定**，"
            "why 写「把文档维护从『想起来才做』变成流程节点；freshness 巡检可挂到同样的触发点」。"
            "这不是 Renderer（不是文档生成）、不是 Security（不是发布审批）、"
            "也不是 DSH-Adapter（不是任务调度），而是 Lifecycle 的变更触发分类。"
            "关键区分：**Release 触发≠人工公开发布许可**——前者是「该重验了」，后者是 SL-CAP-0053 的权限门。"
        ),
        "amendment": {
            "target": "SL-CAP-0043",
            "append_note": (
                "补充触发点（F1-C-C2 由 U05-C15 引入）：变更事件除 commit 推进外，"
                "release 与 merge/PR 也是合法触发源，须纳入 change_event 采集。"
                "硬规则：**触发只表示「该重验了」，不表示「可以发布了」**——"
                "发布授权仍只能由 SL-CAP-0053 的人工门产生，二者不得混同。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true",
        "interfaces": ["SL-CAP-0053（发布门禁，与触发严格分离）", "SL-CAP-0044（影响面）"],
        "unresolved": ["release 触发与 PR 触发的优先级待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C16"],
        "capability": "测试用例维护触发",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0044",
        "final_owner": "Lifecycle",
        "verdict": "ADAPT",
        "reason": (
            "机制是「四条触发条件维护活文档」，why 写「理念可借：文档是活的质量保障清单而非一次性产物；"
            "具体四触发绑死它自己的文档体系」。"
            "在 SourceLore 里，其可迁移部分是**变更影响面的「新事实发现」路径**："
            "新增或修改测试文件本身就是一类变化集，应被路径 B 识别为可能的新知识点。"
            "不是「源码变化引起知识重验」（那归路径 A）、不是「测试执行任务」、"
            "也不是「测试结果作为证据」（那归 EC）。**F1 阶段不要求实际运行测试。**"
        ),
        "amendment": {
            "target": "SL-CAP-0044",
            "append_note": (
                "补充变化类别（F1-C-C2 由 U05-C16 引入）：路径 B 的枚举清单必须显式包含"
                "「测试文件的新增/修改/删除」这一类别。理由：测试是质量保障清单的一部分，"
                "测试文件的变动意味着可能有新的验证点未被登记。"
                "**F1 阶段只要求识别与登记，不要求实际运行测试**——"
                "测试执行归后续运行时批次。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（只取「变化类别」理念，不复制其四条触发条件）",
        "interfaces": ["SL-CAP-0075（评测基线）", "SL-CAP-0043（调度）"],
        "unresolved": ["测试文件变动是否触发 revalidate 待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C21"],
        "capability": "冲突处理",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0028",
        "final_owner": "Evidence-Claims",
        "verdict": "REIMPLEMENT",
        "reason": (
            "审计判 REIMPLEMENT，mechanism 为「缺失」，why 写「全文检索未发现任何关于两条知识互相矛盾时"
            "如何处理的规则。没有裁决机制。SourceLore 必须有显式 conflict 状态与裁决权归属」。"
            "**按冲突类型分开归属，不合并成一个全局冲突状态机**：\n"
            "① Claim 之间证据冲突 → 本条，EC 的裁决状态机；\n"
            "② 历史知识与当前理解冲突 → SL-CAP-0041（可变层/不可变层分离）；\n"
            "③ 多 Agent 并发写入冲突 → SL-CAP-0064（CAS，明确返回 CONFLICT）；\n"
            "④ 人工内容与生成内容冲突 → SL-CAP-0058（生成/人工物理隔离）。"
            "原始 C21 的主要语义是 ①——因为上游 is 知识治理语境下的「两条知识矛盾」，"
            "且 why 要求的是「裁决权归属」。故唯一 owner = EC，做法是给 SL-CAP-0028 补一个 conflict 旁支状态，"
            "而不是新建全局冲突机。"
        ),
        "amendment": {
            "target": "SL-CAP-0028",
            "append_note": (
                "补充冲突旁支状态（F1-C-C2 由 U05-C21 引入）：状态机增加旁支 `conflict`——"
                "两条 Claim 的证据互相矛盾、且无法用现有证据判定谁对时进入该状态。"
                "硬规则一：conflict 是合法终态，**不得强行收敛为 supported 或 refuted**；"
                "必须保留双方证据与各自的 claim_id，并写明冲突点。"
                "硬规则二：conflict 的裁决权归 EC；若需人工介入，走 SL-CAP-0028 已有的人工确认分支。"
                "边界声明：本旁支只管**Claim 之间的证据冲突**。"
                "历史知识与当前理解冲突归 SL-CAP-0041、并发写入冲突归 SL-CAP-0064、"
                "人工与生成内容冲突归 SL-CAP-0058——**不得把这四类合并成一个全局冲突机**。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（上游无实现，本条为自建状态定义）",
        "interfaces": ["SL-CAP-0041", "SL-CAP-0064", "SL-CAP-0058（三类非 claim 冲突的归属）"],
        "unresolved": ["conflict 的收敛条件（何时可解除）待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C25"],
        "capability": "测试覆盖作为质量证据",
        "direction": "ADOPT_EXISTING",
        "target_canonical": "SL-CAP-0075",
        "final_owner": "Evidence-Claims",
        "verdict": "REIMPLEMENT",
        "reason": (
            "机制「3 文件 19 方法」，why 写「存在测试这件事本身是相对 U04 的实质进步，但覆盖严重偏斜："
            "18 个脚本里只有 3 个被测试触及，check_pkb_staleness.py / gen_index.py 零引用。"
            "SourceLore 若建脚本层，必须以『机制必被测』为准入，而非『有 tests 目录』」。"
            "核实四个问题：覆盖率只是**测试运行的测量结果**；**不能**证明某功能正确；"
            "**不能**证明某 Claim 得到支持；**可以**作为 SL-CAP-0075 评测基线的一项输入（但只是一项）。"
            "故归 0075，并补「覆盖率≠正确性」的硬规则。"
        ),
        "amendment": {
            "target": "SL-CAP-0075",
            "append_note": (
                "补充覆盖率语义（F1-C-C2 由 U05-C25 引入）：覆盖率可作为评测基线的一项输入指标，"
                "但必须遵守四条：\n"
                "T-1 **覆盖率不等于正确性**——高覆盖率只说明代码被执行过，不说明结果正确；\n"
                "T-2 **测试存在不等于测试通过**——存在测试文件/用例不构成「已验证」证据；\n"
                "T-3 **测试通过不等于全部功能已验证**——覆盖偏斜时未覆盖部分仍是未知；\n"
                "T-4 上游若存在测试目录或覆盖率数字，**不得直接提升为「已验证」**——"
                "必须区分「被测对象声明了测试」与「本次运行确实通过」。\n"
                "准入原则（借上游价值）：机制层必须以「机制必被测」为准入标准，"
                "不以「有 tests 目录」为准入。"
            ),
        },
        "license_note": "Apache-2.0 / copy_permitted=true（借「机制必被测」准入原则，不复制其测试代码）",
        "interfaces": ["SL-CAP-0028（claim 状态）", "SL-CAP-0070（成本）"],
        "unresolved": ["覆盖率阈值是否进 E-2 交叉指标待 F2"],
    },
    {
        "identity": ["UPSTREAM-05", "C27"],
        "capability": "产出面向人类的整册项目文档",
        "direction": "REJECT_WITH_REASON",
        "target_canonical": None,
        "final_owner": None,
        "verdict": "REJECT",
        "reason": (
            "原始 disposition 已是 **REJECT**，本条维持并给出最终理由。"
            "审计 why 写「这是一个面向『给团队写项目文档』的产物流水线，不是知识治理。"
            "SourceLore 的目标是可机械判定的 claim 集合，不是可读的文档册。产物形态整体不采纳」。"
            "**拒绝的是具体上游机制**（00–12 编号页 + Sphinx 双语站点组成的文档流水线），"
            "不是拒绝「产出可读视图」——后者已由 Renderer 的 SL-CAP-0055（多类型视图）承接。"
            "**不得通过改写成「人类可读报告」重新引入该机制。**"
        ),
        "terminal_disposition": "REJECTED_WITH_REASON",
        "license_note": "Apache-2.0 / copy_permitted=true（但整体机制不采纳，不复制其页集与站点的任何文件）",
        "interfaces": ["SL-CAP-0055（人类可读视图的正确归属）"],
        "unresolved": ["无——已终裁"],
        "awaiting": "F1-C-D terminal_disposition 迁移（三态模型无法表达 REJECT）",
    },
    {
        "identity": ["UPSTREAM-05", "C28"],
        "capability": "双语 Sphinx 站与 gettext 流程",
        "direction": "REJECT_WITH_REASON",
        "target_canonical": None,
        "final_owner": None,
        "verdict": "REJECT",
        "reason": (
            "原始 disposition 已是 **REJECT**，维持。"
            "审计 why 写「与本项目目标正交。它的存在反而说明该上游重心在文档交付，不在知识新鲜度」。"
            "**拒绝的是具体机制**（Sphinx + myst + sphinx-intl 的双语构建链），"
            "不是拒绝多语言能力本身——SourceLore 的多语言若需要，属 F2 的呈现层选型，不由此条引入。"
        ),
        "terminal_disposition": "REJECTED_WITH_REASON",
        "license_note": "Apache-2.0 / copy_permitted=true（机制不采纳，不复制其构建链）",
        "interfaces": [],
        "unresolved": ["无——已终裁"],
        "awaiting": "F1-C-D terminal_disposition 迁移",
    },
]

# 与 F1-C-C1 同构：本批不产生 DEFER，剩余两项 REJECT 保持真实旧状态
UNREVIEWED_AFTER = ["UPSTREAM-05::C27", "UPSTREAM-05::C28"]
