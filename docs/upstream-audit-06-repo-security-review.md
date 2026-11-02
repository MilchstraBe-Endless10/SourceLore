# UPSTREAM-06 审计：Consensys/repo-security-review

- 任务：UPSTREAM-06（M1 多源上游审计，第六源）
- 审计对象：`Consensys/repo-security-review`（整仓，无子树）
- 上游固定提交：`d5128b03d6a785bfb7c8be4139291f887c2a3215`
- 审计方式：本地固定快照静态阅读，零脚本执行、零依赖安装、零容器启动
- 审计执行：DeepSeek-V4.1 Flash（DSH 执行 Agent）
- 审计时间：2026-11-02 15:30 +08:00

本轮的重点不是「这个 skill 能不能用」，而是三件更硬的事：它自身的安全边界是否成立、它的证据纪律能否脱离 Claude Code 独立实现、以及在**没有许可证**的前提下 SourceLore 究竟能拿走什么。

---

## 1. 上游事实

### 1.1 仓储身份

| 项 | 值 |
|---|---|
| Repository ID | 1249083556 |
| URL | https://github.com/Consensys/repo-security-review |
| 描述 | A Claude Skill to perform security code review for repositories (code and Skill) |
| 默认分支 | main |
| 固定提交 SHA | d5128b03d6a785bfb7c8be4139291f887c2a3215 |
| 提交日期 | 2026-10-21T17:06:36Z |
| 提交信息 | Clarify dependency CVE triage and reporting |
| 作者 | behroozreview |
| 主语言 | Shell |
| 体积 | 865 KB |
| Star / Fork / Issue | 32 / 7 / 0 |
| 归档 / 派生 / 私有 | 否 / 否 / 否 |
| 创建时间 | 2026-05-25T10:34:41Z |
| 最近推送 | 2026-10-21T17:06:40Z |
| Topics | 空 |

### 1.2 固定快照

| 项 | 值 |
|---|---|
| 快照路径 | `upstreams/UPSTREAM-06-repo-security-review` |
| `tree.json` 树 SHA | d5128b03d6a785bfb7c8be4139291f887c2a3215 |
| tree 条目数 | 18（16 blob + 2 tree） |
| `truncated` | false |
| blob 数 / 落盘文件数 | 16 / 16 |
| 总字节 | 466023 |
| 清单 | `files.tsv`，无表头，严格 3 列 `path<TAB>bytes<TAB>blob_sha` |
| 完整性核验 | 逐行比对字节数与 Git blob SHA：OK=16 / MISMATCH=0 / MISSING=0，退出码 0 |

两个 tree 对象分别是 `references/` 与 `scripts/`。仓库只有这三层，没有隐藏目录、没有子模块、没有 Git LFS。

### 1.3 真实文件清单

| 文件 | 字节 | Git blob SHA |
|---|---|---|
| `.gitignore` | 10 | e43b0f988953ae3a84b00331d0ccf5f7d51cb3cf |
| `README.md` | 11688 | b4a37c081c5c1a65ff8c30f4de0193de2586333c |
| `SKILL.md` | 90684 | 1694f20debbf3ccb4c5ea259c2b1e9b4addf5d04 |
| `references/phase-llm-security.md` | 12848 | 62912a15ae303d42cf0b1f2458774e145eae4b6e |
| `references/phase0-topology.md` | 6349 | 9954644e6b48200f0d8eba99c93fa0d6fcb950cd |
| `references/phase1-secrets.md` | 5721 | 08e6f65cab052567ee59b10d7d4b19102968552b |
| `references/phase2-architecture.md` | 22977 | 41f73f6bb95a57d687e2cccc1fea7e03de961f30 |
| `references/phase2a-tech-stack.md` | 23206 | 87acbfb900270662907c2f1200f655387f295513 |
| `references/phase3-dependencies.md` | 20198 | 06f3704692a753e511cc740a0aad474045f5b3dc |
| `references/phase4-owasp.md` | 48959 | f6b9d47f1ded436d9273fe85d780d124b4e57ec7 |
| `references/phase5-validate-and-poc.md` | 92637 | 54c8d030097532406d87155b13b415201c4834bf5 |
| `references/phase6-report.md` | 51348 | b786a53771886ee7e7df0793996cb4b0fdc62155 |
| `references/phase7-synthesis.md` | 16946 | 3986b443462baaccb4a31eb512877f8b101c21e9 |
| `references/pr-review.md` | 20774 | 15c425cc30a5981093fb7a503a82c970ccc6ca46 |
| `scripts/repo-security-review-command.md` | 31148 | 8361a8435a2338f613227e51817b7cfb2c88cd66 |
| `scripts/setup.sh` | 10530 | 01c4d9795cd400c967d5e52ff07c78347ad480ff |

合计 8959 行。除 `scripts/setup.sh` 外全部是 Markdown；整个仓库没有一行属于「分析引擎」的代码——它是提示词与规则文本，加一个安装脚本。

### 1.4 许可证：无

这是本轮第一个必须钉死的事实，也是最影响处置结论的一条。

| 检查项 | 结果 |
|---|---|
| GitHub API `license` 字段 | `null` |
| `/repos/Consensys/repo-security-review/license` 端点 | HTTP 404 `Not Found` |
| 16 个文件全文检索 `LICENSE` / `Copyright` / `SPDX` / `©` | 命中 0 |
| 仓库内 LICENSE / COPYING / NOTICE 文件 | 不存在 |
| `.gitignore` | 仅一行 `.DS_Store`，10 字节，不含任何许可声明 |

结论：在默认著作权下该仓库保留全部权利，**不存在可复制或可改编的授权**。这不是「许可证不明」，是「没有许可证」。

因此本轮的执行边界是：

- 上游源码、提示词原文、规则原文、模板一律**不得**并入 SourceLore。
- 本轮全部 `REUSE` 判定只表示抽象设计思想可被采用，不表示允许复制上游源码或文档。
- 具体代码实现原则上必须独立编写；本审计不复述任何上游规则文本，只描述其机制形状。
- 许可证状态作为独立字段记录在 JSON 的 `license.status`，**不得被任何 REUSE 判定覆盖**。

### 1.5 静态 / 动态状态

`test_status = NOT_RUN`。仓库内有 `scripts/setup.sh` 一个可执行脚本，本轮只读、从未执行；未安装 gitleaks / osv-scanner / semgrep / pip-audit / grype 中任何一个；未启动 Docker；未对任何真实部署发起请求。全部结论来自本地快照的静态阅读。

特别说明：上游自带的能力声明（README 与 SKILL.md 的自述）一律按源码证据重新验证，不把文档声称当作已实现能力。

---

## 2. 能力审计

### 2.1 能力矩阵

按真实能力条数计量，共 28 条。判定列只有四种值；`REUSE` 只覆盖抽象设计，不覆盖实现。

