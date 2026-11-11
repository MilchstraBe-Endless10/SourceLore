"""项目知识挖掘：把已登记证据组织成**可阅读**的项目文档。

★ 铁律（对应用户 §3.2）：
  只陈述有证据支撑的内容。原仓库没提供的不编造。
  无法证明的写「未分析 / 证据不足 / 不适用」，绝不用模型想象补齐。
  本模块**不调用任何 LLM**，只做确定性组装。

产出 documents: [{document_id, title, sections:[{section_id, heading, body(markdown), refs}]}]
"""

import json
import re

SCHEMA = "sourcelore-project-doc/1"


# ── 取已采集的内容资产 ───────────────────────────────────────────

def _blob_texts(store, repository_id, data_root):
    """取已采集的文件正文。

    ★ 关键事实（2026-11-11 审计纠正）：
      正文**不在** captured_blob_content 的 payload 里（那里只有元数据）；
      真正的字节存在 `<data_root>/blobs/<sha256>.bin`，
      由 `blob_content_store.get_bytes()` 按 content_sha256 读回并校验。

    ★ 必须走正式 Storage API，不得自行拼路径、不得重新下载。
    """
    out = {}
    meta = {}
    try:
        import blob_content_store as BCS
        rows = store.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='captured_blob_content' "
            "AND repository_id=?", (str(repository_id),)).fetchall()
        for r in rows:
            pl = json.loads(r["payload_json"])
            path = (pl.get("file_path") or pl.get("normalized_path")
                    or pl.get("path"))
            digest = pl.get("content_sha256")
            if not path or not digest:
                continue
            got = BCS.get_bytes(data_root=data_root, content_sha256=digest,
                                verify=True)
            if not got.get("ok"):
                meta[path] = {"error": got.get("error"), "digest": digest}
                continue
            raw = got.get("raw") or b""
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    text = ""
            out[path] = text
            meta[path] = {
                "digest": digest,
                "byte_length": got.get("byte_length"),
                "copy_permitted": pl.get("copy_permitted"),
                "distribution_allowed": pl.get("distribution_allowed"),
                "provenance_level": pl.get("provenance_level"),
                "git_blob_oid": pl.get("git_blob_oid"),
            }
    except Exception as e:
        meta["__error__"] = f"{type(e).__name__}: {e}"
    return out, meta


def _readme_from_tree(texts, tree_entries):
    """找 README：优先已采内容，其次树里有 README 就标注存在。"""
    for path, text in texts.items():
        low = path.lower()
        if low.endswith(("readme.md", "readme", "readme.markdown", "readme.txt")):
            return path, text
    for e in tree_entries or []:
        p = (e.get("path") or "")
        if p.lower().endswith(("readme.md", "readme", "readme.markdown")):
            return p, None
    return None, None


def _manifest_from_tree(texts, tree_entries):
    """找 package.json / pyproject.toml。"""
    for path, text in texts.items():
        if path.endswith("package.json"):
            try:
                return path, json.loads(text)
            except Exception:
                return path, None
    for e in tree_entries or []:
        if (e.get("path") or "").endswith("package.json"):
            return e["path"], None
    return None, None


# ── 从 README 抽取结构化事实（不臆造）────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_CODE_FENCE = re.compile(r"^```([^\n]*)$")


def parse_markdown(text):
    """把 Markdown 切成 (heading, level, lines) 段落列表；保留代码块。"""
    if not text:
        return []
    out = []
    cur = {"heading": None, "level": 0, "lines": []}
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        m = _CODE_FENCE.match(line.strip())
        if m:
            in_code = not in_code
            cur["lines"].append(line)
            continue
        if not in_code:
            h = _HEADING_RE.match(line)
            if h:
                if cur["heading"] or cur["lines"]:
                    out.append(cur)
                cur = {"heading": h.group(2).strip(),
                       "level": len(h.group(1)), "lines": []}
                continue
        cur["lines"].append(line)
    if cur["heading"] or cur["lines"]:
        out.append(cur)
    return out


