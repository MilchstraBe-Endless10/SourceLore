#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 层索引重建工具。★ 默认只读。

规则：
- 只重建 C 层（index_rows / asset_fts），不动 A 层资产、B 层指针、
  Runtime、Claim、Verification。
- commit_sha 投影**按 asset_type 分别定义**，冲突时返回歧义状态而非任选。
- --apply 只允许作用于明确指定的测试库（拒绝默认路径）。

用法：
  --check    报告现状（只读）
  --dry-run  报计划，不写
  --verify   校验重建后一致性
  --apply    真写（需显式 --target，且不得指向默认库）
"""

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "storage"))
sys.path.insert(0, str(ROOT / "src" / "facts"))

AMBI = "<<AMBIGUOUS>>"

# ★ 按资产类型定义 commit_sha 投影。None 表示该类型不投影。
COMMIT_PROJECTION = {
    "repository_snapshot": ("commit_sha",),
    "extracted_fact": ("commit_sha",),
    "claim_candidate": ("commit_sha",),
    # ★ 验证资产自身不带 commit；它的 commit 来自所绑定的 Claim。
    #    不在这里硬猜，留空并标记 NEEDS_JOIN。
    "claim_verification": (),
}


def canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def resolve_commit(asset_type, payload, draft_source=None):
    """返回 (commit_sha_or_None, status)。status ∈ OK/NEEDS_JOIN/AMBIGUOUS/NONE。"""
    if draft_source:
        return draft_source, "OK"
    fields = COMMIT_PROJECTION.get(asset_type, ())
    if not fields:
        return None, "NEEDS_JOIN"
    found = {}
    pl = payload or {}
    for f in fields:
        v = pl.get(f)
        if isinstance(v, str) and v:
            found[f] = v
    if not found:
        # 次级来源：payload.source_snapshot
        snap = pl.get("source_snapshot")
        if isinstance(snap, dict):
            for f in ("commit_sha", "baseline_commit_sha", "observed_commit_sha"):
                v = snap.get(f)
                if isinstance(v, str) and v:
                    found[f"source_snapshot.{f}"] = v
    if not found:
        return None, "NONE"
    vals = set(found.values())
    if len(vals) > 1:
        return AMBI, f"AMBIGUOUS:{sorted(found.items())}"
    return next(iter(vals)), "OK"


def _assets(conn):
    return conn.execute(
        "SELECT asset_id, asset_type, payload_json FROM assets ORDER BY asset_id"
    ).fetchall()


def check(db: Path) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT asset_id, asset_type, commit_sha FROM index_rows")]
        null_rows = [r for r in rows if not r["commit_sha"]]
        types = {}
        for r in rows:
            t = types.setdefault(r["asset_type"],
                                 {"total": 0, "null_commit": 0})
            t["total"] += 1
            if not r["commit_sha"]:
                t["null_commit"] += 1
        counts = {k: c.execute(f'SELECT count(*) FROM "{k}"').fetchone()[0]
                  for k in ("assets", "index_rows", "current_pointers",
                            "operation_log") if _has_table(c, k)}
        return {"db": str(db), "row_count": len(rows),
                "null_commit_count": len(null_rows),
                "by_type": types, "table_counts": counts}
    finally:
        c.close()


def _has_table(c, name):
    return bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone())


def fingerprint(db: Path) -> dict:
    """★ A/B/Runtime 指纹：重建前后必须完全一致。"""
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = {}
        for t in ("assets", "current_pointers", "operation_log",
                  "runtime_checkpoints"):
            if not _has_table(c, t):
                continue
            rows = c.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall()
            out[t] = {"rows": len(rows),
                      "hash": __import__("hashlib").sha256(
                          repr(rows).encode()).hexdigest()[:32]}
        return out
    finally:
        c.close()


def plan(db: Path) -> dict:
    """dry-run：算出每行应得的 commit_sha。"""
    from knowledge_store import KnowledgeStore
    ks = KnowledgeStore(str(db), create=False)
    try:
        items, ambiguous, needs_join = [], [], []
        for r in _assets(ks.conn):
            try:
                pl = json.loads(r["payload_json"]) if isinstance(r["payload_json"], str) \
                    else (r["payload_json"] or {})
            except Exception:
                pl = {}
            cs, st = resolve_commit(r["asset_type"], pl)
            item = {"asset_id": r["asset_id"], "asset_type": r["asset_type"],
                    "commit_sha": cs, "status": st}
            if st.startswith("AMBIGUOUS"):
                ambiguous.append(item)
            elif st == "NEEDS_JOIN":
                needs_join.append(item)
            items.append(item)
        return {"items": items, "ambiguous": ambiguous,
                "needs_join": needs_join,
                "would_update": sum(1 for i in items if i["commit_sha"])}
    finally:
        ks.close()


def apply(db: Path, *, target: str) -> dict:
    """真写 C 层。★ 只允许作用于显式 --target 指定的非默认库。"""
    resolved = Path(db).resolve()
    if str(resolved) != str(Path(target).resolve()):
        raise RuntimeError(f"目标库不匹配：{resolved} != {target}")
    # ★ 拒绝默认生产库（~/.sourcelore/kb.db），必须用隔离副本
    prod = (Path.home() / ".sourcelore" / "kb.db").resolve()
    if resolved == prod or resolved.parent == prod.parent:
        raise RuntimeError(
            "拒绝写入默认生产库 ~/.sourcelore/kb.db；"
            "请先复制到隔离环境并用 --db 指向副本")

    pl = plan(db)
    c = sqlite3.connect(str(db))
    try:
        c.execute("BEGIN")
        updated = 0
        for it in pl["items"]:
            if it["status"] == "OK" and it["commit_sha"]:
                c.execute("UPDATE index_rows SET commit_sha=? WHERE asset_id=?",
                          (it["commit_sha"], it["asset_id"]))
                updated += 1
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    finally:
        c.close()
    return {"updated": updated,
            "ambiguous_left": len(pl["ambiguous"]),
            "needs_join_left": len(pl["needs_join"])}


def verify(db: Path) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT asset_id, asset_type, commit_sha FROM index_rows")]
        nulls = [r for r in rows if not r["commit_sha"]]
        missing = [r for r in rows if not c.execute(
            "SELECT 1 FROM assets WHERE asset_id=?", (r["asset_id"],)).fetchone()]
        return {"ok": not missing,
                "null_commit_count": len(nulls),
                "null_by_type": {t: sum(1 for r in nulls if r["asset_type"] == t)
                                 for t in {r["asset_type"] for r in nulls}},
                "dangling_index_rows": len(missing)}
    finally:
        c.close()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sourcelore_rebuild_index")
    ap.add_argument("--db", required=True, help="目标库路径")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--target", default=None, help="--apply 时必须显式确认")
    a = ap.parse_args(argv)
    db = Path(a.db)
    if not db.exists():
        print(json.dumps({"ok": False, "error": "DB_NOT_FOUND"}, ensure_ascii=False))
        return 3

    if a.apply:
        if not a.target:
            print(json.dumps({"ok": False, "error": "TARGET_REQUIRED"}, ensure_ascii=False))
            return 2
        try:
            res = apply(db, target=a.target)
        except RuntimeError as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "applied": res}, ensure_ascii=False, indent=2))
        return 0

    if a.dry_run:
        print(json.dumps({"ok": True, "dry_run": plan(db)}, ensure_ascii=False, indent=2))
        return 0
    if a.verify:
        v = verify(db)
        print(json.dumps({"ok": v["ok"], "verify": v}, ensure_ascii=False, indent=2))
        return 0 if v["ok"] else 1
    print(json.dumps({"ok": True, "check": check(db)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