| 能力 | 上游实现位置 | 判定 | 治理与证据 |
|---|---|---|---|
| C01 两阶段信任边界（finder → judgment） | SKILL.md L1035–L1122 | ADAPT | 每个阶段跑在独立子代理里，产物是 JSON 而非对话；判断层只拿路径不拿推理。抽象设计可采纳：委托与判断必须由不同上下文承担。但上游自己写明 Boundary 2 不防 Boundary 1（D4），所以这不是完整答案，只是分层的一半 |
| C02 阶段间上下文卫生（下游只读上游结构字段，不读其 findings） | references/phase4-owasp.md L36–L95 | REUSE | 可独立实现的反锚定纪律：下游阶段可以复用上游的结构事实，但不能继承上游的判断。SourceLore 的 Claim/Evidence 模型应同样约束：证据可继承，结论不可继承 |
| C03 Surface Gate：非生产面确定性抑制 + 置信度分级 + 封顶 | references/phase5-validate-and-poc.md L471–L530 | REUSE | glob 匹配 surface_map.non_production[].pattern；test/fixture + high 立即终止；example/demo + high 同样；medium 照常验证但封顶为低置信。确定性前置门能省掉整条验证链开销，且明确区分代码有漏洞与漏洞不在生产面。不依赖任何模型判断 |
| C04 Boundary Gate：pre-auth 可达性门 + auth_coverage 映射 | references/phase5-validate-and-poc.md L608–L692 | ADAPT | 门形状可采纳，但依赖 Phase 2 产出的 auth_coverage，而该映射本身是模型生成的。SourceLore 若采纳，必须把 auth 覆盖判定做成确定性抽取 |
| C05 四节点数据流契约（entrypoint → hops → sink，逐跳 file:line） | references/phase4-owasp.md L367–L460；phase5 L532–L555 | REUSE | 全篇最可迁移的证据形态：把这里有注入变成这条链从哪进、经哪几跳、在哪落地。SourceLore 的 evidence_refs 可直接采用同构结构 |
| C06 不可验证即判否 | references/phase5-validate-and-poc.md L532–L555 | REUSE | 若无法建立逐边界 entrypoint→sink 链，结论为 FALSE_POSITIVE；P4 记录的 hop 找不到即记 P4 不准确并重定位。把说不清显式归入否定，而非留在悬置状态 |
| C07 验证状态机与 report_tier 的固定映射 | references/phase5-validate-and-poc.md L692–L747 | ADAPT | 九态逐一映射到 report_tier，映射固定不可重算。粒度可借鉴，但九态偏多且与 SourceLore 四态不同构，需压缩映射 |
| C08 动态证据升级阶梯 + 每级独立同意 | SKILL.md L400–L618；phase5 L1003–L1075 | ADAPT | 被动 curl GET → 无头 Chromium → docker run，每级各自一道确认门，浏览器单独同意（理由是 sandbox-escape）。阶梯本身对，但默认路径含 docker run 不受信代码（D3），SourceLore 只采纳 curl 一级 |
| C09 环境失败绝不改判 | references/phase5-validate-and-poc.md L795–L833；L1421–L1444 | REUSE | Docker/Playwright 不可用、构建失败、确认被拒，一律不改 validation_status，只记中性备注。不变量级正确性约束：工具没跑起来不是证据 |
| C10 动态否证只降级到人工复核 | references/phase5-validate-and-poc.md L795–L833 | REUSE | clean RUNTIME_NOT_CONFIRMED 只能把 CONFIRMED 降到 NEEDS_RUNTIME，绝不直接判否。代码级证据与运行时证据冲突时仲裁权归人 |
| C11 两份独立控制 + 结构性构造门 | SKILL.md L618–L700；phase5 L120–L146 | REUSE | --poc 只持久化不执行；--runtime 只执行不持久化；无标志时连 pocs/ 目录都不创建；被拒绝的 finding 永不构造利用。本轮最强的安全设计 |
| C12 失效安全门控（fail-safe gating） | references/phase4-owasp.md L100–L120 | REUSE | 进入 low_confidence_signals / truncated_signals 即强制 detection_confidence: reduced；A03/A08 在低置信否定下绝不跳过。不依赖模型的可独立实现规则 |
| C13 Semgrep 三层规则集 + 本地缓存优先 + 废弃包移除 | references/phase4-owasp.md L193–L363 | ADAPT | 常开安全规则 + 语言包 + 框架包；刻意避开 --config=auto；优先本地缓存；显式移除废弃包并留验证说明；gin/echo/fiber 无覆盖则诚实登记缺口。可迁移的是规则工程纪律，具体包名与缓存路径不可复用 |
| C14 族扫描与诚实否定 | references/phase4-owasp.md L801–L848 | REUSE | 每个确认发现都要在同类文件族里扫同一 sink 模式，逐文件确认或排除；类级 confident negative 要求该族全部文件至少被 grep 过，否则降为 reduced 并点名未读文件。对系统性覆盖缺陷的直接修复 |
| C15 依赖可达性三态 + 保守默认 + KEV 下限 | references/phase3-dependencies.md L271–L364 | ADAPT | REACHABLE / UNREACHABLE / INDETERMINATE；transitive+runtime 默认 INDETERMINATE；路径工具失败当作 transitive+runtime；KEV 无视可达性设 HIGH 下限；有界搜索不得产出 UNREACHABLE。三态与保守默认可采纳 |
| C16 P3b 有效严重度与优先级分离 | references/phase3-dependencies.md L271–L364 | REUSE | effective_severity 由可达性 + CVSS + EPSS + KEV 联合决定，priority P0–P3 与报告严重度解耦。技术严重度与处置优先级分离，本轮少见的正确分层 |
| C17 密钥打码与原始输出清理 | references/phase1-secrets.md 全文 | ADAPT | redacted_value 取前 4 后 3；仅 HIGH 进 findings；不验证密钥；处理完删原始输出。打码规则可采纳，但删除是尽力而为且不覆盖 P3 原始 JSON（D11、D12） |
| C18 成本报告（时长 + token 估算） | SKILL.md L1273–L1313；各 reference 的 Cost Report 节 | ADAPT | 每阶段一行，格式固定，严格限于时长与 token，不做文件读写埋点。把一次运行的代价做成可比较的结构字段，方向对，但纯 chars/4 估算无独立核验（D15） |
| C19 多仓库拓扑与跨服务合成 | references/phase0-topology.md 全文；phase7-synthesis.md L55–L162 | REIMPLEMENT | 形态可借鉴，但 SourceLore 的跨源关系不是服务拓扑，而是知识单元之间的依赖与矛盾。直接搬用会产生第二套关系模型，违反单一模型约束 |
| C20 延迟裁决与跨仓库解析 | references/phase7-synthesis.md L162–L219 | ADAPT | PENDING_CROSS_REPO_VALIDATION 占位，后续用其他仓库证据解析；解析必须引用新增跨仓证据，不得复述原论断。单仓库无法裁决是合法中间态 |
| C21 模型分层（Deep / Standard） | SKILL.md L130–L330 | REJECT | 仅 Phase 2 用 Deep 层，其余全部 Standard；只按家族别名 opus/sonnet/haiku 派发。整条机制绑死在 Claude 家族与 Agent 工具上，无法迁移到 DSH |
| C22 Skill/Agent 指令安全（OWASP LLM Top 10） | references/phase-llm-security.md 全文 | ADAPT | 对 skill/instruction 文件做 LLM01/02/05/06/07/08 检查，要求 source→transformation→sink 可追踪。检查清单可采纳为 SourceLore 自审项（它自己就是 agent 产物），但激活条件偏窄 |
| C23 供应商采纳审计模式 | SKILL.md L733–L793；phase6 L618–L776 | ADAPT | --vendor 输出采纳风险裁决 + 条件 + 工具实际行为 + 采纳方补偿控制。报告形态与 SourceLore 的上游审计目的最接近，但其中锁模型层与跳过阶段的部分不采纳 |
| C24 PR diff 增量审查与移除控制回归检查 | references/pr-review.md L50–L250 | REUSE | 三点 diff 取 merge base；对每条被删除行匹配安全控制模式，若等价控制未找到则记 regression: true + removed_control。全量扫描结构性看不到的一类问题，判据确定 |
| C25 一阶段一文件的产物契约 | SKILL.md L1122–L1206；phase6 L7–L58 | REIMPLEMENT | 每个阶段写自己的 JSON，报告层只聚合；跳过阶段在输出里显式缺失而非空对象。但没有统一实体模型，也没有新鲜度与失效语义 |
| C26 新鲜度与失效判定 | 缺失 | REIMPLEMENT | 全仓库无任何知识或结论是否仍有效的概念。上游做的是对某个 commit 扫一遍，产物与 commit 绑定但没有回取与失效机制。SourceLore 的核心恰好在这里 |
| C27 密钥/数据分级 | references/phase1-secrets.md | REIMPLEMENT | 仅分 HIGH/MEDIUM/LOW 三档，分级依据写死在判据里，无字段化分级，无法表达哪类内容可进报告、哪类只能留在快照 |
| C28 一键安装外部扫描器 | scripts/setup.sh 全文 | REJECT | 用 brew / go install @latest / pip --break-system-packages / curl 管道安装六个工具，无版本钉定、无校验和。本仓库最直接的供应链风险面 |

