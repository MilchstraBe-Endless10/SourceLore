#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4A 端到端预览：从真实 KnowledgeView 生成可打开的 HTML 与 JSON。

数据级别：基线 HISTORICAL_REAL_DATA（P1C 记录）；目标 Commit SYNTHETIC_FIXTURE。
**未联网、未使用真实授权。**
"""
import json, sys, tempfile, shutil, datetime, hashlib, importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/collector", "src/storage", "src/runtime", "src/facts",
          "src/evidence_claims", "src/lifecycle", "src/views", "src/renderer"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from knowledge_store import KnowledgeStore
extractor = importlib.import_module("extractor")
FI = importlib.import_module("ingest")
import ec_models as EM, verifier as V, verification_store as VS
import lc_models as L, ref_observer as RO, freshness_evaluator as FE
import lifecycle_store as LS
import revalidation_queue as RQ, revalidation_authorization as AUTH
import revalidation_executor as EX, collector_adapter as CA
import knowledge_view_assembler as KVA, view_integrity as VI
import card_models as CM
import card_renderer as CRD
import report_renderer as RPT
import pre_publish_check as PPC

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUTDIR = ROOT/"docs"/"preview"/"f2p4a"
SUMMARY = ROOT/"docs"/"implementation"/"F2_P4A_E2E_PREVIEW.json"

rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

A = rec["commit_sha"]
B = "b" * 40
TREE_A = "t" * 40
TREE_B = "1" * 40
NOW = "2026-11-05T00:00:00+08:00"
STAMP = datetime.datetime.now(TZ).isoformat(timespec="seconds")


def _plan(c, commit):
    p = {"candidate_id": c["candidate_id"], "repository_id": rec["repository_id"],
         "requested_ref": rec["requested_ref"], "target_commit_sha": commit,
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": c["target_claim_parameters"],
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p


def _auth(c, plan, commit):
    return AUTH.make_test_authorization(
        candidate_id=c["candidate_id"], repository_id=rec["repository_id"],
        requested_ref=rec["requested_ref"], target_commit_sha=commit,
        plan_digest=plan["plan_digest"],
        authorized_scope="full_tree_enumeration",
        issued_at="2026-11-04T00:00:00+08:00",
        expires_at="2027-01-01T00:00:00+08:00")


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:32]


def build_scenario(*, label, target_commit, entries, truncated, target_path):
    """返回 (views, blocked_diagnostics)。"""
    tmp = Path(tempfile.mkdtemp(prefix=f"p4a_{label}_"))
    views = []
    blocked = []
    try:
        with KnowledgeStore(str(tmp/"kb.db")) as ks:
            ents = [{"path": "README", "type": "blob",
                     "sha": rec["blob"]["blob_sha"], "size": rec["blob"]["size"],
                     "mode": "100644", "mode_kind": "file", "depth": 0}]
            snap_a = build_snapshot(
                repository_id=rec["repository_id"],
                requested_repository=rec["target"],
                resolved_repository=rec["resolved_repository"],
                requested_ref=rec["requested_ref"], commit_sha=A,
                root_tree_sha=rec["root_tree_sha"],
                tree_query_ref=rec["tree_query_ref"],
                completeness_status="COMPLETE", tree_entries=ents,
                collected_at=rec["attempted_at"],
                evidence_refs=[f"github:repos/{rec['target']}@{A}"])
            r1 = ingest_snapshot(ks, snap_a); aid = r1["asset_id"]
            f = extractor.extract_file_path_observation(
                ks, snapshot_asset_id=aid, target_path=target_path)
            FI.ingest_fact(ks, f)
            claim_a = EM.build_path_claim(
                repository_id=rec["repository_id"], commit_sha=A,
                target_path=target_path, expected_exists=True,
                claim_origin="human_specified")
            v_a = V.verify_path_claim(ks, claim_a, [f.fact_id])
            VS.ingest_claim(ks, claim_a)
            VS.ingest_verification(ks, v_a, repository_id=rec["repository_id"])

            watch = L.build_watch(repository_id=rec["repository_id"],
                                  requested_ref=rec["requested_ref"],
                                  ref_kind=L.REF_KIND_BRANCH,
                                  retrieval_scope="full_tree_enumeration",
                                  baseline_commit_sha=A, claim_id=claim_a.claim_id)
            LS.ingest_watch(ks, watch)
            synth = dict(rec); synth["commit_sha"] = target_commit
            obs = RO.observe_ref_from_record(
                record=synth, repository_id=rec["repository_id"],
                requested_ref=rec["requested_ref"])
            a_b = FE.assess(watch=watch, observation=obs,
                            source_evidence_conflict=L.CONFLICT_NONE)
            LS.ingest_assessment(ks, a_b)
            prop = RQ.propose_candidate(ks, assessment_id=a_b.assessment_id)
            if not prop.get("ok"):
                return [], [{"error_code": prop.get("reason_code"),
                             "detail": "候选未生成"}]

            c = RQ.read_candidate(ks, candidate_id=prop["candidate_id"],
                                  repository_id=rec["repository_id"])["payload"]
            plan = _plan(c, target_commit)
            auth = _auth(c, plan, target_commit)
            ad = CA.FakeGhAdapter({target_commit: TREE_B},
                {TREE_B: {"entries": entries, "truncated": truncated}})
            res = EX.execute_revalidation(
                ks, candidate_id=c["candidate_id"],
                repository_id=rec["repository_id"], authorization=auth,
                plan=plan, adapter=ad, now=NOW)

            va = KVA.assemble_from_verification(
                ks, verification_id=v_a.verification_id,
                repository_id=rec["repository_id"])
            if va.get("ok"):
                views.append(va["view"])

            if res.ok:
                vb = KVA.assemble_from_verification(
                    ks, verification_id=res.payload["target_verification_id"],
                    repository_id=rec["repository_id"])
                if vb.get("ok"):
                    views.append(vb["view"])
                else:
                    blocked.append({"error_code": vb.get("error_code"),
                                    "detail": vb.get("detail")})
            else:
                blocked.append({"error_code": res.error_code,
                                "detail": res.detail})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return views, blocked


def emit(name, views, blocked, *, report=False):
    """把视图渲染成文件，返回摘要。"""
    htmls, jsons, cards = [], [], []
    for v in views:
        card = CM.build_card(v)
        js = CRD.render_json(card)
        ht = CRD.render_card_html(card, assembled_at=STAMP)
        jsons.append(js); htmls.append(ht); cards.append(card)

    if report and cards:
        rep = RPT.render_report_html(cards, assembled_at=STAMP)
    elif cards:
        rep = RPT.render_report_html(cards, assembled_at=STAMP)
    else:
        rep = CRD.render_blocked_html(
            blocked[0] if blocked else {"error_code": "VIEW_INTEGRITY_FAILED"},
            assembled_at=STAMP)

    files = {}
    if jsons:
        d = OUTDIR/name
        d.mkdir(parents=True, exist_ok=True)
        (d/"rendered_card.json").write_text(jsons[0], encoding="utf-8")
        (d/"knowledge_card.html").write_text(htmls[0], encoding="utf-8")
        files["card_json"] = str((d/"rendered_card.json").relative_to(ROOT))
        files["card_html"] = str((d/"knowledge_card.html").relative_to(ROOT))
        (d/"knowledge_report.html").write_text(rep, encoding="utf-8")
        files["report_html"] = str((d/"knowledge_report.html").relative_to(ROOT))

    return {
        "name": name,
        "view_count": len(views),
        "cards": [{"card_id": c["card_id"],
                   "commit": c["commit_sha"][:12],
                   "verdict": c["verification"]["status"],
                   "review": c["review"]["status"],
                   "provenance": c["provenance"]["level"],
                   "test_only": c["authorization"]["test_only"],
                   "local_coverage_only": c["evidence"]["local_coverage_only"]}
                  for c in cards],
        "blocked": blocked,
        "files": files,
        "html_sha": _sha(rep),
        "card_html_sha": _sha(htmls[0]) if htmls else None,
        "json_sha": _sha(jsons[0]) if jsons else None,
    }


OUTDIR.mkdir(parents=True, exist_ok=True)
scenarios = {}

# S1 完整快照 + 路径不存在 → refuted
v, b = build_scenario(label="s1_refuted", target_commit=B,
                      entries=[{"path": "docs", "type": "tree",
                                "sha": "d" * 40, "mode": "040000"}],
                      truncated=False, target_path="README")
scenarios["s1_refuted"] = emit("s1_refuted", v, b)

# S2 完整快照 + 路径存在 → supported
v, b = build_scenario(label="s2_supported", target_commit=B,
                      entries=[{"path": "README", "type": "blob",
                                "sha": "9" * 40, "size": 13, "mode": "100644"}],
                      truncated=False, target_path="README")
scenarios["s2_supported"] = emit("s2_supported", v, b)

# S3 PARTIAL 未覆盖 → insufficient_evidence
v, b = build_scenario(label="s3_partial", target_commit=B,
                      entries=[{"path": "docs", "type": "tree",
                                "sha": "d" * 40, "mode": "040000"}],
                      truncated=True, target_path="README")
scenarios["s3_partial"] = emit("s3_partial", v, b)

# S4 不同 Commit → 多版本对照报告
v, b = build_scenario(label="s4_multi", target_commit=B,
                      entries=[{"path": "docs", "type": "tree",
                                "sha": "d" * 40, "mode": "040000"}],
                      truncated=False, target_path="README")
scenarios["s4_multi"] = emit("s4_multi", v, b, report=True)

# ── 后台数据：只读性与分发检查 ──────────────────────────────
summary = {
  "artifact": "F2_P4A_E2E_PREVIEW",
  "generated_at": STAMP,
  "data_provenance": "HISTORICAL_REAL_DATA + SYNTHETIC_FIXTURE",
  "live_github_refetch": False,
  "real_human_authorization": False,
  "authorization_kind_used": "TEST_ONLY",
  "output_dir": str(OUTDIR.relative_to(ROOT)),
  "note": ("所有 HTML/JSON 均为本地内部预览产物；"
           "未联网、未使用真实人类授权；不是对外发布的正式知识"),
  "scenarios": scenarios,
  "pre_publish_check": None,
}

# 用第一个场景做分发检查
for key, sc in scenarios.items():
    if sc["view_count"] == 0:
        continue
    name = key
    html = (ROOT/sc["files"]["card_html"]).read_text(encoding="utf-8")
    js = json.loads((ROOT/sc["files"]["card_json"]).read_text(encoding="utf-8"))
    # 重建视图用于检查（轻量：从卡片反推关键字段）
    view_like = {
        "authorization_is_test_only": js["authorization"]["test_only"],
        "provenance_level": js["provenance"]["level"],
        "no_usable_evidence": js["evidence"]["no_usable_evidence"],
        "conflict_indicators": {},
        "limitations": js["limitations"],
    }
    chk = PPC.pre_publish_check({"html": html, "json": js}, view_like,
                                js["distribution"])
    summary["pre_publish_check"] = {"scenario": name, **chk}
    break

SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",
                   encoding="utf-8")

print("场景:", len(scenarios))
for k, sc in scenarios.items():
    print(f"  {k}: views={sc['view_count']} "
          f"cards={[c['verdict'] for c in sc['cards']]} "
          f"blocked={len(sc['blocked'])}")
print("输出目录:", summary["output_dir"])
print("分发检查:", {k: summary['pre_publish_check'][k]
                   for k in ("preview_allowed", "distribution_allowed",
                             "publish_blocked")}
      if summary["pre_publish_check"] else "无")
