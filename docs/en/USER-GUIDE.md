# SourceLore User Guide

New users should first follow the [Quick Start](QUICKSTART.md) to install the Skill with a valid source-root binding before using this detailed command reference.


This guide explains how to use SourceLore to analyze GitHub repositories, query the knowledge base, generate knowledge cards and ask questions in natural language. Every command here comes from the real CLI `--help` output; options not listed here do not exist. If there is any discrepancy, the authoritative source is `python3 <skill-dir>/scripts/sourcelore.py <subcommand> --help`.

Prerequisite: installed and verified as described in the [Installation Guide](INSTALLATION.md). Below, `sourcelore` denotes the entry point `python3 <skill-dir>/scripts/sourcelore.py`.

---

## 1. General conventions

### 1.1 Command structure

```
sourcelore [--data-root DATA_ROOT] [--version] <subcommand> [options]
```

The global option `--data-root` must appear **before** the subcommand. `--version` returns JSON. There are ten subcommands:

```
status, repositories, help, analyze, inspect, history, query, derive, answer, card
```

### 1.2 Output and exit codes

- All JSON output goes to **stdout**, errors to **stderr**.
- Exit codes: `0` success / `1` execution failure / `2` argument error / `3` knowledge base unavailable.
- An error JSON looks like `{"ok": false, "error": "...", "message": "..."}`. When you see `ok: false`, report the failure truthfully.

### 1.3 Authoritative interpretation rules (avoid misstatement)

- `tree_summary` is the authoritative statement of completeness. `COMPLETE` means fully enumerated; `PARTIAL` means only a subset was collected, and paths that do not appear must not be inferred to be absent.
- `completeness_status: PARTIAL` / coverage `ROOT_ONLY`: uncovered parts must not be judged "non-existent".
- `insufficient_evidence`: say only "insufficient evidence", never "the proposition is false".
- `refuted`: holds only for that commit; do not extrapolate.
- The absence of a Claim for a path in the database does not mean the path is absent on GitHub; it means insufficient coverage.
- When `content_captured=0`, say "content was not captured", not what the file "contains".
- Evidence completeness must be reported separately: only `FULLY_LOCATABLE` can be checked item by item; `PARTIALLY_LOCATABLE` means the evidence chain is incomplete.
- When reporting `supported`, also give `review_status`; `pending_review` is not human confirmation.
- Before reporting `supported`/`refuted`, filter by `current_view`; historical Verifications are diagnostic only.
- Exit code 0 / `ok:true` does not mean the knowledge is trustworthy; audit-type requests must be re-checked against raw assets.
- Do not use the model's own reasoning to fill in data the CLI did not return.

---

## 2. Quick start

```sh
# 1. Runtime state
sourcelore status

# 2. List registered repositories
sourcelore repositories

# 3. Analyze a public repository at a fixed commit (offline reuse if cached)
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha>

# 4. Inspect registered knowledge
sourcelore inspect <repository_id>

# 5. Natural-language Q&A (content first, read-only, zero network)
sourcelore answer <repository_id> "Introduce this project"

# 6. Query specific knowledge
sourcelore query <repository_id> --commit <sha> --type claims

# 7. Regenerate derived project documents (D layer only, offline)
sourcelore derive <repository_id>

# 8. Render a knowledge card
sourcelore card --repository-id <repository_id> --claim-id <claim_id>
```

---

## 3. Understand the knowledge base

### 3.1 status

```sh
sourcelore status
```

No arguments. Reports runtime state: skill version, data root, whether the database exists, repository count and the most recent operation. No credentials are emitted.

### 3.2 repositories

```sh
sourcelore repositories
```

No arguments. Lists registered repositories with fields including `repository_id`, `commits`, `snapshot_count`, `fact_count`, `claim_count` and `knowledge_state`.

### 3.3 help

```sh
sourcelore help
sourcelore <subcommand> --help
```

`help` takes no arguments; `<subcommand> --help` shows that subcommand's authoritative option list.

### 3.4 inspect

```
usage: sourcelore inspect [-h] [--content-summary] repository_id
```

```sh
sourcelore inspect <repository_id>
sourcelore inspect <repository_id> --content-summary
```

- Positional `repository_id` (required).
- `--content-summary`: include a content-level overview (blob count, parseable count, fact count).

Output: commit list, tree coverage (including `completeness_status`), facts, claims and limitations. Aggregate knowledge types by `facts[].rule_id`; `observed_path` is often null, which is normal.

### 3.5 history

