#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对已采集的源码正文跑 tree-sitter 符号提取，并把结构事实入库。

★ 为什么需要（2026-11-12 实证）：
  preact 已抓到 src/component.js(7763B)、src/diff/index.js(24615B)、src/index.js(423B)，
  但 assets 表里只有 captured_blob_content / claim_* / extracted_fact，
  完全没有 source_structure_observation → `query --type code` 返回 0 行，
  需求文档 F2_P6A 承诺的「Python 符号 / TS 符号 / Import」在真实仓库上从未产出。

★ 只用官方组件，不自造格式：
  - treesitter_runtime.parse_bytes / language_for_path / walk
  - js_ts_symbol_rules.collect_symbols
  - source_fact_ingest.build_source_fact / ingest_source_facts

用法：
  python3 tools/extract_symbols.py --repository-id 42283287
  python3 tools/extract_symbols.py --repository-id 42283287 --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_SRC = _THIS.parent.parent / "src"
sys.path.insert(0, str(_SRC / "skill_interface"))
import paths  # noqa: E402
paths.ensure_import_path()

from knowledge_store import KnowledgeStore                 # noqa: E402
from paths import db_path as _db_path                       # noqa: E402
import blob_content_store as BS                             # noqa: E402
import treesitter_runtime as TR                             # noqa: E402
import js_ts_symbol_rules as RULES                          # noqa: E402


