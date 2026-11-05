#!/usr/bin/env python3
"""三进程 E2E：写入 → 查询 → 卡片。★ 只用原创授权夹具。"""
import sys, os, json, tempfile, shutil
from pathlib import Path
R = Path(__file__).resolve().parents[1]
for p in ("runtime","storage","collector","facts","evidence_claims","lifecycle",
          "views","renderer","research","content","content_persistence",
          "skill_interface"):
    sys.path.insert(0, str(R/"src"/p))

REPO = "990001"; COMMIT_A = "a"*40; COMMIT_B = "b"*40
README = b"""# Demo Project

Intro paragraph.

## Installation

```bash
npm install demo
```

## Usage

Read the docs.
"""
README_B = b"""# Demo Project

Intro paragraph.

## Setup

Different section.
"""
PKG = json.dumps({"name":"demo","version":"1.0.0",
  "dependencies":{"lodash":"^4.17.0"},
  "devDependencies":{"vitest":"^1.0.0"}}, indent=2).encode()
TMP = os.environ.get("SL_P5F_TMP") or "/tmp/sl_p5f"


def oid(raw):
    import blob_fetcher as BF
    return BF.git_blob_oid(raw)


def phase_write():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    import content_acquisition_policy as POL
    import content_ingest_coordinator as CIC
    import content_extractor as EX, content_models as CM
    import content_fact_ingest as FI
    import content_claim_adapter as CA
    import content_claim_ingest as CI
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    ks = KnowledgeStore(os.path.join(TMP, "kb.db"))
    auth = POL.build_authorization_ref(
        authorization_kind=POL.AUTH_ORIGINAL_FIXTURE, repository_id=REPO,
        scope=["README.md","package.json"], source="project-original",
        verification_status=POL.VERIFIED)
    out = {}
    batches = [
        ("A", COMMIT_A, [("README.md", README), ("package.json", PKG)]),
        ("B", COMMIT_B, [("README.md", README_B), ("package.json", PKG)]),
    ]
    for label, commit, files in batches:
        entries = [{"path": p, "sha": oid(r), "size": len(r), "type": "blob",
                    "mode": "100644"} for p, r in files]
        snap = build_snapshot(repository_id=REPO, requested_repository="origin/demo",
            resolved_repository="origin/demo", requested_ref="main",
            commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{commit}"])
        ing = ingest_snapshot(ks, snap)
        sid = ing["asset_id"]
        li = ks.get_asset(sid, verify=True)["asset"]["logical_identity"]

        content = {}
        facts_by_path = {}
        extractions = {}
        for path, raw in files:
            dec = POL.evaluate_all(repository_id=REPO, commit_sha=commit,
                                   file_path=path, authorization=auth)
            r = CIC.ingest_captured_blob(ks, data_root=TMP, repository_id=REPO,
                commit_sha=commit, source_snapshot_id=sid, file_path=path,
                git_blob_oid=oid(raw), git_object_format="sha1", raw=raw,
                source_declared_size=len(raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            content[path] = r
            parser_id = EX.pick_parser(path)[1]
            ex = EX.extract_one(repository_id=REPO, commit_sha=commit,
                file_path=path, git_blob_oid=oid(raw),
                content_asset_id=r["content_asset_id"], data=raw,
                source_snapshot_id=sid,
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            extractions[path] = ex
            fi = FI.ingest_content_facts(ks, repository_id=REPO,
                commit_sha=commit, snapshot_asset_id=sid,
                snapshot_logical_identity=li, extraction_result=ex,
                content_asset_id=r["content_asset_id"],
                content_sha256=r["content_sha256"], parser_id=parser_id,
                parser_version="1.0.0", file_path=path,
                git_blob_oid=oid(raw), completeness_status="COMPLETE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            # ★ 幂等：第二次跑时 written 为空，fact_id 在 reused 里
            facts_by_path[path] = ([w["fact_id"] for w in fi["written"]]
                                   + [w["fact_id"] for w in fi["reused"]])

        # 命题 → 裁决
        verdicts = []
        readme_facts = (extractions.get("README.md") or {}).get("facts", [])
        for f in readme_facts:
            subj = f.get("subject") or {}
            if f["rule_id"] == "README_HEADING_EXISTS":
                c, b = CA.build_content_claim(
                    claim_type="readme_heading_exists", repository_id=REPO,
                    commit_sha=commit, file_path="README.md",
                    subject={"level": subj.get("level"),
                             "title": subj.get("title")})
            else:
                continue
            # ★ 从 Storage 读回该 Commit 的全部 README 事实（不依赖刚写入的内存列表）
            payloads = []
            for r2 in ks.conn.execute(
                    "SELECT asset_id FROM index_rows "
                    "WHERE asset_type='extracted_fact' AND repository_id=?",
                    (REPO,)).fetchall():
                got = ks.get_asset(r2["asset_id"], verify=True)
                if not got.get("ok"):
                    continue
                pl2 = (got["asset"] or {}).get("payload") or {}
                np2 = pl2.get("normalized_parameters") or {}
                if pl2.get("commit_sha") != commit:
                    continue
                if np2.get("file_path") != "README.md":
                    continue
                payloads.append(pl2)
            v = CA.verify_content_claim(claim=c, facts=payloads,
                content_available=True, completeness_status="COMPLETE",
                subject_binding=b)
            ing = CI.ingest_content_claim(ks, claim=c, verdict=v,
                facts_payload=payloads, repository_id=REPO,
                evidence_refs=[f"content:{r['content_asset_id']}"])
            verdicts.append({"title": subj.get("title"), "level": subj.get("level"),
                             "status": v["status"],
                             "claim_id": ing.get("claim_id"),
                             "verification_id": ing.get("verification_id"),
                             "ingest_ok": ing.get("ok"),
                             "ingest_error": ing.get("error")})
        out[label] = {"snapshot": sid, "facts": facts_by_path,
                      "verdicts": verdicts,
                      "content_ids": {p: r["content_asset_id"] for p, r in content.items()}}
    ks.close()
    print(json.dumps({"phase":"write","ok":True,"summary":out}, ensure_ascii=False))


def phase_query():
    import content_knowledge_query as KQ
    q = KQ.content_query(repository_id=REPO, commit_sha=COMMIT_A,
                         file_path="README.md", data_root=TMP)
    print(json.dumps({"phase":"query","state":q["state"],
        "facts":len(q["facts"]),
        "network_requests":q["network_requests"],
        "content_availability":q["content_availability"],
        "evidence":[{"fact_id":f["fact_id"],"label":f["rule_id"],
                     "L":[f["start_line"],f["end_line"]],
                     "blob":f["git_blob_oid"]} for f in q["facts"][:3]]},
        ensure_ascii=False))


def phase_card():
    import content_card as CC
    r = CC.render_content_card(repository_id=REPO, commit_sha=COMMIT_A,
                               file_path="README.md", data_root=TMP)
    print(json.dumps({"phase":"card","card_type":r["card_type"],
        "html_path":r["html_path"],"html_bytes":r["html_bytes"],
        "facts":r["facts_count"],"state":r["state"],
        "network":r["network_requests"]}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1]
    {"write": phase_write, "query": phase_query, "card": phase_card}[mode]()