统计：REUSE 11 / ADAPT 11 / REIMPLEMENT 4 / REJECT 2 = 28 项。

### 2.2 七个指定分析轴

**轴 A｜技术栈与信任边界。** 仓库本身是提示词工程，没有编译产物；技术栈指它调用的外部工具链：gitleaks、osv-scanner、semgrep、npm audit、pip-audit、grype、jq、curl、Docker、Playwright/Chromium。信任边界有两条，上游自己写明：边界 1 是目标仓库内容到各阶段代理，边界 2 是 finder 输出到判断层。关键在于上游同时写明 Boundary 2 does not protect against Boundary 1 attacks（`references/phase5-validate-and-poc.md` L17–L60）。也就是说判断层自己读源码，它和发现层一样暴露在仓库内提示注入之下。两条边界被并列呈现，实际只有一条对注入有效，而有效的那条保护的是判断不被发现污染，不是判断层不被注入。

**轴 B｜密钥。** 本仓库自身不含任何凭据：16 文件检索无 API key、token、私钥、连接串。它处理密钥的方式是 Phase 1：gitleaks 全历史扫描加两条 `grep -rEn` 补充，仅 HIGH 置信度进 findings，redacted_value 取前 4 后 3，不验证密钥真伪。缺陷在两处：原始扫描输出靠处理完执行 `rm -f` 清理，失败仅告警（D11）；Phase 3 的原始供应商 JSON 完全没有清理步骤（D12），而 `.security-review/` 会被 `--output` 整体复制出去。

**轴 C｜依赖漏洞。** Phase 3 按生态调 osv-scanner 与 npm audit / pip-audit；Phase 3b 做可达性分析，三态为 REACHABLE / UNREACHABLE / INDETERMINATE，transitive+runtime 默认 INDETERMINATE，路径工具失败当作 transitive+runtime，KEV 无视可达性设 HIGH 下限，降级不低于 LOW，并明确禁止用有界搜索产出 UNREACHABLE。这套三态与保守默认是可用的；问题在记录形态——reachable 字段在 P3 恒为 null，由 P3b 回填，中间态在产物里不显式，读一份 P3 产物无法看出还没判还是判不了。此外本仓库依赖的外部工具本身来自 setup.sh 的无钉定安装（D2）。

**轴 D｜OWASP Top 10。** 分三层：确定性规则（Semgrep 三层规则集，刻意避开 `--config=auto`）、模型推理（Source→Sink 追踪、逐类检查块）、需独立核验项（OWASP API Top 10 仅在 is_api_only 或发现 `/api/` 路由时启用）。失效安全门控把 low_confidence_signals / truncated_signals 转成 detection_confidence: reduced 并强制 A03/A08 在低置信否定下绝不跳过——但门控只覆盖这两类，A07/A10 条件于 tech-stack.json 的布尔，一个假否定会整类抹掉检查（D18）。全部静态探测都带 head 封顶（phase4 27 处），与它自己的族扫描纪律直接冲突（D5）。

**轴 E｜发现验证。** 这是本仓库最强的一层，也是本审计最主要的可采纳来源。四道确定性门：Surface Gate（非生产面加置信度分级加封顶）、Boundary Gate（pre-auth 可达性，且对 data_flow.entrypoint 为 null 的 finding 显式拒绝伪造路由）、不可验证即判否（无法建立逐边界链即判否）、环境失败绝不改判（工具没跑起来不是证据）。加上四节点数据流契约与九态验证状态机，构成一套完整的怎么不把扫描器输出当结论的机制。缺陷是九态与 SourceLore 四态不同构（C07），以及置信度轴与严重度轴在报告里混排（D13）。

**轴 F｜Skill / Agent 安全。** Phase 4b 按 OWASP LLM Top 10 检查 instruction 文件，覆盖 LLM01/02/05/06/07/08，要求 source 到 transformation 到 sink 可追踪，无法追踪即误报。检查清单质量不错，尤其 LLM07 的工具授权是否大于步骤所需与 LLM08 的子代理是否有权决定跳转哪些步骤。但激活条件偏窄：纯 skill 仓库才自动跑，混合仓库必须显式传标志。更关键的是本仓库对自身完全适用同一套判据，而它自己的编排层就把哪些阶段跑的决定权交给了 tech-stack.json 的一个布尔，并由级联静默改变（D9）。

**轴 G｜PR / 变更审查。** `--pr` 模式七步：三点 diff 取 merge base、廉价全仓结构上下文、限定范围的 auth/trust 上下文、diff 范围密钥扫描、diff 范围 OWASP 加移除控制回归检查、依赖检查、验证。回归检查是唯一只能靠 diff 得到的一类：对每条被删除行匹配安全控制模式，读 diff 后的完整函数确认等价控制是否仍在，不在则记 regression: true 加 removed_control。这条与 SourceLore 的增量知识机制取向一致，但复用方式必须是抽象契约而非代码——上游的 PR 模式与全量模式共用同一份 Phase 5 文件靠大段条件替换切换（D16），这种形态不应被继承。

---

## 3. 十二项风险核验

按 §4 指定的十二项逐条给源码证据与结论。判定只有三种：成立（源码支持该风险）、部分成立（有机制但不足）、不成立。