```
usage: sourcelore history [-h] repository_id
```

```sh
sourcelore history <repository_id>
```

Lists registered historical versions. **Only registered commits are listed; ancestry or ordering is never inferred.**

---

## 4. Analyze a repository (capture and build)

```
usage: sourcelore analyze [-h] [--ref REF] [--path PATH]
                          [--max-requests MAX_REQUESTS] [--commit COMMIT]
                          [--offline] [--refresh] [--no-token]
                          [--license-known] [--include-content]
                          [--content-status] [--plan] [--resume]
                          [--request-limit REQUEST_LIMIT]
                          [--reserve-requests RESERVE_REQUESTS]
                          [--content-path CONTENT_PATH]
                          url
```

Positional `url`: `https://github.com/<owner>/<repo>` (optionally with `/tree/<ref>`). Only public GitHub repositories are accepted; internal addresses, non-GitHub hosts and unusual ports are rejected.

Options:

| Option | Meaning |
|---|---|
| `--ref REF` | Branch / tag / commit (default HEAD) |
| `--path PATH` | Path to observe |
| `--max-requests MAX_REQUESTS` | GitHub request cap |
| `--commit COMMIT` | Fixed commit SHA (reuses local cache first) |
| `--offline` | Disable all GitHub requests |
| `--refresh` | Explicitly request re-fetch of the remote version |
| `--no-token` | Do not use `GITHUB_TOKEN` for this invocation, even if present |
| `--license-known` | Declare that the repository has a clear licensing basis (internal capture); not declared by default |
| `--include-content` | Perform content-level extraction on a saved snapshot (reads blobs; reports explicitly when bytes are absent) |
| `--content-status` | Report only content availability; no capture, no network |
| `--plan` | Read-only plan: inventory gaps and estimate requests; no network, no asset writes |
| `--resume` | Resume: fill only missing content; reuse what is complete |
| `--request-limit REQUEST_LIMIT` | Max GitHub requests this capture may send (default 8) |
| `--reserve-requests RESERVE_REQUESTS` | Primary quota reserved first (default 5) |
| `--content-path CONTENT_PATH` | Limit content extraction to this path (repeatable) |

### 4.1 Common analysis flows

```sh
# First see the capture plan (read-only, no network, no asset writes)
sourcelore analyze https://github.com/<owner>/<repo> --plan

# Capture at a fixed commit (most common, reproducible)
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha>

# Use only local knowledge, no network
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --offline

# Force re-fetch of the remote version
sourcelore analyze https://github.com/<owner>/<repo> --refresh

# Control the request budget
sourcelore analyze https://github.com/<owner>/<repo> --request-limit 8 --reserve-requests 5

# Observe only one path
sourcelore analyze https://github.com/<owner>/<repo> --path README.md

# Report content availability only (no capture, no network)
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --content-status

# Content-level extraction limited to a path
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --include-content --content-path README.md

# Resume: fill only missing content
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --resume
```

### 4.2 Offline semantics

| Situation | Behavior |
|---|---|
| `--commit` with a complete local snapshot | Reuse directly, zero network requests |
| `--offline` with local data present | Reuse, explicitly marked "GitHub was not contacted" |
| `--offline` with no local data | `OFFLINE_CACHE_MISS`, exit code 3, no fabricated result |
| `--refresh` | Allow re-fetching from the network |
| No `--commit` (mutable branch) | Return `branch_current_unknown: true` |

A local snapshot proves only "a version observed in the past"; it cannot prove the branch still points to it.

### 4.3 Content budgets and status codes

- Budget: 256 KiB per blob, 2 MiB per batch, 32 candidate paths, 100 facts per file. Exceeding it returns `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT`.
- Content status codes: `CONTENT_NOT_CAPTURED` (no bytes) / `BLOB_TOO_LARGE` / `BINARY_CONTENT` / `UNSUPPORTED_ENCODING` / `CONTENT_PARSE_FAILED` / `CONTENT_PARTIAL`.
- Key prerequisite: whether blob bytes were captured must be checked via `snapshot_inventory.content_captured`. If it is 0, report `CONTENT_NOT_CAPTURED` and never guess file content from a path.
- Supported parsers: README (headings + line numbers, links, code-block languages), `package.json` (name/version, dependencies, scripts), `pyproject.toml` (project fields, dependencies, tool tables). Other files yield metadata only.

---

## 5. Query knowledge (query)

