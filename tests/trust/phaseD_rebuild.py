#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 D：隔离副本完整重建 + 前后差异 + 三仓库真实查询验收。只读真实库，写隔离副本。"""
import sys, os, json, subprocess, sqlite3, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
for p in (str(SRC / "trust"), str(SRC / "storage"), str(SRC / "research"),
          str(SRC / "skill_interface"), str(SRC / "collector"), str(SRC / "evidence_claims")):
    if p not in sys.path:
        sys.path.insert(0, p)
from knowledge_store import KnowledgeStore
from index_store import rebuild_index
import tree_scope as TS
import pointer_rebuild as PR

REAL_DB = Path("/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data/kb.db")
WORK = Path(os.environ["SL_TEST_DB"])
CLI = Path.home() / ".agents/skills/sourcelore/scripts/sourcelore.py"
PY = sys.executable
DATA_ROOT = WORK.parent

REPOS = [
    ("24313173", "98e8ff1da1a89f93d1397a24d7413ed15421c139", "is-number"),
    ("38923193", "666df7c10035f7e26f27ec214fe5ae3173435f34", "is-plain-obj"),
    ("42283287", "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab", "preact"),
]


def snapshot(work_db):
    c = sqlite3.connect(f"file:{work_db}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    d = {}
    d["assets"] = c.execute("select count(*) from assets").fetchone()[0]
    d["assets_types"] = dict(c.execute("select asset_type,count(*) from assets group by asset_type").fetchall())
    d["index_rows"] = c.execute("select count(*) from index_rows").fetchone()[0]
    d["index_null_commit"] = c.execute("select count(*) from index_rows where commit_sha is null").fetchone()[0]
    d["current_view"] = c.execute("select count(*) from current_view").fetchone()[0]
    d["cv_by_repo"] = {r[0]: r[1] for r in c.execute("select repository_id,count(*) from current_view group by repository_id")}
    d["pollution_in_index"] = c.execute(
        "select count(*) from index_rows where asset_id in "
        "('SL-A-1724d24d10dc7395efc593017a96f2f9','SL-A-4d6b393c3909185f9eb4ecc55901a73b',"
        "'SL-A-452e014380664d84d0e472c145b6cc83','SL-A-161d1238f95705ed58e9d7804f0da2bc')").fetchone()[0]
    c.close()
    return d


def cli_query(repo, commit, typ):
    p = subprocess.run([PY, str(CLI), "--data-root", str(DATA_ROOT),
                        "query", repo, "--commit", commit, "--type", typ],
                       capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
        return p.returncode, d
    except Exception:
        return p.returncode, {"_raw": p.stdout[:200], "_err": p.stderr[:200]}


def count_findings(d):
    if not isinstance(d, dict): return None
    for k in ("findings", "supported_findings", "results"):
        if isinstance(d.get(k), list): return len(d[k])
    return None


print("=== 阶段D：隔离副本完整重建与前后差异 ===")
before = snapshot(WORK)
print("BEFORE", json.dumps(before, ensure_ascii=False, sort_keys=True))

s = KnowledgeStore(str(WORK), create=False)
r = rebuild_index(s)
print("REBUILD", json.dumps({k: r[k] for k in ("ok","source_assets","indexed","quarantined_count","a_b_unchanged")}, ensure_ascii=False))
for q in r.get("quarantined", []):
    print("  QUARANTINE", q["asset_id"], q["asset_type"], q["reasons"])

# B 层当前指针重建：补上两小仓库从未登记的合法 claim/verification 指针
pr = PR.rebuild_current_pointers(s)
print("POINTER_REBUILD", json.dumps({k: pr[k] for k in ("ok","added_count","repointed_count","kept_count","rejected_count")}, ensure_ascii=False))
for a in pr.get("added", []):
    print("  ADD_PTR", a["repository_id"], a["asset_type"], a["logical_identity"][:34])
s.close()

after = snapshot(WORK)
print("AFTER", json.dumps(after, ensure_ascii=False, sort_keys=True))
print("DIFF", json.dumps({k: {"before": before[k], "after": after[k]}
                          for k in before if before[k] != after[k]}, ensure_ascii=False, sort_keys=True))

# D5 覆盖度派生视图（只读）
print("\n=== D5 派生覆盖度校正（历史快照不改） ===")
c = sqlite3.connect(f"file:{WORK}?mode=ro", uri=True); c.row_factory = sqlite3.Row
for rid, commit, name in REPOS:
    sp = TS.snapshot_for_commit(type("S", (), {"conn": c})(), rid, commit)
    if sp is None:
        print(f"  {name}: NO SNAPSHOT")
        continue
    sc = TS.derive_tree_scope(sp)
    print(f"  {name}: original={sp.get('completeness_status')} deep={sp.get('deep_walk_used')} "
          f"-> derived={sc['scope']} complete={sc['complete']} reason={sc['reason']}")
c.close()

# 三仓库真实查询验收
print("\n=== 三仓库真实查询（隔离副本，--data-root） ===")
for rid, commit, name in REPOS:
    for typ in ("claims", "code", "relation"):
        rc, d = cli_query(rid, commit, typ)
        n = count_findings(d)
        extra = ""
        if isinstance(d, dict):
            extra = " ok=%s state=%s" % (d.get("ok"), d.get("state", d.get("status")))
            # 检测跨仓库污染：is-number 不得出现 isPlainObject 命题
            if name == "is-number" and typ == "claims":
                txt = json.dumps(d, ensure_ascii=False)
                extra += " has_isPlainObject=%s" % ("isPlainObject" in txt)
        print(f"  {name:13} {typ:9} rc={rc} findings={n}{extra}")