| # | 风险 | 判定 | 源码证据 |
|---|---|---|---|
| 1 | 默认执行不受信项目代码 | 部分成立 | `--runtime` 触发 Part 3 对目标仓库 docker build（Dockerfile 来自被审计仓库，RUN 指令在构建期执行）再 docker run。默认关闭、有确认门，但 `--yes` 在 CI 语义下直接跳过（D3、D19） |
| 2 | 默认安装第三方工具 | 成立 | README 的安装步骤就是 `bash scripts/setup.sh`；脚本用 brew / go install @latest / GitHub releases 下载 / pip3 install --break-system-packages / curl 管道执行装六个工具，无版本钉定、无校验和（D2） |
| 3 | 未授权动态漏洞验证 | 部分成立 | 动态验证有两道同意门（Docker 构建运行门、浏览器升级门），但 `--yes` 一次覆盖全部门；`--verify-deployment` 发往真实 URL 的 GET 也在同一标志下自动确认（D19） |
| 4 | 自动构建/执行 PoC | 不成立 | 两份独立控制：`--poc` 只持久化不执行，`--runtime` 只执行不持久化；都不设时连 pocs/ 目录都不创建，poc_skipped 为 true；构造点被钉在验证之后，被拒绝的 finding 永不构造利用（C11） |
| 5 | 对真实服务发起主动网络请求 | 成立 | `--verify-deployment` 发一次被动 GET 并附带 TLS/安全头态势探测（含额外握手与 TLSv1.0 探测）；Phase 3 外联 EPSS/KEV；Semgrep 在本地缓存缺失时回落到 registry 拉规则。全部只读，但确属对外部服务的主动请求 |
| 6 | 把扫描器输出当已确认漏洞 | 部分成立 | 机制上明确反对：边界 2 把 finder 输出当不可信、P5 从零重读源码、P4 的 hop 找不到即记 P4 不准确、无完整链即判否、Semgrep 结果只作种子。缺陷在传导：限定语（无全程序污点引擎）留在中间 JSON，报告层可以只显示未发现注入（D14） |
| 7 | 报告写入密钥或私有源码 | 部分成立 | findings 里打码（前 4 后 3），但原始 gitleaks 输出靠事后删除且失败仅告警（D11）；P3 原始 JSON 无清理（D12）；PoC 脚本有强制打码要求 |
| 8 | 混淆安全评级与未校准的模型置信度 | 成立 | contextual_severity（环境档位调整）与 CONFIRMED_LOW_CONFIDENCE（置信度封顶）落在同一张表的不同列，且 Phase 6 被明令不得重算、禁止在报告里解释两轴差别（D13）。`--verify-deployment` 的 gated 判定是启发式，却直接驱动减一档严重度（D20） |
| 9 | 只适用于 Claude Code、无法迁移到 DSH | 成立 | 安装路径 `~/.claude/skills/`、命令落 `.claude/commands/`、模型分层只认 opus/sonnet/haiku 家族别名、命令文件自陈 not fully standalone（D6、D7） |
| 10 | 工具缺失时仍声称完整审计 | 部分成立 | setup.sh 结尾明写 phases will run in degraded mode，README 写 a missing tool just degrades the matching phase；各阶段有各自降级路径。但降级只写进中间 JSON，报告的 Skipped Phases 段可选，且 `--yes` 下自动跳过级联静默改变阶段集合（D9） |
| 11 | 各阶段数据格式、失败态与权限边界不一致 | 成立 | P2 的缺字段为硬错误与 SKILL.md 的阶段失败绝不中止互斥（D8）；PR 模式与全量模式共用同一份 P5 靠条件替换（D16）；九态与四态映射靠 report_tier 单点承载；各阶段自报成本无合计校验（D15） |
| 12 | 无许可证是否禁止复制具体实现 | 成立 | 见 §1.4。license 为 null 加 /license 404 加全文零许可声明，等于默认著作权下保留全部权利，禁止复制与改编 |

十二项里 6 项成立、5 项部分成立、1 项不成立。不成立的那项（风险 4）在核验后被证伪——上游在这条上做得确实比预期好，两份独立控制的拆分是本轮最值得采纳的设计。

---

## 4. 缺陷清单

本节是缺陷 ID 的唯一权威源。JSON 的 defects 与本表逐条对应。

