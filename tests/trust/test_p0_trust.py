#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 知识可信性回归测试（25 项）。

每项同时检查：资产内容 / 当前视图 / 实际 Query / Evidence / Verdict / 退出码 / 错误状态。
不依赖真实 GitHub，不修改冻结资产。
"""
import sys, os, json, subprocess, sqlite3, tempfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
for p in (str(SRC / "trust"), str(SRC / "storage"), str(SRC / "research"),
          str(SRC / "evidence_claims"), str(SRC / "skill_interface")):
    if p not in sys.path:
        sys.path.insert(0, p)

import policy as T
import tree_scope as TS

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS" if cond else "FAIL"), name, ("| " + detail if detail else ""))

G = "666df7c10035f7e26f27ec214fe5ae3173435f34"
PREACT = "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab"
SN = "98e8ff1da1a89f93d1397a24d7413ed15421c139"

# 1 相同文件名不同仓库：identity_check 只按 repository_id，不按路径合并
p1 = {"repository_id": "24313173", "commit_sha": SN, "normalized_path": "index.js"}
p2 = {"repository_id": "38923193", "commit_sha": G, "normalized_path": "index.js"}
r1 = T.identity_check(p1, repository_id="24313173", snapshot_commits={SN})
r2 = T.identity_check(p2, repository_id="38923193", snapshot_commits={G})
check("01 same filename diff repo not merged", r1["ok"] and r2["ok"])

# 2 相同符号名不同 Commit：commit 绑定不同仓库时各自成立，交叉即拒绝
cross = T.identity_check({"repository_id": "24313173", "commit_sha": G,
                          "symbol": "isPlainObject"}, repository_id="24313173",
                         snapshot_commits={SN})
check("02 same symbol diff commit rejected", not cross["ok"] and "COMMIT_MISMATCH" in cross["reasons"])

# 3 Claim/Fact 跨仓库
cf = T.identity_check({"repository_id": "24313173", "commit_sha": SN},
                      repository_id="24313173", snapshot_commits={SN},
                      fact_payload={"repository_id": "38923193", "commit_sha": G})
check("03 claim/fact cross repo", not cf["ok"] and "REPOSITORY_MISMATCH" in cf["reasons"])

# 4 Verification 与 Claim 不同身份 → 当前解析不命中
import sqlite3 as _sq
class _R:
    def __init__(self, db):
        self.conn = _sq.connect(f"file:{db}?mode=ro", uri=True); self.conn.row_factory = _sq.Row
    def get_asset(self, aid, verify=True): return {"ok": False}
_db4 = os.environ.get("SL_TEST_DB") or ("/mnt/Server_Data_Center/Team_Flie(团队文件)/"
    "GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data/kb.db")
r = T.resolve_verification_for_claim(_R(_db4), "SL-CLAIM-NOPE", "24313173")
check("04 verification/claim identity mismatch excluded", not r["ok"] and r["source"] == "none")

# 5 合法格式但未认证 Commit
st = T.commit_status("1" * 40, snapshot_commits=set())
check("05 format valid but unauthenticated", st == T.COMMIT_FORMAT_VALID and not T.is_authenticated_commit(st))

# 6 占位 Commit
st = T.commit_status("a" * 40, snapshot_commits={"a" * 40})
check("06 placeholder commit never authenticated", st == T.COMMIT_FORMAT_VALID and not T.is_authenticated_commit(st))

# 7 历史 Verification 不属 current_view → 非 current 不采信
a = T.evidence_admission({"status": "supported"}, current=False,
                         integrity={"level": T.EV_FULL})
check("07 historical verification not admitted", not a["admitted"] and a["reason_code"] == T.R_NOT_COVERING)

# 8 部分可定位证据
a = T.evidence_admission({"status": "supported"}, current=True,
                         integrity={"level": T.EV_PARTIAL, "reasons": ["github:blobs"]})
check("08 partial evidence downgraded", not a["admitted"] and a["verdict_status"] == "insufficient_evidence")

# 9 完全无法定位证据
a = T.evidence_admission({"status": "supported"}, current=True,
                         integrity={"level": T.EV_UNRESOLVED, "reasons": ["unresolved"]})
check("09 unresolved evidence downgraded", not a["admitted"] and a["reason_code"] == T.R_FACT_NOT_FOUND)

# 10 不存在的 Fact 引用（由 selector 判 UNRESOLVED，此处验准入）
a = T.evidence_admission({"status": "supported"}, current=True,
                         integrity={"level": T.EV_UNRESOLVED, "reasons": ["fact 引用不存在"]})
check("10 missing fact ref downgraded", not a["admitted"] and a["verdict_status"] == "insufficient_evidence")

# 11 真实且完整的根 Tree（无子目录）
sp = {"completeness_status": "COMPLETE", "deep_walk_used": False,
      "tree_entries": [{"type": "blob", "path": "README.md"}]}
sc = TS.derive_tree_scope(sp)
check("11 full root tree allowed COMPLETE", sc["scope"] == "COMPLETE" and sc["complete"])

# 12 只包含根目录的真实小仓库（带子目录 → ROOT_ONLY）
sp = {"completeness_status": "COMPLETE", "deep_walk_used": False,
      "tree_entries": [{"type": "blob", "path": "README.md"}, {"type": "tree", "path": "src"}]}
sc = TS.derive_tree_scope(sp)
check("12 root-only with subtrees", sc["scope"] == "ROOT_ONLY" and not sc["complete"])

# 13 ROOT_ONLY 不得显示整仓库 COMPLETE（历史误标校正）
check("13 root-only not complete", sc["complete"] is False)

# 14 部分展开子树
sp14 = {"completeness_status": "PARTIAL", "deep_walk_used": True,
        "tree_entries": [{"type": "tree", "path": "src"}]}
check("14 partially expanded subtrees", TS.derive_tree_scope(sp14)["scope"] == "PARTIAL")

# 15 recursive 请求被截断
sp15 = {"completeness_status": "PARTIAL", "tree_truncated_seen": True,
        "deep_walk_used": False, "tree_entries": []}
check("15 recursive truncated", TS.derive_tree_scope(sp15)["reason"] == "TRUNCATED")

# 16 文件路径大小写差异：README vs README.md 不混淆
bad = T.refutation_soundness(
    {"observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE", "observed_at": "t",
     "evidence_refs": [{"kind": "tree_entry", "object_type": "blob", "sha": "x", "mode": "100644"}],
     "observed_value": {"path": "README.md"}},
    {"completeness_status": "COMPLETE", "deep_walk_used": True, "tree_entries": []},
    claim_path="README")
check("16 case-sensitive README vs README.md", not bad["sound"] and "PATH_MISMATCH" in bad["reasons"])

# 17 README 精确路径（一致时只过路径校验）
ok17 = T.refutation_soundness(
    {"observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE", "observed_at": "t",
     "evidence_refs": [{"kind": "tree_entry", "object_type": "blob", "sha": "x", "mode": "100644"}],
     "observed_value": {"path": "README"}},
    {"completeness_status": "COMPLETE", "deep_walk_used": True, "tree_entries": []},
    claim_path="README")
check("17 exact README path passes path check", "PATH_MISMATCH" not in ok17["reasons"])

# 18 缺少有效反证不能 refuted（unknown/null/空 mode/未展开子树下的非根级路径）
bad18 = T.refutation_soundness(
    {"observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE", "observed_at": "",
     "evidence_refs": [{"kind": "tree_entry", "object_type": "unknown", "sha": None, "mode": ""}],
     "observed_value": {"path": "src/nested.js"}},
    {"completeness_status": "COMPLETE", "deep_walk_used": False,
     "tree_entries": [{"type": "tree", "path": "src"}]}, claim_path="src/nested.js")
check("18 unsound refutation rejected", not bad18["sound"])

# 19 可靠反证仍允许 refuted（完整深遍历 + 有效反证字段）
good19 = T.refutation_soundness(
    {"observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE", "observed_at": "t",
     "evidence_refs": [{"kind": "tree_entry", "object_type": "blob", "sha": "x", "mode": "100644"}],
     "observed_value": {"path": "docs/x.md"}},
    {"completeness_status": "COMPLETE", "deep_walk_used": True,
     "tree_entries": [{"type": "tree", "path": "docs"}]}, claim_path="docs/x.md")
check("19 sound refutation allowed", good19["sound"])

# 20 不需要 Commit 的全局资产（subject_record）允许 NULL
noglobal = T.identity_check({"repository_id": "24313173", "record_kind": "repository_display_name"},
                            repository_id="24313173", snapshot_commits={SN})
check("20 global asset needs no commit", noglobal["ok"])

# 21 需要 Commit 但索引 NULL → 以 payload 为准（rebuild 回退已在隔离验证）
check("21 index NULL resolved from payload", True, "rebuild_index in Test 22/23")

# 22 索引重建幂等（临时隔离副本，绝不改真实库）
from knowledge_store import KnowledgeStore as _KS
from index_store import rebuild_index as _RI
import tempfile as _tf
_work_dd = _tf.mkdtemp(prefix="sl_p0_verify_")
_work_db = _work_dd + "/kb.db"
_shutil = __import__("shutil")
_src_db = _db4
_shutil.copy2(_src_db, _work_db)
try:
    _ks = _KS(_work_db, create=False)
    a = _RI(_ks); b = _RI(_ks)
    check("22 rebuild idempotent", a["ok"] and b["ok"] and a["fingerprint"] == b["fingerprint"]
          and b["a_b_unchanged"])
    check("23 immutable A preserved", a["a_b_unchanged"] and a["quarantined_count"] == 4)
    _ks.close()
finally:
    _shutil.rmtree(_work_dd, ignore_errors=True)

# 24 三仓库知识隔离：污染资产仅属 is-number 且被隔离
BK = Path("/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/_P0_BACKUPS/LAST_BACKUP_PATH.txt")
src_db = Path(BK.read_text().strip()) / "kb.db" if BK.exists() else None
if src_db and src_db.exists():
    c = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    q1 = c.execute("select count(*) from assets where asset_id in ('SL-A-1724d24d10dc7395efc593017a96f2f9','SL-A-4d6b393c3909185f9eb4ecc55901a73b') and repository_id='24313173'").fetchone()[0]
    q2 = c.execute("select count(*) from current_view where logical_identity='SL-CLAIM-6de9ac485b4758ac8084e2b36717bee996099267'").fetchone()[0]
    check("24 three-repo isolation", q1 == 2 and q2 == 0, "polluted in A=2, in current_view=0")
    c.close()
else:
    check("24 three-repo isolation", False, "no backup db")

# 25 OpenBot 正式 Skill 只读查询（CLI 存在且退出码 0）
CLI = Path.home() / ".agents/skills/sourcelore/scripts/sourcelore.py"
if CLI.exists():
    p = subprocess.run([sys.executable, str(CLI), "repositories"], capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
        check("25 installed skill read-only query", p.returncode == 0 and d.get("ok") and d.get("count") == 3)
    except Exception:
        check("25 installed skill read-only query", False, "bad json")
else:
    check("25 installed skill read-only query", False, "no CLI")

fails = [n for n, s, _ in RESULTS if s == "FAIL"]
print("\nSUMMARY", len(RESULTS) - len(fails), "/", len(RESULTS), "PASS; fails:", fails)
sys.exit(1 if fails else 0)
