#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D1：终态模型迁移（导出迁移快照）。

终态推导已并入 f1c_apply_routed.py（通过 f1c_terminal_model.derive），
因此任何重跑应用链都会重新生成终态，不会丢失。
本工具职责：跑一次应用链，然后把终态快照导出成独立的迁移记录文件。

用法：python3 tools/fusion/f1c_d1_migrate_terminal.py [--dry-run]
"""
import json, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
OUT = F / "F1C_D1_TERMINAL_MIGRATION.json"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not dry:
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "f1c_apply_routed.py")],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"ERROR: 应用链失败\n{r.stdout}\n{r.stderr}")

    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    tm = draft.get("terminal_model")
    if not tm or len(tm.get("terminal_dispositions", {})) != 143:
        raise SystemExit("ERROR: 应用链未产出 143 项终态，数据不支持，按第 8 节阻止标记 DONE")

    g = draft["global_state_counts"]
    mig = {
        "artifact": "F1C_D1_TERMINAL_MIGRATION",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d1_migrate_terminal.py",
        "principle": ("三个正交概念：mapping_status（进度） / terminal_disposition（设计终态） / "
                      "canonical_origin_type（来源性质）。不手填、不默认 ADOPTED、不依赖遍历顺序。"),
        "derivation_owner": "f1c_terminal_model.derive（由 f1c_apply_routed.py 在写盘前调用）",
        "source_chain": ["F1B_FROZEN_BASELINE.json", "F1-C-B", "F1-C-C1", "F1-C-C2", "F1-C-C3"],
        "totals": {
            "identities": len(tm["terminal_dispositions"]),
            "canonicals": len(tm["canonical_origins"]),
            "terminal_disposition_distribution": g["terminal_disposition_counts"],
            "canonical_origin_distribution": g["canonical_origin_counts"],
            "adoption_role_distribution": g["adoption_role_counts"],
            "mapping_status_distribution": {
                "MAPPED": g["mapped_count"],
                "ROUTED": g["routed_pending_count"],
                "UNREVIEWED": g["unreviewed_count"],
            },
        },
        "laws": tm["laws"],
        "terminal_dispositions": tm["terminal_dispositions"],
        "canonical_origins": tm["canonical_origins"],
    }
    if not dry:
        OUT.write_text(json.dumps(mig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"written -> {OUT.name}")
    else:
        print("(dry-run，未写盘)")
    print(f"identities={mig['totals']['identities']} canonicals={mig['totals']['canonicals']}")
    print(f"  terminal: {mig['totals']['terminal_disposition_distribution']}")
    print(f"  origin  : {mig['totals']['canonical_origin_distribution']}")
    print(f"  role    : {mig['totals']['adoption_role_distribution']}")
    print(f"  mapping : {mig['totals']['mapping_status_distribution']}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