```
usage: sourcelore query [-h] [--commit COMMIT]
                        [--type {path,claims,version,content,code,relation,project}]
                        [--path PATH] [--compare-commit COMPARE_COMMIT]
                        [--max-results MAX_RESULTS] [--symbol SYMBOL]
                        [--symbol-kind SYMBOL_KIND] [--module MODULE]
                        [--show-resolution] [--config CONFIG] [--file FILE]
                        repository_id
```

Positional `repository_id` (required). Options:

| Option | Meaning |
|---|---|
| `--commit COMMIT` | Fixed commit (required for `content` type) |
| `--type {path,claims,version,content,code,relation,project}` | Query type |
| `--path PATH` | Path |
| `--compare-commit COMPARE_COMMIT` | Commit to compare against |
| `--max-results MAX_RESULTS` | Maximum number of results |
| `--symbol SYMBOL` | Look up by symbol `qualified_name` or `name` |
| `--symbol-kind SYMBOL_KIND` | Filter by symbol kind |
| `--module MODULE` | Filter by static import module name |
| `--show-resolution` | Show resolution status and configuration details |
| `--config CONFIG` | Filter by tsconfig path |
| `--file FILE` | Filter ownership by source file path |

Queries reuse stored knowledge and **do not re-contact GitHub**. If output contains unescaped control characters, parse with `json.loads(out, strict=False)`; if parsing fails, say truthfully "no displayable result this round" rather than "no knowledge".

### 5.1 path / claims / version

```sh
# Path observation (--type path requires --path)
sourcelore query <rid> --commit <sha> --type path --path README.md

# Registered claims
sourcelore query <rid> --commit <sha> --type claims

# Compare two commits (--type version requires --compare-commit)
sourcelore query <rid> --commit <sha> --compare-commit <other-sha> --type version
```

Common result fields: `coverage_state`, `coverage_meaning`, `answerable`, `findings[]`, `untrusted_findings[]`, `gaps[]`, `limitations[]`, `distribution_restrictions`. Claims inside `untrusted_findings[]` are excluded and must not be treated as conclusions.

### 5.2 content (content-level knowledge)

```sh
# Content query (--type content requires --commit; --path optional)
sourcelore query <rid> --commit <sha> --type content --path README.md
```

Nine states are strictly distinct and must not be merged:

```
REPOSITORY_NOT_REGISTERED / COMMIT_NOT_REGISTERED / CONTENT_NOT_CAPTURED /
CONTENT_INTEGRITY_FAILED / FACT_NOT_REGISTERED / INSUFFICIENT_EVIDENCE /
SUPPORTED / REFUTED / RETRIEVAL_ERROR
```

In particular: no blob content does not mean the file is absent; a blob with no extracted fact does not mean the proposition is refuted; a fact with no verification does not mean supported; a parse failure does not mean the file lacks the content. `ContentEvidenceRef` gives both byte offset (authoritative) and line number (derived human-readable); missing either means `ref_complete=false` and the reference is not complete.

For a content overview use `inspect <rid> --content-summary`. Four counts must not be conflated:

| Metric | Meaning |
|---|---|
| `file_entries` | Number of file entries (the same blob under multiple paths is counted repeatedly) |
| `unique_blobs` | Number of unique Git Blob OIDs |
| `content_assets` | Number of content assets |
| `facts` | Number of registered facts |

### 5.3 code (source structure)

```sh
sourcelore query <rid> --commit <sha> --type code
sourcelore query <rid> --commit <sha> --type code --path src/app.py
sourcelore query <rid> --commit <sha> --type code --symbol Worker.run
sourcelore query <rid> --commit <sha> --type code --symbol-kind js_class
sourcelore query <rid> --commit <sha> --type code --module lodash
```

