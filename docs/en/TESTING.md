# SourceLore Testing

This document describes SourceLore's existing tests, verification methods, regression mechanisms, known environment dependencies, and frozen check values. The Chinese version is [docs/zh-CN/TESTING.md](../zh-CN/TESTING.md); facts, interfaces, and statuses are identical in both languages.

## 1. Test organization

All tests live under `tests/` in the repository and are run with the Python standard library `unittest discover` — they do **not** depend on pytest, and there is no top-level `requirements.txt`.

The test directories fall into two categories, and the invocation must match:

- **Package directories** (contain `__init__.py`): run with `-t .`; otherwise discover treats package modules as top-level modules and triggers same-name module conflicts or `Start directory not importable`.
- **Plain test directories** (no `__init__.py`): run **without** `-t .`.

Mixing the two invocation styles triggers same-name module conflicts or "Start directory not importable". This is an **invocation problem, not a logic regression**. There is no top-level `pytest.ini` / `setup.cfg` to avoid it, so tests must be run directory by directory.

### 1.1 Directory inventory (verified present, with correct `-t .` usage)

**Package directories (use `-t .`):**

| Directory | Directory | Directory |
|---|---|---|
| `acceptance_orchestration` | `blob_capture` | `bot_presentation` |
| `capture_maintenance` | `content` | `content_persistence` |
| `content_skill` | `js_ts_analysis` | `module_resolution` |
| `p6f_capture` | `product_acceptance` | `product_multirepo` |
| `renderer` | `research` | `skill_interface` |
| `source_analysis` | `ts_projects` | `views` |

**Plain test directories (no `-t .`):**

`collector`, `evidence_claims`, `facts`, `lifecycle`, `runtime`, `storage`, `trust`

## 2. How to run

From the project root (the path contains parentheses and Chinese characters — always quote it in the shell):

```sh
# Package directories: add -t .
python3 -m unittest discover -s tests/renderer -t . -v
python3 -m unittest discover -s tests/skill_interface -t . -v
python3 -m unittest discover -s tests/p6f_capture -t . -v

# Plain directories: no -t .
python3 -m unittest discover -s tests/trust -v
python3 -m unittest discover -s tests/runtime -v
python3 -m unittest discover -s tests/storage -v
```

To run everything, invoke `unittest discover` per directory in a script, deciding whether to pass `-t .` from the inventory above; do not attempt a single `discover -s tests` over the mixed structure.

## 3. Existing tests and historical regression

The repository contains tests covering trust, storage, capture, analysis, rendering, research, skill interface, and product acceptance. The following results were recorded in the historical full regression (see `progress/P1-CONTENT-QA-2026-11-23.md`):

| Directory | Historical result | Notes |
|---|---|---|
| `tests/renderer` | 59/59 passed | Renderer |
| `tests/research` | 122/122 passed | Research / retrieval |
| `tests/runtime` | 45/45 passed | Runtime |
| `tests/p6f_capture` | 40/40 passed | Content capture (includes installed-CLI fixture) |
| `tests/trust` | 25/25 passed | P0 trust assertions |
| `tests/skill_interface` | 7/7 passed (`test_knowledge_answer.py`) | P1 `answer` intent routing |

These are **historical records**, not results from a fresh run in this session. When reproducing, trust the actual results from the current working tree.

## 4. Verification methods and assertions

### 4.1 Read-only assertions

Multiple tests and query paths assert the following fields to prove "read-only and offline":

- `network_requests=0`: queries, `answer`, and card generation make zero network requests.
- `wrote_assets=0`: no authoritative assets are written.

The immutable A layer (authoritative assets) is protected by database triggers; related tests verify that the A layer is immutable and cannot be rewritten.

### 4.2 Trust assertions (P0, 25 items)

Core rules covered by `tests/trust`:

- A commit is trusted only when bound to a registered snapshot of that repository; placeholder 40-hex values (`aaaa…`, etc.) are never authenticated.
- Claims and Facts are identity-checked against the repository and commit; cross-repository commits are blocked.
- Only the current view (`current_view`) decides which assets are valid now; historical verdicts are not mixed in.
- Evidence completeness is `FULLY_LOCATABLE` / `PARTIALLY_LOCATABLE` / `UNRESOLVED_NO_INTEGRITY`; an unresolvable reference downgrades a verdict to `insufficient_evidence`, never to `refuted`.
- `ROOT_ONLY` is never presented as full `COMPLETE` coverage.

### 4.3 Return-value semantics

- A `supported` verdict carries `review_status`; `pending_review` means a CLI adjudication, not human confirmation, and must not be described as "confirmed".
- When `completeness_status: PARTIAL`, uncovered parts must not be judged "non-existent".
- `insufficient_evidence` means only "insufficient evidence", not "the proposition is false".
- `refuted` holds only for that commit and is not extrapolated to other versions.

## 5. Known environment dependencies and historical issues

- **tree-sitter / `.venv`**: JS/TS source analysis depends on tree-sitter grammars, isolated in a project-local `.venv` (see `requirements-treesitter.txt`). When unavailable, the parser returns `PARSER_UNAVAILABLE` rather than falling back to regex — so related tests need that virtual environment to be available.
- **Historical p6f_capture environment issue**: the temporary directory `/tmp/p6b_real` had no `kb.db`, so `analyze --offline` reported `OFFLINE_CACHE_MISS` and `analyze --plan` reported `KNOWLEDGE_DB_MISSING` (both exit code 3). This was a test-environment problem, not a product defect; it was fixed with an isolated fixture, `tests/p6f_capture/installed_cli_fixture.py` (which builds a minimal original tree and `kb.db`). The production database was **not copied**.
- **Cross-commit reads**: `captured_blob_loader` returns `COMMIT_MISMATCH` for the same path at a different commit; tests must prepare assets for the corresponding commit explicitly.

## 6. Regression mechanism and frozen check values

- **Per-directory regression**: run `unittest discover` directory by directory per the inventory in section 1 to reproduce the historical pass counts; do not discover a mixed structure in one pass.
- **Frozen Crosswalk check**: the fusion baseline `docs/fusion/CAPABILITY_CROSSWALK.json` has a fixed SHA-256:

  ```
  42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
  ```

  Any change to the capability-model baseline must re-verify this value; it remained unchanged in the historical P1 acceptance, demonstrating that the trust rules did not regress.

- **F1-B verification scripts**: the `tools/fusion/f1b_verify*.py` family (security 53 checks, collector 30, ec 50, product 43, research 46, lifecycle 48, etc.) writes only the corresponding `*_VERIFICATION.json` files to validate static decision artifacts; it performs no real security operations.

## 7. References

- Historical acceptance: `progress/P1-CONTENT-QA-2026-11-23.md`
- Frozen baseline: `docs/fusion/CAPABILITY_CROSSWALK.json`
- Related documents: [Security](SECURITY.md), [Roadmap](ROADMAP.md), [Installation](INSTALLATION.md)
