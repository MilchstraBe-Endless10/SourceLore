#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Lifecycle 模块：canonical 定义与跨模块去向。

导出符号：
    MODULE                    "Lifecycle"
    FIRST_ID                  "SL-CAP-0040"
    CANON                     6 条 canonical（0040–0045）
    DEFERRED_TO_OTHER_MODULE  本批裁决后推给其它模块的 5 个身份
    CONSUMED_THIS_BATCH       本批正式承接的 12 个身份（2 条 ROUTED + 10 条未审直采）

ID 规则：从 SL-CAP-0040 起连续分配，不重排 0001–0039。
"""

MODULE = "Lifecycle"
FIRST_ID = "SL-CAP-0040"

CANON = [
    {
        "id": "SL-CAP-0040",
        "name": "Subject 稳定身份与知识复用判定（确定性候选 + 模型辅助，两者分离）",
        "description": (
            "知识以 Subject（可长期持续学习的对象）为单位组织，而不以 Question（一次性提问）为单位。"
            "Subject 的稳定身份由三件套确定：subject_key（规范化后的主题标识）、repo_binding"
            "（绑定的仓库身份，见下）、claim_scope（该 Subject 覆盖的断言范围）。\n"
            "仓库身份的层级必须分明：repository_id（GitHub 稳定数字 ID，改名不改号）是身份锚点；"
            "owner/name 是可变的显示名；URL 是取数位置；commit_sha 是内容快照标识。"
            "四者不可互换，尤其不得用 URL 或 owner/name 作为身份键——仓库改名后 URL 就变了，"
            "而知识应当延续。\n"
            "仓库改名：repository_id 不变即视为同一 Subject，旧记录保留并标注 name_history。\n"
            "Fork：与原仓库是关联关系而非身份延续——fork 有自己的 repository_id，"
            "属独立 Subject，通过 forked_from 字段关联，不得合并。\n"
            "复用判定分两步且必须分离：第一步是确定性候选匹配（按 subject_key 规范化 + "
            "claim_scope 重叠度 + repo_binding 计算候选集），第二歩才是模型辅助判断候选之间是否真同一 Subject。"
            "模型判断只能产出建议，不得被记录为「已通过确定性身份校验」。"
            "最终动作按硬顺序 Reuse > Extend > Create：存在 subject_key 精确匹配则 Reuse，"
            "存在 scope 包含关系则 Extend，两者皆无才 Create。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["candidate_subject{subject_key, repo_binding, claim_scope}",
                   "existing_subjects[]", "repo_identity{repository_id, owner, name, url}"],
        "outputs": [
            "subject_identity{subject_key, repository_id, name_history[], claim_scope}",
            "reuse_decision{action: reuse|extend|create, matched_subject_id?, basis}",
            "candidate_set[]{subject_id, match_score, match_reasons[]}",
            "identity_provenance{deterministic_checks[], model_assisted_judgement?}",
        ],
        "depends_on_modules": ["Facts", "Collector", "Storage"],
        "overlaps": (
            "与 Facts 的 SL-CAP-0002（repo_facts 契约）分界：facts 是单次快照的事实，"
            "本条是跨快照持续存在的知识身份。与 Storage 分界：本条定义身份语义与复用规则，"
            "实际读写与索引实现归 Storage"
        ),
        "unresolved": [
            "subject_key 的规范化算法（大小写、复数、同义词消解）待 F2；"
            "本批只要求「规范化必须确定性可复现」",
            "claim_scope 的包含关系如何机械判定（子集判定需要结构化 scope 而非自由文本）待 F2",
            "跨仓库同一主题（如两个仓库都实现 OAuth）是否共享 Subject，属 F1-C 裁决",
            "Subject 身份与 Facts 的 Canonical Knowledge Registry 的关系：本批登记为待裁决事项，不擅改",
        ],
        "refs": [
            ("UPSTREAM-04", "C02", "REIMPLEMENT"),
            ("UPSTREAM-04", "C18", "REIMPLEMENT"),
            ("UPSTREAM-04", "C12", "ADAPT"),
        ],
        "notes": (
            "合并依据：C02 给「Subject 而非 Question 作为身份单位」的判据，C18 给 Reuse/Extend/Create "
            "三态判定的目标，C12 给「优先扩展而非新建」的取向——三者是同一件事的定义、判定与取向。"
            "C02 判 REIMPLEMENT 而非 REUSE：上游 L37 的定义（能持续学习的对象）与四个举例确实是可用判据，"
            "但它没有给出任何可计算的身份键；下游要落库就必须有 subject_key 与 repo_binding，故须补实现。"
            "C18 判 REIMPLEMENT：上游四个关键判断（plausibly covers、already answers it、is still valid、"
            "no existing subject covers it）全是模型主观短语（审计 D1 blocker），照用会导致语料库碎片化。"
            "本条把它们拆成「确定性候选匹配 + 模型辅助判断」两段，且禁止把后者记成确定性校验通过。"
            "C12 判 ADAPT：方向正确（同一 Subject 出两份报告就是失败模式），但只是取向不是规则，"
            "本条改为硬顺序 Reuse > Extend > Create。"
        ),
    },
    {
        "id": "SL-CAP-0041",
        "name": "可变层与不可变层分离（当前理解可改写，历史只追加）",
        "description": (
            "知识库分两层且规则相反：不可变层（Findings / Evidence）只追加，永不被覆盖或删除，"
            "结论被推翻时只标注状态变更；可变层（Current Understanding）是该 Subject 的当前视图，"
            "可就地重写，但每次重写必须留下版本记录与指向前一版的链接。\n"
            "硬规则一：结论被取代不删除旧证据。旧证据属于不可变层，superseded 只是当前视图的标注。\n"
            "硬规则二：任何模块不得直接覆盖历史记录——包括 Renderer（渲染只能产出新版本，"
            "不得回写既有条目）与 Storage（写入只能在不可变层追加，不得 mutate 已写入历史）。\n"
            "硬规则三：Current Understanding 的每次变更必须携带 changed_fields、prev_version_ref、"
            "以及触发这次变更的 change_event（来自 SL-CAP-0043 的变更事件）。\n"
            "硬规则四：恢复到旧版本知识视图时，以该版本记录的 snapshot_boundary 为界——"
            "恢复是「生成一份指向旧版本的新视图」，不是「抹掉后来的记录」。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["subject_id", "new_understanding", "change_event", "immutable_records[]"],
        "outputs": [
            "understanding_version{version_id, subject_id, changed_fields[], prev_version_ref, snapshot_boundary}",
            "immutable_append{record_id, kind: finding|evidence, appended_at}",
            "supersession_marker{superseded_by, superseded_at, applies_to_view_only: true}",
        ],
        "depends_on_modules": ["Storage", "Evidence-Claims"],
        "overlaps": (
            "与 Evidence-Claims 的 SL-CAP-0027（结论生命周期与新鲜度）分界：0027 定义 claim 自身的"
            "superseded_by / retracted_reason 字段语义，本条定义「整个知识库的两层结构」——"
            "即这些字段落在哪一层、谁可以写。两者是字段与容器的关系，不重复"
        ),
        "unresolved": [
            "版本粒度（每次写入一个版本 vs 每次任务一个版本）待 F2",
            "snapshot_boundary 的表示（时间点 vs 版本序号 vs commit）待 F2",
            "不可变层的物理写入与事务由 Storage 实现，本条只定义「只追加」的语义契约",
        ],
        "refs": [
            ("UPSTREAM-04", "C01", "REIMPLEMENT"),
            ("UPSTREAM-04", "C20", "REIMPLEMENT"),
        ],
        "notes": (
            "合并依据：C01 给「可变/不可变两层」的结构，C20 给「Current understanding 演进史」的时间维度——"
            "没有 C20 的层结构就是静态的，没有 C01 的层结构演进史就无处安放。两者是空间与时间的同一设计。"
            "C01 判 REIMPLEMENT 而非审计建议的 REUSE：上游那两句话（就地重写 current understanding、"
            "findings 只追加）确实是最强设计，但上游只把它写在文档里，没有任何写入侧的强制——"
            "没有版本记录、没有 prev 指针，重写就是真的抹掉。本条把取向升格为带版本记录的结构，故不是原样沿用。"
            "C20 判 REIMPLEMENT：上游明令就地重写、旧版本即丢失（审计 D4），这是必须偏离上游处——"
            "改为版本化保留。两者在 SourceLore 都只能取抽象思想，实现自建。"
        ),
    },
    {
        "id": "SL-CAP-0042",
        "name": "内容哈希驱动的精确失效检测（保守降级）",
        "description": (
            "失效检测比对内容哈希而非时间戳。每个 evidence 记录其依赖的 path 与 content_hash；"
            "每条 claim 记录其 evidence_refs。仓库出新 commit 时，只对该 claim 依赖的路径逐个取新哈希：\n"
            "路径内容未变 → 依赖仍有效，可直接重用。\n"
            "路径内容已变 → 标记 dependency_changed，进入重验证队列，但不改判 claim 状态。\n"
            "路径已删除 → 标记 source_removed，同样进重验证队列。\n"
            "路径已重命名 → 按 Git 重命名检测追踪到新路径，标记 path_moved 并保留旧路径以便追溯。\n"
            "变化集不完整（Git tree truncated、分页未取全、部分端点失败）→ 必须降级为"
            " detection_incomplete 并附未覆盖范围，禁止在变化集不完整时输出「已知依赖未变」。\n"
            "硬规则一：只有在变化集完整且依赖登记充分时，才能作出「已知依赖未变」的判断。\n"
            "硬规则二：不得把「旧文件哈希未变」扩大解释为「产品功能未变」——"
            "功能可能由未登记为依赖的文件驱动（配置、路由表、生成脚本）。\n"
            "硬规则三：不得使用文件系统 mtime 作为失效判据。mtime 不是内容，touch 一下就会误判，"
            "内容回退则完全看不见。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["claim_dependencies{claim_id, evidence_refs[]}",
                   "evidence_dependencies{evidence_id, path, content_hash}",
                   "change_set{commit_from, commit_to, changes[], complete: bool}"],
        "outputs": [
            "staleness_record{claim_id, state, affected_paths[], basis}",
            "dependency_state{evidence_id, state: unchanged|changed|removed|moved, new_path?, new_hash?}",
            "detection_coverage{complete, uncovered[]}",
        ],
        "depends_on_modules": ["Collector", "Facts", "Storage"],
        "overlaps": (
            "与 Research 的 SL-CAP-0037（coverage_record）共用「覆盖必须显式」的纪律，对象不同："
            "0037 管外部研究资料的覆盖，本条管仓库变更集的覆盖。"
            "与 Evidence-Claims 的 SL-CAP-0027 分界：0027 的 verified_commit/accessed_at 是记录字段，"
            "本条是「谁拿这些字段来比对、比什么、什么时候判失效」的检测机制"
        ),
        "unresolved": [
            "变更集完整性的判定标准（tree.truncated 之外是否还有其它不完整来源）待 F2",
            "重命名的检测依赖 Git 的 rename 启发式，阈值不可靠时如何降级待 F1-C",
            "非源码来源（Issue/Release/外部网页）的变化检测见 SL-CAP-0045，两套机制如何共用事件模型待 F2",
        ],
        "refs": [
            ("UPSTREAM-05", "C17", "REIMPLEMENT"),
            ("UPSTREAM-04", "C19", "REIMPLEMENT"),
            ("UPSTREAM-06", "C26", "REIMPLEMENT"),
        ],
        "notes": (
            "合并依据：C17 提供「过期检测」的触发位置，C19 提供「知识失效检测」的目标，"
            "C26 提供「新鲜度与失效判定」的缺口定义——三者都在说「什么时候这条知识不再可靠」，"
            "拆开会出现三套互不知情的失效判据。合并为一条检测机制。"
            "C17 判 REIMPLEMENT：上游有实现但手段错误——它比的是文件系统修改时间与归档时间的差，"
            "单向下界（src_mtime <= doc_mtime 直接 continue），mtime 被 reset 或文件被回退就完全看不见。"
            "本能力改成内容哈希比对，只采纳其「零 token 先行」的取向。"
            "C19 判 REIMPLEMENT：上游只有 re-verification 这个词（L46），没有任何检测机制（审计 D3）。"
            "C26 是特别说明的一项：上游该能力处标注为「缺失」——它描述的是上游没有的东西。"
            "因此本条只能把它作为「SourceLore 必须独立设计」的需求来源，不得宣称上游已提供实现。"
            "这一点写在这里以免后续误读。"
        ),
    },
    {
        "id": "SL-CAP-0043",
        "name": "变更类型分类与增量重建调度（重采集/重验证/重渲染/重研究分离）",
        "description": (
            "每个变更事件必须先归类，再决定动作；不得「一变就全重跑」，也不得「一种动作包打天下」。"
            "五类动作与触发条件：\n"
            "recollect——需要新数据：commit 前进且变化集合非空、或外部来源需要重取。\n"
            "revalidate——只需重新验证既有 claim：文件内容变化但事实抽取结果未变。\n"
            "rerender——只需重生成产物：知识未变、仅呈现层或模板变化。\n"
            "reanalyze——需要重做产品语义：实体/流程定义被推翻，属 Product 侧的重做。\n"
            "reindex——仅更新派生索引：索引是派生视图，从不手改，永远可重建。\n"
            "另设人工补充判断通道：当变更涉及人工业务解释、或确定性判据无法归类时，"
            "产出一个需要人工确认的条目，不得自动选择动作。\n"
            "三类判定必须显式标注来源：确定性检查（哈希比对、集合运算）—模型辅助判断（语义是否受影响）"
            "—人工审批。每次调度记录必须写明本次归类依据属于哪一类。\n"
            "调度必须可恢复与幂等：同一 change_event 重复调度结果一致；中断后从已完成的动作续跑，"
            "已完成的采集与验证不重跑。失败动作必须走显式回退路径（降级到 partial 或留待人工），"
            "不得静默跳过。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["change_event{kind, affected_paths[], scope}", "staleness_record[]", "task_tier: L1|L2|L3"],
        "outputs": [
            "action_plan{actions[], per_action_rationale, decision_class: deterministic|model_assisted|human}",
            "action_record{action, status, resume_marker?, rollback_path?}",
            "rollback_record{trigger, from_state, to_state, reason}",
        ],
        "depends_on_modules": ["Lifecycle", "Collector", "Storage"],
        "overlaps": (
            "与 Research 的 SL-CAP-0035 分界：0035 管「一次研究任务内部跑到哪、如何恢复」，"
            "本条管「知识因外部变化需要何种重做」——研究中断恢复归 Research，知识重验证触发归 Lifecycle。"
            "与 Storage 的并发与原子写入分界：本条定义动作序列的语义与顺序，物理事务由 Storage 实现"
        ),
        "unresolved": [
            "五类动作的判定阈值（「事实抽取结果未变」的具体判定）待 F2",
            "task_tier L1/L2/L3 与动作选择的具体映射表待 F1-C 定稿",
            "人工补充判断的入口与权限归属待 F1-C",
            "与 Research resume_point 的接口见第 10 节登记的跨模块 unresolved",
        ],
        "refs": [
            ("UPSTREAM-03", "C08", "ADAPT"),
            ("UPSTREAM-05", "C02", "REUSE"),
            ("UPSTREAM-05", "C11", "ADAPT"),
        ],
        "notes": (
            "合并依据：C08 提供「什么变化触发什么重跑」的九个触发点，C02 提供「本次该出多大力」的三级梯度，"
            "C11 提供「失败怎么回退」的显式路径——三者是同一调度的触发、力度与失败处理。"
            "C08 判 ADAPT：九触发点是三个上游唯一的增量更新契约，但全是叙述句，本条改为可判定条件"
            "（文件哈希变化、注册表条目增减、页面缺失）。"
            "C02 判 REUSE：三级梯度把「AI 该出多少力」变成可分类的动作类而非模糊的「尽量少用」，"
            "直接映射到 L1 不产 claim / L2 产受限 claim / L3 产需人签字的 claim，可原样沿用。"
            "C11 判 ADAPT：上游少见地显式写了失败回退（多数 skill 只写成功路径），"
            "但只到方向，本条补上可执行的回退记录结构。"
            "C08 与 C02 是本批仅有的两条来自 routed 的承接（identity 从 ROUTED 迁到 MAPPED），"
            "均有晋升记录可查。"
        ),
    },
    {
        "id": "SL-CAP-0044",
        "name": "变更影响面分析（两条路径分离：已知依赖检测 / 新事实发现）",
        "description": (
            "仓库变化后必须走两条独立的分析路径，不得合并成一个「只查旧路径」的算法：\n"
            "路径 A（已知依赖检测）：以既有 claim 登记的 evidence 依赖为起点，定位受内容变化影响的"
            "既有 claim。作用是「旧结论哪些需要重验证」。\n"
            "路径 B（新事实发现）：以变化集本身为起点，识别新增文件、新增路由、新增配置、新增依赖、"
            "以及既有清单之外的结构变化，判断哪些可能出现此前未覆盖的知识点。"
            "作用是「有没有该新建而尚未新建的知识」。\n"
            "两条路径可以共享同一份 Collector 变化元数据，但各自的起点、判据与产物不同："
            "路径 A 产出受影响 claim 清单，路径 B 产出候选新增主题清单。\n"
            "硬规则：路径 A 的「未受影响」不能替代路径 B 的「无新事实」——"
            "旧依赖都干净不等于没有新东西。只有在变化集完整且已枚举全部新增项时，"
            "才能宣称「无新事实」。"
        ),
        "disposition": "ADAPT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["change_set{added[], modified[], removed[], renamed[]}", "claim_dependencies[]"],
        "outputs": [
            "impact_report{A_affected_claims[], B_candidate_topics[], coverage_note}",
            "change_classification{class, affected_scope[], basis}",
        ],
        "depends_on_modules": ["Collector", "Facts", "Lifecycle"],
        "overlaps": (
            "与 SL-CAP-0042 分界：0042 判「某条 claim 依赖的文件变没变」（点对点），"
            "本条判「这次变化整体影响了哪些面」（面到面）。0042 是路径 A 的底层机制，"
            "本条在其上做聚合，并额外承担路径 B"
        ),
        "unresolved": [
            "路径 B 的「候选新增主题」由谁判定（确定性规则 vs 模型辅助）待 F1-C",
            "四类判定的置信标注方式（上游的四分类是纯定性）待 F2",
            "与 Security 的交接：安全发现何时因变更必须重新验证，见跨模块 unresolved",
        ],
        "refs": [("UPSTREAM-04", "C17", "ADAPT")],
        "notes": (
            "U04-C17 判 ADAPT：上游的七步流程与四类判定（确定破裂 / 兼容风险 / 安全清理 / 看似未用）"
            "结构很好，但其核心立论「不要因为缺测试就认为无使用」（L16）只是一句提醒、无可执行判据。"
            "本条保留七步结构，补上「两条路径分离」这一关键约束——上游把影响面调查当一件事，"
            "实际上「旧结论受不受影响」与「有没有新东西」是两个方向的问题，合并会系统性漏掉后者。"
            "这也正对应本轮任务的第 5 节：两条路径共享元数据但不得合并算法。"
        ),
    },
    {
        "id": "SL-CAP-0045",
        "name": "外部可变来源的新鲜度与不可复现观察保留",
        "description": (
            "来源必须按可变性分类处理，不可用同一套凭据：\n"
            "不可变源码（commit 固定的片段）——以 commit_sha + content_hash 判定，可精确复算。\n"
            "可变来源（Issue / PR / Release / 外部网页 / 第三方 API）——以 retrieved_at 记录取回时刻，"
            "并在可用时使用 ETag / Last-Modified / 内容哈希作为验证辅助；"
            "验证辅助缺一即降级为 retrieved_at_only，不得据此断言内容仍正确。\n"
            "不可复现观察（付费接口、已下线页面、随机输出、特定环境）——必须保留历史观察记录，"
            "并显式标注 reproducible=no 与 environment_note；这类记录永不被判为 stale，"
            "只标为 unverifiable_since。\n"
            "人工补充的业务解释——记录 who/what/when，与机器观察区别对待，不参与哈希复算。\n"
            "硬规则一：verified_against_commit 不是通用外部信息新鲜度凭据——它只对 commit 固定的源码有效。\n"
            "硬规则二：retrieved_at 只能证明何时取回，不能证明内容现在仍然正确。\n"
            "硬规则三：TTL / ETag / Last-Modified 只能作为验证辅助，不得伪造来源支持。"
        ),
        "disposition": "REIMPLEMENT",
        "v1_scope": "V1_REQUIRED",
        "inputs": ["source_record{kind, retrieved_at, commit_sha?, etag?, last_modified?, content_hash?}"],
        "outputs": [
            "source_freshness{kind, freshness_basis: commit|hash|etag|retrieved_at_only|unverifiable, verdict}",
            "unverifiable_observation{observation, environment_note, unverifiable_since}",
            "human_note{author, content, at}",
        ],
        "depends_on_modules": ["Research", "Evidence-Claims"],
        "overlaps": (
            "与 Research 的 SL-CAP-0037 分界：0037 定义 source_type 与 coverage 的标记，"
            "本条定义「不同标记下如何判新鲜度」。与 Evidence-Claims 的 SL-CAP-0020 分界："
            "0020 的 reproducible 三态是存档形态字段，本条决定「该三态如何驱动失效判定」"
        ),
        "unresolved": [
            "TTL 的默认值与来源分级待 F2",
            "unverifiable_since 是否允许重新降级为可验证（来源恢复时）待 F1-C",
            "与 SL-CAP-0042 的事件模型如何共用待 F2（两者都产出 change event，但数据源不同）",
        ],
        "refs": [],
        "notes": (
            "本条无上游来源，是独立设计。理由写清楚，否则读者会以为漏了引用。"
            "U04-C24 与 U05-C24（不可复现外部观察的字段缺失）在 Research 批次已判定归入 "
            "Evidence-Claims，当前仍是 ROUTED、未被任何批次承接；本批不重复占用，"
            "那两个身份的最终归属以 EC 批次为准。"
            "U06-C26（新鲜度与失效判定）已由 SL-CAP-0042 承接，同一个原始身份只能正式映射一次，"
            "故此处不能再引用。"
            "剩下的内容——按可变性给来源分类、verified_against_commit 只对 commit 固定的源码有效、"
            "retrieved_at 只证明取回时刻、TTL/ETag 只能作辅助不得伪造来源支持、"
            "不可复现观察永不被判 stale 只标 unverifiable_since——是 SourceLore 自建的语义，"
            "六源中没有任何一处提供过，属零来源独立设计。"
        ),
    },
]

# ── 跨模块去向 ───────────────────────────────────────────────────────────
DEFERRED_TO_OTHER_MODULE = {
    ("UPSTREAM-04", "C03"): (
        "Storage",
        "索引是派生视图、禁止手改——这是存储层的写入纪律与重建职责；Lifecycle 只要求「可重建」而不实现索引",
    ),
    ("UPSTREAM-04", "C22"): (
        "Storage",
        "并发写入保护（锁/原子写/幂等/冲突检测）是存储实现的五件套；Lifecycle 只声明所需原子性",
    ),
    ("UPSTREAM-04", "C23"): (
        "Storage",
        "结构化查询是多维索引的检索能力；索引如何建、查询如何执行归 Storage",
    ),
    ("UPSTREAM-05", "C04"): (
        "Evidence-Claims",
        "review_status 的人机权限分离已由 EC 的 SL-CAP-0028 裁决状态机承接（状态迁移凭证）；本批不重复建",
    ),
    ("UPSTREAM-05", "C20"): (
        "Security",
        "保密切分与发布前脱敏属安全分级与产物投放；Lifecycle 不定义敏感度分级",
    ),
}

# ── 本批正式承接的原始身份 ────────────────────────────────────────────────
CONSUMED_THIS_BATCH = {
    ("UPSTREAM-03", "C08"): ("SL-CAP-0043", "cross_module_redirections"),
    ("UPSTREAM-05", "C17"): ("SL-CAP-0042", "cross_module_redirections"),
    ("UPSTREAM-04", "C19"): ("SL-CAP-0042", "unreviewed_adopted"),
    ("UPSTREAM-06", "C26"): ("SL-CAP-0042", "unreviewed_adopted"),
    ("UPSTREAM-04", "C02"): ("SL-CAP-0040", "unreviewed_adopted"),
    ("UPSTREAM-04", "C18"): ("SL-CAP-0040", "unreviewed_adopted"),
    ("UPSTREAM-04", "C12"): ("SL-CAP-0040", "unreviewed_adopted"),
    ("UPSTREAM-04", "C01"): ("SL-CAP-0041", "unreviewed_adopted"),
    ("UPSTREAM-04", "C20"): ("SL-CAP-0041", "unreviewed_adopted"),
    ("UPSTREAM-04", "C17"): ("SL-CAP-0044", "unreviewed_adopted"),
    ("UPSTREAM-05", "C02"): ("SL-CAP-0043", "unreviewed_adopted"),
    ("UPSTREAM-05", "C11"): ("SL-CAP-0043", "unreviewed_adopted"),
}