- Python (`.py`) uses the standard library `ast`; JS/JSX/TS/TSX use tree-sitter (see Installation Guide).
- JS/TS symbol kinds: `js_function` / `js_async_function` / `js_generator_function` / `js_class` / `js_method` / `js_object_method` / `js_variable` / `js_arrow_function` / `js_function_expression` / `ts_interface` / `ts_type_alias` / `ts_enum` / `ts_namespace`.
- Semantic discipline: an arrow binding is not a function declaration; an interface is not a class; an anonymous default export is not given an invented name.
- `require("x")` is a call observation (`LITERAL_REQUIRE_CALL_OBSERVED`), not an ESM declaration; `require(var)` / `import(var)` → `DYNAMIC_MODULE_SPECIFIER`, with no guessed target; `import type` → `is_type_only=true`, not a runtime dependency.
- Parse completeness: `PARSE_COMPLETE` / `PARSE_WITH_ERRORS` / `PARSE_UNSUPPORTED_SYNTAX` / `PARSER_UNAVAILABLE` / `SOURCE_INCOMPLETE` / `CONTENT_INTEGRITY_FAILED`. On syntax errors no authoritative symbol/import/export facts are produced.
- Can confirm: `SOURCE_SYMBOL_DECLARED`, `SOURCE_IMPORT_DECLARED`, `SOURCE_LOCAL_MODULE_RESOLVED`. Cannot confirm execution, usage or runtime success.
- Local module resolution states: `LOCAL_MODULE_RESOLVED` / `EXTERNAL_OR_UNRESOLVED` / `AMBIGUOUS_CANDIDATES` / `INSUFFICIENT_TREE_COVERAGE` / `UNSUPPORTED_IMPORT_FORM`.
- Repository code is never executed. No call graph, runtime dependency graph, data-flow graph, dynamic dispatch or behavior graph is produced.

### 5.4 relation (configuration-aware module resolution)

```sh
sourcelore query <rid> --commit <sha> --type relation
sourcelore query <rid> --commit <sha> --type relation --path src/app.ts
sourcelore query <rid> --commit <sha> --type relation --module ./utils
sourcelore query <rid> --commit <sha> --type relation --show-resolution
```

Three layers are never conflated:

| Layer | State | Meaning |
|---|---|---|
| 1 | `MODULE_REFERENCE_OBSERVED` | The import really exists in source |
| 2 | `CONFIG_MAPPING_CANDIDATE` | A candidate path was found from configuration |
| 3 | `LOCAL_MODULE_RESOLVED` | Unique hit in the current commit tree |

There is no `RUNTIME_IMPORT_VERIFIED` — runtime loading is not verified. JS/TS resolution states: `LOCAL_MODULE_RESOLVED` / `RELATIVE_PATH_CANDIDATE_FOUND` / `AMBIGUOUS_CANDIDATES` / `EXTERNAL_OR_UNRESOLVED` / `UNSUPPORTED_RESOLUTION_POLICY` / `INSUFFICIENT_TREE_COVERAGE` / `DYNAMIC_SPECIFIER`. This version supports only explicit relative paths (`./x`, `../y`); bare specifiers, `@/alias` and `#hash` are all `UNSUPPORTED_RESOLUTION_POLICY`.

### 5.5 project (TypeScript project knowledge)

```sh
sourcelore query <rid> --commit <sha> --type project
sourcelore query <rid> --commit <sha> --type project --config tsconfig.json
sourcelore query <rid> --commit <sha> --type project --file src/app.ts
sourcelore query <rid> --commit <sha> --type project --show-resolution
```

- Only standard `tsconfig.json` / `jsconfig.json` names are recognized; base configs referenced by `extends` are not registered as independent projects.
- `extends`: `files`/`include`/`exclude` are inherited (overridden by child config); `references` is not inherited.
- `references` handles only local configs in the same repository and commit, with cycle and depth-8 detection. `PROJECT_REFERENCE_TARGET_VERIFIED` means only that the target config exists — not that B was built or that A used B's output.
- `files` takes priority over `include` and is unaffected by `exclude`; `exclude` filters only the include scan; `files: []` does not trigger default scanning.
- Unsupported patterns (braces, negation, absolute paths, multiple `**`) → `UNSUPPORTED_SELECTION_RULE`.
- Ownership states are independent: `INPUT_EXPLICITLY_LISTED` / `INPUT_MATCHED_INCLUDE` / `INPUT_EXCLUDED_FROM_INCLUDE` / `INPUT_POSSIBLE_VIA_IMPORT` / `INPUT_MATCHED_MULTIPLE_PROJECTS` / `INPUT_NOT_PROVEN` / `CONFIG_INCOMPLETE` / `UNSUPPORTED_SELECTION_RULE`. `INPUT_EXCLUDED_FROM_INCLUDE` does not mean it cannot enter the TypeScript Program.
- Project context: uniquely verifiable → `PROJECT_CONTEXT_SELECTED`; multiple candidates → `PROJECT_CONTEXT_AMBIGUOUS` (never pick one).
- Any unregistered config yields `CONFIG_CONTENT_NOT_CAPTURED` — do not guess the repository lacks a tsconfig, do not read the working directory, do not borrow from another commit.

---

## 6. Natural-language Q&A (answer)

```
usage: sourcelore answer [-h] [--commit COMMIT] repository_id question
```

