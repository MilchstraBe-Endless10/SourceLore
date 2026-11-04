#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-D：生成 F1D_F2_ENTRY_GATES.json（从 D2 门禁 + D3 阻塞 + D2 冲突派生）。"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
GATES = F / "F1C_D2_F2_GATES.json"
CONF = F / "F1C_D2_CONFLICT_RESOLUTIONS.json"
FRZ = F / "F1C_D3_FREEZE_READINESS.json"
AUD = F / "F1C_D3_PROVENANCE_LICENSE_AUDIT.json"
OUT = F / "F1D_F2_ENTRY_GATES.json"

# 三类阻塞范围
SCOPE_FREEZE = "architecture_freeze"     # 阻塞架构冻结
SCOPE_IMPL = "implementation"            # 阻塞某项实现
SCOPE_DIST = "distribution"              # 阻塞对外分发


def main() -> int:
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    frz = json.loads(FRZ.read_text(encoding="utf-8"))
    aud = json.loads(AUD.read_text(encoding="utf-8"))

    out = []

    # ── D2 的 30 条门禁
    for g in gates["gates"]:
        # F1 阶段门禁在冻结时已由结构检查满足；F2 阶段仍未满足
        scope = SCOPE_IMPL
        status = "SATISFIED_AT_FREEZE" if g["stage"] == "F1" else "OPEN_PENDING_F2"
        out.append({
            "gate_id": g["gate_id"],
            "owner": g["owner"],
            "prerequisite": f"F1-C-D2 {g['conflict_id']} 架构裁决",
            "verification_method": "实测（真实执行）" if g["stage"] == "F2"
                                   else "结构检查（已在 F1-D 复核）",
            "required_evidence": g["criterion"],
            "blocking_scope": scope,
            "stage": g["stage"],
            "status": status,
        })

    # ── Y-6 六个探测
    for p in gates["y6_probes"]:
        out.append({
            "gate_id": p["probe_id"],
            "owner": p["owner"],
            "prerequisite": "F1-C-D2 Y-6 裁决",
            "verification_method": "运行时探测（真实调用 BotHarness/DSH 接口）",
            "required_evidence": p["pass_criterion"],
            "blocking_scope": SCOPE_IMPL,
            "stage": "F2",
            "status": "OPEN_PENDING_F2",
            "fail_fallback": p["fail_fallback"],
            "no_go_if": p["no_go_if"],
        })

    # ── 三条许可/分发门禁（来自 D3 blockers）
    lic_map = {
        "B-1": ("第三方声明措辞", "F5 重写总述为分层表述；不改历史审计",
                "THIRD_PARTY_NOTICES.md 修订稿 + 分层表述核对"),
        "B-2": ("UPSTREAM-06 抽象/表达边界", "法务判断（U06 审计 U10）",
                "法务意见书或明确的保守立场确认"),
        "B-3": ("SL-CAP-0023 CC BY 4.0 署名", "分发物中落地署名 + 许可链接 + 修改声明",
                "分发物含署名段落与许可链接"),
    }
    for b in frz["blockers"]:
        topic, method, ev = lic_map[b["id"]]
        out.append({
            "gate_id": f"{b['id']}-DIST",
            "owner": "Security" if b["id"] != "B-1" else "DSH-Adapter",
            "prerequisite": f"F1-C-D3 {b['id']} 登记",
            "verification_method": method,
            "required_evidence": ev,
            "blocking_scope": SCOPE_DIST,
            "stage": "PRE_DISTRIBUTION",
            "status": "OPEN",
            "note": b["detail"],
            "does_not_block": "内部设计冻结（F1-D 已按 FROZEN_INTERNAL_RESTRICTED 完成）",
        })

    # ── X-5 的崩溃注入与并发（属实现门禁，单列强调）
    out.append({
        "gate_id": "X-5-CRASH-INJECT",
        "owner": "Storage",
        "prerequisite": "F1-C-D2 X-5 架构裁决（契约已定，实现未验证）",
        "verification_method": "崩溃注入（kill 进程 / 磁盘满）+ 并发 CAS 压测，真实执行",
        "required_evidence": "重启后权威位置为上一份已提交状态；并发两 writer 一方成功一方明确 conflict",
        "blocking_scope": SCOPE_IMPL,
        "stage": "F2",
        "status": "OPEN_PENDING_F2",
        "note": "设计要求事务 ≠ 已验证事务正确",
    })
    # ── K-7 人工文档写入限制
    out.append({
        "gate_id": "K-7-HUMAN-DOC",
        "owner": "Renderer",
        "prerequisite": "F1-C-D2 K-7 裁决",
        "verification_method": "代码路径检查 + 若实现局部插入则三条拒绝用例",
        "required_evidence": "F1/F2 中不存在写人工文档的代码路径；F2 若实现须有授权/版本/冲突三条拒绝用例",
        "blocking_scope": SCOPE_IMPL,
        "stage": "F2",
        "status": "OPEN_PENDING_F2",
    })
    # ── EC 离线评测基线
    out.append({
        "gate_id": "EC-EVAL-BASELINE",
        "owner": "Evidence-Claims",
        "prerequisite": "SL-CAP-0075（F1-C-C1 新建）",
        "verification_method": "离线复算评测集与确定性指标（V1 不使用付费 API）",
        "required_evidence": "eval_record{基准集版本, 指标名与数值, 被测判据版本, 运行快照}",
        "blocking_scope": SCOPE_IMPL,
        "stage": "F2",
        "status": "OPEN_PENDING_F2",
    })

    doc = {
        "artifact": "F1D_F2_ENTRY_GATES",
        "schema_version": 1,
        "generated_by": "tools/fusion/f1d_entry_gates.py",
        "principle": ("三类阻塞范围必须分开：architecture_freeze / implementation / distribution。"
                      "**不得因为某项在 F2 实测，就把它描述为 F1 阶段已验证。**"),
        "blocking_scope_definition": {
            SCOPE_FREEZE: "阻塞架构冻结（当前为 0 条——结构不变量全部满足）",
            SCOPE_IMPL: "阻塞正式开发中的该项实现，不阻塞内部设计冻结",
            SCOPE_DIST: "阻塞对外分发，不阻塞内部设计冻结",
        },
        "gates": out,
        "stats": {},
        "f2_entry_conditions": [
            "F1-D 冻结完成（当前：FROZEN_INTERNAL_RESTRICTED）",
            "用户明确批准启动 F2（**本轮未启动**）",
            "F2 首项任务须先跑 Y6-P1..P6 探测，失败走全自建路径",
        ],
        "prohibitions_in_f1d": [
            "未创建正式 Skill", "未实现产品引擎", "未创建数据库", "未安装依赖",
            "未修改运行时配置", "未推送公开仓库", "未创建远程 Release",
        ],
    }
    from collections import Counter
    doc["stats"] = {
        "total": len(out),
        "by_scope": dict(sorted(Counter(g["blocking_scope"] for g in out).items())),
        "by_status": dict(sorted(Counter(g["status"] for g in out).items())),
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gates={len(out)}  by_scope={doc['stats']['by_scope']}")
    print(f"  by_status={doc['stats']['by_status']}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
