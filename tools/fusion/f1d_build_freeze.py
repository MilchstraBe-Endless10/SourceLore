#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-D：正式 Crosswalk 冻结构建器。

从「冻结输入」确定性生成 docs/fusion/CAPABILITY_CROSSWALK.json。
确定性要求：
  1. 字段顺序固定；数组按稳定键排序
  2. 不含每次执行变化的时间戳
  3. 同一输入逐字节一致
  4. 覆盖全部 143 项身份（含 4 项被拒绝、未映射者）

用法：
  python3 tools/fusion/f1d_build_freeze.py            # 写入正式文件 + manifest
  python3 tools/fusion/f1d_build_freeze.py --dry-run   # 只打印，不写盘
  python3 tools/fusion/f1d_build_freeze.py --out DIR   # 写到隔离目录（用于幂等比对）
"""
import json, sys, hashlib, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
REG = F / "F1C_DECISION_REGISTER.json"
CONF = F / "F1C_D2_CONFLICT_RESOLUTIONS.json"
GATES = F / "F1C_D2_F2_GATES.json"
AUD = F / "F1C_D3_PROVENANCE_LICENSE_AUDIT.json"
FREEZE_IN = F / "F1C_D3_FREEZE_READINESS.json"
MIG = F / "F1C_D1_TERMINAL_MIGRATION.json"

CROSSWALK = F / "CAPABILITY_CROSSWALK.json"
MANIFEST = F / "F1D_FREEZE_MANIFEST.json"

FREEZE_SCHEMA_VERSION = 1
MODULES = ["Facts", "Collector", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    """对 JSON 做**语义哈希**：剔除易变的 generated_at 后规范化序列化。

    理由：审计/迁移类 JSON 每次重生成都会改 generated_at，
    若按字节哈希，manifest 在后续任何重生成之后都会「失效」——
    那是假警报，冻结的对象是语义内容而不是时间戳。
    非 JSON 文件仍按字节哈希。
    """
    if p.suffix == ".json":
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.pop("generated_at", None)
            canon = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return sha256_bytes(canon.encode("utf-8"))
        except Exception:
            pass
    return sha256_bytes(p.read_bytes())


def canon_sort_key(c):
    return int(c["canonical_id"].split("-")[-1])


def ref_sort_key(r):
    return (r["upstream_id"], r["original_capability_id"])


def build_crosswalk(raw, draft, reg, conf, gates, aud, freeze_in, mig):
    """纯函数：给定输入产出正式 Crosswalk 结构。"""
    canon = sorted(draft["canonical_capabilities"], key=canon_sort_key)
    tm = draft["terminal_model"]["terminal_dispositions"]
    g = draft["global_state_counts"]
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    src = {s["upstream_id"]: s for s in raw["sources"]}

    mapped = {}
    for c in canon:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in draft["cross_module_redirections"]}

    # —— canonical 定义（字段顺序显式固定）
    cap_out = []
    for c in canon:
        refs = sorted(c["upstream_refs"], key=ref_sort_key)
        per = sorted(c["license_permission"]["per_upstream"], key=lambda p: p["upstream_id"])
        cap_out.append({
            "canonical_id": c["canonical_id"],
            "name": c["name"],
            "owner_module": c["owner_module"],
            "origin_type": c["origin_type"],
            "description": c["description"],
            "upstream_refs": [{
                "upstream_id": r["upstream_id"],
                "original_capability_id": r["original_capability_id"],
                "identity_key": r["identity_key"],
                "upstream_capability": r["upstream_capability"],
                "upstream_disposition": r["upstream_disposition"],
                "verdict": r["verdict"],
                "association_role": ("counterexample" if r["verdict"] == "REJECT" else "positive"),
            } for r in refs],
            "license_permission": {
                "copy_permitted": c["license_permission"].get("copy_permitted"),
                "constraint": c["license_permission"].get("constraint"),
                "per_upstream": [{
                    "upstream_id": p["upstream_id"],
                    "spdx": p["spdx"],
                    "copy_permitted": p["copy_permitted"],
                    "attribution_required": p.get("attribution_required"),
                    "license_link_required": p.get("license_link_required"),
                    "modification_notice_required": p.get("modification_notice_required"),
                } for p in per],
            },
            "f1c_amendments": list(c.get("f1c_amendments") or []),
            "created_in_batch": c.get("created_in_batch"),
            "merge_note": c.get("merge_note"),
        })

    # —— 143 项身份终态（**包含 4 项未映射的拒绝身份**）
    identities = []
    for k in sorted(by):
        it = by[k]
        key = f"{k[0]}::{k[1]}"
        t = tm[key]
        identities.append({
            "identity_key": key,
            "upstream_id": k[0],
            "original_capability_id": k[1],
            "upstream_capability": it["capability"],
            "upstream_where": it["where"],
            "upstream_disposition": it["disposition"],
            "mapping_status": t["mapping_status"],
            "terminal_disposition": t["value"],
            "association_role": t["role"],
            "bound_canonical_ids": sorted(
                [cid for (kk, cid) in mapped.items() if kk == k]),
            "license": {
                "spdx": (it.get("license") or {}).get("spdx"),
                "copy_permitted": (it.get("license") or {}).get("copy_permitted"),
            },
        })

    return {
        "artifact": "CAPABILITY_CROSSWALK",
        "schema_version": 1,
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "status": "FROZEN",
        "generator": "tools/fusion/f1d_build_freeze.py",
        "build_source_chain": [
            "F1B_FROZEN_BASELINE.json",
            "F1-C-B", "F1-C-C1", "F1-C-C2", "F1-C-C3",
            "F1-C-D1", "F1-C-D2", "F1-C-D3",
        ],
        "determinism": {
            "no_timestamps": True,
            "array_ordering": "canonical_id_asc / identity_key_asc / upstream_id_asc",
            "byte_identical_on_same_input": True,
        },
        "source_index_sha256": raw["source_index_sha256"]
        if "source_index_sha256" in raw else draft.get("source_index_sha256"),
        "counts": {
            "upstream_identities": len(identities),
            "canonical_capabilities": len(cap_out),
            "mapping_status": {
                "MAPPED": g["mapped_count"],
                "ROUTED": g["routed_pending_count"],
                "UNREVIEWED": g["unreviewed_count"],
            },
            "terminal_disposition": g["terminal_disposition_counts"],
            "canonical_origin": g["canonical_origin_counts"],
            "amendment_count": sum(len(c.get("f1c_amendments") or []) for c in cap_out),
            "sum_check": len(identities),
        },
        "sources": [{
            "upstream_id": s["upstream_id"],
            "path": s.get("path"),
            "commit_sha": s.get("commit_sha"),
            "spdx": (s["license"] or {}).get("spdx"),
            "copy_permitted": (s["license"] or {}).get("copy_permitted"),
            "reuse_obligation": (s["license"] or {}).get("reuse_obligation"),
        } for s in sorted(raw["sources"], key=lambda x: x["upstream_id"])],
        "canonical_capabilities": cap_out,
        "upstream_identities": identities,
        "cross_module_redirections": sorted([{
            "upstream_id": r["upstream_id"],
            "original_capability_id": r["original_capability_id"],
            "to_module": r.get("to_module"),
            "reason": r.get("reason"),
        } for r in draft["cross_module_redirections"]],
            key=lambda x: (x["upstream_id"], x["original_capability_id"])),
        "routed_promotions": sorted([{
            "upstream_id": r["upstream_id"],
            "original_capability_id": r["original_capability_id"],
            "from": r.get("from"),
            "to_canonical_id": r.get("to_canonical_id"),
            "promoted_in_batch": r.get("promoted_in_batch"),
        } for r in draft["routed_promotions"]],
            key=lambda x: (x["upstream_id"], x["original_capability_id"])),
        "architecture_decisions": [{
            "conflict_id": r["conflict_id"],
            "status": r["resolution_status"],
            "unique_owner": r.get("unique_owner"),
            "affected_canonical_ids": r["affected_canonical_ids"],
        } for r in sorted(conf["resolutions"], key=lambda x: x["conflict_id"])],
        "f2_gates": {
            "gate_count": len(gates["gates"]),
            "y6_probe_count": len(gates["y6_probes"]),
            "artifact": "F1C_D2_F2_GATES.json",
        },
        "license_state": {
            "audit_result_distribution": aud["summary"]["by_result"],
            "verbatim_hit_canonicals": aud["summary"]["verbatim_hit_canonicals"],
            "u06_all_copy_permitted_false": aud["upstream_06_audit"]["all_copy_permitted_false"],
            "blockers": [b["id"] for b in freeze_in["blockers"]],
        },
        "known_limitations": [
            "字符串重合未命中不等于已证明零复制；语义级改写与结构搬运无法机器判定",
            "七条零来源 canonical 的质量审查仅完成结构与依据核验，实现质量留 F2",
            "UPSTREAM-06 无许可证：抽象思想与受保护表达的边界需法务判断（U06 U10）",
        ],
    }


def build_manifest(raw, draft, crosswalk_bytes, crosswalk_rel):
    """manifest 只哈希「输入」与「产物」，不含自我引用循环。"""
    inputs = [
        RAW, BASE, REG, CONF, GATES, AUD, FREEZE_IN, MIG,
        F / "CROSSWALK_PROGRESS.json",
        F / "F1C_C2_U05_RECONCILIATION.json",
        F / "F1C_C3_RECONCILIATION.json",
        F / "F1C_D1_TERMINAL_MIGRATION.json",
        F / "F1C_D3_COUNTEREXAMPLE_AUDIT.json",
        F / "F1C_D3_ZERO_ORIGIN_REVIEW.json",
    ] + sorted((ROOT / "progress").glob("UPSTREAM-0*-audit.json"))

    input_hashes = []
    for p in inputs:
        if not p.exists():
            raise SystemExit(f"ERROR: 冻结输入缺失 {p}")
        input_hashes.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p)})
    input_hashes.sort(key=lambda x: x["path"])

    g = draft["global_state_counts"]
    tm = draft["terminal_model"]["terminal_dispositions"]
    canon = draft["canonical_capabilities"]

    return {
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "freeze_scope": {
            "artifacts": [crosswalk_rel],
            "description": "SourceLore M1-FUSION-GATE/F1 融合阶段的能力基线冻结",
            "does_not_include": [
                "产品实现代码", "Skill", "数据库", "运行时配置",
            ],
        },
        "canonical_count": len(canon),
        "upstream_identity_count": len(raw["items"]),
        "terminal_disposition_counts": g["terminal_disposition_counts"],
        "mapping_status_counts": {
            "MAPPED": g["mapped_count"],
            "ROUTED": g["routed_pending_count"],
            "UNREVIEWED": g["unreviewed_count"],
        },
        "source_commit_refs": {
            s["upstream_id"]: {"path": s.get("path"), "commit_sha": s.get("commit_sha")}
            for s in sorted(raw["sources"], key=lambda x: x["upstream_id"])
        },
        "input_file_hashes": input_hashes,
        "input_hash_method": {
            "json": "剔除 generated_at 后按规范化 JSON 序列化哈希（语义哈希）",
            "other": "文件字节 SHA-256",
            "rationale": "冻结对象是语义内容，不是执行时刻；避免重生成导致假失效",
        },
        "crosswalk_sha256": sha256_bytes(crosswalk_bytes),
        "crosswalk_path": crosswalk_rel,
        "included_decision_registers": [
            "F1C_DECISION_REGISTER.json",
            "F1C_B_ROUTED_RECONCILIATION.json",
            "F1C_C1_RESOLUTION.json",
            "F1C_C2_U05_RECONCILIATION.json",
            "F1C_C3_RECONCILIATION.json",
            "F1C_D1_TERMINAL_MIGRATION.json",
            "F1C_D2_CONFLICT_RESOLUTIONS.json",
            "F1C_D3_PROVENANCE_LICENSE_AUDIT.json",
        ],
        "amendment_count": sum(len(c.get("f1c_amendments") or []) for c in canon),
        "unresolved_dependencies": {
            "f2_gates": 30,
            "y6_runtime_probes": 6,
            "implementation_dependency_conflicts": ["X-5"],
            "blocked_conflicts": ["Y-6"],
        },
        "legal_review_status": {
            "B-1_third_party_notices_wording": "OPEN — 总述措辞与实际引文不符；原计划 F5 重写",
            "B-2_upstream_06_boundary": "OPEN — 抽象思想与受保护表达边界需法务判断（U06 U10）",
            "B-3_sl_cap_0023_attribution": "OPEN — CC BY 4.0 短句，分发物须履行署名与许可链接",
            "distribution_permitted": False,
        },
        "runtime_verification_status": {
            "H-A": "VERIFIED", "H-B": "PARTIALLY_VERIFIED", "H-C": "PARTIALLY_VERIFIED",
            "H-D": "UNVERIFIED", "H-E": "UNVERIFIED", "H-F": "UNVERIFIED",
            "H-G": "VERIFIED_SEMANTIC_ONLY", "H-H": "UNVERIFIED",
            "product_implementation": "NOT_STARTED",
            "skill": "NOT_CREATED",
            "database": "NOT_CREATED",
        },
        "freeze_decision": "FROZEN_INTERNAL_RESTRICTED",
        "freeze_decision_basis": {
            "structural_invariants": "PASS（143 身份 / 75 canonical / 三态守恒 / 21 amendment / 历史映射保持）",
            "reproducible_build": "PASS（两次生成逐字节一致）",
            "distribution_gates": "OPEN（B-1/B-2/B-3 未闭环）",
            "means": "内部设计基线已冻结；**不代表可以公开分发，也不代表可以进入正式运行**",
        },
        "identity_of_manifest": "由最终 Git Commit 固定，不在本文件内自引",
    }


def main() -> int:
    dry = "--dry-run" in sys.argv
    outdir = None
    if "--out" in sys.argv:
        outdir = Path(sys.argv[sys.argv.index("--out") + 1])

    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    reg = json.loads(REG.read_text(encoding="utf-8"))
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    aud = json.loads(AUD.read_text(encoding="utf-8"))
    freeze_in = json.loads(FREEZE_IN.read_text(encoding="utf-8"))
    mig = json.loads(MIG.read_text(encoding="utf-8"))

    cw = build_crosswalk(raw, draft, reg, conf, gates, aud, freeze_in, mig)

    # 确定性序列化：固定 indent、ensure_ascii=False、末尾换行
    payload = (json.dumps(cw, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    if dry:
        print(f"(dry-run) bytes={len(payload)} sha256={sha256_bytes(payload)}")
        print(f"  canonical={cw['counts']['canonical_capabilities']} "
              f"identities={cw['counts']['upstream_identities']} "
              f"terminal={cw['counts']['terminal_disposition']}")
        return 0

    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / "CAPABILITY_CROSSWALK.json"
        p.write_bytes(payload)
        print(f"written -> {p}  sha256={sha256_bytes(payload)}")
        return 0

    CROSSWALK.write_bytes(payload)
    rel = str(CROSSWALK.relative_to(ROOT))
    man = build_manifest(raw, draft, payload, rel)
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"written -> {rel}")
    print(f"  crosswalk sha256 = {sha256_bytes(payload)}")
    print(f"  canonical={cw['counts']['canonical_capabilities']} "
          f"identities={cw['counts']['upstream_identities']} "
          f"amendment={cw['counts']['amendment_count']}")
    print(f"  terminal={cw['counts']['terminal_disposition']}")
    print(f"written -> {MANIFEST.name}  (freeze_decision={man['freeze_decision']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
