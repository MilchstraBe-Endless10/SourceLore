# SourceLore 测试

本文说明 SourceLore 现有测试、验证方法、回归机制、已知环境依赖与冻结校验值。英文版见 [docs/en/TESTING.md](../en/TESTING.md)，事实、接口与状态与本文完全一致。

## 1. 测试组织

测试全部位于仓库 `tests/` 下，按目录用 Python 标准库 `unittest discover` 运行——测试**不依赖** pytest，也不要求顶层 `requirements.txt`。

目录分两类，运行方式必须区分：

- **包目录**（含 `__init__.py`）：运行时加 `-t .`，否则 discover 会把包内模块当成顶层模块，触发同名模块冲突或 `Start directory not importable`。
- **普通测试目录**（无 `__init__.py`）：运行时**不加** `-t .`。

混用两种运行方式会触发同名模块冲突或 "Start directory not importable"，这属于**运行方式问题，不是逻辑回归**。仓库顶层没有统一的 `pytest.ini` / `setup.cfg` 来规避这一点，因此必须逐目录运行。

### 1.1 目录清单（实测存在，含正确的 `-t .` 用法）

**包目录（加 `-t .`）：**

| 目录 | 目录 | 目录 |
|---|---|---|
| `acceptance_orchestration` | `blob_capture` | `bot_presentation` |
| `capture_maintenance` | `content` | `content_persistence` |
| `content_skill` | `js_ts_analysis` | `module_resolution` |
| `p6f_capture` | `product_acceptance` | `product_multirepo` |
| `renderer` | `research` | `skill_interface` |
| `source_analysis` | `ts_projects` | `views` |

**普通测试目录（不加 `-t .`）：**

`collector`、`evidence_claims`、`facts`、`lifecycle`、`runtime`、`storage`、`trust`

## 2. 运行方式

在工程根目录下执行（路径含括号与中文，shell 中务必加引号）：

```sh
# 包目录：加 -t .
python3 -m unittest discover -s tests/renderer -t . -v
python3 -m unittest discover -s tests/skill_interface -t . -v
python3 -m unittest discover -s tests/p6f_capture -t . -v

# 普通目录：不加 -t .
python3 -m unittest discover -s tests/trust -v
python3 -m unittest discover -s tests/runtime -v
python3 -m unittest discover -s tests/storage -v
```

要跑全部目录，请用脚本逐目录调用（按上一节清单决定是否带 `-t .`），不要用一次 `discover -s tests` 覆盖混合结构。

## 3. 现有测试与历史回归

仓库包含多批测试，覆盖可信性、存储、采集、分析、渲染、研究、技能接口与产品验收等。下表为历史全量回归中记录的结果（见 `progress/P1-CONTENT-QA-2026-11-23.md`）：

| 目录 | 历史结果 | 备注 |
|---|---|---|
| `tests/renderer` | 59/59 通过 | 渲染器 |
| `tests/research` | 122/122 通过 | 研究 / 检索 |
| `tests/runtime` | 45/45 通过 | 运行时 |
| `tests/p6f_capture` | 40/40 通过 | 内容采集（含已安装 CLI 夹具） |
| `tests/trust` | 25/25 通过 | P0 可信性断言 |
| `tests/skill_interface` | 7/7 通过（`test_knowledge_answer.py`） | P1 `answer` 意图分流 |

以上为**历史记录**，不是本次重新执行的结论。复现时以当前工作树实际运行结果为准。

## 4. 验证方法与断言

### 4.1 只读断言

多个测试与查询路径断言以下字段，用于证明"只读、不联网"：

- `network_requests=0`：查询、`answer`、卡片生成均为零网络请求。
- `wrote_assets=0`：不写入权威资产。

A 层（不可变资产）由数据库触发器保护；相关测试验证 A 层不可变、不可被改写。

### 4.2 可信性断言（P0，25 项）

`tests/trust` 覆盖的核心规则：

- Commit 只有绑定到本仓库已登记快照才可信，40 位占位值（`aaaa…` 等）永不认证。
- Claim / Fact 按仓库与 Commit 做身份核对，跨仓库 Commit 被阻断。
- 只有当前视图（`current_view`）决定当前有效资产，历史裁决不混入。
- 证据完整性为 `FULLY_LOCATABLE` / `PARTIALLY_LOCATABLE` / `UNRESOLVED_NO_INTEGRITY`；不可解析引用使裁决降级为 `insufficient_evidence`，不变为 `refuted`。
- `ROOT_ONLY` 不冒充完整 `COMPLETE` 覆盖。

### 4.3 返回值语义

- `supported` 裁决带 `review_status`；`pending_review` 表示 CLI 裁决、非人工确认，不得说成"已确认"。
- `completeness_status: PARTIAL` 时，未覆盖部分不得判为"不存在"。
- `insufficient_evidence` 只能说"证据不足"，不能说"命题错误"。
- `refuted` 只对该 Commit 成立，不外推到其他版本。

## 5. 已知环境依赖与历史问题

- **tree-sitter / `.venv`**：JS/TS 源码分析依赖 tree-sitter grammar，隔离在项目本地 `.venv`（见 `requirements-treesitter.txt`）。缺失时解析器返回 `PARSER_UNAVAILABLE`，不用正则凑数——因此相关测试需要该虚拟环境可用。
- **p6f_capture 的历史环境问题**：曾因临时目录 `/tmp/p6b_real` 没有 `kb.db`，`analyze --offline` 报 `OFFLINE_CACHE_MISS`、`analyze --plan` 报 `KNOWLEDGE_DB_MISSING`（均为退出码 3）。这是测试环境问题，不是产品缺陷；已用隔离夹具 `tests/p6f_capture/installed_cli_fixture.py` 修复（构造最小原创树与 `kb.db`），**未复制生产库**。
- **跨版本读取**：`captured_blob_loader` 对相同路径不同 Commit 返回 `COMMIT_MISMATCH`，测试需显式准备对应 Commit 的资产。

## 6. 回归机制与冻结校验值

- **逐目录回归**：按第 1 节清单逐目录运行 `unittest discover`，可复现历史通过数；不要把混合结构的目录一次性 discover。
- **冻结 Crosswalk 校验**：融合基线 `docs/fusion/CAPABILITY_CROSSWALK.json` 的 SHA-256 固定为：

  ```
  42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
  ```

  任何改动能力模型基线的改动都必须重新核验此值；历史 P1 验收中该值保持不变，用以证明可信性规则未回退。

- **F1-B 验证脚本**：`tools/fusion/f1b_verify*.py` 系列（security 53 条、collector 30 条、ec 50 条、product 43 条、research 46 条、lifecycle 48 条等）只写对应的 `*_VERIFICATION.json`，用于校验静态裁决产物，不执行任何真实安全操作。

## 7. 参考

- 历史验收：`progress/P1-CONTENT-QA-2026-11-23.md`
- 冻结基线：`docs/fusion/CAPABILITY_CROSSWALK.json`
- 相关文档：[安全与授权](SECURITY.md)、[路线图](ROADMAP.md)、[安装指南](INSTALLATION.md)
