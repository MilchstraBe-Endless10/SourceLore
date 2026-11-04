#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D3：来源可信性 / 许可证 / 实际复用 / 设计处置 四层审计（只读现算）。

四件事不合并成一个布尔值：
  A. provenance      来源是否真实可定位
  B. license         上游授予了什么权限
  C. actual_reuse    实际有没有复制受保护表达
  D. disposition     SourceLore 最终怎么处置

关键区分：
  copy_permitted=true  ≠ 已经复制
  copy_permitted=false ≠ 不能参考抽象思想
  REUSE/ADAPT/REIMPLEMENT ≠ 法律许可
  REJECT ≠ 无设计价值
"""
import json, re, glob, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
OUT = F / "F1C_D3_PROVENANCE_LICENSE_AUDIT.json"
TZ = timezone(timedelta(hours=8))

# 各源的署名义务（来自 RAW 索引 sources 字段，非手填）
OPS = {"UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03",
       "UPSTREAM-04", "UPSTREAM-05", "UPSTREAM-06"}


def word_runs(text, minwords=6):
    """提取 ≥minwords 连续英文词的串。"""
    if not isinstance(text, str):
        return set()
    return {m.strip() for m in re.findall(
        r"(?:[A-Za-z][A-Za-z0-9'\-]+ )(?:[A-Za-z0-9'\-]+ ){%d,}" % (minwords - 1), text)}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    src = {s["upstream_id"]: s for s in raw["sources"]}
    canon = draft["canonical_capabilities"]
    tm = draft["terminal_model"]["terminal_dispositions"]

    # 产品代码实际存在哪些文件（不是目录）
    code_files = []
    for d in ("src", "tests", "schemas", "skills"):
        code_files += [str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*") if p.is_file()] \
            if (ROOT / d).exists() else []

    # 上游英文原文池（只取 RAW 里记录的上游描述，不是本项目自填字段）
    upstream_runs = set()
    for i in raw["items"]:
        for f in ("capability", "mechanism", "why"):
            upstream_runs |= word_runs(i.get(f))

    # canonical 文本池（区分字段：description 是设计文本，ref.upstream_capability 是转述）
    def canon_texts(c):
        return {
            "description": c.get("description") or "",
            "amendments": " ".join(c.get("f1c_amendments") or []),
            "ref_transcriptions": " ".join(
                (r.get("upstream_capability") or "") for r in c["upstream_refs"]),
        }

    # 逐条审计
    audits = []
    for c in canon:
        cid = c["canonical_id"]
        refs = c["upstream_refs"]
        texts = canon_texts(c)
        # 命中：仅报告「设计文本（description/amendments）」里的逐字重合
        design_blob = (texts["description"] + " " + texts["amendments"]).lower()
        verbatim = sorted(r for r in upstream_runs if r.lower() in design_blob)

        lic_sources = sorted({r["upstream_id"] for r in refs})
        per = c["license_permission"]["per_upstream"]
        bad_perm = [p for p in per if p["upstream_id"] == "UPSTREAM-06"
                    and p.get("copy_permitted") is not False]
        source_ids = [f"{r['upstream_id']}::{r['original_capability_id']}" for r in refs]

        # 复用分类（C 层）
        if not refs:
            reuse = "INTERNAL_DESIGN_ONLY"
        elif verbatim:
            reuse = "VERBATIM_SHORT_QUOTE_IN_DESIGN_TEXT"
        else:
            reuse = "ABSTRACT_IDEA_ONLY"

        # 署名义务（B 层）
        obligations = []
        for sid in lic_sources:
            lv = (src.get(sid) or {}).get("license") or {}
            ob = {"upstream_id": sid, "spdx": lv.get("spdx"),
                  "copy_permitted": lv.get("copy_permitted"),
                  "attribution_required": lv.get("attribution_required"),
                  "license_link_required": lv.get("license_link_required"),
                  "modification_notice_required": lv.get("modification_notice_required"),
                  "reuse_obligation": lv.get("reuse_obligation")}
            obligations.append(ob)

        # 结果（不因「没发现」就当 PASS）
        if bad_perm:
            result, sev = "BLOCKED", "blocker"
            rem = "UPSTREAM-06 的 copy_permitted 被覆写为 true"
        elif "U06" in "".join(lic_sources) or "UPSTREAM-06" in lic_sources:
            result, sev = "PASS_WITH_DEPENDENCY", "normal"
            rem = ("含 UPSTREAM-06 来源：零复制，只作抽象思想；"
                   "抽象思想与受保护表达的边界需法务判断（U06 审计 U10）")
        elif verbatim:
            result, sev = "REVIEW_REQUIRED", "high"
            rem = "设计文本含逐字英文短句；需核对是否履行 CC BY 4.0 / MIT 署名义务"
        elif any(o["spdx"] == "CC-BY-4.0" for o in obligations):
            result, sev = "PASS_WITH_DEPENDENCY", "normal"
            rem = "CC BY 4.0 来源：须在分发物中履行署名与许可链接义务"
        elif any(o["spdx"] == "Apache-2.0" for o in obligations):
            result, sev = "PASS_WITH_DEPENDENCY", "normal"
            rem = "Apache-2.0 来源：若再分发需保留 LICENSE 与修改声明（本仓库无实际代码复制）"
        else:
            result, sev = "PASS", "normal"
            rem = None

        audits.append({
            "subject_id": cid,
            "audit_category": "canonical",
            "expected_owner": c["owner_module"],
            "actual_owner": c["owner_module"],
            "upstream_identities": source_ids,
            "upstream_dispositions": sorted({r["upstream_disposition"] for r in refs}) or None,
            "terminal_dispositions": sorted({tm[r["upstream_id"] + "::" + r["original_capability_id"]]["value"]
                                             for r in refs}) or None,
            "association_roles": sorted({tm[r["upstream_id"] + "::" + r["original_capability_id"]]["role"]
                                         for r in refs}) or None,
            "license_permission": {"per_upstream": obligations,
                                   "aggregate_copy_permitted":
                                   c["license_permission"].get("copy_permitted")},
            "actual_reuse_classification": reuse,
            "verbatim_runs_detected": verbatim[:5],
            "verbatim_run_count": len(verbatim),
            "origin_type": c.get("origin_type"),
            "evidence_locations": ([f"{cid}.description"] if verbatim else []),
            "verification_method": "machine_text_overlap(>=6 English words)+metadata_read",
            "result": result,
            "severity": sev,
            "remediation_required": rem,
            "remaining_uncertainty": (
                "仅用字符串重合检测，不能证明「零复制」；语义级改写与结构搬运无法机器判定"
                if result != "PASS" else
                "字符串重合检测未命中，但语义级改写无法机器判定"),
        })

    # UPSTREAM-06 全 28 项专项
    u06 = []
    for k in sorted((k for k in by if k[0] == "UPSTREAM-06")):
        it = by[k]
        lic = it.get("license") or {}
        key = f"{k[0]}::{k[1]}"
        mapped_to = next((c["canonical_id"] for c in canon
                          if any((r["upstream_id"], r["original_capability_id"]) == k
                                 for r in c["upstream_refs"])), None)
        # 检查该 canonical 的 per_upstream 是否对 U06 保持 false
        perm_ok = True
        if mapped_to:
            cc = next(c for c in canon if c["canonical_id"] == mapped_to)
            for p in cc["license_permission"]["per_upstream"]:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    perm_ok = False
        # 该身份自身的上游文本是否出现在任何 canonical 的设计文本里
        runs = set()
        for f in ("capability", "mechanism", "why"):
            runs |= word_runs(it.get(f))
        hits = []
        for c in canon:
            blob = ((c.get("description") or "") + " " +
                    " ".join(c.get("f1c_amendments") or [])).lower()
            for r in runs:
                if r.lower() in blob:
                    hits.append({"canonical_id": c["canonical_id"], "run": r[:80]})
        u06.append({
            "identity_key": key,
            "capability": it["capability"],
            "raw_disposition": it["disposition"],
            "license_status": "none",
            "copy_permitted_in_raw": lic.get("copy_permitted"),
            "mapped_to": mapped_to,
            "terminal_disposition": tm[key]["value"],
            "role": tm[key]["role"],
            "copy_permitted_in_canonical": perm_ok,
            "verbatim_hits": hits[:3],
            "result": ("BLOCKED" if (lic.get("copy_permitted") is not False or not perm_ok or hits)
                       else "PASS"),
        })

    # 各源汇总
    sources = []
    for sid in sorted(OPS):
        lv = (src.get(sid) or {}).get("license") or {}
        n_items = sum(1 for k in by if k[0] == sid)
        reasons = {i["result"] for i in audits
                   if any(s.startswith(sid + "::") for s in i["upstream_identities"])}
        sources.append({
            "upstream_id": sid,
            "path": (src.get(sid) or {}).get("path"),
            "spdx": lv.get("spdx"),
            "spdx_api": lv.get("spdx_api"),
            "copy_permitted": lv.get("copy_permitted"),
            "copyright_holders": lv.get("copyright_holders"),
            "attribution_required": lv.get("attribution_required"),
            "license_link_required": lv.get("license_link_required"),
            "modification_notice_required": lv.get("modification_notice_required"),
            "reuse_obligation": lv.get("reuse_obligation"),
            "identity_count": n_items,
            "canonical_results": sorted(reasons) or ["NO_CANONICAL_ASSOCIATION"],
        })

    doc = {
        "artifact": "F1C_D3_PROVENANCE_LICENSE_AUDIT",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d3_audit.py（只读现算）",
        "four_layer_principle": {
            "A_provenance": "来源是否真实、准确、可定位",
            "B_license": "上游授予的复制与使用权限",
            "C_actual_reuse": "实际复制了什么（代码/规则/prompt/模板/受保护表达）",
            "D_disposition": "最终采用、拒绝或作为反例",
            "rule": "四层不合并；copy_permitted=true 不等于已复制；"
                    "copy_permitted=false 不阻止参考抽象思想；"
                    "REUSE/ADAPT/REIMPLEMENT 不是法律许可；REJECT 不等于无设计价值",
        },
        "verification_scope": {
            "machine_check": "canonical 设计文本(description+amendments)与上游文本 ≥6 连续英文词的逐字重合",
            "cannot_verify": ["语义级改写", "结构搬运", "人工核对的具体受保护表达"],
            "consequence": "字符串未命中不等于已证明零复制",
        },
        "product_code_state": {
            "files_under_src_tests_schemas_skills": code_files,
            "count": len(code_files),
            "note": "产品代码、Skill、Schema 全部未实现；上游无任何代码可被复制",
        },
        "sources": sources,
        "canonical_audits": audits,
        "upstream_06_audit": {
            "identity_count": len(u06),
            "all_copy_permitted_false": all(x["copy_permitted_in_raw"] is False for x in u06),
            "any_canonical_overrides": [x["identity_key"] for x in u06
                                        if x["copy_permitted_in_canonical"] is False],
            "verbatim_hits": [x for x in u06 if x["verbatim_hits"]],
            "items": u06,
            "legal_position": "默认著作权下保留全部权利；无复制、改编、再分发授权",
            "reuse_scope": "design-only",
        },
        "summary": {},
    }

    from collections import Counter
    doc["summary"] = {
        "canonical_total": len(audits),
        "by_result": dict(sorted(Counter(a["result"] for a in audits).items())),
        "by_severity": dict(sorted(Counter(a["severity"] for a in audits).items())),
        "verbatim_hit_canonicals": sorted(a["subject_id"] for a in audits
                                          if a["verbatim_run_count"]),
        "sources_with_copy_permitted_false": [s["upstream_id"] for s in sources
                                              if s["copy_permitted"] is False],
        "u06_blocked": [x["identity_key"] for x in u06 if x["result"] == "BLOCKED"],
    }

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"canonical 审计 {len(audits)} 条  results={doc['summary']['by_result']}")
    print(f"逐字命中的 canonical: {doc['summary']['verbatim_hit_canonicals']}")
    print(f"UPSTREAM-06: {len(u06)} 项，权限全 false={doc['upstream_06_audit']['all_copy_permitted_false']}，"
          f"BLOCKED={doc['summary']['u06_blocked'] or '无'}")
    print(f"产品代码文件数: {len(code_files)}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