```sh
sourcelore answer <repository_id> "Introduce this project"
sourcelore answer <repository_id> "How do I use this library"
sourcelore answer <repository_id> "What is the architecture"
sourcelore answer <repository_id> "What are the core functions"
sourcelore answer <repository_id> "Why are these conclusions trustworthy"
sourcelore answer <repository_id> "Is the knowledge base complete"
sourcelore answer <repository_id> "How do I use it" --commit <sha>
```

- Positional `repository_id` and `question` (natural-language question).
- `--commit`: fixed commit; defaults to the latest registered snapshot of that repository.
- Read-only, zero network, zero writes, no third-party code execution; answers come entirely from registered, verified local assets.
- Output contains `intent`, `blocks[]` (each with `heading`/`body`/`refs`), `audit`, `network_requests=0`, `wrote_assets=0`. Present `blocks[].body` as the real text and use `refs` for provenance; do not rewrite the body or fill gaps with reasoning.

Intents and triggers:

| intent | Triggering questions | Content shown |
|---|---|---|
| `introduce` | introduce / purpose / features / overview (default) | Project purpose, stack and manifest, main exports, core implementation excerpts |
| `usage` | how to use / install / API / examples | README Install/Usage/example sections plus manifest |
| `architecture` | architecture / structure / modules / dependencies / entry points | Exports and module pointers, file structure, dependency declarations |
| `code` | source / functions / classes / exports / symbols | Symbol table, core implementation excerpts, dependencies |
| `evidence` | why trustworthy / evidence / basis | Claims and verdicts, evidence locations, with `audit` |
| `completeness` | completeness / coverage / check the knowledge base | Coverage notes, file structure, with `audit` |

**Audit fields appear only for `evidence`/`completeness`**; other intents return `audit=null`, so statistics do not drown out ordinary answers. Chinese questions are mapped to English README headings (use/install → `install`/`usage`, performance → `benchmark`, license → `license`). Common limitations are always attached: commit may not be latest, `distribution_allowed=false`, ROOT_ONLY subdirectories not captured.

---

## 7. Generate knowledge cards (card)

```
usage: sourcelore card [-h] --repository-id REPOSITORY_ID
                       [--claim-id CLAIM_ID]
                       [--verification-id VERIFICATION_ID]
                       [--content-fact-id CONTENT_FACT_ID]
                       [--content-claim-id CONTENT_CLAIM_ID] [--commit COMMIT]
                       [--path PATH] [--code] [--vault VAULT]
```

| Option | Meaning |
|---|---|
| `--repository-id REPOSITORY_ID` | Required |
| `--claim-id CLAIM_ID` | Generate from a claim |
| `--verification-id VERIFICATION_ID` | Generate from a verification |
| `--content-fact-id CONTENT_FACT_ID` | Generate from a content fact |
| `--content-claim-id CONTENT_CLAIM_ID` | Generate from a content claim |
| `--commit COMMIT` | Fixed commit |
| `--path PATH` | Path |
| `--code` | Generate a source-structure card |
| `--vault VAULT` | Also export as an Obsidian bidirectional-link note (vault directory) |

```sh
# By claim / verification
sourcelore card --repository-id <rid> --claim-id <claim_id>
sourcelore card --repository-id <rid> --verification-id <verification_id>

# Content knowledge cards
sourcelore card --repository-id <rid> --commit <sha> --path README.md
sourcelore card --repository-id <rid> --content-fact-id <fact_id>
sourcelore card --repository-id <rid> --content-claim-id <claim_id>

# Source-structure card (text block for in-bot display)
sourcelore card --repository-id <rid> --commit <sha> --path <p> --code

# Export an Obsidian note
sourcelore card --repository-id <rid> --claim-id <claim_id> --vault <vault-dir>
```

`card ... --code` returns by default `{"format":"bot_block","repository":"owner/name","text":"<dot-grid table>","network_requests":0}`. Present the `text` directly to the user; **do not** open a browser or generate an HTML file. The five dot-grid levels mean: `▣ verified·proposition holds` / `▤ observed·not yet verified` / `□ insufficient evidence` / `△ semantic form unsupported` / `· not analyzed`. Cards always display `distribution_allowed=false` and `copy_permitted=false`; an incomplete evidence chain yields only a diagnostic card, never a full-score card. Large raw text is not echoed by default; evidence labels carry only structured descriptions (e.g. `heading:L2`).

Queries and card generation follow a **read-only contract**: zero network requests, no database writes, no re-extraction, no pointer advancement.

