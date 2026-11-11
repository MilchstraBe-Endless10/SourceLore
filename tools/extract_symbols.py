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

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
