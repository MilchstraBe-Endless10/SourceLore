#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p6f_capture 安装版 CLI 测试的隔离夹具（tempfile 专属，绝不触碰真实用户库）。

历史背景 / 修复说明
--------------------
test_installed_cli.py 的三个用例（query / offline analyze / plan）曾把
SOURCELORE_DATA_ROOT 写死到 ``/tmp/p6b_real`` —— 那是早期人工验收留下的
易失数据根。清理后该目录只剩空 cards/、没有 kb.db，于是 CLI 如实返回：
  * query   → REPOSITORY_NOT_REGISTERED（测试期望 SUPPORTED）
  * analyze --offline → OFFLINE_CACHE_MISS（退出码 3）
  * analyze --plan    → KNOWLEDGE_DB_MISSING（退出码 3）
这些是 CLI 对“空知识库”的正确响应，不是产品回归；P0 改动只涉及
trust/renderer/cards，未触及 data_root 解析。

本夹具用 tempfile.mkdtemp() 建隔离 data_root，并用与
tools/f2p5f_e2e.py 相同的真实入库链路（build_snapshot/ingest_snapshot
→ ingest_captured_blob → extract_one → ingest_content_facts →
build_content_claim/verify_content_claim/ingest_content_claim）从**原创
README 文本**构造一份最小知识库。它让三个用例在真实 CLI 子进程里得到真实的
SUPPORTED / 零网络 / 只读计划结果：不复制任何真实用户库，不伪造成功状态，
不修改 CLI 的错误语义。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in ("runtime", "storage", "collector", "facts", "evidence_claims",
           "lifecycle", "views", "renderer", "research", "skill_interface",
           "content", "content_persistence", "source_analysis"):
    _sp = str(ROOT / "src" / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# 与被测 CLI 保持同一身份参数；fixture 内所有内容均为本文件内原创文本。
REPOSITORY_ID = "24313173"
COMMIT = "98e8ff1da1a89f93d1397a24d7413ed15421c139"
README_PATH = "README.md"
PACKAGE_PATH = "package.json"
OWNER, NAME = "jonschlinkert", "is-number"

README = (
    b"# is-number fixture\n\n"
    b"Original synthetic fixture authored for p6f_capture tests.\n\n"
    b"## Installation\n\n"
    b"This heading is extracted by the real README parser.\n"
)
PACKAGE = json.dumps(
    {"name": "fixture-is-number", "version": "1.0.0",
     "dependencies": {"fixture-dep": "^1.0.0"}},
    indent=2,
).encode("utf-8")
FILES = ((README_PATH, README), (PACKAGE_PATH, PACKAGE))


def git_blob_oid(raw: bytes) -> str:
    import blob_fetcher as BF
    return BF.git_blob_oid(raw)


def build(data_root: str | Path) -> None:
    """在空目录 data_root 里构造最小但真实的知识库。"""
    import content_acquisition_policy as POL
    import content_ingest_coordinator as CIC
    import content_extractor as EX
    import content_fact_ingest as FI
    import content_claim_adapter as CA
    import content_claim_ingest as CI
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)
    ks = KnowledgeStore(str(root / "kb.db"))
    try:
        auth = POL.build_authorization_ref(
            authorization_kind=POL.AUTH_ORIGINAL_FIXTURE,
            repository_id=REPOSITORY_ID,
            scope=[p for p, _ in FILES],
            source="p6f_capture-synthetic-fixture",
            verification_status=POL.VERIFIED)

        entries = [{"path": path, "sha": git_blob_oid(raw), "size": len(raw),
                    "type": "blob", "mode": "100644"}
                   for path, raw in FILES]
        snap = build_snapshot(
            repository_id=REPOSITORY_ID,
            requested_repository=f"{OWNER}/{NAME}",
            resolved_repository=f"{OWNER}/{NAME}",
            requested_ref="main", commit_sha=COMMIT,
            root_tree_sha="t" * 40, tree_query_ref="t" * 40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"fixture@{COMMIT}"],
            # deep_walk_used 由 READ_ME 的 tree_summary 复核使用；此夹具是
            # 原创最小树，仅根层两个 blob，标记 deep_walk 以免被误判 ROOT_ONLY。
            deep_walk_used=True)
        snap_ing = ingest_snapshot(ks, snap)
        snap_id = snap_ing["asset_id"]
        logical = ks.get_asset(snap_id, verify=True)["asset"]["logical_identity"]

        # analyze 按 owner/name 定位仓库依赖本地 slug 速查表（非权威旁路）
        (root / "repo_slugs.json").write_text(
            json.dumps({f"{OWNER}/{NAME}".lower(): REPOSITORY_ID},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

        for path, raw in FILES:
            oid = git_blob_oid(raw)
            dec = POL.evaluate_all(repository_id=REPOSITORY_ID,
                                   commit_sha=COMMIT, file_path=path,
                                   authorization=auth)
            if dec["PERSIST_DECISION"]["decision"] != POL.ALLOW:
                raise RuntimeError(f"fixture authorization blocked {path}: {dec}")
            cap = CIC.ingest_captured_blob(
                ks, data_root=str(root), repository_id=REPOSITORY_ID,
                commit_sha=COMMIT, source_snapshot_id=snap_id, file_path=path,
                git_blob_oid=oid, git_object_format="sha1", raw=raw,
                source_declared_size=len(raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            if not cap.get("ok"):
                raise RuntimeError(f"fixture blob ingest failed for {path}: {cap}")

            parser_id = EX.pick_parser(path)[1]
            ex = EX.extract_one(
                repository_id=REPOSITORY_ID, commit_sha=COMMIT,
                file_path=path, git_blob_oid=oid,
                content_asset_id=cap["content_asset_id"], data=raw,
                source_snapshot_id=snap_id,
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            FI.ingest_content_facts(
                ks, repository_id=REPOSITORY_ID, commit_sha=COMMIT,
                snapshot_asset_id=snap_id, snapshot_logical_identity=logical,
                extraction_result=ex,
                content_asset_id=cap["content_asset_id"],
                content_sha256=cap["content_sha256"], parser_id=parser_id,
                parser_version="1.0.0", file_path=path, git_blob_oid=oid,
                completeness_status="COMPLETE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")

            if path != README_PATH:
                continue
            # 真实裁决：为每个 README 标题建命题，用抽取到的事实做验证，
            # 走与正式流水线相同的 ingest_content_claim，得到真实 supported。
            payloads = []
            for row in ks.conn.execute(
                    "SELECT asset_id FROM index_rows "
                    "WHERE asset_type='extracted_fact' AND repository_id=?",
                    (REPOSITORY_ID,)).fetchall():
                got = ks.get_asset(row["asset_id"], verify=True)
                if not got.get("ok"):
                    continue
                pl = (got["asset"] or {}).get("payload") or {}
                np_ = pl.get("normalized_parameters") or {}
                if (pl.get("commit_sha") == COMMIT
                        and np_.get("file_path") == README_PATH):
                    payloads.append(pl)

            for fact in (ex.get("facts") or []):
                if fact.get("rule_id") != "README_HEADING_EXISTS":
                    continue
                subject = fact.get("subject") or {}
                claim, binding = CA.build_content_claim(
                    claim_type="readme_heading_exists",
                    repository_id=REPOSITORY_ID, commit_sha=COMMIT,
                    file_path=README_PATH, subject={
                        "level": subject.get("level"),
                        "title": subject.get("title")},
                    snapshot_logical_identity=logical)
                verdict = CA.verify_content_claim(
                    claim=claim, facts=payloads, content_available=True,
                    completeness_status="COMPLETE", subject_binding=binding)
                res = CI.ingest_content_claim(
                    ks, claim=claim, verdict=verdict, facts_payload=payloads,
                    repository_id=REPOSITORY_ID,
                    evidence_refs=[f"content:{cap['content_asset_id']}"])
                if not res.get("ok") or verdict.get("status") != "supported":
                    raise RuntimeError(
                        f"fixture claim/verification failed: {verdict} {res}")
    finally:
        ks.close()


class FixtureRoot:
    """上下文管理器：tempfile 临时根 + 自动清理。"""

    def __init__(self):
        self.path: Path | None = None

    def __enter__(self) -> str:
        tmp = tempfile.mkdtemp(prefix="p6f_installed_cli_")
        self.path = Path(tmp)
        build(tmp)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        if self.path is not None:
            import shutil
            shutil.rmtree(self.path, ignore_errors=True)
        return False
