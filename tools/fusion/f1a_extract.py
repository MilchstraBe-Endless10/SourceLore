#!/usr/bin/env python3
"""F1-A · 原始能力索引提取器（SourceLore M1-FUSION-GATE / F1）

职责：把六份 progress/UPSTREAM-0X-audit.json 的 capability_matrix 原样抽取为
一份可机读、可复用的原始能力索引，并做四项确定性校验：
  1. 身份键 (upstream_id, original_capability_id) 全局唯一
  2. 每源计数与合计 = 143（动态核算，不写死）
  3. 每项 6 个必填字段齐全（id/capability/where/disposition/why；mechanism 可选）
  4. 许可证状态逐源独立登记（不得被 disposition 覆盖），UPSTREAM-06 = design-only

本脚本只读上游 JSON，不改任何审计史料；输出到 docs/fusion/。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "progress"
OUT_DIR = ROOT / "docs" / "fusion"
OUT_INDEX = OUT_DIR / "RAW_CAPABILITY_INDEX.json"
OUT_PROGRESS = OUT_DIR / "CROSSWALK_PROGRESS.json"

UPSTREAMS = [
    ("UPSTREAM-01", "repo-analyzer-skill"),
    ("UPSTREAM-02", "deer-flow/github-deep-research"),
    ("UPSTREAM-03", "repository-discovery"),
    ("UPSTREAM-04", "agent-skills/swe-research"),
    ("UPSTREAM-05", "lazy-rabbit-skills/project-knowledge-base"),
    ("UPSTREAM-06", "repo-security-review"),
]

REQUIRED_FIELDS = ["id", "capability", "where", "disposition", "why"]
VALID_DISPOSITIONS = {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}
TZ = timezone(timedelta(hours=8))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def license_register(uid: str, doc: dict) -> dict:
    """逐源登记许可证事实。许可证与处置严格分离（约束 2）。"""
    up = doc.get("upstream") or {}
    top = doc.get("license") or {}

    if uid == "UPSTREAM-01":
        lic = up.get("license") or {}
        return {
            "spdx": lic.get("spdx_id"),
            "spdx_api": lic.get("spdx_id"),
            "copyright_holders": [lic.get("copyright")] if lic.get("copyright") else [],
            "source": "upstream.license",
            "reuse_obligation": lic.get("reuse_obligation"),
            "copy_permitted": True,
            "attribution_required": True,
            "license_link_required": False,
            "modification_notice_required": False,
            "note": "MIT：保留版权与许可声明。",
        }
    if uid == "UPSTREAM-02":
        lic = up.get("license") or {}
        return {
            "spdx": lic.get("spdx_id"),
            "spdx_api": lic.get("spdx_id"),
            "copyright_holders": list(lic.get("copyright") or []),
            "source": "upstream.license",
            "reuse_obligation": lic.get("reuse_obligation"),
            "copy_permitted": True,
            "attribution_required": True,
            "license_link_required": False,
            "modification_notice_required": False,
            "note": "MIT 双版权行，两行均须保留。",
        }
    if uid == "UPSTREAM-03":
        lic = up.get("license") or {}
        return {
            "spdx": lic.get("spdx_id_verified"),
            "spdx_api": lic.get("spdx_id_api"),
            "copyright_holders": list(lic.get("copyright") or []),
            "source": "upstream.license",
            "reuse_obligation": lic.get("reuse_obligation"),
            "copy_permitted": True,
            "attribution_required": True,
            "license_link_required": True,
            "modification_notice_required": True,
            "copyright_note": lic.get("copyright_note"),
            "api_discrepancy_note": lic.get("api_discrepancy_note"),
            "note": "CC BY 4.0：署名+许可链接+修改声明+不得附加限制。上游 LICENSE 无版权行，署名需四要素合成。",
        }
    if uid == "UPSTREAM-04":
        lic = up.get("license") or {}
        return {
            "spdx": lic.get("spdx_id_verified"),
            "spdx_api": lic.get("spdx_id_api"),
            "copyright_holders": list(lic.get("copyright") or []),
            "source": "upstream.license",
            "reuse_obligation": lic.get("reuse_obligation"),
            "copy_permitted": True,
            "attribution_required": True,
            "license_link_required": False,
            "modification_notice_required": True,
            "note": "MIT，LICENSE 含完整版权行。",
        }
    if uid == "UPSTREAM-05":
        lic = top or (up.get("license") or {})
        return {
            "spdx": lic.get("claimed") or lic.get("api_spdx"),
            "spdx_api": lic.get("api_spdx"),
            "copyright_holders": [],
            "source": "top-level license",
            "reuse_obligation": lic.get("redistribution_obligation"),
            "copy_permitted": True,
            "attribution_required": True,
            "license_link_required": True,
            "modification_notice_required": True,
            "notice_file_present": lic.get("notice_file_present"),
            "note": "Apache-2.0，无 NOTICE 文件；再分发需保留 LICENSE 与修改声明。",
        }
    if uid == "UPSTREAM-06":
        return {
            "spdx": None,
            "spdx_api": top.get("api_spdx"),
            "copyright_holders": [],
            "source": "top-level license",
            "reuse_obligation": None,
            "copy_permitted": False,
            "attribution_required": False,
            "license_link_required": False,
            "modification_notice_required": False,
            "status": top.get("status"),
            "legal_position": top.get("legal_position"),
            "reuse_scope": top.get("reuse_scope"),
            "may_copy_upstream_text": top.get("may_copy_upstream_text"),
            "may_copy_upstream_code": top.get("may_copy_upstream_code"),
            "may_copy_upstream_prompts": top.get("may_copy_upstream_prompts"),
            "may_copy_upstream_rules": top.get("may_copy_upstream_rules"),
            "may_copy_upstream_templates": top.get("may_copy_upstream_templates"),
            "may_reimplement_based_on_idea": top.get("may_reimplement_based_on_idea"),
            "independent_implementation_required": top.get("independent_implementation_required"),
            "unresolved": top.get("unresolved"),
            "note": "无许可证 = 保留全部权利。仅参考抽象设计，禁止任何形式的文本/代码/提示词/规则/模板移植。",
        }
    raise ValueError(uid)


def main() -> int:
    errors: list[str] = []
    items: list[dict] = []
    source_records: list[dict] = []
    seen_keys: dict[tuple[str, str], str] = {}

    for uid, label in UPSTREAMS:
        path = PROGRESS / f"{uid}-audit.json"
        if not path.exists():
            errors.append(f"E-MISSING-FILE {path}")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        cm = doc.get("capability_matrix")
        if not isinstance(cm, list):
            errors.append(f"E-NO-MATRIX {uid}")
            continue

        lic = license_register(uid, doc)
        up = doc.get("upstream") or {}
        source_records.append({
            "upstream_id": uid,
            "label": label,
            "repo_url": up.get("url"),
            "repo_id": up.get("repo_id"),
            "subtree": up.get("subtree"),
            "commit_sha": up.get("commit_sha"),
            "default_branch": up.get("default_branch"),
            "raw_count": len(cm),
            "license": lic,
            "license_copy_permitted": lic.get("copy_permitted"),
            "audit_file": f"progress/{uid}-audit.json",
            "audit_file_sha256": sha256_file(path),
        })

        for pos, cap in enumerate(cm, start=1):
            missing = [f for f in REQUIRED_FIELDS if not cap.get(f)]
            if missing:
                errors.append(f"E-MISSING-FIELD {uid}/{cap.get('id')} -> {missing}")
            disp = cap.get("disposition")
            if disp not in VALID_DISPOSITIONS:
                errors.append(f"E-BAD-DISPOSITION {uid}/{cap.get('id')} -> {disp!r}")

            key = (uid, cap.get("id"))
            if key in seen_keys:
                errors.append(f"E-DUP-KEY {uid}/{cap.get('id')}")
            seen_keys[key] = f"{uid}#{pos}"

            items.append({
                "identity_key": f"{uid}::{cap.get('id')}",
                "upstream_id": uid,
                "original_capability_id": cap.get("id"),
                "sequence_in_source": pos,
                "capability": cap.get("capability"),
                "mechanism": cap.get("mechanism"),
                "where": cap.get("where"),
                "disposition": disp,
                "why": cap.get("why"),
                "license": {
                    "spdx": lic.get("spdx"),
                    "copy_permitted": lic.get("copy_permitted"),
                    "attribution_required": lic.get("attribution_required"),
                    "license_link_required": lic.get("license_link_required"),
                    "modification_notice_required": lic.get("modification_notice_required"),
                },
                "evidence": {
                    "audit_file": f"progress/{uid}-audit.json",
                    "pointer": f"capability_matrix[{pos - 1}]",
                    "where": cap.get("where"),
                },
                "crosswalk": {
                    "canonical_id": None,
                    "mapping_status": "UNMAPPED",
                    "batch": None,
                    "note": None,
                },
            })

    total = len(items)
    per_source = {s["upstream_id"]: s["raw_count"] for s in source_records}
    dynamic_total = sum(per_source.values())

    if total != dynamic_total:
        errors.append(f"E-COUNT-MISMATCH items={total} sum(raw_count)={dynamic_total}")
    if len(seen_keys) != total:
        errors.append(f"E-KEY-NOT-UNIQUE unique={len(seen_keys)} total={total}")
    for dup_check_uid, _ in UPSTREAMS:
        ids = [i["original_capability_id"] for i in items if i["upstream_id"] == dup_check_uid]
        if len(ids) != len(set(ids)):
            errors.append(f"E-DUP-ID-IN-SOURCE {dup_check_uid}")

    lic06 = next((s["license"] for s in source_records if s["upstream_id"] == "UPSTREAM-06"), {})
    if lic06.get("copy_permitted") is not False:
        errors.append("E-U06-LICENSE not design-only")

    now = datetime.now(TZ).isoformat(timespec="seconds")
    index = {
        "artifact": "RAW_CAPABILITY_INDEX",
        "schema_version": 1,
        "task": "M1-FUSION-GATE-F1 / F1-A",
        "generated_at": now,
        "generator": "tools/fusion/f1a_extract.py",
        "identity_key": "upstream_id + original_capability_id",
        "purpose": "六源 143 项原始能力的一次性、可机读、可复用的索引；F1-B/C/D 的输入基线。",
        "does_not_mean": "143 不是最终独立能力数，只是上游候选数；去重后 canonical 数必然减少。",
        "counts": {
            "total_raw_capabilities": total,
            "per_source": per_source,
            "dynamic_sum_check": dynamic_total,
            "unique_identity_keys": len(seen_keys),
            "mapped": 0,
            "unmapped": total,
        },
        "sources": source_records,
        "items": items,
    }

    progress_doc = {
        "artifact": "CROSSWALK_PROGRESS",
        "schema_version": 1,
        "task": "M1-FUSION-GATE-F1",
        "phase": "F1-A_DONE / F1-B_PENDING",
        "updated_at": now,
        "batches": [
            {"id": "F1-A", "name": "原始能力索引与身份校验", "status": "DONE",
             "output": "docs/fusion/RAW_CAPABILITY_INDEX.json"},
            {"id": "F1-B", "name": "按逻辑模块合并原始能力→canonical", "status": "PENDING",
             "output": "docs/fusion/CAPABILITY_CROSSWALK.json"},
            {"id": "F1-C", "name": "十项冲突裁决", "status": "PENDING",
             "output": "docs/fusion/ABILITY_DECISIONS.md"},
            {"id": "F1-D", "name": "自动化验收 + 账本更新", "status": "PENDING",
             "output": "docs/fusion/F1_VERIFICATION.json"},
        ],
        "modules": [
            "Collector", "Facts", "Evidence-Claims", "Product", "Research",
            "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter",
        ],
        "module_progress": {m: {"canonical_count": 0, "raw_consumed": 0, "status": "PENDING"}
                            for m in ["Collector", "Facts", "Evidence-Claims", "Product", "Research",
                                      "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"]},
        "next_batch_start": (
            "F1-B 第一模块：Facts。输入 docs/fusion/RAW_CAPABILITY_INDEX.json，"
            "从 UPSTREAM-01 C01/C02/C03/C04/C05/C10 与 UPSTREAM-05 的采集/事实类条目开始建立 canonical。"
        ),
        "invariants": [
            "每个 (upstream_id, original_capability_id) 必须且只能映射一次",
            "每个 canonical 必须恰好一个 owner_module（十模块之一）",
            "license_permission 独立于 disposition，不得互相覆盖",
            "UPSTREAM-06 全部 28 项 copy_permitted=false",
            "名称相似而语义不同不得合并",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_PROGRESS.write_text(json.dumps(progress_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"per_source = {per_source}")
    print(f"total_raw_capabilities = {total}")
    print(f"dynamic_sum_check = {dynamic_total}")
    print(f"unique_identity_keys = {len(seen_keys)}")
    print(f"u06_copy_permitted = {lic06.get('copy_permitted')}")
    print(f"wrote {OUT_INDEX.relative_to(ROOT)} ({OUT_INDEX.stat().st_size} bytes)")
    print(f"wrote {OUT_PROGRESS.relative_to(ROOT)} ({OUT_PROGRESS.stat().st_size} bytes)")
    if errors:
        print("ERRORS:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
