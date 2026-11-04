#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 测试夹具：真实入库的快照资产（不联网）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"src"/"facts"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime")):
    if p not in sys.path: sys.path.insert(0, p)

from knowledge_store import KnowledgeStore
from source_snapshot import build_snapshot

README = {"path": "README", "type": "blob", "sha": "980a0d5f" + "0"*32,
          "size": 13, "mode": "100644", "mode_kind": "file", "depth": 0}
DOCS   = {"path": "docs", "type": "tree", "sha": "d"*40, "size": None,
          "mode": "040000", "mode_kind": "file", "depth": 0}
GUIDE  = {"path": "docs/guide.md", "type": "blob", "sha": "h"*40, "size": 7,
          "mode": "100644", "mode_kind": "file", "depth": 1}
LINK   = {"path": "link", "type": "blob", "sha": "e"*40, "size": 4,
          "mode": "120000", "mode_kind": "symlink", "depth": 0}
SUBM   = {"path": "sub", "type": "commit", "sha": "f"*40, "size": None,
          "mode": "160000", "mode_kind": "submodule", "depth": 0}
WEIRD  = {"path": "weird", "type": "unknown", "sha": "g"*40, "size": 3,
          "mode": "100644", "mode_kind": "file", "depth": 0}

FULL_ENTRIES = [README, DOCS, GUIDE, LINK, SUBM, WEIRD]


def make_snapshot_payload(*, repo_id="1296269", commit="a"*40, tree="b"*40,
                          completeness="COMPLETE", entries=None,
                          truncated=False, manifest_v1=False,
                          scope="full_tree_enumeration", collected="t"):
    ent = entries if entries is not None else FULL_ENTRIES
    snap = build_snapshot(
        repository_id=repo_id, requested_repository="o/r", resolved_repository="o/r",
        requested_ref="master", commit_sha=commit, root_tree_sha=tree,
        tree_query_ref=tree, completeness_status=completeness,
        tree_entries=ent, collected_at=collected, evidence_refs=["ev"],
        truncated_seen=truncated, retrieval_scope=scope,
        manifest_v1=manifest_v1)
    return snap


def ingest_snapshot_asset(store, **kw) -> dict:
    """把一个快照写入 Storage，返回 asset_id 等。"""
    from ingest_coordinator import ingest_snapshot
    snap = make_snapshot_payload(**kw)
    r = ingest_snapshot(store, snap)
    return {"result": r, "snapshot": snap, "asset_id": r.get("asset_id")}


def fresh_store(tmpdir):
    return KnowledgeStore(str(Path(tmpdir) / "kb.db"))