def _first_paragraph(sec):
    """取某段落的第一段正文（跳过空行、标题、徽章行）。"""
    buf = []
    in_code = False
    for ln in sec.get("lines") or []:
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not s:
            if buf:
                break
            continue
        # 跳过纯徽章 / 图片行
        if s.startswith("[![") or s.startswith("![") or s.startswith("<img"):
            continue
        buf.append(s)
    return " ".join(buf).strip()


def _install_like(sec):
    """从段落里抽出像是安装/使用命令的代码块。"""
    blocks, cur, in_code = [], [], False
    for ln in sec.get("lines") or []:
        s = ln.strip()
        if s.startswith("```"):
            if in_code and cur:
                blocks.append("\n".join(cur))
                cur = []
            in_code = not in_code
            continue
        if in_code:
            cur.append(ln)
    if cur:
        blocks.append("\n".join(cur))
    return blocks[:2]


# ── 文档章节构造 ────────────────────────────────────────────────

# ── 从已读原文抽取可陈述的符号事实（不推测）────────────────────

_JS_EXPORT = re.compile(
    r"^\s*export\s+(default\s+)?(?:async\s+)?"
    r"(function|class|const|let|var)\s+([A-Za-z_$][\w$]*)", re.M)
_JS_EXPORT_FROM = re.compile(
    r"^\s*export\s+\{([^}]*)\}\s+from\s+['\"]([^'\"]+)['\"]", re.M)
_JS_EXPORT_STAR = re.compile(
    r"^\s*export\s+\*\s+from\s+['\"]([^'\"]+)['\"]", re.M)
_JS_FUNC = re.compile(
    r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)
_PY_DEF = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.M)
_PY_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.M)