---

## 8. Generate derived documents (derive)

```
usage: sourcelore derive [-h] [repository_id]
```

```sh
sourcelore derive <repository_id>
sourcelore derive          # omit to process all repositories
```

- Positional `repository_id` is optional; omitting it processes all repositories.
- Generates derived views and project knowledge documents, **offline, no network**, rebuilding only the D layer and leaving A/B/C untouched.
- Check `tree_status` first; `ROOT_ONLY` is a normal, genuine state and must not be "corrected" to COMPLETE.

---

## 9. Multi-repository and evidence query examples

### 9.1 Multi-repository inventory

Loop with a script and aggregate instead of flooding the screen with individual calls. Example (Python):

```python
from hermes_tools import terminal
import json

rids = ["repo-a", "repo-b", "repo-c"]
for rid in rids:
    out = terminal(f"sourcelore inspect {rid}", timeout=60)["output"]
    data = json.loads(out, strict=False)
    print(rid, data.get("knowledge_state"), data.get("completeness_status"))
```

Get each `repository_id` from `repositories`, then `inspect` each one. When aggregating, first confirm each repository's commit and coverage status, then compare.

### 9.2 Evidence query and interpretation

```sh
# 1. Query a path observation and confirm coverage
sourcelore query <rid> --commit <sha> --type path --path docs/README.md

# 2. Query all claims to find a claim_id
sourcelore query <rid> --commit <sha> --type claims

# 3. Render a card by claim to see the verdict and evidence locations
sourcelore card --repository-id <rid> --claim-id <claim_id>

# 4. When audit fields are needed, use the answer evidence intent
sourcelore answer <rid> "Why are these conclusions trustworthy" --commit <sha>
```

Interpretation order: check `coverage_state` and limitations → check `findings[]` verdicts → check evidence completeness (only `FULLY_LOCATABLE` is checkable item by item) → check `review_status` (`pending_review` is not human confirmation) → filter out historical Verifications by `current_view`. Claims in `untrusted_findings[]` are excluded.

---

## 10. Using it through an agent in natural language

Users need not memorize commands; the Skill maps natural-language requests to the corresponding CLI:

| User says | Actual command |
|---|---|
| Analyze / build a knowledge base with SourceLore | `analyze <url>` |
| Query a saved fixed commit (do not ask GitHub) | `analyze <url> --commit <sha>` |
| Use only local knowledge, no network | `analyze <url> --offline` |
| Force re-fetch of the remote version | `analyze <url> --refresh` |
| What repositories are registered | `repositories` |
| Introduce / usage / architecture Q&A | `answer <rid> "<question>"` |
| Show what is known about a repository | `inspect <rid>` |
| Does X exist in this commit | `query <rid> --commit <sha> --type path --path X` |
| What claims are registered | `query <rid> --commit <sha> --type claims` |
| Compare two commits | `query <rid> --commit <sha> --compare-commit <sha> --type version` |
| Generate a knowledge card | `card --repository-id <id> --claim-id <id>` |
| Extract file content knowledge | `analyze <url> --commit <sha> --include-content` |
| Query source structure | `query <rid> --commit <sha> --type code` |

Boundaries: when a user asks "is this project good / are features complete / is the documentation good", do not force an answer from the knowledge base — state that no such evidence exists. Refuse requests to analyze private repositories, create issues/PRs, commit code or execute repository scripts. Every answer should state: whether SourceLore was actually invoked, which repository and commit were queried, what was actually read, whether the result was verified, what coverage limitations exist, and whether any network request or data modification occurred.

---

## 11. Limitation semantics at a glance

- `ROOT_ONLY`: only the root directory was enumerated; not COMPLETE; missing content is "not analyzed".
- `distribution_allowed=false` / `copy_permitted=false`: internal preview only, not for public distribution; distribution gates B-1/B-2/B-3 remain open.
- `review_status=pending_review`: CLI adjudication, not human confirmation.
- `PARTIAL` / `insufficient_evidence` / `refuted`: none may be extrapolated into "non-existent" or "proposition is false".
- Repository code is never executed; private repositories are not supported; only `https://github.com/<owner>/<repo>` is accepted.
- Unauthenticated use is limited to 60 GitHub requests/hour; when rate-limited the tool returns `RATE_LIMITED` with `retry_after` within 2 seconds and does not auto-retry.
- Content is bounded by budget (256 KiB per blob, 2 MiB per batch, 32 candidate paths, 100 facts per file).
