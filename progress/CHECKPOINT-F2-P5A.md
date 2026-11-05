# F2-P5A Skill 安装与集成（检查点）

**基线**：HEAD `8c6c087`（非 056de10）· Crosswalk sha256 `42841207…` 已复算匹配

## 接口审计（关键：没有 CLI 层）

| 模块 | 真实可调用接口 | CLI |
|---|---|---|
| `src/storage/knowledge_store.py` | `KnowledgeStore` 类、`get_asset`/`history`/`current_pointer`/`append_asset_and_advance` | **无** |
| `src/collector/` | `GitHubClient` 类、`ingest_snapshot()`、`build_snapshot()` | **无** |
| `src/facts/extractor.py` | `extract_file_path_observation(store, snapshot_asset_id=, target_path=)` | **无** |
| `src/evidence_claims/verifier.py` | `verify_path_claim(store, claim, fact_ids)` | **无** |
| `src/views/` | `assemble_from_verification(store, verification_id=, repository_id=)` | **无** |
| `src/research/` | `run_research(store, query)` | **无** |
| `src/renderer/` | `build_card(view)` / `render_json` / `render_card_html` | **无** |

**结论：整个工程零个 `argparse`、零个 `__main__`。** Skill 的 CLI 必须新建。
且 `KnowledgeStore` **没有 list-repositories 类聚合接口** —— 需在 CLI 层只读查 `index_rows`。

## Skill 发现机制（实测）

- `~/.agents/skills/<name>/SKILL.md` 已被 DSH 发现（现存 omarchy、diagnose-crash）
- SKILL.md frontmatter 只需 `name` + `description`（omarchy 实测）
- `~/.agents/skills/sourcelore` **不存在**（无同名冲突）

## 下一步

1. `src/skill_interface/` 六个模块
2. `skill/sourcelore/` 源目录
3. 安装到 `~/.agents/skills/sourcelore/`
4. 测试 + 验收 + 报告
