#!/usr/bin/env python3
"""F2-P5G 三进程 E2E：写入 → 查询 → 卡片。★ 原创授权 Python 夹具。"""
import sys, os, json, tempfile, shutil
from pathlib import Path
R = Path(__file__).resolve().parents[1]
for p in ("runtime","storage","collector","facts","evidence_claims","lifecycle",
          "views","renderer","research","content","content_persistence",
          "source_analysis","skill_interface"):
    sys.path.insert(0, str(R/"src"/p))

REPO = "990001"
COMMIT_A = "a"*40
COMMIT_B = "b"*40
TMP = os.environ.get("SL_P5G_TMP") or "/tmp/sl_p5g"

APP_A = '''"""Demo module."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import thirdparty

from . import helper


class Worker:
    """A worker class."""

    @staticmethod
    def build():
        return Worker()

    def run(self):
        return 1


async def fetch():
    return 2


def outer():
    def inner():
        return 3
    return inner
'''

APP_B = APP_A.replace("def run(self):", "def execute(self):")


def phase_write():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    import python_ast_parser as P, source_fact_ingest as SFI
    import content_ingest_coordinator as CIC
    import blob_fetcher as BF
    import content_acquisition_policy as POL
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    ks = KnowledgeStore(os.path.join(TMP, "kb.db"))
    auth = POL.build_authorization_ref(
        authorization_kind=POL.AUTH_ORIGINAL_FIXTURE, repository_id=REPO,
        scope=["app.py"], source="project-original",
        verification_status=POL.VERIFIED)
    out = {}
    for label, commit, raw in (("A", COMMIT_A, APP_A.encode()),
                               ("B", COMMIT_B, APP_B.encode())):
        entries = [{"path": "app.py", "sha": BF.git_blob_oid(raw),
                    "size": len(raw), "type": "blob", "mode": "100644"}]
        snap = build_snapshot(repository_id=REPO, requested_repository="origin/demo",
            resolved_repository="origin/demo", requested_ref="main",
            commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{commit}"])
        sid = ingest_snapshot(ks, snap)["asset_id"]

        dec = POL.evaluate_all(repository_id=REPO, commit_sha=commit,
                               file_path="app.py", authorization=auth)
        if dec["PERSIST_DECISION"]["decision"] != POL.ALLOW:
            out[label] = {"blocked": True}; continue
        ing = CIC.ingest_captured_blob(
            ks, data_root=TMP, repository_id=REPO, commit_sha=commit,
            source_snapshot_id=sid, file_path="app.py",
            git_blob_oid=BF.git_blob_oid(raw), git_object_format="sha1",
            raw=raw, source_declared_size=len(raw),
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        o = P.parse_source(raw, repository_id=REPO, commit_sha=commit,
                           file_path="app.py", git_blob_oid=BF.git_blob_oid(raw),
                           content_asset_id=ing["content_asset_id"],
                           content_sha256=ing["content_sha256"],
                           provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        fr = SFI.ingest_source_facts(ks, observation=o,
                                     source_snapshot_id=sid)
        out[label] = {"content": ing["content_asset_id"],
                      "symbols": [s["qualified_name"] for s in o["observed_symbols"]],
                      "imports": len(o["observed_imports"]),
                      "written": len(fr["written"]),
                      "status": o["extraction_status"]}
    ks.close()
    print(json.dumps({"phase": "write", "ok": True, "summary": out},
                     ensure_ascii=False))


def phase_query():
    import source_knowledge_query as Q
    for label, commit in (("A", COMMIT_A), ("B", COMMIT_B)):
        q = Q.source_query(repository_id=REPO, commit_sha=commit,
                           file_path="app.py", data_root=TMP)
        names = sorted(s["subject"]["qualified_name"] for s in q["symbols"])
        print(json.dumps({"phase": "query", "commit": label,
                          "state": q["state"], "symbols": names,
                          "imports": q["counts"]["imports"],
                          "network": q["network_requests"]},
                         ensure_ascii=False))


def phase_card():
    import source_knowledge as SK
    r = SK.render_source_card(repository_id=REPO, commit_sha=COMMIT_A,
                              file_path="app.py", data_root=TMP)
    print(json.dumps({"phase": "card", **r}, ensure_ascii=False))


if __name__ == "__main__":
    {"write": phase_write, "query": phase_query, "card": phase_card}[sys.argv[1]]()
