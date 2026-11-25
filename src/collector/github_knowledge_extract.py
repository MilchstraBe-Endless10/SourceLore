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


def _tree_paths_from_snapshot(store, repository_id, commit_sha):
    """从已登记快照读取同 Commit 的完整路径集合（零网络）。

    返回 (tree_paths:set, completeness:str)。没有完整清单时返回空集合 +
    'UNKNOWN'，让 resolver 诚实降级到 INSUFFICIENT_TREE_COVERAGE。
    """
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    paths, completeness = set(), "UNKNOWN"
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("commit_sha") != str(commit_sha):
            continue
        completeness = pl.get("completeness_status") or "UNKNOWN"
        entries = pl.get("tree_entries")
        if not entries:
            for br in pl.get("blob_refs") or []:
                p = br.get("path") if isinstance(br, dict) else br
                if p:
                    paths.add(p)
            break
        for e in entries:
            if isinstance(e, dict):
                p = e.get("path")
                if p and e.get("type", "blob") != "tree":
                    paths.add(p)
            elif e:
                paths.add(e)
        break
    return paths, completeness


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

    source_entries, config_entries = [], []
    rr_provenance = None
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
        # ★ D-68：抽取产物的来源等级必须**继承自被抽取的 blob**，
        #   不能硬编码。真实远程 blob 抽出的源码事实仍是 AUTHORIZED_REMOTE_SOURCE；
        #   合成夹具抽出的仍是合成夹具。谎报任何一方都是证据造假。
        _prov = meta.get("provenance_level")
        if not _prov:
            rec["notes"].append("PROVENANCE_UNKNOWN")
            out["files"].append(rec)
            continue
        rr_provenance = rr_provenance or _prov

        # ① 内容抽取
        try:
            ex = CX.extract_one(
                repository_id=str(repository_id), commit_sha=str(commit_sha),
                file_path=path, git_blob_oid=sha,
                content_asset_id=caid, data=raw,
                source_snapshot_id=meta.get("source_snapshot_id") or "",
                provenance_level=_prov,
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
                    provenance_level=_prov)
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
                    provenance_level=_prov)
                rec["parser_status"] = obs.get("parse_status")
                if obs.get("extraction_status") == "EXTRACTED":
                    sr = SFI.ingest_source_facts(
                        store, observation=obs,
                        source_snapshot_id=meta.get("source_snapshot_id") or "")
                    # ★ D-62：reused 也是有效事实（重复执行不该报 0）。
                    n_written = len(sr.get("written") or [])
                    n_reused = len(sr.get("reused") or [])
                    n = n_written + n_reused
                    rec["source_facts"] = n
                    rec["source_facts_written"] = n_written
                    rec["source_facts_reused"] = n_reused
                    out["source_facts"] += n
                    rec["symbols"] = len(obs.get("observed_symbols") or [])
                    rec["exports"] = len(obs.get("observed_exports") or [])
                    rec["imports"] = len(obs.get("observed_imports") or [])
                    # ★ D-53：解析成功 != 语义被理解。
                    #   0 事实时不能一律报 VALID_EMPTY_RESULT，
                    #   必须先查有没有「已识别但未支持」的形态。
                    import semantic_coverage as SC
                    text = raw.decode("utf-8", "replace")
                    forms = SC.detect_unsupported_forms(text)
                    _nodes = (len(obs.get("observed_symbols") or [])
                              + len(obs.get("observed_exports") or [])
                              + len(obs.get("observed_imports") or []))
                    cov = SC.coverage_report(
                        file_path=path, language=obs.get("language") or "javascript",
                        parser_version="js-ts/1",
                        parse_status=obs.get("parse_status") or "PARSE_COMPLETE",
                        facts_persisted=n, claims_verified=0,
                        observed_nodes=_nodes,
                        unsupported_forms=forms)
                    rec["coverage"] = cov
                    rec["analysis_coverage"] = cov["analysis_coverage"]
                    if cov["analysis_coverage"] == SC.UNSUPPORTED_SEMANTIC_FORM:
                        rec["notes"].append(
                            "UNSUPPORTED_SEMANTIC_FORM: 存在已识别但规则族未覆盖的形态 "
                            + ",".join(forms))
                    # ★ 收集到统一输入（在线链路），配置与源码身份分离。
                    name = path.rsplit("/", 1)[-1]
                    if name in ("tsconfig.json", "jsconfig.json"):
                        config_entries.append({
                            "config_path": path, "raw": raw,
                            "blob_oid": sha, "content_asset_id": caid,
                            "content_digest": cdigest})
                    else:
                        source_entries.append({
                            "file_path": path, "raw": raw,
                            "git_blob_oid": sha, "content_asset_id": caid,
                            "content_sha256": cdigest})
            except Exception as e:
                rec["notes"].append("SOURCE_PARSE_FAILED:%s" % type(e).__name__)

        out["files"].append(rec)

    # ★ 在线链路接入共享关系组件（与本地链路同一契约，零网络）。
    tree_paths, tree_completeness = _tree_paths_from_snapshot(
        store, repository_id, commit_sha)
    out["relation"] = {"status": "NOT_RUN",
                       "tree_completeness": tree_completeness,
                       "tree_paths": len(tree_paths)}
    if source_entries or config_entries:
        try:
            import module_relation_pipeline as MRP
            rr = MRP.process_source_relations(
                store, repository_id=repository_id, commit_sha=commit_sha,
                file_sources=source_entries, config_sources=config_entries,
                tree_paths=tree_paths,
                source_completeness=("COMPLETE" if tree_completeness
                                     in ("COMPLETE", "FULL") else "INCOMPLETE"),
                provenance_level=rr_provenance or "AUTHORIZED_REMOTE_SOURCE",
                source_snapshot_id="")
            out["relation"] = rr
            out["relation"]["tree_completeness"] = tree_completeness
        except Exception as e:
            out["relation"] = {"status": f"ERROR:{type(e).__name__}:{e}",
                               "tree_completeness": tree_completeness}
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