| ID | 严重度 | 文件 | 位置 | 问题 | 修复方向 |
|---|---|---|---|---|---|
| D1 | blocker | 整仓 | 仓库根目录；全部 16 个文件 | 无任何许可证。GitHub API 返回 license 为 null，/license 端点 404，16 个文件全文检索 LICENSE / Copyright / SPDX / © 命中 0。仓库内容（SKILL.md 各阶段提示词、四个 references 的规则原文、setup.sh 与命令模板）在默认著作权下保留全部权利，不存在可复制或可改编的授权 | 上游源码、提示词、规则原文与模板一律不得并入 SourceLore；本轮只提取抽象设计思想，落点写成独立实现的契约。许可证状态作为独立字段记录，不得被 REUSE 判定覆盖 |
| D2 | blocker | scripts/setup.sh | scripts/setup.sh 全文 | 标准安装步骤就是静默安装第三方工具：install_gitleaks 走 brew 再 go install @latest 再从 GitHub releases 下载 tar 包解压到系统目录；install_osv_scanner / install_semgrep / install_pip_audit 用 pip3 install --break-system-packages 后回退普通 pip；install_grype 用 curl 管道执行远程 install.sh。全程无版本钉定、无校验和验证、无来源签名检查，且默认写入系统目录 | SourceLore 不采纳该脚本任何一行。若未来需要外部扫描器，必须钉定确切版本、校验发布物哈希、安装到隔离前缀、绝不使用管道执行。工具缺失时应显式降级并在产物中标注，而不是自动补装 |
| D3 | blocker | SKILL.md 与 references/phase5-validate-and-poc.md | SKILL.md L618–L700；phase5 L1003–L1167 | 默认路径会构建并运行不受信项目代码。`--runtime` 触发 Part 3：对目标仓库执行 docker build（Dockerfile 来自被审计仓库本身，其 RUN 指令在构建阶段执行），随后 docker run 起服务并发起利用请求。加固标志只加在 docker run 上，构建阶段不受这些限制。同意门存在，但 `--yes` 在 CI 语义下会直接跳过 | SourceLore 拒绝任何默认执行不受信代码的路径。动态证据最多到被动只读 GET，且必须默认关闭、显式开关、每级独立确认、无一键绕过 |
| D4 | high | references/phase5-validate-and-poc.md | phase5 L17–L60；SKILL.md L1035–L1122 | 上游自己承认防护不完整：边界 2 明确写着不防边界 1 攻击。Phase 5 作为判断层仍然读目标仓库源码，因此与 Phase 2/4 同样暴露在仓库内提示注入之下。两条边界被并列呈现，但实际只有一条对注入有效，且有效的那条保护的是判断不被发现污染，不是判断层不被注入 | SourceLore 必须把读取不受信内容本身作为风险面单独建模：读到的内容一律标记为数据、提取结论与执行指令分离、注入文本作为 finding 而非指令。不能靠分层代理解决 |
| D5 | high | references/phase4-owasp.md 及其他 reference | phase4 全文；统计 phase4 有 29 处 grep / 27 处 head 封顶，phase2a 15/15，phase2 3/3，phase5 7/6 | 全部静态探测都带 head 封顶。命中集超过上限即静默截断，不记录被截掉了多少。大仓库里族扫描会漏掉尾部文件，而 P4 的诚实否定纪律要求覆盖整个文件族——两者直接冲突：封顶后的 grep 无法证明族内全部文件被检查过 | 任何有界搜索必须在产物里显式记录截断（命中总数与已检查数），并因此禁止产出 confident negative。SourceLore 的否定结论必须携带搜索边界证据 |
| D6 | high | SKILL.md | SKILL.md L130–L330；L162；L205–L213 | 模型分层绑死在 Claude 家族：只认 opus / sonnet / haiku 别名，Phase 2 必须 Deep 层，交互式环境只暴露通用别名，解析结果记入 run-metadata.json 的 fallback_notes。对非 Claude Code 宿主没有任何等价机制，也没有降级路径 | SourceLore 不复制模型分层。按任务复杂度与工具可用能力选路，并把实际使用的模型写入产物；不得把某个供应商的某一层当作阶段定义的一部分 |
| D7 | high | scripts/repo-security-review-command.md 与 SKILL.md | command L1–L5；SKILL.md 全文；README L15–L28 | 宿主路径硬编码：安装位置是 `~/.claude/skills/`，命令文件要求保存到 `.claude/commands/`，且文件头自陈 not fully standalone。整个编排层的可移植性依赖 Claude Code 的 skill/command 加载约定，迁移到其他宿主需要重写编排层而非改配置 | SourceLore 的编排层必须与宿主解耦：阶段定义、输入清单、产物路径全部显式声明，不依赖任何宿主的自动发现约定 |
| D8 | medium | references/phase2-architecture.md 与 SKILL.md | phase2 L57–L92；SKILL.md L1515–L1523 | 失败语义自相矛盾。phase2 的 Step 0 规定缺字段是硬错误，而 SKILL.md 的 Error Handling 规定单阶段失败绝不中止整条流水线。同一份流水线里同一个阶段的失败有两种互斥处置，且没有说明哪种优先 | 阶段失败必须只有一个权威语义。SourceLore 采用：阶段失败则该阶段产出的 Claim 全部不写入，任务状态记 failed，下游在产物中标注上游缺失，绝不静默继续也不整体中止 |
| D9 | medium | SKILL.md | SKILL.md L940–L995 | 自动跳过级联在 `--yes` 下静默改变阶段集合。is_skill_repo 为真时 Phases 3/4/5 全跳、只跑 4b；`--yes` 直接静默确认。报告因此可能声称审计完成而实际从未做依赖与代码层检查，且跳过决定由 tech-stack.json 的一个布尔驱动，该布尔本身来自模型判断 | 阶段集合的任何变化必须写进产物并在报告顶部声明。完成只能指所声明的阶段集合全部完成，不能指流水线跑到了最后一行 |
| D10 | medium | SKILL.md | SKILL.md L1444–L1640；各 reference 的 Final Response 节 | 存在两条会泄露发现的聊天通道：编排器的一行进度更新，与各阶段的 final response。各 reference 都写了禁令，但 SKILL.md 的 Final Step 又明确要求把完成的报告读回聊天。禁令与要求在同一仓库里并存，边界靠模型自觉 | 产物与聊天必须物理分离：聊天输出只允许包含产物路径与状态，禁止包含任何承载结论的文本。这条要由工具层强制，不靠提示词 |
| D11 | medium | references/phase1-secrets.md | phase1 全文 | 原始扫描输出删除是尽力而为：处理完执行删除，失败仅告警。若删除失败，未打码的原始命中集留在 `.security-review/` 里，而该目录随后会被 `--output` 复制出去。打码规则只作用于 findings 字段，不作用于磁盘上的原始文件 | 原始扫描输出不应落盘，或必须落在内存/临时路径并在同一进程内消费。打码不能只作用于展示层 |
| D12 | medium | references/phase3-dependencies.md | phase3 全文 | 原始扫描器 JSON（npm audit 原始输出、osv 输出）写入 `.security-review/` 且无清理步骤。这些文件包含完整依赖树与公告原文，随 `--output` 一并外发。与 D11 是同一类问题的另一半：P1 有不彻底的清理，P3 完全没有 | 中间产物与交付产物必须分目录，中间产物默认不持久化；确需保留的必须显式声明并纳入清理 |
| D13 | medium | references/phase5-validate-and-poc.md 与 phase6 | phase5 L1444–L1631；phase6 L103–L152 | 置信度与严重度两根轴在报告里混排。contextual_severity 是确定性档位调整，CONFIRMED_LOW_CONFIDENCE 是置信度封顶，两者落在同一张表的不同列，读者容易把被环境软化误读为不确定或反之。Phase 6 被明令不得重算、只能直接读取，但两轴语义差别没有在报告里解释，且明确禁止解释 | 置信度与严重度必须是两个独立字段，且报告必须同时展示两者的来源。禁止用不解释来避免混淆 |
| D14 | medium | references/phase4-owasp.md | phase4 L265–L365；L930–L936 | 无全程序污点引擎，上游自陈干净的 Semgrep 结果只意味着没有规则命中的 sink，不意味着没有可注入的数据流。这条限定写在 Phase 4 的说明里，但没有对应的产物字段强制把它带到报告层——报告可以只显示未发现注入，限定语留在中间 JSON 里 | 限定语必须随结论一起上行到最终产物。每条 Claim 都带 limitations 字段正是为此；静态扫描的结论必须携带本结论的搜索边界 |
| D15 | medium | SKILL.md | SKILL.md L1273–L1313 | 成本报告全部是估算：token 按字符数除以四推算，时长按阶段时间戳相减，无 tokenizer、无独立核验、无与供应商账单的对照。该字段被设计成贴回来做成本分析的输入，但精度未知且误差方向未知 | 自报成本必须标注为估算并说明估算方法；不得进入任何自动化决策 |
| D16 | medium | references/phase5-validate-and-poc.md 与 pr-review.md | phase5 L60–L146；pr-review L252–L300 | PR 模式与全量模式共用同一份 Phase 5 文件，靠大段条件替换切换行为：文件名替换、Part 2/3 整体禁用、Step 0.4/0.5 禁用、Axis 2 永不适用。两套语义写在同一份文档里，任何一次修改都可能只改到其中一套 | 不同模式应拆成不同的产物契约与不同的执行文件，共享部分抽成显式引用的公共契约，而不是用条件段落在同一文件内分支 |
| D17 | medium | references/phase4-owasp.md | phase4 L193–L363 | Semgrep 规则来源存在静默回落：优先本地缓存，缺失则回落到 registry 拉取。同一份代码在不同机器上可能用不同版本的规则集，而产物里只有来源标签，没有规则集指纹 | 规则集必须有内容指纹并写入产物；无指纹的结果不可比较。SourceLore 若引入任何外部规则，必须锁版本加记指纹 |
| D18 | medium | references/phase2a-tech-stack.md 与 phase4 | phase2a L240–L300；phase4 L100–L120 | 失效安全门控只覆盖 A03/A08：A10（SSRF）与 A07（认证）条件于提前算出的布尔，而这两个布尔可能来自无清单证据的低置信否定。一个假否定会整类抹掉对应检查，且不进低置信信号清单 | 级联条件本身必须参与失效安全：任何门控布尔若来自低置信信号，其下游整类检查一律降级运行而非跳过 |
| D19 | low | scripts/repo-security-review-command.md | command L256–L360 | `--yes` 一键绕过全部三道同意门（输出复制门、Docker 运行时门、部署验证门），以及纯 skill 仓库的自动跳过级联。文档说明这是 CI 预期行为，但同一个标志同时覆盖复制文件与执行不受信代码两类完全不同的风险 | 同意门必须按风险类别分别授权，不得用单一布尔覆盖全部。执行不受信代码的授权在任何模式下都不得自动化 |
| D20 | low | SKILL.md | SKILL.md L400–L618 | 部署验证的 classification 是启发式：由 401/403、身份提供方主机名模式、同源路径子串、正文关键词共同判定为 gated。这些启发式没有校准数据，误判会直接抬高或压低整批 finding 的严重度轴 | 任何影响严重度的分类必须是可审计的确定性事实，或明确标注为启发式且不参与严重度计算 |

