"""共享：原创夹具全链路构建（供 E2E 与 Gold 复用）。"""
import sys, os, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import fixtures as FX
import blob_content_store as BS, content_ingest_coordinator as CIC
import captured_blob_loader as L, blob_fetcher as BF
import content_acquisition_policy as POL
import content_extractor as EX, content_models as CM
import content_fact_ingest as FI, content_claim_adapter as CA
from knowledge_store import KnowledgeStore
from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot


def authorized():
    return POL.build_authorization_ref(
        authorization_kind=POL.AUTH_ORIGINAL_FIXTURE,
        repository_id=FX.REPO,
        scope=["README.md", "package.json", "pyproject.toml"],
        source="project-original-fixture",
        verification_status=POL.VERIFIED)


def make_snapshot(ks, commit, files):
    entries = []
    for path, raw in files:
        entries.append({"path": path, "sha": FX.oid(raw), "size": len(raw),
                        "type": "blob", "mode": "100644"})
    snap = build_snapshot(
        repository_id=FX.REPO, requested_repository="origin/demo",
        resolved_repository="origin/demo", requested_ref="main",
        commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
        completeness_status="COMPLETE", tree_entries=entries,
        collected_at="", evidence_refs=[f"github@{commit}"])
    ing = ingest_snapshot(ks, snap)
    li = ks.get_asset(ing["asset_id"], verify=True)["asset"]["logical_identity"]
    return ing["asset_id"], li


def capture(ks, tmp, snap_asset, commit, files, auth=None):
    """五维授权 → 持久化 → 返回 content map。"""
    auth = auth or authorized()
    out = {}
    for path, raw in files:
        dec = POL.evaluate_all(repository_id=FX.REPO, commit_sha=commit,
                               file_path=path, authorization=auth)
        if dec["PERSIST_DECISION"]["decision"] != POL.ALLOW:
            out[path] = {"blocked": dec}
            continue
        r = CIC.ingest_captured_blob(
            ks, data_root=tmp, repository_id=FX.REPO, commit_sha=commit,
            source_snapshot_id=snap_asset, file_path=path,
            git_blob_oid=FX.oid(raw), git_object_format="sha1", raw=raw,
            source_declared_size=len(raw),
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        out[path] = {"asset_id": r.get("content_asset_id"),
                     "sha256": r.get("content_sha256"),
                     "oid": FX.oid(raw), "raw": raw, "ok": r.get("ok"),
                     "decisions": dec}
    return out


def extract_and_ingest(ks, snap_asset, snap_li, commit, content, paths=None):
    """解析 → Facts 入库 → 返回 (facts_payload, per_path)。"""
    res = {}
    for path, meta in content.items():
        if meta.get("blocked"):
            continue
        if paths and path not in paths:
            continue
        parser_id = (EX.pick_parser(path)[0] or "meta") if hasattr(EX, "pick_parser") else "meta"
        ex = EX.extract_one(repository_id=FX.REPO, commit_sha=commit,
                            file_path=path, git_blob_oid=meta["oid"],
                            content_asset_id=meta["asset_id"],
                            data=meta["raw"], source_snapshot_id=snap_asset,
                            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        ing = FI.ingest_content_facts(
            ks, repository_id=FX.REPO, commit_sha=commit,
            snapshot_asset_id=snap_asset, snapshot_logical_identity=snap_li,
            extraction_result=ex, content_asset_id=meta["asset_id"],
            content_sha256=meta["sha256"], parser_id=parser_id,
            parser_version="1.0.0", file_path=path,
            git_blob_oid=meta["oid"], completeness_status="COMPLETE",
            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        payloads = []
        for w in ing["written"]:
            got = ks.get_asset(w["asset_id"], verify=True)
            if got.get("ok"):
                payloads.append(got["asset"]["payload"])
        res[path] = {"extraction": ex, "ingest": ing, "facts": payloads}
    return res