def extract_symbols_from_source(path, text):
    """从已采集的源码文本里抽符号。只陈述字面可见的声明。"""
    if not text:
        return []
    out = []
    low = path.lower()

    if low.endswith((".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")):
        for m in _JS_EXPORT.finditer(text):
            is_default = bool(m.group(1))
            kind = m.group(2)
            name = m.group(3)
            line = text[:m.start()].count("\n") + 1
            out.append({
                "name": name, "kind": kind,
                "export_kind": "default" if is_default else "named",
                "line": line, "path": path,
            })
        for m in _JS_EXPORT_FROM.finditer(text):
            names = [x.strip().split(" as ")[-1].strip()
                     for x in m.group(1).split(",") if x.strip()]
            line = text[:m.start()].count("\n") + 1
            for nm in names:
                if nm:
                    out.append({"name": nm, "kind": "re_export",
                                "export_kind": "named", "target": m.group(2),
                                "line": line, "path": path})
        for m in _JS_EXPORT_STAR.finditer(text):
            line = text[:m.start()].count("\n") + 1
            out.append({"name": "*", "kind": "re_export",
                        "export_kind": "star", "target": m.group(1),
                        "line": line, "path": path})
    elif low.endswith(".py"):
        for m in _PY_DEF.finditer(text):
            out.append({"name": m.group(1), "kind": "function",
                        "export_kind": "module",
                        "line": text[:m.start()].count("\n") + 1, "path": path})
        for m in _PY_CLASS.finditer(text):
            out.append({"name": m.group(1), "kind": "class",
                        "export_kind": "module",
                        "line": text[:m.start()].count("\n") + 1, "path": path})
    # 去重（同 名+kind+行）
    seen, uniq = set(), []
    for x in out:
        k = (x.get("name"), x.get("kind"), x.get("line"), x.get("path"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq


def build_overview(*, repo_name, commit_sha, tree_entries, readme_path,
                   readme_sections, manifest, manifest_path, code_rows,
                   claims, coverage_note, source_symbols=None):
    secs = []

    # 1) 项目用途：直接引 README 首段（有证据）
    purpose = ""
    for s in readme_sections[:3]:
        p = _first_paragraph(s)
        if len(p) >= 20:
            purpose = p
            break
    if purpose:
        body = (purpose + "\n\n"
                f"> 来源：`{readme_path}` · 固定 Commit `{commit_sha[:12]}`")
        secs.append({"section_id": "purpose", "heading": "项目用途",
                     "body": body,
                     "refs": [{"kind": "readme", "path": readme_path}]})
    else:
        secs.append({
            "section_id": "purpose", "heading": "项目用途",
            "body": ("未分析。\n\n" if not readme_path
                     else "README 尚未采集正文，无法提取项目用途；"
                          "不得据此推断项目功能。\n\n"
                          f"> 已知存在：`{readme_path}`（仅路径观察）"),
            "refs": ([{"kind": "readme_path_only", "path": readme_path}]
                     if readme_path else []),
        })

    # 2) 技术栈与清单（来自真实 manifest）
    if isinstance(manifest, dict):
        lines = ["由 `" + (manifest_path or "package.json") + "` 直接读取：", ""]
        for k in ("name", "version", "description", "main", "module",
                  "types", "type", "license"):
            if manifest.get(k):
                lines.append(f"- **{k}**：`{manifest[k]}`")
        deps = manifest.get("dependencies") or {}
        dev = manifest.get("devDependencies") or {}
        if deps:
            lines.append("")
            lines.append(f"**运行时依赖**（{len(deps)} 个）："
                         + "、".join(f"`{d}`" for d in list(deps)[:15]))
        if dev:
            lines.append("")
            lines.append(f"**开发依赖**（{len(dev)} 个）："
                         + "、".join(f"`{d}`" for d in list(dev)[:15]))
        scripts = manifest.get("scripts") or {}
        if scripts:
            lines.append("")
            lines.append("**可用命令**（来自 manifest.scripts，"
                         "仅声明存在，不代表已执行验证）：")
            for k, v in list(scripts.items())[:12]:
                lines.append(f"- `{k}` → `{v}`")
        secs.append({"section_id": "stack", "heading": "技术栈与清单",
                     "body": "\n".join(lines),
                     "refs": [{"kind": "manifest", "path": manifest_path}]})
    else:
        secs.append({
            "section_id": "stack", "heading": "技术栈与清单",
            "body": ("未分析。本 Commit 未采集到可解析的 `package.json`；"
                     "不从目录名推断技术栈。"),
            "refs": [],
        })

    # 3) 入口与主要导出：优先 AST 观察，回退从已采原文直接读出的声明
    exports = [c for c in (code_rows or [])
               if (c.get("kind") in ("export", "import")) ]
    if not exports and source_symbols:
        lines = ["以下符号声明**直接从已采集的源文件正文读出**"
                 "（本 Commit 未做 AST 结构分析，故按字面匹配）：", "",
                 "| 名称 | 类型 | 导出方式 | 文件 | 行号 |",
                 "|---|---|---|---|---|"]
        for x in source_symbols[:40]:
            lines.append(f"| `{x.get('name')}` | {x.get('kind')} | "
                         f"{x.get('export_kind')} | `{x.get('path')}` | "
                         f"{x.get('line')} |")
        refs = []
        for x in source_symbols[:40]:
            d = (x.get("digest") or "")
            if d:
                refs.append({"kind": "blob", "digest": d,
                             "path": x.get("path"), "line": x.get("line")})
        secs.append({"section_id": "entrypoints", "heading": "主要导出与符号",
                     "body": "\n".join(lines), "refs": refs})
    elif exports:
        lines = ["以下导出/导入观察来自源码 AST 解析，"
                 "**只陈述声明存在，不推断运行行为**：", ""]
        lines.append("| 名称 | 类型 | 指向模块 | 行号 |")
        lines.append("|---|---|---|---|")
        for c in exports[:30]:
            s = c.get("subject") or {}
            nm = s.get("exported_name") or s.get("imported_name") or "-"
            kind = s.get("export_kind") or c.get("kind") or "-"
            ref = s.get("source_reference") or "-"
            ln = c.get("start_line")
            lines.append(f"| `{nm}` | {kind} | `{ref}` | "
                         f"{ln if ln is not None else '-'} |")
        secs.append({"section_id": "entrypoints", "heading": "主要导出与模块指向",
                     "body": "\n".join(lines),
                     "refs": [{"kind": "source_fact", "fact_id": c.get("fact_id")}
                              for c in exports[:30]]})
    else:
        secs.append({
            "section_id": "entrypoints", "heading": "主要导出与符号",
            "body": ("未分析。本 Commit 既未做源码结构分析，"
                     "也未采集到可解析的源文件正文；"
                     "这不代表项目没有导出。"),
            "refs": [],
        })

    # 4) 知识覆盖范围与限制
    lines = [f"- 树完整度：{coverage_note}", ""]
    lines.append(f"- 已登记命题：{len(claims or [])} 条")
    lines.append("- 本卡片的全部内容派生于已登记证据；"
                 "未覆盖部分不推断、不补写。")
    secs.append({"section_id": "coverage", "heading": "知识覆盖与限制",
                 "body": "\n".join(lines), "refs": []})

    return {"document_id": "project-overview", "title": "项目总览",
            "sections": secs}


def build_readme_doc(*, repo_name, commit_sha, readme_path, readme_sections):
    """完整 README（章节化，保留原始结构）。"""
    if not readme_sections:
        return {
            "document_id": "readme", "title": "README 原文",
            "sections": [{
                "section_id": "absent", "heading": "README 原文",
                "body": ("本 Commit 未采集到 README 正文。"
                         + (f"仅确认路径存在：`{readme_path}`。"
                            if readme_path else "树中亦未见 README。")
                         + "\n\n不得据此推断项目介绍内容。"),
                "refs": ([{"kind": "readme_path_only", "path": readme_path}]
                         if readme_path else []),
            }],
        }

    secs = []
    for i, s in enumerate(readme_sections):
        head = s.get("heading") or ("正文" if i == 0 else f"段落 {i + 1}")
        body = "\n".join(s.get("lines") or []).strip()
        if not body:
            continue
        secs.append({
            "section_id": f"readme-{i}",
            "heading": head,
            "body": body,
            "refs": [{"kind": "readme", "path": readme_path}],
        })
    if not secs:
        secs = [{"section_id": "readme-0", "heading": "README 原文",
                 "body": ("README 已存在但正文尚未采集。"
                          f"\n\n> 路径：`{readme_path}`"),
                 "refs": [{"kind": "readme_path_only", "path": readme_path}]}]
    return {"document_id": "readme", "title": "README 原文", "sections": secs}


def build_structure_doc(*, repo_name, commit_sha, tree_entries, coverage_note):
    """文件结构（按目录聚合，标注完整度）。"""
    entries = tree_entries or []
    by_dir = {}
    for e in entries:
        p = e.get("path") or ""
        if not p:
            continue
        d = p.rsplit("/", 1)[0] if "/" in p else "（根）"
        by_dir.setdefault(d, []).append(e)

    secs = []
    lines = [f"共 {len(entries)} 个条目。", "",
             f"**完整度**：{coverage_note}", ""]
    if not entries:
        lines.append("树中无可列举条目。")
    secs.append({"section_id": "summary", "heading": "概览",
                 "body": "\n".join(lines),
                 "refs": [{"kind": "tree", "commit_sha": commit_sha}]})

    for d in sorted(by_dir):
        items = by_dir[d]
        rows = ["| 路径 | 类型 | 大小 |", "|---|---|---|"]
        for e in sorted(items, key=lambda x: x.get("path") or "")[:80]:
            t = e.get("type") or "blob"
            w = {"tree": "目录", "blob": "文件"}.get(t, t)
            size = e.get("size")
            rows.append(f"| `{e.get('path')}` | {w} | "
                        f"{size if size is not None else '-'} |")
        secs.append({
            "section_id": "dir:" + d,
            "heading": d,
            "body": "\n".join(rows),
            "refs": [{"kind": "tree", "commit_sha": commit_sha, "dir": d}],
        })
    return {"document_id": "structure", "title": "文件结构", "sections": secs}


def build_deps_doc(*, repo_name, commit_sha, code_rows, manifest, manifest_path,
                   source_symbols=None):
    """模块与依赖。区分「已解析」「未解析」「未分析」。"""
    secs = []
    imports = []
    for c in (code_rows or []):
        s = c.get("subject") or {}
        ref = s.get("source_reference")
        if ref:
            imports.append({
                "name": s.get("exported_name") or s.get("imported_name"),
                "kind": s.get("export_kind") or c.get("kind"),
                "target": ref,
                "fact_id": c.get("fact_id"),
            })

    if imports:
        lines = ["**已解析的模块指向**（来自源码 AST 观察）：", "",
                 "| 名称 | 关系 | 目标模块 |", "|---|---|---|"]
        for i in imports[:60]:
            lines.append(f"| `{i['name']}` | {i['kind']} | `{i['target']}` |")
        lines.append("")
        lines.append("> 这些是**静态观察到的模块说明符**。"
                     "说明符能否落到真实文件由 resolver 决定；"
                     "未解析不等于不存在。")
        secs.append({"section_id": "imports", "heading": "内部模块指向",
                     "body": "\n".join(lines),
                     "refs": [{"kind": "source_fact", "fact_id": i["fact_id"]}
                              for i in imports[:60] if i.get("fact_id")]})
    elif source_symbols:
        # ★ 2026-11-12：tree-sitter 已接入（tools/extract_symbols.py 产出
        #   source_structure_observation 与 static_module_resolution），
        #   不再是「按字面匹配」。文案必须与事实一致。
        lines = ["**从已采集源文件解析出的模块指向**"
                 "（tree-sitter 解析 + 相对路径解析；仅覆盖已采集文件）：", "",
                 "| 名称 | 关系 | 目标模块 | 文件 | 行号 |",
                 "|---|---|---|---|---|"]
        n = 0
        for x in source_symbols:
            if x.get("kind") not in ("re_export",):
                continue
            lines.append(f"| `{x.get('name')}` | {x.get('kind')} | "
                         f"`{x.get('target') or '-'}` | `{x.get('path')}` | "
                         f"{x.get('line')} |")
            n += 1
        if n == 0:
            lines.append("| — | 未发现模块指向 | — | — | — |")
        lines.append("")
        lines.append("> 说明符能否落到真实文件由 resolver 决定；未解析不等于不存在。")
        secs.append({"section_id": "imports", "heading": "内部模块指向",
                     "body": "\n".join(lines), "refs": []})
    else:
        secs.append({
            "section_id": "imports", "heading": "内部模块指向",
            "body": ("未分析。本 Commit 既未做源码结构解析，"
                     "也未采集到可解析的源文件正文；"
                     "**这不代表项目没有依赖**。"),
            "refs": [],
        })

    # 外部依赖（来自 manifest，有证据）
    if isinstance(manifest, dict):
        deps = manifest.get("dependencies") or {}
        dev = manifest.get("devDependencies") or {}
        if deps or dev:
            lines = ["来自 `" + (manifest_path or "package.json") + "` 的声明。",
                     "",
                     "> ★ **清单声明依赖 ≠ 依赖已安装**；缺少声明 ≠ 项目未使用。", ""]
            if deps:
                lines.append(f"**dependencies**（{len(deps)}）：")
                for k, v in list(deps.items())[:40]:
                    lines.append(f"- `{k}` `{v}`")
            if dev:
                lines.append("")
                lines.append(f"**devDependencies**（{len(dev)}）：")
                for k, v in list(dev.items())[:40]:
                    lines.append(f"- `{k}` `{v}`")
            secs.append({"section_id": "external", "heading": "外部依赖声明",
                         "body": "\n".join(lines),
                         "refs": [{"kind": "manifest", "path": manifest_path}]})

    return {"document_id": "dependencies", "title": "模块与依赖", "sections": secs}


def _short(cid):
    return (cid or "").split("-")[-1][:10]


def build_claims_doc(*, repo_name, commit_sha, claims, verifications):
    vmap = {}
    for v in (verifications or []):
        cid = v.get("claim_id")
        if cid:
            vmap.setdefault(cid, []).append(v)

    dedup = {}
    for c in (claims or []):
        cid = c.get("claim_id")
        if not cid:
            continue
        if cid not in dedup:
            dedup[cid] = c

    rows = ["| Claim | 类型 | 文件 | 裁决 | 证据数 |",
            "|---|---|---|---|---|"]
    detail = []
    for cid, c in sorted(dedup.items()):
        vs = vmap.get(cid) or []
        status = vs[0].get("status") if vs else c.get("verdict_status")
        facts = []
        for v in vs:
            facts.extend(v.get("fact_ids") or [])
        rows.append(f"| `{_short(cid)}` | {c.get('claim_type') or '-'} | "
                    f"`{c.get('normalized_path') or '-'}` | "
                    f"{status or '未裁决'} | {len(facts)} |")
        if facts:
            detail.append(f"- `{_short(cid)}` 证据："
                          + "、".join(f"`{f[:26]}`" for f in facts[:4]))

    secs = [{"section_id": "table", "heading": "命题与裁决",
             "body": "\n".join(rows) if dedup else "本仓库暂无已登记命题。",
             "refs": [{"kind": "claim", "claim_id": k} for k in list(dedup)[:60]]}]

    if detail:
        secs.append({"section_id": "evidence", "heading": "证据定位",
                     "body": "\n".join(detail[:40]), "refs": []})
    return {"document_id": "claims", "title": "知识主张与证据", "sections": secs}


def mine_project_knowledge(*, store, repository_id, commit_sha, tree_entries,
                           code_rows, claims, verifications, data_root):
    """总入口：产出 documents + project 元信息。"""
    texts, blob_meta = _blob_texts(store, repository_id, data_root)
    readme_path, readme_text = _readme_from_tree(texts, tree_entries)
    manifest_path, manifest = _manifest_from_tree(texts, tree_entries)
    readme_sections = parse_markdown(readme_text) if readme_text else []

    # ★ 从已读原文抽符号（只在没有 AST 观察时作为回退证据）
    source_symbols = []
    for path, text in texts.items():
        if not text:
            continue
        digest = (blob_meta.get(path) or {}).get("digest")
        for sym in extract_symbols_from_source(path, text):
            sym["digest"] = digest
            source_symbols.append(sym)

    repo_name = None
    try:
        import bot_card as BCARD
        repo_name = BCARD.lookup_repo_name(store, str(repository_id))
    except Exception:
        pass

    # 完整度说明（如实）
    depth = max((str(e.get("path") or "").count("/") for e in (tree_entries or [])),
                default=0)
    n = len(tree_entries or [])
    if depth == 0 and n > 0:
        coverage_note = f"仅根层（{n} 条目，最大深度 0）；子目录内容未采集"
    else:
        coverage_note = f"{n} 条目，最大深度 {depth}"

    docs = [
        build_overview(repo_name=repo_name, commit_sha=commit_sha,
                       tree_entries=tree_entries, readme_path=readme_path,
                       readme_sections=readme_sections, manifest=manifest,
                       manifest_path=manifest_path, code_rows=code_rows,
                       claims=claims, coverage_note=coverage_note,
                       source_symbols=source_symbols),
        build_readme_doc(repo_name=repo_name, commit_sha=commit_sha,
                         readme_path=readme_path,
                         readme_sections=readme_sections),
        build_structure_doc(repo_name=repo_name, commit_sha=commit_sha,
                            tree_entries=tree_entries,
                            coverage_note=coverage_note),
        build_deps_doc(repo_name=repo_name, commit_sha=commit_sha,
                       code_rows=code_rows, manifest=manifest,
                       manifest_path=manifest_path,
                       source_symbols=source_symbols),
        build_claims_doc(repo_name=repo_name, commit_sha=commit_sha,
                         claims=claims, verifications=verifications),
    ]

    for d in docs:
        d["schema"] = SCHEMA
        d["repository_id"] = str(repository_id)
        d["commit_sha"] = commit_sha
        d["section_count"] = len(d["sections"])

    return {
        "documents": docs,
        "project": {
            "blobs_read": len(texts),
            "symbols_from_source": len(source_symbols),
            "blob_meta": blob_meta,
            "readme_path": readme_path,
            "readme_captured": bool(readme_text),
            "manifest_path": manifest_path,
            "manifest_parsed": isinstance(manifest, dict),
            "coverage_note": coverage_note,
            "code_observation_count": len(code_rows or []),
        },
    }
