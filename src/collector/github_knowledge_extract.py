#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 路径：已捕获字节 → 内容事实 + 源码事实 + 命题。

★ 复用既有抽取链路，不新增任何解析器。
★ 只处理**已在本地有完整字节**的文件；不触发网络。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("content", "content_persistence", "source_analysis", "storage",
           "facts", "evidence_claims", "skill_interface", "collector",
           "renderer"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

SOURCE_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".py")


def extract_captured(*, store, data_root, repository_id, commit_sha,
                     content_report, paths=None):
    """对已捕获文件抽取知识。★ 完全离线。"""
    import content_ingest_coordinator as CIC
    import content_extractor as CX
    import content_fact_ingest as CFI
    import content_claim_adapter as CCA
    import content_claim_ingest as CCI
    import content_knowledge_query as CKQ
    import blob_content_store as BS
    import ec_models as M

    # 已捕获且完整的路径
    captured = []
    for r in (content_report.get("results") or []):
        if r.get("status") in ("CAPTURED_VERIFIED", "ALREADY_CAPTURED",
                              "CONTENT_CAPTURED_VERIFIED") or r.get("reused"):
            captured.append(r["file_path"])
    if paths:
        captured = [p for p in captured if p in set(paths)]

    out = {"ok": True, "files": [], "content_facts": 0, "source_facts": 0,
           "claims": 0, "verifications": 0,
           "limitations": [
               "只处理已捕获且完整的本地字节；不联网",
               "静态分析不等于运行时行为验证",
           ]}

    for path in captured:
        rec = {"file_path": path, "content_extracted": False,
               "content_facts": 0, "source_facts": 0,
               "claims": 0, "verifications": 0, "notes": []}
        meta = CIC.find_content_asset(store, repository_id=str(repository_id),
                                      commit_sha=str(commit_sha),
                                      file_path=path)
        if meta is None:
            rec["notes"].append("CONTENT_ASSET_MISSING")
            out["files"].append(rec)
            continue

        raw = _load_bytes(data_root, meta)
        if raw is None:
            rec["notes"].append("CONTENT_BYTES_UNREADABLE")
            out["files"].append(rec)
            continue

        sha = meta.get("git_blob_oid") or ""
        caid = meta.get("content_asset_id")
        cdigest = meta.get("content_sha256")

        # ① 内容抽取
        try:
            ex = CX.extract_one(
                repository_id=str(repository_id), commit_sha=str(commit_sha),
                file_path=path, git_blob_oid=sha,
                content_asset_id=caid, data=raw,
                source_snapshot_id=meta.get("source_snapshot_id") or "",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE",
                declared_completeness="COMPLETE")
            if ex.get("status") == "CONTENT_AVAILABLE":
                fr = CFI.ingest_content_facts(
                    store, repository_id=str(repository_id),
                    commit_sha=str(commit_sha),
                    snapshot_asset_id=meta.get("source_snapshot_id") or "",
                    snapshot_logical_identity="SL-SNAP-%s" % repository_id,
                    extraction_result={"facts": ex.get("facts") or []},
                    content_asset_id=caid, content_sha256=cdigest,
                    parser_id="content-extractor", parser_version="1",
                    file_path=path, git_blob_oid=sha,
                    completeness_status="COMPLETE",
                    provenance_level="AUTHORIZED_LOCAL_FIXTURE")
                n = len(fr.get("written") or [])
                rec["content_facts"] = n
                rec["content_extracted"] = True
                out["content_facts"] += n
            else:
                rec["notes"].append("CONTENT_NOT_AVAILABLE:%s" % ex.get("status"))
        except Exception as e:
            rec["notes"].append("CONTENT_EXTRACT_FAILED:%s" % type(e).__name__)

        # ② 内容命题
        if rec["content_facts"]:
            c = _content_claims(
                store=store, repository_id=repository_id,
                commit_sha=commit_sha, path=path,
                CCA=CCA, CCI=CCI, CKQ=CKQ, M=M)
            rec["claims"] += c["claims"]
            rec["verifications"] += c["verifications"]
            out["claims"] += c["claims"]
            out["verifications"] += c["verifications"]
            rec["notes"].extend(c.get("errors") or [])

        # ③ 源码结构
        if path.endswith(SOURCE_SUFFIXES):
            try:
                import source_dispatch as SD
                import source_fact_ingest as SFI
                obs = SD.parse_source(
                    raw, repository_id=str(repository_id),
                    commit_sha=str(commit_sha), file_path=path,
                    git_blob_oid=sha, content_asset_id=caid,
                    content_sha256=cdigest,
                    provenance_level="AUTHORIZED_LOCAL_FIXTURE")
                rec["parser_status"] = obs.get("parse_status")
                if obs.get("extraction_status") == "EXTRACTED":
                    sr = SFI.ingest_source_facts(
                        store, observation=obs,
                        source_snapshot_id=meta.get("source_snapshot_id") or "")
                    n = len(sr.get("written") or [])
                    rec["source_facts"] = n
                    out["source_facts"] += n
                    rec["symbols"] = len(obs.get("observed_symbols") or [])
                    rec["exports"] = len(obs.get("observed_exports") or [])
                    rec["imports"] = len(obs.get("observed_imports") or [])
                    if n == 0:
                        rec["notes"].append(
                            "VALID_EMPTY_RESULT: 该文件在解析契约内无可登记结构 "
                            "(可能是 CommonJS module.exports，不在当前 export 契约)")
            except Exception as e:
                rec["notes"].append("SOURCE_PARSE_FAILED:%s" % type(e).__name__)

        out["files"].append(rec)
    return out


def _load_bytes(data_root, meta):
    import hashlib
    from pathlib import Path as _P
    sha = (meta.get("content_sha256") or "").replace("sha256:", "")
    if not sha:
        return None
    f = _P(data_root) / "blobs" / (sha + ".bin")
    if not f.exists():
        return None
    return f.read_bytes()


def _content_claims(*, store, repository_id, commit_sha, path,
                    CCA, CCI, CKQ, M):
    """复用 local_content_ingest 的命题逻辑（同一条链路）。"""
    import local_content_ingest as LCI
    stored = CKQ.query_content_facts(
        store=store, repository_id=str(repository_id),
        commit_sha=str(commit_sha), file_path=path, limit=500)
    return LCI._build_content_claims(
        store, repository_id=str(repository_id), commit_sha=str(commit_sha),
        file_path=path, extraction={"written": [{"fact_id": f.get("fact_id")}
                                               for f in stored]},
        facts=[], snapshot_asset_id="", evidence_refs=[])