def _iter_captured_sources(store, repository_id):
    """列出该仓库已采集的可解析源文件。"""
    rows = store.conn.execute(
        "select asset_id, payload_json from assets "
        "where repository_id=? and asset_type='captured_blob_content'",
        (str(repository_id),)).fetchall()
    out = []
    for asset_id, pj in rows:
        try:
            p = json.loads(pj)
        except Exception:
            continue
        path = p.get("file_path") or ""
        lang = TR.language_for_path(path)
        if not lang:
            continue
        out.append({
            "asset_id": asset_id,
            "file_path": path,
            "language": lang,
            "content_sha256": (p.get("content_sha256") or "").split(":", 1)[-1],
            "commit_sha": p.get("commit_sha"),
            "git_blob_oid": p.get("git_blob_oid"),
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository-id", required=True)
    ap.add_argument("--data-root")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    data_root = a.data_root or str(_THIS.parent.parent.parent / "SourceLore_Data")
    dbp = _db_path(data_root)
    if not Path(dbp).exists():
        print(json.dumps({"ok": False, "error": "KNOWLEDGE_DB_MISSING"}, ensure_ascii=False))
        return 3

    store = KnowledgeStore(str(dbp), create=False)
    sources = _iter_captured_sources(store, a.repository_id)

    report = {"ok": True, "repository_id": a.repository_id,
              "scanned": [], "symbols": [], "errors": []}

    for src in sources:
        got = BS.get_bytes(data_root=data_root,
                           content_sha256=src["content_sha256"], verify=True)
        if not got.get("ok"):
            report["errors"].append({"file_path": src["file_path"],
                                     "error": got.get("error")})
            continue
        raw = got["raw"]

        try:
            # ★ 用官方 parse_source：一次产出 symbols / imports / exports / evidence_ranges，
            #   不要再手工拼 observation（会漏掉 imports 与 exports 的 evidence_ref）。
            import js_ts_parser as JTP
            obs = JTP.parse_source(
                raw,
                repository_id=str(a.repository_id),
                commit_sha=src["commit_sha"],
                file_path=src["file_path"],
                git_blob_oid=src["git_blob_oid"],
                content_asset_id=src["asset_id"],
                content_sha256="sha256:" + src["content_sha256"],
                provenance_level="OBSERVED",
            )
            syms = obs.get("observed_symbols") or []
            report.setdefault("_observations", []).append(
                (src["file_path"], obs))
            report.setdefault("_relations_src", []).append(
                (src["file_path"], obs))
        except Exception as exc:
            report["errors"].append({"file_path": src["file_path"],
                                     "error": "parse: %s" % exc})
            continue
        parse_status = obs.get("status", "")
        diags = {"has_error": parse_status != "EXTRACTED"}

        report["scanned"].append({
            "file_path": src["file_path"],
            "language": src["language"],
            "byte_length": len(raw),
            "symbol_count": len(syms),
            "parse_status": str(parse_status),
            "parse_error": bool(diags.get("has_error")),
        })
        for s in syms:
            rec = dict(s)
            rec["file_path"] = src["file_path"]
            rec["language"] = src["language"]
            report["symbols"].append(rec)

    report["scanned_count"] = len(report["scanned"])
    report["symbol_count"] = len(report["symbols"])

    if not a.dry_run and report.get("_observations"):
        import source_fact_ingest as SFI
        agg = {"written": [], "reused": [], "skipped": []}
        for file_path, o in report["_observations"]:
            if not (o.get("observed_symbols") or o.get("observed_imports")
                    or o.get("observed_exports")):
                continue
            try:
                r = SFI.ingest_source_facts(store, observation=o,
                                            source_snapshot_id=None)
                for k in ("written", "reused", "skipped"):
                    agg[k].extend(r.get(k) or [])
                report.setdefault("ingest_files", []).append({
                    "file_path": file_path,
                    "written": len(r.get("written") or []),
                    "reused": len(r.get("reused") or []),
                    "skipped": len(r.get("skipped") or []),
                })
            except Exception as exc:
                report.setdefault("ingest_files", []).append({
                    "file_path": file_path, "error": str(exc)})
        report["ingest"] = {
            "written": len(agg["written"]),
            "reused": len(agg["reused"]),
            "skipped": len(agg["skipped"]),
            "skip_samples": agg["skipped"][:5],
        }
        report.pop("_observations", None)

    # ── relation 阶段：把已采集文件之间的相对 import 解析成真实路径 ──
    #   ★ 只用「已采集文件集合」作 tree_paths。解析结果只覆盖这些文件之间的引用，
    #     不得声称是全仓库依赖图。
    if not a.dry_run:
        try:
            import js_ts_module_resolver as RES
            import module_relation_ingest as MRI
            # ★ 实测 resolve_js_import 成功时返回字符串 "LOCAL_MODULE_RESOLVED"，
            #   该常量分散在多个模块，直接用字面量最稳（已实测确认）。
            RESOLVED_STATE = "LOCAL_MODULE_RESOLVED"
            import ingest as FI

            tree_paths = sorted({x.get("file_path") for x in
                                 _iter_captured_sources(store, a.repository_id)
                                 if x.get("file_path")})
            rel_written, rel_skipped = [], []
            for file_path, o in (report.get("_relations_src") or []):
                for imp in (o.get("observed_imports") or []):
                    r = RES.resolve_js_import(
                        import_record=imp, source_path=file_path,
                        tree_paths=tree_paths)
                    if r.get("status") != RESOLVED_STATE:
                        continue
                    target = r["candidates"][0]["path"]
                    resolution = {
                        "resolution_id": "SL-REL-%s-%s" % (
                            o["observation_id"].split("-")[-1],
                            abs(hash((file_path, imp.get("module_specifier"),
                                      target))) % (10 ** 12)),
                        "repository_id": str(a.repository_id),
                        "commit_sha": o["commit_sha"],
                        "importing_file_path": file_path,
                        "module_specifier": imp.get("module_specifier"),
                        "import_kind": imp.get("import_kind"),
                        "is_type_only": bool(imp.get("is_type_only")),
                        "resolved_target_path": target,
                        "resolution_state": r["status"],
                        "resolution_policy": "RELATIVE_LOCAL",
                        "candidate_paths": r.get("candidates") or [],
                        "importing_blob_oid": o.get("git_blob_oid"),
                        "importing_content_asset_id": o.get("content_asset_id"),
                        "resolver_version": "js-ts-resolver/1",
                        "provenance_level": "OBSERVED",
                    }
                    ev_refs = [imp.get("evidence_ref")] if imp.get("evidence_ref") else []
                    try:
                        fact = MRI.build_relation_fact(
                            resolution=resolution, evidence_refs=ev_refs)
                        prev = store.conn.execute(
                            "SELECT asset_id FROM index_rows WHERE "
                            "asset_type='extracted_fact' AND logical_identity=?",
                            (fact.fact_id,)).fetchone()
                        if prev:
                            rel_skipped.append({"reason": "reused"})
                            continue
                        res = FI.ingest_fact(store, fact)
                        if res.get("ok"):
                            rel_written.append({
                                "from": file_path, "spec": imp.get("module_specifier"),
                                "to": target})
                        else:
                            rel_skipped.append({"reason": res.get("error")})
                    except Exception as exc:
                        rel_skipped.append({"reason": str(exc)})
            report["relation"] = {
                "tree_paths": len(tree_paths),
                "written": len(rel_written),
                "skipped": len(rel_skipped),
                "edges": rel_written[:20],
                "coverage_note": ("仅覆盖已采集 %d 个文件之间的相对引用，"
                                  "不代表全仓库依赖图" % len(tree_paths)),
            }
        except Exception as exc:
            report["relation"] = {"error": str(exc)}

    # ── ts_project 阶段：jsconfig.json / tsconfig.json → 项目声明事实 ──
    if not a.dry_run:
        try:
            import ts_project_context as TPC
            import ts_project_ingest as TPI

            # ★ tree_paths 必须包含**所有已采集文件**（含配置文件本身），
            #   不能只用可解析的源码文件——否则 discover_config_paths 找不到 jsconfig。
            tree_paths = sorted({
                json.loads(pj).get("file_path")
                for (pj,) in store.conn.execute(
                    "select payload_json from assets where repository_id=? "
                    "and asset_type='captured_blob_content'",
                    (str(a.repository_id),)).fetchall()
                if json.loads(pj).get("file_path")})
            # 收集配置文件字节
            config_blobs = {}
            for (asset_id, pj) in store.conn.execute(
                    "select asset_id, payload_json from assets where "
                    "repository_id=? and asset_type='captured_blob_content'",
                    (str(a.repository_id),)).fetchall():
                pp = json.loads(pj)
                fp = pp.get("file_path") or ""
                if not fp.endswith(("tsconfig.json", "jsconfig.json")):
                    continue
                sha = (pp.get("content_sha256") or "").split(":", 1)[-1]
                got = BS.get_bytes(data_root=data_root, content_sha256=sha,
                                   verify=True)
                if got.get("ok"):
                    config_blobs[fp] = {
                        "raw": got["raw"],
                        "blob_oid": pp.get("git_blob_oid"),
                        "content_asset_id": asset_id,
                        "content_digest": sha,
                    }
            if config_blobs:
                built = TPC.build_all_projects(
                    tree_paths=tree_paths, config_blobs=config_blobs,
                    repository_id=str(a.repository_id),
                    commit_sha=list(config_blobs.values()) and
                               json.loads(store.conn.execute(
                                   "select payload_json from assets where asset_type="
                                   "'captured_blob_content' and repository_id=? limit 1",
                                   (str(a.repository_id),)).fetchone()[0]).get("commit_sha"),
                    provenance_level="OBSERVED")
                proj_new = proj_reused = proj_fail = 0
                for proj in (built.get("projects") or []):
                    r = TPI.ingest_project(store, project=proj)
                    # ★ _put 返回 {written:bool, reused:bool}，没有 ok 键。
                    #   把 reused 当失败会误报——先前的 projects_written=0 就是这个 bug。
                    if r.get("written"):
                        proj_new += 1
                    elif r.get("reused"):
                        proj_reused += 1
                    else:
                        proj_fail += 1
                report["ts_project"] = {
                    "config_blobs": list(config_blobs),
                    "projects_built": len(built.get("projects") or []),
                    "projects_new": proj_new,
                    "projects_reused": proj_reused,
                    "projects_failed": proj_fail,
                }
            else:
                report["ts_project"] = {
                    "config_blobs": [], "note": "未采集到 tsconfig.json / jsconfig.json"}
        except Exception as exc:
            report["ts_project"] = {"error": str(exc)}

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