统计：blocker 3 / high 4 / medium 11 / low 2 = 20 项。三个 blocker 是 D1、D2、D3。

三个 blocker 有共同的形状：它们都不是功能没做，而是做了但边界不成立。D1 是没有授权却提供整套可复制的方法论；D2 是把装工具做成默认路径且不钉版本；D3 是把跑不受信代码做成一条可选但其同意可被 CI 标志一次性绕过的路径。其余 high 与 medium 大多是这三条的下游后果。

---

## 5. 可复用能力与融合落点

### 5.1 最有价值的机制

按可迁移性排序，前四条是本轮真正的收获。

**一、四节点数据流契约。** 注入类 finding 必须给出 entrypoint（HTTP 方法加路径，或 CLI 参数/环境变量/文件读取作为输入点，file:line）、hops（每跨一次文件边界一条，逐条 file:line）、sink（精确表达式，file:line）。同函数内 hops 为空；任一跳跨文件则标记 cross_file；跨文件边界却缺 hop 的声称被明确判为不可验证。这把这里有注入变成一条可被第二个上下文独立复核的链。SourceLore 的 evidence_refs 应采用同构结构：证据不是某文件某行，而是从哪进、经哪几跳、在哪落地。

**二、确定性前置门加置信度封顶。** Surface Gate 与 Boundary Gate 都是先判面再判洞：非生产面加高置信直接终止，不进验证链；中置信则照常验证但结果封顶为低置信。两条门各带一句关键纪律：绝不因为 finding 严重就跳过门；门不是误报判定（非生产面与误报严格区分）。这套形状可以直接独立实现，且不依赖任何模型判断。

**三、环境失败绝不改判，动态否证只降级到人工复核。** 工具没跑起来、构建失败、确认被拒，一律不改判定状态；干净的运行时否证最多把确认降到需人工复核，绝不直接判否。这与 SourceLore 不变量同源，本轮确认上游独立得出同一结论——两处独立收敛，说明这是不变量级而非风格选择。

**四、族扫描与诚实否定。** 每个确认发现都要在同类文件族里扫同一 sink 模式，逐文件确认或排除；类级确信否定要求该族全部文件至少被 grep 过，否则降为降低置信并点名未读文件。上游给的失败案例极准：读了 curl 包装器就宣布 SSRF 确信无，而同目录的 wget 包装器没读——族里一个成员没读，整个类的确信就作废。

### 5.2 采纳摘要

这不是第二张能力矩阵，只是把落点按进哪个层重排。第 1 列是层名，第 2 列才是能力 ID。

| 落点层 | 关联能力 | 采纳形态 |
|---|---|---|
| 证据契约层 | C05 C06 C14 | 四节点数据流加不可验证即判否加族扫描留痕，三条合并成 evidence_refs 结构与否定结论的覆盖面字段 |
| 验证门层 | C03 C04 C12 C18 | 确定性前置门（面门加边界门）、失效安全门控、条件布尔参与失效安全。全部由脚本判定，不进模型推理 |
| 不变量层 | C09 C10 | 环境失败不改判；运行时否证只降级到人工复核。并入既有不变量，不新增条目 |
| 风险控制层 | C11 C17 | 构造与执行拆成两个互不蕴含的开关；原始扫描输出不落盘。若做动态验证必须照此拆分 |
| 增量审查层 | C24 C20 | PR diff 的移除控制回归检查；跨源无法裁决时记中间态并要求新增证据才能解析 |
| 报告纪律层 | C23 C16 | 供应商裁决式报告结构（敢不敢用加需要什么补偿控制）；有效严重度与处置优先级分成两个字段 |
| 明确不采纳 | C19 C21 C25 C26 C27 C28 | 服务拓扑合成、模型分层、一阶段一文件的产物契约、上游完全没有的新鲜度机制、非字段化的密钥分级、一键安装 |

### 5.3 不能采纳的

- 任何上游源码、提示词原文、规则原文、模板（D1）。
- `setup.sh` 的任何一行（D2）。
- 默认执行不受信代码的路径与一键绕过（D3、D19）。
- Claude 家族模型分层与 Claude Code 宿主约定（D6、D7）。
- PR 模式的条件替换式复用（D16）——形态本身就该被拒绝，不只是实现。

---

## 6. 独立的 SourceLore 安全分析契约

这一节是本轮的主要产出。它不复述上游任何规则文本，只声明 SourceLore 自己要什么。

### 6.1 安全发现的最小记录

每条 finding 至少含十个字段，缺一不可。

| 字段 | 含义 | 约束 |
|---|---|---|
| finding_id | 稳定 ID | 与 claim id 同域，不复用任务 id |
| repository_id | 被审对象 | 与既有 upstreams 账本一致 |
| source_commit_sha | 40 位完整 Git Commit SHA | 短 SHA 不得入库 |
| category | 漏洞类别 | 不沿用上游 O-XXX / L-XXX 前缀体系 |
| affected_component | 受影响组件 | 组件粒度而非文件粒度 |
| evidence_refs | 证据引用 | 四节点结构：entrypoint / hops / sink，逐跳带 path、line、content_hash |
| verification_status | 四态 | candidate / verified / rejected / insufficient evidence |
| severity | 严重度 | 与置信度分离，见 6.3 |
| limitations | 本结论的边界 | 必填。静态结论必须写明搜索边界；无污点引擎即写无污点引擎 |
| remediation_summary | 修复方向 | 一段话，不写代码 |

### 6.2 四态与五类陈述的对应

SourceLore 用自己的四态，不照抄上游九态。五类陈述与四态的映射是固定的：

- 观察到的源码事实 → 不是 finding。进 Evidence，不进 finding 表。
- 规则检出的风险候选 → candidate。扫描器输出永远停在这里。
- 未证实的模型推断 → insufficient evidence，不是 candidate。区分点在证据强度：候选有规则命中，推断只有模型叙述。
- 有证据的安全发现 → verified。要求四节点链完整到 file:line，且限制条件已写进 limitations。
- 证据不足或不适用 → insufficient evidence。这是一个成功结果，不是失败。

rejected 只有一个来源：证伪。被证伪的 finding 必须留证伪证据，且不能靠没找到来证伪——无完整链只归 insufficient evidence。

### 6.3 严重度与置信度必须分离

这是对 D13 与 D20 的直接回应。SourceLore 的做法：

