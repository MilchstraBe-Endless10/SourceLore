#!/usr/bin/env python3
"""D-67 历史索引补全：只 UPDATE index_rows（C 层，可重建），不动 assets。

安全前提：
  1. 只补 commit_sha IS NULL 的 claim_verification 行
  2. commit 从该 verification 的 claim 取（claim 索引行有 commit 且同仓库）
  3. claim_id 必须唯一确认来源，歧义则不补、计入 blocked
  4. 幂等：已补的行不再动
"""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in ("storage", "facts", "evidence_claims", "content_persistence"):
    sys.path.insert(0, str(ROOT / "src" / p))

def run(db_path, *, apply=False):
    from knowledge_store import KnowledgeStore
    ks = KnowledgeStore(db_path, create=False)
    rows = ks.conn.execute(
        "SELECT asset_id, logical_identity, repository_id FROM index_rows "
        "WHERE asset_type='claim_verification' AND commit_sha IS NULL").fetchall()
    out = {"total_null": len(rows), "filled": [], "blocked": [], "applied": apply}
    for r in rows:
        ver = ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_id=?", (r["asset_id"],)).fetchone()
        try:
            d = json.loads(ver["payload_json"])
        except Exception:
            out["blocked"].append({"verification_id": r["logical_identity"],
                                   "why": "payload 不可解析"}); continue
        cid = d.get("claim_id")
        if not cid:
            out["blocked"].append({"verification_id": r["logical_identity"],
                                   "why": "payload 无 claim_id"}); continue
        cands = ks.conn.execute(
            "SELECT commit_sha FROM index_rows WHERE asset_type='claim_candidate' "
            "AND logical_identity=? AND repository_id=?", (cid, r["repository_id"])).fetchall()
        commits = sorted({c["commit_sha"] for c in cands if c["commit_sha"]})
        if not commits:
            out["blocked"].append({"verification_id": r["logical_identity"],
                                   "claim_id": cid, "why": "claim 索引无 commit"}); continue
        if len(commits) > 1:
            out["blocked"].append({"verification_id": r["logical_identity"],
                                   "claim_id": cid, "why": "claim 跨多个 commit，歧义"}); continue
        out["filled"].append({"verification_id": r["logical_identity"],
                              "claim_id": cid, "commit_sha": commits[0]})
        if apply:
            ks.conn.execute("UPDATE index_rows SET commit_sha=? WHERE asset_id=?",
                            (commits[0], r["asset_id"]))
    if apply and out["filled"]:
        ks.conn.commit()
    ks.close()
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    res = run(a.db, apply=a.apply)
    print(json.dumps({k: (v if k != "filled" else v[:3]) for k, v in res.items()},
                     ensure_ascii=False, indent=1)[:600])
    print(f"可补 {len(res['filled'])} 条，阻断 {len(res['blocked'])} 条")
