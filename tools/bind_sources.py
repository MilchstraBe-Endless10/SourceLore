#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过正式存储接口建立经严格验证的 repo_bindings（B 层关系表）。

用法：
  python3 tools/bind_sources.py --data-root <root> \
      --github-id 1459544036 --local-id local:4034d62ed2cf \
      --commit 8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024 [--apply]

默认 dry-run：只验证并打印将要写入的绑定，不写库。
--apply 才真正调用 KnowledgeStore.bind_repo 写入（仅 INSERT repo_bindings）。
A 层资产指纹在写入前后校验，确保不被改动。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
for sub in ("storage", "trust"):
    p = str(SRC / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from knowledge_store import KnowledgeStore
import source_provenance as SP
import source_binding as SB


def a_layer_fingerprint(store):
    """A 层不可变资产指纹：按 asset_id+content_hash 排序哈希。"""
    rows = store.conn.execute(
        "SELECT asset_id, asset_type, content_hash FROM assets ORDER BY asset_id").fetchall()
    h = hashlib.sha256()
    for r in rows:
        h.update(("%s|%s|%s\n" % (r[0], r[1], r[2])).encode())
    return h.hexdigest(), len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--github-id", required=True)
    ap.add_argument("--local-id", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    db = Path(a.data_root) / "kb.db"
    if not db.is_file():
        print(json.dumps({"ok": False, "error": "KB_NOT_FOUND", "path": str(db)}))
        return 2
    store = KnowledgeStore(str(db))
    before, n_before = a_layer_fingerprint(store)

    v = SP.verify_source_binding(store, github_id=a.github_id,
                                 local_id=a.local_id, commit_sha=a.commit)
    if not v.get("ok"):
        print(json.dumps({"ok": False, "error": "SOURCE_VERIFICATION_FAILED",
                          "detail": v}, ensure_ascii=False, indent=2))
        store.close()
        return 3

    # subject_id 用内容锚点；repository_id 为本地补充源（非 GitHub 数字 ID）
    subject_id = SB.content_anchor(a.commit, str(v["root_tree_sha"]))
    evidence = ("source_verified=1;method=github_identity_record+blob_subset;"
                "commit=%s;root_tree=%s;github_asset=%s;local_asset=%s;"
                "resolved_repository=%s;github_id=%s" % (
                    a.commit, v["root_tree_sha"], v["github_asset_id"],
                    v["local_asset_id"], v["resolved_repository"], a.github_id))

    result = {"ok": True, "dry_run": not a.apply, "verification": v,
              "binding": {"subject_id": subject_id, "repository_id": a.local_id,
                          "evidence_ref": evidence}}
    if a.apply:
        # 关键：GitHub ID 侧也建立一条绑定，resolve_supplement 从 GitHub ID 出发查找
        r1 = store.bind_repo(subject_id=subject_id, repository_id=a.github_id,
                             evidence_ref=evidence)
        r2 = store.bind_repo(subject_id=subject_id, repository_id=a.local_id,
                             evidence_ref=evidence)
        after, n_after = a_layer_fingerprint(store)
        result["writes"] = {"github": r1, "local": r2}
        result["a_layer_unchanged"] = (before == after and n_before == n_after)
        result["a_layer_fingerprint"] = before
        if not result["a_layer_unchanged"]:
            result["ok"] = False
            result["error"] = "A_LAYER_MUTATED"
    store.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
