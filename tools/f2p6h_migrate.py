#!/usr/bin/env python3
"""P6H 数据根统一迁移：多库 → 一个 SourceLore_Data。

★ 不做 SQLite 覆盖复制。逐资产搬运：
  - 按 (asset_type, logical_identity, repository_id, asset_version) 判重
  - 已存在 → 跳过（幂等）
  - 不合并不同 repository_id 的资产
  - Blob 按 content_sha256 内容寻址，天然去重
  - 只写目标库，不动源库
"""
import argparse, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in ("storage", "facts", "evidence_claims", "runtime"):
    sys.path.insert(0, str(ROOT / "src" / p))

TABLES = ("assets", "current_view", "index_rows", "repo_bindings", "operation_log")


def open_db(path):
    from knowledge_store import KnowledgeStore
    return KnowledgeStore(str(path), create=True)


def ensure_target(target):
    """目标不存在时，用源库结构建骨架（不拷数据）。"""
    target = Path(target); target.mkdir(parents=True, exist_ok=True)
    db = target / "kb.db"
    if db.exists():
        return db
    return db


def snapshot(ks, label):
    out = {"label": label}
    for t in ("assets", "index_rows", "current_view"):
        try:
            out[t] = ks.conn.execute(f"SELECT count(*) c FROM {t}").fetchone()["c"]
        except Exception:
            out[t] = None
    out["repos"] = sorted({r["repository_id"] for r in ks.conn.execute(
        "SELECT DISTINCT repository_id FROM assets").fetchall()})
    return out


def migrate(src_db, dst_db, *, apply=False):
    src = open_db(src_db); dst = open_db(dst_db)
    report = {"src": str(src_db), "dst": str(dst_db), "apply": apply,
              "before_src": snapshot(src, "src"),
              "before_dst": snapshot(dst, "dst"),
              "copied": {}, "skipped": {}, "blocked": []}

    # 已存在的资产标识
    have = set()
    for r in dst.conn.execute(
            "SELECT asset_type, logical_identity, repository_id, asset_version FROM assets").fetchall():
        have.add((r["asset_type"], r["logical_identity"], r["repository_id"], r["asset_version"]))

    rows = src.conn.execute("SELECT * FROM assets ORDER BY repository_id, asset_type, asset_version").fetchall()
    for r in rows:
        key = (r["asset_type"], r["logical_identity"], r["repository_id"], r["asset_version"])
        if key in have:
            report["skipped"][r["asset_type"]] = report["skipped"].get(r["asset_type"], 0) + 1
            continue
        if not r["payload_json"]:
            report["blocked"].append({"asset_id": r["asset_id"], "why": "payload 为空"})
            continue
        report["copied"][r["asset_type"]] = report["copied"].get(r["asset_type"], 0) + 1
        if apply:
            dst.conn.execute(
                """INSERT OR IGNORE INTO assets(asset_id, asset_type, logical_identity,
                   repository_id, subject_id, asset_version, content_hash, payload_json,
                   commit_sha, root_tree_sha, tree_query_ref, operation_id, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["asset_id"], r["asset_type"], r["logical_identity"],
                 r["repository_id"], r["subject_id"], r["asset_version"],
                 r["content_hash"], r["payload_json"], r["commit_sha"],
                 r["root_tree_sha"], r["tree_query_ref"], r["operation_id"],
                 r["created_at"]))
            # 索引行同步搬运（保持原 commit_sha，逐行照抄）
            src_ix = src.conn.execute(
                "SELECT * FROM index_rows WHERE asset_id=?", (r["asset_id"],)).fetchone()
            if src_ix:
                dst.conn.execute(
                    """INSERT OR IGNORE INTO index_rows(asset_id, asset_type, logical_identity,
                       repository_id, subject_id, commit_sha, asset_version)
                       VALUES(?,?,?,?,?,?,?)""",
                    (src_ix["asset_id"], src_ix["asset_type"], src_ix["logical_identity"],
                     src_ix["repository_id"], src_ix["subject_id"],
                     src_ix["commit_sha"], src_ix["asset_version"]))
    if apply:
        # current_view / repo_bindings / operation_log 也搬（同样只补不改）
        for t, cols in (
            ("current_view", "logical_identity, repository_id, asset_id, asset_version"),
            ("repo_bindings", "repository_id, binding_json"),
        ):
            try:
                for r in src.conn.execute(f"SELECT {cols} FROM {t}").fetchall():
                    vals = tuple(r[k] for k in r.keys())
                    dst.conn.execute(
                        f"INSERT OR IGNORE INTO {t}({cols}) VALUES({','.join('?'*len(vals))})", vals)
            except Exception as e:
                report["blocked"].append({"table": t, "why": str(e)[:120]})
        dst.conn.commit()

    report["after_dst"] = snapshot(dst, "dst")
    src.close(); dst.close()
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    ensure_target(a.dst)
    for s in a.src:
        rep = migrate(Path(s) / "kb.db", Path(a.dst) / "kb.db", apply=a.apply)
        print(json.dumps({k: rep[k] for k in ("src", "apply", "copied", "skipped", "blocked")},
                         ensure_ascii=False))