- severity 只由技术事实决定，不由部署环境、认证门、扫描置信度调整。
- 环境信息（是否公网可达、是否被认证门挡住）单独记在 context 字段，作为阅读辅助，不参与 severity 计算。
- 置信度（verification_status 加 limitations）是另一个轴，永不与 severity 合成一个数字。
- 任何启发式判定（例如这个部署看起来有 SSO）必须标注为启发式，且不得参与 severity。

理由：两个轴的混淆无法在阅读层修复，只能在记录层分离。上游选择在报告里不解释，这不是解决方案。

### 6.4 能力边界声明

SourceLore 的安全分析不承诺以下任何一项：

- 不承诺静态分析可以发现全部漏洞。静态分析能给出的是规则命中的 sink 与人工追踪到的链，不是不存在注入数据流。
- 不承诺覆盖率。任何本类未发现问题的结论必须携带搜索边界（哪些文件被扫过、哪些被截断、哪些未读）。
- 不承诺动态验证。没有真实执行过 PoC 的结论一律标 NOT_RUN，不得写成通过动态安全测试。
- 不承诺跨仓库可达性。单仓库内无法裁决的问题记 insufficient evidence 并写明缺的那个事实，不猜。

---

## 7. 安全流水线各阶段的数据契约

上游的阶段集合与其产物，按契约是否成立评估，而不是按有没有这个阶段。

| 阶段 | 上游产物 | 契约评估 |
|---|---|---|
| P0 拓扑（仅多仓） | service-topology.json | 结构完整（服务、端口、入站认证、出站连接、共享环境变量、信任边界缺口、置信度、来源）。但它是服务拓扑不是知识关系，SourceLore 不采纳该形态（C19） |
| P1 密钥 | phase1-secrets.json | 打码规则明确，仅 HIGH 进 findings，不验证真伪。原始输出清理不彻底（D11） |
| P2 架构 | phase2-architecture.json，含 coverage / auth_coverage / surface_map | 是下游三道门的输入源。coverage 的全量记账纪律质量高；auth_coverage 的置信度分级可用，但取值本身来自模型判断 |
| P2a 技术栈 | tech-stack.json | 唯一结构输入，字段多且带检测低置信记账。缺陷是无清单证据的假值只记入低置信信号清单，而其下游整类检查可能直接跳过（D18） |
| P3 依赖 | phase3-cves.json | reachable 恒为 null 待 P3b 回填；enrichment 有 EPSS/KEV 两个失败态，诚实。原始 JSON 无清理（D12） |
| P3b 可达性 | phase3b-reachability.json | 三态加保守默认加 KEV 下限加降级下限，规则完整。有效严重度与优先级两字段分离，是本轮少见的正确分层（C16） |
| P4 OWASP | phase4-owasp.json | 字段最丰富：已跑检查、低置信已跑检查、已跳过检查（带否定置信）、类级否定（带未检查文件）、findings（含数据流、面类型、检测置信、族扫描留痕）。空字段省略规则明确。是 SourceLore 最该参考的产物形态 |
| P4b LLM 安全 | phase-llm-security.json | poc_needed 恒 false，明令不进 P5 验证。误报段独立存在。激活条件偏窄 |
| P5 验证 | phase5-validated.json 加 phase5-pocs.json | 增量写入（每处理完一条立即读改写）——这是对长任务上下文丢失的正确应对，值得单独采纳。九态加报告层固定映射，理由字段归属规则精确到字段级 |
| P6 报告 | final-report.md / pr-report.md / vendor 报告 | 四种报告结构；需复核与误报各自成段，后者总是包含；不重算校准只读字段。缺陷是两轴混排不解释（D13） |
| P7 合成（仅多仓） | system-findings.json 加 system-report.md | 五类跨服务漏洞加延迟裁决解析（要求新增证据，禁止复述原论断）。形态不适配 SourceLore（C19、C20） |

契约层面的普遍缺陷在 D8、D9、D15、D16 四条：失败语义互斥、阶段集合可静默改变、自报成本无核验、模式切换靠条件替换。

---

## 8. DSH 兼容性

结论：不能直接迁移，需要重写编排层，可迁移的只有设计。

| 依赖项 | 上游用法 | DSH 现状 | 可迁移性 |
|---|---|---|---|
| skill 发现 | `~/.claude/skills/<name>/` | DSH 用 `~/.agents/skills/` 与项目级 skill 目录 | 需改写路径与发现机制 |
| 命令入口 | `.claude/commands/<name>.md`，靠 `$ARGUMENTS` | DSH 用 skill 工具与显式工具调用 | 需重写入口层 |
| 阶段隔离 | Agent 工具派生子代理，Deep/Standard 分层 | DSH 用 subagent / workflow，无同构分层 | 隔离机制可重建，分层不可迁移（C21） |
| 模型解析 | 家族别名 opus/sonnet/haiku | DSH 走 provider/model 显式路由 | 不迁移（D6） |
| 产物路径 | `{repo_path}/.security-review/` | 无冲突，可原样采用 | 可迁移 |
| 外部工具 | gitleaks / semgrep / osv-scanner / grype / Docker / Playwright | DSH 未安装，且按只读边界不安装 | 不迁移（D2） |

能带走的：阶段间的产物契约形状、两阶段信任边界、四道确定性门、失效安全门控、增量写入纪律。不能带走的：宿主约定、模型分层、安装脚本、任何代码与规则文本。

---

## 9. 与 UPSTREAM-01–05 的交叉关系

分工保持不变，本轮不新增任何与 01–05 并行的数据模型。

| 对照 | 关系 |
|---|---|
| vs 01（源码事实与工程结构） | 01 提供确定性仓储事实抽取。本轮没有任何新的 collector 设计——上游的 Phase 0 与 P2a 都是从文件系统直接抽取，不构成第二套仓储事实层。明确不实现新的 GitHub Collector |
| vs 02（GitHub 历史与外部调研） | 本轮的外联只有 EPSS、KEV、Semgrep registry 三类只读查询，全部记录为审计事实而非知识。02 的外部调研结论权威性不变 |
| vs 03（产品模型 / Claim / Evidence / Unknowns） | 本轮的落点全部并入 03 的模型。C05 的四节点结构写进 evidence_refs，C06 的不可验证即判否写进四态中的 insufficient evidence，不新增实体。上游的九态验证状态机被压缩映射到四态，不产生第二套状态机 |
| vs 04（知识复用、历史、过时、跨会话检索） | 上游完全没有新鲜度机制（C26）。本轮确认了这一点，因此不提供任何关于 fresh/stale 的新判据，04 的既有结论不变。唯一可借的是 P5 的增量写入纪律（每完成一条立即落盘），它解决的是长任务中途丢失，与 04 的知识过时不同层 |
| vs 05（知识文档生成、确定性工具、人工审批、密钥分级） | 05 的密钥分级是字段化的，本轮上游的分级写死在判据里（C27）。因此密钥分级仍以 05 为准，本轮不提出替代方案。05 的产物契约与本轮无关 |

一句话：06 只往 03 的证据结构与验证纪律层落点，不侵入任何既有权威源。

---

## 10. SourceLore v1 采纳 vs 推迟

### 10.1 v1 采纳

五条，全部是抽象设计，全部独立实现。

