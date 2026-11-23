import sys
sys.path.insert(0, "src/trust")
import policy as P

snaps = {"666df7c10035f7e26f27ec214fe5ae3173435f34"}
print("placeholder:", P.commit_status("a" * 40, snapshot_commits=snaps))
print("bad format:", P.commit_status("xyz", snapshot_commits=snaps))
print("bound:", P.commit_status("666df7c10035f7e26f27ec214fe5ae3173435f34", snapshot_commits=snaps))
print("format only:", P.commit_status("1" * 40, snapshot_commits=snaps))
print("conflict:", P.commit_status("1" * 40, snapshot_commits={"1" * 40},
      snapshot_payloads=[{"root_tree_sha": "a"}, {"root_tree_sha": "b"}]))
print("auth placeholder:", P.is_authenticated_commit(P.commit_status("a" * 40, snapshot_commits=snaps)))
print("auth bound:", P.is_authenticated_commit(P.commit_status("1" * 40, snapshot_commits={"1" * 40})))
print("crossrepo:", P.identity_check(
    {"repository_id": "38923193", "commit_sha": "666df7c10035f7e26f27ec214fe5ae3173435f34"},
    repository_id="24313173", snapshot_commits=snaps, require_authenticated_commit=True))
print("admit partial:", P.evidence_admission({"status": "supported"}, current=True,
      integrity={"level": "PARTIALLY_LOCATABLE", "reasons": ["github:blobs"]}))
print("admit hist:", P.evidence_admission({"status": "supported"}, current=False,
      integrity={"level": "FULLY_LOCATABLE"}))
print("refute unsound:", P.refutation_soundness(
    {"observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE", "observed_at": "",
     "evidence_refs": [{"kind": "tree_entry", "object_type": "unknown", "sha": None, "mode": ""}]},
    {"completeness_status": "COMPLETE", "tree_entries": [{"type": "tree"}]}, claim_path="README"))