1. 证据四节点结构（C05）——evidence_refs 从路径加行升级为 entrypoint/hops/sink，逐跳带 content_hash。这是 03 模型的字段扩展，不是新模型。
2. 确定性前置门（C03、C04）——面门与边界门，脚本判定，带置信度分级与封顶规则。
3. 不变量补充（C09、C10）——环境失败不改判、运行时否证只降级。并入既有不变量，不新增条目。
4. 否定结论的覆盖面字段（C14）——任何本类未发现必须携带被扫文件清单与未读文件清单，否则降为降低置信。
5. 增量写入纪律（P5 的逐条落盘）——长任务每完成一条立即读改写产物，不等批次结束。

### 10.2 推迟

| 项 | 推迟理由 |
|---|---|
| 动态验证（C08 的 curl 一级） | v1 不做任何动态证据。阶梯设计与同意门设计先记档，实现推迟到有真实的本地被测对象时 |
| Surface / Boundary 门的完整实现 | 依赖 surface_map 与 auth_coverage 两个结构输入，而这两个输入本身需要先建。v1 只落规则，不落自动分类 |
| PR 增量审查（C24） | 依赖 Git diff 增量管道，与 04 的增量知识机制合并设计，不在 v1 |
| 依赖可达性三态（C15、C16） | 需要生态解析器，v1 无依赖扫描能力 |
| 供应商裁决报告结构（C23） | 只在需要对外评估第三方时才有意义，v1 不产出 |

---

## 11. 测试状态

NOT_RUN。

- 上游 `scripts/setup.sh` 只读未执行。
- 未安装 gitleaks / osv-scanner / semgrep / pip-audit / grype 中任何一个。
- 未启动 Docker，未构建任何镜像，未运行任何容器。
- 未对任何真实部署发起 HTTP 请求。
- 未执行任何 PoC，未生成任何 PoC 文件。

本审计的 28 条能力判定与 20 条缺陷全部来自静态阅读。不得把本审计读作该工具已通过安全测试，也不得读作该工具不安全——两者的证据都不在本次审计范围内。

---

## 12. 遗留未决

| ID | 事项 | 状态 | 说明 |
|---|---|---|---|
| U1 | phase2-architecture.md 第七节之后的检查清单条目只读到要点 | 已登记 | 不影响能力判定：这些是检查清单条目，不构成机制 |
| U2 | phase5-validate-and-poc.md 五类 PoC 的代码模板未逐行通读 | 已登记 | 模板内容是构造示例，不改变能力判定；已确认该段含强制打码要求 |
| U3 | phase5-validate-and-poc.md 决策树、Docker 编排、浏览器驱动、就绪探测只读了边界段 | 已登记 | 结论已由同意门与加固标志段支撑；细节不改变风险判定 |
| U4 | phase5-validate-and-poc.md Dockerfile 合成八步只读了第一步 | 已登记 | 合成失败态已在失败模式参考中记录 |
| U5 | phase6-report.md 四种报告的完整模板只读了结构与裁决规则 | 已登记 | 报告模板属呈现层，不改变能力与缺陷判定 |
| U6 | phase7-synthesis.md 系统级 schema 与报告模板未逐字段读 | 已登记 | 该阶段整体判定为 REIMPLEMENT，不进入 SourceLore |
| U7 | pr-review.md 输出 schema 未逐字段读 | 已登记 | 已读验证交接与范围声明，足够支撑 C24 判定 |
| U8 | repo-security-review-command.md 阶段编排细节读到关键分支，未逐行 | 已登记 | 编排层整体判定为需重写（D7） |
| U9 | 上游 32 star / 7 fork 的真实使用情况与外部评价 | 未调研 | 本轮只做源码静态审计，不做生态调研（属 02 职责） |
| U10 | 无许可证状态下抽象设计思想的边界究竟多宽 | 需法务判断 | 本轮采取保守立场：不复述任何上游规则文本、不复制模板、不逐句改写；只描述机制形状并独立设计 |

九项已读未尽的都属于清单条目、模板内容、呈现层，不改变三类判定：能力有无、缺陷成立与否、可迁移性。U10 是实质未决，且无法由审计本身解决。

---

## 13. SHA 规范化

本轮起所有新记录使用 40 位完整 Git Commit SHA。两个概念语义不同，不得互换。

| 字段 | 值 | 含义 |
|---|---|---|
| upstream_pinned_sha | d5128b03d6a785bfb7c8be4139291f887c2a3215 | 被审计的上游提交 |
| audit_git_commit | 见 progress/TASKS.json 与 progress/STATE.json | 产生本审计的 SourceLore 提交 |

上游 SHA 不是本地 Git 对象，因此不能用 `git cat-file` 核验；核验方式是比对 `tree.json.sha`、本审计 JSON 的三处字段、以及 manifest 的 commit。

---

## 14. 验收

九项门禁逐条实跑，退出码为本轮真实执行结果，不是声明。

| # | 门禁 | 检查内容 | 退出码 |
| --- | --- | --- | --- |
| 1 | 上游 SHA 与快照匹配 | 四处 SHA 字段均为 d5128b03d6a785bfb7c8be4139291f887c2a3215，且等于 tree.json.sha 与 manifest commit | 0 |
| 2 | 全部证据路径与行号可解析 | 8 个 evidence 路径命中 8/8；20 条缺陷的文件路径与行号命中 20/20；文档内行号引用全部落在对应文件的实际行数内 | 0 |
| 3 | Markdown 与 JSON 一致 | 能力 28 项逐条比对（ID 与判定），11/11/4/2 两侧相同；缺陷 20 条 ID 与严重度逐条比对，3/4/11/2 两侧相同 | 0 |
| 4 | 无许可证处置有据 | license 状态为 none、API 字段为 null、端点 404、全文命中 0 四项一致；JSON 中复用范围记为设计层且不得复制上游文本 | 0 |
| 5 | 静态与动态不混淆 | test_status 为 NOT_RUN、dynamic_tests_run 为 false；全文对动态执行结果的肯定式断言共 0 处 | 0 |
| 6 | 前五个上游结论不变 | UPSTREAM-01–05 五份记录与 HEAD 零差异；本轮 TASKS.json 改动只落在 UPSTREAM-06 任务行 | 0 |
| 7 | 账本与真实 Git 状态一致 | STATE.last_verified_commit 对象存在；全部 git_commit 为 40 位且可解析；DONE 8 / PENDING 0 | 0 |
| 8 | 未执行上游代码、未装依赖 | 快照 16 个文件全部在 tree.json 登记，未登记 0、哈希不符 0；无缓存目录、无 .pyc、无 node_modules | 0 |
| 9 | 无敏感或未授权第三方内容 | 私钥 / 凭据字面量 / GitHub token / 云 AK / 家目录 / 内网地址命中 0；文档内无嵌入的上游源码块 | 0 |

---

## 15. 本轮不做

- 不执行 setup.sh，不安装任何上游依赖，不运行任何安全扫描器。
- 不启动 Docker 容器，不构建镜像，不生成或执行 PoC。
- 不扫描任何真实部署，不发起任何主动网络请求。
- 不复制上游源码、提示词、规则原文或模板进 SourceLore。
- 不实现新的 GitHub Collector、知识存储系统或报告证据模型。
- 不进入 M2 开发；本轮完成后停止，下一阶段是 M1-FUSION-GATE。
